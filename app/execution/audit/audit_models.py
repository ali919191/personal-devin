"""Structured models used by the execution audit logging layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ExecutionRecordStatus = Literal["success", "failure"]


@dataclass(frozen=True)
class ExecutionError:
    """Normalized error payload stored in execution audit records."""

    type: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "message": self.message,
        }


@dataclass(frozen=True)
class ExecutionRecord:
    """Append-only execution audit record."""

    id: str
    timestamp: str
    input: dict[str, Any]
    output: Any
    status: ExecutionRecordStatus
    error: ExecutionError | None = None
    schema_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "timestamp": self.timestamp,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "error": self.error.to_dict() if self.error is not None else None,
        }
