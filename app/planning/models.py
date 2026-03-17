"""Data models for the planning system."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Task(BaseModel):
    """Represents a single task in a plan."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, description="Task name")
    description: str = Field(..., min_length=1, description="Task description")
    dependencies: list[str] = Field(
        default_factory=list, description="List of task IDs this task depends on"
    )
    status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending", description="Current task status"
    )
    priority: int = Field(default=0, ge=0, le=100, description="Task priority (0-100)")
    metadata: dict = Field(default_factory=dict, description="Additional task metadata")

    def __str__(self) -> str:
        """String representation."""
        return f"Task({self.name})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"Task(id={self.id}, name={self.name!r}, "
            f"dependencies={self.dependencies}, priority={self.priority})"
        )


class Plan(BaseModel):
    """Represents a complete plan with ordered tasks."""

    id: UUID = Field(default_factory=uuid4)
    goal: str = Field(..., min_length=1, description="Overall goal")
    tasks: list[Task] = Field(
        default_factory=list, description="List of tasks in execution order"
    )

    def __str__(self) -> str:
        """String representation."""
        return f"Plan({self.goal})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"Plan(id={self.id}, goal={self.goal!r}, task_count={len(self.tasks)})"

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Retrieve a task by its ID."""
        for task in self.tasks:
            if str(task.id) == task_id:
                return task
        return None
