"""Cross-platform lifecycle control for the isolated MCP fixture process."""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import IO


def reserve_loopback_port() -> int:
    """Ask the OS for an unused loopback TCP port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


class FixtureProcess:
    """Start, observe, stop, and restart the deterministic fixture."""

    def __init__(
        self,
        *,
        database: Path,
        port: int | None = None,
        response_delay_seconds: float = 0.75,
        fault_mode: str = "clean",
        log_file: Path | None = None,
    ) -> None:
        self.database = Path(database)
        self.port = port if port is not None else reserve_loopback_port()
        self.response_delay_seconds = response_delay_seconds
        self.fault_mode = fault_mode
        self.log_file = Path(log_file) if log_file is not None else None
        self.process: subprocess.Popen[bytes] | None = None
        self._log_handle: IO[bytes] | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"

    @staticmethod
    def _structured(response: dict[str, object] | None) -> dict[str, object] | None:
        if response is None:
            return None
        value = response.get("structuredContent")
        if value is None:
            value = response.get("structured_content")
        return value if isinstance(value, dict) else None

    def start(self, *, timeout_seconds: float = 10.0) -> None:
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError("fixture is already running")
        readiness_nonce = secrets.token_hex(16)
        command = [
            sys.executable,
            "-m",
            "effect_witness.fixture_server",
            "--database",
            str(self.database),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--response-delay-seconds",
            str(self.response_delay_seconds),
            "--fault-mode",
            self.fault_mode,
            "--readiness-nonce",
            readiness_nonce,
            "--test-mode",
        ]
        if self.log_file is None:
            stdout: int | IO[bytes] = subprocess.DEVNULL
        else:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = self.log_file.open("ab")
            stdout = self._log_handle
        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NO_WINDOW
        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
        except OSError:
            self._close_log()
            raise
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            exit_code = self.process.poll()
            if exit_code is not None:
                self._close_log()
                raise RuntimeError(
                    f"fixture exited before readiness with code {exit_code}"
                )
            from .mcp_client import call_tool_sync

            observation = call_tool_sync(
                self.url,
                name="fixture_identity",
                arguments={},
                timeout_seconds=0.25,
            )
            if observation.succeeded:
                structured = self._structured(observation.response)
                if structured == {"readiness_nonce": readiness_nonce}:
                    return
            time.sleep(0.05)
        self.stop()
        raise TimeoutError("fixture readiness timeout")

    def wait(self, *, timeout_seconds: float = 5.0) -> int:
        if self.process is None:
            raise RuntimeError("fixture has not been started")
        exit_code = self.process.wait(timeout=timeout_seconds)
        self._close_log()
        return int(exit_code)

    def stop(self) -> None:
        if self.process is None:
            self._close_log()
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5.0)
        self._close_log()

    def restart(
        self,
        *,
        timeout_seconds: float = 10.0,
        fault_mode: str | None = None,
    ) -> None:
        self.stop()
        if fault_mode is not None:
            self.fault_mode = fault_mode
        self.start(timeout_seconds=timeout_seconds)

    def _close_log(self) -> None:
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def __enter__(self) -> FixtureProcess:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
