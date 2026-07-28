"""Schema-v5 runner for a registered mini-swe-agent coding effect."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import platform
import signal
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .artifact import _is_link_or_reparse
from .coding_constraints import verify_coding_constraints
from .coding_dependencies import verify_mini_swe_wheel
from .coding_fixture import (
    changed_paths,
    create_fixture,
    snapshot,
    tamper_fixture,
    validate_fixture,
)
from .coding_journal import initialize_journal, read_attempts
from .coding_registration import (
    BLOCKED_CLAIMS,
    EVIDENCE_BOUNDARY,
    EVIDENCE_SCOPE,
    LANE,
    MACHINE_ARCHITECTURE,
    MINI_SWE_AGENT_DEVELOPMENT_STATUS,
    MINI_SWE_AGENT_LICENSE,
    MINI_SWE_AGENT_PYTHON_REQUIRES,
    MINI_SWE_AGENT_RUNTIME_FILES,
    MINI_SWE_AGENT_VERSION,
    MINI_SWE_AGENT_WHEEL,
    MINI_SWE_AGENT_WHEEL_BYTES,
    MINI_SWE_AGENT_WHEEL_SHA256,
    MINI_SWE_AGENT_WHEEL_URL,
    PYTHON_CONSTRAINT_PACKAGE_COUNT,
    PYTHON_CONSTRAINTS_SHA256,
    REGISTERED_ROUNDS,
    SCENARIO_ORDER,
    SCENARIOS,
    SCHEMA_VERSION,
)
from .coding_semantics import evaluate_round
from .filesystem_paths import (
    create_owned_directory,
    create_staging_directory,
    ensure_disjoint_paths,
    publish_staging_directory,
    remove_owned_directories,
    remove_owned_directory,
)
from .models import canonical_json, strict_json_loads

_WORKER_TIMEOUT_SECONDS = 60
_MAX_WORKER_OUTPUT_BYTES = 64 * 1024
_PRODUCER_VERSIONS = ("0.4.0",)

_WORKER_FIELDS = {
    "agent_exit_status",
    "declared_mutation_count",
    "expected_error_type",
    "message_role_sequence",
    "mini_swe_agent_version",
    "model_query_count",
    "observed_mutation_returncodes",
    "phase",
    "status",
    "trajectory_state",
}


def _worker_environment(config_home: Path) -> dict[str, str]:
    allowed = (
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "WINDIR",
    )
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    if "PATH" not in environment:
        raise RuntimeError("coding-agent worker requires a bounded PATH")
    if os.name != "nt":
        environment["LANG"] = "C.UTF-8"
        environment["LC_ALL"] = "C.UTF-8"
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(config_home),
            "MSWEA_GLOBAL_CONFIG_DIR": str(config_home / "mini-swe-agent"),
            "MSWEA_SILENT_STARTUP": "1",
            "NO_COLOR": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
            "USERPROFILE": str(config_home),
        }
    )
    return environment


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                env=_worker_environment(Path(os.devnull).parent),
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
        raise RuntimeError(
            "coding-agent worker process tree did not terminate"
        ) from error


def _run_worker(
    *,
    config_home: Path,
    inject_save_failure: bool,
    journal: Path,
    phase: str,
    policy: str,
    trajectory: Path,
    wheel: Path,
    workspace: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-I",
        "-m",
        "effect_witness.coding_worker",
        "--journal",
        str(journal),
        "--phase",
        phase,
        "--policy",
        policy,
        "--trajectory",
        str(trajectory),
        "--wheel",
        str(wheel),
        "--workspace",
        str(workspace),
    ]
    if inject_save_failure:
        command.append("--inject-save-failure")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=workspace,
        env=_worker_environment(config_home),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=_WORKER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        raise RuntimeError("coding-agent worker timed out") from None
    if (
        len(stdout.encode("utf-8")) > _MAX_WORKER_OUTPUT_BYTES
        or len(stderr.encode("utf-8")) > _MAX_WORKER_OUTPUT_BYTES
    ):
        raise RuntimeError("coding-agent worker output exceeded the registered bound")
    lines = stdout.splitlines()
    if len(lines) != 1:
        raise RuntimeError("coding-agent worker stdout record count differs")
    try:
        record = strict_json_loads(lines[0])
    except (ValueError, RecursionError):
        raise RuntimeError("coding-agent worker stdout is not strict JSON") from None
    if not isinstance(record, dict) or set(record) != _WORKER_FIELDS:
        raise RuntimeError("coding-agent worker record differs from registration")
    if stderr != "":
        raise RuntimeError("coding-agent worker wrote unexpected stderr")
    return {
        **record,
        "exit_code": process.returncode,
        "stderr_empty": True,
        "stdout_record_count": 1,
    }


def _capture_state(workspace: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    return snapshot(workspace), validate_fixture(workspace), changed_paths(workspace)


def _make_owned_work_writable(root: Path) -> None:
    """Clear read-only bits only below the exact owned work root."""

    if not root.is_dir() or _is_link_or_reparse(root):
        raise RuntimeError("coding-agent work directory is not ordinary")
    for current, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current)
        if _is_link_or_reparse(current_path):
            raise RuntimeError("coding-agent work tree contains a reparse point")
        for name in directory_names:
            if _is_link_or_reparse(current_path / name):
                raise RuntimeError("coding-agent work tree contains a reparse point")
        for name in file_names:
            path = current_path / name
            if _is_link_or_reparse(path):
                raise RuntimeError("coding-agent work tree contains a reparse point")
            mode = path.stat(follow_symlinks=False).st_mode
            if not mode & stat.S_IWRITE:
                path.chmod(mode | stat.S_IWRITE)


def _run_round(
    *,
    case_root: Path,
    round_index: int,
    scenario_id: str,
    wheel: Path,
) -> dict[str, Any]:
    registration = SCENARIOS[scenario_id]
    case_root.mkdir()
    workspace = case_root / "workspace"
    workspace.mkdir()
    create_fixture(workspace)
    journal = case_root / "witness.sqlite"
    trajectory = case_root / "trajectory.json"
    initialize_journal(journal)

    snapshots: dict[str, Any] = {}
    validations: dict[str, Any] = {}
    changes: dict[str, list[str]] = {}
    snapshots["s0"], validations["s0"], changes["s0"] = _capture_state(workspace)

    initial_home = case_root / "initial-home"
    initial_home.mkdir()
    processes = [
        _run_worker(
            config_home=initial_home,
            inject_save_failure=registration["fault"],
            journal=journal,
            phase="initial",
            policy=registration["policy"],
            trajectory=trajectory,
            wheel=wheel,
            workspace=workspace,
        )
    ]
    snapshots["s1"], validations["s1"], changes["s1"] = _capture_state(workspace)

    if registration["tamper"]:
        tamper_fixture(workspace)
    snapshots["s2"], validations["s2"], changes["s2"] = _capture_state(workspace)

    if registration["restart"]:
        restart_home = case_root / "restart-home"
        restart_home.mkdir()
        processes.append(
            _run_worker(
                config_home=restart_home,
                inject_save_failure=False,
                journal=journal,
                phase="restart",
                policy=registration["policy"],
                trajectory=trajectory,
                wheel=wheel,
                workspace=workspace,
            )
        )
    snapshots["s3"], validations["s3"], changes["s3"] = _capture_state(workspace)
    journal_rows = read_attempts(journal)
    checks = evaluate_round(
        scenario_id,
        processes=processes,
        journal=journal_rows,
        snapshots=snapshots,
        validations=validations,
        changed_paths=changes,
    )
    return {
        "all_checks_met": all(checks.values()),
        "checks": checks,
        "changed_paths": changes,
        "journal": journal_rows,
        "processes": processes,
        "round": round_index,
        "scenario_id": scenario_id,
        "snapshots": snapshots,
        "validations": validations,
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        canonical_json(value) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_junit(path: Path, cases: dict[str, dict[str, Any]]) -> None:
    suite = ET.Element(
        "testsuite",
        {
            "failures": "0",
            "name": "effect-witness-mini-swe-agent",
            "tests": str(len(SCENARIO_ORDER) * REGISTERED_ROUNDS),
        },
    )
    for scenario_id in SCENARIO_ORDER:
        case = cases[scenario_id]
        for round_record in case["rounds"]:
            round_index = round_record["round"]
            name = f"{scenario_id}/round-{round_index:02d}"
            node = ET.SubElement(
                suite,
                "testcase",
                {
                    "classname": "effect_witness.mini_swe_agent",
                    "name": name,
                },
            )
            output = ET.SubElement(node, "system-out")
            output.text = canonical_json(
                {
                    "failed_checks": sorted(
                        key
                        for key, passed in round_record["checks"].items()
                        if passed is not True
                    ),
                    "round": round_index,
                    "scenario_id": scenario_id,
                }
            )
    path.write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))


def _write_manifest(output: Path) -> int:
    files = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "manifest.sha256"
    )
    lines: list[str] = []
    for path in files:
        if _is_link_or_reparse(path):
            raise RuntimeError("coding-agent artifact contains a link or reparse point")
        relative = path.relative_to(output).as_posix()
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n")
    (output / "manifest.sha256").write_text(
        "".join(lines),
        encoding="utf-8",
        newline="\n",
    )
    return len(lines)


def _provenance() -> dict[str, Any]:
    return {
        "mini_swe_agent": {
            "development_status": MINI_SWE_AGENT_DEVELOPMENT_STATUS,
            "license": MINI_SWE_AGENT_LICENSE,
            "python_requires": MINI_SWE_AGENT_PYTHON_REQUIRES,
            "runtime_files": MINI_SWE_AGENT_RUNTIME_FILES,
            "version": MINI_SWE_AGENT_VERSION,
            "wheel_bytes": MINI_SWE_AGENT_WHEEL_BYTES,
            "wheel_filename": MINI_SWE_AGENT_WHEEL,
            "wheel_in_artifact": False,
            "wheel_sha256": MINI_SWE_AGENT_WHEEL_SHA256,
            "wheel_url": MINI_SWE_AGENT_WHEEL_URL,
        },
        "model_api_calls": 0,
        "paid_service_calls": 0,
        "python_constraint_package_count": PYTHON_CONSTRAINT_PACKAGE_COUNT,
        "python_constraints_are_hash_lock": False,
        "python_constraints_sha256": PYTHON_CONSTRAINTS_SHA256,
        "raw_trajectory_in_artifact": False,
        "selected_runtime_bytes_verified": True,
    }


def run_coding_agent_lane(
    output_dir: str | Path,
    *,
    constraints_file: str | Path,
    dependency_dir: str | Path,
    work_dir: str | Path | None = None,
    source_revision: str = "UNCOMMITTED",
) -> dict[str, Any]:
    """Run, normalize, and atomically seal schema-v5 evidence."""

    if source_revision != "UNCOMMITTED" and (
        len(source_revision) != 40
        or any(character not in "0123456789abcdef" for character in source_revision)
    ):
        raise ValueError(
            "source_revision must be UNCOMMITTED or a lowercase 40-character commit"
        )
    platform_system = platform.system()
    machine = platform.machine()
    if (platform_system, machine) not in {
        ("Linux", "x86_64"),
        ("Windows", "AMD64"),
    }:
        raise RuntimeError("coding-agent lane supports only x86-64 Windows and Linux")
    if platform.python_implementation() != "CPython" or sys.version_info[:2] != (
        3,
        12,
    ):
        raise RuntimeError("coding-agent lane supports only CPython 3.12")

    dependency_root = Path(os.path.abspath(os.fspath(dependency_dir)))
    if not dependency_root.is_dir() or _is_link_or_reparse(dependency_root):
        raise ValueError("coding-agent dependency directory is not ordinary")
    members = list(dependency_root.iterdir())
    if (
        len(members) != 1
        or members[0].name != MINI_SWE_AGENT_WHEEL
        or not members[0].is_file()
    ):
        raise ValueError("coding-agent dependency directory inventory differs")
    wheel = verify_mini_swe_wheel(members[0]).path
    constraint_report = verify_coding_constraints(constraints_file)
    installed_version = importlib.metadata.version("mini-swe-agent")
    if installed_version != MINI_SWE_AGENT_VERSION:
        raise RuntimeError("installed mini-swe-agent version differs from registration")
    producer_version = importlib.metadata.version("effect-witness")
    if producer_version not in _PRODUCER_VERSIONS:
        raise RuntimeError("installed EffectWitness version is not registered")

    output_target, dependency_root = ensure_disjoint_paths(
        output_dir,
        dependency_root,
        label="coding-agent artifact and dependency directories",
    )
    requested_work: Path | None = None
    if work_dir is not None:
        output_target, requested_work = ensure_disjoint_paths(
            output_target,
            work_dir,
            label="coding-agent artifact and work directories",
        )
        _, requested_work = ensure_disjoint_paths(
            dependency_root,
            requested_work,
            label="coding-agent dependency and work directories",
        )
    output, staging = create_staging_directory(
        output_target,
        label="coding-agent artifact output directory",
    )
    published = False
    requested_work = requested_work if requested_work is not None else staging / "_work"
    work: Path | None = None
    try:
        work = create_owned_directory(
            requested_work,
            label="coding-agent work directory",
        )
        case_values: dict[str, dict[str, Any]] = {}
        for scenario_id in SCENARIO_ORDER:
            scenario_root = work / scenario_id
            scenario_root.mkdir()
            rounds = [
                _run_round(
                    case_root=scenario_root / f"round-{round_index:02d}",
                    round_index=round_index,
                    scenario_id=scenario_id,
                    wheel=wheel,
                )
                for round_index in range(1, REGISTERED_ROUNDS + 1)
            ]
            case_values[scenario_id] = {
                "all_registered_checks_met": all(
                    round_record["all_checks_met"] for round_record in rounds
                ),
                "fault": SCENARIOS[scenario_id]["fault"],
                "policy": SCENARIOS[scenario_id]["policy"],
                "restart": SCENARIOS[scenario_id]["restart"],
                "round_count": REGISTERED_ROUNDS,
                "rounds": rounds,
                "scenario_id": scenario_id,
                "tamper": SCENARIOS[scenario_id]["tamper"],
            }
        _make_owned_work_writable(work)
        remove_owned_directory(work, label="coding-agent work directory")
        work = None

        results = staging / "results"
        results.mkdir()
        for scenario_id, case in case_values.items():
            _write_json(results / f"{scenario_id}.json", case)
        _write_json(staging / "provenance.json", _provenance())

        round_records = [
            round_record
            for case in case_values.values()
            for round_record in case["rounds"]
        ]
        summary = {
            "all_registered_checks_met": all(
                case["all_registered_checks_met"] is True
                for case in case_values.values()
            ),
            "blocked_claims": list(BLOCKED_CLAIMS),
            "command_execution_count": sum(
                row["command_executed"] is True
                for round_record in round_records
                for row in round_record["journal"]
            ),
            "declared_mutation_count": sum(
                process["declared_mutation_count"]
                for round_record in round_records
                for process in round_record["processes"]
            ),
            "declared_source_revision": source_revision,
            "dependencies": {
                "effect-witness": producer_version,
                "mini-swe-agent": installed_version,
            },
            "dependency_constraint_package_count": constraint_report[
                "registered_package_count"
            ],
            "evidence_boundary": EVIDENCE_BOUNDARY,
            "evidence_scope": EVIDENCE_SCOPE,
            "lane": LANE,
            "model_api_calls": 0,
            "paid_service_calls": 0,
            "registered_rounds": REGISTERED_ROUNDS,
            "runtime": {
                "implementation": platform.python_implementation(),
                "machine_architecture": MACHINE_ARCHITECTURE,
                "platform_system": platform_system,
                "python": platform.python_version(),
            },
            "scenario_count": len(case_values),
            "schema_version": SCHEMA_VERSION,
            "source_revision_verification": "caller_declared",
            "worker_process_count": sum(
                len(round_record["processes"]) for round_record in round_records
            ),
        }
        if summary["all_registered_checks_met"] is not True:
            raise RuntimeError("registered coding-agent matrix did not pass")
        _write_json(staging / "summary.json", summary)
        _write_junit(staging / "junit.xml", case_values)
        _write_manifest(staging)
        publish_staging_directory(
            staging,
            output,
            label="coding-agent artifact output directory",
        )
        published = True
        return summary
    except BaseException:
        try:
            if work is not None and work.exists():
                _make_owned_work_writable(work)
            remove_owned_directories(
                [
                    (work, "coding-agent work directory"),
                    (
                        output if published else staging,
                        "coding-agent artifact output directory",
                    ),
                ]
            )
        except Exception as cleanup_error:
            raise RuntimeError(
                "coding-agent cleanup failed after execution failure"
            ) from cleanup_error
        raise
