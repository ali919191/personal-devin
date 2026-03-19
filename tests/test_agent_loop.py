"""Tests for Agent 17 deterministic loop optimization."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.agent.agent_loop import AgentLoop
from app.agent.loop_state import LoopStatus, LoopStep
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.feedback.engine import FeedbackEngine
from app.planning.models import ExecutionGroup, ExecutionPlan, PlanMetadata, TaskNode


def fixed_now() -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC)


def make_plan(*nodes: TaskNode) -> ExecutionPlan:
    node_list = list(nodes)
    return ExecutionPlan(
        ordered_tasks=node_list,
        execution_groups=[ExecutionGroup(group_id=0, task_ids=[node.id for node in node_list])],
        metadata=PlanMetadata(total_tasks=len(node_list), has_cycles=False),
    )


def make_task(task_id: str, status: ExecutionStatus) -> ExecutionTask:
    now = datetime.now(UTC)
    return ExecutionTask(
        id=task_id,
        description=f"Task {task_id}",
        dependencies=[],
        status=status,
        started_at=now,
        completed_at=now,
    )


def make_report(tasks: list[ExecutionTask]) -> ExecutionReport:
    completed = sum(1 for task in tasks if task.status == ExecutionStatus.COMPLETED)
    failed = sum(1 for task in tasks if task.status == ExecutionStatus.FAILED)
    skipped = sum(1 for task in tasks if task.status == ExecutionStatus.SKIPPED)
    status = ExecutionStatus.COMPLETED if failed == 0 and skipped == 0 else ExecutionStatus.FAILED
    now = datetime.now(UTC)
    return ExecutionReport(
        tasks=tasks,
        status=status,
        total_tasks=len(tasks),
        completed_tasks=completed,
        failed_tasks=failed,
        skipped_tasks=skipped,
        started_at=now,
        completed_at=now,
    )


@patch("app.agent.agent_loop.run_plan")
@patch("app.agent.agent_loop.build_execution_plan")
def test_loop_success_path(build_execution_plan_mock, run_plan_mock) -> None:
    plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
    report = make_report([make_task("task-1", ExecutionStatus.COMPLETED)])
    build_execution_plan_mock.return_value = plan
    run_plan_mock.return_value = report

    loop = AgentLoop(
        memory_service=MagicMock(),
        self_improvement_engine=MagicMock(),
        now_fn=fixed_now,
    )
    result = loop.run("Sample goal")

    assert result.status == "success"
    assert result.reflection.notes == "All tasks succeeded"
    assert [state.step for state in loop.state_history if state.status == LoopStatus.SUCCESS] == [
        LoopStep.PLAN,
        LoopStep.EXECUTE,
        LoopStep.VALIDATE,
        LoopStep.REFLECT,
    ]


@patch("app.agent.agent_loop.run_plan")
@patch("app.agent.agent_loop.build_execution_plan")
def test_transient_retry(build_execution_plan_mock, run_plan_mock) -> None:
    plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
    report = make_report([make_task("task-1", ExecutionStatus.COMPLETED)])
    build_execution_plan_mock.return_value = plan
    run_plan_mock.side_effect = [TimeoutError("temporary"), report]

    loop = AgentLoop(
        memory_service=MagicMock(),
        self_improvement_engine=MagicMock(),
        now_fn=fixed_now,
    )
    result = loop.run("Goal")

    assert result.status == "success"
    assert run_plan_mock.call_count == 2
    retry_states = [
        state
        for state in loop.state_history
        if state.step == LoopStep.EXECUTE and state.status == LoopStatus.RETRY
    ]
    assert len(retry_states) == 1


@patch("app.agent.agent_loop.run_plan")
@patch("app.agent.agent_loop.build_execution_plan")
def test_fail_fast_logic_error(build_execution_plan_mock, run_plan_mock) -> None:
    plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
    build_execution_plan_mock.return_value = plan
    run_plan_mock.side_effect = RuntimeError("logic failure")

    loop = AgentLoop(
        memory_service=MagicMock(),
        self_improvement_engine=MagicMock(),
        now_fn=fixed_now,
    )

    with pytest.raises(RuntimeError):
        loop.run("Goal")

    assert run_plan_mock.call_count == 1


@patch("app.agent.agent_loop.run_plan")
@patch("app.agent.agent_loop.build_execution_plan")
def test_deterministic_iteration_id(build_execution_plan_mock, run_plan_mock) -> None:
    plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
    report = make_report([make_task("task-1", ExecutionStatus.COMPLETED)])
    build_execution_plan_mock.return_value = plan
    run_plan_mock.return_value = report

    loop_a = AgentLoop(
        memory_service=MagicMock(),
        self_improvement_engine=MagicMock(),
        now_fn=fixed_now,
    )
    loop_b = AgentLoop(
        memory_service=MagicMock(),
        self_improvement_engine=MagicMock(),
        now_fn=fixed_now,
    )

    result_a = loop_a.run("  Repeatable Goal ")
    result_b = loop_b.run("Repeatable Goal")

    assert result_a.status == "success"
    assert result_b.status == "success"
    assert loop_a.last_iteration_id == loop_b.last_iteration_id


@patch("app.agent.agent_loop.run_plan")
@patch("app.agent.agent_loop.build_execution_plan")
def test_logging_structure(build_execution_plan_mock, run_plan_mock) -> None:
    plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
    report = make_report([make_task("task-1", ExecutionStatus.COMPLETED)])
    build_execution_plan_mock.return_value = plan
    run_plan_mock.return_value = report

    loop = AgentLoop(
        memory_service=MagicMock(),
        self_improvement_engine=MagicMock(),
        now_fn=fixed_now,
    )
    loop.run("Goal")

    assert len(loop.loop_logs) == 4
    for entry in loop.loop_logs:
        assert "iteration_id" in entry
        assert "step" in entry
        assert "status" in entry
        assert "duration_ms" in entry
        assert "error_type" in entry


@patch("app.agent.agent_loop.run_plan")
@patch("app.agent.agent_loop.build_execution_plan")
def test_deterministic_clock_timestamps(build_execution_plan_mock, run_plan_mock) -> None:
    plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
    report = make_report([make_task("task-1", ExecutionStatus.COMPLETED)])
    build_execution_plan_mock.return_value = plan
    run_plan_mock.return_value = report

    loop = AgentLoop(
        memory_service=MagicMock(),
        self_improvement_engine=MagicMock(),
        now_fn=fixed_now,
    )
    loop.run("Goal")

    state_timestamps = {state.timestamp for state in loop.state_history}
    log_timestamps = {entry["timestamp"] for entry in loop.loop_logs}

    assert state_timestamps == {"2024-01-01T00:00:00Z"}
    assert log_timestamps == {"2024-01-01T00:00:00Z"}


@patch("app.agent.agent_loop.run_plan")
@patch("app.agent.agent_loop.build_execution_plan")
def test_feedback_stage_runs_and_routes_to_adaptation_inputs(
    build_execution_plan_mock,
    run_plan_mock,
) -> None:
    plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
    report = make_report([make_task("task-1", ExecutionStatus.FAILED)])
    build_execution_plan_mock.return_value = plan
    run_plan_mock.return_value = report

    memory = MagicMock()
    loop = AgentLoop(
        memory_service=memory,
        self_improvement_engine=MagicMock(),
        feedback_engine=FeedbackEngine(now_fn=fixed_now),
        now_fn=fixed_now,
    )
    result = loop.run("Goal")

    assert result.status == "failure"
    assert memory.log_decision.call_count >= 2
    decisions = [
        call.kwargs.get("decision")
        for call in memory.log_decision.call_args_list
        if "decision" in call.kwargs
    ]
    assert "feedback_signal" in decisions
    assert memory.log_failure.call_count >= 1
