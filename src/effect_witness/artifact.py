"""Offline verification for EffectWitness evidence artifacts.

The manifest is an integrity checksum, not a signature or an authenticity
claim.  Verification also checks the schema's internal relationships so that
an intact but self-contradictory artifact does not pass.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .artifact_semantics import (
    SCENARIO_SPECS,
    expected_contract_counts,
    verify_registered_case,
)
from .models import ClientOutcome, ContractResult, json_exact_equal, strict_json_loads

_MANIFEST_LINE = re.compile(r"^(?P<sha256>[0-9a-f]{64})  (?P<path>.+)$")
_MAX_FILE_BYTES = 10 * 1024 * 1024
_MAX_TOTAL_BYTES = 50 * 1024 * 1024
_EXPECTED_BLOCKED_CLAIMS = (
    "exactly-once execution",
    "official MCP certification",
    "production reliability",
    "security",
    "distributed consistency",
    "framework superiority",
    "external adoption",
)
_EXPECTED_EVIDENCE_SCOPE = (
    "synthetic local SQLite effects over loopback MCP Streamable HTTP"
)
_EXPECTED_SUMMARY_FIELDS = {
    "all_expectations_met",
    "blocked_claims",
    "contract_result_counts",
    "dependencies",
    "evidence_scope",
    "model_api_calls",
    "paid_service_calls",
    "runtime",
    "scenario_count",
    "schema_version",
    "source_revision",
}


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        return True
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        reparse_flag and attributes & reparse_flag
    )


def _same_snapshot_file(
    left: os.stat_result,
    right: os.stat_result,
) -> bool:
    return os.path.samestat(left, right)


def _same_snapshot_content_version(
    left: os.stat_result,
    right: os.stat_result,
) -> bool:
    """Compare identity and content metadata across path and handle stats."""

    return _same_snapshot_file(left, right) and (
        left.st_size,
        left.st_mtime_ns,
    ) == (
        right.st_size,
        right.st_mtime_ns,
    )


def _same_snapshot_version(
    left: os.stat_result,
    right: os.stat_result,
) -> bool:
    return _same_snapshot_file(left, right) and (
        left.st_size,
        left.st_mtime_ns,
        left.st_ctime_ns,
    ) == (
        right.st_size,
        right.st_mtime_ns,
        right.st_ctime_ns,
    )


def _snapshot_file_bytes(
    path: Path,
    *,
    relative: str,
    pre_open: os.stat_result,
    errors: list[str],
) -> bytes | None:
    if pre_open.st_size > _MAX_FILE_BYTES:
        errors.append(f"artifact file exceeds size limit: {relative}")
        return None

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        errors.append(f"cannot open {relative} ({type(exc).__name__})")
        return None

    result: bytes | None = None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or _metadata_is_link_or_reparse(opened)
            or not _same_snapshot_content_version(pre_open, opened)
        ):
            errors.append(f"artifact file changed before snapshot read: {relative}")
            return None
        if opened.st_size > _MAX_FILE_BYTES:
            errors.append(f"artifact file exceeds size limit: {relative}")
            return None

        remaining = opened.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                errors.append(f"artifact file changed during snapshot read: {relative}")
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        result = b"".join(chunks)

        after_read = os.fstat(descriptor)
        try:
            post_read = path.stat(follow_symlinks=False)
        except OSError as exc:
            errors.append(
                f"artifact file changed during snapshot read: "
                f"{relative} ({type(exc).__name__})"
            )
            return None
        if (
            len(result) != opened.st_size
            or _metadata_is_link_or_reparse(post_read)
            or not stat.S_ISREG(post_read.st_mode)
            or not _same_snapshot_version(pre_open, post_read)
            or not _same_snapshot_version(opened, after_read)
            or not _same_snapshot_content_version(opened, post_read)
        ):
            errors.append(f"artifact file changed during snapshot read: {relative}")
            return None
        return result
    except OSError as exc:
        errors.append(f"cannot read {relative} ({type(exc).__name__})")
        return None
    finally:
        try:
            os.close(descriptor)
        except OSError as exc:
            errors.append(f"cannot close {relative} ({type(exc).__name__})")


def _read_json(
    snapshot: dict[str, bytes],
    relative: str,
    errors: list[str],
) -> Any | None:
    content = snapshot.get(relative)
    if content is None:
        errors.append(f"{PurePosixPath(relative).name}: unavailable from snapshot")
        return None
    try:
        return strict_json_loads(content.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        errors.append(
            f"{PurePosixPath(relative).name}: invalid JSON ({type(exc).__name__})"
        )
        return None


def _artifact_snapshot(
    root: Path,
    errors: list[str],
) -> tuple[set[str], dict[str, bytes]]:
    files: set[str] = set()
    snapshot: dict[str, bytes] = {}
    total_bytes = 0
    total_limit_reported = False
    directory_states: dict[Path, os.stat_result] = {}

    def walk_error(error: OSError) -> None:
        errors.append(f"artifact traversal failed ({type(error).__name__})")

    for current, directory_names, file_names in os.walk(
        root,
        followlinks=False,
        onerror=walk_error,
    ):
        current_path = Path(current)
        current_relative = (
            "." if current_path == root else current_path.relative_to(root).as_posix()
        )
        try:
            current_metadata = current_path.stat(follow_symlinks=False)
        except OSError as exc:
            errors.append(
                f"cannot inspect artifact directory {current_relative} "
                f"({type(exc).__name__})"
            )
            directory_names.clear()
            continue
        prior_directory_metadata = directory_states.setdefault(
            current_path,
            current_metadata,
        )
        if (
            _metadata_is_link_or_reparse(current_metadata)
            or not stat.S_ISDIR(current_metadata.st_mode)
            or not _same_snapshot_version(
                prior_directory_metadata,
                current_metadata,
            )
        ):
            errors.append(
                f"artifact directory changed during snapshot: {current_relative}"
            )
            directory_names.clear()
            continue

        directory_names.sort()
        file_names.sort()
        for directory_name in list(directory_names):
            directory = current_path / directory_name
            relative = directory.relative_to(root).as_posix()
            try:
                metadata = directory.stat(follow_symlinks=False)
            except OSError as exc:
                errors.append(
                    f"cannot inspect artifact directory {relative} "
                    f"({type(exc).__name__})"
                )
                directory_names.remove(directory_name)
                continue
            if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(
                metadata.st_mode
            ):
                errors.append(
                    f"links, junctions, and non-directories are not allowed: {relative}"
                )
                directory_names.remove(directory_name)
                continue
            directory_states.setdefault(directory, metadata)

        for file_name in file_names:
            path = current_path / file_name
            relative = path.relative_to(root).as_posix()
            try:
                metadata = path.stat(follow_symlinks=False)
            except OSError as exc:
                errors.append(f"cannot inspect {relative} ({type(exc).__name__})")
                continue
            if _metadata_is_link_or_reparse(metadata):
                errors.append(f"links and junctions are not allowed: {relative}")
                continue
            if not stat.S_ISREG(metadata.st_mode):
                errors.append(f"non-regular artifact entry is not allowed: {relative}")
                continue
            files.add(relative)
            if metadata.st_size > _MAX_FILE_BYTES:
                errors.append(f"artifact file exceeds size limit: {relative}")
                continue
            total_bytes += metadata.st_size
            if total_bytes > _MAX_TOTAL_BYTES:
                if not total_limit_reported:
                    errors.append("artifact exceeds total size limit")
                    total_limit_reported = True
                continue
            content = _snapshot_file_bytes(
                path,
                relative=relative,
                pre_open=metadata,
                errors=errors,
            )
            if content is not None:
                snapshot[relative] = content

    for directory, before in sorted(
        directory_states.items(),
        key=lambda item: str(item[0]),
    ):
        relative = "." if directory == root else directory.relative_to(root).as_posix()
        try:
            after = directory.stat(follow_symlinks=False)
        except OSError as exc:
            errors.append(
                f"artifact directory changed during snapshot: "
                f"{relative} ({type(exc).__name__})"
            )
            continue
        if (
            _metadata_is_link_or_reparse(after)
            or not stat.S_ISDIR(after.st_mode)
            or not _same_snapshot_version(before, after)
        ):
            errors.append(f"artifact directory changed during snapshot: {relative}")
    return files, snapshot


def _load_manifest(
    snapshot: dict[str, bytes],
    errors: list[str],
) -> dict[str, str]:
    content = snapshot.get("manifest.sha256")
    if content is None:
        errors.append("manifest.sha256 is missing or unavailable from snapshot")
        return {}
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeError as exc:
        errors.append(f"manifest.sha256 is unreadable ({type(exc).__name__})")
        return {}
    records: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        match = _MANIFEST_LINE.fullmatch(line)
        if match is None:
            errors.append(f"manifest line {line_number} is malformed")
            continue
        relative = match.group("path")
        pure = PurePosixPath(relative)
        if (
            relative == "manifest.sha256"
            or "\x00" in relative
            or "\\" in relative
            or pure.is_absolute()
            or not pure.parts
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            errors.append(f"manifest line {line_number} has an unsafe path")
            continue
        if relative in records:
            errors.append(f"manifest contains duplicate path: {relative}")
            continue
        records[relative] = match.group("sha256")
    if not records:
        errors.append("manifest contains no valid records")
    return records


def _verify_hashes(
    snapshot: dict[str, bytes],
    manifest: dict[str, str],
    actual_files: set[str],
    errors: list[str],
) -> None:
    listed_files = set(manifest)
    expected_files = actual_files - {"manifest.sha256"}
    for relative in sorted(listed_files - expected_files):
        errors.append(f"manifest lists a missing file: {relative}")
    for relative in sorted(expected_files - listed_files):
        errors.append(f"file is not covered by the manifest: {relative}")
    for relative in sorted(listed_files & expected_files):
        content = snapshot.get(relative)
        if content is None:
            errors.append(f"cannot hash unavailable snapshot file: {relative}")
            continue
        actual = hashlib.sha256(content).hexdigest()
        if actual != manifest[relative]:
            errors.append(f"SHA-256 mismatch: {relative}")


def _verify_results(
    snapshot: dict[str, bytes],
    manifest: dict[str, str],
    errors: list[str],
) -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    result_paths = sorted(
        relative
        for relative in manifest
        if relative.startswith("results/") and relative.endswith(".json")
    )
    cases: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    allowed_contract_results = {item.value for item in ContractResult}
    allowed_client_outcomes = {item.value for item in ClientOutcome}
    for relative in result_paths:
        pure = PurePosixPath(relative)
        if len(pure.parts) != 2:
            errors.append(f"result path must be directly under results/: {relative}")
            continue
        data = _read_json(snapshot, relative, errors)
        if not isinstance(data, dict):
            if data is not None:
                errors.append(f"result must be a JSON object: {relative}")
            continue
        scenario_id = data.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id != pure.stem:
            errors.append(f"scenario_id does not match its filename: {relative}")
            continue
        if scenario_id in cases:
            errors.append(f"duplicate scenario_id: {scenario_id}")
            continue
        contract_result = data.get("contract_result")
        client_outcome = data.get("client_outcome")
        if contract_result not in allowed_contract_results:
            errors.append(f"invalid contract_result in {relative}")
        if client_outcome not in allowed_client_outcomes:
            errors.append(f"invalid client_outcome in {relative}")
        expected = data.get("expected")
        if not isinstance(expected, dict):
            errors.append(f"expected must be an object in {relative}")
            expected = {}
        checks = data.get("evidence_checks")
        recomputed = (
            expected.get("contract_result") == contract_result
            and expected.get("client_outcome") == client_outcome
            and isinstance(checks, dict)
            and bool(checks)
            and all(value is True for value in checks.values())
        )
        if data.get("expectation_met") is not recomputed:
            errors.append(f"expectation_met is inconsistent in {relative}")
        witness = data.get("witness")
        if (
            not isinstance(witness, dict)
            or not isinstance(witness.get("effect_count"), int)
            or isinstance(witness.get("effect_count"), bool)
            or witness["effect_count"] < 0
        ):
            errors.append(f"witness.effect_count is invalid in {relative}")
        verify_registered_case(data, errors)
        if isinstance(contract_result, str):
            counts[contract_result] += 1
        cases[scenario_id] = data
    if not result_paths:
        errors.append("artifact contains no result JSON files")
    if set(cases) != set(SCENARIO_SPECS):
        errors.append("schema-v2 scenario set is incomplete or unexpected")
    return cases, counts


def _verify_summary(
    snapshot: dict[str, bytes],
    cases: dict[str, dict[str, Any]],
    counts: Counter[str],
    errors: list[str],
) -> dict[str, Any] | None:
    summary = _read_json(snapshot, "summary.json", errors)
    if not isinstance(summary, dict):
        if summary is not None:
            errors.append("summary.json must contain an object")
        return None
    if set(summary) != _EXPECTED_SUMMARY_FIELDS:
        errors.append("summary fields differ from registration")
    if not json_exact_equal(summary.get("schema_version"), 2):
        errors.append("unsupported summary schema_version")
    if not json_exact_equal(summary.get("scenario_count"), len(cases)):
        errors.append("summary scenario_count is inconsistent")
    expected_all = bool(cases) and all(
        case.get("expectation_met") is True for case in cases.values()
    )
    if summary.get("all_expectations_met") is not expected_all:
        errors.append("summary all_expectations_met is inconsistent")
    if not json_exact_equal(
        summary.get("contract_result_counts"), dict(sorted(counts.items()))
    ):
        errors.append("summary contract_result_counts is inconsistent")
    if not json_exact_equal(
        summary.get("contract_result_counts"), expected_contract_counts()
    ):
        errors.append("summary contract_result_counts is not the v2 matrix")
    if not json_exact_equal(
        summary.get("blocked_claims"), list(_EXPECTED_BLOCKED_CLAIMS)
    ):
        errors.append("summary blocked claims differ from registration")
    if summary.get("evidence_scope") != _EXPECTED_EVIDENCE_SCOPE:
        errors.append("summary evidence_scope differs from registration")
    for field in ("model_api_calls", "paid_service_calls"):
        value = summary.get(field)
        if type(value) is not int or value != 0:
            errors.append(f"summary {field} is invalid")
    dependencies = summary.get("dependencies")
    if not isinstance(dependencies, dict):
        errors.append("summary dependencies are missing")
    else:
        if set(dependencies) != {"effect-witness", "httpx", "mcp"}:
            errors.append("summary dependency fields differ from registration")
        for dependency in ("effect-witness", "httpx", "mcp"):
            if (
                not isinstance(dependencies.get(dependency), str)
                or not dependencies[dependency]
            ):
                errors.append(f"summary dependency {dependency} is invalid")
        for case in cases.values():
            protocol = case.get("protocol")
            if isinstance(protocol, dict) and protocol.get(
                "python_sdk"
            ) != dependencies.get("mcp"):
                errors.append("case MCP version differs from summary dependency")
    runtime = summary.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("summary runtime is missing")
    else:
        if set(runtime) != {"implementation", "platform_system", "python", "sqlite"}:
            errors.append("summary runtime fields differ from registration")
        for field in ("implementation", "platform_system", "python", "sqlite"):
            if not isinstance(runtime.get(field), str) or not runtime[field]:
                errors.append(f"summary runtime {field} is invalid")
    source_revision = summary.get("source_revision")
    if source_revision != "UNCOMMITTED" and (
        not isinstance(source_revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_revision) is None
    ):
        errors.append("summary source_revision is invalid")
    return summary


def _verify_junit(
    snapshot: dict[str, bytes],
    cases: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    content = snapshot.get("junit.xml")
    if content is None:
        errors.append("junit.xml is missing or unavailable from snapshot")
        return
    try:
        suite = ET.fromstring(content)
    except ET.ParseError as exc:
        errors.append(f"junit.xml is invalid ({type(exc).__name__})")
        return
    if suite.tag != "testsuite":
        errors.append("junit.xml root is not testsuite")
        return
    expected_failures = sum(
        case.get("expectation_met") is not True for case in cases.values()
    )
    expected_suite_attributes = {
        "failures": str(expected_failures),
        "name": "effect-witness-mcp",
        "tests": str(len(cases)),
    }
    if suite.attrib != expected_suite_attributes:
        errors.append("JUnit suite attributes are inconsistent")
    children = list(suite)
    if any(child.tag != "testcase" for child in children):
        errors.append("JUnit suite contains an unexpected child")
    nodes = [child for child in children if child.tag == "testcase"]
    if len(nodes) != len(cases):
        errors.append("JUnit test count is inconsistent")
    names = [node.get("name") for node in nodes]
    if len(names) != len(set(names)) or set(names) != set(cases):
        errors.append("JUnit scenario names are inconsistent")
        return
    for node in nodes:
        name = node.get("name")
        if name not in cases:
            continue
        case = cases[name]
        expected_failure = case.get("expectation_met") is not True
        expected_node_attributes = {
            "classname": "effect_witness.mcp",
            "name": name,
        }
        if node.attrib != expected_node_attributes:
            errors.append(f"JUnit testcase attributes are inconsistent for {name}")
        expected_child_tags = (
            ["failure", "system-out"] if expected_failure else ["system-out"]
        )
        if [child.tag for child in node] != expected_child_tags:
            errors.append(f"JUnit testcase children are inconsistent for {name}")
        failure = node.find("failure")
        if failure is not None and failure.attrib != {"message": "unexpected result"}:
            errors.append(f"JUnit failure attributes are inconsistent for {name}")
        output_node = node.find("system-out")
        if output_node is None or output_node.attrib or list(output_node):
            errors.append(f"JUnit system-out shape is inconsistent for {name}")
        output = output_node.text if output_node is not None else None
        try:
            observed = strict_json_loads(output) if output is not None else None
        except (ValueError, RecursionError):
            observed = None
        witness = case.get("witness")
        checks = case.get("evidence_checks")
        failed_evidence_checks = (
            sorted(name for name, passed in checks.items() if passed is not True)
            if isinstance(checks, dict)
            else ["<invalid-evidence-checks>"]
        )
        expected_output = {
            "client_outcome": case.get("client_outcome"),
            "contract_result": case.get("contract_result"),
            "effect_count": (
                witness.get("effect_count") if isinstance(witness, dict) else None
            ),
            "failed_evidence_checks": failed_evidence_checks,
        }
        if not json_exact_equal(observed, expected_output):
            errors.append(f"JUnit system-out is inconsistent for {name}")


def _verify_artifact_impl(artifact_dir: str | Path) -> dict[str, Any]:
    """Verify one schema-v2 evidence directory without running its scenarios."""

    root = Path(artifact_dir)
    errors: list[str] = []
    if not root.is_dir() or _is_link_or_reparse(root):
        return {
            "artifact_schema_version": None,
            "errors": ["artifact directory is missing or is not a regular directory"],
            "files_hashed": 0,
            "scenario_count": 0,
            "verified": False,
            "verification_scope": (
                "offline integrity and internal consistency; not authenticity"
            ),
        }
    actual_files, snapshot = _artifact_snapshot(root, errors)
    manifest = _load_manifest(snapshot, errors)
    _verify_hashes(snapshot, manifest, actual_files, errors)
    expected_shapes = {"manifest.sha256", "summary.json", "junit.xml"}
    unexpected = {
        relative
        for relative in actual_files
        if relative not in expected_shapes
        and not (
            relative.startswith("results/")
            and len(PurePosixPath(relative).parts) == 2
            and relative.endswith(".json")
        )
    }
    for relative in sorted(unexpected):
        errors.append(f"unexpected artifact file: {relative}")
    cases, counts = _verify_results(snapshot, manifest, errors)
    summary = _verify_summary(snapshot, cases, counts, errors)
    _verify_junit(snapshot, cases, errors)
    return {
        "artifact_schema_version": (
            summary.get("schema_version") if isinstance(summary, dict) else None
        ),
        "errors": sorted(set(errors)),
        "files_hashed": len(manifest),
        "scenario_count": len(cases),
        "verified": not errors,
        "verification_scope": (
            "offline integrity and internal consistency; not authenticity"
        ),
    }


def verify_artifact(artifact_dir: str | Path) -> dict[str, Any]:
    """Fail closed with a structured report for every malformed artifact."""

    try:
        return _verify_artifact_impl(artifact_dir)
    except Exception as exc:
        return {
            "artifact_schema_version": None,
            "errors": [f"artifact verification aborted ({type(exc).__name__})"],
            "files_hashed": 0,
            "scenario_count": 0,
            "verified": False,
            "verification_scope": (
                "offline integrity and internal consistency; not authenticity"
            ),
        }
