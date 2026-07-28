"""Durable out-of-workspace decision journal for the schema-v5 lane."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .coding_registration import MUTATION_ACTION_SHA256, OPERATION_ID

_SCHEMA = """
CREATE TABLE IF NOT EXISTS coding_attempts (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    phase TEXT NOT NULL CHECK (phase IN ('initial', 'restart')),
    decision TEXT NOT NULL CHECK (
        decision IN ('EXECUTED', 'RECONCILED', 'UNRESOLVED')
    ),
    operation_id TEXT NOT NULL,
    action_sha256 TEXT NOT NULL,
    command_executed INTEGER NOT NULL CHECK (command_executed IN (0, 1)),
    returncode INTEGER,
    before_tree_sha256 TEXT NOT NULL,
    after_tree_sha256 TEXT NOT NULL,
    CHECK (
        (decision = 'EXECUTED' AND command_executed = 1 AND returncode IS NOT NULL)
        OR
        (
            decision = 'RECONCILED'
            AND command_executed = 0
            AND returncode = 0
        )
        OR
        (
            decision = 'UNRESOLVED'
            AND command_executed = 0
            AND returncode IS NULL
        )
    )
);
"""


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize_journal(path: Path) -> None:
    if path.exists():
        raise FileExistsError("coding journal must start absent")
    with _connect(path) as connection:
        connection.executescript(_SCHEMA)


def append_attempt(
    path: Path,
    *,
    phase: str,
    decision: str,
    command_executed: bool,
    returncode: int | None,
    before_tree_sha256: str,
    after_tree_sha256: str,
) -> None:
    with _connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO coding_attempts (
                phase,
                decision,
                operation_id,
                action_sha256,
                command_executed,
                returncode,
                before_tree_sha256,
                after_tree_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                phase,
                decision,
                OPERATION_ID,
                MUTATION_ACTION_SHA256,
                int(command_executed),
                returncode,
                before_tree_sha256,
                after_tree_sha256,
            ),
        )
        connection.commit()


def read_attempts(path: Path) -> list[dict[str, Any]]:
    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT
                sequence,
                phase,
                decision,
                operation_id,
                action_sha256,
                command_executed,
                returncode,
                before_tree_sha256,
                after_tree_sha256
            FROM coding_attempts
            ORDER BY sequence
            """
        ).fetchall()
    return [
        {
            "action_sha256": row["action_sha256"],
            "after_tree_sha256": row["after_tree_sha256"],
            "before_tree_sha256": row["before_tree_sha256"],
            "command_executed": bool(row["command_executed"]),
            "decision": row["decision"],
            "operation_id": row["operation_id"],
            "phase": row["phase"],
            "returncode": row["returncode"],
            "sequence": row["sequence"],
        }
        for row in rows
    ]


def has_one_registered_commit(
    path: Path,
    *,
    pre_tree_sha256: str,
    post_tree_sha256: str,
) -> bool:
    rows = read_attempts(path)
    return len(rows) == 1 and rows[0] == {
        "action_sha256": MUTATION_ACTION_SHA256,
        "after_tree_sha256": post_tree_sha256,
        "before_tree_sha256": pre_tree_sha256,
        "command_executed": True,
        "decision": "EXECUTED",
        "operation_id": OPERATION_ID,
        "phase": "initial",
        "returncode": 0,
        "sequence": 1,
    }
