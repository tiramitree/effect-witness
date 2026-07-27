"""Fail-closed path ownership helpers for the real filesystem lane."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import time
from pathlib import Path

from .artifact import _is_link_or_reparse

_REMOVE_ATTEMPTS = 50
_WINDOWS_REMOVE_RETRY_DELAY_SECONDS = 0.1
_WINDOWS_TRANSIENT_REMOVE_ERRORS = frozenset({5, 32, 33})


def _absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _comparison_path(path: str | Path) -> Path:
    """Return a normalized path used only for containment comparisons."""

    raw = os.path.realpath(os.path.abspath(os.fspath(path)))
    if os.name == "nt":
        if raw.startswith("\\\\?\\UNC\\"):
            raw = "\\\\" + raw[8:]
        elif raw.startswith("\\\\?\\"):
            raw = raw[4:]
        raw = os.path.normcase(raw)
    return Path(raw)


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


def _is_retryable_remove_error(error: OSError) -> bool:
    return (
        os.name == "nt"
        and isinstance(error, PermissionError)
        and getattr(error, "winerror", None) in _WINDOWS_TRANSIENT_REMOVE_ERRORS
    )


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


def ensure_disjoint_paths(
    first: str | Path,
    second: str | Path,
    *,
    label: str,
) -> tuple[Path, Path]:
    """Return absolute paths only when neither target contains the other."""

    first_path = _absolute(first)
    second_path = _absolute(second)
    first_comparison = _comparison_path(first_path)
    second_comparison = _comparison_path(second_path)
    if (
        first_comparison == second_comparison
        or first_comparison in second_comparison.parents
        or second_comparison in first_comparison.parents
    ):
        raise ValueError(f"{label} must not overlap")
    return first_path, second_path


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

    for attempt in range(_REMOVE_ATTEMPTS):
        if _metadata(path) is None:
            return
        _assert_ordinary_directory(path, label=label)
        try:
            shutil.rmtree(deletion_path, onerror=ignore_disappeared_child)
        except FileNotFoundError:
            continue
        except OSError as exc:
            if _is_retryable_remove_error(exc) and attempt + 1 < _REMOVE_ATTEMPTS:
                time.sleep(_WINDOWS_REMOVE_RETRY_DELAY_SECONDS)
                continue
            raise RuntimeError(
                f"cannot remove {label} ({type(exc).__name__})"
            ) from None
    if _metadata(path) is not None:
        raise RuntimeError(f"{label} still exists after bounded cleanup")


def remove_owned_directories(
    targets: list[tuple[Path | None, str]],
) -> None:
    """Attempt every exact cleanup and fail only when a target remains."""

    failed: list[tuple[Path, str]] = []
    for path, label in targets:
        if path is None:
            continue
        try:
            remove_owned_directory(path, label=label)
        except Exception:
            failed.append((path, label))
    unresolved = False
    for path, _label in failed:
        try:
            unresolved = _metadata(path) is not None or unresolved
        except RuntimeError:
            unresolved = True
    if unresolved:
        raise RuntimeError("one or more owned directories remain after cleanup")


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
