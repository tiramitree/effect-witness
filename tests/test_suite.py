from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from effect_witness.suite import run_suite


def test_suite_seals_expected_negative_and_unresolved_controls(tmp_path) -> None:
    output = tmp_path / "artifacts"
    work = tmp_path / "work"

    summary = run_suite(output, work_dir=work)

    assert summary["all_expectations_met"] is True
    assert summary["scenario_count"] == 10
    assert summary["contract_result_counts"] == {
        "MATCH": 3,
        "MISMATCH": 4,
        "NOT_APPLICABLE": 3,
    }
    unresolved = json.loads(
        (
            output / "results" / "stable_postcommit_exit_status_unavailable.json"
        ).read_text(encoding="utf-8")
    )
    assert unresolved["client_outcome"] == "UNRESOLVED"
    assert unresolved["witness"]["effect_count"] == 1
    assert not work.exists()

    for line in (output / "manifest.sha256").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        content = (output / Path(relative)).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest


def test_suite_rejects_invalid_source_revision_before_writing(tmp_path) -> None:
    output = tmp_path / "artifact"

    with pytest.raises(ValueError, match="source_revision"):
        run_suite(output, source_revision="not-a-commit")

    assert not output.exists()
