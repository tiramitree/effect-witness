"""Pure registered relationships for schema-v5 coding-agent evidence."""

from __future__ import annotations

from typing import Any

from .coding_registration import (
    INJECTED_TRAJECTORY_EXIT_CODE,
    MINI_SWE_AGENT_VERSION,
    MUTATION_ACTION_SHA256,
    OPERATION_ID,
    REGISTERED_TREES,
    SCENARIOS,
    UNRESOLVED_EXIT_CODE,
)
from .models import json_exact_equal

_COMPLETE_ROLES = ["system", "user", "assistant", "user", "assistant", "exit"]
_FAULT_ROLES = ["system", "user", "assistant", "user"]
_UNRESOLVED_ROLES = ["system", "user", "assistant", "exit"]


def _process(
    *,
    phase: str,
    exit_code: int,
    status: str,
    agent_exit_status: str,
    expected_error_type: str,
    observations: list[int],
    roles: list[str],
    model_query_count: int,
    trajectory_state: str,
) -> dict[str, Any]:
    return {
        "agent_exit_status": agent_exit_status,
        "declared_mutation_count": 1,
        "exit_code": exit_code,
        "expected_error_type": expected_error_type,
        "message_role_sequence": roles,
        "mini_swe_agent_version": MINI_SWE_AGENT_VERSION,
        "model_query_count": model_query_count,
        "observed_mutation_returncodes": observations,
        "phase": phase,
        "status": status,
        "stderr_empty": True,
        "stdout_record_count": 1,
        "trajectory_state": trajectory_state,
    }


def expected_processes(scenario_id: str) -> list[dict[str, Any]]:
    if scenario_id not in SCENARIOS:
        raise ValueError("unregistered coding-agent scenario")
    if scenario_id == "clean":
        return [
            _process(
                phase="initial",
                exit_code=0,
                status="completed",
                agent_exit_status="Submitted",
                expected_error_type="",
                observations=[0],
                roles=_COMPLETE_ROLES,
                model_query_count=2,
                trajectory_state="VALID_JSON",
            )
        ]
    processes = [
        _process(
            phase="initial",
            exit_code=INJECTED_TRAJECTORY_EXIT_CODE,
            status="trajectory_write_failed",
            agent_exit_status="",
            expected_error_type="InjectedTrajectoryWriteFailure",
            observations=[0],
            roles=_FAULT_ROLES,
            model_query_count=1,
            trajectory_state="INVALID_REGISTERED_PREFIX",
        )
    ]
    if scenario_id == "save_fault_blind_restart":
        processes.append(
            _process(
                phase="restart",
                exit_code=0,
                status="completed",
                agent_exit_status="Submitted",
                expected_error_type="",
                observations=[1],
                roles=_COMPLETE_ROLES,
                model_query_count=2,
                trajectory_state="VALID_JSON",
            )
        )
    elif scenario_id == "save_fault_reconcile":
        processes.append(
            _process(
                phase="restart",
                exit_code=0,
                status="completed",
                agent_exit_status="Submitted",
                expected_error_type="",
                observations=[0],
                roles=_COMPLETE_ROLES,
                model_query_count=2,
                trajectory_state="VALID_JSON",
            )
        )
    else:
        processes.append(
            _process(
                phase="restart",
                exit_code=UNRESOLVED_EXIT_CODE,
                status="unresolved",
                agent_exit_status="UnresolvedEffectState",
                expected_error_type="UnresolvedEffectState",
                observations=[],
                roles=_UNRESOLVED_ROLES,
                model_query_count=1,
                trajectory_state="VALID_JSON",
            )
        )
    return processes


def _journal_row(
    sequence: int,
    *,
    phase: str,
    decision: str,
    command_executed: bool,
    returncode: int | None,
    before: str,
    after: str,
) -> dict[str, Any]:
    return {
        "action_sha256": MUTATION_ACTION_SHA256,
        "after_tree_sha256": REGISTERED_TREES[after]["tree_sha256"],
        "before_tree_sha256": REGISTERED_TREES[before]["tree_sha256"],
        "command_executed": command_executed,
        "decision": decision,
        "operation_id": OPERATION_ID,
        "phase": phase,
        "returncode": returncode,
        "sequence": sequence,
    }


