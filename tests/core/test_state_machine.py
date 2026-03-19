"""Tests for Agent 16 state machine."""

import pytest

from app.core.state import (
    InvalidStateTransitionError,
    SystemState,
    SystemStateMachine,
)


def test_valid_state_progression_reaches_completed() -> None:
    machine = SystemStateMachine(run_id="run-001", trace_id="trace-run-001")

    machine.transition_to(SystemState.PLANNING)
    machine.transition_to(SystemState.EXECUTING)
    machine.transition_to(SystemState.VALIDATING)
    machine.transition_to(SystemState.REFLECTING)
    machine.transition_to(SystemState.IMPROVING)
    machine.transition_to(SystemState.COMPLETED)

    assert machine.state == SystemState.COMPLETED
    assert [t.to_state for t in machine.transitions] == [
        SystemState.PLANNING,
        SystemState.EXECUTING,
        SystemState.VALIDATING,
        SystemState.REFLECTING,
        SystemState.IMPROVING,
        SystemState.COMPLETED,
    ]


def test_invalid_transition_is_rejected() -> None:
    machine = SystemStateMachine(run_id="run-002", trace_id="trace-run-002")

    with pytest.raises(InvalidStateTransitionError):
        machine.transition_to(SystemState.EXECUTING)


def test_failure_transition_is_allowed_from_active_state() -> None:
    machine = SystemStateMachine(run_id="run-003", trace_id="trace-run-003")

    machine.transition_to(SystemState.PLANNING)
    machine.transition_to(SystemState.FAILED, reason="planning_failed")

    assert machine.state == SystemState.FAILED
    assert machine.transitions[-1].reason == "planning_failed"


def test_terminal_state_rejects_future_transitions() -> None:
    machine = SystemStateMachine(run_id="run-004", trace_id="trace-run-004")

    machine.transition_to(SystemState.PLANNING)
    machine.transition_to(SystemState.EXECUTING)
    machine.transition_to(SystemState.VALIDATING)
    machine.transition_to(SystemState.REFLECTING)
    machine.transition_to(SystemState.IMPROVING)
    machine.transition_to(SystemState.COMPLETED)

    with pytest.raises(InvalidStateTransitionError):
        machine.transition_to(SystemState.FAILED)


def test_snapshot_is_serializable() -> None:
    machine = SystemStateMachine(run_id="run-005", trace_id="trace-run-005")
    machine.transition_to(SystemState.PLANNING, metadata={"phase": "planning"})

    snapshot = machine.snapshot().to_dict()

    assert snapshot["run_id"] == "run-005"
    assert snapshot["trace_id"] == "trace-run-005"
    assert snapshot["current_state"] == "planning"
    assert snapshot["transitions"][0]["metadata"] == {"phase": "planning"}