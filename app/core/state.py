"""Deterministic system state machine for Agent 16 orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SystemState(str, Enum):
    """Stable system lifecycle states for orchestration runs."""

    INITIALIZED = "initialized"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    REFLECTING = "reflecting"
    IMPROVING = "improving"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[SystemState, set[SystemState]] = {
    SystemState.INITIALIZED: {SystemState.PLANNING, SystemState.FAILED},
    SystemState.PLANNING: {SystemState.EXECUTING, SystemState.FAILED},
    SystemState.EXECUTING: {SystemState.VALIDATING, SystemState.FAILED},
    SystemState.VALIDATING: {SystemState.REFLECTING, SystemState.FAILED},
    SystemState.REFLECTING: {SystemState.IMPROVING, SystemState.FAILED},
    SystemState.IMPROVING: {SystemState.COMPLETED, SystemState.FAILED},
    SystemState.COMPLETED: set(),
    SystemState.FAILED: set(),
}


class InvalidStateTransitionError(ValueError):
    """Raised when an invalid state transition is attempted."""


@dataclass(frozen=True)
class StateTransition:
    """Serializable transition record emitted by the state machine."""

    index: int
    from_state: SystemState
    to_state: SystemState
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation of this transition."""
        return {
            "index": self.index,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SystemStateSnapshot:
    """Serializable snapshot of a run's current state and history."""

    run_id: str
    trace_id: str
    current_state: SystemState
    transitions: list[StateTransition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation of the state snapshot."""
        return {
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "current_state": self.current_state.value,
            "transitions": [transition.to_dict() for transition in self.transitions],
        }


class SystemStateMachine:
    """Strict orchestration state machine with explicit transition validation."""

    def __init__(self, run_id: str, trace_id: str) -> None:
        self._run_id = run_id
        self._trace_id = trace_id
        self._state = SystemState.INITIALIZED
        self._transitions: list[StateTransition] = []

    @property
    def state(self) -> SystemState:
        """Return the current state."""
        return self._state

    @property
    def transitions(self) -> list[StateTransition]:
        """Return a copy of the transition history."""
        return list(self._transitions)

    def can_transition_to(self, new_state: SystemState) -> bool:
        """Return True when the requested transition is valid."""
        return new_state in _ALLOWED_TRANSITIONS[self._state]

    def transition_to(
        self,
        new_state: SystemState,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> StateTransition:
        """Advance the state machine to a valid next state."""
        if not self.can_transition_to(new_state):
            raise InvalidStateTransitionError(
                f"Invalid transition: {self._state.value} -> {new_state.value}"
            )

        transition = StateTransition(
            index=len(self._transitions) + 1,
            from_state=self._state,
            to_state=new_state,
            reason=reason,
            metadata=dict(metadata or {}),
        )
        self._transitions.append(transition)
        self._state = new_state
        return transition

    def snapshot(self) -> SystemStateSnapshot:
        """Return an immutable snapshot of the current machine state."""
        return SystemStateSnapshot(
            run_id=self._run_id,
            trace_id=self._trace_id,
            current_state=self._state,
            transitions=self.transitions,
        )