"""Pure registered relationships for schema-v4 replay evidence."""

from __future__ import annotations

import hashlib
from typing import Any, Final

from .filesystem_semantics import EDITED, FIXTURE
from .langgraph_registration import (
    INJECTED_EXIT_CODE,
    SCENARIOS,
    WORKER_BLIND_RESUME_EVENT_TYPES,
    WORKER_FAULT_EVENT_TYPES,
    WORKER_RECONCILE_RESUME_EVENT_TYPES,
)
from .models import json_exact_equal, sha256_json

TAMPERED: Final = b"alpha\nomega\n"


def expected_tree(relative: str, content: bytes) -> dict[str, Any]:
    """Return the exact public byte-tree projection for one file."""

    entries = [
        {
            "bytes": len(content),
            "kind": "file",
            "path": relative,
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    ]
    return {"entries": entries, "tree_sha256": sha256_json(entries)}


def empty_tree() -> dict[str, Any]:
    """Return the exact empty byte-tree projection."""

    return {"entries": [], "tree_sha256": sha256_json([])}


def _call_shape(call: Any, *, is_error: bool) -> bool:
    expected_fields = {
        "completed",
        "content_types",
        "exception_types",
        "is_error",
        "response_text_included",
        "response_text_redacted",
        "structured_content_present",
        "text_block_count",
    }
    return (
        isinstance(call, dict)
        and set(call) == expected_fields
        and call["completed"] is True
        and call["content_types"] == ["text"]
        and call["exception_types"] == []
        and call["is_error"] is is_error
        and call["response_text_included"] is False
        and call["response_text_redacted"] is True
        and call["structured_content_present"] is (not is_error)
        and call["text_block_count"] == 1
        and type(call["text_block_count"]) is int
    )


def _fault_process_registered(value: Any) -> bool:
    return json_exact_equal(
        value,
        {
            "checkpoint": {
                "available": True,
                "history_count": 1,
                "next": ["workflow"],
            },
            "error_types": ["InjectedPostEffectFailure"],
            "exit_code": INJECTED_EXIT_CODE,
            "status": "failed",
            "stderr_empty": True,
            "stdout_record_count": 1,
        },
    )


def _resume_process_registered(
    value: Any,
    *,
    decision: str,
    mutating_call_performed: bool,
    observation: dict[str, Any] | None,
) -> bool:
    workflow_result: dict[str, Any] = {
        "decision": decision,
        "mutating_call_performed": mutating_call_performed,
    }
    if observation is not None:
        workflow_result["observation"] = observation
    return json_exact_equal(
        value,
        {
            "checkpoint": {
                "available": True,
                "history_count": 2,
                "next": [],
            },
            "exit_code": 0,
            "status": "completed",
            "stderr_empty": True,
            "stdout_record_count": 1,
            "workflow_result": workflow_result,
        },
    )


def evaluate_round(
    scenario_id: str,
    *,
    decisions: Any,
    events: Any,
    fault_process: Any,
    observations: Any,
    resume_process: Any,
    s0: Any,
    s1: Any,
    s2: Any,
    s3: Any,
) -> dict[str, bool]:
    """Recompute the exact registered round without executing any dependency."""

    if scenario_id not in SCENARIOS:
        raise ValueError("unregistered replay scenario")
    registration = SCENARIOS[scenario_id]
    is_edit = registration["tool_name"] == "edit_file"
    expected_s0 = expected_tree("document.txt", FIXTURE) if is_edit else empty_tree()
    expected_s1 = expected_tree(
        "document.txt",
        EDITED if is_edit else FIXTURE,
    )
    expected_observation_errors: list[bool]
    expected_decisions: list[str]
    expected_resume_events: tuple[str, ...]
    expected_resume_decision: str
    resume_call: dict[str, Any] | None
    if scenario_id == "write_blind":
        expected_observation_errors = [False, False]
        expected_decisions = []
        expected_resume_events = WORKER_BLIND_RESUME_EVENT_TYPES
        expected_resume_decision = "TOOL_RESULT"
        resume_call = (
            observations[-1]
            if isinstance(observations, list) and observations
            else None
        )
    elif scenario_id == "edit_blind":
        expected_observation_errors = [False, True]
        expected_decisions = []
        expected_resume_events = WORKER_BLIND_RESUME_EVENT_TYPES
        expected_resume_decision = "TOOL_RESULT"
        resume_call = (
            observations[-1]
            if isinstance(observations, list) and observations
            else None
        )
    elif scenario_id == "edit_reconcile":
        expected_observation_errors = [False]
        expected_decisions = ["COMMITTED_CONFIRMED"]
        expected_resume_events = WORKER_RECONCILE_RESUME_EVENT_TYPES[scenario_id]
        expected_resume_decision = "COMMITTED_CONFIRMED"
        resume_call = None
    else:
        expected_observation_errors = [False]
        expected_decisions = ["UNRESOLVED"]
        expected_resume_events = WORKER_RECONCILE_RESUME_EVENT_TYPES[scenario_id]
        expected_resume_decision = "UNRESOLVED"
        resume_call = None
    observed_errors = (
        [item.get("is_error") for item in observations]
        if isinstance(observations, list)
        and all(isinstance(item, dict) for item in observations)
        else None
    )
    calls_registered = (
        isinstance(observations, list)
        and len(observations) == len(expected_observation_errors)
        and all(
            _call_shape(call, is_error=is_error)
            for call, is_error in zip(
                observations,
                expected_observation_errors,
                strict=True,
            )
        )
    )
    expected_events = [
        *(
            {"phase": "fault", "type": event_type}
            for event_type in WORKER_FAULT_EVENT_TYPES
        ),
        *(
            {"phase": "resume", "type": event_type}
            for event_type in expected_resume_events
        ),
    ]
    checks = {
        "decisions_registered": decisions == expected_decisions,
        "event_sequence_registered": json_exact_equal(events, expected_events),
        "fault_process_registered": _fault_process_registered(fault_process),
        "mutating_call_count_registered": (
            isinstance(observations, list)
            and len(observations) == len(expected_observation_errors)
        ),
        "mutating_call_results_registered": (
            observed_errors == expected_observation_errors
        ),
        "mutating_call_shapes_registered": calls_registered,
        "resume_process_registered": _resume_process_registered(
            resume_process,
            decision=expected_resume_decision,
            mutating_call_performed=registration["policy"] == "blind",
            observation=resume_call,
        ),
        "s0_registered": json_exact_equal(s0, expected_s0),
        "s1_registered": json_exact_equal(s1, expected_s1),
        "s0_differs_s1": not json_exact_equal(s0, s1),
    }
    if registration["tamper_before_resume"]:
        expected_tampered = expected_tree("document.txt", TAMPERED)
        checks.update(
            {
                "s2_tampered_tree_registered": json_exact_equal(
                    s2,
                    expected_tampered,
                ),
                "s1_differs_s2_after_registered_tamper": not json_exact_equal(
                    s2,
                    s1,
                ),
                "s2_equals_s3_after_unresolved_resume": json_exact_equal(
                    s2,
                    s3,
                ),
            }
        )
    else:
        checks.update(
            {
                "s1_equals_s2_before_resume": json_exact_equal(s1, s2),
                "s2_equals_s3_after_resume": json_exact_equal(s2, s3),
            }
        )
    return checks
