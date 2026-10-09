from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import effect_witness.langgraph_semantics as producer_semantics
from effect_witness.artifact_v4 import (
    _expected_provenance,
    verify_langgraph_artifact,
)
from effect_witness.filesystem_registration import (
    PROTOCOL_VERSION,
    SERVER_IDENTITY,
)
from effect_witness.filesystem_semantics import EDITED, FIXTURE
from effect_witness.langgraph_registration import (
    BLOCKED_CLAIMS,
    DURABILITY,
    EVIDENCE_BOUNDARY,
    EVIDENCE_SCOPE,
    LANE,
    LANGGRAPH_PACKAGES,
    REGISTERED_ROUNDS,
    SCENARIO_ORDER,
    SCENARIOS,
    SCHEMA_VERSION,
    WORKER_BLIND_RESUME_EVENT_TYPES,
    WORKER_FAULT_EVENT_TYPES,
    WORKER_RECONCILE_RESUME_EVENT_TYPES,
)
from effect_witness.langgraph_semantics import (
    TAMPERED,
    empty_tree,
    evaluate_round,
    expected_tree,
)
from effect_witness.models import canonical_json, sha256_json


def _call(*, is_error: bool) -> dict[str, object]:
    return {
        "completed": True,
        "content_types": ["text"],
        "exception_types": [],
        "is_error": is_error,
        "response_text_included": False,
        "response_text_redacted": True,
        "structured_content_present": not is_error,
        "text_block_count": 1,
    }


def _fault_process() -> dict[str, object]:
    return {
        "checkpoint": {
            "available": True,
            "history_count": 1,
            "next": ["workflow"],
        },
        "error_types": ["InjectedPostEffectFailure"],
        "exit_code": 17,
        "status": "failed",
        "stderr_empty": True,
        "stdout_record_count": 1,
    }


def _resume_process(
    *,
    decision: str,
    mutating_call_performed: bool,
    observation: dict[str, object] | None,
) -> dict[str, object]:
    workflow_result: dict[str, object] = {
        "decision": decision,
        "mutating_call_performed": mutating_call_performed,
    }
    if observation is not None:
        workflow_result["observation"] = observation
    return {
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
    }


