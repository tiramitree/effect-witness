"""Exact, non-executing verification for the registered mini-swe-agent wheel."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .artifact import _is_link_or_reparse
from .models import json_exact_equal, strict_json_loads

MINI_SWE_AGENT_PACKAGE: Final = "mini-swe-agent"
MINI_SWE_AGENT_VERSION: Final = "2.4.6"
MINI_SWE_AGENT_WHEEL_FILENAME: Final = "mini_swe_agent-2.4.6-py3-none-any.whl"
MINI_SWE_AGENT_WHEEL_URL: Final = (
    "https://files.pythonhosted.org/packages/a2/00/"
    "a2f454775f69f540ab529c5f5e35d672f6491f0e6edab7cb196a0d2a0e2e/"
    "mini_swe_agent-2.4.6-py3-none-any.whl"
)
MINI_SWE_AGENT_WHEEL_BYTES: Final = 115037
MINI_SWE_AGENT_WHEEL_SHA256: Final = (
    "a35463c553ac825c7773b03cfa69cd44958e3af20155dcc5711fdf9e4c67cd54"
)
MINI_SWE_AGENT_PROVENANCE_SHA256: Final = (
    "f4f892dbf9227941116a9c3f3590aa20044b5d38c83e3134116c48f7a6e1a4db"
)
MINI_SWE_AGENT_LICENSE: Final = "MIT"
MINI_SWE_AGENT_DEVELOPMENT_STATUS: Final = "Alpha"
MINI_SWE_AGENT_PYTHON_REQUIRES: Final = ">=3.10"

_PROVENANCE_MAX_BYTES = 16 * 1024
_HASH_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class MiniSweWheel:
    """A wheel whose exact registered bytes have been verified."""

    path: Path
    version: str
    sha256: str
    bytes: int


def expected_mini_swe_provenance() -> dict[str, object]:
    """Return the exact public metadata registered for the wheel."""

    return {
        "development_status": MINI_SWE_AGENT_DEVELOPMENT_STATUS,
        "filename": MINI_SWE_AGENT_WHEEL_FILENAME,
        "license": MINI_SWE_AGENT_LICENSE,
        "package": MINI_SWE_AGENT_PACKAGE,
        "python_requires": MINI_SWE_AGENT_PYTHON_REQUIRES,
        "sha256": MINI_SWE_AGENT_WHEEL_SHA256,
        "size_bytes": MINI_SWE_AGENT_WHEEL_BYTES,
        "url": MINI_SWE_AGENT_WHEEL_URL,
        "version": MINI_SWE_AGENT_VERSION,
    }


def verify_wheel_provenance_bytes(content: bytes) -> dict[str, Any]:
    """Require the checked-in provenance to match the runtime registration."""

    if len(content) > _PROVENANCE_MAX_BYTES:
        raise ValueError("mini-swe-agent provenance is too large")
    try:
        parsed = strict_json_loads(content.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(
            f"mini-swe-agent provenance is invalid ({type(exc).__name__})"
        ) from None
    expected = expected_mini_swe_provenance()
    if not isinstance(parsed, dict) or not json_exact_equal(parsed, expected):
        raise ValueError("mini-swe-agent provenance differs from registration")
    return parsed


def _wheel_metadata(path: Path) -> os.stat_result:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValueError(
            f"mini-swe-agent wheel is unavailable ({type(exc).__name__})"
        ) from None
    if not stat.S_ISREG(metadata.st_mode) or _is_link_or_reparse(path):
        raise ValueError("mini-swe-agent wheel is not an accepted regular file")
    return metadata


def verify_mini_swe_wheel(path: str | Path) -> MiniSweWheel:
    """Recheck the registered filename, size, and SHA-256 without extraction."""

    wheel = Path(os.path.abspath(os.fspath(path)))
    if wheel.name != MINI_SWE_AGENT_WHEEL_FILENAME:
        raise ValueError("mini-swe-agent wheel filename differs from registration")
    before = _wheel_metadata(wheel)
    if before.st_size != MINI_SWE_AGENT_WHEEL_BYTES:
        raise ValueError("mini-swe-agent wheel size differs from registration")

    digest = hashlib.sha256()
    try:
        with wheel.open("rb") as stream:
            while chunk := stream.read(_HASH_CHUNK_BYTES):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(
            f"mini-swe-agent wheel cannot be read ({type(exc).__name__})"
        ) from None

    after = _wheel_metadata(wheel)
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if before_identity != after_identity:
        raise ValueError("mini-swe-agent wheel changed during verification")
    if digest.hexdigest() != MINI_SWE_AGENT_WHEEL_SHA256:
        raise ValueError("mini-swe-agent wheel digest differs from registration")
    return MiniSweWheel(
        path=wheel,
        version=MINI_SWE_AGENT_VERSION,
        sha256=MINI_SWE_AGENT_WHEEL_SHA256,
        bytes=MINI_SWE_AGENT_WHEEL_BYTES,
    )
