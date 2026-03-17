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


# ---------------------------------------------------------------------------
# Agent 02 — Planning Engine models
# ---------------------------------------------------------------------------


class TaskNode(BaseModel):
    """Input task node received from the Task Decomposition Engine (Agent 01).

    Uses plain string IDs so the Planning Engine operates independently of
    UUID-based internal Agent 01 identifiers.
    """

    id: str = Field(..., min_length=1, description="Unique task identifier")
    description: str = Field(..., min_length=1, description="Task description")
    dependencies: list[str] = Field(
        ...,
        description="IDs of tasks this task depends on",
    )

    @classmethod
    def from_dict(cls, task: dict) -> "TaskNode":
        """Create TaskNode from plain dictionary input."""
        return cls.model_validate(task)

    def __str__(self) -> str:
        """String representation."""
        return f"TaskNode({self.id})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"TaskNode(id={self.id!r}, description={self.description!r}, "
            f"dependencies={self.dependencies})"
        )


class PlanMetadata(BaseModel):
    """Metadata summary attached to a generated ExecutionPlan."""

    total_tasks: int = Field(..., ge=0, description="Total number of tasks in the plan")
    has_cycles: bool = Field(
        ..., description="Always False for successful plans; cycles raise exceptions"
    )


class ExecutionGroup(BaseModel):
    """Tasks discovered in the same topological level during traversal."""

    group_id: int = Field(..., ge=0, description="Zero-based group index")
    task_ids: list[str] = Field(
        default_factory=list,
        description="IDs of tasks in this parallelisable execution group",
    )


class ExecutionPlan(BaseModel):
    """Deterministic execution plan produced by the Planning Engine (Agent 02).

    Output contract::

        {
            "ordered_tasks": [...],      # topologically sorted TaskNodes
            "execution_groups": [...],   # grouped by parallelisability
            "metadata": {
                "total_tasks": int,
                "has_cycles": bool
            }
        }
    """

    ordered_tasks: list[TaskNode] = Field(
        default_factory=list,
        description="Tasks sorted in topological execution order",
    )
    execution_groups: list[ExecutionGroup] = Field(
        default_factory=list,
        description="Tasks grouped by parallelisable execution level",
    )
    metadata: PlanMetadata = Field(..., description="Plan metadata")
