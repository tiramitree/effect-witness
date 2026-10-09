"""Exact registration for the schema-v4 LangGraph replay evidence lane."""

from __future__ import annotations

from typing import Any, Final

SCHEMA_VERSION: Final = 4
LANE: Final = "langgraph_mcp_filesystem_replay"
REGISTERED_ROUNDS: Final = 10
INJECTED_EXIT_CODE: Final = 17
DURABILITY: Final = "sync"
MACHINE_ARCHITECTURE: Final = "x86_64"
PYTHON_CONSTRAINTS_SHA256: Final = (
    "ad4ee58ce68f49ce0cd2c0b98d410af9c2a887ead107a2ff254c3be35c4925d7"
)
PYTHON_CONSTRAINT_PACKAGE_COUNT: Final = 58

LANGGRAPH_PACKAGES: Final[dict[str, dict[str, str]]] = {
    "langgraph": {
        "version": "1.2.9",
        "license": "MIT",
    },
    "langgraph-checkpoint": {
        "version": "4.1.1",
        "license": "MIT",
    },
    "langgraph-checkpoint-sqlite": {
        "version": "3.1.1",
        "license": "MIT",
    },
    "sqlite-vec": {
        "version": "0.1.9",
        "license": "MIT License, Apache License, Version 2.0",
        "wheel_license_file_present": False,
    },
}

EFFECT_WITNESS_PRODUCER_VERSIONS: Final[tuple[str, ...]] = (
    "0.3.0",
    "0.3.1",
    "0.3.2",
    "0.3.3",
    "0.4.0",
)

SCENARIOS: Final[dict[str, dict[str, Any]]] = {
    "write_blind": {
        "policy": "blind",
        "tamper_before_resume": False,
        "tool_name": "write_file",
    },
    "edit_blind": {
        "policy": "blind",
        "tamper_before_resume": False,
        "tool_name": "edit_file",
    },
    "edit_reconcile": {
        "policy": "reconcile",
        "tamper_before_resume": False,
        "tool_name": "edit_file",
    },
    "edit_reconcile_tampered": {
        "policy": "reconcile",
        "tamper_before_resume": True,
        "tool_name": "edit_file",
    },
}
SCENARIO_ORDER: Final[tuple[str, ...]] = tuple(SCENARIOS)

EVIDENCE_BOUNDARY: Final[dict[str, bool]] = {
    "absolute_paths_included": False,
    "checkpoint_database_included": False,
    "checkpoint_shm_included": False,
    "checkpoint_wal_included": False,
    "environment_included": False,
    "event_journal_database_included": False,
    "fixture_content_included": False,
    "hostnames_included": False,
    "pids_included": False,
    "ports_included": False,
    "raw_checkpoint_rows_included": False,
    "raw_exception_messages_included": False,
    "raw_server_logs_included": False,
    "raw_tool_arguments_included": False,
    "raw_tool_responses_included": False,
    "raw_worker_stderr_included": False,
    "raw_worker_stdout_included": False,
    "timestamps_included": False,
}

BLOCKED_CLAIMS: Final[tuple[str, ...]] = (
    "exactly-once execution",
    "arbitrary LangGraph workflow correctness",
    "arbitrary MCP server correctness",
    "official MCP certification or conformance",
    "SQLite or checkpointer crash consistency",
    "production recovery or availability",
    "production filesystem behavior",
    "concurrency behavior",
    "distributed consistency",
    "reconciliation correctness beyond the registered byte-tree postcondition",
    "model-driven agent behavior",
    "long-context or long-term-memory behavior",
    "multi-agent behavior",
    "performance or scale",
    "security or vulnerability status",
    "source authenticity without an external trusted Git or release digest",
    "external adoption or review",
)

EVIDENCE_SCOPE: Final = (
    "exact LangGraph Functional API and SQLite checkpoint versions resuming "
    "registered official-filesystem MCP effects across separate Python processes"
)

WORKER_FAULT_EVENT_TYPES: Final[tuple[str, ...]] = (
    "WORKER_STARTED",
    "TASK_STARTED",
    "TOOL_SENT",
    "TOOL_OBSERVED",
    "MCP_CONTEXT_CLOSED",
    "FAULT_AFTER_EFFECT_BEFORE_TASK_RETURN",
)

WORKER_BLIND_RESUME_EVENT_TYPES: Final[tuple[str, ...]] = (
    "WORKER_STARTED",
    "TASK_STARTED",
    "TOOL_SENT",
    "TOOL_OBSERVED",
    "MCP_CONTEXT_CLOSED",
    "TASK_RETURNED",
)

WORKER_RECONCILE_RESUME_EVENT_TYPES: Final[dict[str, tuple[str, ...]]] = {
    "edit_reconcile": (
        "WORKER_STARTED",
        "TASK_STARTED",
        "COMMITTED_CONFIRMED",
    ),
    "edit_reconcile_tampered": (
        "WORKER_STARTED",
        "TASK_STARTED",
        "UNRESOLVED",
    ),
}
