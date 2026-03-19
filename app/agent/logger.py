"""Structured logger for agent loop step events."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.agent.loop_state import LoopStatus, LoopStep


def _utc_timestamp(now_fn: Callable[[], datetime] | None = None) -> str:
    now_fn = now_fn or (lambda: datetime.now(UTC))
    return now_fn().isoformat().replace("+00:00", "Z")


class LoopLogger:
    """Collects deterministic, structured loop logs as dictionaries."""

    def __init__(
        self,
        sink: Callable[[dict[str, Any]], None] | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._entries: list[dict[str, Any]] = []
        self._sink = sink
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

    @property
    def entries(self) -> tuple[dict[str, Any], ...]:
        """Return immutable view of current log entries."""
        return tuple(self._entries)

    def emit_step(
        self,
        *,
        iteration_id: str,
        step: LoopStep,
        status: LoopStatus,
        duration_ms: int,
        error_type: str | None = None,
        attempt: int = 1,
    ) -> dict[str, Any]:
        """Append and optionally forward a structured step log entry."""
        entry: dict[str, Any] = {
            "timestamp": _utc_timestamp(self._now_fn),
            "iteration_id": iteration_id,
            "step": step.value,
            "status": status.value,
            "attempt": attempt,
            "duration_ms": duration_ms,
            "error_type": error_type,
        }
        self._entries.append(entry)
        if self._sink is not None:
            self._sink(dict(entry))
        return entry
