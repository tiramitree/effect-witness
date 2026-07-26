"""Shared types and canonical serialization helpers."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Any


class ContractResult(StrEnum):
    """Result vocabulary that avoids claiming official protocol certification."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ClientOutcome(StrEnum):
    """What the client knows, independent of the server-side effect fact."""

    SUCCEEDED = "SUCCEEDED"
    FAILED_PRECOMMIT = "FAILED_PRECOMMIT"
    UNKNOWN = "UNKNOWN"
    COMMITTED_CONFIRMED = "COMMITTED_CONFIRMED"
    ABSENT_CONFIRMED = "ABSENT_CONFIRMED"
    UNRESOLVED = "UNRESOLVED"


class FaultMode(StrEnum):
    """Deterministic fixture faults. They are available only in test mode."""

    CLEAN = "clean"
    PRE_COMMIT_EXIT = "pre_commit_exit"
    POST_COMMIT_DELAY = "post_commit_delay"
    POST_COMMIT_EXIT = "post_commit_exit"


class ToolStrategy(StrEnum):
    """Reference implementation behavior, not a framework ranking."""

    UNSAFE = "unsafe"
    STABLE_OPERATION = "stable_operation"


class PayloadConflict(ValueError):
    """A stable operation identifier was reused with a different payload."""


class AttemptBindingError(ValueError):
    """An attempt was committed against a different tool or operation."""


class AttemptStateError(RuntimeError):
    """An attempt was committed from a non-receivable terminal state."""


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data deterministically."""

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    """Hash the canonical JSON representation of a value."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


def strict_json_loads(value: str) -> Any:
    """Load strict JSON with unique keys and finite standard numbers only."""

    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonstandard_constant,
        parse_float=_finite_float,
    )


def json_exact_equal(left: Any, right: Any) -> bool:
    """Compare parsed JSON values without Python's bool/int coercion."""

    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            json_exact_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            json_exact_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right
