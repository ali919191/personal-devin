"""Schemas for Agent 05 orchestration results."""

from typing import Literal

from pydantic import BaseModel, Field

from app.execution.models import ExecutionReport
from app.planning.models import ExecutionPlan
from app.adaptation.models import Adaptation as RuntimeAdaptation
from app.evaluation.models import EvaluationResult
from app.feedback.models import FeedbackSignal
from pydantic import ConfigDict


class ReflectionResult(BaseModel):
    """Structured reflection generated after execution."""

    failed_tasks: list[str] = Field(default_factory=list)
    success_rate: float = Field(..., ge=0.0, le=1.0)
    notes: str = Field(..., min_length=1)


class AgentResult(BaseModel):
    """Structured result of a full agent loop run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    goal: str = Field(..., min_length=1)
    status: Literal["success", "partial", "failure"]
    plan: ExecutionPlan
    execution: ExecutionReport
    reflection: ReflectionResult
    evaluation: EvaluationResult | None = Field(default=None)
    feedback: FeedbackSignal | None = Field(default=None)
    adaptation: list[RuntimeAdaptation] = Field(default_factory=list)