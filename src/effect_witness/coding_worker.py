"""Isolated mini-swe-agent worker for the registered schema-v5 lane."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import stat
from pathlib import Path
from typing import Any

from .artifact import _is_link_or_reparse
from .coding_dependencies import verify_mini_swe_wheel
from .coding_effect_adapter import CodingEffectAdapter, UnresolvedEffectState
from .coding_registration import (
    INJECTED_TRAJECTORY_BYTES,
    INJECTED_TRAJECTORY_EXIT_CODE,
    MINI_SWE_AGENT_RUNTIME_FILES,
    MINI_SWE_AGENT_TRAJECTORY_FORMAT,
    MINI_SWE_AGENT_VERSION,
    MUTATION_COMMAND,
    SUBMIT_COMMAND,
    UNRESOLVED_EXIT_CODE,
)
from .models import canonical_json, strict_json_loads

_UNEXPECTED_EXIT_CODE = 31


class InjectedTrajectoryWriteFailure(OSError):
    """Registered application-level failure during the first trajectory save."""


def _regular_file_bytes(path: Path) -> bytes:
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or _is_link_or_reparse(path):
        raise RuntimeError("installed mini-swe-agent source is not a regular file")
    content = path.read_bytes()
    after = path.stat(follow_symlinks=False)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if identity_before != identity_after:
        raise RuntimeError(
            "installed mini-swe-agent source changed during verification"
        )
    return content


def _verify_upstream_runtime(package_root: Path) -> None:
    if importlib.metadata.version("mini-swe-agent") != MINI_SWE_AGENT_VERSION:
        raise RuntimeError("installed mini-swe-agent version differs from registration")
    for relative, expected in MINI_SWE_AGENT_RUNTIME_FILES.items():
        path = package_root.parent / relative
        content = _regular_file_bytes(path)
        if (
            len(content) != expected["bytes"]
            or hashlib.sha256(content).hexdigest() != expected["sha256"]
        ):
            raise RuntimeError(
                "installed mini-swe-agent runtime bytes differ from registration"
            )


def _model_output(content: str, command: str) -> dict[str, Any]:
    return {
        "content": content,
        "extra": {
            "actions": [{"command": command}],
            "cost": 0.0,
            "timestamp": 0.0,
        },
        "role": "assistant",
    }


def _trajectory_state(path: Path) -> str:
    if not path.is_file() or _is_link_or_reparse(path):
        return "ABSENT"
    try:
        value = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        content = path.read_bytes()
        if content == INJECTED_TRAJECTORY_BYTES:
            return "INVALID_REGISTERED_PREFIX"
        return "INVALID_OTHER"
    if (
        isinstance(value, dict)
        and value.get("trajectory_format") == MINI_SWE_AGENT_TRAJECTORY_FORMAT
        and isinstance(value.get("messages"), list)
        and isinstance(value.get("info"), dict)
    ):
        return "VALID_JSON"
    return "INVALID_OTHER"


def _message_projection(messages: list[dict[str, Any]]) -> dict[str, Any]:
    declared = 0
    observations: list[int] = []
    roles: list[str] = []
    for message in messages:
        role = message.get("role")
        roles.append(role if isinstance(role, str) else "INVALID")
        actions = message.get("extra", {}).get("actions", [])
        if isinstance(actions, list):
            declared += sum(
                1
                for action in actions
                if isinstance(action, dict)
                and action.get("command") == MUTATION_COMMAND
                and set(action) == {"command"}
            )
        if role == "user":
            returncode = message.get("extra", {}).get("returncode")
            if type(returncode) is int:
                observations.append(returncode)
    return {
        "declared_mutation_count": declared,
        "message_role_sequence": roles,
        "observed_mutation_returncodes": observations,
    }


def _run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if os.environ.get("MSWEA_SILENT_STARTUP") != "1":
        raise RuntimeError("mini-swe-agent startup output is not disabled")
    verify_mini_swe_wheel(args.wheel)

    import minisweagent
    from minisweagent import __version__ as mini_version
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.local import LocalEnvironment
    from minisweagent.models.test_models import DeterministicModel

    if mini_version != MINI_SWE_AGENT_VERSION:
        raise RuntimeError("imported mini-swe-agent version differs from registration")
    package_root = Path(minisweagent.__file__).resolve().parent
    _verify_upstream_runtime(package_root)

    model = DeterministicModel(
        cost_per_call=0.0,
        outputs=[
            _model_output("Apply the registered fix and test it.", MUTATION_COMMAND),
            _model_output("Submit the registered result.", SUBMIT_COMMAND),
        ],
    )
    base = LocalEnvironment(cwd=str(args.workspace), env={}, timeout=30)
    environment = CodingEffectAdapter(
        base,
        journal=args.journal,
        phase=args.phase,
        policy=args.policy,
        workspace=args.workspace,
    )

    if args.inject_save_failure:

        class RegisteredFaultAgent(DefaultAgent):
            save_calls = 0

            def save(self, path: Path | None, *extra_dicts: Any) -> dict[str, Any]:
                self.save_calls += 1
                if self.save_calls == 1:
                    if path is None:
                        raise RuntimeError(
                            "registered fault requires a trajectory path"
                        )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb") as stream:
                        stream.write(INJECTED_TRAJECTORY_BYTES)
                        stream.flush()
                        os.fsync(stream.fileno())
                    raise InjectedTrajectoryWriteFailure(
                        "registered trajectory write failure"
                    )
                return super().save(path, *extra_dicts)

        agent_class = RegisteredFaultAgent
    else:
        agent_class = DefaultAgent

    agent = agent_class(
        model,
        environment,
        system_template="You execute only the registered synthetic coding task.",
        instance_template="Apply the exact registered patch and finish.",
        step_limit=3,
        cost_limit=0.0,
        wall_time_limit_seconds=30,
        max_consecutive_format_errors=1,
        output_path=args.trajectory,
    )
    status = "completed"
    process_exit = 0
    expected_error_type = ""
    try:
        result = agent.run("registered synthetic calculator repair")
        agent_exit_status = result.get("exit_status", "")
    except InjectedTrajectoryWriteFailure:
        status = "trajectory_write_failed"
        process_exit = INJECTED_TRAJECTORY_EXIT_CODE
        expected_error_type = "InjectedTrajectoryWriteFailure"
        agent_exit_status = ""
    except UnresolvedEffectState:
        status = "unresolved"
        process_exit = UNRESOLVED_EXIT_CODE
        expected_error_type = "UnresolvedEffectState"
        last = agent.messages[-1] if agent.messages else {}
        agent_exit_status = last.get("extra", {}).get("exit_status", "")
    except Exception as error:
        status = "unexpected_error"
        process_exit = _UNEXPECTED_EXIT_CODE
        expected_error_type = type(error).__name__
        last = agent.messages[-1] if agent.messages else {}
        agent_exit_status = last.get("extra", {}).get("exit_status", "")

    projection = _message_projection(agent.messages)
    record = {
        "agent_exit_status": agent_exit_status,
        "declared_mutation_count": projection["declared_mutation_count"],
        "expected_error_type": expected_error_type,
        "message_role_sequence": projection["message_role_sequence"],
        "mini_swe_agent_version": mini_version,
        "model_query_count": agent.n_calls,
        "observed_mutation_returncodes": projection["observed_mutation_returncodes"],
        "phase": args.phase,
        "status": status,
        "trajectory_state": _trajectory_state(args.trajectory),
    }
    return record, process_exit


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=["initial", "restart"])
    parser.add_argument("--policy", required=True, choices=["blind", "reconcile"])
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--inject-save-failure", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        record, exit_code = _run(args)
    except Exception as error:
        record = {
            "agent_exit_status": "",
            "declared_mutation_count": 0,
            "expected_error_type": type(error).__name__,
            "message_role_sequence": [],
            "mini_swe_agent_version": MINI_SWE_AGENT_VERSION,
            "model_query_count": 0,
            "observed_mutation_returncodes": [],
            "phase": args.phase,
            "status": "worker_setup_failed",
            "trajectory_state": _trajectory_state(args.trajectory),
        }
        exit_code = _UNEXPECTED_EXIT_CODE
    print(canonical_json(record))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
