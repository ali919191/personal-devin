"""Tests for Evaluator — Agent 19 Evaluation Engine."""

import pytest

from app.evaluation.evaluator import Evaluator
from app.evaluation.models import EvaluationInput, EvaluationResult


@pytest.fixture()
def evaluator() -> Evaluator:
    return Evaluator()


# ---------------------------------------------------------------------------
# Exact match
# ---------------------------------------------------------------------------

def test_exact_match_string(evaluator: Evaluator) -> None:
    inp = EvaluationInput(
        task_id="t1",
        expected_output="hello world",
        actual_output="hello world",
    )
    result: EvaluationResult = evaluator.evaluate(inp)

    assert result.task_id == "t1"
    assert result.success is True
    assert result.score == 1.0
    assert "exactly" in result.feedback.lower()
    assert result.metrics["match_type"] == "exact"


def test_exact_match_integer(evaluator: Evaluator) -> None:
    inp = EvaluationInput(
        task_id="t2",
        expected_output=42,
        actual_output=42,
    )
    result = evaluator.evaluate(inp)

    assert result.success is True
    assert result.score == 1.0
    assert result.metrics["match_type"] == "exact"


def test_exact_match_dict(evaluator: Evaluator) -> None:
    expected = {"key": "value", "num": 7}
    inp = EvaluationInput(
        task_id="t3",
        expected_output=expected,
        actual_output={"key": "value", "num": 7},
    )
    result = evaluator.evaluate(inp)

    assert result.success is True
    assert result.score == 1.0
    assert result.metrics["match_type"] == "exact"


# ---------------------------------------------------------------------------
# Mismatch / failure
# ---------------------------------------------------------------------------

def test_mismatch_string(evaluator: Evaluator) -> None:
    inp = EvaluationInput(
        task_id="t4",
        expected_output="expected",
        actual_output="completely different",
    )
    result = evaluator.evaluate(inp)

    assert result.success is False
    assert result.score == 0.0
    assert result.metrics["match_type"] == "failure"
    assert "expected" in result.feedback
    assert "completely different" in result.feedback


def test_mismatch_integer(evaluator: Evaluator) -> None:
    inp = EvaluationInput(
        task_id="t5",
        expected_output=1,
        actual_output=2,
    )
    result = evaluator.evaluate(inp)

    assert result.success is False
    assert result.score == 0.0
    assert result.metrics["match_type"] == "failure"


def test_mismatch_type(evaluator: Evaluator) -> None:
    """A string '42' must not equal an integer 42."""
    inp = EvaluationInput(
        task_id="t6",
        expected_output=42,
        actual_output="42",
    )
    result = evaluator.evaluate(inp)

    assert result.success is False
    assert result.score == 0.0


# ---------------------------------------------------------------------------
# Partial match
# ---------------------------------------------------------------------------

def test_partial_match_expected_in_actual(evaluator: Evaluator) -> None:
    inp = EvaluationInput(
        task_id="t7",
        expected_output="hello",
        actual_output="hello world",
    )
    result = evaluator.evaluate(inp)

    assert result.success is False
    assert result.score == 0.5
    assert result.metrics["match_type"] == "partial"
    assert "partial" in result.feedback.lower()


def test_partial_match_actual_in_expected(evaluator: Evaluator) -> None:
    inp = EvaluationInput(
        task_id="t8",
        expected_output="hello world",
        actual_output="hello",
    )
    result = evaluator.evaluate(inp)

    assert result.success is False
    assert result.score == 0.5
    assert result.metrics["match_type"] == "partial"


# ---------------------------------------------------------------------------
# No expected output (None)
# ---------------------------------------------------------------------------

def test_no_expected_output_passes(evaluator: Evaluator) -> None:
    inp = EvaluationInput(
        task_id="t9",
        expected_output=None,
        actual_output="anything",
    )
    result = evaluator.evaluate(inp)

    assert result.success is True
    assert result.score == 1.0
    assert result.metrics["match_type"] == "no_expectation"


# ---------------------------------------------------------------------------
# Determinism — same input always yields same output
# ---------------------------------------------------------------------------

def test_evaluation_is_deterministic(evaluator: Evaluator) -> None:
    inp = EvaluationInput(
        task_id="t10",
        expected_output="abc",
        actual_output="xyz",
    )
    results = [evaluator.evaluate(inp) for _ in range(5)]

    scores = {r.score for r in results}
    feedbacks = {r.feedback for r in results}
    successes = {r.success for r in results}

    assert len(scores) == 1
    assert len(feedbacks) == 1
    assert len(successes) == 1


# ---------------------------------------------------------------------------
# Metadata is ignored (does not affect score)
# ---------------------------------------------------------------------------

def test_metadata_does_not_affect_score(evaluator: Evaluator) -> None:
    base = EvaluationInput(
        task_id="t11",
        expected_output="x",
        actual_output="x",
    )
    with_meta = EvaluationInput(
        task_id="t11",
        expected_output="x",
        actual_output="x",
        metadata={"env": "prod", "run": 3},
    )
    r1 = evaluator.evaluate(base)
    r2 = evaluator.evaluate(with_meta)

    assert r1.score == r2.score
    assert r1.success == r2.success
    assert r1.metrics["match_type"] == r2.metrics["match_type"]
