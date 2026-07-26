from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from effect_witness.artifact import verify_artifact
from effect_witness.models import canonical_json, sha256_json
from effect_witness.suite import run_suite


@pytest.fixture(scope="module")
def baseline_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("artifact-semantics")
    artifact = root / "artifact"
    run_suite(artifact, work_dir=root / "work")
    return artifact


def _copy(baseline: Path, tmp_path: Path) -> Path:
    target = tmp_path / "artifact"
    shutil.copytree(baseline, target)
    return target


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


def _load_case(root: Path, scenario_id: str) -> tuple[Path, dict[str, object]]:
    path = root / "results" / f"{scenario_id}.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _write_case(path: Path, case: dict[str, object]) -> None:
    path.write_text(
        json.dumps(case, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_rejects_false_evidence_check_even_with_rewritten_manifest(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    checks = case["evidence_checks"]
    assert isinstance(checks, dict)
    checks["both_calls_succeeded"] = False
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "evidence_checks are not all true" in error for error in report["errors"]
    )


def test_rejects_self_consistent_effect_count_fabrication(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    witness = case["witness"]
    assert isinstance(witness, dict)
    witness["effect_count"] = 99
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "witness effect_count is inconsistent" in error for error in report["errors"]
    )


def test_rejects_annotation_drift_even_when_labels_are_unchanged(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    annotations = case["declared_annotations"]
    assert isinstance(annotations, dict)
    annotations["idempotentHint"] = False
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "declared annotations differ from registration" in error
        for error in report["errors"]
    )


def test_rejects_input_schema_drift(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    case["declared_input_schema"] = {"properties": {}}
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "declared input schema differs from registration" in error
        for error in report["errors"]
    )


def test_rejects_forged_registered_request_hash(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    forged = "0" * 64
    stimulus = case["stimulus"]
    journal = case["client_journal"]
    assert isinstance(stimulus, dict)
    assert isinstance(journal, dict)
    stimulus["request_argument_sha256s"] = [forged, forged]
    for event in journal["client_events"]:
        if event["event_type"] == "SENT":
            event["payload"]["arguments_sha256"] = forged
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "request argument hashes differ from registration" in error
        for error in report["errors"]
    )


def test_rejects_missing_registered_decision_event(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(
        artifact,
        "idempotent_truth_postcommit_blind_retry",
    )
    journal = case["client_journal"]
    assert isinstance(journal, dict)
    events = [
        event
        for event in journal["client_events"]
        if event["event_type"] != "BLIND_RETRY"
    ]
    for sequence, event in enumerate(events, start=1):
        event["seq"] = sequence
    journal["client_events"] = events
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "journal event state machine is inconsistent" in error
        for error in report["errors"]
    )


def test_rejects_contradictory_reconciliation_fact(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "stable_postcommit_exit_reconcile")
    observations = case["observations"]
    journal = case["client_journal"]
    assert isinstance(observations, list)
    assert isinstance(journal, dict)
    response = observations[1]["response"]
    response["structuredContent"]["effect_count"] = 0
    response["structuredContent"]["effects"] = []
    response["content"][0]["text"] = canonical_json(response["structuredContent"])
    for event in journal["client_events"]:
        if event["event_type"] == "RECONCILIATION_OBSERVED":
            event["payload"]["response_sha256"] = sha256_json(response)
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "reconciliation fact is inconsistent" in error for error in report["errors"]
    )


def test_malformed_evidence_checks_are_structurally_rejected(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    case["evidence_checks"] = []
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "evidence_checks are not all true" in error for error in report["errors"]
    )


def test_rejects_forged_concurrency_witness(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_concurrent_8")
    witness = case["concurrency_witness"]
    assert isinstance(witness, dict)
    witness["max_in_flight"] = 1
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "concurrency witness is inconsistent" in error for error in report["errors"]
    )


def test_rejects_contradictory_write_effect_id(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_misleading_sequential")
    response = case["observations"][1]["response"]
    response["structuredContent"]["effect_id"] = 1
    response["content"][0]["text"] = canonical_json(response["structuredContent"])
    journal = case["client_journal"]
    for event in journal["client_events"]:
        if event["event_type"] == "RECEIVED" and event["attempt_id"] == "a2":
            event["payload"]["response_sha256"] = sha256_json(response)
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "write response effect facts are inconsistent" in error
        for error in report["errors"]
    )


def test_rejects_contradictory_reconciliation_rows(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "stable_postcommit_exit_reconcile")
    response = case["observations"][1]["response"]
    structured = response["structuredContent"]
    structured["attempts"][0]["state"] = "RECEIVED"
    structured["effects"][0]["payload_sha256"] = "0" * 64
    response["content"][0]["text"] = canonical_json(structured)
    journal = case["client_journal"]
    for event in journal["client_events"]:
        if event["event_type"] == "RECONCILIATION_OBSERVED":
            event["payload"]["response_sha256"] = sha256_json(response)
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "reconciliation fact is inconsistent" in error for error in report["errors"]
    )


