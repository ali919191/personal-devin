from datetime import UTC, datetime

from app.memory.feedback_engine import FeedbackEngine
from app.memory.models import ExecutionRecord


def _record(
    task_id: str,
    *,
    success: bool,
    errors: list[str] | None = None,
    strategy: str = "",
) -> ExecutionRecord:
    metadata = {"source": "test"}
    if strategy:
        metadata["strategy"] = strategy

    return ExecutionRecord(
        task_id=task_id,
        input={"goal": task_id},
        plan={"strategy": strategy} if strategy else {},
        result={"status": "completed" if success else "failed"},
        success=success,
        errors=list(errors or []),
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        metadata=metadata,
    )


def test_build_context_detects_repeated_failures_and_strategies() -> None:
    engine = FeedbackEngine()
    records = [
        _record("t1", success=False, errors=["timeout"]),
        _record("t2", success=False, errors=["timeout"]),
        _record("t3", success=True, strategy="backoff"),
        _record("t4", success=True, strategy="backoff"),
        _record("t5", success=True, strategy="cache"),
    ]

    context = engine.build_context(records)

    assert context["total_records"] == 5
    assert context["repeated_failures"][0]["signature"] == "timeout"
    assert context["repeated_failures"][0]["count"] >= 2
    assert context["success_strategies"][0] == {"strategy": "backoff", "count": 2}


def test_adjust_task_is_deterministic() -> None:
    engine = FeedbackEngine()
    task = {"id": "task-1", "description": "Run task", "dependencies": []}
    context = {
        "repeated_failures": [{"signature": "timeout", "count": 3, "source": "memory:test"}],
        "success_strategies": [{"strategy": "backoff", "count": 2}],
    }

    first = engine.adjust_task(task, context)
    second = engine.adjust_task(task, context)

    assert first == second
    assert first["metadata"]["avoid_failure_signatures"] == ["timeout"]
    assert first["metadata"]["preferred_strategies"] == ["backoff"]
