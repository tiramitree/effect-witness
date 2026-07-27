from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import effect_witness.suite as suite_module
from effect_witness.mcp_client import CallObservation
from effect_witness.models import ClientOutcome, ContractResult
from effect_witness.suite import Expected, Scenario, run_suite


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


def test_precommit_clean_retry_has_response_budget_beyond_busy_window(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_call = suite_module.call_tool_sync
    write_timeouts: list[float] = []

    def call_tool(
        url: str,
        *,
        name: str,
        arguments: dict[str, object],
        timeout_seconds: float = 2.0,
    ) -> CallObservation:
        observation = original_call(
            url,
            name=name,
            arguments=arguments,
            timeout_seconds=timeout_seconds,
        )
        if name == "truthful_idempotent_write":
            write_timeouts.append(timeout_seconds)
            if len(write_timeouts) == 2 and timeout_seconds <= 5.0:
                return CallObservation(
                    completed=False,
                    is_error=None,
                    exception_types=("ReadTimeout",),
                    response=None,
                )
        return observation

    monkeypatch.setattr(suite_module, "call_tool_sync", call_tool)

    case = suite_module._precommit_reconcile_retry(tmp_path)

    assert write_timeouts == [
        suite_module.NORMAL_MCP_TIMEOUT_SECONDS,
        suite_module.NORMAL_MCP_TIMEOUT_SECONDS,
    ]
    assert case["client_outcome"] == ClientOutcome.SUCCEEDED
    assert all(value is True for value in case["evidence_checks"].values())


def test_suite_refuses_to_seal_failed_registered_scenario(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "artifact"
    work = tmp_path / "work"

    def failed_case(root: Path) -> dict[str, object]:
        assert root == work
        return {
            "client_outcome": ClientOutcome.UNKNOWN,
            "contract_result": ContractResult.NOT_APPLICABLE,
            "evidence_checks": {"response_was_confirmed": False},
            "scenario_id": "failed-control",
        }

    scenario = Scenario(
        scenario_id="failed-control",
        run=failed_case,
        expected=Expected(
            contract_result=ContractResult.NOT_APPLICABLE,
            client_outcome=ClientOutcome.SUCCEEDED,
        ),
    )
    monkeypatch.setattr(suite_module, "_scenarios", lambda: [scenario])

    with pytest.raises(RuntimeError, match="artifact was not sealed"):
        run_suite(output, work_dir=work)

    assert output.is_dir()
    assert list(output.iterdir()) == []
    assert not work.exists()
