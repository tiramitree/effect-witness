"""Strict offline verifier for schema-v3 real-filesystem evidence."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .artifact import (
    _artifact_snapshot,
    _is_link_or_reparse,
    _load_manifest,
    _read_json,
    _verify_hashes,
)
from .filesystem_registration import (
    BLOCKED_CLAIMS,
    EVIDENCE_BOUNDARY,
    FILESYSTEM_PACKAGE,
    JAVASCRIPT_SDK,
    NODE_VERSION,
    PACKAGE_LOCK_SHA256,
    PROTOCOL_VERSION,
    PYTHON_MCP_VERSION,
    SCENARIO_ORDER,
    SERVER_DISTRIBUTION_FILES,
    SERVER_IDENTITY,
    TOOL_REGISTRATION,
    UPSTREAM_ROOT_LICENSE,
)
from .filesystem_semantics import evaluate_scenario, registered_stimulus
from .models import json_exact_equal, sha256_json, strict_json_loads

_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_CASE_FIELDS = {
    "checks",
    "expectation_met",
    "first_call",
    "observation_outcome",
    "s0",
    "s0_equals_s1",
    "s1",
    "s1_equals_s2",
    "s2",
    "scenario_id",
    "second_call",
    "stimulus",
    "stimulus_sha256",
    "tool_name",
}


def _append(errors: list[str], scenario_id: str, message: str) -> None:
    errors.append(f"{scenario_id}: {message}")


def _valid_call_shape(call: Any, *, read_result: bool) -> bool:
    if not isinstance(call, dict):
        return False
    common = {
        "completed",
        "content_types",
        "exception_types",
        "is_error",
        "response_text_included",
        "structured_content_present",
        "text_block_count",
    }
    expected = (
        common | {"text_bytes", "text_sha256"}
        if read_result
        else common | {"response_text_redacted"}
    )
    if set(call) != expected:
        return False
    if (
        call["completed"] is not True
        or call["content_types"] != ["text"]
        or call["exception_types"] != []
        or type(call["is_error"]) is not bool
        or call["response_text_included"] is not False
        or type(call["structured_content_present"]) is not bool
        or type(call["text_block_count"]) is not int
        or call["text_block_count"] != 1
    ):
        return False
    if read_result:
        return (
            type(call["text_bytes"]) is int
            and call["text_bytes"] >= 0
            and isinstance(call["text_sha256"], str)
            and _HEX64.fullmatch(call["text_sha256"]) is not None
        )
    return call["response_text_redacted"] is True


def _valid_tree(tree: Any) -> bool:
    if not isinstance(tree, dict) or set(tree) != {"entries", "tree_sha256"}:
        return False
    if (
        not isinstance(tree["tree_sha256"], str)
        or _HEX64.fullmatch(tree["tree_sha256"]) is None
        or not isinstance(tree["entries"], list)
        or sha256_json(tree["entries"]) != tree["tree_sha256"]
    ):
        return False
    paths: list[str] = []
    for entry in tree["entries"]:
        if not isinstance(entry, dict):
            return False
        if entry.get("kind") == "directory":
            if set(entry) != {"kind", "path"}:
                return False
        elif entry.get("kind") == "file":
            if set(entry) != {"bytes", "kind", "path", "sha256"}:
                return False
            if (
                type(entry["bytes"]) is not int
                or entry["bytes"] < 0
                or not isinstance(entry["sha256"], str)
                or _HEX64.fullmatch(entry["sha256"]) is None
            ):
                return False
        else:
            return False
        path = entry.get("path")
        if (
            not isinstance(path, str)
            or not path
            or path == "."
            or "\\" in path
            or ":" in path
            or PurePosixPath(path).is_absolute()
            or any(segment in {"", ".", ".."} for segment in path.split("/"))
            or any(ord(character) < 32 for character in path)
        ):
            return False
        paths.append(path)
    return paths == sorted(set(paths))


def _verify_case(
    case: Any,
    *,
    scenario_id: str,
    platform_system: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(case, dict):
        _append(errors, scenario_id, "result is not an object")
        return None
    if set(case) != _CASE_FIELDS:
        _append(errors, scenario_id, "result fields differ from registration")
    if case.get("scenario_id") != scenario_id:
        _append(errors, scenario_id, "scenario identifier differs from filename")
    read_result = scenario_id == "read_text_file"
    first = case.get("first_call")
    second = case.get("second_call")
    if not _valid_call_shape(first, read_result=read_result):
        _append(errors, scenario_id, "first call shape is invalid")
    if not _valid_call_shape(second, read_result=read_result):
        _append(errors, scenario_id, "second call shape is invalid")
    trees = [case.get(name) for name in ("s0", "s1", "s2")]
    if not all(_valid_tree(tree) for tree in trees):
        _append(errors, scenario_id, "byte-tree shape is invalid")
    if not all(isinstance(value, dict) for value in [first, second, *trees]):
        return case
    expected_checks, expected_outcome = evaluate_scenario(
        scenario_id,
        first=first,
        second=second,
        s0=trees[0],
        s1=trees[1],
        s2=trees[2],
        platform_system=platform_system,
    )
    if not json_exact_equal(case.get("checks"), expected_checks):
        _append(errors, scenario_id, "registered checks are inconsistent")
    if case.get("expectation_met") is not all(expected_checks.values()):
        _append(errors, scenario_id, "expectation flag is inconsistent")
    if case.get("expectation_met") is not True:
        _append(errors, scenario_id, "registered expectation was not met")
    if case.get("observation_outcome") != expected_outcome:
        _append(errors, scenario_id, "observation outcome is inconsistent")
    expected_stimulus = registered_stimulus(scenario_id)[1]
    if not json_exact_equal(case.get("stimulus"), expected_stimulus):
        _append(errors, scenario_id, "stimulus differs from registration")
    if case.get("stimulus_sha256") != sha256_json(expected_stimulus):
        _append(errors, scenario_id, "stimulus digest is inconsistent")
    expected_tool = registered_stimulus(scenario_id)[0]
    if case.get("tool_name") != expected_tool:
        _append(errors, scenario_id, "tool name differs from registration")
    if case.get("s0_equals_s1") is not json_exact_equal(trees[0], trees[1]):
        _append(errors, scenario_id, "S0/S1 relationship is inconsistent")
    if case.get("s1_equals_s2") is not json_exact_equal(trees[1], trees[2]):
        _append(errors, scenario_id, "S1/S2 relationship is inconsistent")
    return case


def _verify_tools(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("tools.json is not an array")
        return
    expected = [
        {
            "description_included": False,
            "descriptor_without_description_included": False,
            "name": name,
            **TOOL_REGISTRATION[name],
        }
        for name in sorted(TOOL_REGISTRATION)
    ]
    if not json_exact_equal(value, expected):
        errors.append("tools.json differs from the exact registration")


def _expected_provenance() -> dict[str, Any]:
    return {
        "javascript_sdk": JAVASCRIPT_SDK,
        "lockfile_sha256": PACKAGE_LOCK_SHA256,
        "npm_package": FILESYSTEM_PACKAGE,
        "python_mcp_sdk_version": PYTHON_MCP_VERSION,
        "server_distribution_files": {
            path: {"bytes": values[0], "sha256": values[1]}
            for path, values in sorted(SERVER_DISTRIBUTION_FILES.items())
        },
        "npm_package_files_in_artifact": False,
        "upstream_root_license": UPSTREAM_ROOT_LICENSE,
    }


def _verify_summary(
    summary: Any,
    *,
    cases: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(summary, dict):
        errors.append("summary.json is not an object")
        return None
    expected_fields = {
        "all_registered_checks_met",
        "blocked_claims",
        "dependencies",
        "evidence_boundary",
        "evidence_scope",
        "lane",
        "model_api_calls",
        "observation_outcome_counts",
        "paid_service_calls",
        "protocol",
        "runtime",
        "scenario_count",
        "schema_version",
        "source_revision",
    }
    if set(summary) != expected_fields:
        errors.append("summary fields differ from schema-v3 registration")
    if summary.get("schema_version") != 3:
        errors.append("unsupported summary schema_version")
    if summary.get("lane") != "real_mcp_filesystem_stdio":
        errors.append("summary lane differs from registration")
    if summary.get("scenario_count") != len(SCENARIO_ORDER):
        errors.append("summary scenario_count is inconsistent")
    if summary.get("all_registered_checks_met") is not True:
        errors.append("summary registered checks did not all pass")
    if summary.get("blocked_claims") != list(BLOCKED_CLAIMS):
        errors.append("summary blocked_claims differ from registration")
    if not json_exact_equal(summary.get("evidence_boundary"), EVIDENCE_BOUNDARY):
        errors.append("summary evidence boundary differs from registration")
    if summary.get("evidence_scope") != (
        "exact official filesystem server over stdio with controlled "
        "relative byte-tree observations"
    ):
        errors.append("summary evidence scope differs from registration")
    for field in ("model_api_calls", "paid_service_calls"):
        if type(summary.get(field)) is not int or summary[field] != 0:
            errors.append(f"summary {field} is invalid")
    expected_protocol = {
        "protocol_version": PROTOCOL_VERSION,
        "server_capabilities": {"tools": {"listChanged": True}},
        "server_identity": SERVER_IDENTITY,
    }
    if not json_exact_equal(summary.get("protocol"), expected_protocol):
        errors.append("summary protocol differs from observed registration")
    dependencies = summary.get("dependencies")
    if dependencies != {
        "effect-witness": "0.2.0",
        "mcp-python": PYTHON_MCP_VERSION,
    }:
        errors.append("summary dependencies differ from registration")
    runtime = summary.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {
        "implementation",
        "node",
        "platform_system",
        "python",
    }:
        errors.append("summary runtime fields differ from registration")
    else:
        if runtime.get("node") != NODE_VERSION:
            errors.append("summary Node version differs from registration")
        if runtime.get("platform_system") not in {"Linux", "Windows"}:
            errors.append("summary platform is not registered")
        for field in ("implementation", "python"):
            if not isinstance(runtime.get(field), str) or not runtime[field]:
                errors.append(f"summary runtime {field} is invalid")
    source_revision = summary.get("source_revision")
    if source_revision != "UNCOMMITTED" and (
        not isinstance(source_revision, str)
        or _SOURCE_REVISION.fullmatch(source_revision) is None
    ):
        errors.append("summary source_revision is invalid")
    counts = Counter(
        case.get("observation_outcome")
        for case in cases.values()
        if isinstance(case.get("observation_outcome"), str)
    )
    if summary.get("observation_outcome_counts") != dict(sorted(counts.items())):
        errors.append("summary observation outcome counts are inconsistent")
    if summary.get("scenario_count") != len(cases):
        errors.append("summary scenario count differs from result files")
    return summary


def _verify_junit(
    content: bytes | None,
    cases: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    if content is None:
        errors.append("junit.xml is missing or unavailable")
        return
    try:
        suite = ET.fromstring(content)
    except ET.ParseError as exc:
        errors.append(f"junit.xml is invalid ({type(exc).__name__})")
        return
    if suite.tag != "testsuite" or suite.attrib != {
        "failures": "0",
        "name": "effect-witness-real-filesystem",
        "tests": str(len(cases)),
    }:
        errors.append("JUnit suite differs from registration")
        return
    nodes = list(suite)
    if (
        len(nodes) != len(cases)
        or any(node.tag != "testcase" for node in nodes)
        or {node.get("name") for node in nodes} != set(cases)
    ):
        errors.append("JUnit testcase set is inconsistent")
        return
    for node in nodes:
        scenario_id = node.get("name")
        if node.attrib != {
            "classname": "effect_witness.real_filesystem",
            "name": scenario_id,
        }:
            _append(errors, str(scenario_id), "JUnit attributes are inconsistent")
        children = list(node)
        if [child.tag for child in children] != ["system-out"]:
            _append(errors, str(scenario_id), "JUnit children are inconsistent")
            continue
        output = children[0]
        if output.attrib or list(output) or output.text is None:
            _append(errors, str(scenario_id), "JUnit system-out shape is invalid")
            continue
        try:
            observed = strict_json_loads(output.text)
        except (ValueError, RecursionError):
            observed = None
        case = cases[str(scenario_id)]
        expected = {
            "failed_checks": [],
            "observation_outcome": case["observation_outcome"],
            "scenario_id": scenario_id,
        }
        if not json_exact_equal(observed, expected):
            _append(errors, str(scenario_id), "JUnit system-out is inconsistent")


def _verify_filesystem_artifact_impl(artifact_dir: str | Path) -> dict[str, Any]:
    root = Path(artifact_dir)
    errors: list[str] = []
    if not root.is_dir() or _is_link_or_reparse(root):
        return {
            "artifact_schema_version": None,
            "errors": ["artifact directory is missing or is not a regular directory"],
            "files_hashed": 0,
            "lane": "real_mcp_filesystem_stdio",
            "scenario_count": 0,
            "verified": False,
            "verification_scope": (
                "offline integrity and internal consistency; not authenticity"
            ),
        }
    actual_files, snapshot = _artifact_snapshot(root, errors)
    manifest = _load_manifest(snapshot, errors)
    _verify_hashes(snapshot, manifest, actual_files, errors)
    expected_files = {
        "junit.xml",
        "manifest.sha256",
        "provenance.json",
        "summary.json",
        "tools.json",
        *(f"results/{scenario_id}.json" for scenario_id in SCENARIO_ORDER),
    }
    for relative in sorted(actual_files - expected_files):
        errors.append(f"unexpected artifact file: {relative}")
    for relative in sorted(expected_files - actual_files):
        errors.append(f"expected artifact file is missing: {relative}")
    summary = _read_json(snapshot, "summary.json", errors)
    platform_system = (
        summary.get("runtime", {}).get("platform_system")
        if isinstance(summary, dict) and isinstance(summary.get("runtime"), dict)
        else ""
    )
    cases: dict[str, dict[str, Any]] = {}
    for scenario_id in SCENARIO_ORDER:
        value = _read_json(snapshot, f"results/{scenario_id}.json", errors)
        case = _verify_case(
            value,
            scenario_id=scenario_id,
            platform_system=platform_system,
            errors=errors,
        )
        if case is not None:
            cases[scenario_id] = case
    _verify_tools(_read_json(snapshot, "tools.json", errors), errors)
    provenance = _read_json(snapshot, "provenance.json", errors)
    if not json_exact_equal(provenance, _expected_provenance()):
        errors.append("provenance.json differs from registration")
    summary_value = _verify_summary(summary, cases=cases, errors=errors)
    _verify_junit(snapshot.get("junit.xml"), cases, errors)
    return {
        "artifact_schema_version": (
            summary_value.get("schema_version")
            if isinstance(summary_value, dict)
            else None
        ),
        "errors": sorted(set(errors)),
        "files_hashed": len(manifest),
        "lane": "real_mcp_filesystem_stdio",
        "scenario_count": len(cases),
        "verified": not errors,
        "verification_scope": (
            "offline integrity and internal consistency; not authenticity"
        ),
    }


def verify_filesystem_artifact(artifact_dir: str | Path) -> dict[str, Any]:
    """Fail closed without exposing malformed artifact values or host paths."""

    try:
        return _verify_filesystem_artifact_impl(artifact_dir)
    except Exception as exc:
        return {
            "artifact_schema_version": None,
            "errors": [f"artifact verification aborted ({type(exc).__name__})"],
            "files_hashed": 0,
            "lane": "real_mcp_filesystem_stdio",
            "scenario_count": 0,
            "verified": False,
            "verification_scope": (
                "offline integrity and internal consistency; not authenticity"
            ),
        }
