"""Real-implementation evidence lane for the exact official filesystem server."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import stat
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .artifact import _is_link_or_reparse
from .filesystem_dependencies import verify_dependency_directory
from .filesystem_paths import (
    create_owned_directory,
    create_staging_directory,
    publish_staging_directory,
    remove_owned_directory,
)
from .filesystem_registration import (
    BLOCKED_CLAIMS,
    EVIDENCE_BOUNDARY,
    FILESYSTEM_PACKAGE,
    JAVASCRIPT_SDK,
    PROTOCOL_VERSION,
    PYTHON_MCP_VERSION,
    SCENARIO_ORDER,
    SERVER_DISTRIBUTION_FILES,
    SERVER_IDENTITY,
    TOOL_REGISTRATION,
    UPSTREAM_ROOT_LICENSE,
)
from .filesystem_semantics import (
    FIXTURE,
    evaluate_scenario,
    registered_stimulus,
)
from .models import canonical_json, json_exact_equal, sha256_json

_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_MAX_WITNESS_FILE_BYTES = 2 * 1024 * 1024


def _server_environment() -> dict[str, str]:
    """Return the minimal non-user environment passed to the server."""

    environment: dict[str, str] = {}
    for key in ("COMSPEC", "SYSTEMROOT", "WINDIR"):
        value = os.environ.get(key)
        if value:
            environment[key] = value
    if os.name != "nt":
        environment["LANG"] = "C.UTF-8"
        environment["LC_ALL"] = "C.UTF-8"
    return environment


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    segments = value.split("/")
    if (
        not value
        or value == "."
        or "\\" in value
        or ":" in value
        or path.is_absolute()
        or any(segment in {"", ".", ".."} for segment in segments)
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("witness contains an unsafe relative path")
    return value


def _file_bytes(path: Path, *, relative: str) -> bytes:
    try:
        before = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise RuntimeError(
            f"witness file is unavailable ({type(exc).__name__})"
        ) from None
    if (
        not stat.S_ISREG(before.st_mode)
        or _is_link_or_reparse(path)
        or before.st_size > _MAX_WITNESS_FILE_BYTES
    ):
        raise RuntimeError("witness contains an unsupported file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not os.path.samestat(before, opened) or opened.st_size != before.st_size:
            raise RuntimeError("witness file changed before observation")
        remaining = opened.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise RuntimeError("witness file changed during observation")
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        current = path.stat(follow_symlinks=False)
        if (
            not os.path.samestat(opened, after)
            or not os.path.samestat(opened, current)
            or (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
            != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or (opened.st_size, opened.st_mtime_ns)
            != (current.st_size, current.st_mtime_ns)
        ):
            raise RuntimeError("witness file changed during observation")
        return content
    finally:
        os.close(descriptor)


def _byte_tree(root: Path) -> dict[str, Any]:
    """Capture a fail-closed relative byte-tree projection."""

    if not root.is_dir() or _is_link_or_reparse(root):
        raise RuntimeError("witness root is not an accepted directory")
    entries: list[dict[str, Any]] = []
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        if _is_link_or_reparse(current_path):
            raise RuntimeError("witness contains a linked directory")
        directory_names.sort()
        file_names.sort()
        for name in directory_names:
            candidate = current_path / name
            if not candidate.is_dir() or _is_link_or_reparse(candidate):
                raise RuntimeError("witness contains an unsupported directory")
            relative = _safe_relative(candidate.relative_to(root).as_posix())
            entries.append({"kind": "directory", "path": relative})
        for name in file_names:
            candidate = current_path / name
            relative = _safe_relative(candidate.relative_to(root).as_posix())
            content = _file_bytes(candidate, relative=relative)
            entries.append(
                {
                    "bytes": len(content),
                    "kind": "file",
                    "path": relative,
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    entries.sort(key=lambda item: item["path"])
    return {
        "entries": entries,
        "tree_sha256": sha256_json(entries),
    }


def _exception_types(error: BaseException) -> list[str]:
    names = {type(error).__name__}
    nested = getattr(error, "exceptions", ())
    for child in nested:
        names.update(_exception_types(child))
    cause = error.__cause__
    if cause is not None:
        names.update(_exception_types(cause))
    return sorted(names)


def _normalized_call(
    *,
    completed: bool,
    response: Any | None = None,
    error: BaseException | None = None,
    read_result: bool,
) -> dict[str, Any]:
    if not completed:
        return {
            "completed": False,
            "content_types": [],
            "exception_types": _exception_types(error) if error else ["UnknownError"],
            "is_error": None,
            "response_text_included": False,
            "structured_content_present": False,
            "text_block_count": 0,
        }
    normalized = response.model_dump(mode="json", by_alias=True, exclude_none=True)
    content = normalized.get("content")
    blocks = content if isinstance(content, list) else []
    content_types = [
        item.get("type")
        for item in blocks
        if isinstance(item, dict) and isinstance(item.get("type"), str)
    ]
    text_values = [
        item.get("text")
        for item in blocks
        if isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text"), str)
    ]
    result: dict[str, Any] = {
        "completed": True,
        "content_types": sorted(content_types),
        "exception_types": [],
        "is_error": bool(normalized.get("isError", False)),
        "response_text_included": False,
        "structured_content_present": (
            "structuredContent" in normalized or "structured_content" in normalized
        ),
        "text_block_count": len(text_values),
    }
    if read_result and len(text_values) == 1:
        encoded = text_values[0].encode("utf-8")
        result.update(
            {
                "text_bytes": len(encoded),
                "text_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    else:
        result["response_text_redacted"] = True
    return result


async def _call(
    session: ClientSession,
    *,
    name: str,
    arguments: dict[str, Any],
    read_result: bool,
) -> dict[str, Any]:
    try:
        response = await session.call_tool(name, arguments)
    except Exception as error:
        return _normalized_call(
            completed=False,
            error=error,
            read_result=read_result,
        )
    return _normalized_call(
        completed=True,
        response=response,
        read_result=read_result,
    )


def _tool_records(
    tools: list[Any],
    *,
    forbidden: tuple[str, ...],
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if tool.name not in TOOL_REGISTRATION:
            continue
        if tool.name in selected:
            raise RuntimeError("server returned a duplicate registered tool")
        descriptor = tool.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )
        description = descriptor.pop("description", "")
        if not isinstance(description, str):
            raise RuntimeError("registered tool description is unavailable")
        serialized = canonical_json(descriptor)
        if any(
            value and value.casefold() in serialized.casefold() for value in forbidden
        ):
            raise RuntimeError("registered descriptor contains a private runtime value")
        description_claims = {
            "multiple_nested_directories_in_one_operation": (
                "Can create multiple nested directories in one operation."
                in description
            )
        }
        record = {
            "annotations": descriptor.get("annotations"),
            "description_claims": description_claims,
            "description_included": False,
            "description_sha256": hashlib.sha256(
                description.encode("utf-8")
            ).hexdigest(),
            "descriptor_without_description_included": False,
            "descriptor_without_description_sha256": hashlib.sha256(
                serialized.encode("utf-8")
            ).hexdigest(),
            "name": tool.name,
        }
        expected = {
            "description_included": False,
            "descriptor_without_description_included": False,
            "name": tool.name,
            **TOOL_REGISTRATION[tool.name],
        }
        if not json_exact_equal(record, expected):
            raise RuntimeError("registered tool descriptor differs from registration")
        selected[tool.name] = record
    if set(selected) != set(TOOL_REGISTRATION):
        raise RuntimeError("server did not return the complete registered tool set")
    return [selected[name] for name in sorted(selected)]


def _initialize_scenario(root: Path, scenario_id: str) -> None:
    root.mkdir()
    if scenario_id == "read_text_file":
        (root / "fixture.txt").write_bytes(FIXTURE)
    elif scenario_id == "edit_file":
        (root / "document.txt").write_bytes(FIXTURE)


async def _run_scenarios(
    *,
    node_command: str,
    server_entrypoint: Path,
    dependency_dir: Path,
    sandbox: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    parameters = StdioServerParameters(
        command=node_command,
        args=[str(server_entrypoint), str(sandbox)],
        env=_server_environment(),
        cwd=str(dependency_dir),
        encoding="utf-8",
        encoding_error_handler="strict",
    )
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(parameters, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                initialization = await session.initialize()
                init = initialization.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                )
                protocol = {
                    "protocol_version": init.get("protocolVersion"),
                    "server_capabilities": init.get("capabilities"),
                    "server_identity": init.get("serverInfo"),
                }
                if protocol != {
                    "protocol_version": PROTOCOL_VERSION,
                    "server_capabilities": {"tools": {"listChanged": True}},
                    "server_identity": SERVER_IDENTITY,
                }:
                    raise RuntimeError(
                        "server initialization differs from registration"
                    )
                tool_response = await session.list_tools()
                forbidden = (
                    str(sandbox),
                    str(dependency_dir),
                    str(server_entrypoint),
                    node_command if Path(node_command).is_absolute() else "",
                )
                tools = _tool_records(tool_response.tools, forbidden=forbidden)
                cases: list[dict[str, Any]] = []
                platform_system = platform.system()
                for scenario_id in SCENARIO_ORDER:
                    root = sandbox / scenario_id
                    _initialize_scenario(root, scenario_id)
                    tool_name, stimulus, arguments = registered_stimulus(scenario_id)
                    actual_arguments = dict(arguments)
                    actual_arguments["path"] = str(root / arguments["path"])
                    s0 = _byte_tree(root)
                    first = await _call(
                        session,
                        name=tool_name,
                        arguments=actual_arguments,
                        read_result=scenario_id == "read_text_file",
                    )
                    s1 = _byte_tree(root)
                    second = await _call(
                        session,
                        name=tool_name,
                        arguments=actual_arguments,
                        read_result=scenario_id == "read_text_file",
                    )
                    s2 = _byte_tree(root)
                    checks, outcome = evaluate_scenario(
                        scenario_id,
                        first=first,
                        second=second,
                        s0=s0,
                        s1=s1,
                        s2=s2,
                        platform_system=platform_system,
                    )
                    cases.append(
                        {
                            "checks": checks,
                            "expectation_met": all(checks.values()),
                            "first_call": first,
                            "observation_outcome": outcome,
                            "s0": s0,
                            "s0_equals_s1": json_exact_equal(s0, s1),
                            "s1": s1,
                            "s1_equals_s2": json_exact_equal(s1, s2),
                            "s2": s2,
                            "scenario_id": scenario_id,
                            "stimulus": stimulus,
                            "stimulus_sha256": sha256_json(stimulus),
                            "tool_name": tool_name,
                            "second_call": second,
                        }
                    )
                return protocol, tools, cases


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_junit(path: Path, cases: list[dict[str, Any]]) -> None:
    suite = ET.Element(
        "testsuite",
        {
            "failures": str(sum(case["expectation_met"] is not True for case in cases)),
            "name": "effect-witness-real-filesystem",
            "tests": str(len(cases)),
        },
    )
    for case in cases:
        node = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "effect_witness.real_filesystem",
                "name": case["scenario_id"],
            },
        )
        failed = sorted(
            name for name, passed in case["checks"].items() if passed is not True
        )
        if failed:
            failure = ET.SubElement(node, "failure", {"message": "unexpected result"})
            failure.text = canonical_json({"failed_checks": failed})
        output = ET.SubElement(node, "system-out")
        output.text = canonical_json(
            {
                "failed_checks": failed,
                "observation_outcome": case["observation_outcome"],
                "scenario_id": case["scenario_id"],
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
    rows = []
    for relative, content in sorted(captured):
        rows.append(f"{hashlib.sha256(content).hexdigest()}  {relative}\n")
    (output / "manifest.sha256").write_text(
        "".join(rows),
        encoding="utf-8",
        newline="\n",
    )
    return len(rows)


def run_filesystem_lane(
    output_dir: str | Path,
    *,
    dependency_dir: str | Path,
    node_command: str = "node",
    work_dir: str | Path | None = None,
    source_revision: str = "UNCOMMITTED",
) -> dict[str, Any]:
    """Run and seal the schema-v3 exact-filesystem evidence lane."""

    if (
        source_revision != "UNCOMMITTED"
        and _SOURCE_REVISION.fullmatch(source_revision) is None
    ):
        raise ValueError(
            "source_revision must be UNCOMMITTED or a lowercase 40-character commit"
        )
    platform_system = platform.system()
    if platform_system not in {"Linux", "Windows"}:
        raise RuntimeError("real filesystem lane supports only Linux and Windows")
    dependency = verify_dependency_directory(
        dependency_dir,
        node_command=node_command,
    )
    dependency_root = dependency.dependency_root
    output, staging = create_staging_directory(
        output_dir,
        label="artifact output directory",
    )
    published = False
    requested_work = Path(work_dir) if work_dir is not None else staging / "_work"
    work: Path | None = None
    try:
        work = create_owned_directory(
            requested_work,
            label="filesystem lane work directory",
        )
        sandbox = work / "sandbox"
        sandbox.mkdir()
        try:
            protocol, tools, cases = asyncio.run(
                _run_scenarios(
                    node_command=dependency.node_command,
                    server_entrypoint=dependency.server_entrypoint,
                    dependency_dir=dependency_root,
                    sandbox=sandbox,
                )
            )
        finally:
            remove_owned_directory(
                work,
                label="filesystem lane work directory",
            )
            work = None
        results = staging / "results"
        results.mkdir()
        for case in cases:
            _write_json(results / f"{case['scenario_id']}.json", case)
        provenance = {
            "javascript_sdk": JAVASCRIPT_SDK,
            "lockfile_sha256": dependency.lockfile_sha256,
            "npm_package": FILESYSTEM_PACKAGE,
            "python_mcp_sdk_version": importlib.metadata.version("mcp"),
            "server_distribution_files": {
                path: {"bytes": values[0], "sha256": values[1]}
                for path, values in sorted(SERVER_DISTRIBUTION_FILES.items())
            },
            "npm_package_files_in_artifact": False,
            "upstream_root_license": UPSTREAM_ROOT_LICENSE,
        }
        if provenance["python_mcp_sdk_version"] != PYTHON_MCP_VERSION:
            raise RuntimeError("Python MCP SDK version differs from registration")
        _write_json(staging / "provenance.json", provenance)
        _write_json(staging / "tools.json", tools)
        outcomes = Counter(case["observation_outcome"] for case in cases)
        summary = {
            "all_registered_checks_met": all(
                case["expectation_met"] is True for case in cases
            ),
            "blocked_claims": list(BLOCKED_CLAIMS),
            "dependencies": {
                "effect-witness": importlib.metadata.version("effect-witness"),
                "mcp-python": importlib.metadata.version("mcp"),
            },
            "evidence_boundary": EVIDENCE_BOUNDARY,
            "evidence_scope": (
                "exact official filesystem server over stdio with controlled "
                "relative byte-tree observations"
            ),
            "lane": "real_mcp_filesystem_stdio",
            "model_api_calls": 0,
            "observation_outcome_counts": dict(sorted(outcomes.items())),
            "paid_service_calls": 0,
            "protocol": protocol,
            "runtime": {
                "implementation": platform.python_implementation(),
                "node": dependency.node_version,
                "platform_system": platform_system,
                "python": platform.python_version(),
            },
            "scenario_count": len(cases),
            "schema_version": 3,
            "source_revision": source_revision,
        }
        _write_json(staging / "summary.json", summary)
        _write_junit(staging / "junit.xml", cases)
        _write_manifest(staging)
        publish_staging_directory(
            staging,
            output,
            label="artifact output directory",
        )
        published = True
        return summary
    except Exception:
        if work is not None:
            remove_owned_directory(
                work,
                label="filesystem lane work directory",
            )
        remove_owned_directory(
            output if published else staging,
            label="artifact output directory",
        )
        raise
