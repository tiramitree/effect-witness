from __future__ import annotations

import socket

import pytest

from effect_witness.fixture_server import build_server
from effect_witness.mcp_client import list_tools_sync
from effect_witness.process import FixtureProcess


def test_direct_server_builder_rejects_non_loopback_host(tmp_path) -> None:
    non_loopback_host = ".".join(("0", "0", "0", "0"))
    with pytest.raises(ValueError, match="loopback-only"):
        build_server(
            database=tmp_path / "effects.sqlite",
            host=non_loopback_host,
            port=1,
            response_delay_seconds=0.1,
            fault_mode="clean",
            readiness_nonce="test",
            test_mode=True,
        )


def test_loopback_client_ignores_environment_proxies(tmp_path, monkeypatch) -> None:
    fixture = FixtureProcess(database=tmp_path / "effects.sqlite")
    with fixture:
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("no_proxy", "")
        tools = list_tools_sync(fixture.url)

    assert {tool["name"] for tool in tools} >= {
        "truthful_idempotent_write",
        "misleading_idempotent_write",
    }


def test_occupied_port_cannot_fake_fixture_readiness(tmp_path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = int(listener.getsockname()[1])
        fixture = FixtureProcess(
            database=tmp_path / "effects.sqlite",
            port=port,
        )
        with pytest.raises((RuntimeError, TimeoutError)):
            fixture.start(timeout_seconds=1.0)
        fixture.stop()
