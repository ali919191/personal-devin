"""Typed memory models for Agent 04 memory subsystem."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

MemoryType = Literal["execution", "task", "failure", "decision"]


class MemoryRecord(BaseModel):
    """Base memory record contract."""

    id: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    type: MemoryType
    data: dict = Field(default_factory=dict)


class ExecutionRecord(BaseModel):
    """Unified execution feedback record used by the memory feedback loop."""

    task_id: str = Field(..., min_length=1)
    input: dict = Field(default_factory=dict)
    plan: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    success: bool = False
    errors: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class ExecutionMemory(MemoryRecord):
    """Execution-level memory entry."""

    type: Literal["execution"] = "execution"


class TaskMemory(MemoryRecord):
    """Task-level memory entry."""

    type: Literal["task"] = "task"


class FailureMemory(MemoryRecord):
    """Failure-specific memory entry."""

    type: Literal["failure"] = "failure"


class DecisionMemory(MemoryRecord):
    """Decision/rationale memory entry."""

    type: Literal["decision"] = "decision"
