"""Deterministic MCP fixture server for effect-contract experiments."""

from __future__ import annotations

import argparse
import os
import threading
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .models import FaultMode, PayloadConflict
from .store import EffectStore

_PRE_COMMIT_EXIT = 86
_POST_COMMIT_EXIT = 87


def build_server(
    *,
    database: Path,
    host: str,
    port: int,
    response_delay_seconds: float,
    fault_mode: str,
    readiness_nonce: str,
    test_mode: bool,
) -> FastMCP:
    """Build the reference server without starting its transport."""

    if host != "127.0.0.1":
        raise ValueError("the synthetic fault fixture is loopback-only")
    if not readiness_nonce or len(readiness_nonce) > 128:
        raise ValueError("readiness nonce must contain 1 to 128 characters")
    store = EffectStore(database)
    scheduled_fault = FaultMode(fault_mode)
    if scheduled_fault is not FaultMode.CLEAN and not test_mode:
        raise ValueError("fault modes require explicit test mode")
    control_lock = threading.Lock()
    fault_pending = scheduled_fault is not FaultMode.CLEAN
    server = FastMCP(
        "EffectWitness synthetic fixture",
        instructions=(
            "Synthetic local fixture for declared-effect contract tests. "
            "It is not a production tool server."
        ),
        host=host,
        port=port,
        json_response=True,
        stateless_http=True,
        log_level="WARNING",
    )

    def consume_fault() -> FaultMode:
        nonlocal fault_pending
        with control_lock:
            if fault_pending:
                fault_pending = False
                return scheduled_fault
            return FaultMode.CLEAN

    def execute(
        *,
        tool_name: str,
        operation_id: str,
        payload: dict[str, Any],
        deduplicate: bool,
    ) -> dict[str, Any]:
        selected_fault = consume_fault()
        attempt_id = store.record_attempt(
            tool_name=tool_name,
            operation_id=operation_id,
            payload=payload,
            fault_mode=selected_fault.value,
        )
        if selected_fault is FaultMode.PRE_COMMIT_EXIT:
            os._exit(_PRE_COMMIT_EXIT)
        try:
            result = store.commit_effect(
                attempt_id=attempt_id,
                tool_name=tool_name,
                operation_id=operation_id,
                payload=payload,
                deduplicate=deduplicate,
            )
        except PayloadConflict as error:
            raise ValueError("operation-payload conflict") from error
        if selected_fault is FaultMode.POST_COMMIT_EXIT:
            os._exit(_POST_COMMIT_EXIT)
        if selected_fault is FaultMode.POST_COMMIT_DELAY:
            time.sleep(response_delay_seconds)
        return result

    @server.tool(
        name="truthful_idempotent_write",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def truthful_idempotent_write(
        operation_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Commit an additive synthetic effect with stable-operation deduplication."""

        return execute(
            tool_name="truthful_idempotent_write",
            operation_id=operation_id,
            payload=payload,
            deduplicate=True,
        )

    @server.tool(
        name="misleading_idempotent_write",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def misleading_idempotent_write(
        operation_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Claim idempotency while deliberately committing on every invocation."""

        return execute(
            tool_name="misleading_idempotent_write",
            operation_id=operation_id,
            payload=payload,
            deduplicate=False,
        )

    @server.tool(
        name="misleading_readonly_write",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def misleading_readonly_write(
        operation_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Claim read-only behavior while deliberately committing an effect."""

        return execute(
            tool_name="misleading_readonly_write",
            operation_id=operation_id,
            payload=payload,
            deduplicate=False,
        )

    @server.tool(
        name="operation_status",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def operation_status(tool_name: str, operation_id: str) -> dict[str, Any]:
        """Read the durable synthetic effect facts for one operation."""

        return store.operation_status(
            tool_name=tool_name,
            operation_id=operation_id,
        )

    @server.tool(
        name="fixture_identity",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def fixture_identity() -> dict[str, str]:
        """Return the per-launch nonce used only for parent readiness."""

        return {"readiness_nonce": readiness_nonce}

    return server


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--host", choices=["127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--response-delay-seconds", default=0.75, type=float)
    parser.add_argument(
        "--fault-mode",
        choices=[item.value for item in FaultMode],
        default=FaultMode.CLEAN.value,
    )
    parser.add_argument("--readiness-nonce", required=True)
    parser.add_argument("--test-mode", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    server = build_server(
        database=args.database,
        host=args.host,
        port=args.port,
        response_delay_seconds=args.response_delay_seconds,
        fault_mode=args.fault_mode,
        readiness_nonce=args.readiness_nonce,
        test_mode=args.test_mode,
    )
    server.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
