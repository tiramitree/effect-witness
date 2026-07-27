"""SQLite-backed external effect witness.

Each method opens its own connection so concurrent tool calls exercise SQLite's
real transaction arbitration. The database represents server-side facts only;
client observations belong in a separate journal.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

from .models import (
    AttemptBindingError,
    AttemptStateError,
    PayloadConflict,
    canonical_json,
    sha256_json,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    fault_mode TEXT NOT NULL,
    state TEXT NOT NULL,
    received_seq INTEGER NOT NULL,
    terminal_seq INTEGER
);

CREATE TABLE IF NOT EXISTS effects (
    effect_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    attempt_id TEXT NOT NULL UNIQUE,
    commit_seq INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(attempt_id) REFERENCES attempts(attempt_id)
);

CREATE TABLE IF NOT EXISTS stable_operations (
    tool_name TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    effect_id INTEGER NOT NULL,
    PRIMARY KEY(tool_name, operation_id),
    FOREIGN KEY(effect_id) REFERENCES effects(effect_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    canonical_payload_sha256 TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_effects_operation
ON effects(tool_name, operation_id, effect_id);

CREATE INDEX IF NOT EXISTS idx_attempts_operation
ON attempts(tool_name, operation_id, received_seq);
"""

SQLITE_BUSY_TIMEOUT_SECONDS: Final = 5.0
_SQLITE_BUSY_TIMEOUT_MILLISECONDS: Final = int(SQLITE_BUSY_TIMEOUT_SECONDS * 1000)


