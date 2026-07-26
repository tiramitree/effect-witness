from __future__ import annotations

from effect_witness.journal import ClientJournal


def test_client_unknown_is_not_rewritten_as_success(tmp_path) -> None:
    journal = ClientJournal(tmp_path / "client.sqlite")
    journal.create_operation(
        scenario_id="s1",
        operation_id="op-1",
        payload={"value": 1},
        retry_budget=0,
    )
    journal.record_send(
        scenario_id="s1",
        attempt_id="a1",
        tool_name="tool",
        arguments={"operation_id": "op-1", "payload": {"value": 1}},
    )
    journal.record_observation(
        scenario_id="s1",
        attempt_id="a1",
        completed=False,
        is_error=None,
        exception_types=("ReadTimeout",),
        response=None,
    )

    snapshot = journal.snapshot()

    assert snapshot["client_operations"][0]["state"] == "UNKNOWN"
    assert snapshot["client_events"][-1]["event_type"] == "UNKNOWN"
    assert snapshot["client_events"][-1]["payload"]["response_sha256"] is None
