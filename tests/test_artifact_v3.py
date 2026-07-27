from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pytest

import effect_witness.artifact_v3 as artifact_v3_module
from effect_witness.artifact import verify_artifact
from effect_witness.artifact_v3 import (
    _expected_provenance,
    verify_filesystem_artifact,
)
from effect_witness.filesystem_registration import (
    BLOCKED_CLAIMS,
    EVIDENCE_BOUNDARY,
    PROTOCOL_VERSION,
    SCENARIO_ORDER,
    SERVER_IDENTITY,
    TOOL_REGISTRATION,
)
from effect_witness.filesystem_semantics import (
    EDITED,
    FIXTURE,
    _expected_file,
    _tree,
    evaluate_scenario,
    registered_stimulus,
)
from effect_witness.models import canonical_json, sha256_json


def _call(*, error: bool, read_result: bool) -> dict[str, object]:
    value: dict[str, object] = {
        "completed": True,
        "content_types": ["text"],
        "exception_types": [],
        "is_error": error,
        "response_text_included": False,
        "structured_content_present": not error,
        "text_block_count": 1,
    }
    if read_result:
        value["text_bytes"] = len(FIXTURE)
        value["text_sha256"] = hashlib.sha256(FIXTURE).hexdigest()
    else:
        value["response_text_redacted"] = True
    return value


