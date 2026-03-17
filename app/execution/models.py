"""Pydantic models for the Execution Engine (Agent 03)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Lifecycle status of a single execution task or an overall report."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionTask(BaseModel):
    """A task being tracked through the execution lifecycle.

    Created by converting a ``TaskNode`` (from the Planning Engine) and
    enriched with runtime status, output, and timing information.
    """

    id: str = Field(..., min_length=1, description="Unique task identifier")
    description: str = Field(..., min_length=1, description="Task description")
    dependencies: list[str] = Field(
        default_factory=list,
        description="IDs of tasks this task depends on",
    )
    status: ExecutionStatus = Field(
        default=ExecutionStatus.PENDING,
        description="Current lifecycle status",
    )
    output: str | None = Field(default=None, description="Task output on success")
    error: str | None = Field(default=None, description="Error message on failure")
    started_at: datetime | None = Field(default=None, description="Execution start time")
    completed_at: datetime | None = Field(
        default=None, description="Execution completion time"
    )

    def __str__(self) -> str:
        return f"ExecutionTask({self.id}, {self.status})"

    def __repr__(self) -> str:
        return (
            f"ExecutionTask(id={self.id!r}, status={self.status!r}, "
            f"dependencies={self.dependencies})"
        )


class ExecutionReport(BaseModel):
    """Structured result of a complete execution run produced by the Runner.

    Output contract::

        {
            "tasks":           [...],        # all ExecutionTask entries with final status
            "status":          "completed",  # overall run status
            "total_tasks":     int,
            "completed_tasks": int,
            "failed_tasks":    int,
            "skipped_tasks":   int,
            "started_at":      datetime,
            "completed_at":    datetime | None
        }
    """

    tasks: list[ExecutionTask] = Field(
        default_factory=list,
        description="All tasks with their final execution status",
    )
    status: ExecutionStatus = Field(
        ..., description="Overall execution run status"
    )
    total_tasks: int = Field(..., ge=0, description="Total number of tasks")
    completed_tasks: int = Field(..., ge=0, description="Number of successfully completed tasks")
    failed_tasks: int = Field(..., ge=0, description="Number of failed tasks")
    skipped_tasks: int = Field(..., ge=0, description="Number of skipped tasks")
    started_at: datetime = Field(..., description="When the run started")
    completed_at: datetime | None = Field(default=None, description="When the run finished")
