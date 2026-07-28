"""Exact installed-version gate for the schema-v5 Python 3.12 snapshot."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import re
import sys
from pathlib import Path

from .artifact import _is_link_or_reparse
from .coding_registration import (
    PYTHON_CONSTRAINT_PACKAGE_COUNT,
    PYTHON_CONSTRAINTS_SHA256,
)

_CONSTRAINT = re.compile(
    r"^(?P<name>[a-z0-9][a-z0-9._-]*)=="
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)"
    r"(?P<windows> ; sys_platform == \"win32\")?$"
)
_MAX_CONSTRAINT_BYTES = 32 * 1024


def _canonical_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def verify_coding_constraints(path: str | Path) -> dict[str, int]:
    """Bind exact bytes and every applicable installed distribution."""

    constraint_path = Path(os.path.abspath(os.fspath(path)))
    if not constraint_path.is_file() or _is_link_or_reparse(constraint_path):
        raise RuntimeError("coding-agent constraint snapshot is not ordinary")
    try:
        content = constraint_path.read_bytes()
    except OSError as error:
        raise RuntimeError(
            f"coding-agent constraint snapshot is unreadable ({type(error).__name__})"
        ) from None
    if (
        not content
        or len(content) > _MAX_CONSTRAINT_BYTES
        or b"\r" in content
        or not content.endswith(b"\n")
        or hashlib.sha256(content).hexdigest() != PYTHON_CONSTRAINTS_SHA256
    ):
        raise RuntimeError(
            "coding-agent constraint snapshot bytes differ from registration"
        )
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeError as error:
        raise RuntimeError(
            f"coding-agent constraint snapshot is not UTF-8 ({type(error).__name__})"
        ) from None
    registrations: dict[str, tuple[str, bool]] = {}
    for line in lines:
        if line.startswith("#"):
            continue
        match = _CONSTRAINT.fullmatch(line)
        if match is None:
            raise RuntimeError("coding-agent constraint line differs from registration")
        name = _canonical_distribution_name(match.group("name"))
        if name in registrations:
            raise RuntimeError("coding-agent constraint snapshot contains a duplicate")
        registrations[name] = (
            match.group("version"),
            match.group("windows") is not None,
        )
    if len(registrations) != PYTHON_CONSTRAINT_PACKAGE_COUNT:
        raise RuntimeError(
            "coding-agent constraint package count differs from registration"
        )
    applicable = {
        name: version
        for name, (version, windows_only) in registrations.items()
        if not windows_only or sys.platform == "win32"
    }
    try:
        observed = {name: importlib.metadata.version(name) for name in applicable}
    except importlib.metadata.PackageNotFoundError:
        raise RuntimeError(
            "an applicable coding-agent distribution is unavailable"
        ) from None
    if observed != applicable:
        raise RuntimeError(
            "installed coding-agent versions differ from the constraint snapshot"
        )
    return {
        "applicable_package_count": len(applicable),
        "registered_package_count": len(registrations),
    }
