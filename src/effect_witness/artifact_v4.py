"""Strict offline verifier for schema-v4 LangGraph replay evidence."""

from __future__ import annotations

import hashlib
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
from .filesystem_registration import (
    FILESYSTEM_PACKAGE,
    JAVASCRIPT_SDK,
    NODE_VERSION,
    PACKAGE_LOCK_SHA256,
    PROTOCOL_VERSION,
    PYTHON_MCP_VERSION,
    SERVER_DISTRIBUTION_FILES,
    SERVER_IDENTITY,
    UPSTREAM_ROOT_LICENSE,
)
from .filesystem_semantics import EDITED, FIXTURE
from .langgraph_registration import (
    BLOCKED_CLAIMS,
    DURABILITY,
    EFFECT_WITNESS_PRODUCER_VERSIONS,
    EVIDENCE_BOUNDARY,
    EVIDENCE_SCOPE,
    INJECTED_EXIT_CODE,
    LANE,
    LANGGRAPH_PACKAGES,
    MACHINE_ARCHITECTURE,
    PYTHON_CONSTRAINT_PACKAGE_COUNT,
    PYTHON_CONSTRAINTS_SHA256,
    REGISTERED_ROUNDS,
    SCENARIO_ORDER,
    SCENARIOS,
    SCHEMA_VERSION,
    WORKER_BLIND_RESUME_EVENT_TYPES,
    WORKER_FAULT_EVENT_TYPES,
    WORKER_RECONCILE_RESUME_EVENT_TYPES,
)
from .models import canonical_json, json_exact_equal, sha256_json, strict_json_loads

_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40}$")
_PYTHON_VERSION = re.compile(r"^3\.(?:11|12|13)\.\d+$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_CASE_FIELDS = {
    "all_registered_checks_met",
    "policy",
    "round_count",
    "rounds",
    "scenario_id",
    "tool_name",
}
_ROUND_FIELDS = {
    "all_checks_met",
    "checks",
    "decisions",
    "events",
    "fault_process",
    "mutating_call_observations",
    "resume_process",
    "round",
    "s0",
    "s1",
    "s2",
    "s3",
}
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
_DIAGNOSTIC_PATHS = _EXPECTED_DIRECTORIES | _EXPECTED_FILES
_TAMPERED = b"alpha\nomega\n"


def _append(errors: list[str], scenario_id: str, message: str) -> None:
    errors.append(f"{scenario_id}: {message}")


def _valid_tree(tree: Any) -> bool:
    if not isinstance(tree, dict) or set(tree) != {"entries", "tree_sha256"}:
        return False
    if (
        not isinstance(tree["tree_sha256"], str)
        or _HEX64.fullmatch(tree["tree_sha256"]) is None
        or not isinstance(tree["entries"], list)
        or sha256_json(tree["entries"]) != tree["tree_sha256"]
    ):
        return False
    paths: list[str] = []
    for entry in tree["entries"]:
        if not isinstance(entry, dict):
            return False
        if entry.get("kind") == "directory":
            if set(entry) != {"kind", "path"}:
                return False
        elif entry.get("kind") == "file":
            if set(entry) != {"bytes", "kind", "path", "sha256"}:
                return False
            if (
                type(entry["bytes"]) is not int
                or entry["bytes"] < 0
                or not isinstance(entry["sha256"], str)
                or _HEX64.fullmatch(entry["sha256"]) is None
            ):
                return False
        else:
            return False
        path = entry.get("path")
        if (
            not isinstance(path, str)
            or not path
            or path == "."
            or "\\" in path
            or ":" in path
            or PurePosixPath(path).is_absolute()
            or any(segment in {"", ".", ".."} for segment in path.split("/"))
            or any(ord(character) < 32 for character in path)
        ):
            return False
        paths.append(path)
    return paths == sorted(set(paths))


