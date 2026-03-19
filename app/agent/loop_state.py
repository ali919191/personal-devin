"""Immutable state records for deterministic agent loop execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum


class LoopStep(str, Enum):
    """Supported deterministic loop phases."""

    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    REFLECT = "REFLECT"


class LoopStatus(str, Enum):
    """Allowed loop state lifecycle markers."""

    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"


def utc_timestamp(now_fn: Callable[[], datetime] | None = None) -> str:
    """Return a standardized UTC timestamp in ISO 8601 form."""
    now_fn = now_fn or (lambda: datetime.now(UTC))
    return now_fn().isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class LoopState:
    """Immutable state snapshot for one loop-step attempt."""

    iteration_id: str
    step: LoopStep
    status: LoopStatus
    attempt: int
    timestamp: str
