"""Deterministic evaluator for Agent 19 Evaluation Engine."""

from app.core.logger import get_logger
from app.evaluation.models import EvaluationInput, EvaluationResult

logger = get_logger(__name__)

# Scoring constants — deterministic, no randomness.
_SCORE_EXACT_MATCH: float = 1.0
_SCORE_PARTIAL_MATCH: float = 0.5
_SCORE_FAILURE: float = 0.0


class Evaluator:
    """Pure, deterministic evaluator.

    Produces an :class:`EvaluationResult` from an :class:`EvaluationInput`
    with no side-effects, no randomness, and no external I/O.
    """

    def evaluate(self, input_data: EvaluationInput) -> EvaluationResult:
        """Evaluate *input_data* and return a structured result.

        Scoring rules:
        - If ``expected_output`` is ``None`` the task is considered
          successful with a score of 1.0 (no expectation to violate).
        - Exact equality  → score 1.0, success True.
        - Partial string  → score 0.5, success False.
        - No match        → score 0.0, success False.
        """
        logger.info(
            "evaluation_started",
            {"task_id": input_data.task_id},
        )

        if input_data.expected_output is None:
            result = self._build_result(
                task_id=input_data.task_id,
                success=True,
                score=_SCORE_EXACT_MATCH,
                feedback="No expected output specified; evaluation passed by default.",
                match_type="no_expectation",
            )
        else:
            result = self._compare(input_data)

        logger.info(
            "evaluation_completed",
            {
                "task_id": result.task_id,
                "success": result.success,
                "score": result.score,
            },
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compare(self, input_data: EvaluationInput) -> EvaluationResult:
        """Perform deterministic comparison between expected and actual."""
        expected = input_data.expected_output
        actual = input_data.actual_output

        # Exact equality check (works for any type that supports __eq__).
        if expected == actual:
            return self._build_result(
                task_id=input_data.task_id,
                success=True,
                score=_SCORE_EXACT_MATCH,
                feedback="Output matches expected exactly.",
                match_type="exact",
            )

        # Partial string containment — only attempted when both values are str.
        if isinstance(expected, str) and isinstance(actual, str):
            if expected in actual or actual in expected:
                return self._build_result(
                    task_id=input_data.task_id,
                    success=False,
                    score=_SCORE_PARTIAL_MATCH,
                    feedback=(
                        f"Partial string match detected. "
                        f"Expected: {expected!r}, Got: {actual!r}."
                    ),
                    match_type="partial",
                )

        # No match.
        return self._build_result(
            task_id=input_data.task_id,
            success=False,
            score=_SCORE_FAILURE,
            feedback=(
                f"Output does not match expected. "
                f"Expected: {expected!r}, Got: {actual!r}."
            ),
            match_type="failure",
        )

    @staticmethod
    def _build_result(
        *,
        task_id: str,
        success: bool,
        score: float,
        feedback: str,
        match_type: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            task_id=task_id,
            success=success,
            score=score,
            feedback=feedback,
            metrics={"match_type": match_type, "score": score},
        )
