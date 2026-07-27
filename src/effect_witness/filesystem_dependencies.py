"""Fail-closed checks for the separately installed filesystem server."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact import _is_link_or_reparse
from .filesystem_registration import (
    FILESYSTEM_PACKAGE,
    JAVASCRIPT_SDK,
    NODE_VERSION,
    PACKAGE_JSON_SHA256,
    PACKAGE_LOCK_SHA256,
    SERVER_DISTRIBUTION_FILES,
)
from .models import strict_json_loads


@dataclass(frozen=True)
class FilesystemDependency:
    """Validated runtime paths; paths are never serialized into evidence."""

    dependency_root: Path
    node_command: str
    server_entrypoint: Path
    lockfile_sha256: str
    node_version: str


def _regular_file(path: Path, *, label: str) -> bytes:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValueError(f"{label} is unavailable ({type(exc).__name__})") from None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or _is_link_or_reparse(path)
        or metadata.st_size > 2 * 1024 * 1024
    ):
        raise ValueError(f"{label} is not an accepted regular file")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{label} cannot be read ({type(exc).__name__})") from None


def _json_object(content: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = strict_json_loads(content.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"{label} is invalid ({type(exc).__name__})") from None
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not a JSON object")
    return value


def _lock_package(lock: dict[str, Any], key: str) -> dict[str, Any]:
    packages = lock.get("packages")
    if not isinstance(packages, dict) or not isinstance(packages.get(key), dict):
        raise ValueError("package lock is missing a registered dependency")
    return packages[key]


def verify_lock_bytes(
    package_json: bytes,
    package_lock: bytes,
) -> dict[str, Any]:
    """Verify the exact package input and lock closure used by the lane."""

    if hashlib.sha256(package_json).hexdigest() != PACKAGE_JSON_SHA256:
        raise ValueError("integration package.json differs from registration")
    if hashlib.sha256(package_lock).hexdigest() != PACKAGE_LOCK_SHA256:
        raise ValueError("integration package lock differs from registration")
    lock = _json_object(package_lock, label="integration package lock")
    if lock.get("lockfileVersion") != 3:
        raise ValueError("integration package lock version differs from registration")
    server = _lock_package(
        lock,
        "node_modules/@modelcontextprotocol/server-filesystem",
    )
    sdk = _lock_package(lock, "node_modules/@modelcontextprotocol/sdk")
    if (
        server.get("version") != FILESYSTEM_PACKAGE["version"]
        or server.get("integrity") != FILESYSTEM_PACKAGE["npm_sri"]
        or server.get("license") != FILESYSTEM_PACKAGE["npm_license_field"]
    ):
        raise ValueError("filesystem package lock entry differs from registration")
    if (
        sdk.get("version") != JAVASCRIPT_SDK["version"]
        or sdk.get("integrity") != JAVASCRIPT_SDK["npm_sri"]
        or sdk.get("license") != JAVASCRIPT_SDK["license_field"]
    ):
        raise ValueError("JavaScript SDK lock entry differs from registration")
    return {
        "javascript_sdk_version": sdk["version"],
        "lockfile_sha256": PACKAGE_LOCK_SHA256,
        "lockfile_version": 3,
        "server_package_version": server["version"],
    }


def _minimal_process_environment() -> dict[str, str]:
    environment: dict[str, str] = {}
    for key in ("COMSPEC", "SYSTEMROOT", "WINDIR"):
        value = os.environ.get(key)
        if value:
            environment[key] = value
    if os.name != "nt":
        environment["LANG"] = "C.UTF-8"
        environment["LC_ALL"] = "C.UTF-8"
    return environment


def _resolve_executable(command: str, *, label: str) -> str:
    found = shutil.which(command)
    if found is None:
        raise ValueError(f"{label} executable is unavailable")
    try:
        resolved = Path(found).resolve(strict=True)
        metadata = resolved.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValueError(
            f"{label} executable cannot be resolved ({type(exc).__name__})"
        ) from None
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} executable is not a regular file")
    return str(resolved)


def _command_version(
    command: str,
    flag: str,
    *,
    label: str,
    path_entries: tuple[str, ...] = (),
) -> str:
    executable = _resolve_executable(command, label=label)
    environment = _minimal_process_environment()
    if path_entries:
        environment["PATH"] = os.pathsep.join(path_entries)
    try:
        completed = subprocess.run(
            [executable, flag],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
            text=True,
            encoding="utf-8",
            errors="strict",
            env=environment,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise ValueError(
            f"{label} version check failed ({type(exc).__name__})"
        ) from None
    if completed.returncode != 0:
        raise ValueError(f"{label} version check returned a nonzero status")
    return completed.stdout.strip()


def verify_dependency_directory(
    dependency_dir: str | Path,
    *,
    node_command: str,
) -> FilesystemDependency:
    """Bind an installed server to the registered package lock and Node."""

    root = Path(os.path.abspath(os.fspath(dependency_dir)))
    if not root.is_dir() or _is_link_or_reparse(root):
        raise ValueError("dependency directory is not an accepted directory")
    package_json = _regular_file(root / "package.json", label="package.json")
    package_lock = _regular_file(root / "package-lock.json", label="package-lock.json")
    registration = verify_lock_bytes(package_json, package_lock)
    server_root = root / "node_modules" / "@modelcontextprotocol" / "server-filesystem"
    installed_package = _json_object(
        _regular_file(server_root / "package.json", label="installed server metadata"),
        label="installed server metadata",
    )
    if (
        installed_package.get("name") != FILESYSTEM_PACKAGE["name"]
        or installed_package.get("version") != FILESYSTEM_PACKAGE["version"]
        or installed_package.get("license") != FILESYSTEM_PACKAGE["npm_license_field"]
    ):
        raise ValueError("installed server metadata differs from registration")
    _verify_server_distribution(server_root)
    entrypoint = server_root / "dist" / "index.js"
    node_version = _command_version(node_command, "--version", label="Node")
    if node_version != NODE_VERSION:
        raise ValueError("Node version differs from registration")
    return FilesystemDependency(
        dependency_root=root,
        node_command=_resolve_executable(node_command, label="Node"),
        server_entrypoint=entrypoint,
        lockfile_sha256=registration["lockfile_sha256"],
        node_version=node_version,
    )


def _verify_server_distribution(server_root: Path) -> None:
    actual_files: dict[str, tuple[int, str]] = {}
    for candidate in sorted(server_root.rglob("*")):
        relative = candidate.relative_to(server_root).as_posix()
        if candidate.is_dir():
            if _is_link_or_reparse(candidate):
                raise ValueError("installed server contains a linked directory")
            continue
        content = _regular_file(candidate, label="installed server distribution file")
        actual_files[relative] = (
            len(content),
            hashlib.sha256(content).hexdigest(),
        )
    if actual_files != SERVER_DISTRIBUTION_FILES:
        raise ValueError("installed server distribution differs from registration")