def expected_journal(scenario_id: str) -> list[dict[str, Any]]:
    rows = [
        _journal_row(
            1,
            phase="initial",
            decision="EXECUTED",
            command_executed=True,
            returncode=0,
            before="PRE",
            after="POST",
        )
    ]
    if scenario_id == "save_fault_blind_restart":
        rows.append(
            _journal_row(
                2,
                phase="restart",
                decision="EXECUTED",
                command_executed=True,
                returncode=1,
                before="POST",
                after="POST",
            )
        )
    elif scenario_id == "save_fault_reconcile":
        rows.append(
            _journal_row(
                2,
                phase="restart",
                decision="RECONCILED",
                command_executed=False,
                returncode=0,
                before="POST",
                after="POST",
            )
        )
    elif scenario_id == "save_fault_reconcile_tampered":
        rows.append(
            _journal_row(
                2,
                phase="restart",
                decision="UNRESOLVED",
                command_executed=False,
                returncode=None,
                before="TAMPERED",
                after="TAMPERED",
            )
        )
    return rows


def expected_snapshots(scenario_id: str) -> dict[str, Any]:
    if scenario_id == "save_fault_reconcile_tampered":
        return {
            "s0": REGISTERED_TREES["PRE"],
            "s1": REGISTERED_TREES["POST"],
            "s2": REGISTERED_TREES["TAMPERED"],
            "s3": REGISTERED_TREES["TAMPERED"],
        }
    return {
        "s0": REGISTERED_TREES["PRE"],
        "s1": REGISTERED_TREES["POST"],
        "s2": REGISTERED_TREES["POST"],
        "s3": REGISTERED_TREES["POST"],
    }


def expected_validations(scenario_id: str) -> dict[str, Any]:
    tampered = scenario_id == "save_fault_reconcile_tampered"
    return {
        "s0": {"output_included": False, "returncode": 1, "status": "FAILED"},
        "s1": {"output_included": False, "returncode": 0, "status": "PASSED"},
        "s2": {
            "output_included": False,
            "returncode": 1 if tampered else 0,
            "status": "FAILED" if tampered else "PASSED",
        },
        "s3": {
            "output_included": False,
            "returncode": 1 if tampered else 0,
            "status": "FAILED" if tampered else "PASSED",
        },
    }


def expected_changed_paths(scenario_id: str) -> dict[str, list[str]]:
    return {
        "s0": [],
        "s1": ["src/calculator.py"],
        "s2": ["src/calculator.py"],
        "s3": ["src/calculator.py"],
    }


def evaluate_round(
    scenario_id: str,
    *,
    processes: Any,
    journal: Any,
    snapshots: Any,
    validations: Any,
    changed_paths: Any,
) -> dict[str, bool]:
    """Recompute the exact fixed scenario without importing mini-swe-agent."""

    if scenario_id not in SCENARIOS:
        raise ValueError("unregistered coding-agent scenario")
    process_expectation = expected_processes(scenario_id)
    journal_expectation = expected_journal(scenario_id)
    command_executions = (
        sum(
            item.get("command_executed") is True
            for item in journal
            if isinstance(item, dict)
        )
        if isinstance(journal, list)
        else -1
    )
    expected_executions = 2 if scenario_id == "save_fault_blind_restart" else 1
    decisions = (
        [item.get("decision") for item in journal]
        if isinstance(journal, list) and all(isinstance(item, dict) for item in journal)
        else None
    )
    expected_decisions = [item["decision"] for item in journal_expectation]
    return {
        "changed_paths_registered": json_exact_equal(
            changed_paths,
            expected_changed_paths(scenario_id),
        ),
        "command_execution_count_registered": (
            command_executions == expected_executions
        ),
        "journal_decisions_registered": decisions == expected_decisions,
        "journal_registered": json_exact_equal(journal, journal_expectation),
        "processes_registered": json_exact_equal(processes, process_expectation),
        "snapshots_registered": json_exact_equal(
            snapshots,
            expected_snapshots(scenario_id),
        ),
        "validations_registered": json_exact_equal(
            validations,
            expected_validations(scenario_id),
        ),
    }
