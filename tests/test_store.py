from __future__ import annotations

import concurrent.futures
import sqlite3

import pytest

import effect_witness.store as store_module
from effect_witness.models import PayloadConflict
from effect_witness.store import EffectStore


def _record_and_commit(
    store: EffectStore,
    *,
    attempt_id: str,
    tool_name: str,
    operation_id: str,
    payload: dict[str, object],
    deduplicate: bool,
) -> dict[str, object]:
    store.record_attempt(
        attempt_id=attempt_id,
        tool_name=tool_name,
        operation_id=operation_id,
        payload=payload,
        fault_mode="clean",
    )
    return store.commit_effect(
        attempt_id=attempt_id,
        tool_name=tool_name,
        operation_id=operation_id,
        payload=payload,
        deduplicate=deduplicate,
    )


def test_unsafe_control_commits_every_attempt(tmp_path) -> None:
    store = EffectStore(tmp_path / "effects.sqlite")
    first = _record_and_commit(
        store,
        attempt_id="a1",
        tool_name="unsafe",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=False,
    )
    second = _record_and_commit(
        store,
        attempt_id="a2",
        tool_name="unsafe",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=False,
    )

    status = store.operation_status(tool_name="unsafe", operation_id="op-1")
    assert first["effect_id"] != second["effect_id"]
    assert status["effect_count"] == 2


def test_stable_operation_returns_one_effect(tmp_path) -> None:
    store = EffectStore(tmp_path / "effects.sqlite")
    first = _record_and_commit(
        store,
        attempt_id="a1",
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=True,
    )
    second = _record_and_commit(
        store,
        attempt_id="a2",
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=True,
    )

    status = store.operation_status(tool_name="stable", operation_id="op-1")
    assert first["effect_id"] == second["effect_id"]
    assert second["deduplicated"] is True
    assert status["effect_count"] == 1


def test_stable_operation_rejects_payload_conflict(tmp_path) -> None:
    store = EffectStore(tmp_path / "effects.sqlite")
    _record_and_commit(
        store,
        attempt_id="a1",
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=True,
    )
    store.record_attempt(
        attempt_id="a2",
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 2},
        fault_mode="clean",
    )

    with pytest.raises(PayloadConflict):
        store.commit_effect(
            attempt_id="a2",
            tool_name="stable",
            operation_id="op-1",
            payload={"value": 2},
            deduplicate=True,
        )

    status = store.operation_status(tool_name="stable", operation_id="op-1")
    assert status["effect_count"] == 1
    assert status["attempts"][-1]["state"] == "PAYLOAD_CONFLICT"


def test_concurrent_stable_operation_is_atomic(tmp_path) -> None:
    store = EffectStore(tmp_path / "effects.sqlite")

    def invoke(index: int) -> dict[str, object]:
        return _record_and_commit(
            store,
            attempt_id=f"a{index:02d}",
            tool_name="stable",
            operation_id="op-1",
            payload={"value": 1},
            deduplicate=True,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(invoke, range(16)))

    status = store.operation_status(tool_name="stable", operation_id="op-1")
    assert len({result["effect_id"] for result in results}) == 1
    assert status["effect_count"] == 1
    assert len(status["attempts"]) == 16


def test_snapshot_has_no_local_path_or_wall_clock(tmp_path) -> None:
    store = EffectStore(tmp_path / "effects.sqlite")
    _record_and_commit(
        store,
        attempt_id="a1",
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=True,
    )

    snapshot = store.full_snapshot()

    assert set(snapshot) == {
        "attempts",
        "effects",
        "stable_operations",
        "audit_events",
    }
    assert "created_at" not in snapshot["attempts"][0]
    assert "path" not in snapshot["effects"][0]


def test_wal_transition_occurs_only_at_store_initialization(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements: list[str] = []
    real_connect = sqlite3.connect

    class RecordingConnection(sqlite3.Connection):
        def execute(self, sql: str, *args: object, **kwargs: object):
            statements.append(sql)
            return super().execute(sql, *args, **kwargs)

    def recording_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        kwargs["factory"] = RecordingConnection
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(store_module.sqlite3, "connect", recording_connect)
    store = EffectStore(tmp_path / "effects.sqlite")
    _record_and_commit(
        store,
        attempt_id="a1",
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=True,
    )
    store.operation_status(tool_name="stable", operation_id="op-1")

    assert statements.count("PRAGMA journal_mode=WAL") == 1
    assert statements.count("PRAGMA journal_mode") >= 1