def _expected_tree(content: bytes) -> dict[str, Any]:
    entries = [
        {
            "bytes": len(content),
            "kind": "file",
            "path": "document.txt",
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    ]
    return {"entries": entries, "tree_sha256": sha256_json(entries)}


def _empty_tree() -> dict[str, Any]:
    return {"entries": [], "tree_sha256": sha256_json([])}


def _call_registered(value: Any, *, is_error: bool) -> bool:
    return (
        isinstance(value, dict)
        and set(value)
        == {
            "completed",
            "content_types",
            "exception_types",
            "is_error",
            "response_text_included",
            "response_text_redacted",
            "structured_content_present",
            "text_block_count",
        }
        and value["completed"] is True
        and value["content_types"] == ["text"]
        and value["exception_types"] == []
        and value["is_error"] is is_error
        and value["response_text_included"] is False
        and value["response_text_redacted"] is True
        and value["structured_content_present"] is (not is_error)
        and type(value["text_block_count"]) is int
        and value["text_block_count"] == 1
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


def _registered_checks(
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
    registration = SCENARIOS[scenario_id]
    is_edit = registration["tool_name"] == "edit_file"
    expected_s0 = _expected_tree(FIXTURE) if is_edit else _empty_tree()
    expected_s1 = _expected_tree(EDITED if is_edit else FIXTURE)
    if scenario_id == "write_blind":
        expected_errors = [False, False]
        expected_decisions: list[str] = []
        resume_events = WORKER_BLIND_RESUME_EVENT_TYPES
        resume_decision = "TOOL_RESULT"
    elif scenario_id == "edit_blind":
        expected_errors = [False, True]
        expected_decisions = []
        resume_events = WORKER_BLIND_RESUME_EVENT_TYPES
        resume_decision = "TOOL_RESULT"
    elif scenario_id == "edit_reconcile":
        expected_errors = [False]
        expected_decisions = ["COMMITTED_CONFIRMED"]
        resume_events = WORKER_RECONCILE_RESUME_EVENT_TYPES[scenario_id]
        resume_decision = "COMMITTED_CONFIRMED"
    else:
        expected_errors = [False]
        expected_decisions = ["UNRESOLVED"]
        resume_events = WORKER_RECONCILE_RESUME_EVENT_TYPES[scenario_id]
        resume_decision = "UNRESOLVED"
    calls = observations if isinstance(observations, list) else []
    resume_observation = (
        calls[-1] if registration["policy"] == "blind" and calls else None
    )
    expected_events = [
        *(
            {"phase": "fault", "type": event_type}
            for event_type in WORKER_FAULT_EVENT_TYPES
        ),
        *({"phase": "resume", "type": event_type} for event_type in resume_events),
    ]
    checks = {
        "decisions_registered": decisions == expected_decisions,
        "event_sequence_registered": json_exact_equal(events, expected_events),
        "fault_process_registered": _fault_process_registered(fault_process),
        "mutating_call_count_registered": len(calls) == len(expected_errors),
        "mutating_call_results_registered": (
            [call.get("is_error") for call in calls if isinstance(call, dict)]
            == expected_errors
        ),
        "mutating_call_shapes_registered": (
            len(calls) == len(expected_errors)
            and all(
                _call_registered(call, is_error=is_error)
                for call, is_error in zip(calls, expected_errors, strict=True)
            )
        ),
        "resume_process_registered": _resume_process_registered(
            resume_process,
            decision=resume_decision,
            mutating_call_performed=registration["policy"] == "blind",
            observation=resume_observation,
        ),
        "s0_registered": json_exact_equal(s0, expected_s0),
        "s1_registered": json_exact_equal(s1, expected_s1),
        "s0_differs_s1": not json_exact_equal(s0, s1),
    }
    if registration["tamper_before_resume"]:
        expected_tampered = _expected_tree(_TAMPERED)
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
                "s2_equals_s3_after_unresolved_resume": json_exact_equal(s2, s3),
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
    if type(value.get("round")) is not int or value["round"] != expected_round:
        _append(errors, label, "round index differs from registration")
    for state in ("s0", "s1", "s2", "s3"):
        if not _valid_tree(value.get(state)):
            _append(errors, label, f"{state.upper()} byte-tree shape is invalid")
    if not all(
        isinstance(value.get(state), dict) for state in ("s0", "s1", "s2", "s3")
    ):
        return value
    try:
        expected_checks = _registered_checks(
            scenario_id,
            decisions=value.get("decisions"),
            events=value.get("events"),
            fault_process=value.get("fault_process"),
            observations=value.get("mutating_call_observations"),
            resume_process=value.get("resume_process"),
            s0=value["s0"],
            s1=value["s1"],
            s2=value["s2"],
            s3=value["s3"],
        )
    except (TypeError, ValueError):
        _append(errors, label, "registered relationships could not be recomputed")
        return value
    if not json_exact_equal(value.get("checks"), expected_checks):
        _append(errors, label, "registered checks are inconsistent")
    if value.get("all_checks_met") is not all(expected_checks.values()):
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
    if value.get("policy") != registration["policy"]:
        _append(errors, scenario_id, "policy differs from registration")
    if value.get("tool_name") != registration["tool_name"]:
        _append(errors, scenario_id, "tool name differs from registration")
    if (
        type(value.get("round_count")) is not int
        or value["round_count"] != REGISTERED_ROUNDS
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


def _expected_provenance() -> dict[str, Any]:
    return {
        "javascript_sdk": JAVASCRIPT_SDK,
        "langgraph_packages": LANGGRAPH_PACKAGES,
        "lockfile_sha256": PACKAGE_LOCK_SHA256,
        "npm_package": FILESYSTEM_PACKAGE,
        "npm_package_files_in_artifact": False,
        "python_mcp_sdk_version": PYTHON_MCP_VERSION,
        "python_version_constraint_package_count": PYTHON_CONSTRAINT_PACKAGE_COUNT,
        "python_version_constraints_sha256": PYTHON_CONSTRAINTS_SHA256,
        "python_version_constraints_are_hash_lock": False,
        "raw_checkpoint_database_in_artifact": False,
        "server_distribution_files": {
            path: {"bytes": values[0], "sha256": values[1]}
            for path, values in sorted(SERVER_DISTRIBUTION_FILES.items())
        },
        "strict_msgpack_required": True,
        "upstream_root_license": UPSTREAM_ROOT_LICENSE,
    }


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
        "declared_source_revision",
        "dependencies",
        "durability",
        "evidence_boundary",
        "evidence_scope",
        "lane",
        "model_api_calls",
        "mutating_call_observation_count",
        "paid_service_calls",
        "protocol",
        "registered_rounds",
        "runtime",
        "scenario_count",
        "schema_version",
        "source_revision_verification",
        "strict_msgpack",
        "worker_process_count",
    }
    if set(summary) != expected_fields:
        errors.append("summary fields differ from schema-v4 registration")
    if (
        type(summary.get("schema_version")) is not int
        or summary["schema_version"] != SCHEMA_VERSION
    ):
        errors.append("unsupported summary schema_version")
    if summary.get("lane") != LANE:
        errors.append("summary lane differs from registration")
    if type(summary.get("scenario_count")) is not int or summary[
        "scenario_count"
    ] != len(SCENARIO_ORDER):
        errors.append("summary scenario_count differs from registration")
    if (
        type(summary.get("registered_rounds")) is not int
        or summary["registered_rounds"] != REGISTERED_ROUNDS
    ):
        errors.append("summary registered_rounds differs from registration")
    if summary.get("all_registered_checks_met") is not True:
        errors.append("summary registered checks did not all pass")
    if summary.get("blocked_claims") != list(BLOCKED_CLAIMS):
        errors.append("summary blocked_claims differ from registration")
    if not json_exact_equal(summary.get("evidence_boundary"), EVIDENCE_BOUNDARY):
        errors.append("summary evidence boundary differs from registration")
    if summary.get("evidence_scope") != EVIDENCE_SCOPE:
        errors.append("summary evidence scope differs from registration")
    if summary.get("durability") != DURABILITY:
        errors.append("summary durability differs from registration")
    if summary.get("strict_msgpack") is not True:
        errors.append("summary strict_msgpack differs from registration")
    for field in ("model_api_calls", "paid_service_calls"):
        if type(summary.get(field)) is not int or summary[field] != 0:
            errors.append(f"summary {field} is invalid")
    expected_protocol = {
        "protocol_version": PROTOCOL_VERSION,
        "server_capabilities": {"tools": {"listChanged": True}},
        "server_identity": SERVER_IDENTITY,
    }
    if not json_exact_equal(summary.get("protocol"), expected_protocol):
        errors.append("summary protocol differs from registration")
    dependencies = summary.get("dependencies")
    expected_dependency_fields = {
        "effect-witness",
        "mcp-python",
        *LANGGRAPH_PACKAGES,
    }
    if not isinstance(dependencies, dict) or set(dependencies) != set(
        expected_dependency_fields
    ):
        errors.append("summary dependencies differ from registration")
    else:
        if (
            dependencies["effect-witness"] not in EFFECT_WITNESS_PRODUCER_VERSIONS
            or dependencies["mcp-python"] != PYTHON_MCP_VERSION
            or any(
                dependencies[package] != registration["version"]
                for package, registration in LANGGRAPH_PACKAGES.items()
            )
        ):
            errors.append("summary dependency versions differ from registration")
    runtime = summary.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {
        "implementation",
        "machine_architecture",
        "node",
        "platform_system",
        "python",
    }:
        errors.append("summary runtime fields differ from registration")
    else:
        if runtime.get("implementation") != "CPython":
            errors.append("summary Python implementation differs from registration")
        if runtime.get("machine_architecture") != MACHINE_ARCHITECTURE:
            errors.append("summary machine architecture differs from registration")
        if runtime.get("node") != NODE_VERSION:
            errors.append("summary Node version differs from registration")
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
    call_count = sum(
        len(round_value.get("mutating_call_observations", []))
        for case in cases.values()
        for round_value in case.get("rounds", [])
        if isinstance(round_value, dict)
        and isinstance(round_value.get("mutating_call_observations"), list)
    )
    if (
        type(summary.get("mutating_call_observation_count")) is not int
        or summary["mutating_call_observation_count"] != call_count
    ):
        errors.append("summary mutating call count is inconsistent")
    expected_workers = len(SCENARIO_ORDER) * REGISTERED_ROUNDS * 2
    if (
        type(summary.get("worker_process_count")) is not int
        or summary["worker_process_count"] != expected_workers
    ):
        errors.append("summary worker process count is inconsistent")
    if type(summary.get("scenario_count")) is not int or summary[
        "scenario_count"
    ] != len(cases):
        errors.append("summary scenario count differs from result files")
    if not all(
        case.get("all_registered_checks_met") is True for case in cases.values()
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
            "name": "effect-witness-langgraph-replay",
            "tests": str(len(SCENARIO_ORDER) * REGISTERED_ROUNDS),
        },
    )
    for scenario_id in SCENARIO_ORDER:
        for round_index in range(1, REGISTERED_ROUNDS + 1):
            name = f"{scenario_id}/round-{round_index:02d}"
            expected_node = ET.SubElement(
                expected_suite,
                "testcase",
                {
                    "classname": "effect_witness.langgraph_replay",
                    "name": name,
                },
            )
            expected_output = ET.SubElement(expected_node, "system-out")
            expected_output.text = canonical_json(
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
    try:
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        suite = ET.fromstring(content, parser=parser)
    except ET.ParseError as error:
        errors.append(f"junit.xml is invalid ({type(error).__name__})")
        return
    expected_count = len(SCENARIO_ORDER) * REGISTERED_ROUNDS
    if suite.tag != "testsuite" or suite.attrib != {
        "failures": "0",
        "name": "effect-witness-langgraph-replay",
        "tests": str(expected_count),
    }:
        errors.append("JUnit suite differs from registration")
        return
    if suite.text is not None or suite.tail is not None:
        errors.append("JUnit suite text differs from registration")
        return
    nodes = list(suite)
    expected_names = [
        f"{scenario_id}/round-{round_index:02d}"
        for scenario_id in SCENARIO_ORDER
        for round_index in range(1, REGISTERED_ROUNDS + 1)
    ]
    if (
        len(nodes) != expected_count
        or any(node.tag != "testcase" for node in nodes)
        or [node.get("name") for node in nodes] != expected_names
    ):
        errors.append("JUnit testcase sequence is inconsistent")
        return
    for node in nodes:
        name = str(node.get("name"))
        scenario_id, round_label = name.split("/", 1)
        round_index = int(round_label.removeprefix("round-"))
        if node.attrib != {
            "classname": "effect_witness.langgraph_replay",
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
            or case["rounds"][round_index - 1].get("all_checks_met") is not True
        ):
            _append(errors, name, "JUnit testcase has no passing result round")


def _verify_langgraph_artifact_impl(artifact_dir: str | Path) -> dict[str, Any]:
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
    if not json_exact_equal(provenance, _expected_provenance()):
        errors.append("provenance.json differs from registration")
    summary = _verify_summary(
        _read_json(snapshot, "summary.json", errors),
        cases=cases,
        errors=errors,
    )
    _verify_junit(snapshot.get("junit.xml"), cases, errors)
    return {
        "artifact_schema_version": (
            summary.get("schema_version") if isinstance(summary, dict) else None
        ),
        "errors": sorted(set(errors)),
        "files_hashed": len(manifest),
        "lane": LANE,
        "round_count": REGISTERED_ROUNDS if len(cases) == len(SCENARIO_ORDER) else 0,
        "scenario_count": len(cases),
        "verified": not errors,
        "verification_scope": (
            "offline integrity and internal consistency; not authenticity"
        ),
    }


def verify_langgraph_artifact(artifact_dir: str | Path) -> dict[str, Any]:
    """Fail closed without exposing malformed artifact values or host paths."""

    try:
        return _verify_langgraph_artifact_impl(artifact_dir)
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