def _states(
    scenario_id: str,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    if scenario_id == "read_text_file":
        tree = _tree([_expected_file("fixture.txt", FIXTURE)])
        return (
            _call(error=False, read_result=True),
            _call(error=False, read_result=True),
            tree,
            tree,
            tree,
        )
    if scenario_id == "create_directory":
        return (
            _call(error=False, read_result=False),
            _call(error=False, read_result=False),
            _tree([]),
            _tree([{"kind": "directory", "path": "new-dir"}]),
            _tree([{"kind": "directory", "path": "new-dir"}]),
        )
    if scenario_id == "create_directory_nested_claim":
        tree = _tree([])
        return (
            _call(error=True, read_result=False),
            _call(error=True, read_result=False),
            tree,
            tree,
            tree,
        )
    if scenario_id == "write_file":
        effect = _tree([_expected_file("document.txt", FIXTURE)])
        return (
            _call(error=False, read_result=False),
            _call(error=False, read_result=False),
            _tree([]),
            effect,
            effect,
        )
    if scenario_id == "edit_file":
        effect = _tree([_expected_file("document.txt", EDITED)])
        return (
            _call(error=False, read_result=False),
            _call(error=True, read_result=False),
            _tree([_expected_file("document.txt", FIXTURE)]),
            effect,
            effect,
        )
    raise AssertionError("unregistered scenario")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _registered_artifact(root: Path) -> None:
    results = root / "results"
    results.mkdir(parents=True)
    cases = []
    for scenario_id in SCENARIO_ORDER:
        first, second, s0, s1, s2 = _states(scenario_id)
        checks, outcome = evaluate_scenario(
            scenario_id,
            first=first,
            second=second,
            s0=s0,
            s1=s1,
            s2=s2,
            platform_system="Windows",
        )
        tool_name, stimulus, _ = registered_stimulus(scenario_id)
        case = {
            "checks": checks,
            "expectation_met": all(checks.values()),
            "first_call": first,
            "observation_outcome": outcome,
            "s0": s0,
            "s0_equals_s1": s0 == s1,
            "s1": s1,
            "s1_equals_s2": s1 == s2,
            "s2": s2,
            "scenario_id": scenario_id,
            "second_call": second,
            "stimulus": stimulus,
            "stimulus_sha256": sha256_json(stimulus),
            "tool_name": tool_name,
        }
        cases.append(case)
        _write_json(results / f"{scenario_id}.json", case)
    tools = [
        {
            "description_included": False,
            "descriptor_without_description_included": False,
            "name": name,
            **TOOL_REGISTRATION[name],
        }
        for name in sorted(TOOL_REGISTRATION)
    ]
    _write_json(root / "tools.json", tools)
    _write_json(root / "provenance.json", _expected_provenance())
    counts = Counter(case["observation_outcome"] for case in cases)
    summary = {
        "all_registered_checks_met": True,
        "blocked_claims": list(BLOCKED_CLAIMS),
        "dependencies": {
            "effect-witness": "0.2.0",
            "mcp-python": "1.28.1",
        },
        "evidence_boundary": EVIDENCE_BOUNDARY,
        "evidence_scope": (
            "exact official filesystem server over stdio with controlled "
            "relative byte-tree observations"
        ),
        "lane": "real_mcp_filesystem_stdio",
        "model_api_calls": 0,
        "observation_outcome_counts": dict(sorted(counts.items())),
        "paid_service_calls": 0,
        "protocol": {
            "protocol_version": PROTOCOL_VERSION,
            "server_capabilities": {"tools": {"listChanged": True}},
            "server_identity": SERVER_IDENTITY,
        },
        "runtime": {
            "implementation": "CPython",
            "node": "v24.18.0",
            "platform_system": "Windows",
            "python": "3.12.10",
        },
        "scenario_count": len(cases),
        "schema_version": 3,
        "source_revision": "UNCOMMITTED",
    }
    _write_json(root / "summary.json", summary)
    suite = ET.Element(
        "testsuite",
        {
            "failures": "0",
            "name": "effect-witness-real-filesystem",
            "tests": str(len(cases)),
        },
    )
    for case in cases:
        node = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "effect_witness.real_filesystem",
                "name": case["scenario_id"],
            },
        )
        output = ET.SubElement(node, "system-out")
        output.text = canonical_json(
            {
                "failed_checks": [],
                "observation_outcome": case["observation_outcome"],
                "scenario_id": case["scenario_id"],
            }
        )
    ET.ElementTree(suite).write(
        root / "junit.xml",
        encoding="utf-8",
        xml_declaration=True,
    )
    rows = []
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(root).as_posix()
        rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n")
    (root / "manifest.sha256").write_text(
        "".join(rows),
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


def test_schema_v3_verifies_registered_artifact(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)

    report = verify_filesystem_artifact(artifact)

    assert report == {
        "artifact_schema_version": 3,
        "errors": [],
        "files_hashed": 9,
        "lane": "real_mcp_filesystem_stdio",
        "scenario_count": 5,
        "verified": True,
        "verification_scope": (
            "offline integrity and internal consistency; not authenticity"
        ),
    }


def test_schema_v3_rejects_self_consistent_unregistered_claim(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "create_directory_nested_claim.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["observation_outcome"] = "BUG"
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert (
        "create_directory_nested_claim: observation outcome is inconsistent"
        in report["errors"]
    )


def test_schema_v3_rejects_extra_manifest_covered_file(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    _write_json(artifact / "extra.json", {"looks": "valid"})
    _rewrite_manifest(artifact)

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert "unexpected artifact file: extra.json" in report["errors"]


def test_schema_v3_rejects_hash_drift(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary = artifact / "summary.json"
    summary.write_bytes(summary.read_bytes() + b" ")

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert "SHA-256 mismatch: summary.json" in report["errors"]


def test_schema_v3_rejects_junit_drift_with_rewritten_manifest(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    junit = artifact / "junit.xml"
    content = junit.read_text(encoding="utf-8")
    junit.write_text(
        content.replace(
            'name="effect-witness-real-filesystem"',
            'name="unregistered-suite"',
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert "JUnit suite differs from registration" in report["errors"]


def test_schema_v3_rejects_provenance_pin_drift(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    provenance_path = artifact / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["npm_package"]["version"] = "unregistered"
    _write_json(provenance_path, provenance)
    _rewrite_manifest(artifact)

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert "provenance.json differs from registration" in report["errors"]


@pytest.mark.parametrize(
    "unsafe_path",
    ("C" + ":/private", "../private", "parent/../../private", "parent//private"),
)
def test_schema_v3_rejects_unsafe_tree_path(tmp_path, unsafe_path: str) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    result_path = artifact / "results" / "write_file.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for state in ("s1", "s2"):
        result[state]["entries"][0]["path"] = unsafe_path
        result[state]["tree_sha256"] = sha256_json(result[state]["entries"])
    _write_json(result_path, result)
    _rewrite_manifest(artifact)

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert "write_file: byte-tree shape is invalid" in report["errors"]


def test_schema_v3_rejects_evidence_boundary_flip(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["evidence_boundary"]["absolute_paths_included"] = True
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert "summary evidence boundary differs from registration" in report["errors"]


def test_schema_v3_rejects_invalid_source_revision(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    _registered_artifact(artifact)
    summary_path = artifact / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["source_revision"] = "not-a-commit"
    _write_json(summary_path, summary)
    _rewrite_manifest(artifact)

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert "summary source_revision is invalid" in report["errors"]


def test_schema_v3_rejects_root_reparse_point(monkeypatch, tmp_path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    monkeypatch.setattr(
        artifact_v3_module,
        "_is_link_or_reparse",
        lambda path: path == artifact,
    )

    report = verify_filesystem_artifact(artifact)

    assert report["verified"] is False
    assert report["errors"] == [
        "artifact directory is missing or is not a regular directory"
    ]


def test_v01_reference_remains_schema_v2_compatible() -> None:
    reference = Path(__file__).resolve().parents[1] / "evidence" / "reference-v0.1.0"

    report = verify_artifact(reference)

    assert report["verified"] is True
    assert report["artifact_schema_version"] == 2
    assert report["scenario_count"] == 10
