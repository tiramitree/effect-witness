"""Executable MCP effect-contract scenario suite and canonical evidence export."""

from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import sqlite3
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .journal import ClientJournal
from .mcp_client import (
    NORMAL_MCP_TIMEOUT_SECONDS,
    CallObservation,
    call_tool_sync,
    list_tools_sync,
)
from .models import ClientOutcome, ContractResult, canonical_json
from .process import FixtureProcess
from .store import EffectStore

_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40}$")
# One mutating fixture call can encounter separate busy windows while recording
# receipt and committing its effect. The eight-way control therefore uses a
# dedicated budget with scheduling headroom; registered short faults still
# pass their explicit sub-second budgets.
CONCURRENT_MCP_TIMEOUT_SECONDS: Final = 30.0
_DIAGNOSTIC_TOKEN = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")


@dataclass(frozen=True)
class Expected:
    contract_result: ContractResult
    client_outcome: ClientOutcome


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    run: Callable[[Path], dict[str, Any]]
    expected: Expected


def _arguments(
    operation_id: str = "op-1",
    *,
    value: int = 1,
) -> dict[str, Any]:
    return {"operation_id": operation_id, "payload": {"value": value}}


def _structured(observation: CallObservation) -> dict[str, Any]:
    if not observation.succeeded or observation.response is None:
        raise ValueError("tool response was not successful")
    value = observation.response.get("structuredContent")
    if value is None:
        value = observation.response.get("structured_content")
    if not isinstance(value, dict):
        raise TypeError("tool response has no structured content")
    return value


def _tool_map(url: str) -> dict[str, dict[str, Any]]:
    return {
        tool["name"]: tool
        for tool in list_tools_sync(
            url,
            timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
        )
    }


def _protocol() -> dict[str, str]:
    return {
        "name": "MCP",
        "python_sdk": importlib.metadata.version("mcp"),
    }


def _idempotent_result(
    *,
    effect_count: int,
    evidence_established: bool,
) -> ContractResult:
    if not evidence_established or effect_count < 1:
        return ContractResult.UNRESOLVED
    if effect_count == 1:
        return ContractResult.MATCH
    return ContractResult.MISMATCH


def _client_success(observations: list[CallObservation]) -> ClientOutcome:
    if observations and all(observation.succeeded for observation in observations):
        return ClientOutcome.SUCCEEDED
    return ClientOutcome.UNKNOWN


def _safe_diagnostic_token(value: object) -> str:
    text = value if isinstance(value, str) else ""
    return text if _DIAGNOSTIC_TOKEN.fullmatch(text) else "redacted"


def _failure_diagnostic(case: dict[str, Any]) -> dict[str, Any]:
    checks = case.get("evidence_checks")
    failed_checks = (
        sorted(
            _safe_diagnostic_token(name)
            for name, value in checks.items()
            if value is not True
        )
        if isinstance(checks, dict)
        else ["evidence_checks_missing"]
    )
    observations = case.get("observations")
    normalized_observations = observations if isinstance(observations, list) else []
    exception_types = sorted(
        {
            _safe_diagnostic_token(exception_type)
            for observation in normalized_observations
            if isinstance(observation, dict)
            for exception_type in observation.get("exception_types", ())
        }
    )
    witness = case.get("witness")
    normalized_witness = witness if isinstance(witness, dict) else {}
    concurrency = case.get("concurrency_witness")
    normalized_concurrency = concurrency if isinstance(concurrency, dict) else {}
    return {
        "completed_observations": sum(
            observation.get("completed") is True
            for observation in normalized_observations
            if isinstance(observation, dict)
        ),
        "concurrency": {
            key: value
            for key in ("barrier_parties", "barrier_passed", "max_in_flight")
            if isinstance((value := normalized_concurrency.get(key)), int)
            and not isinstance(value, bool)
        },
        "exception_types": exception_types,
        "failed_checks": failed_checks,
        "observation_count": len(normalized_observations),
        "scenario_id": _safe_diagnostic_token(case.get("scenario_id")),
        "witness": {
            key: value
            for key in ("attempt_count", "effect_count")
            if isinstance((value := normalized_witness.get(key)), int)
            and not isinstance(value, bool)
        },
    }


def _request_hashes(journal: ClientJournal) -> list[str]:
    snapshot = journal.snapshot()
    return [
        event["payload"]["arguments_sha256"]
        for event in snapshot["client_events"]
        if event["event_type"] == "SENT"
    ]


