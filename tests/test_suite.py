from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import effect_witness.suite as suite_module
from effect_witness.mcp_client import CallObservation
from effect_witness.models import ClientOutcome, ContractResult
from effect_witness.store import SQLITE_BUSY_TIMEOUT_SECONDS
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


def test_concurrent_control_has_budget_beyond_two_busy_windows(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_call = suite_module.call_tool_sync
    call_timeouts: list[float] = []

    def call_tool(
        url: str,
        *,
        name: str,
        arguments: dict[str, object],
        timeout_seconds: float,
    ) -> CallObservation:
        if name == "misleading_idempotent_write":
            call_timeouts.append(timeout_seconds)
            if timeout_seconds <= 2 * SQLITE_BUSY_TIMEOUT_SECONDS:
                return CallObservation(
                    completed=False,
                    is_error=None,
                    exception_types=("ReadTimeout",),
                    response=None,
                )
        return original_call(
            url,
            name=name,
            arguments=arguments,
            timeout_seconds=timeout_seconds,
        )

    monkeypatch.setattr(suite_module, "call_tool_sync", call_tool)

    case = suite_module._concurrent_duplicate(
        tmp_path,
        scenario_id="idempotent_misleading_concurrent_8",
        tool_name="misleading_idempotent_write",
    )

    assert suite_module.CONCURRENT_MCP_TIMEOUT_SECONDS > (
        2 * SQLITE_BUSY_TIMEOUT_SECONDS + 5.0
    )
    assert call_timeouts == [suite_module.CONCURRENT_MCP_TIMEOUT_SECONDS] * 8
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
            "evidence_checks": {
                "response_was_confirmed": False,
                "unsafe/check/name": False,
            },
            "observations": [
                {
                    "completed": False,
                    "exception_types": ["ReadTimeout"],
                    "is_error": None,
                    "response": {
                        "unregistered_detail": "sensitive-local-message",
                    },
                }
            ],
            "scenario_id": "failed-control",
            "unregistered_detail": "sensitive-local-message",
            "witness": {"attempt_count": 1, "effect_count": 1},
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

    with pytest.raises(RuntimeError, match="artifact was not sealed") as raised:
        run_suite(output, work_dir=work)

    message = str(raised.value)
    assert "response_was_confirmed" in message
    assert "ReadTimeout" in message
    assert '"attempt_count":1' in message
    assert "unsafe/check/name" not in message
    assert "sensitive-local-message" not in message
    assert output.is_dir()
    assert list(output.iterdir()) == []
    assert not work.exists()
