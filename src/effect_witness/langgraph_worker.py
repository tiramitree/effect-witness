"""Isolated schema-v4 LangGraph worker.

The public runner invokes this module in separate Python processes. Paths and
raw checkpoint state stay inside the disposable work directory; stdout carries
one normalized JSON record.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.func import entrypoint, task
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from effect_witness.artifact import _is_link_or_reparse
from effect_witness.filesystem_dependencies import verify_dependency_directory
from effect_witness.filesystem_lane import (
    _byte_tree,
    _call,
    _server_environment,
)
from effect_witness.filesystem_registration import (
    PROTOCOL_VERSION,
    SERVER_IDENTITY,
)
from effect_witness.filesystem_semantics import EDITED, registered_stimulus
from effect_witness.langgraph_registration import (
    DURABILITY,
    INJECTED_EXIT_CODE,
    LANGGRAPH_PACKAGES,
    SCENARIOS,
)
from effect_witness.langgraph_semantics import expected_tree
from effect_witness.models import canonical_json, json_exact_equal

_THREAD_ID = re.compile(
    r"^schema-v4/(write_blind|edit_blind|edit_reconcile|"
    r"edit_reconcile_tampered)/round-(0[1-9]|10)$"
)


class InjectedPostEffectFailure(RuntimeError):
    """Registered failure after MCP success and before task return."""


def _versions() -> dict[str, str]:
    registered = {
        "effect-witness": "0.3.0",
        "mcp": "1.28.1",
        **{
            package: registration["version"]
            for package, registration in LANGGRAPH_PACKAGES.items()
        },
    }
    observed = {package: importlib.metadata.version(package) for package in registered}
    if observed != registered:
        raise RuntimeError("installed worker package versions differ from registration")
    return observed


def _event(
    database: Path,
    *,
    event_type: str,
    phase: str,
    payload: dict[str, Any] | None = None,
) -> None:
    serialized = canonical_json(payload or {})
    with sqlite3.connect(database, timeout=5.0) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                phase TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO events(event_type, phase, payload_json)
            VALUES (?, ?, ?)
            """,
            (event_type, phase, serialized),
        )
        connection.commit()


async def _invoke_tool(
    *,
    dependency_dir: Path,
    node_command: str,
    scenario_root: Path,
    tool_name: str,
) -> dict[str, Any]:
    dependency = verify_dependency_directory(
        dependency_dir,
        node_command=node_command,
    )
    registered_name, _, arguments = registered_stimulus(tool_name)
    if registered_name != tool_name:
        raise RuntimeError("tool registration differs from requested scenario")
    actual_arguments = dict(arguments)
    actual_arguments["path"] = str(scenario_root / arguments["path"])
    parameters = StdioServerParameters(
        command=dependency.node_command,
        args=[str(dependency.server_entrypoint), str(scenario_root)],
        env=_server_environment(),
        cwd=str(dependency.dependency_root),
        encoding="utf-8",
        encoding_error_handler="strict",
    )
    with open(os.devnull, "w", encoding="utf-8") as errlog:  # noqa: ASYNC230
        async with stdio_client(parameters, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                initialization = await session.initialize()
                normalized = initialization.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                )
                protocol = {
                    "protocol_version": normalized.get("protocolVersion"),
                    "server_capabilities": normalized.get("capabilities"),
                    "server_identity": normalized.get("serverInfo"),
                }
                expected_protocol = {
                    "protocol_version": PROTOCOL_VERSION,
                    "server_capabilities": {"tools": {"listChanged": True}},
                    "server_identity": SERVER_IDENTITY,
                }
                if not json_exact_equal(protocol, expected_protocol):
                    raise RuntimeError(
                        "server initialization differs from registration"
                    )
                return await _call(
                    session,
                    name=tool_name,
                    arguments=actual_arguments,
                    read_result=False,
                )


def _checkpoint_summary(workflow: Any, config: dict[str, Any]) -> dict[str, Any]:
    try:
        snapshot = workflow.get_state(config)
        history_count = sum(1 for _ in workflow.get_state_history(config))
    except (RuntimeError, ValueError, sqlite3.Error) as error:
        return {
            "available": False,
            "error_type": type(error).__name__,
        }
    return {
        "available": True,
        "history_count": history_count,
        "next": sorted(snapshot.next),
    }


