"""Fail-closed path ownership helpers for the real filesystem lane."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

from .artifact import _is_link_or_reparse


def _absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _metadata(path: Path) -> os.stat_result | None:
    try:
        return path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError(
            f"cannot inspect {type(exc).__name__} path boundary"
        ) from None


def _assert_ordinary_directory(path: Path, *, label: str) -> None:
    metadata = _metadata(path)
    if (
        metadata is None
        or not stat.S_ISDIR(metadata.st_mode)
        or _is_link_or_reparse(path)
    ):
        raise RuntimeError(f"{label} is not an ordinary directory")


def _ensure_safe_parent_chain(target: Path, *, label: str) -> None:
    missing: list[Path] = []
    current = target.parent
    while True:
        metadata = _metadata(current)
        if metadata is None:
            missing.append(current)
        else:
            _assert_ordinary_directory(current, label=f"{label} parent")
        if current.parent == current:
            break
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except OSError as exc:
            raise RuntimeError(
                f"cannot create {label} parent ({type(exc).__name__})"
            ) from None
        _assert_ordinary_directory(directory, label=f"{label} parent")


def new_directory_target(path: str | Path, *, label: str) -> Path:
    """Return an absolute absent target below an ordinary parent chain."""

    target = _absolute(path)
    if _metadata(target) is not None:
        raise FileExistsError(f"{label} must be absent")
    _ensure_safe_parent_chain(target, label=label)
    if _metadata(target) is not None:
        raise FileExistsError(f"{label} must remain absent")
    return target


def create_owned_directory(path: str | Path, *, label: str) -> Path:
    target = new_directory_target(path, label=label)
    try:
        target.mkdir()
    except OSError as exc:
        raise RuntimeError(f"cannot create {label} ({type(exc).__name__})") from None
    _assert_ordinary_directory(target, label=label)
    return target


def create_staging_directory(
    final_path: str | Path,
    *,
    label: str,
) -> tuple[Path, Path]:
    final = new_directory_target(final_path, label=label)
    try:
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{final.name}.staging-",
                dir=final.parent,
            )
        )
    except OSError as exc:
        raise RuntimeError(
            f"cannot create {label} staging directory ({type(exc).__name__})"
        ) from None
    _assert_ordinary_directory(staging, label=f"{label} staging directory")
    return final, staging


def remove_owned_directory(path: Path, *, label: str) -> None:
    """Remove only an exact ordinary root created by the current operation."""

    if _metadata(path) is None:
        return
    _assert_ordinary_directory(path, label=label)

    def ignore_disappeared_child(_function, _failed_path, error_info) -> None:
        error = error_info[1]
        if isinstance(error, FileNotFoundError):
            return
        raise error

    deletion_path = path
    if os.name == "nt":
        raw = os.fspath(path)
        if raw.startswith("\\\\"):
            raw = "\\\\?\\UNC\\" + raw.lstrip("\\")
        elif not raw.startswith("\\\\?\\"):
            raw = "\\\\?\\" + raw
        deletion_path = Path(raw)

    for _attempt in range(3):
        if _metadata(path) is None:
            return
        _assert_ordinary_directory(path, label=label)
        try:
            shutil.rmtree(deletion_path, onerror=ignore_disappeared_child)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RuntimeError(
                f"cannot remove {label} ({type(exc).__name__})"
            ) from None
    if _metadata(path) is not None:
        raise RuntimeError(f"{label} still exists after bounded cleanup")


def publish_staging_directory(
    staging: Path,
    final: Path,
    *,
    label: str,
) -> None:
    """Atomically publish a complete same-parent directory."""

    _assert_ordinary_directory(staging, label=f"{label} staging directory")
    _ensure_safe_parent_chain(final, label=label)
    if staging.parent != final.parent:
        raise RuntimeError(f"{label} staging directory is not a sibling")
    if _metadata(final) is not None:
        raise FileExistsError(f"{label} must remain absent")
    try:
        os.replace(staging, final)
    except OSError as exc:
        raise RuntimeError(f"cannot publish {label} ({type(exc).__name__})") from None
    _assert_ordinary_directory(final, label=label)
