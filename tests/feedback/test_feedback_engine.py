from datetime import UTC, datetime

import pytest

from app.evaluation.models import EvaluationResult
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.feedback.engine import FeedbackEngine


FIXED_NOW = datetime(2024, 1, 1, tzinfo=UTC)


def _now() -> datetime:
    return FIXED_NOW


def _task(task_id: str, status: ExecutionStatus) -> ExecutionTask:
    return ExecutionTask(
        id=task_id,
        description=f"Task {task_id}",
        dependencies=[],
        status=status,
        started_at=FIXED_NOW,
        completed_at=FIXED_NOW,
    )


def _report(tasks: list[ExecutionTask]) -> ExecutionReport:
    completed = sum(1 for task in tasks if task.status == ExecutionStatus.COMPLETED)
    failed = sum(1 for task in tasks if task.status == ExecutionStatus.FAILED)
    skipped = sum(1 for task in tasks if task.status == ExecutionStatus.SKIPPED)
    status = ExecutionStatus.COMPLETED if failed == 0 and skipped == 0 else ExecutionStatus.FAILED
    return ExecutionReport(
        tasks=tasks,
        status=status,
        total_tasks=len(tasks),
        completed_tasks=completed,
        failed_tasks=failed,
        skipped_tasks=skipped,
        started_at=FIXED_NOW,
        completed_at=FIXED_NOW,
    )


def _evaluation(
    *,
    execution_id: str,
    success: bool,
    score: float,
    match_type: str,
) -> EvaluationResult:
    return EvaluationResult(
        task_id=execution_id,
        success=success,
        score=score,
        feedback="deterministic evaluation",
        metrics={"match_type": match_type},
    )


def test_deterministic_feedback_generation() -> None:
    engine = FeedbackEngine(now_fn=_now)
    report = _report([_task("task-1", ExecutionStatus.COMPLETED)])
    evaluation = _evaluation(
        execution_id="exec-1",
        success=True,
        score=1.0,
        match_type="exact",
    )

    first = engine.generate_feedback(report, evaluation)
    second = engine.generate_feedback(report, evaluation)

    assert first == second
    assert first.success is True
    assert first.failure_type is None
    assert first.score == 1.0
    assert first.timestamp == FIXED_NOW


def test_correct_failure_classification() -> None:
    engine = FeedbackEngine(now_fn=_now)
    report = _report(
        [
            _task("task-1", ExecutionStatus.COMPLETED),
            _task("task-2", ExecutionStatus.FAILED),
        ]
    )
    evaluation = _evaluation(
        execution_id="exec-2",
        success=False,
        score=0.0,
        match_type="failure",
    )

    signal = engine.generate_feedback(report, evaluation)

    assert signal.success is False
    assert signal.failure_type == "execution_failure"


def test_suggestion_generation_consistency() -> None:
    engine = FeedbackEngine(now_fn=_now)
    report = _report([_task("task-1", ExecutionStatus.COMPLETED)])
    evaluation = _evaluation(
        execution_id="exec-3",
        success=False,
        score=0.5,
        match_type="partial",
    )

    first = engine.generate_feedback(report, evaluation)
    second = engine.generate_feedback(report, evaluation)

    assert first.improvement_suggestions == second.improvement_suggestions
    assert first.improvement_suggestions == [
        "refine_expected_output_constraints",
        "add_post_execution_output_sanitization",
    ]


def test_batch_processing_correctness() -> None:
    engine = FeedbackEngine(now_fn=_now)
    reports = [
        _report([_task("task-1", ExecutionStatus.COMPLETED)]),
        _report([_task("task-2", ExecutionStatus.FAILED)]),
    ]
    evaluations = [
        _evaluation(execution_id="exec-4", success=True, score=1.0, match_type="exact"),
        _evaluation(execution_id="exec-5", success=False, score=0.0, match_type="failure"),
    ]

    batch = engine.batch_feedback(reports, evaluations)

    assert len(batch.signals) == 2
    assert batch.signals[0].execution_id == "exec-4"
    assert batch.signals[0].success is True
    assert batch.signals[1].execution_id == "exec-5"
    assert batch.signals[1].failure_type == "execution_failure"


def test_batch_feedback_requires_aligned_inputs() -> None:
    engine = FeedbackEngine(now_fn=_now)
    reports = [_report([_task("task-1", ExecutionStatus.COMPLETED)])]
    evaluations: list[EvaluationResult] = []

    with pytest.raises(ValueError, match="same length"):
        engine.batch_feedback(reports, evaluations)


def test_feedback_includes_injected_adaptation_follow_up_when_failure_persists() -> None:
    engine = FeedbackEngine(now_fn=_now)
    report = _report([_task("task-1", ExecutionStatus.FAILED)])
    evaluation = EvaluationResult(
        task_id="exec-6",
        success=False,
        score=0.0,
        feedback="deterministic evaluation",
        metrics={
            "match_type": "failure",
            "applied_modifiers": {"retry_limit": 3},
        },
    )

    signal = engine.generate_feedback(report, evaluation)

    assert signal.failure_type == "execution_failure"
    assert "review_injected_adaptation_effectiveness" in signal.improvement_suggestions