def _worker(args: argparse.Namespace) -> int:
    versions = _versions()
    scenario_argument = Path(os.path.abspath(os.fspath(args.scenario_root)))
    if not scenario_argument.is_dir() or _is_link_or_reparse(scenario_argument):
        raise ValueError("worker scenario root is not an ordinary directory")
    scenario_root = scenario_argument.resolve(strict=True)
    case_root = scenario_root.parent
    checkpoint = Path(os.path.abspath(os.fspath(args.checkpoint)))
    journal = Path(os.path.abspath(os.fspath(args.journal)))
    dependency_dir = args.dependency_dir.resolve(strict=True)
    registration = SCENARIOS.get(args.scenario_id)
    if registration is None:
        raise ValueError("worker scenario is not registered")
    if args.phase not in {"fault", "resume"}:
        raise ValueError("worker phase is not registered")
    if (
        args.policy != registration["policy"]
        or args.tool_name != registration["tool_name"]
    ):
        raise ValueError("worker policy or tool differs from scenario registration")
    thread_match = _THREAD_ID.fullmatch(args.thread_id)
    if thread_match is None:
        raise ValueError("worker thread identifier is not registered")
    if (
        thread_match.group(1) != args.scenario_id
        or scenario_root.name != "sandbox"
        or case_root.name != f"round-{thread_match.group(2)}"
        or case_root.parent.name != args.scenario_id
        or _is_link_or_reparse(case_root)
        or checkpoint.parent != case_root
        or checkpoint.name != "checkpoint.sqlite"
        or journal.parent != case_root
        or journal.name != "journal.sqlite"
    ):
        raise ValueError("worker paths differ from the registered case boundary")
    for database in (checkpoint, journal):
        if database.exists() and (
            not database.is_file() or _is_link_or_reparse(database)
        ):
            raise ValueError("worker database path is not an ordinary file")
    if args.phase == "fault" and (checkpoint.exists() or journal.exists()):
        raise ValueError("fault worker database paths must start absent")
    if args.phase == "resume" and (not checkpoint.is_file() or not journal.is_file()):
        raise ValueError("resume worker databases are unavailable")
    if os.environ.get("LANGGRAPH_STRICT_MSGPACK") != "true":
        raise RuntimeError("strict msgpack mode is not enabled")

    _event(
        journal,
        event_type="WORKER_STARTED",
        phase=args.phase,
        payload={"durability": DURABILITY},
    )

    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:

        @task(name="registered_filesystem_effect")
        def filesystem_effect(payload: dict[str, str]) -> dict[str, Any]:
            if payload != {
                "scenario_id": args.scenario_id,
                "tool_name": args.tool_name,
            }:
                raise RuntimeError("task payload differs from registration")
            _event(
                journal,
                event_type="TASK_STARTED",
                phase=args.phase,
                payload={"tool_name": args.tool_name},
            )
            if args.phase == "resume" and args.policy == "reconcile":
                current = _byte_tree(scenario_root)
                expected = expected_tree("document.txt", EDITED)
                if json_exact_equal(current, expected):
                    _event(
                        journal,
                        event_type="COMMITTED_CONFIRMED",
                        phase=args.phase,
                    )
                    return {
                        "decision": "COMMITTED_CONFIRMED",
                        "mutating_call_performed": False,
                    }
                _event(
                    journal,
                    event_type="UNRESOLVED",
                    phase=args.phase,
                )
                return {
                    "decision": "UNRESOLVED",
                    "mutating_call_performed": False,
                }

            _event(
                journal,
                event_type="TOOL_SENT",
                phase=args.phase,
                payload={"tool_name": args.tool_name},
            )
            observation = asyncio.run(
                _invoke_tool(
                    dependency_dir=dependency_dir,
                    node_command=args.node_command,
                    scenario_root=scenario_root,
                    tool_name=args.tool_name,
                )
            )
            _event(
                journal,
                event_type="TOOL_OBSERVED",
                phase=args.phase,
                payload=observation,
            )
            _event(
                journal,
                event_type="MCP_CONTEXT_CLOSED",
                phase=args.phase,
            )
            if args.phase == "fault":
                if (
                    observation.get("completed") is not True
                    or observation.get("is_error") is not False
                ):
                    raise RuntimeError("registered first mutating call did not succeed")
                _event(
                    journal,
                    event_type="FAULT_AFTER_EFFECT_BEFORE_TASK_RETURN",
                    phase=args.phase,
                )
                raise InjectedPostEffectFailure("registered fault window")
            _event(
                journal,
                event_type="TASK_RETURNED",
                phase=args.phase,
                payload={"is_error": observation.get("is_error")},
            )
            return {
                "decision": "TOOL_RESULT",
                "mutating_call_performed": True,
                "observation": observation,
            }

        @entrypoint(checkpointer=saver)
        def workflow(_: dict[str, int] | None) -> dict[str, Any]:
            return filesystem_effect(
                {
                    "scenario_id": args.scenario_id,
                    "tool_name": args.tool_name,
                }
            ).result()

        config = {
            "configurable": {
                "checkpoint_ns": "",
                "thread_id": args.thread_id,
            }
        }
        invocation = {"probe_schema": 4} if args.phase == "fault" else None
        try:
            value = workflow.invoke(
                invocation,
                config,
                durability=DURABILITY,
            )
        except InjectedPostEffectFailure as error:
            summary = {
                "checkpoint": _checkpoint_summary(workflow, config),
                "error_types": [type(error).__name__],
                "phase": args.phase,
                "status": "failed",
                "versions": versions,
            }
            print(canonical_json(summary), flush=True)
            return INJECTED_EXIT_CODE if args.phase == "fault" else 1

        summary = {
            "checkpoint": _checkpoint_summary(workflow, config),
            "phase": args.phase,
            "status": "completed",
            "value": value,
            "versions": versions,
        }
        print(canonical_json(summary), flush=True)
        return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--dependency-dir", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--node-command", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--scenario-root", required=True, type=Path)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--tool-name", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one registered worker phase."""

    return _worker(_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
