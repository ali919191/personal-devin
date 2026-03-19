"""Structured models used by the execution audit logging layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ExecutionRecordStatus = Literal["success", "failure"]


@dataclass(frozen=True)
class ExecutionRecord:
    """Append-only execution audit record."""

    id: str
    timestamp: str
    input: dict[str, Any]
    output: Any
    status: ExecutionRecordStatus
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "error": self.error,
        }