class EffectStore:
    """Durable server-side witness for synthetic externally visible effects."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection(initialize=True) as connection:
            connection.executescript(_SCHEMA)

    def _open(self, *, initialize: bool = False) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            isolation_level=None,
            timeout=SQLITE_BUSY_TIMEOUT_SECONDS,
        )
        connection.row_factory = sqlite3.Row
        try:
            if initialize:
                journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[
                    0
                ]
            else:
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            connection.execute("PRAGMA synchronous=FULL")
            synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MILLISECONDS}"
            )
            if str(journal_mode).lower() != "wal" or int(synchronous) != 2:
                raise RuntimeError("SQLite WAL/FULL durability mode unavailable")
        except Exception:
            connection.close()
            raise
        return connection

    @contextmanager
    def _connection(
        self,
        *,
        initialize: bool = False,
    ) -> Iterator[sqlite3.Connection]:
        connection = self._open(initialize=initialize)
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: Any,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO audit_events (
                entity_type,
                entity_id,
                event_type,
                canonical_payload_sha256
            ) VALUES (?, ?, ?, ?)
            """,
            (entity_type, entity_id, event_type, sha256_json(payload)),
        )
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)

    def record_attempt(
        self,
        *,
        tool_name: str,
        operation_id: str,
        payload: Any,
        fault_mode: str,
        attempt_id: str | None = None,
    ) -> str:
        """Persist request receipt before any effect can occur."""

        payload_hash = sha256_json(payload)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            sequence = self._append_event(
                connection,
                entity_type="attempt",
                entity_id=attempt_id or "pending",
                event_type="RECEIVED",
                payload={
                    "tool_name": tool_name,
                    "operation_id": operation_id,
                    "payload_sha256": payload_hash,
                    "fault_mode": fault_mode,
                },
            )
            if attempt_id is None:
                attempt_id = f"a{sequence:06d}"
                connection.execute(
                    "UPDATE audit_events SET entity_id = ? WHERE seq = ?",
                    (attempt_id, sequence),
                )
            connection.execute(
                """
                INSERT INTO attempts (
                    attempt_id,
                    tool_name,
                    operation_id,
                    payload_sha256,
                    fault_mode,
                    state,
                    received_seq
                ) VALUES (?, ?, ?, ?, ?, 'RECEIVED', ?)
                """,
                (
                    attempt_id,
                    tool_name,
                    operation_id,
                    payload_hash,
                    fault_mode,
                    sequence,
                ),
            )
            connection.commit()
            return attempt_id

    def mark_precommit_abort(self, attempt_id: str) -> None:
        """Mark a controlled pre-commit failure that did not kill the process."""

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = connection.execute(
                "SELECT state FROM attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if attempt is None:
                connection.rollback()
                raise KeyError("unknown attempt")
            if attempt["state"] != "RECEIVED":
                connection.rollback()
                raise AttemptStateError("attempt is not in RECEIVED state")
            sequence = self._append_event(
                connection,
                entity_type="attempt",
                entity_id=attempt_id,
                event_type="ABORTED_PRECOMMIT",
                payload={"attempt_id": attempt_id},
            )
            cursor = connection.execute(
                """
                UPDATE attempts
                SET state = 'ABORTED_PRECOMMIT', terminal_seq = ?
                WHERE attempt_id = ? AND state = 'RECEIVED'
                """,
                (sequence, attempt_id),
            )
            if cursor.rowcount != 1:
                raise AttemptStateError("attempt state changed")
            connection.commit()

    def commit_effect(
        self,
        *,
        attempt_id: str,
        tool_name: str,
        operation_id: str,
        payload: Any,
        deduplicate: bool,
    ) -> dict[str, Any]:
        """Commit one effect or return the stable prior result atomically."""

        payload_hash = sha256_json(payload)
        payload_json = canonical_json(payload)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = connection.execute(
                """
                SELECT tool_name, operation_id, payload_sha256, state
                FROM attempts
                WHERE attempt_id = ?
                """,
                (attempt_id,),
            ).fetchone()
            if attempt is None:
                connection.rollback()
                raise KeyError("unknown attempt")
            if (
                attempt["tool_name"] != tool_name
                or attempt["operation_id"] != operation_id
            ):
                connection.rollback()
                raise AttemptBindingError(
                    "attempt is bound to another tool or operation"
                )
            if attempt["payload_sha256"] != payload_hash:
                connection.rollback()
                raise PayloadConflict("attempt payload changed")
            if attempt["state"] != "RECEIVED":
                connection.rollback()
                raise AttemptStateError("attempt is not in RECEIVED state")

            if deduplicate:
                existing = connection.execute(
                    """
                    SELECT
                        stable_operations.payload_sha256,
                        effects.effect_id,
                        effects.result_json,
                        effects.commit_seq
                    FROM stable_operations
                    JOIN effects
                      ON effects.effect_id = stable_operations.effect_id
                    WHERE stable_operations.tool_name = ?
                      AND stable_operations.operation_id = ?
                    """,
                    (tool_name, operation_id),
                ).fetchone()
                if existing is not None:
                    if existing["payload_sha256"] != payload_hash:
                        sequence = self._append_event(
                            connection,
                            entity_type="attempt",
                            entity_id=attempt_id,
                            event_type="PAYLOAD_CONFLICT",
                            payload={
                                "tool_name": tool_name,
                                "operation_id": operation_id,
                                "payload_sha256": payload_hash,
                            },
                        )
                        cursor = connection.execute(
                            """
                            UPDATE attempts
                            SET state = 'PAYLOAD_CONFLICT', terminal_seq = ?
                            WHERE attempt_id = ? AND state = 'RECEIVED'
                            """,
                            (sequence, attempt_id),
                        )
                        if cursor.rowcount != 1:
                            raise AttemptStateError("attempt state changed")
                        connection.commit()
                        raise PayloadConflict(
                            "operation identifier is bound to another payload"
                        )
                    sequence = self._append_event(
                        connection,
                        entity_type="attempt",
                        entity_id=attempt_id,
                        event_type="DEDUP_HIT",
                        payload={
                            "effect_id": existing["effect_id"],
                            "operation_id": operation_id,
                        },
                    )
                    cursor = connection.execute(
                        """
                        UPDATE attempts
                        SET state = 'DEDUP_HIT', terminal_seq = ?
                        WHERE attempt_id = ? AND state = 'RECEIVED'
                        """,
                        (sequence, attempt_id),
                    )
                    if cursor.rowcount != 1:
                        raise AttemptStateError("attempt state changed")
                    connection.commit()
                    result = json.loads(existing["result_json"])
                    result["deduplicated"] = True
                    return result

            placeholder = {
                "deduplicated": False,
                "operation_id": operation_id,
                "payload_sha256": payload_hash,
                "tool_name": tool_name,
            }
            cursor = connection.execute(
                """
                INSERT INTO effects (
                    tool_name,
                    operation_id,
                    payload_sha256,
                    payload_json,
                    result_json,
                    attempt_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_name,
                    operation_id,
                    payload_hash,
                    payload_json,
                    canonical_json(placeholder),
                    attempt_id,
                ),
            )
            assert cursor.lastrowid is not None
            effect_id = int(cursor.lastrowid)
            result = {
                **placeholder,
                "effect_id": effect_id,
            }
            result_json = canonical_json(result)
            sequence = self._append_event(
                connection,
                entity_type="effect",
                entity_id=str(effect_id),
                event_type="COMMITTED",
                payload=result,
            )
            connection.execute(
                """
                UPDATE effects
                SET result_json = ?, commit_seq = ?
                WHERE effect_id = ?
                """,
                (result_json, sequence, effect_id),
            )
            if deduplicate:
                connection.execute(
                    """
                    INSERT INTO stable_operations (
                        tool_name,
                        operation_id,
                        payload_sha256,
                        effect_id
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (tool_name, operation_id, payload_hash, effect_id),
                )
            cursor = connection.execute(
                """
                UPDATE attempts
                SET state = 'EFFECT_COMMITTED', terminal_seq = ?
                WHERE attempt_id = ? AND state = 'RECEIVED'
                """,
                (sequence, attempt_id),
            )
            if cursor.rowcount != 1:
                raise AttemptStateError("attempt state changed")
            connection.commit()
            return result

    def operation_status(
        self,
        *,
        tool_name: str,
        operation_id: str,
    ) -> dict[str, Any]:
        """Return server facts without mutating effect state."""

        with self._connection() as connection:
            connection.execute("BEGIN")
            effects = connection.execute(
                """
                SELECT
                    effect_id,
                    payload_sha256,
                    result_json,
                    attempt_id,
                    commit_seq
                FROM effects
                WHERE tool_name = ? AND operation_id = ?
                ORDER BY effect_id
                """,
                (tool_name, operation_id),
            ).fetchall()
            attempts = connection.execute(
                """
                SELECT
                    attempt_id,
                    payload_sha256,
                    fault_mode,
                    state,
                    received_seq,
                    terminal_seq
                FROM attempts
                WHERE tool_name = ? AND operation_id = ?
                ORDER BY received_seq, attempt_id
                """,
                (tool_name, operation_id),
            ).fetchall()
            connection.commit()
        return {
            "effect_count": len(effects),
            "effects": [
                {
                    "attempt_id": row["attempt_id"],
                    "commit_seq": row["commit_seq"],
                    "effect_id": row["effect_id"],
                    "payload_sha256": row["payload_sha256"],
                    "result": json.loads(row["result_json"]),
                }
                for row in effects
            ],
            "operation_id": operation_id,
            "attempts": [dict(row) for row in attempts],
            "tool_name": tool_name,
        }

    def full_snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Export normalized database facts without local paths or timestamps."""

        tables = {
            "attempts": ("SELECT * FROM attempts ORDER BY received_seq, attempt_id"),
            "effects": "SELECT * FROM effects ORDER BY effect_id",
            "stable_operations": (
                "SELECT * FROM stable_operations ORDER BY tool_name, operation_id"
            ),
            "audit_events": "SELECT * FROM audit_events ORDER BY seq",
        }
        with self._connection() as connection:
            connection.execute("BEGIN")
            snapshot = {
                name: [dict(row) for row in connection.execute(query).fetchall()]
                for name, query in tables.items()
            }
            connection.commit()
            return snapshot
