"""Strict offline verifier for schema-v5 mini-swe-agent evidence."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any

from .artifact import (
    _artifact_snapshot,
    _is_link_or_reparse,
    _load_manifest,
    _read_json,
    _verify_hashes,
)
from .coding_registration import (
    BLOCKED_CLAIMS,
    EVIDENCE_BOUNDARY,
    EVIDENCE_SCOPE,
    INJECTED_TRAJECTORY_EXIT_CODE,
    LANE,
    MACHINE_ARCHITECTURE,
    MINI_SWE_AGENT_DEVELOPMENT_STATUS,
    MINI_SWE_AGENT_LICENSE,
    MINI_SWE_AGENT_PYTHON_REQUIRES,
    MINI_SWE_AGENT_RUNTIME_FILES,
    MINI_SWE_AGENT_VERSION,
    MINI_SWE_AGENT_WHEEL,
    MINI_SWE_AGENT_WHEEL_BYTES,
    MINI_SWE_AGENT_WHEEL_SHA256,
    MINI_SWE_AGENT_WHEEL_URL,
    MUTATION_ACTION_SHA256,
    OPERATION_ID,
    PYTHON_CONSTRAINT_PACKAGE_COUNT,
    PYTHON_CONSTRAINTS_SHA256,
    REGISTERED_FIXTURE_PATHS,
    REGISTERED_ROUNDS,
    REGISTERED_TREES,
    SCENARIO_ORDER,
    SCENARIOS,
    SCHEMA_VERSION,
    UNRESOLVED_EXIT_CODE,
)
from .models import canonical_json, json_exact_equal, sha256_json, strict_json_loads

_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40}$")
_PYTHON_VERSION = re.compile(r"^3\.12\.\d+$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_PRODUCER_VERSIONS = ("0.4.0",)
_STATE_KEYS = ("s0", "s1", "s2", "s3")
_CASE_FIELDS = {
    "all_registered_checks_met",
    "fault",
    "policy",
    "restart",
    "round_count",
    "rounds",
    "scenario_id",
    "tamper",
}
_ROUND_FIELDS = {
    "all_checks_met",
    "changed_paths",
    "checks",
    "journal",
    "processes",
    "round",
    "scenario_id",
    "snapshots",
    "validations",
}
_CHECK_FIELDS = {
    "changed_paths_registered",
    "command_execution_count_registered",
    "journal_decisions_registered",
    "journal_registered",
    "processes_registered",
    "snapshots_registered",
    "validations_registered",
}
_PROCESS_FIELDS = {
    "agent_exit_status",
    "declared_mutation_count",
    "exit_code",
    "expected_error_type",
    "message_role_sequence",
    "mini_swe_agent_version",
    "model_query_count",
    "observed_mutation_returncodes",
    "phase",
    "status",
    "stderr_empty",
    "stdout_record_count",
    "trajectory_state",
}
_JOURNAL_FIELDS = {
    "action_sha256",
    "after_tree_sha256",
    "before_tree_sha256",
    "command_executed",
    "decision",
    "operation_id",
    "phase",
    "returncode",
    "sequence",
}
_VALIDATION_FIELDS = {"output_included", "returncode", "status"}
_EXPECTED_DIRECTORIES = frozenset({".", "results"})
_EXPECTED_FILES = frozenset(
    {
        "junit.xml",
        "manifest.sha256",
        "provenance.json",
        "summary.json",
        *(f"results/{scenario_id}.json" for scenario_id in SCENARIO_ORDER),
    }
)
_MANIFEST_FILES = _EXPECTED_FILES - {"manifest.sha256"}
_DIAGNOSTIC_PATHS = _EXPECTED_DIRECTORIES | _EXPECTED_FILES


def _append(errors: list[str], label: str, message: str) -> None:
    errors.append(f"{label}: {message}")


def _safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value == ".":
        return False
    path = PurePosixPath(value)
    return not (
        "\\" in value
        or ":" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or any(ord(character) < 32 for character in value)
    )


def _valid_tree(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"entries", "tree_sha256"}:
        return False
    entries = value["entries"]
    tree_sha256 = value["tree_sha256"]
    if (
        not isinstance(entries, list)
        or not isinstance(tree_sha256, str)
        or _HEX64.fullmatch(tree_sha256) is None
        or sha256_json(entries) != tree_sha256
    ):
        return False
    paths: list[str] = []
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"bytes", "kind", "path", "sha256"}
            or entry.get("kind") != "file"
            or type(entry.get("bytes")) is not int
            or entry["bytes"] < 0
            or not isinstance(entry.get("sha256"), str)
            or _HEX64.fullmatch(entry["sha256"]) is None
            or not _safe_relative_path(entry.get("path"))
        ):
            return False
        paths.append(entry["path"])
    return paths == sorted(set(paths)) and tuple(paths) == REGISTERED_FIXTURE_PATHS


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


def _expected_processes(scenario_id: str) -> list[dict[str, Any]]:
    if scenario_id == "clean":
        return [
            _process(
                phase="initial",
                exit_code=0,
                status="completed",
                agent_exit_status="Submitted",
                expected_error_type="",
                observations=[0],
                roles=["system", "user", "assistant", "user", "assistant", "exit"],
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
            roles=["system", "user", "assistant", "user"],
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
                roles=["system", "user", "assistant", "user", "assistant", "exit"],
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
                roles=["system", "user", "assistant", "user", "assistant", "exit"],
                model_query_count=2,
                trajectory_state="VALID_JSON",
            )
        )
    elif scenario_id == "save_fault_reconcile_tampered":
        processes.append(
            _process(
                phase="restart",
                exit_code=UNRESOLVED_EXIT_CODE,
                status="unresolved",
                agent_exit_status="UnresolvedEffectState",
                expected_error_type="UnresolvedEffectState",
                observations=[],
                roles=["system", "user", "assistant", "exit"],
                model_query_count=1,
                trajectory_state="VALID_JSON",
            )
        )
    else:
        raise ValueError("unregistered coding-agent scenario")
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


def _expected_journal(scenario_id: str) -> list[dict[str, Any]]:
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
    elif scenario_id != "clean":
        raise ValueError("unregistered coding-agent scenario")
    return rows


def _expected_snapshots(scenario_id: str) -> dict[str, Any]:
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


def _expected_validations(scenario_id: str) -> dict[str, Any]:
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


def _expected_changed_paths(scenario_id: str) -> dict[str, list[str]]:
    if scenario_id not in SCENARIOS:
        raise ValueError("unregistered coding-agent scenario")
    return {
        "s0": [],
        "s1": ["src/calculator.py"],
        "s2": ["src/calculator.py"],
        "s3": ["src/calculator.py"],
    }


def _registered_checks(
    scenario_id: str,
    *,
    processes: Any,
    journal: Any,
    snapshots: Any,
    validations: Any,
    changed_paths: Any,
) -> dict[str, bool]:
    expected_journal = _expected_journal(scenario_id)
    command_executions = (
        sum(
            row.get("command_executed") is True
            for row in journal
            if isinstance(row, dict)
        )
        if isinstance(journal, list)
        else -1
    )
    decisions = (
        [row.get("decision") for row in journal]
        if isinstance(journal, list) and all(isinstance(row, dict) for row in journal)
        else None
    )
    expected_executions = 2 if scenario_id == "save_fault_blind_restart" else 1
    return {
        "changed_paths_registered": json_exact_equal(
            changed_paths,
            _expected_changed_paths(scenario_id),
        ),
        "command_execution_count_registered": (
            command_executions == expected_executions
        ),
        "journal_decisions_registered": (
            decisions == [row["decision"] for row in expected_journal]
        ),
        "journal_registered": json_exact_equal(journal, expected_journal),
        "processes_registered": json_exact_equal(
            processes,
            _expected_processes(scenario_id),
        ),
        "snapshots_registered": json_exact_equal(
            snapshots,
            _expected_snapshots(scenario_id),
        ),
        "validations_registered": json_exact_equal(
            validations,
            _expected_validations(scenario_id),
        ),
    }


def _nested_shapes_registered(
    value: dict[str, Any],
    label: str,
    errors: list[str],
) -> None:
    processes = value.get("processes")
    if not isinstance(processes, list) or any(
        not isinstance(process, dict) or set(process) != _PROCESS_FIELDS
        for process in processes
    ):
        _append(errors, label, "process record fields differ from registration")
    journal = value.get("journal")
    if not isinstance(journal, list) or any(
        not isinstance(row, dict) or set(row) != _JOURNAL_FIELDS for row in journal
    ):
        _append(errors, label, "journal record fields differ from registration")
    snapshots = value.get("snapshots")
    if not isinstance(snapshots, dict) or set(snapshots) != set(_STATE_KEYS):
        _append(errors, label, "snapshot fields differ from registration")
    else:
        for state in _STATE_KEYS:
            if not _valid_tree(snapshots[state]):
                _append(errors, label, f"{state.upper()} snapshot shape is invalid")
    validations = value.get("validations")
    if (
        not isinstance(validations, dict)
        or set(validations) != set(_STATE_KEYS)
        or any(
            not isinstance(validations.get(state), dict)
            or set(validations[state]) != _VALIDATION_FIELDS
            for state in _STATE_KEYS
        )
    ):
        _append(errors, label, "validation fields differ from registration")
    changed_paths = value.get("changed_paths")
    if (
        not isinstance(changed_paths, dict)
        or set(changed_paths) != set(_STATE_KEYS)
        or any(
            not isinstance(changed_paths.get(state), list)
            or any(
                not _safe_relative_path(path) or path not in REGISTERED_FIXTURE_PATHS
                for path in changed_paths[state]
            )
            for state in _STATE_KEYS
        )
    ):
        _append(errors, label, "changed-path fields differ from registration")


def _verify_round(
    value: Any,
    *,
    expected_round: int,
    scenario_id: str,
    errors: list[str],
) -> dict[str, Any] | None:
    label = f"{scenario_id}/round-{expected_round:02d}"
    if not isinstance(value, dict):
        _append(errors, label, "round is not an object")
        return None
    if set(value) != _ROUND_FIELDS:
        _append(errors, label, "round fields differ from registration")
    if value.get("scenario_id") != scenario_id:
        _append(errors, label, "scenario identifier differs from registration")
    if type(value.get("round")) is not int or value.get("round") != expected_round:
        _append(errors, label, "round index differs from registration")
    _nested_shapes_registered(value, label, errors)
    try:
        expected_checks = _registered_checks(
            scenario_id,
            processes=value.get("processes"),
            journal=value.get("journal"),
            snapshots=value.get("snapshots"),
            validations=value.get("validations"),
            changed_paths=value.get("changed_paths"),
        )
    except (KeyError, TypeError, ValueError):
        _append(errors, label, "registered relationships could not be recomputed")
        return value
    checks = value.get("checks")
    if not isinstance(checks, dict) or set(checks) != _CHECK_FIELDS:
        _append(errors, label, "check fields differ from registration")
    if not json_exact_equal(checks, expected_checks):
        _append(errors, label, "registered checks are inconsistent")
    if any(passed is not True for passed in expected_checks.values()):
        _append(errors, label, "registered relationships did not all pass")
    expected_flag = all(passed is True for passed in expected_checks.values())
    if value.get("all_checks_met") is not expected_flag:
        _append(errors, label, "round pass flag is inconsistent")
    if value.get("all_checks_met") is not True:
        _append(errors, label, "registered round did not pass")
    return value


def _verify_case(
    value: Any,
    *,
    scenario_id: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _append(errors, scenario_id, "result is not an object")
        return None
    if set(value) != _CASE_FIELDS:
        _append(errors, scenario_id, "result fields differ from registration")
    registration = SCENARIOS[scenario_id]
    if value.get("scenario_id") != scenario_id:
        _append(errors, scenario_id, "scenario identifier differs from filename")
    for field in ("fault", "policy", "restart", "tamper"):
        if not json_exact_equal(value.get(field), registration[field]):
            _append(errors, scenario_id, f"{field} differs from registration")
    if (
        type(value.get("round_count")) is not int
        or value.get("round_count") != REGISTERED_ROUNDS
    ):
        _append(errors, scenario_id, "round count differs from registration")
    rounds = value.get("rounds")
    if not isinstance(rounds, list) or len(rounds) != REGISTERED_ROUNDS:
        _append(errors, scenario_id, "round list differs from registration")
        return value
    verified_rounds = [
        _verify_round(
            round_value,
            expected_round=round_index,
            scenario_id=scenario_id,
            errors=errors,
        )
        for round_index, round_value in enumerate(rounds, start=1)
    ]
    expected_flag = all(
        isinstance(round_value, dict) and round_value.get("all_checks_met") is True
        for round_value in verified_rounds
    )
    if value.get("all_registered_checks_met") is not expected_flag:
        _append(errors, scenario_id, "case pass flag is inconsistent")
    if value.get("all_registered_checks_met") is not True:
        _append(errors, scenario_id, "registered case did not pass")
    return value


def _expected_provenance(*, historical: bool = False) -> dict[str, Any]:
    return {
        "mini_swe_agent": {
            "development_status": MINI_SWE_AGENT_DEVELOPMENT_STATUS,
            "license": MINI_SWE_AGENT_LICENSE,
            "python_requires": MINI_SWE_AGENT_PYTHON_REQUIRES,
            "runtime_files": MINI_SWE_AGENT_RUNTIME_FILES,
            "version": MINI_SWE_AGENT_VERSION,
            "wheel_bytes": MINI_SWE_AGENT_WHEEL_BYTES,
            "wheel_filename": MINI_SWE_AGENT_WHEEL,
            "wheel_in_artifact": False,
            "wheel_sha256": MINI_SWE_AGENT_WHEEL_SHA256,
            "wheel_url": MINI_SWE_AGENT_WHEEL_URL,
        },
        "model_api_calls": 0,
        "paid_service_calls": 0,
        "python_constraint_package_count": PYTHON_CONSTRAINT_PACKAGE_COUNT,
        "python_constraints_are_hash_lock": False,
        "python_constraints_sha256": (
            "a2a4b3cf0af75c357e1e4578d0cc4b0ffa222dcb9358a0b60a4e3a47512196eb"
            if historical
            else PYTHON_CONSTRAINTS_SHA256
        ),
        "raw_trajectory_in_artifact": False,
        "selected_runtime_bytes_verified": True,
    }


def _round_records(cases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for scenario_id in SCENARIO_ORDER:
        case = cases.get(scenario_id)
        if not isinstance(case, dict) or not isinstance(case.get("rounds"), list):
            continue
        records.extend(
            round_value
            for round_value in case["rounds"]
            if isinstance(round_value, dict)
        )
    return records


def _verify_summary(
    summary: Any,
    *,
    cases: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(summary, dict):
        errors.append("summary.json is not an object")
        return None
    expected_fields = {
        "all_registered_checks_met",
        "blocked_claims",
        "command_execution_count",
        "declared_mutation_count",
        "declared_source_revision",
        "dependencies",
        "dependency_constraint_package_count",
        "evidence_boundary",
        "evidence_scope",
        "lane",
        "model_api_calls",
        "paid_service_calls",
        "registered_rounds",
        "runtime",
        "scenario_count",
        "schema_version",
        "source_revision_verification",
        "worker_process_count",
    }
    if set(summary) != expected_fields:
        errors.append("summary fields differ from schema-v5 registration")
    if (
        type(summary.get("schema_version")) is not int
        or summary.get("schema_version") != SCHEMA_VERSION
    ):
        errors.append("unsupported summary schema_version")
    if summary.get("lane") != LANE:
        errors.append("summary lane differs from registration")
    if type(summary.get("scenario_count")) is not int or summary.get(
        "scenario_count"
    ) != len(SCENARIO_ORDER):
        errors.append("summary scenario_count differs from registration")
    if (
        type(summary.get("registered_rounds")) is not int
        or summary.get("registered_rounds") != REGISTERED_ROUNDS
    ):
        errors.append("summary registered_rounds differs from registration")
    if summary.get("all_registered_checks_met") is not True:
        errors.append("summary registered checks did not all pass")
    if not json_exact_equal(summary.get("blocked_claims"), list(BLOCKED_CLAIMS)):
        errors.append("summary blocked_claims differ from registration")
    if not json_exact_equal(summary.get("evidence_boundary"), EVIDENCE_BOUNDARY):
        errors.append("summary evidence boundary differs from registration")
    if summary.get("evidence_scope") != EVIDENCE_SCOPE:
        errors.append("summary evidence scope differs from registration")
    for field in ("model_api_calls", "paid_service_calls"):
        if type(summary.get(field)) is not int or summary.get(field) != 0:
            errors.append(f"summary {field} is invalid")
    dependencies = summary.get("dependencies")
    if (
        not isinstance(dependencies, dict)
        or set(dependencies) != {"effect-witness", "mini-swe-agent"}
        or dependencies.get("effect-witness") not in _PRODUCER_VERSIONS
        or dependencies.get("mini-swe-agent") != MINI_SWE_AGENT_VERSION
    ):
        errors.append("summary dependencies differ from registration")
    if (
        type(summary.get("dependency_constraint_package_count")) is not int
        or summary.get("dependency_constraint_package_count")
        != PYTHON_CONSTRAINT_PACKAGE_COUNT
    ):
        errors.append("summary dependency constraint count is inconsistent")
    runtime = summary.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {
        "implementation",
        "machine_architecture",
        "platform_system",
        "python",
    }:
        errors.append("summary runtime fields differ from registration")
    else:
        if runtime.get("implementation") != "CPython":
            errors.append("summary Python implementation differs from registration")
        if runtime.get("machine_architecture") != MACHINE_ARCHITECTURE:
            errors.append("summary machine architecture differs from registration")
        if runtime.get("platform_system") not in {"Linux", "Windows"}:
            errors.append("summary platform is not registered")
        if (
            not isinstance(runtime.get("python"), str)
            or _PYTHON_VERSION.fullmatch(runtime["python"]) is None
        ):
            errors.append("summary runtime python is invalid")
    source_revision = summary.get("declared_source_revision")
    if source_revision != "UNCOMMITTED" and (
        not isinstance(source_revision, str)
        or _SOURCE_REVISION.fullmatch(source_revision) is None
    ):
        errors.append("summary declared_source_revision is invalid")
    if summary.get("source_revision_verification") != "caller_declared":
        errors.append("summary source revision verification differs from registration")

    records = _round_records(cases)
    expected_command_count = REGISTERED_ROUNDS * sum(
        sum(row["command_executed"] is True for row in _expected_journal(scenario_id))
        for scenario_id in SCENARIO_ORDER
    )
    observed_command_count = sum(
        row.get("command_executed") is True
        for record in records
        if isinstance(record.get("journal"), list)
        for row in record["journal"]
        if isinstance(row, dict)
    )
    if (
        type(summary.get("command_execution_count")) is not int
        or summary.get("command_execution_count") != expected_command_count
        or summary.get("command_execution_count") != observed_command_count
    ):
        errors.append("summary command execution count is inconsistent")

    expected_worker_count = REGISTERED_ROUNDS * sum(
        len(_expected_processes(scenario_id)) for scenario_id in SCENARIO_ORDER
    )
    observed_worker_count = sum(
        len(record["processes"])
        for record in records
        if isinstance(record.get("processes"), list)
    )
    if (
        type(summary.get("worker_process_count")) is not int
        or summary.get("worker_process_count") != expected_worker_count
        or summary.get("worker_process_count") != observed_worker_count
    ):
        errors.append("summary worker process count is inconsistent")

    mutation_values = [
        process.get("declared_mutation_count")
        for record in records
        if isinstance(record.get("processes"), list)
        for process in record["processes"]
        if isinstance(process, dict)
    ]
    observed_mutation_count: int | None = (
        sum(mutation_values)
        if all(type(value) is int for value in mutation_values)
        else None
    )
    if (
        type(summary.get("declared_mutation_count")) is not int
        or summary.get("declared_mutation_count") != expected_worker_count
        or summary.get("declared_mutation_count") != observed_mutation_count
    ):
        errors.append("summary declared mutation count is inconsistent")
    if len(cases) != len(SCENARIO_ORDER):
        errors.append("summary scenario count differs from result files")
    if not all(
        isinstance(cases.get(scenario_id), dict)
        and cases[scenario_id].get("all_registered_checks_met") is True
        for scenario_id in SCENARIO_ORDER
    ):
        errors.append("summary pass flag disagrees with result files")
    return summary


def _verify_junit(
    content: bytes | None,
    cases: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    if content is None:
        errors.append("junit.xml is missing or unavailable")
        return
    expected_suite = ET.Element(
        "testsuite",
        {
            "failures": "0",
            "name": "effect-witness-mini-swe-agent",
            "tests": str(len(SCENARIO_ORDER) * REGISTERED_ROUNDS),
        },
    )
    expected_names: list[str] = []
    for scenario_id in SCENARIO_ORDER:
        for round_index in range(1, REGISTERED_ROUNDS + 1):
            name = f"{scenario_id}/round-{round_index:02d}"
            expected_names.append(name)
            node = ET.SubElement(
                expected_suite,
                "testcase",
                {
                    "classname": "effect_witness.mini_swe_agent",
                    "name": name,
                },
            )
            output = ET.SubElement(node, "system-out")
            output.text = canonical_json(
                {
                    "failed_checks": [],
                    "round": round_index,
                    "scenario_id": scenario_id,
                }
            )
    expected_bytes = ET.tostring(
        expected_suite,
        encoding="utf-8",
        xml_declaration=True,
    )
    if content != expected_bytes:
        errors.append("JUnit bytes differ from canonical registration")
        return
    try:
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        suite = ET.fromstring(content, parser=parser)
    except ET.ParseError as error:
        errors.append(f"junit.xml is invalid ({type(error).__name__})")
        return
    expected_count = len(expected_names)
    if suite.tag != "testsuite" or suite.attrib != {
        "failures": "0",
        "name": "effect-witness-mini-swe-agent",
        "tests": str(expected_count),
    }:
        errors.append("JUnit suite differs from registration")
        return
    if suite.text is not None or suite.tail is not None:
        errors.append("JUnit suite text differs from registration")
        return
    nodes = list(suite)
    if (
        len(nodes) != expected_count
        or any(node.tag != "testcase" for node in nodes)
        or [node.get("name") for node in nodes] != expected_names
    ):
        errors.append("JUnit testcase sequence is inconsistent")
        return
    for position, (node, name) in enumerate(zip(nodes, expected_names, strict=True)):
        scenario_index, round_offset = divmod(position, REGISTERED_ROUNDS)
        scenario_id = SCENARIO_ORDER[scenario_index]
        round_index = round_offset + 1
        if node.attrib != {
            "classname": "effect_witness.mini_swe_agent",
            "name": name,
        }:
            _append(errors, name, "JUnit attributes are inconsistent")
        if node.text is not None or node.tail is not None:
            _append(errors, name, "JUnit testcase text is inconsistent")
        children = list(node)
        if [child.tag for child in children] != ["system-out"]:
            _append(errors, name, "JUnit children are inconsistent")
            continue
        output = children[0]
        if (
            output.attrib
            or list(output)
            or output.text is None
            or output.tail is not None
        ):
            _append(errors, name, "JUnit system-out shape is invalid")
            continue
        try:
            observed = strict_json_loads(output.text)
        except (ValueError, RecursionError):
            observed = None
        expected = {
            "failed_checks": [],
            "round": round_index,
            "scenario_id": scenario_id,
        }
        if not json_exact_equal(observed, expected):
            _append(errors, name, "JUnit system-out is inconsistent")
        case = cases.get(scenario_id)
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("rounds"), list)
            or len(case["rounds"]) < round_index
            or not isinstance(case["rounds"][round_index - 1], dict)
            or case["rounds"][round_index - 1].get("all_checks_met") is not True
        ):
            _append(errors, name, "JUnit testcase has no passing result round")


def _verify_coding_agent_artifact_impl(
    artifact_dir: str | Path,
) -> dict[str, Any]:
    root = Path(artifact_dir)
    errors: list[str] = []
    if not root.is_dir() or _is_link_or_reparse(root):
        return {
            "artifact_schema_version": None,
            "errors": ["artifact directory is missing or is not a regular directory"],
            "files_hashed": 0,
            "lane": LANE,
            "round_count": 0,
            "scenario_count": 0,
            "verified": False,
            "verification_scope": (
                "offline integrity and internal consistency; not authenticity"
            ),
        }
    actual_files, snapshot = _artifact_snapshot(
        root,
        errors,
        diagnostic_paths=_DIAGNOSTIC_PATHS,
        expected_directories=_EXPECTED_DIRECTORIES,
    )
    manifest = _load_manifest(
        snapshot,
        errors,
        diagnostic_paths=_DIAGNOSTIC_PATHS,
    )
    _verify_hashes(
        snapshot,
        manifest,
        actual_files,
        errors,
        diagnostic_paths=_DIAGNOSTIC_PATHS,
    )
    if any(not _safe_relative_path(path) for path in manifest):
        errors.append("manifest contains an unsafe path")
    if set(manifest) != _MANIFEST_FILES:
        errors.append("manifest closure differs from registration")
    else:
        expected_manifest = "".join(
            f"{manifest[path]}  {path}\n" for path in sorted(_MANIFEST_FILES)
        ).encode("utf-8")
        if snapshot.get("manifest.sha256") != expected_manifest:
            errors.append("manifest bytes differ from canonical registration")
    if actual_files != _EXPECTED_FILES:
        errors.append("artifact file inventory differs from registration")

    cases: dict[str, dict[str, Any]] = {}
    for scenario_id in SCENARIO_ORDER:
        case = _verify_case(
            _read_json(snapshot, f"results/{scenario_id}.json", errors),
            scenario_id=scenario_id,
            errors=errors,
        )
        if case is not None:
            cases[scenario_id] = case
    provenance = _read_json(snapshot, "provenance.json", errors)
    if not any(
        json_exact_equal(provenance, _expected_provenance(historical=historical))
        for historical in (False, True)
    ):
        errors.append("provenance.json differs from registration")
    summary = _verify_summary(
        _read_json(snapshot, "summary.json", errors),
        cases=cases,
        errors=errors,
    )
    _verify_junit(snapshot.get("junit.xml"), cases, errors)
    return {
        "artifact_schema_version": (
            SCHEMA_VERSION
            if isinstance(summary, dict)
            and type(summary.get("schema_version")) is int
            and summary.get("schema_version") == SCHEMA_VERSION
            else None
        ),
        "errors": sorted(set(errors)),
        "files_hashed": len(manifest),
        "lane": LANE,
        "round_count": (REGISTERED_ROUNDS if len(cases) == len(SCENARIO_ORDER) else 0),
        "scenario_count": len(cases),
        "verified": not errors,
        "verification_scope": (
            "offline integrity and internal consistency; not authenticity"
        ),
    }


def verify_coding_agent_artifact(artifact_dir: str | Path) -> dict[str, Any]:
    """Fail closed without exposing malformed artifact values or host paths."""

    try:
        return _verify_coding_agent_artifact_impl(artifact_dir)
    except Exception as error:
        return {
            "artifact_schema_version": None,
            "errors": [f"artifact verification aborted ({type(error).__name__})"],
            "files_hashed": 0,
            "lane": LANE,
            "round_count": 0,
            "scenario_count": 0,
            "verified": False,
            "verification_scope": (
                "offline integrity and internal consistency; not authenticity"
            ),
        }
