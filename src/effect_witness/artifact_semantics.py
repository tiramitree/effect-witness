"""Registered schema-v2 invariants for offline artifact verification."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .models import json_exact_equal, sha256_json, strict_json_loads

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_PAYLOAD_SHA256 = sha256_json({"value": 1})
_ARGUMENTS_SHA256 = sha256_json({"operation_id": "op-1", "payload": {"value": 1}})


@dataclass(frozen=True)
class ScenarioSpec:
    tool_name: str
    hint: str
    contract_result: str
    client_outcome: str
    calls: int
    effect_count: int
    attempt_states: dict[str, int]
    fault_modes: dict[str, int]
    observation_success: tuple[bool, ...]
    write_observation_indices: tuple[int, ...]
    final_client_state: str
    fault: str
    policy: str
    reconciliation_observation_index: int | None = None
    before_retry: dict[str, Any] | None = None


SCENARIO_SPECS: dict[str, ScenarioSpec] = {
    "idempotent_truth_sequential": ScenarioSpec(
        "truthful_idempotent_write",
        "idempotentHint",
        "MATCH",
        "SUCCEEDED",
        2,
        1,
        {"DEDUP_HIT": 1, "EFFECT_COMMITTED": 1},
        {"clean": 2},
        (True, True),
        (0, 1),
        "RECEIVED",
        "clean",
        "direct_repeat",
    ),
    "idempotent_misleading_sequential": ScenarioSpec(
        "misleading_idempotent_write",
        "idempotentHint",
        "MISMATCH",
        "SUCCEEDED",
        2,
        2,
        {"EFFECT_COMMITTED": 2},
        {"clean": 2},
        (True, True),
        (0, 1),
        "RECEIVED",
        "clean",
        "direct_repeat",
    ),
    "idempotent_truth_postcommit_blind_retry": ScenarioSpec(
        "truthful_idempotent_write",
        "idempotentHint",
        "MATCH",
        "SUCCEEDED",
        2,
        1,
        {"DEDUP_HIT": 1, "EFFECT_COMMITTED": 1},
        {"clean": 1, "post_commit_delay": 1},
        (False, True),
        (0, 1),
        "RECEIVED",
        "post_commit_delay",
        "blind_retry",
        before_retry={
            "attempt_count": 1,
            "attempt_fault_mode_counts": {"post_commit_delay": 1},
            "attempt_state_counts": {"EFFECT_COMMITTED": 1},
            "effect_count": 1,
            "effect_payload_sha256": [_PAYLOAD_SHA256],
            "operation_id": "op-1",
            "tool_name": "truthful_idempotent_write",
        },
    ),
    "idempotent_misleading_postcommit_blind_retry": ScenarioSpec(
        "misleading_idempotent_write",
        "idempotentHint",
        "MISMATCH",
        "SUCCEEDED",
        2,
        2,
        {"EFFECT_COMMITTED": 2},
        {"clean": 1, "post_commit_delay": 1},
        (False, True),
        (0, 1),
        "RECEIVED",
        "post_commit_delay",
        "blind_retry",
        before_retry={
            "attempt_count": 1,
            "attempt_fault_mode_counts": {"post_commit_delay": 1},
            "attempt_state_counts": {"EFFECT_COMMITTED": 1},
            "effect_count": 1,
            "effect_payload_sha256": [_PAYLOAD_SHA256],
            "operation_id": "op-1",
            "tool_name": "misleading_idempotent_write",
        },
    ),
    "readonly_misleading_clean": ScenarioSpec(
        "misleading_readonly_write",
        "readOnlyHint",
        "MISMATCH",
        "SUCCEEDED",
        1,
        1,
        {"EFFECT_COMMITTED": 1},
        {"clean": 1},
        (True,),
        (0,),
        "RECEIVED",
        "clean",
        "direct",
    ),
    "stable_precommit_exit_reconcile_retry": ScenarioSpec(
        "truthful_idempotent_write",
        "idempotentHint",
        "NOT_APPLICABLE",
        "SUCCEEDED",
        2,
        1,
        {"EFFECT_COMMITTED": 1, "RECEIVED": 1},
        {"clean": 1, "pre_commit_exit": 1},
        (False, True, True),
        (0, 2),
        "RECEIVED",
        "pre_commit_exit",
        "reconcile_then_retry_if_absent",
        reconciliation_observation_index=1,
        before_retry={
            "attempt_count": 1,
            "attempt_fault_mode_counts": {"pre_commit_exit": 1},
            "attempt_state_counts": {"RECEIVED": 1},
            "effect_count": 0,
            "effect_payload_sha256": [],
            "operation_id": "op-1",
            "tool_name": "truthful_idempotent_write",
        },
    ),
    "stable_postcommit_exit_reconcile": ScenarioSpec(
        "truthful_idempotent_write",
        "idempotentHint",
        "NOT_APPLICABLE",
        "COMMITTED_CONFIRMED",
        1,
        1,
        {"EFFECT_COMMITTED": 1},
        {"post_commit_exit": 1},
        (False, True),
        (0,),
        "COMMITTED_CONFIRMED",
        "post_commit_exit",
        "reconcile_if_available",
        reconciliation_observation_index=1,
    ),
    "stable_postcommit_exit_status_unavailable": ScenarioSpec(
        "truthful_idempotent_write",
        "idempotentHint",
        "NOT_APPLICABLE",
        "UNRESOLVED",
        1,
        1,
        {"EFFECT_COMMITTED": 1},
        {"post_commit_exit": 1},
        (False,),
        (0,),
        "UNRESOLVED",
        "post_commit_exit",
        "reconcile_if_available",
    ),
    "idempotent_truth_concurrent_8": ScenarioSpec(
        "truthful_idempotent_write",
        "idempotentHint",
        "MATCH",
        "SUCCEEDED",
        8,
        1,
        {"DEDUP_HIT": 7, "EFFECT_COMMITTED": 1},
        {"clean": 8},
        (True,) * 8,
        tuple(range(8)),
        "RECEIVED",
        "clean",
        "concurrent_repeat",
    ),
    "idempotent_misleading_concurrent_8": ScenarioSpec(
        "misleading_idempotent_write",
        "idempotentHint",
        "MISMATCH",
        "SUCCEEDED",
        8,
        8,
        {"EFFECT_COMMITTED": 8},
        {"clean": 8},
        (True,) * 8,
        tuple(range(8)),
        "RECEIVED",
        "clean",
        "concurrent_repeat",
    ),
}

_EVENT_TYPES: dict[str, tuple[str, ...]] = {
    "idempotent_truth_sequential": (
        "OPERATION_CREATED",
        "SENT",
        "RECEIVED",
        "SENT",
        "RECEIVED",
    ),
    "idempotent_misleading_sequential": (
        "OPERATION_CREATED",
        "SENT",
        "RECEIVED",
        "SENT",
        "RECEIVED",
    ),
    "idempotent_truth_postcommit_blind_retry": (
        "OPERATION_CREATED",
        "SENT",
        "UNKNOWN",
        "BLIND_RETRY",
        "SENT",
        "RECEIVED",
    ),
    "idempotent_misleading_postcommit_blind_retry": (
        "OPERATION_CREATED",
        "SENT",
        "UNKNOWN",
        "BLIND_RETRY",
        "SENT",
        "RECEIVED",
    ),
    "readonly_misleading_clean": (
        "OPERATION_CREATED",
        "SENT",
        "RECEIVED",
    ),
    "stable_precommit_exit_reconcile_retry": (
        "OPERATION_CREATED",
        "SENT",
        "UNKNOWN",
        "RECONCILIATION_OBSERVED",
        "ABSENT_CONFIRMED",
        "SENT",
        "RECEIVED",
    ),
    "stable_postcommit_exit_reconcile": (
        "OPERATION_CREATED",
        "SENT",
        "UNKNOWN",
        "RECONCILIATION_OBSERVED",
        "COMMITTED_CONFIRMED",
    ),
    "stable_postcommit_exit_status_unavailable": (
        "OPERATION_CREATED",
        "SENT",
        "UNKNOWN",
        "RECONCILIATION_UNAVAILABLE",
    ),
    "idempotent_truth_concurrent_8": (
        "OPERATION_CREATED",
        *("SENT",) * 8,
        *("RECEIVED",) * 8,
    ),
    "idempotent_misleading_concurrent_8": (
        "OPERATION_CREATED",
        *("SENT",) * 8,
        *("RECEIVED",) * 8,
    ),
}

_DECISION_PAYLOADS: dict[str, dict[str, Any]] = {
    "ABSENT_CONFIRMED": {"effect_count": 0, "server_exit_code": 86},
    "BLIND_RETRY": {"reason": "ambiguous_transport_failure"},
    "COMMITTED_CONFIRMED": {"effect_count": 1, "server_exit_code": 87},
    "RECONCILIATION_UNAVAILABLE": {"server_exit_code": 87},
}


_CONTRACT_BASIS = {
    "idempotent_truth_sequential": (
        "idempotentHint=true with repeated identical arguments"
    ),
    "idempotent_misleading_sequential": (
        "idempotentHint=true with repeated identical arguments"
    ),
    "idempotent_truth_postcommit_blind_retry": (
        "idempotentHint=true after ambiguous response loss"
    ),
    "idempotent_misleading_postcommit_blind_retry": (
        "idempotentHint=true after ambiguous response loss"
    ),
    "readonly_misleading_clean": "readOnlyHint=true",
    "stable_precommit_exit_reconcile_retry": (
        "confirmed pre-commit absence does not exercise repeat-effect safety"
    ),
    "stable_postcommit_exit_reconcile": (
        "single ambiguous call does not exercise repeat safety"
    ),
    "stable_postcommit_exit_status_unavailable": (
        "single ambiguous call does not exercise repeat safety"
    ),
    "idempotent_truth_concurrent_8": (
        "idempotentHint=true under eight identical concurrent calls"
    ),
    "idempotent_misleading_concurrent_8": (
        "idempotentHint=true under eight identical concurrent calls"
    ),
}

_WRITE_RESPONSE_FACTS: dict[str, tuple[tuple[int, bool], ...]] = {
    "idempotent_truth_sequential": ((1, False), (1, True)),
    "idempotent_misleading_sequential": ((1, False), (2, False)),
    "idempotent_truth_postcommit_blind_retry": ((1, True),),
    "idempotent_misleading_postcommit_blind_retry": ((2, False),),
    "readonly_misleading_clean": ((1, False),),
    "stable_precommit_exit_reconcile_retry": ((1, False),),
    "stable_postcommit_exit_reconcile": (),
    "stable_postcommit_exit_status_unavailable": (),
    "idempotent_truth_concurrent_8": ((1, False), *((1, True),) * 7),
    "idempotent_misleading_concurrent_8": tuple(
        (effect_id, False) for effect_id in range(1, 9)
    ),
}


def _expected_evidence_check_keys(scenario_id: str) -> set[str]:
    hint = SCENARIO_SPECS[scenario_id].hint
    common = {
        "declared_annotations_are_exact",
        f"declared_{hint}_is_true",
        "protocol_schema_is_exact",
    }
    if scenario_id.endswith("_sequential"):
        extras = {
            "both_calls_succeeded",
            "clean_fault_plan_is_exact",
            "control_effect_count_is_exact",
            "request_arguments_are_identical",
            "server_attempt_count_is_two",
        }
    elif scenario_id.endswith("_postcommit_blind_retry"):
        extras = {
            "control_effect_count_is_exact",
            "effect_committed_before_retry",
            "fault_plan_is_exact",
            "first_call_was_transport_ambiguous",
            "request_arguments_are_identical",
            "retry_succeeded",
            "server_attempt_count_is_two",
        }
    elif scenario_id == "readonly_misleading_clean":
        extras = {
            "call_succeeded",
            "clean_fault_plan_is_exact",
            "negative_control_effect_count_is_one",
            "server_attempt_count_is_one",
        }
    elif scenario_id == "stable_precommit_exit_reconcile_retry":
        extras = {
            "absence_confirmed_before_retry",
            "fault_plan_is_exact",
            "first_call_was_transport_ambiguous",
            "precommit_exit_code_is_86",
            "request_arguments_are_identical",
            "retry_succeeded",
            "server_attempt_count_is_two",
            "truthful_control_effect_count_is_one",
        }
    elif scenario_id.startswith("stable_postcommit_exit_"):
        extras = {
            "fault_plan_is_exact",
            "first_call_was_transport_ambiguous",
            "postcommit_exit_code_is_87",
            "server_attempt_count_is_one",
            "server_effect_count_is_one",
            "status_availability_matches_scenario",
        }
    else:
        extras = {
            "all_eight_calls_succeeded",
            "clean_fault_plan_is_exact",
            "concurrency_barrier_released_all_eight",
            "control_effect_count_is_exact",
            "request_arguments_are_identical",
            "server_attempt_count_is_eight",
        }
    return common | extras


def _expected_expectation_input(scenario_id: str) -> dict[str, Any]:
    if scenario_id == "readonly_misleading_clean":
        return {"expected_effects": 0}
    if scenario_id.startswith("stable_postcommit_exit_"):
        return {"expected_max_effects": None}
    return {"expected_max_effects": 1}


def _expected_annotations(tool_name: str) -> dict[str, Any]:
    return {
        "destructiveHint": False,
        "idempotentHint": tool_name != "misleading_readonly_write",
        "openWorldHint": False,
        "readOnlyHint": tool_name == "misleading_readonly_write",
        "title": None,
    }


def _expected_input_schema(tool_name: str) -> dict[str, Any]:
    return {
        "properties": {
            "operation_id": {"title": "Operation Id", "type": "string"},
            "payload": {
                "additionalProperties": True,
                "title": "Payload",
                "type": "object",
            },
        },
        "required": ["operation_id", "payload"],
        "title": f"{tool_name}Arguments",
        "type": "object",
    }


def _append(errors: list[str], scenario_id: str, message: str) -> None:
    errors.append(f"{scenario_id}: {message}")


def _successful_observation(observation: Any) -> bool:
    return (
        isinstance(observation, dict)
        and observation.get("completed") is True
        and observation.get("is_error") is False
        and isinstance(observation.get("response"), dict)
    )


def _verify_response(
    observation: dict[str, Any],
    *,
    successful: bool,
    scenario_id: str,
    errors: list[str],
) -> None:
    if set(observation) != {"completed", "exception_types", "is_error", "response"}:
        _append(errors, scenario_id, "observation fields differ from registration")
    if successful:
        if not _successful_observation(observation):
            _append(errors, scenario_id, "successful observation shape is invalid")
            return
        if observation.get("exception_types") != []:
            _append(errors, scenario_id, "successful observation has exceptions")
        response = observation["response"]
        expected_response_fields = {"_meta", "content", "isError", "structuredContent"}
        if set(response) != expected_response_fields:
            _append(errors, scenario_id, "response fields differ from registration")
        if response.get("_meta") is not None:
            _append(errors, scenario_id, "response metadata differs from registration")
        if response.get("isError") is not False:
            _append(errors, scenario_id, "successful MCP response has isError=true")
        structured = response.get("structuredContent")
        if not isinstance(structured, dict):
            _append(errors, scenario_id, "successful response lacks structuredContent")
            return
        content = response.get("content")
        if not isinstance(content, list) or len(content) != 1:
            _append(errors, scenario_id, "successful response lacks text content")
            return
        first = content[0]
        if not isinstance(first, dict):
            _append(errors, scenario_id, "response text content is invalid")
            return
        expected_content_fields = {"_meta", "annotations", "text", "type"}
        if (
            set(first) != expected_content_fields
            or first.get("_meta") is not None
            or first.get("annotations") is not None
            or first.get("type") != "text"
            or not isinstance(first.get("text"), str)
        ):
            _append(errors, scenario_id, "response text content is invalid")
            return
        try:
            text_value = strict_json_loads(first["text"])
        except (ValueError, RecursionError):
            _append(errors, scenario_id, "response text is not JSON")
            return
        if not json_exact_equal(text_value, structured):
            _append(errors, scenario_id, "response text and structuredContent differ")
    else:
        if not isinstance(observation, dict):
            _append(errors, scenario_id, "failed observation is not an object")
            return
        if (
            observation.get("completed") is not False
            or observation.get("is_error") is not None
            or observation.get("response") is not None
        ):
            _append(errors, scenario_id, "transport-ambiguous observation is invalid")
        exceptions = observation.get("exception_types")
        if (
            not isinstance(exceptions, list)
            or not exceptions
            or any(not isinstance(item, str) or not item for item in exceptions)
            or exceptions != sorted(set(exceptions))
        ):
            _append(
                errors, scenario_id, "transport failure exception types are invalid"
            )


def _verify_journal(
    case: dict[str, Any],
    spec: ScenarioSpec,
    *,
    scenario_id: str,
    observations: list[Any],
    request_hashes: list[str],
    errors: list[str],
) -> None:
    journal = case.get("client_journal")
    if not isinstance(journal, dict):
        _append(errors, scenario_id, "client_journal is missing")
        return
    if set(journal) != {"client_events", "client_operations"}:
        _append(errors, scenario_id, "journal fields differ from registration")
    operations = journal.get("client_operations")
    events = journal.get("client_events")
    if not isinstance(operations, list) or len(operations) != 1:
        _append(errors, scenario_id, "journal must contain one client operation")
        return
    if not isinstance(events, list):
        _append(errors, scenario_id, "journal events are missing")
        return
    operation = operations[0]
    if not isinstance(operation, dict):
        _append(errors, scenario_id, "client operation is invalid")
        return
    expected_operation = {
        "attempts_used": spec.calls,
        "operation_id": "op-1",
        "payload_sha256": _PAYLOAD_SHA256,
        "retry_budget": spec.calls - 1,
        "scenario_id": scenario_id,
        "state": spec.final_client_state,
    }
    if not json_exact_equal(operation, expected_operation):
        _append(errors, scenario_id, "client operation summary is inconsistent")

    sequences = [event.get("seq") for event in events if isinstance(event, dict)]
    if not json_exact_equal(sequences, list(range(1, len(events) + 1))):
        _append(errors, scenario_id, "journal event sequence is not contiguous")
    event_types = tuple(
        event.get("event_type") if isinstance(event, dict) else None for event in events
    )
    if event_types != _EVENT_TYPES[scenario_id]:
        _append(errors, scenario_id, "journal event state machine is inconsistent")
    expected_event_fields = {
        "attempt_id",
        "canonical_payload_sha256",
        "event_type",
        "payload",
        "scenario_id",
        "seq",
    }
    for event in events:
        if not isinstance(event, dict):
            _append(errors, scenario_id, "journal event is not an object")
            continue
        if set(event) != expected_event_fields:
            _append(
                errors,
                scenario_id,
                "journal event fields differ from registration",
            )
        if event.get("scenario_id") != scenario_id:
            _append(errors, scenario_id, "journal event has another scenario_id")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            _append(errors, scenario_id, "journal event payload is invalid")
        elif event.get("canonical_payload_sha256") != sha256_json(payload):
            _append(errors, scenario_id, "journal event payload hash is inconsistent")
        event_type = event.get("event_type")
        if event_type == "OPERATION_CREATED" and (
            event.get("attempt_id") is not None
            or not json_exact_equal(
                payload,
                {
                    "operation_id": "op-1",
                    "payload_sha256": _PAYLOAD_SHA256,
                    "retry_budget": spec.calls - 1,
                },
            )
        ):
            _append(errors, scenario_id, "operation-created event is inconsistent")
        if event_type in _DECISION_PAYLOADS and (
            event.get("attempt_id") is not None
            or not json_exact_equal(payload, _DECISION_PAYLOADS[event_type])
        ):
            _append(errors, scenario_id, f"{event_type} decision is inconsistent")

    sent = [
        event
        for event in events
        if isinstance(event, dict) and event.get("event_type") == "SENT"
    ]
    if len(sent) != spec.calls:
        _append(errors, scenario_id, "journal SENT count is inconsistent")
    sent_payloads = [event.get("payload") for event in sent]
    sent_hashes = [
        payload.get("arguments_sha256") if isinstance(payload, dict) else None
        for payload in sent_payloads
    ]
    if sent_hashes != request_hashes:
        _append(errors, scenario_id, "journal request hashes are inconsistent")
    expected_attempt_ids = [f"a{index}" for index in range(1, spec.calls + 1)]
    if [event.get("attempt_id") for event in sent] != expected_attempt_ids:
        _append(errors, scenario_id, "journal SENT attempt order is inconsistent")
    for payload, expected_attempt_id in zip(
        sent_payloads,
        expected_attempt_ids,
        strict=False,
    ):
        expected_sent_payload = {
            "arguments_sha256": _ARGUMENTS_SHA256,
            "attempt_id": expected_attempt_id,
            "tool_name": spec.tool_name,
        }
        if not json_exact_equal(payload, expected_sent_payload):
            _append(errors, scenario_id, "journal SENT payload is inconsistent")

    terminals = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event_type") in {"RECEIVED", "UNKNOWN", "ERROR_RESPONSE"}
    ]
    if len(terminals) != spec.calls:
        _append(errors, scenario_id, "journal terminal write count is inconsistent")
    for terminal, observation_index, expected_attempt_id in zip(
        terminals,
        spec.write_observation_indices,
        expected_attempt_ids,
        strict=False,
    ):
        if observation_index >= len(observations):
            continue
        observation = observations[observation_index]
        if not isinstance(observation, dict):
            continue
        response = observation.get("response")
        payload = terminal.get("payload")
        if not isinstance(payload, dict):
            continue
        if terminal.get("attempt_id") != expected_attempt_id:
            _append(errors, scenario_id, "journal terminal attempt is inconsistent")
        expected_response_hash = sha256_json(response) if response is not None else None
        expected_event = (
            "RECEIVED"
            if _successful_observation(observation)
            else "ERROR_RESPONSE"
            if observation.get("completed") is True
            else "UNKNOWN"
        )
        if terminal.get("event_type") != expected_event:
            _append(errors, scenario_id, "journal terminal event is inconsistent")
        expected_terminal_payload = {
            "completed": observation.get("completed"),
            "exception_types": observation.get("exception_types"),
            "is_error": observation.get("is_error"),
            "response_sha256": expected_response_hash,
        }
        if not json_exact_equal(payload, expected_terminal_payload):
            _append(errors, scenario_id, "journal terminal payload is inconsistent")

    reconciliations = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event_type") == "RECONCILIATION_OBSERVED"
    ]
    if spec.reconciliation_observation_index is None:
        if reconciliations:
            _append(errors, scenario_id, "unexpected reconciliation observation")
    elif len(reconciliations) != 1:
        _append(errors, scenario_id, "reconciliation observation count is invalid")
    else:
        index = spec.reconciliation_observation_index
        if index < len(observations) and isinstance(observations[index], dict):
            observation = observations[index]
            response = observation.get("response")
            payload = reconciliations[0].get("payload")
            if not isinstance(payload, dict):
                _append(errors, scenario_id, "reconciliation payload is invalid")
                return
            expected_hash = sha256_json(response) if response is not None else None
            expected_reconciliation_payload = {
                "completed": observation.get("completed"),
                "exception_types": observation.get("exception_types"),
                "is_error": observation.get("is_error"),
                "response_sha256": expected_hash,
            }
            if not json_exact_equal(payload, expected_reconciliation_payload):
                _append(errors, scenario_id, "reconciliation payload is inconsistent")
            if reconciliations[0].get("attempt_id") is not None:
                _append(errors, scenario_id, "reconciliation attempt_id must be null")
            structured = (
                response.get("structuredContent")
                if isinstance(response, dict)
                else None
            )
            is_precommit = scenario_id == "stable_precommit_exit_reconcile_retry"
            expected_attempt = {
                "attempt_id": "a000001",
                "fault_mode": "pre_commit_exit" if is_precommit else "post_commit_exit",
                "payload_sha256": _PAYLOAD_SHA256,
                "received_seq": 1,
                "state": "RECEIVED" if is_precommit else "EFFECT_COMMITTED",
                "terminal_seq": None if is_precommit else 2,
            }
            expected_effects = []
            if not is_precommit:
                result = {
                    "deduplicated": False,
                    "effect_id": 1,
                    "operation_id": "op-1",
                    "payload_sha256": _PAYLOAD_SHA256,
                    "tool_name": spec.tool_name,
                }
                expected_effects = [
                    {
                        "attempt_id": "a000001",
                        "commit_seq": 2,
                        "effect_id": 1,
                        "payload_sha256": _PAYLOAD_SHA256,
                        "result": result,
                    }
                ]
            expected_status = {
                "attempts": [expected_attempt],
                "effect_count": len(expected_effects),
                "effects": expected_effects,
                "operation_id": "op-1",
                "tool_name": spec.tool_name,
            }
            if not json_exact_equal(structured, expected_status):
                _append(errors, scenario_id, "reconciliation fact is inconsistent")


def verify_registered_case(case: dict[str, Any], errors: list[str]) -> None:
    """Recompute the registered scenario-v2 invariants from exported facts."""

    scenario_id = case.get("scenario_id")
    if not isinstance(scenario_id, str) or scenario_id not in SCENARIO_SPECS:
        errors.append("unknown schema-v2 scenario")
        return
    spec = SCENARIO_SPECS[scenario_id]
    expected_case_fields = {
        "client_journal",
        "client_outcome",
        "contract_basis",
        "contract_result",
        "declared_annotations",
        "declared_input_schema",
        "evidence_checks",
        "expectation_input",
        "expectation_met",
        "expected",
        "observations",
        "protocol",
        "scenario_id",
        "stimulus",
        "witness",
    }
    if spec.before_retry is not None:
        expected_case_fields.add("intermediate_witness")
    if scenario_id.endswith("_concurrent_8"):
        expected_case_fields.add("concurrency_witness")
    if set(case) != expected_case_fields:
        _append(errors, scenario_id, "case fields differ from registration")
    if case.get("contract_result") != spec.contract_result:
        _append(errors, scenario_id, "contract_result differs from registered verdict")
    if case.get("client_outcome") != spec.client_outcome:
        _append(errors, scenario_id, "client_outcome differs from registered outcome")
    if not json_exact_equal(
        case.get("expected"),
        {
            "client_outcome": spec.client_outcome,
            "contract_result": spec.contract_result,
        },
    ):
        _append(errors, scenario_id, "expected outcome is not registered")
    if case.get("contract_basis") != _CONTRACT_BASIS[scenario_id]:
        _append(errors, scenario_id, "contract_basis differs from registration")
    if not json_exact_equal(
        case.get("expectation_input"), _expected_expectation_input(scenario_id)
    ):
        _append(errors, scenario_id, "expectation_input differs from registration")
    protocol = case.get("protocol")
    if (
        not isinstance(protocol, dict)
        or set(protocol) != {"name", "python_sdk"}
        or protocol.get("name") != "MCP"
        or not isinstance(protocol.get("python_sdk"), str)
        or not protocol["python_sdk"]
    ):
        _append(errors, scenario_id, "protocol metadata differs from registration")

    checks = case.get("evidence_checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        _append(errors, scenario_id, "evidence_checks are not all true")
    if isinstance(checks, dict) and set(checks) != _expected_evidence_check_keys(
        scenario_id
    ):
        _append(errors, scenario_id, "evidence_check keys differ from registration")
    if case.get("expectation_met") is not True:
        _append(errors, scenario_id, "expectation_met must be true for this artifact")

    annotations = case.get("declared_annotations")
    if not json_exact_equal(annotations, _expected_annotations(spec.tool_name)):
        _append(errors, scenario_id, "declared annotations differ from registration")
    input_schema = case.get("declared_input_schema")
    if not json_exact_equal(input_schema, _expected_input_schema(spec.tool_name)):
        _append(errors, scenario_id, "declared input schema differs from registration")

    witness = case.get("witness")
    if not isinstance(witness, dict):
        _append(errors, scenario_id, "witness is missing")
        witness = {}
    expected_witness_fields = {
        "attempt_count",
        "attempt_fault_mode_counts",
        "attempt_state_counts",
        "effect_count",
        "effect_payload_sha256",
        "operation_id",
        "tool_name",
    }
    if set(witness) != expected_witness_fields:
        _append(errors, scenario_id, "witness fields differ from registration")
    if witness.get("tool_name") != spec.tool_name:
        _append(errors, scenario_id, "witness tool_name is inconsistent")
    if witness.get("operation_id") != "op-1":
        _append(errors, scenario_id, "witness operation_id is inconsistent")
    if not json_exact_equal(witness.get("attempt_count"), spec.calls):
        _append(errors, scenario_id, "witness attempt_count is inconsistent")
    if not json_exact_equal(witness.get("effect_count"), spec.effect_count):
        _append(errors, scenario_id, "witness effect_count is inconsistent")
    if not json_exact_equal(witness.get("attempt_state_counts"), spec.attempt_states):
        _append(errors, scenario_id, "witness attempt states are inconsistent")
    if not json_exact_equal(witness.get("attempt_fault_mode_counts"), spec.fault_modes):
        _append(errors, scenario_id, "witness fault modes are inconsistent")
    effect_hashes = witness.get("effect_payload_sha256")
    if (
        not isinstance(effect_hashes, list)
        or len(effect_hashes) != spec.effect_count
        or any(
            not isinstance(item, str) or not _HEX64.fullmatch(item)
            for item in effect_hashes
        )
        or any(item != _PAYLOAD_SHA256 for item in effect_hashes)
    ):
        _append(errors, scenario_id, "witness effect payload hashes are inconsistent")

    stimulus = case.get("stimulus")
    if not isinstance(stimulus, dict):
        _append(errors, scenario_id, "stimulus is missing")
        stimulus = {}
    if set(stimulus) != {"calls", "fault", "policy", "request_argument_sha256s"}:
        _append(errors, scenario_id, "stimulus fields differ from registration")
    if not json_exact_equal(stimulus.get("calls"), spec.calls):
        _append(errors, scenario_id, "stimulus call count is inconsistent")
    if stimulus.get("fault") != spec.fault or stimulus.get("policy") != spec.policy:
        _append(errors, scenario_id, "stimulus fault or policy is inconsistent")
    request_hashes = stimulus.get("request_argument_sha256s")
    if (
        not isinstance(request_hashes, list)
        or len(request_hashes) != spec.calls
        or any(item != _ARGUMENTS_SHA256 for item in request_hashes)
    ):
        _append(errors, scenario_id, "request argument hashes differ from registration")
        request_hashes = []

    observations = case.get("observations")
    if not isinstance(observations, list):
        _append(errors, scenario_id, "observations are missing")
        observations = []
    if len(observations) != len(spec.observation_success):
        _append(errors, scenario_id, "observation count is inconsistent")
    for observation, successful in zip(
        observations,
        spec.observation_success,
        strict=False,
    ):
        if isinstance(observation, dict):
            _verify_response(
                observation,
                successful=successful,
                scenario_id=scenario_id,
                errors=errors,
            )
        else:
            _append(errors, scenario_id, "observation is not an object")

    successful_write_results: list[dict[str, Any]] = []
    for observation_index in spec.write_observation_indices:
        if observation_index >= len(observations):
            continue
        observation = observations[observation_index]
        if not _successful_observation(observation):
            continue
        response = observation["response"]
        structured = response.get("structuredContent")
        if not isinstance(structured, dict):
            continue
        successful_write_results.append(structured)
        effect_id = structured.get("effect_id")
        if (
            set(structured)
            != {
                "deduplicated",
                "effect_id",
                "operation_id",
                "payload_sha256",
                "tool_name",
            }
            or not isinstance(structured.get("deduplicated"), bool)
            or not isinstance(effect_id, int)
            or isinstance(effect_id, bool)
            or effect_id < 1
            or effect_id > spec.effect_count
            or structured.get("operation_id") != "op-1"
            or structured.get("payload_sha256") != _PAYLOAD_SHA256
            or structured.get("tool_name") != spec.tool_name
        ):
            _append(errors, scenario_id, "write response fact is inconsistent")
    observed_write_facts = []
    for result in successful_write_results:
        effect_id = result.get("effect_id")
        deduplicated = result.get("deduplicated")
        if (
            isinstance(effect_id, int)
            and not isinstance(effect_id, bool)
            and isinstance(deduplicated, bool)
        ):
            observed_write_facts.append((effect_id, deduplicated))
    if tuple(sorted(observed_write_facts)) != _WRITE_RESPONSE_FACTS[scenario_id]:
        _append(errors, scenario_id, "write response effect facts are inconsistent")

    expected_concurrency = {
        "barrier_parties": 8,
        "barrier_passed": 8,
        "max_in_flight": 8,
    }
    if scenario_id.endswith("_concurrent_8"):
        if not json_exact_equal(case.get("concurrency_witness"), expected_concurrency):
            _append(errors, scenario_id, "concurrency witness is inconsistent")
    elif "concurrency_witness" in case:
        _append(errors, scenario_id, "unexpected concurrency witness")

    if spec.before_retry is not None:
        expected_intermediate = {"before_retry": spec.before_retry}
        if not json_exact_equal(
            case.get("intermediate_witness"),
            expected_intermediate,
        ):
            _append(errors, scenario_id, "before-retry witness is inconsistent")
    elif "intermediate_witness" in case:
        _append(errors, scenario_id, "unexpected intermediate witness")

    _verify_journal(
        case,
        spec,
        scenario_id=scenario_id,
        observations=observations,
        request_hashes=request_hashes,
        errors=errors,
    )


def expected_contract_counts() -> dict[str, int]:
    return dict(
        sorted(
            Counter(spec.contract_result for spec in SCENARIO_SPECS.values()).items()
        )
    )