def test_deep_response_text_is_structurally_rejected(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    response = case["observations"][0]["response"]
    response["content"][0]["text"] = "[" * 10000 + "0" + "]" * 10000
    journal = case["client_journal"]
    for event in journal["client_events"]:
        if event["event_type"] == "RECEIVED" and event["attempt_id"] == "a1":
            event["payload"]["response_sha256"] = sha256_json(response)
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any("response text is not JSON" in error for error in report["errors"])


def test_rejects_partial_before_retry_witness(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(
        artifact,
        "idempotent_truth_postcommit_blind_retry",
    )
    intermediate = case["intermediate_witness"]
    assert isinstance(intermediate, dict)
    before = intermediate["before_retry"]
    assert isinstance(before, dict)
    before["attempt_state_counts"] = {"RECEIVED": 1}
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "before-retry witness is inconsistent" in error for error in report["errors"]
    )


def test_rejects_duplicate_json_object_keys(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path = artifact / "summary.json"
    text = path.read_text(encoding="utf-8")
    assert text.lstrip().startswith("{")
    path.write_text(
        text.replace("{", '{"schema_version": 2,', 1),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any("summary.json: invalid JSON" in error for error in report["errors"])


def test_rejects_non_finite_response_json(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    response = case["observations"][0]["response"]
    response["content"][0]["text"] = '{"value":NaN}'
    journal = case["client_journal"]
    for event in journal["client_events"]:
        if event["event_type"] == "RECEIVED" and event["attempt_id"] == "a1":
            event["payload"]["response_sha256"] = sha256_json(response)
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any("response text is not JSON" in error for error in report["errors"])


def test_rejects_integer_substitution_for_boolean_annotation(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    annotations = case["declared_annotations"]
    assert isinstance(annotations, dict)
    annotations["destructiveHint"] = 0
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "declared annotations differ from registration" in error
        for error in report["errors"]
    )


def test_rejects_float_substitution_for_integer_witness_count(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    witness = case["witness"]
    assert isinstance(witness, dict)
    witness["attempt_count"] = 2.0
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "witness attempt_count is inconsistent" in error for error in report["errors"]
    )


def test_rejects_boolean_substitution_in_before_retry_witness(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(
        artifact,
        "idempotent_truth_postcommit_blind_retry",
    )
    intermediate = case["intermediate_witness"]
    assert isinstance(intermediate, dict)
    before = intermediate["before_retry"]
    assert isinstance(before, dict)
    before["effect_count"] = True
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "before-retry witness is inconsistent" in error for error in report["errors"]
    )


def test_rejects_unregistered_evidence_check_keys(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    case["evidence_checks"] = {"security": True}
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "evidence_check keys differ from registration" in error
        for error in report["errors"]
    )


def test_rejects_unregistered_case_and_nested_fields(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    case["production_deployment"] = True
    case["witness"]["security"] = True
    case["client_journal"]["external_adoption"] = True
    case["observations"][0]["independent_review"] = True
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    for expected_error in (
        "case fields differ from registration",
        "witness fields differ from registration",
        "journal fields differ from registration",
        "observation fields differ from registration",
    ):
        assert any(expected_error in error for error in report["errors"])


def test_rejects_summary_claim_and_numeric_type_substitutions(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path = artifact / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["schema_version"] = 2.0
    summary["contract_result_counts"]["MATCH"] = 3.0
    summary["model_api_calls"] = 0.0
    summary["evidence_scope"] = "production deployment with external adoption"
    summary["production_deployment"] = True
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    for expected_error in (
        "summary fields differ from registration",
        "unsupported summary schema_version",
        "summary contract_result_counts is inconsistent",
        "summary model_api_calls is invalid",
        "summary evidence_scope differs from registration",
    ):
        assert expected_error in report["errors"]


def test_rejects_unregistered_junit_state_and_numeric_substitution(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path = artifact / "junit.xml"
    tree = ET.parse(path)
    suite = tree.getroot()
    suite.set("errors", "0")
    node = suite.find("testcase")
    assert node is not None
    ET.SubElement(node, "error")
    output = node.find("system-out")
    assert output is not None and output.text is not None
    payload = json.loads(output.text)
    payload["effect_count"] = float(payload["effect_count"])
    output.text = canonical_json(payload)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert "JUnit suite attributes are inconsistent" in report["errors"]
    assert any(
        "JUnit testcase children are inconsistent" in error
        for error in report["errors"]
    )
    assert any(
        "JUnit system-out is inconsistent" in error for error in report["errors"]
    )


def test_rejects_unregistered_response_and_event_payload_fields(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    response = case["observations"][0]["response"]
    response["production_deployment"] = True
    response["content"].append(dict(response["content"][0]))
    journal = case["client_journal"]
    for event in journal["client_events"]:
        if event["event_type"] == "SENT" and event["attempt_id"] == "a1":
            event["payload"]["security"] = True
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
        if event["event_type"] == "RECEIVED" and event["attempt_id"] == "a1":
            event["payload"]["response_sha256"] = sha256_json(response)
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "response fields differ from registration" in error
        for error in report["errors"]
    )
    assert any(
        "successful response lacks text content" in error for error in report["errors"]
    )
    assert any(
        "journal SENT payload is inconsistent" in error for error in report["errors"]
    )


def test_rejects_non_string_failure_exception_type(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(
        artifact,
        "stable_postcommit_exit_status_unavailable",
    )
    observation = case["observations"][0]
    observation["exception_types"] = [True]
    journal = case["client_journal"]
    for event in journal["client_events"]:
        if event["event_type"] == "UNKNOWN":
            event["payload"]["exception_types"] = [True]
            event["canonical_payload_sha256"] = sha256_json(event["payload"])
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "transport failure exception types are invalid" in error
        for error in report["errors"]
    )


def test_rejects_unregistered_explanatory_and_protocol_fields(
    baseline_artifact: Path,
    tmp_path: Path,
) -> None:
    artifact = _copy(baseline_artifact, tmp_path)
    path, case = _load_case(artifact, "idempotent_truth_sequential")
    case["contract_basis"] = "opposite claim"
    case["expectation_input"] = {"expected_max_effects": 99}
    case["protocol"]["name"] = "A2A"
    _write_case(path, case)
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert any(
        "contract_basis differs from registration" in error
        for error in report["errors"]
    )
    assert any(
        "expectation_input differs from registration" in error
        for error in report["errors"]
    )
    assert any(
        "protocol metadata differs from registration" in error
        for error in report["errors"]
    )
