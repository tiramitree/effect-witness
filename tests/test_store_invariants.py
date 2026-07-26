from __future__ import annotations

import pytest

from effect_witness.models import AttemptBindingError, AttemptStateError
from effect_witness.store import EffectStore


def test_attempt_cannot_be_rebound_or_committed_twice(tmp_path) -> None:
    store = EffectStore(tmp_path / "effects.sqlite")
    attempt_id = store.record_attempt(
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        fault_mode="clean",
    )

    with pytest.raises(AttemptBindingError):
        store.commit_effect(
            attempt_id=attempt_id,
            tool_name="other",
            operation_id="op-1",
            payload={"value": 1},
            deduplicate=False,
        )

    first = store.commit_effect(
        attempt_id=attempt_id,
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=False,
    )
    with pytest.raises(AttemptStateError):
        store.commit_effect(
            attempt_id=attempt_id,
            tool_name="stable",
            operation_id="op-1",
            payload={"value": 1},
            deduplicate=False,
        )

    status = store.operation_status(tool_name="stable", operation_id="op-1")
    assert first["effect_id"] == 1
    assert status["effect_count"] == 1
    assert status["attempts"][0]["state"] == "EFFECT_COMMITTED"


def test_server_generated_attempt_ids_remain_unique_after_prior_audit_events(
    tmp_path,
) -> None:
    store = EffectStore(tmp_path / "effects.sqlite")
    first = store.record_attempt(
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        fault_mode="clean",
    )
    store.commit_effect(
        attempt_id=first,
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        deduplicate=True,
    )
    second = store.record_attempt(
        tool_name="stable",
        operation_id="op-1",
        payload={"value": 1},
        fault_mode="clean",
    )

    assert first != second
    assert first.startswith("a")
    assert second.startswith("a")