def _requests_are_identical(journal: ClientJournal, *, count: int) -> bool:
    hashes = _request_hashes(journal)
    return len(hashes) == count and len(set(hashes)) == 1


def _declaration_checks(
    tool: dict[str, Any],
    *,
    hint: str,
) -> dict[str, bool]:
    annotations = tool.get("annotations")
    schema = tool.get("inputSchema")
    if not isinstance(annotations, dict):
        annotations = {}
    if not isinstance(schema, dict):
        schema = {}
    tool_name = tool.get("name")
    expected_annotations = {
        "destructiveHint": False,
        "idempotentHint": hint == "idempotentHint",
        "openWorldHint": False,
        "readOnlyHint": hint == "readOnlyHint",
        "title": None,
    }
    expected_schema = {
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
    return {
        "declared_annotations_are_exact": annotations == expected_annotations,
        f"declared_{hint}_is_true": annotations.get(hint) is True,
        "protocol_schema_is_exact": schema == expected_schema,
    }


def _wait_for_witness(
    store: EffectStore,
    *,
    tool_name: str,
    attempt_count: int,
    effect_count: int,
    timeout_seconds: float = 1.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    latest = _witness_summary(store, tool_name=tool_name)
    while time.monotonic() < deadline:
        if (
            latest["attempt_count"] == attempt_count
            and latest["effect_count"] == effect_count
        ):
            return latest
        time.sleep(0.02)
        latest = _witness_summary(store, tool_name=tool_name)
    return latest


def _observe(
    *,
    journal: ClientJournal,
    scenario_id: str,
    attempt_id: str,
    url: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float = NORMAL_MCP_TIMEOUT_SECONDS,
) -> CallObservation:
    journal.record_send(
        scenario_id=scenario_id,
        attempt_id=attempt_id,
        tool_name=tool_name,
        arguments=arguments,
    )
    observation = call_tool_sync(
        url,
        name=tool_name,
        arguments=arguments,
        timeout_seconds=timeout_seconds,
    )
    journal.record_observation(
        scenario_id=scenario_id,
        attempt_id=attempt_id,
        completed=observation.completed,
        is_error=observation.is_error,
        exception_types=observation.exception_types,
        response=observation.response,
    )
    return observation


def _witness_summary(
    store: EffectStore,
    *,
    tool_name: str,
    operation_id: str = "op-1",
) -> dict[str, Any]:
    status = store.operation_status(
        tool_name=tool_name,
        operation_id=operation_id,
    )
    return {
        "attempt_count": len(status["attempts"]),
        "attempt_fault_mode_counts": dict(
            sorted(Counter(row["fault_mode"] for row in status["attempts"]).items())
        ),
        "attempt_state_counts": dict(
            sorted(Counter(row["state"] for row in status["attempts"]).items())
        ),
        "effect_count": status["effect_count"],
        "effect_payload_sha256": sorted(
            row["payload_sha256"] for row in status["effects"]
        ),
        "operation_id": operation_id,
        "tool_name": tool_name,
    }


def _base_case(
    root: Path,
    *,
    scenario_id: str,
    tool_name: str,
    retry_budget: int,
) -> tuple[Path, Path, ClientJournal, EffectStore]:
    case_root = root / scenario_id
    case_root.mkdir(parents=True)
    effect_database = case_root / "effects.sqlite"
    journal_database = case_root / "client.sqlite"
    journal = ClientJournal(journal_database)
    journal.create_operation(
        scenario_id=scenario_id,
        operation_id="op-1",
        payload={"value": 1},
        retry_budget=retry_budget,
    )
    return (
        effect_database,
        journal_database,
        journal,
        EffectStore(effect_database),
    )


def _sequential_duplicate(
    root: Path,
    *,
    scenario_id: str,
    tool_name: str,
    control_effect_count: int,
) -> dict[str, Any]:
    effect_db, _, journal, store = _base_case(
        root,
        scenario_id=scenario_id,
        tool_name=tool_name,
        retry_budget=1,
    )
    fixture = FixtureProcess(database=effect_db)
    arguments = _arguments()
    with fixture:
        tools = _tool_map(fixture.url)
        first = _observe(
            journal=journal,
            scenario_id=scenario_id,
            attempt_id="a1",
            url=fixture.url,
            tool_name=tool_name,
            arguments=arguments,
        )
        second = _observe(
            journal=journal,
            scenario_id=scenario_id,
            attempt_id="a2",
            url=fixture.url,
            tool_name=tool_name,
            arguments=arguments,
        )
    effects = _witness_summary(store, tool_name=tool_name)
    observations = [first, second]
    evidence_established = (
        all(observation.succeeded for observation in observations)
        and effects["attempt_count"] == 2
    )
    result = _idempotent_result(
        effect_count=effects["effect_count"],
        evidence_established=evidence_established,
    )
    return {
        "contract_basis": "idempotentHint=true with repeated identical arguments",
        "contract_result": result,
        "client_outcome": _client_success(observations),
        "declared_annotations": tools[tool_name]["annotations"],
        "declared_input_schema": tools[tool_name]["inputSchema"],
        "evidence_checks": {
            **_declaration_checks(tools[tool_name], hint="idempotentHint"),
            "both_calls_succeeded": all(
                observation.succeeded for observation in observations
            ),
            "clean_fault_plan_is_exact": (
                effects["attempt_fault_mode_counts"] == {"clean": 2}
            ),
            "control_effect_count_is_exact": (
                effects["effect_count"] == control_effect_count
            ),
            "request_arguments_are_identical": _requests_are_identical(
                journal, count=2
            ),
            "server_attempt_count_is_two": effects["attempt_count"] == 2,
        },
        "expectation_input": {"expected_max_effects": 1},
        "observations": [observation.to_dict() for observation in observations],
        "protocol": _protocol(),
        "scenario_id": scenario_id,
        "stimulus": {
            "calls": 2,
            "fault": "clean",
            "policy": "direct_repeat",
            "request_argument_sha256s": _request_hashes(journal),
        },
        "witness": effects,
        "client_journal": journal.snapshot(),
    }


def _postcommit_blind_retry(
    root: Path,
    *,
    scenario_id: str,
    tool_name: str,
    control_effect_count: int,
) -> dict[str, Any]:
    effect_db, _, journal, store = _base_case(
        root,
        scenario_id=scenario_id,
        tool_name=tool_name,
        retry_budget=1,
    )
    fixture = FixtureProcess(
        database=effect_db,
        response_delay_seconds=0.6,
        fault_mode="post_commit_delay",
    )
    arguments = _arguments()
    with fixture:
        tools = _tool_map(fixture.url)
        first = _observe(
            journal=journal,
            scenario_id=scenario_id,
            attempt_id="a1",
            url=fixture.url,
            tool_name=tool_name,
            arguments=arguments,
            timeout_seconds=0.15,
        )
        before_retry = _wait_for_witness(
            store,
            tool_name=tool_name,
            attempt_count=1,
            effect_count=1,
        )
        journal.record_decision(
            scenario_id=scenario_id,
            event_type="BLIND_RETRY",
            state="RETRYING",
            payload={"reason": "ambiguous_transport_failure"},
        )
        second = _observe(
            journal=journal,
            scenario_id=scenario_id,
            attempt_id="a2",
            url=fixture.url,
            tool_name=tool_name,
            arguments=arguments,
        )
    effects = _witness_summary(store, tool_name=tool_name)
    evidence_established = (
        not first.completed
        and before_retry["attempt_count"] == 1
        and before_retry["effect_count"] == 1
        and second.succeeded
        and effects["attempt_count"] == 2
    )
    result = _idempotent_result(
        effect_count=effects["effect_count"],
        evidence_established=evidence_established,
    )
    return {
        "contract_basis": "idempotentHint=true after ambiguous response loss",
        "contract_result": result,
        "client_outcome": (
            ClientOutcome.SUCCEEDED if second.succeeded else ClientOutcome.UNKNOWN
        ),
        "declared_annotations": tools[tool_name]["annotations"],
        "declared_input_schema": tools[tool_name]["inputSchema"],
        "evidence_checks": {
            **_declaration_checks(tools[tool_name], hint="idempotentHint"),
            "control_effect_count_is_exact": (
                effects["effect_count"] == control_effect_count
            ),
            "fault_plan_is_exact": (
                effects["attempt_fault_mode_counts"]
                == {"clean": 1, "post_commit_delay": 1}
            ),
            "effect_committed_before_retry": (
                before_retry["attempt_count"] == 1 and before_retry["effect_count"] == 1
            ),
            "first_call_was_transport_ambiguous": not first.completed,
            "request_arguments_are_identical": _requests_are_identical(
                journal, count=2
            ),
            "retry_succeeded": second.succeeded,
            "server_attempt_count_is_two": effects["attempt_count"] == 2,
        },
        "expectation_input": {"expected_max_effects": 1},
        "intermediate_witness": {"before_retry": before_retry},
        "observations": [first.to_dict(), second.to_dict()],
        "protocol": _protocol(),
        "scenario_id": scenario_id,
        "stimulus": {
            "calls": 2,
            "fault": "post_commit_delay",
            "policy": "blind_retry",
            "request_argument_sha256s": _request_hashes(journal),
        },
        "witness": effects,
        "client_journal": journal.snapshot(),
    }


def _misleading_readonly(root: Path) -> dict[str, Any]:
    scenario_id = "readonly_misleading_clean"
    tool_name = "misleading_readonly_write"
    effect_db, _, journal, store = _base_case(
        root,
        scenario_id=scenario_id,
        tool_name=tool_name,
        retry_budget=0,
    )
    fixture = FixtureProcess(database=effect_db)
    arguments = _arguments()
    with fixture:
        tools = _tool_map(fixture.url)
        observation = _observe(
            journal=journal,
            scenario_id=scenario_id,
            attempt_id="a1",
            url=fixture.url,
            tool_name=tool_name,
            arguments=arguments,
        )
    effects = _witness_summary(store, tool_name=tool_name)
    evidence_established = observation.succeeded and effects["attempt_count"] == 1
    if not evidence_established:
        result = ContractResult.UNRESOLVED
    elif effects["effect_count"] == 0:
        result = ContractResult.MATCH
    else:
        result = ContractResult.MISMATCH
    return {
        "contract_basis": "readOnlyHint=true",
        "contract_result": result,
        "client_outcome": _client_success([observation]),
        "declared_annotations": tools[tool_name]["annotations"],
        "declared_input_schema": tools[tool_name]["inputSchema"],
        "evidence_checks": {
            **_declaration_checks(tools[tool_name], hint="readOnlyHint"),
            "call_succeeded": observation.succeeded,
            "clean_fault_plan_is_exact": (
                effects["attempt_fault_mode_counts"] == {"clean": 1}
            ),
            "negative_control_effect_count_is_one": effects["effect_count"] == 1,
            "server_attempt_count_is_one": effects["attempt_count"] == 1,
        },
        "expectation_input": {"expected_effects": 0},
        "observations": [observation.to_dict()],
        "protocol": _protocol(),
        "scenario_id": scenario_id,
        "stimulus": {
            "calls": 1,
            "fault": "clean",
            "policy": "direct",
            "request_argument_sha256s": _request_hashes(journal),
        },
        "witness": effects,
        "client_journal": journal.snapshot(),
    }


def _precommit_reconcile_retry(root: Path) -> dict[str, Any]:
    scenario_id = "stable_precommit_exit_reconcile_retry"
    tool_name = "truthful_idempotent_write"
    effect_db, _, journal, store = _base_case(
        root,
        scenario_id=scenario_id,
        tool_name=tool_name,
        retry_budget=1,
    )
    fixture = FixtureProcess(database=effect_db, fault_mode="pre_commit_exit")
    arguments = _arguments()
    fixture.start()
    try:
        tools = _tool_map(fixture.url)
        first = _observe(
            journal=journal,
            scenario_id=scenario_id,
            attempt_id="a1",
            url=fixture.url,
            tool_name=tool_name,
            arguments=arguments,
        )
        exit_code = fixture.wait()
        fixture.fault_mode = "clean"
        fixture.start()
        status_observation = call_tool_sync(
            fixture.url,
            name="operation_status",
            arguments={"tool_name": tool_name, "operation_id": "op-1"},
            timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
        )
        journal.record_reconciliation(
            scenario_id=scenario_id,
            completed=status_observation.completed,
            is_error=status_observation.is_error,
            exception_types=status_observation.exception_types,
            response=status_observation.response,
        )
        status = _structured(status_observation)
        before_retry = _witness_summary(store, tool_name=tool_name)
        if status["effect_count"] != 0 or exit_code != 86:
            raise AssertionError("pre-commit absence was not established")
        journal.record_decision(
            scenario_id=scenario_id,
            event_type="ABSENT_CONFIRMED",
            state=ClientOutcome.ABSENT_CONFIRMED,
            payload={"effect_count": 0, "server_exit_code": exit_code},
        )
        second = _observe(
            journal=journal,
            scenario_id=scenario_id,
            attempt_id="a2",
            url=fixture.url,
            tool_name=tool_name,
            arguments=arguments,
        )
    finally:
        fixture.stop()
    effects = _witness_summary(store, tool_name=tool_name)
    result = ContractResult.NOT_APPLICABLE
    return {
        "contract_basis": (
            "confirmed pre-commit absence does not exercise repeat-effect safety"
        ),
        "contract_result": result,
        "client_outcome": (
            ClientOutcome.SUCCEEDED if second.succeeded else ClientOutcome.UNKNOWN
        ),
        "declared_annotations": tools[tool_name]["annotations"],
        "declared_input_schema": tools[tool_name]["inputSchema"],
        "evidence_checks": {
            **_declaration_checks(tools[tool_name], hint="idempotentHint"),
            "absence_confirmed_before_retry": (
                status_observation.succeeded and status["effect_count"] == 0
            ),
            "fault_plan_is_exact": (
                effects["attempt_fault_mode_counts"]
                == {"clean": 1, "pre_commit_exit": 1}
            ),
            "first_call_was_transport_ambiguous": not first.completed,
            "precommit_exit_code_is_86": exit_code == 86,
            "request_arguments_are_identical": _requests_are_identical(
                journal, count=2
            ),
            "retry_succeeded": second.succeeded,
            "server_attempt_count_is_two": effects["attempt_count"] == 2,
            "truthful_control_effect_count_is_one": effects["effect_count"] == 1,
        },
        "expectation_input": {"expected_max_effects": 1},
        "intermediate_witness": {"before_retry": before_retry},
        "observations": [
            first.to_dict(),
            status_observation.to_dict(),
            second.to_dict(),
        ],
        "protocol": _protocol(),
        "scenario_id": scenario_id,
        "stimulus": {
            "calls": 2,
            "fault": "pre_commit_exit",
            "policy": "reconcile_then_retry_if_absent",
            "request_argument_sha256s": _request_hashes(journal),
        },
        "witness": effects,
        "client_journal": journal.snapshot(),
    }


def _postcommit_reconcile(root: Path, *, status_available: bool) -> dict[str, Any]:
    suffix = "reconcile" if status_available else "status_unavailable"
    scenario_id = f"stable_postcommit_exit_{suffix}"
    tool_name = "truthful_idempotent_write"
    effect_db, _, journal, store = _base_case(
        root,
        scenario_id=scenario_id,
        tool_name=tool_name,
        retry_budget=0,
    )
    fixture = FixtureProcess(database=effect_db, fault_mode="post_commit_exit")
    arguments = _arguments()
    fixture.start()
    try:
        tools = _tool_map(fixture.url)
        first = _observe(
            journal=journal,
            scenario_id=scenario_id,
            attempt_id="a1",
            url=fixture.url,
            tool_name=tool_name,
            arguments=arguments,
        )
        exit_code = fixture.wait()
        status_observation: CallObservation | None = None
        if status_available:
            fixture.fault_mode = "clean"
            fixture.start()
            status_observation = call_tool_sync(
                fixture.url,
                name="operation_status",
                arguments={"tool_name": tool_name, "operation_id": "op-1"},
                timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
            )
            journal.record_reconciliation(
                scenario_id=scenario_id,
                completed=status_observation.completed,
                is_error=status_observation.is_error,
                exception_types=status_observation.exception_types,
                response=status_observation.response,
            )
            status = _structured(status_observation)
            if status["effect_count"] != 1 or exit_code != 87:
                raise AssertionError("post-commit fact was not recovered")
            outcome = ClientOutcome.COMMITTED_CONFIRMED
            journal.record_decision(
                scenario_id=scenario_id,
                event_type="COMMITTED_CONFIRMED",
                state=outcome,
                payload={"effect_count": 1, "server_exit_code": exit_code},
            )
        else:
            outcome = ClientOutcome.UNRESOLVED
            journal.record_decision(
                scenario_id=scenario_id,
                event_type="RECONCILIATION_UNAVAILABLE",
                state=outcome,
                payload={"server_exit_code": exit_code},
            )
    finally:
        fixture.stop()
    effects = _witness_summary(store, tool_name=tool_name)
    observations = [first.to_dict()]
    if status_observation is not None:
        observations.append(status_observation.to_dict())
    status_check = (
        status_observation is not None and status_observation.succeeded
        if status_available
        else status_observation is None
    )
    return {
        "contract_basis": "single ambiguous call does not exercise repeat safety",
        "contract_result": ContractResult.NOT_APPLICABLE,
        "client_outcome": outcome,
        "declared_annotations": tools[tool_name]["annotations"],
        "declared_input_schema": tools[tool_name]["inputSchema"],
        "evidence_checks": {
            **_declaration_checks(tools[tool_name], hint="idempotentHint"),
            "first_call_was_transport_ambiguous": not first.completed,
            "fault_plan_is_exact": (
                effects["attempt_fault_mode_counts"] == {"post_commit_exit": 1}
            ),
            "postcommit_exit_code_is_87": exit_code == 87,
            "server_attempt_count_is_one": effects["attempt_count"] == 1,
            "server_effect_count_is_one": effects["effect_count"] == 1,
            "status_availability_matches_scenario": status_check,
        },
        "expectation_input": {"expected_max_effects": None},
        "observations": observations,
        "protocol": _protocol(),
        "scenario_id": scenario_id,
        "stimulus": {
            "calls": 1,
            "fault": "post_commit_exit",
            "policy": "reconcile_if_available",
            "request_argument_sha256s": _request_hashes(journal),
        },
        "witness": effects,
        "client_journal": journal.snapshot(),
    }


def _concurrent_duplicate(
    root: Path,
    *,
    scenario_id: str,
    tool_name: str,
) -> dict[str, Any]:
    effect_db, _, journal, store = _base_case(
        root,
        scenario_id=scenario_id,
        tool_name=tool_name,
        retry_budget=7,
    )
    fixture = FixtureProcess(database=effect_db)
    arguments = _arguments()
    with fixture:
        tools = _tool_map(fixture.url)
        attempt_ids = [f"a{index}" for index in range(1, 9)]
        for attempt_id in attempt_ids:
            journal.record_send(
                scenario_id=scenario_id,
                attempt_id=attempt_id,
                tool_name=tool_name,
                arguments=arguments,
            )

        barrier = threading.Barrier(len(attempt_ids), timeout=5.0)
        concurrency_lock = threading.Lock()
        in_flight = 0
        max_in_flight = 0
        barrier_passed = 0

        def invoke(_: str) -> CallObservation:
            nonlocal barrier_passed, in_flight, max_in_flight
            with concurrency_lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            try:
                barrier.wait()
                with concurrency_lock:
                    barrier_passed += 1
                return call_tool_sync(
                    fixture.url,
                    name=tool_name,
                    arguments=arguments,
                    timeout_seconds=CONCURRENT_MCP_TIMEOUT_SECONDS,
                )
            finally:
                with concurrency_lock:
                    in_flight -= 1

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            observations = list(executor.map(invoke, attempt_ids))
        for attempt_id, observation in zip(
            attempt_ids,
            observations,
            strict=True,
        ):
            journal.record_observation(
                scenario_id=scenario_id,
                attempt_id=attempt_id,
                completed=observation.completed,
                is_error=observation.is_error,
                exception_types=observation.exception_types,
                response=observation.response,
            )
    effects = _witness_summary(store, tool_name=tool_name)
    all_succeeded = all(observation.succeeded for observation in observations)
    evidence_established = all_succeeded and effects["attempt_count"] == 8
    concurrency_witness = {
        "barrier_parties": barrier.parties,
        "barrier_passed": barrier_passed,
        "max_in_flight": max_in_flight,
    }
    result = _idempotent_result(
        effect_count=effects["effect_count"],
        evidence_established=evidence_established,
    )
    control_effect_count = 1 if tool_name == "truthful_idempotent_write" else 8
    return {
        "contract_basis": "idempotentHint=true under eight identical concurrent calls",
        "contract_result": result,
        "client_outcome": _client_success(observations),
        "declared_annotations": tools[tool_name]["annotations"],
        "declared_input_schema": tools[tool_name]["inputSchema"],
        "evidence_checks": {
            **_declaration_checks(tools[tool_name], hint="idempotentHint"),
            "all_eight_calls_succeeded": all_succeeded,
            "clean_fault_plan_is_exact": (
                effects["attempt_fault_mode_counts"] == {"clean": 8}
            ),
            "concurrency_barrier_released_all_eight": (
                concurrency_witness
                == {
                    "barrier_parties": 8,
                    "barrier_passed": 8,
                    "max_in_flight": 8,
                }
            ),
            "control_effect_count_is_exact": (
                effects["effect_count"] == control_effect_count
            ),
            "request_arguments_are_identical": _requests_are_identical(
                journal, count=8
            ),
            "server_attempt_count_is_eight": effects["attempt_count"] == 8,
        },
        "expectation_input": {"expected_max_effects": 1},
        "concurrency_witness": concurrency_witness,
        "observations": [observation.to_dict() for observation in observations],
        "protocol": _protocol(),
        "scenario_id": scenario_id,
        "stimulus": {
            "calls": 8,
            "fault": "clean",
            "policy": "concurrent_repeat",
            "request_argument_sha256s": _request_hashes(journal),
        },
        "witness": effects,
        "client_journal": journal.snapshot(),
    }


def _scenarios() -> list[Scenario]:
    return [
        Scenario(
            "idempotent_truth_sequential",
            lambda root: _sequential_duplicate(
                root,
                scenario_id="idempotent_truth_sequential",
                tool_name="truthful_idempotent_write",
                control_effect_count=1,
            ),
            Expected(ContractResult.MATCH, ClientOutcome.SUCCEEDED),
        ),
        Scenario(
            "idempotent_misleading_sequential",
            lambda root: _sequential_duplicate(
                root,
                scenario_id="idempotent_misleading_sequential",
                tool_name="misleading_idempotent_write",
                control_effect_count=2,
            ),
            Expected(ContractResult.MISMATCH, ClientOutcome.SUCCEEDED),
        ),
        Scenario(
            "idempotent_truth_postcommit_blind_retry",
            lambda root: _postcommit_blind_retry(
                root,
                scenario_id="idempotent_truth_postcommit_blind_retry",
                tool_name="truthful_idempotent_write",
                control_effect_count=1,
            ),
            Expected(ContractResult.MATCH, ClientOutcome.SUCCEEDED),
        ),
        Scenario(
            "idempotent_misleading_postcommit_blind_retry",
            lambda root: _postcommit_blind_retry(
                root,
                scenario_id="idempotent_misleading_postcommit_blind_retry",
                tool_name="misleading_idempotent_write",
                control_effect_count=2,
            ),
            Expected(ContractResult.MISMATCH, ClientOutcome.SUCCEEDED),
        ),
        Scenario(
            "readonly_misleading_clean",
            _misleading_readonly,
            Expected(ContractResult.MISMATCH, ClientOutcome.SUCCEEDED),
        ),
        Scenario(
            "stable_precommit_exit_reconcile_retry",
            _precommit_reconcile_retry,
            Expected(ContractResult.NOT_APPLICABLE, ClientOutcome.SUCCEEDED),
        ),
        Scenario(
            "stable_postcommit_exit_reconcile",
            lambda root: _postcommit_reconcile(root, status_available=True),
            Expected(
                ContractResult.NOT_APPLICABLE,
                ClientOutcome.COMMITTED_CONFIRMED,
            ),
        ),
        Scenario(
            "stable_postcommit_exit_status_unavailable",
            lambda root: _postcommit_reconcile(root, status_available=False),
            Expected(ContractResult.NOT_APPLICABLE, ClientOutcome.UNRESOLVED),
        ),
        Scenario(
            "idempotent_truth_concurrent_8",
            lambda root: _concurrent_duplicate(
                root,
                scenario_id="idempotent_truth_concurrent_8",
                tool_name="truthful_idempotent_write",
            ),
            Expected(ContractResult.MATCH, ClientOutcome.SUCCEEDED),
        ),
        Scenario(
            "idempotent_misleading_concurrent_8",
            lambda root: _concurrent_duplicate(
                root,
                scenario_id="idempotent_misleading_concurrent_8",
                tool_name="misleading_idempotent_write",
            ),
            Expected(ContractResult.MISMATCH, ClientOutcome.SUCCEEDED),
        ),
    ]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_junit(
    path: Path,
    cases: list[dict[str, Any]],
) -> None:
    suite = ET.Element(
        "testsuite",
        {
            "name": "effect-witness-mcp",
            "tests": str(len(cases)),
            "failures": str(sum(not case["expectation_met"] for case in cases)),
        },
    )
    for case in cases:
        node = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "effect_witness.mcp",
                "name": case["scenario_id"],
            },
        )
        if not case["expectation_met"]:
            failure = ET.SubElement(node, "failure", {"message": "unexpected result"})
            failure.text = canonical_json(
                {
                    "actual": {
                        "client_outcome": case["client_outcome"],
                        "contract_result": case["contract_result"],
                    },
                    "expected": case["expected"],
                    "failed_evidence_checks": sorted(
                        name
                        for name, passed in case.get("evidence_checks", {}).items()
                        if passed is not True
                    ),
                }
            )
        output = ET.SubElement(node, "system-out")
        output.text = canonical_json(
            {
                "client_outcome": case["client_outcome"],
                "contract_result": case["contract_result"],
                "effect_count": case["witness"]["effect_count"],
                "failed_evidence_checks": sorted(
                    name
                    for name, passed in case.get("evidence_checks", {}).items()
                    if passed is not True
                ),
            }
        )
    ET.ElementTree(suite).write(
        path,
        encoding="utf-8",
        xml_declaration=True,
    )


