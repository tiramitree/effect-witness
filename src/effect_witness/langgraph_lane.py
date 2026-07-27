"""Schema-v4 runner for LangGraph replay across exact real MCP effects."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import signal
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .artifact import _is_link_or_reparse
from .filesystem_dependencies import verify_dependency_directory
from .filesystem_lane import _byte_tree, _file_bytes, _safe_relative
from .filesystem_paths import (
    create_owned_directory,
    create_staging_directory,
    ensure_disjoint_paths,
    publish_staging_directory,
    remove_owned_directories,
    remove_owned_directory,
)
from .filesystem_registration import (
    FILESYSTEM_PACKAGE,
    JAVASCRIPT_SDK,
    PACKAGE_LOCK_SHA256,
    PROTOCOL_VERSION,
    PYTHON_MCP_VERSION,
    SERVER_DISTRIBUTION_FILES,
    SERVER_IDENTITY,
    UPSTREAM_ROOT_LICENSE,
)
from .filesystem_semantics import FIXTURE
from .langgraph_constraints import verify_python_constraints
from .langgraph_registration import (
    BLOCKED_CLAIMS,
    DURABILITY,
    EFFECT_WITNESS_PRODUCER_VERSIONS,
    EVIDENCE_BOUNDARY,
    EVIDENCE_SCOPE,
    LANE,
    LANGGRAPH_PACKAGES,
    MACHINE_ARCHITECTURE,
    PYTHON_CONSTRAINT_PACKAGE_COUNT,
    PYTHON_CONSTRAINTS_SHA256,
    REGISTERED_ROUNDS,
    SCENARIO_ORDER,
    SCENARIOS,
    SCHEMA_VERSION,
)
from .langgraph_semantics import TAMPERED, evaluate_round
from .models import canonical_json, json_exact_equal, strict_json_loads

_WORKER_TIMEOUT_SECONDS = 60
_MAX_WORKER_OUTPUT_BYTES = 64 * 1024


def _versions() -> dict[str, str]:
    registered = {
        "effect-witness": EFFECT_WITNESS_PRODUCER_VERSIONS[-1],
        "mcp": PYTHON_MCP_VERSION,
        **{
            package: registration["version"]
            for package, registration in LANGGRAPH_PACKAGES.items()
        },
    }
    observed = {package: importlib.metadata.version(package) for package in registered}
    if observed != registered:
        raise RuntimeError("installed replay package versions differ from registration")
    return observed


def _worker_environment() -> dict[str, str]:
    allowed = (
        "COMSPEC",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "WINDIR",
    )
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    if os.name != "nt":
        environment["LANG"] = "C.UTF-8"
        environment["LC_ALL"] = "C.UTF-8"
    environment.update(
        {
            "LANGCHAIN_TRACING_V2": "false",
            "LANGGRAPH_STRICT_MSGPACK": "true",
            "LANGSMITH_TRACING": "false",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
        }
    )
    return environment


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                [
                    "taskkill.exe",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                env=_worker_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("worker process tree did not terminate") from error


def _run_worker(
    *,
    checkpoint: Path,
    dependency_dir: Path,
    journal: Path,
    node_command: str,
    phase: str,
    policy: str,
    scenario_id: str,
    scenario_root: Path,
    thread_id: str,
    tool_name: str,
    versions: dict[str, str],
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-I",
        "-m",
        "effect_witness.langgraph_worker",
        "--checkpoint",
        str(checkpoint),
        "--dependency-dir",
        str(dependency_dir),
        "--journal",
        str(journal),
        "--node-command",
        node_command,
        "--phase",
        phase,
        "--policy",
        policy,
        "--scenario-id",
        scenario_id,
        "--scenario-root",
        str(scenario_root),
        "--thread-id",
        thread_id,
        "--tool-name",
        tool_name,
    ]
    creation_flags = 0
    start_new_session = os.name != "nt"
    if os.name == "nt":
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    try:
        process = subprocess.Popen(
            command,
            env=_worker_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            cwd=checkpoint.parent,
            creationflags=creation_flags,
            start_new_session=start_new_session,
        )
    except OSError as error:
        raise RuntimeError("worker process did not start") from error
    try:
        stdout, stderr = process.communicate(timeout=_WORKER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        _terminate_process_tree(process)
        raise RuntimeError("worker process timed out") from error
    except BaseException:
        try:
            _terminate_process_tree(process)
        except Exception as cleanup_error:
            raise RuntimeError(
                "worker process cleanup failed after interruption"
            ) from cleanup_error
        raise
    if (
        len(stdout.encode("utf-8")) > _MAX_WORKER_OUTPUT_BYTES
        or len(stderr.encode("utf-8")) > _MAX_WORKER_OUTPUT_BYTES
    ):
        raise RuntimeError("worker output exceeded the registered bound")
    lines = [line for line in stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("worker stdout record count differs from registration")
    try:
        summary = strict_json_loads(lines[0])
    except (ValueError, RecursionError) as error:
        raise RuntimeError("worker stdout is not strict JSON") from error
    if (
        not isinstance(summary, dict)
        or summary.get("versions") != versions
        or summary.get("phase") != phase
    ):
        raise RuntimeError("worker summary differs from registration")
    return {
        "exit_code": process.returncode,
        "stderr_empty": not stderr.strip(),
        "stdout_record_count": len(lines),
        "summary": summary,
    }


def _events(database: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(database, timeout=5.0) as connection:
        rows = connection.execute(
            """
            SELECT sequence, event_type, phase, payload_json
            FROM events
            ORDER BY sequence
            """
        ).fetchall()
    events: list[dict[str, Any]] = []
    for sequence, event_type, phase, payload_json in rows:
        try:
            payload = strict_json_loads(payload_json)
        except (ValueError, RecursionError) as error:
            raise RuntimeError("worker journal payload is not strict JSON") from error
        if not isinstance(payload, dict):
            raise RuntimeError("worker journal payload is not an object")
        events.append(
            {
                "event_type": event_type,
                "payload": payload,
                "phase": phase,
                "sequence": sequence,
            }
        )
    return events


def _validate_journal_events(
    events: list[dict[str, Any]],
    *,
    tool_name: str,
) -> None:
    sequences = [event["sequence"] for event in events]
    if any(type(sequence) is not int for sequence in sequences) or sequences != list(
        range(1, len(events) + 1)
    ):
        raise RuntimeError("worker journal sequence differs from registration")
    latest_observation_error: bool | None = None
    for event in events:
        event_type = event["event_type"]
        payload = event["payload"]
        if event_type == "WORKER_STARTED":
            expected = {"durability": DURABILITY}
        elif event_type in {"TASK_STARTED", "TOOL_SENT"}:
            expected = {"tool_name": tool_name}
        elif event_type == "TASK_RETURNED":
            if not json_exact_equal(
                payload,
                {"is_error": latest_observation_error},
            ):
                raise RuntimeError("worker journal payload differs from registration")
            continue
        elif event_type == "TOOL_OBSERVED":
            if (
                not isinstance(payload, dict)
                or type(payload.get("is_error")) is not bool
            ):
                raise RuntimeError("worker journal payload differs from registration")
            latest_observation_error = payload["is_error"]
            continue
        else:
            expected = {}
        if not json_exact_equal(payload, expected):
            raise RuntimeError("worker journal payload differs from registration")


def _process_facts(
    record: dict[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    summary = record["summary"]
    if phase == "fault":
        return {
            "checkpoint": summary.get("checkpoint"),
            "error_types": summary.get("error_types"),
            "exit_code": record["exit_code"],
            "status": summary.get("status"),
            "stderr_empty": record["stderr_empty"],
            "stdout_record_count": record["stdout_record_count"],
        }
    return {
        "checkpoint": summary.get("checkpoint"),
        "exit_code": record["exit_code"],
        "status": summary.get("status"),
        "stderr_empty": record["stderr_empty"],
        "stdout_record_count": record["stdout_record_count"],
        "workflow_result": summary.get("value"),
    }


def _run_round(
    *,
    case_root: Path,
    dependency_dir: Path,
    node_command: str,
    policy: str,
    round_index: int,
    scenario_id: str,
    tamper: bool,
    tool_name: str,
    versions: dict[str, str],
) -> dict[str, Any]:
    case_root.mkdir()
    scenario_root = case_root / "sandbox"
    scenario_root.mkdir()
    if tool_name == "edit_file":
        (scenario_root / "document.txt").write_bytes(FIXTURE)
    checkpoint = case_root / "checkpoint.sqlite"
    journal = case_root / "journal.sqlite"
    thread_id = f"schema-v4/{scenario_id}/round-{round_index:02d}"
    s0 = _byte_tree(scenario_root)
    fault = _run_worker(
        checkpoint=checkpoint,
        dependency_dir=dependency_dir,
        journal=journal,
        node_command=node_command,
        phase="fault",
        policy=policy,
        scenario_id=scenario_id,
        scenario_root=scenario_root,
        thread_id=thread_id,
        tool_name=tool_name,
        versions=versions,
    )
    s1 = _byte_tree(scenario_root)
    if tamper:
        (scenario_root / "document.txt").write_bytes(TAMPERED)
    s2 = _byte_tree(scenario_root)
    resume = _run_worker(
        checkpoint=checkpoint,
        dependency_dir=dependency_dir,
        journal=journal,
        node_command=node_command,
        phase="resume",
        policy=policy,
        scenario_id=scenario_id,
        scenario_root=scenario_root,
        thread_id=thread_id,
        tool_name=tool_name,
        versions=versions,
    )
    s3 = _byte_tree(scenario_root)
    events = _events(journal)
    _validate_journal_events(events, tool_name=tool_name)
    observations = [
        event["payload"] for event in events if event["event_type"] == "TOOL_OBSERVED"
    ]
    decisions = [
        event["event_type"]
        for event in events
        if event["event_type"] in {"COMMITTED_CONFIRMED", "UNRESOLVED"}
    ]
    normalized_events = [
        {"phase": event["phase"], "type": event["event_type"]} for event in events
    ]
    fault_process = _process_facts(fault, phase="fault")
    resume_process = _process_facts(resume, phase="resume")
    checks = evaluate_round(
        scenario_id,
        decisions=decisions,
        events=normalized_events,
        fault_process=fault_process,
        observations=observations,
        resume_process=resume_process,
        s0=s0,
        s1=s1,
        s2=s2,
        s3=s3,
    )
    if not all(checks.values()):
        raise RuntimeError("registered replay round did not pass")
    record = {
        "all_checks_met": True,
        "checks": checks,
        "decisions": decisions,
        "events": normalized_events,
        "fault_process": fault_process,
        "mutating_call_observations": observations,
        "resume_process": resume_process,
        "round": round_index,
        "s0": s0,
        "s1": s1,
        "s2": s2,
        "s3": s3,
    }
    remove_owned_directory(
        case_root,
        label="LangGraph replay round work directory",
    )
    return record


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_junit(path: Path, cases: dict[str, dict[str, Any]]) -> None:
    test_count = len(cases) * REGISTERED_ROUNDS
    suite = ET.Element(
        "testsuite",
        {
            "failures": "0",
            "name": "effect-witness-langgraph-replay",
            "tests": str(test_count),
        },
    )
    for scenario_id in SCENARIO_ORDER:
        for round_record in cases[scenario_id]["rounds"]:
            round_index = round_record["round"]
            name = f"{scenario_id}/round-{round_index:02d}"
            node = ET.SubElement(
                suite,
                "testcase",
                {
                    "classname": "effect_witness.langgraph_replay",
                    "name": name,
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
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def _write_manifest(output: Path) -> int:
    if not output.is_dir() or _is_link_or_reparse(output):
        raise RuntimeError("artifact staging root is not an ordinary directory")
    captured: list[tuple[str, bytes]] = []
    for current, directory_names, file_names in os.walk(
        output,
        followlinks=False,
    ):
        current_path = Path(current)
        if not current_path.is_dir() or _is_link_or_reparse(current_path):
            raise RuntimeError("artifact staging contains an unsafe directory")
        directory_names.sort()
        file_names.sort()
        for name in directory_names:
            candidate = current_path / name
            if not candidate.is_dir() or _is_link_or_reparse(candidate):
                raise RuntimeError("artifact staging contains an unsafe directory")
            _safe_relative(candidate.relative_to(output).as_posix())
        for name in file_names:
            path = current_path / name
            relative = _safe_relative(path.relative_to(output).as_posix())
            if relative == "manifest.sha256":
                raise RuntimeError("artifact manifest already exists before sealing")
            captured.append((relative, _file_bytes(path, relative=relative)))
    rows = [
        f"{hashlib.sha256(content).hexdigest()}  {relative}\n"
        for relative, content in sorted(captured)
    ]
    (output / "manifest.sha256").write_text(
        "".join(rows),
        encoding="utf-8",
        newline="\n",
    )
    return len(rows)


def _provenance() -> dict[str, Any]:
    return {
        "javascript_sdk": JAVASCRIPT_SDK,
        "langgraph_packages": LANGGRAPH_PACKAGES,
        "lockfile_sha256": PACKAGE_LOCK_SHA256,
        "npm_package": FILESYSTEM_PACKAGE,
        "npm_package_files_in_artifact": False,
        "python_mcp_sdk_version": PYTHON_MCP_VERSION,
        "python_version_constraint_package_count": PYTHON_CONSTRAINT_PACKAGE_COUNT,
        "python_version_constraints_sha256": PYTHON_CONSTRAINTS_SHA256,
        "python_version_constraints_are_hash_lock": False,
        "raw_checkpoint_database_in_artifact": False,
        "server_distribution_files": {
            path: {"bytes": values[0], "sha256": values[1]}
            for path, values in sorted(SERVER_DISTRIBUTION_FILES.items())
        },
        "strict_msgpack_required": True,
        "upstream_root_license": UPSTREAM_ROOT_LICENSE,
    }


def run_langgraph_lane(
    output_dir: str | Path,
    *,
    constraints_file: str | Path,
    dependency_dir: str | Path,
    node_command: str = "node",
    work_dir: str | Path | None = None,
    source_revision: str = "UNCOMMITTED",
) -> dict[str, Any]:
    """Run, normalize, and atomically seal schema-v4 replay evidence."""

    if source_revision != "UNCOMMITTED" and (
        len(source_revision) != 40
        or any(character not in "0123456789abcdef" for character in source_revision)
    ):
        raise ValueError(
            "source_revision must be UNCOMMITTED or a lowercase 40-character commit"
        )
    platform_system = platform.system()
    if platform_system not in {"Linux", "Windows"}:
        raise RuntimeError("LangGraph replay lane supports only Linux and Windows")
    machine = platform.machine()
    if (platform_system, machine) not in {
        ("Linux", "x86_64"),
        ("Windows", "AMD64"),
    }:
        raise RuntimeError("LangGraph replay lane supports only x86-64")
    if platform.python_implementation() != "CPython" or sys.version_info[:2] not in {
        (3, 11),
        (3, 12),
        (3, 13),
    }:
        raise RuntimeError("LangGraph replay lane supports CPython 3.11 through 3.13")
    verify_python_constraints(constraints_file)
    versions = _versions()
    dependency = verify_dependency_directory(
        dependency_dir,
        node_command=node_command,
    )
    output_target, _ = ensure_disjoint_paths(
        output_dir,
        dependency.dependency_root,
        label="artifact output and dependency directories",
    )
    requested_work: Path | None = None
    if work_dir is not None:
        output_target, requested_work = ensure_disjoint_paths(
            output_target,
            work_dir,
            label="artifact output and work directories",
        )
        _, requested_work = ensure_disjoint_paths(
            dependency.dependency_root,
            requested_work,
            label="dependency and work directories",
        )
    output, staging = create_staging_directory(
        output_target,
        label="artifact output directory",
    )
    published = False
    requested_work = requested_work if requested_work is not None else staging / "_work"
    work: Path | None = None
    try:
        work = create_owned_directory(
            requested_work,
            label="LangGraph replay work directory",
        )
        case_values: dict[str, dict[str, Any]] = {}
        for scenario_id in SCENARIO_ORDER:
            registration = SCENARIOS[scenario_id]
            scenario_root = work / scenario_id
            scenario_root.mkdir()
            rounds = [
                _run_round(
                    case_root=scenario_root / f"round-{round_index:02d}",
                    dependency_dir=dependency.dependency_root,
                    node_command=dependency.node_command,
                    policy=registration["policy"],
                    round_index=round_index,
                    scenario_id=scenario_id,
                    tamper=registration["tamper_before_resume"],
                    tool_name=registration["tool_name"],
                    versions=versions,
                )
                for round_index in range(1, REGISTERED_ROUNDS + 1)
            ]
            case_values[scenario_id] = {
                "all_registered_checks_met": all(
                    round_record["all_checks_met"] for round_record in rounds
                ),
                "policy": registration["policy"],
                "round_count": REGISTERED_ROUNDS,
                "rounds": rounds,
                "scenario_id": scenario_id,
                "tool_name": registration["tool_name"],
            }
        remove_owned_directory(
            work,
            label="LangGraph replay work directory",
        )
        work = None
        results = staging / "results"
        results.mkdir()
        for scenario_id, case in case_values.items():
            _write_json(results / f"{scenario_id}.json", case)
        _write_json(staging / "provenance.json", _provenance())
        total_calls = sum(
            len(round_record["mutating_call_observations"])
            for case in case_values.values()
            for round_record in case["rounds"]
        )
        summary = {
            "all_registered_checks_met": all(
                case["all_registered_checks_met"] is True
                for case in case_values.values()
            ),
            "blocked_claims": list(BLOCKED_CLAIMS),
            "dependencies": {
                "effect-witness": versions["effect-witness"],
                "mcp-python": versions["mcp"],
                **{
                    package: versions[package] for package in sorted(LANGGRAPH_PACKAGES)
                },
            },
            "declared_source_revision": source_revision,
            "durability": DURABILITY,
            "evidence_boundary": EVIDENCE_BOUNDARY,
            "evidence_scope": EVIDENCE_SCOPE,
            "lane": LANE,
            "model_api_calls": 0,
            "mutating_call_observation_count": total_calls,
            "paid_service_calls": 0,
            "protocol": {
                "protocol_version": PROTOCOL_VERSION,
                "server_capabilities": {"tools": {"listChanged": True}},
                "server_identity": SERVER_IDENTITY,
            },
            "registered_rounds": REGISTERED_ROUNDS,
            "runtime": {
                "implementation": platform.python_implementation(),
                "machine_architecture": MACHINE_ARCHITECTURE,
                "node": dependency.node_version,
                "platform_system": platform_system,
                "python": platform.python_version(),
            },
            "scenario_count": len(case_values),
            "schema_version": SCHEMA_VERSION,
            "source_revision_verification": "caller_declared",
            "strict_msgpack": True,
            "worker_process_count": len(case_values) * REGISTERED_ROUNDS * 2,
        }
        if summary["all_registered_checks_met"] is not True:
            raise RuntimeError("registered replay matrix did not pass")
        _write_json(staging / "summary.json", summary)
        _write_junit(staging / "junit.xml", case_values)
        _write_manifest(staging)
        publish_staging_directory(
            staging,
            output,
            label="artifact output directory",
        )
        published = True
        return summary
    except BaseException:
        try:
            remove_owned_directories(
                [
                    (work, "LangGraph replay work directory"),
                    (
                        output if published else staging,
                        "artifact output directory",
                    ),
                ]
            )
        except Exception as cleanup_error:
            raise RuntimeError(
                "LangGraph replay cleanup failed after execution failure"
            ) from cleanup_error
        raise