def _registered_round(scenario_id: str, round_index: int) -> dict[str, object]:
    registration = SCENARIOS[scenario_id]
    if registration["tool_name"] == "edit_file":
        s0 = expected_tree("document.txt", FIXTURE)
        s1 = expected_tree("document.txt", EDITED)
    else:
        s0 = empty_tree()
        s1 = expected_tree("document.txt", FIXTURE)
    if scenario_id == "write_blind":
        observations = [_call(is_error=False), _call(is_error=False)]
        decisions: list[str] = []
        resume_events = WORKER_BLIND_RESUME_EVENT_TYPES
        resume = _resume_process(
            decision="TOOL_RESULT",
            mutating_call_performed=True,
            observation=observations[-1],
        )
        s2 = s1
    elif scenario_id == "edit_blind":
        observations = [_call(is_error=False), _call(is_error=True)]
        decisions = []
        resume_events = WORKER_BLIND_RESUME_EVENT_TYPES
        resume = _resume_process(
            decision="TOOL_RESULT",
            mutating_call_performed=True,
            observation=observations[-1],
        )
        s2 = s1
    elif scenario_id == "edit_reconcile":
        observations = [_call(is_error=False)]
        decisions = ["COMMITTED_CONFIRMED"]
        resume_events = WORKER_RECONCILE_RESUME_EVENT_TYPES[scenario_id]
        resume = _resume_process(
            decision="COMMITTED_CONFIRMED",
            mutating_call_performed=False,
            observation=None,
        )
        s2 = s1
    else:
        observations = [_call(is_error=False)]
        decisions = ["UNRESOLVED"]
        resume_events = WORKER_RECONCILE_RESUME_EVENT_TYPES[scenario_id]
        resume = _resume_process(
            decision="UNRESOLVED",
            mutating_call_performed=False,
            observation=None,
        )
        s2 = expected_tree("document.txt", TAMPERED)
    s3 = s2
    events = [
        *(
            {"phase": "fault", "type": event_type}
            for event_type in WORKER_FAULT_EVENT_TYPES
        ),
        *({"phase": "resume", "type": event_type} for event_type in resume_events),
    ]
    fault = _fault_process()
    checks = evaluate_round(
        scenario_id,
        decisions=decisions,
        events=events,
        fault_process=fault,
        observations=observations,
        resume_process=resume,
        s0=s0,
        s1=s1,
        s2=s2,
        s3=s3,
    )
    return {
        "all_checks_met": all(checks.values()),
        "checks": checks,
        "decisions": decisions,
        "events": events,
        "fault_process": fault,
        "mutating_call_observations": observations,
        "resume_process": resume,
        "round": round_index,
        "s0": s0,
        "s1": s1,
        "s2": s2,
        "s3": s3,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _rewrite_manifest(root: Path) -> None:
    rows = []
    for path in sorted(
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file() and candidate.name != "manifest.sha256"
    ):
        relative = path.relative_to(root).as_posix()
        rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n")
    (root / "manifest.sha256").write_text(
        "".join(rows),
        encoding="utf-8",
        newline="\n",
    )


def _registered_artifact(
    root: Path,
    *,
    effect_witness_version: str = "0.4.0",
) -> None:
    results = root / "results"
    results.mkdir(parents=True)
    cases: dict[str, dict[str, object]] = {}
    for scenario_id in SCENARIO_ORDER:
        registration = SCENARIOS[scenario_id]
        rounds = [
            _registered_round(scenario_id, round_index)
            for round_index in range(1, REGISTERED_ROUNDS + 1)
        ]
        case = {
            "all_registered_checks_met": True,
            "policy": registration["policy"],
            "round_count": REGISTERED_ROUNDS,
            "rounds": rounds,
            "scenario_id": scenario_id,
            "tool_name": registration["tool_name"],
        }
        cases[scenario_id] = case
        _write_json(results / f"{scenario_id}.json", case)
    _write_json(root / "provenance.json", _expected_provenance())
    total_calls = sum(
        len(round_value["mutating_call_observations"])
        for case in cases.values()
        for round_value in case["rounds"]
    )
    summary = {
        "all_registered_checks_met": True,
        "blocked_claims": list(BLOCKED_CLAIMS),
        "declared_source_revision": "UNCOMMITTED",
        "dependencies": {
            "effect-witness": effect_witness_version,
            "mcp-python": "1.28.1",
            **{
                package: registration["version"]
                for package, registration in sorted(LANGGRAPH_PACKAGES.items())
            },
        },
        "durability": DURABILITY,
        "evidence_boundary": EVIDENCE_BOUNDARY,
        "evidence_scope": EVIDENCE_SCOPE,
        "lane": LANE,
        "model_api_calls": 0,
        "mutating_call_observation_count": total_calls,
        "paid_service_calls": 0,
        "protocol": {
            "protocol_version": PROTOCOL_VERSION,
            "server_capabilities": {"tools": {"listChanged": True}},
            "server_identity": SERVER_IDENTITY,
        },
        "registered_rounds": REGISTERED_ROUNDS,
        "runtime": {
            "implementation": "CPython",
            "machine_architecture": "x86_64",
            "node": "v24.18.0",
            "platform_system": "Windows",
            "python": "3.12.10",
        },
        "scenario_count": len(SCENARIO_ORDER),
        "schema_version": SCHEMA_VERSION,
        "source_revision_verification": "caller_declared",
        "strict_msgpack": True,
        "worker_process_count": len(SCENARIO_ORDER) * REGISTERED_ROUNDS * 2,
    }
    _write_json(root / "summary.json", summary)
    suite = ET.Element(
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
            node = ET.SubElement(
                suite,
                "testcase",
                {
                    "classname": "effect_witness.langgraph_replay",
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
    (root / "junit.xml").write_bytes(
        ET.tostring(
            suite,
            encoding="utf-8",
            xml_declaration=True,
        )
    )
    _rewrite_manifest(root)


def test_schema_v4_verifies_registered_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report == {
        "artifact_schema_version": 4,
        "errors": [],
        "files_hashed": 7,
        "lane": "langgraph_mcp_filesystem_replay",
        "round_count": 10,
        "scenario_count": 4,
        "verified": True,
        "verification_scope": (
            "offline integrity and internal consistency; not authenticity"
        ),
    }


def test_schema_v4_rejects_unregistered_producer_version(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact, effect_witness_version="0.3.4")

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "summary dependency versions differ from registration" in report["errors"]


@pytest.mark.parametrize(
    "producer_version",
    ("0.3.0", "0.3.1", "0.3.2", "0.3.3"),
)
def test_schema_v4_accepts_legacy_registered_producer_version(
    tmp_path: Path,
    producer_version: str,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact, effect_witness_version=producer_version)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is True
    assert report["errors"] == []


def test_schema_v4_rejects_extra_manifest_covered_file(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    _write_json(artifact / "checkpoint.sqlite", {"looks": "normalized"})
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "artifact file inventory differs from registration" in report["errors"]


def test_schema_v4_redacts_unregistered_filename_from_report(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    sentinel = "sensitive-sentinel.txt"
    (artifact / sentinel).write_text("unregistered", encoding="utf-8")
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)
    serialized = json.dumps(report, sort_keys=True)

    assert report["verified"] is False
    assert sentinel not in serialized
    assert "artifact file inventory differs from registration" in report["errors"]


def test_schema_v4_rejects_extra_empty_directory(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    (artifact / "unexpected-empty").mkdir()

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "artifact directory inventory differs from registration" in report["errors"]


def test_schema_v4_rejects_hash_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary = artifact / "summary.json"
    summary.write_bytes(summary.read_bytes() + b" ")

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "SHA-256 mismatch: summary.json" in report["errors"]


def test_schema_v4_rejects_self_consistent_state_forgery(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "write_blind.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    forged_entries = [
        {
            "bytes": 1,
            "kind": "file",
            "path": "document.txt",
            "sha256": hashlib.sha256(b"x").hexdigest(),
        }
    ]
    result["rounds"][0]["s3"] = {
        "entries": forged_entries,
        "tree_sha256": sha256_json(forged_entries),
    }
    result["rounds"][0]["checks"]["s2_equals_s3_after_resume"] = True
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert (
        "write_blind/round-01: registered checks are inconsistent" in report["errors"]
    )


def test_schema_v4_rejects_missing_round(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "edit_blind.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["rounds"].pop()
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "edit_blind: round list differs from registration" in report["errors"]


def test_schema_v4_rejects_boundary_flip(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["evidence_boundary"]["checkpoint_database_included"] = True
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "summary evidence boundary differs from registration" in report["errors"]


def test_schema_v4_rejects_provenance_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    provenance_path = artifact / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["langgraph_packages"]["langgraph"]["version"] = "unregistered"
    _write_json(provenance_path, provenance)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "provenance.json differs from registration" in report["errors"]


def test_schema_v4_rejects_junit_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    junit = artifact / "junit.xml"
    junit.write_text(
        junit.read_text(encoding="utf-8").replace(
            'tests="40"',
            'tests="39"',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "JUnit suite differs from registration" in report["errors"]


def test_schema_v4_rejects_junit_crlf_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    junit = artifact / "junit.xml"
    junit.write_bytes(junit.read_bytes().replace(b"?>\n", b"?>\r\n", 1))
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "JUnit bytes differ from canonical registration" in report["errors"]


def test_schema_v4_rejects_junit_comment(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    junit = artifact / "junit.xml"
    content = junit.read_text(encoding="utf-8")
    junit.write_text(
        content.replace(
            "<testcase",
            "<!--unregistered--><testcase",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "JUnit bytes differ from canonical registration" in report["errors"]


def test_schema_v4_rejects_junit_unregistered_text(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    junit = artifact / "junit.xml"
    content = junit.read_text(encoding="utf-8")
    junit.write_text(
        content.replace(
            'tests="40">',
            'tests="40">unregistered',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "JUnit bytes differ from canonical registration" in report["errors"]
    assert "JUnit suite text differs from registration" in report["errors"]


@pytest.mark.parametrize(
    "unsafe_path",
    ("C" + ":/private", "../private", "parent/../../private", "parent\\private"),
)
def test_schema_v4_rejects_unsafe_tree_path(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "edit_reconcile.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for state in ("s1", "s2", "s3"):
        result["rounds"][0][state]["entries"][0]["path"] = unsafe_path
        result["rounds"][0][state]["tree_sha256"] = sha256_json(
            result["rounds"][0][state]["entries"]
        )
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "edit_reconcile/round-01: S1 byte-tree shape is invalid" in report["errors"]


def test_schema_v4_rejects_integer_as_boolean(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "write_blind.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["rounds"][0]["mutating_call_observations"][0]["completed"] = 1
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert (
        "write_blind/round-01: registered checks are inconsistent" in report["errors"]
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("round", True),
        ("fault_available", 1),
        ("fault_history_count", True),
        ("fault_stderr_empty", 1),
        ("fault_stdout_record_count", True),
        ("resume_history_count", 2.0),
    ),
)
def test_schema_v4_rejects_numeric_boolean_coercion(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "write_blind.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    round_value = result["rounds"][0]
    if field == "round":
        round_value["round"] = replacement
    elif field == "fault_available":
        round_value["fault_process"]["checkpoint"]["available"] = replacement
    elif field == "fault_history_count":
        round_value["fault_process"]["checkpoint"]["history_count"] = replacement
    elif field == "fault_stderr_empty":
        round_value["fault_process"]["stderr_empty"] = replacement
    elif field == "fault_stdout_record_count":
        round_value["fault_process"]["stdout_record_count"] = replacement
    else:
        round_value["resume_process"]["checkpoint"]["history_count"] = replacement
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("schema_version", 4.0),
        ("scenario_count", 4.0),
        ("registered_rounds", True),
        ("mutating_call_observation_count", 60.0),
        ("worker_process_count", 80.0),
    ),
)
def test_schema_v4_rejects_summary_numeric_coercion(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary[field] = replacement
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("implementation", "unregistered"),
        ("machine_architecture", "unregistered"),
        ("python", "unregistered"),
    ),
)
def test_schema_v4_rejects_unregistered_runtime_string(
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["runtime"][field] = replacement
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False


def test_schema_v4_rejects_duplicate_json_key(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    content = summary_path.read_text(encoding="utf-8")
    summary_path.write_text(
        content.replace(
            '"schema_version": 4,',
            '"schema_version": 4, "schema_version": 4,',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is False
    assert "summary.json: invalid JSON (ValueError)" in report["errors"]


def test_schema_v4_verifier_does_not_use_producer_evaluator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(producer_semantics, "evaluate_round", fail)

    report = verify_langgraph_artifact(artifact)

    assert report["verified"] is True
    assert report["errors"] == []


def test_historical_dependency_binding_remains_exact(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    provenance_path = artifact / "provenance.json"
    historical = _expected_provenance(historical=True)
    summary_path = artifact / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["dependencies"]["langgraph-checkpoint-sqlite"] = "3.1.0"
    _write_json(summary_path, summary)
    _write_json(provenance_path, historical)
    _rewrite_manifest(artifact)
    assert verify_langgraph_artifact(artifact)["verified"] is True

    historical["javascript_sdk"] = _expected_provenance()["javascript_sdk"]
    _write_json(provenance_path, historical)
    _rewrite_manifest(artifact)
    report = verify_langgraph_artifact(artifact)
    assert report["verified"] is False
    assert "provenance.json differs from registration" in report["errors"]


def test_historical_python_summary_must_match_provenance(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    _write_json(
        artifact / "provenance.json",
        _expected_provenance(historical_python=True),
    )
    _rewrite_manifest(artifact)
    report = verify_langgraph_artifact(artifact)
    assert report["verified"] is False
    assert "summary dependency versions differ from registration" in report["errors"]
    summary_path = artifact / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["dependencies"]["langgraph-checkpoint-sqlite"] = "3.1.0"
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)
    assert verify_langgraph_artifact(artifact)["verified"] is True
