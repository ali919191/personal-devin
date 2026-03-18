"""Schemas for Agent 05 orchestration results."""

from typing import Literal

from pydantic import BaseModel, Field

from app.execution.models import ExecutionReport
from app.planning.models import ExecutionPlan


class ReflectionResult(BaseModel):
    """Structured reflection generated after execution."""

    failed_tasks: list[str] = Field(default_factory=list)
    success_rate: float = Field(..., ge=0.0, le=1.0)
    notes: str = Field(..., min_length=1)


class AgentResult(BaseModel):
    """Structured result of a full agent loop run."""

    goal: str = Field(..., min_length=1)
    status: Literal["success", "partial", "failure"]
    plan: ExecutionPlan
    execution: ExecutionReport
    reflection: ReflectionResult