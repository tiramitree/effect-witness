"""Small exact-version MCP client used by the reproducible fixture scenarios."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Final

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# Normal observations must outlast the fixture store's five-second busy window.
# Registered transport faults always pass their shorter timeout explicitly.
NORMAL_MCP_TIMEOUT_SECONDS: Final = 10.0


@dataclass(frozen=True)
class CallObservation:
    """Normalized client observation with no host paths or exception messages."""

    completed: bool
    is_error: bool | None
    exception_types: tuple[str, ...]
    response: dict[str, Any] | None

    @property
    def succeeded(self) -> bool:
        return self.completed and self.is_error is False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _exception_types(error: BaseException) -> tuple[str, ...]:
    names = {type(error).__name__}
    nested = getattr(error, "exceptions", ())
    for child in nested:
        names.update(_exception_types(child))
    cause = error.__cause__
    if cause is not None:
        names.update(_exception_types(cause))
    return tuple(sorted(names))


async def _session(
    url: str,
    *,
    timeout_seconds: float,
) -> tuple[
    httpx.AsyncClient,
    Any,
]:
    timeout = httpx.Timeout(
        connect=max(timeout_seconds, 1.0),
        read=timeout_seconds,
        write=max(timeout_seconds, 1.0),
        pool=max(timeout_seconds, 1.0),
    )
    client = httpx.AsyncClient(timeout=timeout, trust_env=False)
    transport = streamable_http_client(
        url,
        http_client=client,
        terminate_on_close=False,
    )
    return client, transport


async def list_tools(
    url: str,
    *,
    timeout_seconds: float = NORMAL_MCP_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Return normalized MCP tool descriptors."""

    client, transport = await _session(url, timeout_seconds=timeout_seconds)
    try:
        async with (
            transport as (read_stream, write_stream, _),
            ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=timeout_seconds),
            ) as session,
        ):
            await session.initialize()
            response = await session.list_tools()
            return [
                tool.model_dump(mode="json", by_alias=True) for tool in response.tools
            ]
    finally:
        await client.aclose()


async def call_tool(
    url: str,
    *,
    name: str,
    arguments: dict[str, Any],
    timeout_seconds: float = NORMAL_MCP_TIMEOUT_SECONDS,
) -> CallObservation:
    """Call one MCP tool and normalize success or transport failure."""

    client, transport = await _session(url, timeout_seconds=timeout_seconds)
    try:
        try:
            async with (
                transport as (read_stream, write_stream, _),
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                ) as session,
            ):
                await session.initialize()
                response = await session.call_tool(
                    name,
                    arguments,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                )
                normalized = response.model_dump(mode="json", by_alias=True)
                return CallObservation(
                    completed=True,
                    is_error=bool(normalized.get("isError", False)),
                    exception_types=(),
                    response=normalized,
                )
        except Exception as error:
            return CallObservation(
                completed=False,
                is_error=None,
                exception_types=_exception_types(error),
                response=None,
            )
    finally:
        await client.aclose()


def list_tools_sync(
    url: str,
    *,
    timeout_seconds: float = NORMAL_MCP_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    return asyncio.run(list_tools(url, timeout_seconds=timeout_seconds))


def call_tool_sync(
    url: str,
    *,
    name: str,
    arguments: dict[str, Any],
    timeout_seconds: float = NORMAL_MCP_TIMEOUT_SECONDS,
) -> CallObservation:
    return asyncio.run(
        call_tool(
            url,
            name=name,
            arguments=arguments,
            timeout_seconds=timeout_seconds,
        )
    )
