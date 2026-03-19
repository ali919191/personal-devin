"""Tests for EvaluationService — Agent 19 Evaluation Engine."""

from unittest.mock import MagicMock, call

import pytest

from app.evaluation.evaluator import Evaluator
from app.evaluation.models import EvaluationInput, EvaluationResult
from app.evaluation.service import EvaluationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_service(memory_service: object | None = None) -> EvaluationService:
    if memory_service is None:
        memory_service = MagicMock()
    return EvaluationService(evaluator=Evaluator(), memory_service=memory_service)


# ---------------------------------------------------------------------------
# Evaluation flow
# ---------------------------------------------------------------------------

def test_evaluate_and_record_returns_result() -> None:
    service = make_service()
    inp = EvaluationInput(
        task_id="task-001",
        expected_output="ok",
        actual_output="ok",
    )

    result: EvaluationResult = service.evaluate_and_record(inp)

    assert isinstance(result, EvaluationResult)
    assert result.task_id == "task-001"
    assert result.success is True
    assert result.score == 1.0


def test_evaluate_and_record_failure() -> None:
    service = make_service()
    inp = EvaluationInput(
        task_id="task-002",
        expected_output="expected",
        actual_output="wrong",
    )

    result = service.evaluate_and_record(inp)

    assert result.success is False
    assert result.score == 0.0


def test_evaluate_and_record_partial() -> None:
    service = make_service()
    inp = EvaluationInput(
        task_id="task-003",
        expected_output="partial",
        actual_output="partial match here",
    )

    result = service.evaluate_and_record(inp)

    assert result.success is False
    assert result.score == 0.5


# ---------------------------------------------------------------------------
# Memory interaction
# ---------------------------------------------------------------------------

def test_memory_log_decision_called_once() -> None:
    mock_memory = MagicMock()
    service = make_service(mock_memory)
    inp = EvaluationInput(
        task_id="task-004",
        expected_output="data",
        actual_output="data",
    )

    service.evaluate_and_record(inp)

    mock_memory.log_decision.assert_called_once()


def test_memory_log_decision_receives_correct_task_id() -> None:
    mock_memory = MagicMock()
    service = make_service(mock_memory)
    inp = EvaluationInput(
        task_id="task-005",
        expected_output="value",
        actual_output="value",
    )

    service.evaluate_and_record(inp)

    _, kwargs = mock_memory.log_decision.call_args
    context: dict = kwargs.get("context") or mock_memory.log_decision.call_args[1].get("context", {})
    # Also support positional calls
    if not context:
        args = mock_memory.log_decision.call_args[0]
        # signature: log_decision(decision, reason, context)
        context = args[2] if len(args) > 2 else {}

    assert context.get("task_id") == "task-005"


def test_memory_log_decision_stores_score_and_success() -> None:
    mock_memory = MagicMock()
    service = make_service(mock_memory)
    inp = EvaluationInput(
        task_id="task-006",
        expected_output="abc",
        actual_output="xyz",
    )

    service.evaluate_and_record(inp)

    call_kwargs = mock_memory.log_decision.call_args[1]
    context: dict = call_kwargs["context"]

    assert "score" in context
    assert "success" in context
    assert context["score"] == 0.0
    assert context["success"] is False


def test_memory_log_decision_stores_feedback() -> None:
    mock_memory = MagicMock()
    service = make_service(mock_memory)
    inp = EvaluationInput(
        task_id="task-007",
        expected_output="expected",
        actual_output="expected",
    )

    service.evaluate_and_record(inp)

    call_kwargs = mock_memory.log_decision.call_args[1]
    context: dict = call_kwargs["context"]

    assert "feedback" in context
    assert isinstance(context["feedback"], str)
    assert len(context["feedback"]) > 0


def test_memory_log_decision_decision_label() -> None:
    mock_memory = MagicMock()
    service = make_service(mock_memory)
    inp = EvaluationInput(
        task_id="task-008",
        expected_output=None,
        actual_output="anything",
    )

    service.evaluate_and_record(inp)

    call_kwargs = mock_memory.log_decision.call_args[1]
    assert call_kwargs["decision"] == "evaluation_result"


# ---------------------------------------------------------------------------
# Service uses injected evaluator (dependency injection)
# ---------------------------------------------------------------------------

def test_custom_evaluator_is_used() -> None:
    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = EvaluationResult(
        task_id="task-custom",
        success=True,
        score=1.0,
        feedback="mock feedback",
        metrics={"match_type": "exact", "score": 1.0},
    )
    mock_memory = MagicMock()

    service = EvaluationService(evaluator=mock_evaluator, memory_service=mock_memory)
    inp = EvaluationInput(
        task_id="task-custom",
        expected_output="x",
        actual_output="x",
    )

    result = service.evaluate_and_record(inp)

    mock_evaluator.evaluate.assert_called_once_with(inp)
    assert result.task_id == "task-custom"
