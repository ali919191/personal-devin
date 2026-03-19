"""Evaluation service for Agent 19 — orchestrates evaluation and memory storage."""

from app.core.logger import get_logger
from app.evaluation.evaluator import Evaluator
from app.evaluation.models import EvaluationInput, EvaluationResult

logger = get_logger(__name__)


class EvaluationService:
    """Orchestrates evaluation and persists results to the memory system.

    Parameters
    ----------
    evaluator:
        A :class:`~app.evaluation.evaluator.Evaluator` instance used to
        score each :class:`~app.evaluation.models.EvaluationInput`.
    memory_service:
        Any object that exposes a ``log_decision(decision, reason, context)``
        method matching the :class:`~app.memory.service.MemoryService`
        interface.  Accepted as a plain ``object`` so callers can pass mocks
        without importing the concrete class.
    """

    def __init__(self, evaluator: Evaluator, memory_service: object) -> None:
        self._evaluator = evaluator
        self._memory_service = memory_service

    def evaluate_and_record(self, input_data: EvaluationInput) -> EvaluationResult:
        """Run evaluation and store the result in the memory system.

        Steps
        -----
        1. Delegate to :meth:`Evaluator.evaluate` for deterministic scoring.
        2. Persist the result via ``memory_service.log_decision``.
        3. Return the :class:`EvaluationResult` to the caller.
        """
        logger.info(
            "evaluation_service_started",
            {"task_id": input_data.task_id},
        )

        result: EvaluationResult = self._evaluator.evaluate(input_data)

        self._memory_service.log_decision(  # type: ignore[attr-defined]
            decision="evaluation_result",
            reason=result.feedback,
            context={
                "task_id": result.task_id,
                "success": result.success,
                "score": result.score,
                "feedback": result.feedback,
                "metrics": result.metrics,
            },
        )

        logger.info(
            "evaluation_service_completed",
            {
                "task_id": result.task_id,
                "success": result.success,
                "score": result.score,
            },
        )

        return result