def _manifest(output_dir: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(
        candidate
        for candidate in output_dir.rglob("*")
        if candidate.is_file() and candidate.name != "manifest.sha256"
    ):
        relative = path.relative_to(output_dir).as_posix()
        content = path.read_bytes()
        records.append(
            {
                "bytes": len(content),
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return records


def run_suite(
    output_dir: str | Path,
    *,
    work_dir: str | Path | None = None,
    source_revision: str = "UNCOMMITTED",
) -> dict[str, Any]:
    """Run all local MCP scenarios and seal machine-readable evidence."""

    if (
        source_revision != "UNCOMMITTED"
        and _SOURCE_REVISION.fullmatch(source_revision) is None
    ):
        raise ValueError(
            "source_revision must be UNCOMMITTED or a 40-character lowercase Git commit"
        )
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("output directory must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    work = Path(work_dir) if work_dir is not None else output / "_work"
    if work.exists():
        raise FileExistsError("work directory must be absent")
    work.mkdir(parents=True)
    cases: list[dict[str, Any]] = []
    try:
        for scenario in _scenarios():
            case = scenario.run(work)
            expected = {
                "client_outcome": scenario.expected.client_outcome,
                "contract_result": scenario.expected.contract_result,
            }
            case["expected"] = expected
            checks = case.get("evidence_checks")
            case["expectation_met"] = (
                case["client_outcome"] == scenario.expected.client_outcome
                and case["contract_result"] == scenario.expected.contract_result
                and isinstance(checks, dict)
                and bool(checks)
                and all(value is True for value in checks.values())
            )
            cases.append(case)
    finally:
        shutil.rmtree(work, ignore_errors=False)

    failed_scenarios = sorted(
        case["scenario_id"] for case in cases if case["expectation_met"] is not True
    )
    if not cases or failed_scenarios:
        diagnostics = [
            _failure_diagnostic(case)
            for case in cases
            if case.get("expectation_met") is not True
        ]
        if not diagnostics:
            diagnostics = [{"scenario_id": "none-ran"}]
        raise RuntimeError(
            "registered scenario matrix did not pass "
            f"({canonical_json(diagnostics)}); artifact was not sealed"
        )

    results_dir = output / "results"
    results_dir.mkdir()
    for case in cases:
        _write_json(results_dir / f"{case['scenario_id']}.json", case)
    counts = Counter(case["contract_result"] for case in cases)
    summary = {
        "all_expectations_met": all(case["expectation_met"] for case in cases),
        "blocked_claims": [
            "exactly-once execution",
            "official MCP certification",
            "production reliability",
            "security",
            "distributed consistency",
            "framework superiority",
            "external adoption",
        ],
        "contract_result_counts": dict(sorted(counts.items())),
        "dependencies": {
            "mcp": importlib.metadata.version("mcp"),
            "httpx": importlib.metadata.version("httpx"),
            "effect-witness": importlib.metadata.version("effect-witness"),
        },
        "evidence_scope": (
            "synthetic local SQLite effects over loopback MCP Streamable HTTP"
        ),
        "model_api_calls": 0,
        "paid_service_calls": 0,
        "runtime": {
            "implementation": platform.python_implementation(),
            "platform_system": platform.system(),
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
        },
        "scenario_count": len(cases),
        "schema_version": 2,
        "source_revision": source_revision,
    }
    _write_json(output / "summary.json", summary)
    _write_junit(output / "junit.xml", cases)
    manifest = _manifest(output)
    (output / "manifest.sha256").write_text(
        "".join(f"{record['sha256']}  {record['path']}\n" for record in manifest),
        encoding="utf-8",
        newline="\n",
    )
    return summary
