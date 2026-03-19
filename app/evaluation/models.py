"""Data models for Agent 19 Evaluation Engine."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class EvaluationInput:
    """Input contract for a single evaluation request."""

    task_id: str
    expected_output: Optional[Any]
    actual_output: Any
    metadata: Optional[Dict[str, Any]] = field(default=None)


@dataclass(frozen=True)
class EvaluationResult:
    """Structured result produced by the evaluator."""

    task_id: str
    success: bool
    score: float  # 0.0 – 1.0
    feedback: str
    metrics: Dict[str, Any]
