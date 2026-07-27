"""Pure registered semantics for schema-v3 filesystem evidence."""

from __future__ import annotations

import hashlib
from typing import Any, Final

from .models import json_exact_equal, sha256_json

FIXTURE: Final = b"alpha\nbeta\n"
EDITED: Final = b"alpha\ngamma\n"
FIXTURE_SHA256: Final = hashlib.sha256(FIXTURE).hexdigest()
EDITED_SHA256: Final = hashlib.sha256(EDITED).hexdigest()


def _expected_file(relative: str, content: bytes) -> dict[str, Any]:
    return {
        "bytes": len(content),
        "kind": "file",
        "path": relative,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _tree(entries: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(entries, key=lambda item: item["path"])
    return {"entries": ordered, "tree_sha256": sha256_json(ordered)}


def _call_shape(call: dict[str, Any], *, error: bool, read_result: bool) -> bool:
    if (
        call.get("completed") is not True
        or call.get("exception_types") != []
        or call.get("is_error") is not error
        or call.get("content_types") != ["text"]
        or call.get("text_block_count") != 1
        or call.get("response_text_included") is not False
        or call.get("structured_content_present") is not (not error)
    ):
        return False
    if read_result:
        return (
            call.get("text_bytes") == len(FIXTURE)
            and call.get("text_sha256") == FIXTURE_SHA256
            and "response_text_redacted" not in call
        )
    return (
        call.get("response_text_redacted") is True
        and "text_bytes" not in call
        and "text_sha256" not in call
    )


def evaluate_scenario(
    scenario_id: str,
    *,
    first: dict[str, Any],
    second: dict[str, Any],
    s0: dict[str, Any],
    s1: dict[str, Any],
    s2: dict[str, Any],
    platform_system: str,
) -> tuple[dict[str, bool], str]:
    """Recompute the exact registered relationship without executing tools."""

    checks: dict[str, bool] = {
        "s0_hash_is_valid": s0.get("tree_sha256") == sha256_json(s0.get("entries")),
        "s1_hash_is_valid": s1.get("tree_sha256") == sha256_json(s1.get("entries")),
        "s2_hash_is_valid": s2.get("tree_sha256") == sha256_json(s2.get("entries")),
    }
    if scenario_id == "read_text_file":
        expected = _tree([_expected_file("fixture.txt", FIXTURE)])
        checks.update(
            {
                "first_call_registered": _call_shape(
                    first, error=False, read_result=True
                ),
                "second_call_registered": _call_shape(
                    second, error=False, read_result=True
                ),
                "s0_registered": json_exact_equal(s0, expected),
                "s0_equals_s1": json_exact_equal(s0, s1),
                "s1_equals_s2": json_exact_equal(s1, s2),
            }
        )
        return checks, "CONSISTENT_WITH_READ_ONLY_HINT_ON_REGISTERED_INPUT"
    if scenario_id == "create_directory":
        expected_s0 = _tree([])
        expected_effect = _tree([{"kind": "directory", "path": "new-dir"}])
        checks.update(
            {
                "first_call_registered": _call_shape(
                    first, error=False, read_result=False
                ),
                "second_call_registered": _call_shape(
                    second, error=False, read_result=False
                ),
                "s0_registered": json_exact_equal(s0, expected_s0),
                "s1_registered": json_exact_equal(s1, expected_effect),
                "s0_differs_s1": not json_exact_equal(s0, s1),
                "s1_equals_s2": json_exact_equal(s1, s2),
            }
        )
        return checks, "CONSISTENT_WITH_IDEMPOTENT_HINT_ON_REGISTERED_INPUT"
    if scenario_id == "write_file":
        expected_s0 = _tree([])
        expected_effect = _tree([_expected_file("document.txt", FIXTURE)])
        checks.update(
            {
                "first_call_registered": _call_shape(
                    first, error=False, read_result=False
                ),
                "second_call_registered": _call_shape(
                    second, error=False, read_result=False
                ),
                "s0_registered": json_exact_equal(s0, expected_s0),
                "s1_registered": json_exact_equal(s1, expected_effect),
                "s0_differs_s1": not json_exact_equal(s0, s1),
                "s1_equals_s2": json_exact_equal(s1, s2),
            }
        )
        return checks, "CONSISTENT_WITH_IDEMPOTENT_HINT_ON_REGISTERED_INPUT"
    if scenario_id == "edit_file":
        expected_s0 = _tree([_expected_file("document.txt", FIXTURE)])
        expected_effect = _tree([_expected_file("document.txt", EDITED)])
        checks.update(
            {
                "first_call_registered": _call_shape(
                    first, error=False, read_result=False
                ),
                "second_call_registered": _call_shape(
                    second, error=True, read_result=False
                ),
                "s0_registered": json_exact_equal(s0, expected_s0),
                "s1_registered": json_exact_equal(s1, expected_effect),
                "s0_differs_s1": not json_exact_equal(s0, s1),
                "s1_equals_s2": json_exact_equal(s1, s2),
            }
        )
        return checks, "REPEAT_RETURNED_ERROR_AFTER_FIRST_VISIBLE_EFFECT"
    if scenario_id != "create_directory_nested_claim":
        raise ValueError("unregistered filesystem scenario")
    empty = _tree([])
    nested = _tree(
        [
            {"kind": "directory", "path": "parent"},
            {"kind": "directory", "path": "parent/child"},
        ]
    )
    error_observation = (
        _call_shape(first, error=True, read_result=False)
        and _call_shape(second, error=True, read_result=False)
        and json_exact_equal(s0, empty)
        and json_exact_equal(s0, s1)
        and json_exact_equal(s1, s2)
    )
    success_observation = (
        _call_shape(first, error=False, read_result=False)
        and _call_shape(second, error=False, read_result=False)
        and json_exact_equal(s0, empty)
        and json_exact_equal(s1, nested)
        and not json_exact_equal(s0, s1)
        and json_exact_equal(s1, s2)
    )
    if platform_system == "Windows":
        platform_accepts = error_observation
    elif platform_system == "Linux":
        platform_accepts = error_observation or success_observation
    else:
        platform_accepts = False
    checks.update(
        {
            "description_claim_registered": True,
            "platform_registered": platform_system in {"Linux", "Windows"},
            "platform_observation_registered": platform_accepts,
        }
    )
    if error_observation:
        outcome = "ERROR_WITH_NO_VISIBLE_BYTE_TREE_EFFECT"
    elif success_observation:
        outcome = "NESTED_DIRECTORIES_CREATED"
    else:
        outcome = "UNREGISTERED_OBSERVATION"
    return checks, outcome


def registered_stimulus(
    scenario_id: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return tool name, public relative stimulus, and in-process argument template."""

    if scenario_id == "read_text_file":
        return (
            "read_text_file",
            {"relative_path": "fixture.txt"},
            {"path": "fixture.txt"},
        )
    if scenario_id == "create_directory":
        return (
            "create_directory",
            {"relative_path": "new-dir"},
            {"path": "new-dir"},
        )
    if scenario_id == "create_directory_nested_claim":
        return (
            "create_directory",
            {"relative_path": "parent/child"},
            {"path": "parent/child"},
        )
    if scenario_id == "write_file":
        return (
            "write_file",
            {
                "content_bytes": len(FIXTURE),
                "content_sha256": FIXTURE_SHA256,
                "relative_path": "document.txt",
            },
            {"content": FIXTURE.decode("utf-8"), "path": "document.txt"},
        )
    if scenario_id == "edit_file":
        return (
            "edit_file",
            {
                "edit_count": 1,
                "new_text_sha256": hashlib.sha256(b"gamma").hexdigest(),
                "old_text_sha256": hashlib.sha256(b"beta").hexdigest(),
                "relative_path": "document.txt",
            },
            {
                "edits": [{"newText": "gamma", "oldText": "beta"}],
                "path": "document.txt",
            },
        )
    raise ValueError("unregistered filesystem scenario")
