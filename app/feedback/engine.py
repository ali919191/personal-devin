"""Deterministic Feedback Loop Engine (Agent 20)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from app.core.logger import get_logger
from app.evaluation.models import EvaluationResult
from app.execution.models import ExecutionReport
from app.feedback.models import FeedbackBatch, FeedbackSignal

logger = get_logger(__name__)


class FeedbackEngine:
    """Produces deterministic feedback signals from execution + evaluation outputs."""

    _SUGGESTIONS: dict[str, list[str]] = {
        "execution_failure": [
            "add_task_level_retry_with_backoff",
            "introduce_precondition_validation",
        ],
        "task_failure": [
            "inspect_failed_task_dependencies",
            "tighten_task_input_validation",
        ],
        "dependency_skip": [
            "promote_dependency_health_checks",
            "add_fallback_path_for_blocked_dependencies",
        ],
        "partial_match": [
            "refine_expected_output_constraints",
            "add_post_execution_output_sanitization",
        ],
        "quality_failure": [
            "increase_assertion_coverage_for_outputs",
            "tighten_evaluation_thresholds",
        ],
    }

    _CONFIDENCE_BY_FAILURE: dict[str, float] = {
        "execution_failure": 0.75,
        "task_failure": 0.85,
        "dependency_skip": 0.8,
        "partial_match": 0.9,
        "quality_failure": 0.7,
    }

    def __init__(self, now_fn: Callable[[], datetime] | None = None) -> None:
        if now_fn is None:
            raise ValueError("now_fn must be provided for deterministic feedback timestamps")
        self._now_fn = now_fn

    def generate_feedback(
        self,
        execution: ExecutionReport,
        evaluation: EvaluationResult,
    ) -> FeedbackSignal:
        """Generate a deterministic feedback signal from a single run."""
        normalized_score = self._normalize_score(evaluation.score)
        failure_type = self._classify_failure(execution, evaluation)
        suggestions = self._suggestions_for(failure_type)
        success = bool(evaluation.success) and failure_type is None

        if failure_type is None:
            confidence = 1.0
        else:
            confidence = self._CONFIDENCE_BY_FAILURE.get(failure_type, 0.7)

        signal = FeedbackSignal(
            execution_id=evaluation.task_id,
            score=normalized_score,
            success=success,
            failure_type=failure_type,
            improvement_suggestions=suggestions,
            confidence=round(confidence, 4),
            timestamp=self._normalize_timestamp(self._now_fn()),
        )

        logger.info(
            "feedback_generated",
            {
                "execution_id": signal.execution_id,
                "score": signal.score,
                "failure_type": signal.failure_type,
                "suggestions": signal.improvement_suggestions,
            },
        )
        return signal

    def batch_feedback(
        self,
        executions: Sequence[ExecutionReport],
        evaluations: Sequence[EvaluationResult],
    ) -> FeedbackBatch:
        """Generate deterministic feedback signals for aligned execution/evaluation pairs."""
        if len(executions) != len(evaluations):
            raise ValueError("executions and evaluations must have the same length")

        signals = [
            self.generate_feedback(execution=execution, evaluation=evaluation)
            for execution, evaluation in zip(executions, evaluations)
        ]
        return FeedbackBatch(signals=signals)

    def _classify_failure(
        self,
        execution: ExecutionReport,
        evaluation: EvaluationResult,
    ) -> str | None:
        if evaluation.success and execution.failed_tasks == 0 and execution.skipped_tasks == 0:
            return None

        match_type = str(evaluation.metrics.get("match_type", "")).strip().lower()
        if match_type == "partial":
            return "partial_match"

        if execution.failed_tasks > 0 and evaluation.score <= 0.2:
            return "execution_failure"

        if execution.failed_tasks > 0:
            return "task_failure"

        if execution.skipped_tasks > 0:
            return "dependency_skip"

        return "quality_failure"

    def _suggestions_for(self, failure_type: str | None) -> list[str]:
        if failure_type is None:
            return []
        suggestions = self._SUGGESTIONS.get(failure_type, ["review_evaluation_contract"])
        return list(suggestions)

    def _normalize_score(self, score: float) -> float:
        bounded = min(max(float(score), 0.0), 1.0)
        return round(bounded, 4)

    def _normalize_timestamp(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)