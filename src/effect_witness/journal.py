"""Client-owned SQLite journal, intentionally separate from server effect facts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import canonical_json, sha256_json

_SCHEMA = """
CREATE TABLE IF NOT EXISTS client_operations (
    scenario_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    retry_budget INTEGER NOT NULL,
    attempts_used INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL,
    attempt_id TEXT,
    event_type TEXT NOT NULL,
    canonical_payload_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(scenario_id) REFERENCES client_operations(scenario_id)
);
"""


class ClientJournal:
    """Persist exactly what the client knew and decided."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(_SCHEMA)

    def _open(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            isolation_level=None,
            timeout=5.0,
        )
        connection.row_factory = sqlite3.Row
        try:
            journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            connection.execute("PRAGMA synchronous=FULL")
            synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            if str(journal_mode).lower() != "wal" or int(synchronous) != 2:
                raise RuntimeError("SQLite WAL/FULL durability mode unavailable")
        except Exception:
            connection.close()
            raise
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _append(
        connection: sqlite3.Connection,
        *,
        scenario_id: str,
        attempt_id: str | None,
        event_type: str,
        payload: Any,
    ) -> None:
        connection.execute(
            """
            INSERT INTO client_events (
                scenario_id,
                attempt_id,
                event_type,
                canonical_payload_sha256,
                payload_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                attempt_id,
                event_type,
                sha256_json(payload),
                canonical_json(payload),
            ),
        )

    def create_operation(
        self,
        *,
        scenario_id: str,
        operation_id: str,
        payload: Any,
        retry_budget: int,
    ) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO client_operations (
                    scenario_id,
                    operation_id,
                    payload_sha256,
                    retry_budget,
                    state
                ) VALUES (?, ?, ?, ?, 'NEW')
                """,
                (
                    scenario_id,
                    operation_id,
                    sha256_json(payload),
                    retry_budget,
                ),
            )
            self._append(
                connection,
                scenario_id=scenario_id,
                attempt_id=None,
                event_type="OPERATION_CREATED",
                payload={
                    "operation_id": operation_id,
                    "payload_sha256": sha256_json(payload),
                    "retry_budget": retry_budget,
                },
            )
            connection.commit()

    def record_send(
        self,
        *,
        scenario_id: str,
        attempt_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            operation = connection.execute(
                """
                SELECT attempts_used, retry_budget
                FROM client_operations
                WHERE scenario_id = ?
                """,
                (scenario_id,),
            ).fetchone()
            if operation is None:
                connection.rollback()
                raise KeyError("unknown scenario")
            if operation["attempts_used"] >= operation["retry_budget"] + 1:
                connection.rollback()
                raise RuntimeError("retry budget exhausted")
            connection.execute(
                """
                UPDATE client_operations
                SET attempts_used = attempts_used + 1, state = 'SENT'
                WHERE scenario_id = ?
                """,
                (scenario_id,),
            )
            self._append(
                connection,
                scenario_id=scenario_id,
                attempt_id=attempt_id,
                event_type="SENT",
                payload={
                    "arguments_sha256": sha256_json(arguments),
                    "attempt_id": attempt_id,
                    "tool_name": tool_name,
                },
            )
            connection.commit()

    def record_observation(
        self,
        *,
        scenario_id: str,
        attempt_id: str,
        completed: bool,
        is_error: bool | None,
        exception_types: tuple[str, ...],
        response: dict[str, Any] | None,
    ) -> None:
        if not completed:
            state = "UNKNOWN"
        elif is_error is True:
            state = "ERROR_RESPONSE"
        else:
            state = "RECEIVED"
        payload = {
            "completed": completed,
            "is_error": is_error,
            "exception_types": list(exception_types),
            "response_sha256": sha256_json(response) if response is not None else None,
        }
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE client_operations
                SET state = ?
                WHERE scenario_id = ?
                """,
                (state, scenario_id),
            )
            self._append(
                connection,
                scenario_id=scenario_id,
                attempt_id=attempt_id,
                event_type=state,
                payload=payload,
            )
            connection.commit()

    def record_reconciliation(
        self,
        *,
        scenario_id: str,
        completed: bool,
        is_error: bool | None,
        exception_types: tuple[str, ...],
        response: dict[str, Any] | None,
    ) -> None:
        """Record a status query without consuming the write retry budget."""

        payload = {
            "completed": completed,
            "is_error": is_error,
            "exception_types": list(exception_types),
            "response_sha256": sha256_json(response) if response is not None else None,
        }
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._append(
                connection,
                scenario_id=scenario_id,
                attempt_id=None,
                event_type="RECONCILIATION_OBSERVED",
                payload=payload,
            )
            connection.commit()

    def record_decision(
        self,
        *,
        scenario_id: str,
        event_type: str,
        state: str,
        payload: Any,
    ) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE client_operations
                SET state = ?
                WHERE scenario_id = ?
                """,
                (state, scenario_id),
            )
            self._append(
                connection,
                scenario_id=scenario_id,
                attempt_id=None,
                event_type=event_type,
                payload=payload,
            )
            connection.commit()

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        with self._connection() as connection:
            connection.execute("BEGIN")
            operations = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM client_operations ORDER BY scenario_id"
                ).fetchall()
            ]
            events = [
                {
                    **dict(row),
                    "payload": json.loads(row["payload_json"]),
                }
                for row in connection.execute(
                    """
                    SELECT * FROM client_events
                    ORDER BY seq
                    """
                ).fetchall()
            ]
            connection.commit()
        for event in events:
            del event["payload_json"]
        return {
            "client_operations": operations,
            "client_events": events,
        }
