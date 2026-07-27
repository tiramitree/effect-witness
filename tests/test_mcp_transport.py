from __future__ import annotations

import inspect

import effect_witness.mcp_client as mcp_client
from effect_witness.mcp_client import (
    NORMAL_MCP_TIMEOUT_SECONDS,
    call_tool_sync,
    list_tools_sync,
)
from effect_witness.process import FixtureProcess
from effect_witness.store import EffectStore


def _arguments(*, value: int = 1) -> dict[str, object]:
    return {"operation_id": "op-1", "payload": {"value": value}}


def _structured(response: dict[str, object] | None) -> dict[str, object]:
    assert response is not None
    value = response.get("structuredContent")
    if value is None:
        value = response.get("structured_content")
    assert isinstance(value, dict)
    return value


def test_normal_timeout_is_shared_by_async_and_sync_clients() -> None:
    assert NORMAL_MCP_TIMEOUT_SECONDS > 5.0
    for client in (
        mcp_client.list_tools,
        mcp_client.call_tool,
        mcp_client.list_tools_sync,
        mcp_client.call_tool_sync,
    ):
        assert (
            inspect.signature(client).parameters["timeout_seconds"].default
            == NORMAL_MCP_TIMEOUT_SECONDS
        )


def test_annotations_are_visible_over_streamable_http(tmp_path) -> None:
    fixture = FixtureProcess(database=tmp_path / "effects.sqlite")
    with fixture:
        tools = {tool["name"]: tool for tool in list_tools_sync(fixture.url)}

    assert tools["truthful_idempotent_write"]["annotations"] == {
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
        "readOnlyHint": False,
        "title": None,
    }
    assert tools["misleading_readonly_write"]["annotations"]["readOnlyHint"] is True
    for name in (
        "truthful_idempotent_write",
        "misleading_idempotent_write",
        "misleading_readonly_write",
    ):
        properties = tools[name]["inputSchema"]["properties"]
        assert "attempt_id" not in properties
        assert "fault_mode" not in properties


def test_post_commit_delay_is_transport_ambiguous_but_durable(tmp_path) -> None:
    database = tmp_path / "effects.sqlite"
    fixture = FixtureProcess(
        database=database,
        response_delay_seconds=0.75,
        fault_mode="post_commit_delay",
    )
    with fixture:
        precondition = call_tool_sync(
            fixture.url,
            name="fixture_identity",
            arguments={},
            timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
        )
        assert precondition.succeeded is True
        observation = call_tool_sync(
            fixture.url,
            name="truthful_idempotent_write",
            arguments=_arguments(),
            timeout_seconds=0.15,
        )
        assert observation.completed is False
        transport_ready = call_tool_sync(
            fixture.url,
            name="fixture_identity",
            arguments={},
            timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
        )
        assert transport_ready.succeeded is True
        status_call = call_tool_sync(
            fixture.url,
            name="operation_status",
            arguments={
                "tool_name": "truthful_idempotent_write",
                "operation_id": "op-1",
            },
            timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
        )

    status = _structured(status_call.response)
    assert status["effect_count"] == 1
    assert len(status["attempts"]) == 1
    assert status["attempts"][0]["fault_mode"] == "post_commit_delay"


def test_blind_retry_exposes_misleading_idempotent_hint(tmp_path) -> None:
    database = tmp_path / "effects.sqlite"
    fixture = FixtureProcess(
        database=database,
        response_delay_seconds=0.75,
        fault_mode="post_commit_delay",
    )
    with fixture:
        first = call_tool_sync(
            fixture.url,
            name="misleading_idempotent_write",
            arguments=_arguments(),
            timeout_seconds=0.15,
        )
        assert first.completed is False
        transport_ready = call_tool_sync(
            fixture.url,
            name="fixture_identity",
            arguments={},
            timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
        )
        assert transport_ready.succeeded is True
        second = call_tool_sync(
            fixture.url,
            name="misleading_idempotent_write",
            arguments=_arguments(),
            timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
        )
        assert second.succeeded is True
        status_call = call_tool_sync(
            fixture.url,
            name="operation_status",
            arguments={
                "tool_name": "misleading_idempotent_write",
                "operation_id": "op-1",
            },
            timeout_seconds=NORMAL_MCP_TIMEOUT_SECONDS,
        )

    status = _structured(status_call.response)
    assert status["effect_count"] == 2
    assert len(status["attempts"]) == 2
    assert [attempt["fault_mode"] for attempt in status["attempts"]] == [
        "post_commit_delay",
        "clean",
    ]


def test_post_commit_process_exit_survives_restart(tmp_path) -> None:
    database = tmp_path / "effects.sqlite"
    fixture = FixtureProcess(database=database, fault_mode="post_commit_exit")
    fixture.start()
    try:
        observation = call_tool_sync(
            fixture.url,
            name="truthful_idempotent_write",
            arguments=_arguments(),
        )
        assert observation.completed is False
        assert fixture.wait() == 87
        offline = EffectStore(database).operation_status(
            tool_name="truthful_idempotent_write",
            operation_id="op-1",
        )
        assert offline["effect_count"] == 1

        fixture.fault_mode = "clean"
        fixture.start()
        status_call = call_tool_sync(
            fixture.url,
            name="operation_status",
            arguments={
                "tool_name": "truthful_idempotent_write",
                "operation_id": "op-1",
            },
        )
        status = _structured(status_call.response)
        assert status["effect_count"] == 1
    finally:
        fixture.stop()


def test_precommit_process_exit_has_no_effect(tmp_path) -> None:
    database = tmp_path / "effects.sqlite"
    fixture = FixtureProcess(database=database, fault_mode="pre_commit_exit")
    fixture.start()
    try:
        observation = call_tool_sync(
            fixture.url,
            name="truthful_idempotent_write",
            arguments=_arguments(),
        )
        assert observation.completed is False
        assert fixture.wait() == 86
    finally:
        fixture.stop()

    status = EffectStore(database).operation_status(
        tool_name="truthful_idempotent_write",
        operation_id="op-1",
    )
    assert status["effect_count"] == 0
    assert status["attempts"][0]["state"] == "RECEIVED"


def test_mcp_error_response_is_not_classified_as_success(tmp_path) -> None:
    database = tmp_path / "effects.sqlite"
    fixture = FixtureProcess(database=database)
    with fixture:
        first = call_tool_sync(
            fixture.url,
            name="truthful_idempotent_write",
            arguments=_arguments(value=1),
        )
        conflict = call_tool_sync(
            fixture.url,
            name="truthful_idempotent_write",
            arguments=_arguments(value=2),
        )
        status_call = call_tool_sync(
            fixture.url,
            name="operation_status",
            arguments={
                "tool_name": "truthful_idempotent_write",
                "operation_id": "op-1",
            },
        )

    status = _structured(status_call.response)
    assert first.succeeded is True
    assert conflict.completed is True
    assert conflict.is_error is True
    assert conflict.succeeded is False
    assert status["effect_count"] == 1
    assert status["attempts"][-1]["state"] == "PAYLOAD_CONFLICT"
