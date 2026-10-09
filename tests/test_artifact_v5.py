from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import effect_witness.artifact_v5 as verifier
import effect_witness.coding_semantics as producer_semantics
from effect_witness.artifact_v5 import verify_coding_agent_artifact
from effect_witness.coding_registration import (
    BLOCKED_CLAIMS,
    EVIDENCE_BOUNDARY,
    EVIDENCE_SCOPE,
    LANE,
    MINI_SWE_AGENT_DEVELOPMENT_STATUS,
    MINI_SWE_AGENT_LICENSE,
    MINI_SWE_AGENT_PYTHON_REQUIRES,
    MINI_SWE_AGENT_RUNTIME_FILES,
    MINI_SWE_AGENT_VERSION,
    MINI_SWE_AGENT_WHEEL,
    MINI_SWE_AGENT_WHEEL_BYTES,
    MINI_SWE_AGENT_WHEEL_SHA256,
    MINI_SWE_AGENT_WHEEL_URL,
    PYTHON_CONSTRAINT_PACKAGE_COUNT,
    PYTHON_CONSTRAINTS_SHA256,
    REGISTERED_ROUNDS,
    SCENARIO_ORDER,
    SCENARIOS,
    SCHEMA_VERSION,
)
from effect_witness.models import canonical_json, sha256_json


def test_historical_python_constraints_are_offline_only(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    provenance = verifier._expected_provenance(historical=True)
    _write_json(artifact / "provenance.json", provenance)
    _rewrite_manifest(artifact)
    assert verify_coding_agent_artifact(artifact)["verified"] is True
    provenance["python_constraints_sha256"] = "0" * 64
    _write_json(artifact / "provenance.json", provenance)
    _rewrite_manifest(artifact)
    report = verify_coding_agent_artifact(artifact)
    assert report["verified"] is False
    assert "provenance.json differs from registration" in report["errors"]


def _write_json(path: Path, value: object) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


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


def _registered_round(scenario_id: str, round_index: int) -> dict[str, object]:
    processes = producer_semantics.expected_processes(scenario_id)
    journal = producer_semantics.expected_journal(scenario_id)
    snapshots = producer_semantics.expected_snapshots(scenario_id)
    validations = producer_semantics.expected_validations(scenario_id)
    changed_paths = producer_semantics.expected_changed_paths(scenario_id)
    checks = producer_semantics.evaluate_round(
        scenario_id,
        processes=processes,
        journal=journal,
        snapshots=snapshots,
        validations=validations,
        changed_paths=changed_paths,
    )
    return {
        "all_checks_met": all(checks.values()),
        "changed_paths": changed_paths,
        "checks": checks,
        "journal": journal,
        "processes": processes,
        "round": round_index,
        "scenario_id": scenario_id,
        "snapshots": snapshots,
        "validations": validations,
    }


def _write_junit(path: Path) -> None:
    suite = ET.Element(
        "testsuite",
        {
            "failures": "0",
            "name": "effect-witness-mini-swe-agent",
            "tests": str(len(SCENARIO_ORDER) * REGISTERED_ROUNDS),
        },
    )
    for scenario_id in SCENARIO_ORDER:
        for round_index in range(1, REGISTERED_ROUNDS + 1):
            node = ET.SubElement(
                suite,
                "testcase",
                {
                    "classname": "effect_witness.mini_swe_agent",
                    "name": f"{scenario_id}/round-{round_index:02d}",
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
    path.write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))


def _registered_artifact(root: Path) -> None:
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
            "fault": registration["fault"],
            "policy": registration["policy"],
            "restart": registration["restart"],
            "round_count": REGISTERED_ROUNDS,
            "rounds": rounds,
            "scenario_id": scenario_id,
            "tamper": registration["tamper"],
        }
        cases[scenario_id] = case
        _write_json(results / f"{scenario_id}.json", case)

    provenance = {
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
        "python_constraints_sha256": PYTHON_CONSTRAINTS_SHA256,
        "raw_trajectory_in_artifact": False,
        "selected_runtime_bytes_verified": True,
    }
    _write_json(root / "provenance.json", provenance)
    round_records = [
        round_value for case in cases.values() for round_value in case["rounds"]
    ]
    summary = {
        "all_registered_checks_met": True,
        "blocked_claims": list(BLOCKED_CLAIMS),
        "command_execution_count": sum(
            row["command_executed"] is True
            for round_value in round_records
            for row in round_value["journal"]
        ),
        "declared_mutation_count": sum(
            process["declared_mutation_count"]
            for round_value in round_records
            for process in round_value["processes"]
        ),
        "declared_source_revision": "UNCOMMITTED",
        "dependencies": {
            "effect-witness": "0.4.0",
            "mini-swe-agent": MINI_SWE_AGENT_VERSION,
        },
        "dependency_constraint_package_count": PYTHON_CONSTRAINT_PACKAGE_COUNT,
        "evidence_boundary": EVIDENCE_BOUNDARY,
        "evidence_scope": EVIDENCE_SCOPE,
        "lane": LANE,
        "model_api_calls": 0,
        "paid_service_calls": 0,
        "registered_rounds": REGISTERED_ROUNDS,
        "runtime": {
            "implementation": "CPython",
            "machine_architecture": "x86_64",
            "platform_system": "Windows",
            "python": "3.12.10",
        },
        "scenario_count": len(SCENARIO_ORDER),
        "schema_version": SCHEMA_VERSION,
        "source_revision_verification": "caller_declared",
        "worker_process_count": sum(
            len(round_value["processes"]) for round_value in round_records
        ),
    }
    _write_json(root / "summary.json", summary)
    _write_junit(root / "junit.xml")
    _rewrite_manifest(root)


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_schema_v5_verifies_registered_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report == {
        "artifact_schema_version": 5,
        "errors": [],
        "files_hashed": 7,
        "lane": "mini_swe_agent_coding_reconciliation",
        "round_count": 3,
        "scenario_count": 4,
        "verified": True,
        "verification_scope": (
            "offline integrity and internal consistency; not authenticity"
        ),
    }
    assert len([path for path in artifact.rglob("*") if path.is_file()]) == 8


