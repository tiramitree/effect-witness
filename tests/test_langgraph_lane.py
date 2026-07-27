from __future__ import annotations

import sys
from pathlib import Path

import pytest

import effect_witness.langgraph_lane as lane_module


def test_worker_interruption_terminates_process_tree_and_uses_isolation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "case" / "checkpoint.sqlite"
    checkpoint.parent.mkdir()
    captured: dict[str, object] = {}
    terminated: list[object] = []

    class InterruptedProcess:
        pid = 123
        returncode = None

        def communicate(self, *, timeout: int) -> tuple[str, str]:
            captured["timeout"] = timeout
            raise KeyboardInterrupt

    process = InterruptedProcess()

    def fake_popen(command: list[str], **kwargs: object) -> InterruptedProcess:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return process

    monkeypatch.setattr(lane_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        lane_module,
        "_terminate_process_tree",
        terminated.append,
    )

    with pytest.raises(KeyboardInterrupt):
        lane_module._run_worker(
            checkpoint=checkpoint,
            dependency_dir=tmp_path / "dependency",
            journal=checkpoint.parent / "journal.sqlite",
            node_command="node",
            phase="fault",
            policy="blind",
            scenario_id="write_blind",
            scenario_root=checkpoint.parent / "sandbox",
            thread_id="schema-v4/write_blind/round-01",
            tool_name="write_file",
            versions={},
        )

    command = captured["command"]
    kwargs = captured["kwargs"]
    assert isinstance(command, list)
    assert command[:3] == [sys.executable, "-I", "-m"]
    assert isinstance(kwargs, dict)
    assert kwargs["cwd"] == checkpoint.parent
    assert kwargs["env"]["PYTHONNOUSERSITE"] == "1"
    assert terminated == [process]
