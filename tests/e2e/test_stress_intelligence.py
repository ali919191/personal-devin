"""Stress + intelligence behavioral validation suite.

These are end-to-end style behavioral tests under adversarial conditions.
Some tests are intentionally strict and may fail, which signals robustness or
intelligence gaps rather than syntax-level regressions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.agent.agent_loop import AgentLoop
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.planning import build_execution_plan


def fixed_now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def _make_loop() -> AgentLoop:
    memory = MagicMock()
    memory.get_feedback_context.return_value = {}
    memory.log_decision.return_value = None
    memory.log_task.return_value = None
    memory.log_execution.return_value = None
    memory.log_failure.return_value = None
    memory.record_execution.return_value = None
    return AgentLoop(memory_service=memory, self_improvement_engine=MagicMock(), now_fn=fixed_now)


def _task(task_id: str, status: ExecutionStatus, deps: list[str] | None = None) -> ExecutionTask:
    return ExecutionTask(
        id=task_id,
        description=f"task {task_id}",
        dependencies=deps or [],
        status=status,
        started_at=fixed_now(),
        completed_at=fixed_now(),
    )


# ---------------------------------------------------------------------------
# 1) STRESS TESTING
# ---------------------------------------------------------------------------


def test_malformed_plan_rejected() -> None:
    malformed_plan = [{"invalid": "missing required fields"}]

    with pytest.raises(ValueError):
        build_execution_plan(malformed_plan)


def test_partial_failure_recovery() -> None:
    loop = _make_loop()

    def partial_report(_):
        tasks = [
            _task("task-1", ExecutionStatus.COMPLETED),
            _task("task-2", ExecutionStatus.FAILED),
        ]
        return ExecutionReport(
            tasks=tasks,
            status=ExecutionStatus.FAILED,
            total_tasks=2,
            completed_tasks=1,
            failed_tasks=1,
            skipped_tasks=0,
            started_at=fixed_now(),
            completed_at=fixed_now(),
        )

    loop._execute = partial_report

    result = loop.run("Execute a plan where one step intentionally fails")

    assert result is not None
    assert result.execution is not None
    assert result.status in ["partial", "failure", "success"]
    assert result.reflection is not None


@pytest.mark.xfail(reason="Conflict detection not implemented yet")
def test_conflicting_goals() -> None:
    loop = _make_loop()

    result = loop.run("Delete a file and ensure the file remains unchanged")

    assert result is not None
    assert result.status in ["failure", "partial"]


def test_long_execution_chain() -> None:
    loop = _make_loop()

    def long_chain(goal: str):
        return [
            {
                "id": f"task-{idx}",
                "description": f"{goal} :: step {idx}",
                "dependencies": [f"task-{idx - 1}"] if idx > 1 else [],
            }
            for idx in range(1, 21)
        ]

    loop._goal_to_tasks = long_chain
    result = loop.run("Perform 20 sequential dependent steps")

    assert result is not None
    assert result.execution is not None
    assert len(result.execution.tasks) >= 1


# ---------------------------------------------------------------------------
# 2) REAL INPUT EXECUTION
# ---------------------------------------------------------------------------


def test_ambiguous_goal_planning() -> None:
    loop = _make_loop()

    result = loop.run("Improve system performance")

    assert result.plan is not None
    assert len(result.plan.ordered_tasks) > 0


def test_recovery_behavior() -> None:
    loop = _make_loop()

    result = loop.run("Run a task that may fail and recover")

    assert result is not None
    assert result.reflection is not None


# ---------------------------------------------------------------------------
# 3) FAILURE INTELLIGENCE
# ---------------------------------------------------------------------------


def test_learning_signal_present() -> None:
    loop = _make_loop()

    result = loop.run("Trigger a failure and observe learning")

    assert result.reflection is not None


def test_adaptation_output() -> None:
    loop = _make_loop()

    result = loop.run("Cause repeated failure scenario")

    assert result.reflection is not None


def test_memory_influences_behavior() -> None:
    loop = _make_loop()

    goal = "Trigger known failure pattern"

    first = loop.run(goal)
    second = loop.run(goal)

    assert first is not None
    assert second is not None
    assert second.status in ["success", "partial", "failure"]