def test_schema_v5_rejects_forged_manifest_digest(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    manifest = artifact / "manifest.sha256"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    lines[0] = ("0" * 64) + lines[0][64:]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert any(error.startswith("SHA-256 mismatch:") for error in report["errors"])


def test_schema_v5_rejects_noncanonical_manifest_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    manifest = artifact / "manifest.sha256"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    manifest.write_bytes("\r\n".join(reversed(lines)).encode("utf-8"))

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert "manifest bytes differ from canonical registration" in report["errors"]


def test_schema_v5_rejects_manifest_covered_extra_file(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    (artifact / "unexpected.bin").write_bytes(b"not registered")
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert "artifact file inventory differs from registration" in report["errors"]
    assert "manifest closure differs from registration" in report["errors"]
    assert "unexpected.bin" not in json.dumps(report)


def test_schema_v5_rejects_extra_raw_process_field_without_leak(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "clean.json"
    result = _load_json(result_path)
    sentinel = "unsafe:private-sentinel-raw-agent-output"
    result["rounds"][0]["processes"][0]["raw_shell_output"] = sentinel
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)
    serialized = json.dumps(report, sort_keys=True)

    assert report["verified"] is False
    assert (
        "clean/round-01: process record fields differ from registration"
        in report["errors"]
    )
    assert sentinel not in serialized


def test_schema_v5_rejects_integer_as_boolean(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "clean.json"
    result = _load_json(result_path)
    result["rounds"][0]["processes"][0]["stderr_empty"] = 1
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert "clean/round-01: registered checks are inconsistent" in report["errors"]


def test_schema_v5_rejects_boolean_as_summary_count(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    summary = _load_json(summary_path)
    summary["worker_process_count"] = True
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert "summary worker process count is inconsistent" in report["errors"]


def test_schema_v5_rejects_unreleased_producer_version(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    summary = _load_json(summary_path)
    summary["dependencies"]["effect-witness"] = "0.3.3"
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert "summary dependencies differ from registration" in report["errors"]


def test_schema_v5_redacts_malformed_schema_value(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    summary = _load_json(summary_path)
    sentinel = "unsafe:private-sentinel-schema-value"
    summary["schema_version"] = sentinel
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)
    serialized = json.dumps(report, sort_keys=True)

    assert report["verified"] is False
    assert report["artifact_schema_version"] is None
    assert sentinel not in serialized


def test_schema_v5_rejects_fake_journal_execution(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "save_fault_reconcile.json"
    result = _load_json(result_path)
    restart = result["rounds"][0]["journal"][1]
    restart["command_executed"] = True
    restart["decision"] = "EXECUTED"
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert (
        "save_fault_reconcile/round-01: registered checks are inconsistent"
        in report["errors"]
    )
    assert "summary command execution count is inconsistent" in report["errors"]


def test_schema_v5_rejects_registered_shape_snapshot_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "clean.json"
    result = _load_json(result_path)
    result["rounds"][0]["snapshots"]["s3"] = producer_semantics.expected_snapshots(
        "clean"
    )["s0"]
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert "clean/round-01: registered checks are inconsistent" in report["errors"]


def test_schema_v5_rejects_unsafe_snapshot_path_without_leak(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "clean.json"
    result = _load_json(result_path)
    sentinel = "unsafe:private-sentinel-snapshot-path"
    tree = result["rounds"][0]["snapshots"]["s1"]
    tree["entries"][0]["path"] = sentinel
    tree["tree_sha256"] = sha256_json(tree["entries"])
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)
    serialized = json.dumps(report, sort_keys=True)

    assert report["verified"] is False
    assert "clean/round-01: S1 snapshot shape is invalid" in report["errors"]
    assert sentinel not in serialized


def test_schema_v5_rejects_duplicate_json_key(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    content = summary_path.read_text(encoding="utf-8")
    summary_path.write_text(
        content.replace(
            '"schema_version":5',
            '"schema_version":5,"schema_version":5',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert "summary.json: invalid JSON (ValueError)" in report["errors"]


def test_schema_v5_rejects_noncanonical_junit(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    junit = artifact / "junit.xml"
    junit.write_bytes(junit.read_bytes().replace(b"<testcase", b"<!--x--><testcase", 1))
    _rewrite_manifest(artifact)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert "JUnit bytes differ from canonical registration" in report["errors"]


def test_schema_v5_does_not_parse_noncanonical_junit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    junit = artifact / "junit.xml"
    junit.write_bytes(junit.read_bytes() + b" ")
    _rewrite_manifest(artifact)

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(verifier.ET, "fromstring", fail)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is False
    assert report["errors"] == ["JUnit bytes differ from canonical registration"]


def test_schema_v5_uses_one_bounded_artifact_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    calls = 0
    original = verifier._artifact_snapshot

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(verifier, "_artifact_snapshot", counted)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is True
    assert calls == 1


def test_schema_v5_verifier_does_not_use_producer_evaluator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(producer_semantics, "evaluate_round", fail)

    report = verify_coding_agent_artifact(artifact)

    assert report["verified"] is True
    assert report["errors"] == []
