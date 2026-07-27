from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import effect_witness.artifact as artifact_module
from effect_witness.artifact import verify_artifact


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


def test_verifies_fresh_suite_artifact(schema_v2_artifact: Path) -> None:
    artifact = schema_v2_artifact

    report = verify_artifact(artifact)

    assert report == {
        "artifact_schema_version": 2,
        "errors": [],
        "files_hashed": 12,
        "scenario_count": 10,
        "verified": True,
        "verification_scope": (
            "offline integrity and internal consistency; not authenticity"
        ),
    }


def test_detects_hash_tampering(schema_v2_artifact: Path) -> None:
    artifact = schema_v2_artifact
    summary = artifact / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert "SHA-256 mismatch: summary.json" in report["errors"]


def test_detects_self_consistent_summary_lie(schema_v2_artifact: Path) -> None:
    artifact = schema_v2_artifact
    summary_path = artifact / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["scenario_count"] = 999
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest(artifact)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert "summary scenario_count is inconsistent" in report["errors"]


def test_rejects_manifest_path_traversal(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "manifest.sha256").write_text(
        f"{'0' * 64}  ../outside\n",
        encoding="utf-8",
        newline="\n",
    )

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert "manifest line 1 has an unsafe path" in report["errors"]


def test_rejects_unmanifested_file(schema_v2_artifact: Path) -> None:
    artifact = schema_v2_artifact
    shutil.copyfile(artifact / "summary.json", artifact / "extra.json")

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert "file is not covered by the manifest: extra.json" in report["errors"]
    assert "unexpected artifact file: extra.json" in report["errors"]


def test_fixture_copy_is_isolated_from_template(
    schema_v2_artifact: Path,
    schema_v2_artifact_template: Path,
) -> None:
    template_summary = schema_v2_artifact_template / "summary.json"
    original = template_summary.read_bytes()

    (schema_v2_artifact / "summary.json").write_bytes(b"changed-copy")

    assert template_summary.read_bytes() == original


def test_rejects_root_reparse_point(monkeypatch, tmp_path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    monkeypatch.setattr(
        artifact_module,
        "_is_link_or_reparse",
        lambda path: path == artifact,
    )

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert report["errors"] == [
        "artifact directory is missing or is not a regular directory"
    ]


def test_unexpected_verifier_error_is_structured(monkeypatch, tmp_path) -> None:
    def fail(_artifact_dir):
        raise RuntimeError("sensitive detail")

    monkeypatch.setattr(artifact_module, "_verify_artifact_impl", fail)

    report = verify_artifact(tmp_path)

    assert report["verified"] is False
    assert report["errors"] == ["artifact verification aborted (RuntimeError)"]
    assert "sensitive detail" not in repr(report)
