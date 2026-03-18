"""Tests for Agent 05 Agent Loop."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, call, patch

from app.agent.agent_loop import AgentLoop
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.planning.models import ExecutionGroup, ExecutionPlan, PlanMetadata, TaskNode


def make_plan(*nodes: TaskNode) -> ExecutionPlan:
    node_list = list(nodes)
    return ExecutionPlan(
        ordered_tasks=node_list,
        execution_groups=[ExecutionGroup(group_id=0, task_ids=[node.id for node in node_list])],
        metadata=PlanMetadata(total_tasks=len(node_list), has_cycles=False),
    )


def make_task(
    task_id: str,
    status: ExecutionStatus,
    *,
    error: str | None = None,
    skip_reason: str | None = None,
) -> ExecutionTask:
    return ExecutionTask(
        id=task_id,
        description=f"Task {task_id}",
        dependencies=[],
        status=status,
        error=error,
        skip_reason=skip_reason,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )


def make_report(tasks: list[ExecutionTask]) -> ExecutionReport:
    completed = sum(1 for task in tasks if task.status == ExecutionStatus.COMPLETED)
    failed = sum(1 for task in tasks if task.status == ExecutionStatus.FAILED)
    skipped = sum(1 for task in tasks if task.status == ExecutionStatus.SKIPPED)
    status = ExecutionStatus.COMPLETED if completed == len(tasks) else ExecutionStatus.FAILED
    started_at = datetime.now(UTC)
    return ExecutionReport(
        tasks=tasks,
        status=status,
        total_tasks=len(tasks),
        completed_tasks=completed,
        failed_tasks=failed,
        skipped_tasks=skipped,
        started_at=started_at,
        completed_at=started_at,
    )


class TestAgentLoop:
    @patch("app.agent.agent_loop.run_plan")
    @patch("app.agent.agent_loop.build_execution_plan")
    def test_full_success(self, build_execution_plan_mock, run_plan_mock) -> None:
        plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
        report = make_report([make_task("task-1", ExecutionStatus.COMPLETED)])
        build_execution_plan_mock.return_value = plan
        run_plan_mock.return_value = report

        memory = MagicMock()
        result = AgentLoop(memory_service=memory).run("Sample goal")

        build_execution_plan_mock.assert_called_once_with(
            [{"id": "task-1", "description": "Sample goal", "dependencies": []}]
        )
        run_plan_mock.assert_called_once_with(plan)
        assert result.status == "success"
        assert result.reflection.success_rate == 1.0
        assert result.reflection.notes == "All tasks succeeded"

    @patch("app.agent.agent_loop.run_plan")
    @patch("app.agent.agent_loop.build_execution_plan")
    def test_partial_failure(self, build_execution_plan_mock, run_plan_mock) -> None:
        plan = make_plan(
            TaskNode(id="task-1", description="goal", dependencies=[]),
            TaskNode(id="task-2", description="goal-2", dependencies=[]),
        )
        report = make_report(
            [
                make_task("task-1", ExecutionStatus.COMPLETED),
                make_task("task-2", ExecutionStatus.FAILED, error="boom"),
            ]
        )
        build_execution_plan_mock.return_value = plan
        run_plan_mock.return_value = report

        result = AgentLoop(memory_service=MagicMock()).run("Goal")

        assert result.status == "partial"
        assert result.reflection.failed_tasks == ["task-2"]
        assert result.reflection.notes == "Partial failure detected"

    @patch("app.agent.agent_loop.run_plan")
    @patch("app.agent.agent_loop.build_execution_plan")
    def test_full_failure(self, build_execution_plan_mock, run_plan_mock) -> None:
        plan = make_plan(TaskNode(id="task-1", description="goal", dependencies=[]))
        report = make_report([make_task("task-1", ExecutionStatus.FAILED, error="boom")])
        build_execution_plan_mock.return_value = plan
        run_plan_mock.return_value = report

        result = AgentLoop(memory_service=MagicMock()).run("Goal")

        assert result.status == "failure"
        assert result.reflection.failed_tasks == ["task-1"]
        assert result.reflection.notes == "Execution failed"

    @patch("app.agent.agent_loop.run_plan")
    @patch("app.agent.agent_loop.build_execution_plan")
    def test_memory_logging_invoked(self, build_execution_plan_mock, run_plan_mock) -> None:
        plan = make_plan(
            TaskNode(id="task-1", description="goal", dependencies=[]),
            TaskNode(id="task-2", description="goal-2", dependencies=[]),
        )
        report = make_report(
            [
                make_task("task-1", ExecutionStatus.COMPLETED),
                make_task(
                    "task-2",
                    ExecutionStatus.SKIPPED,
                    error="dependency_failed:task-1",
                    skip_reason="dependency_failed:task-1",
                ),
            ]
        )
        build_execution_plan_mock.return_value = plan
        run_plan_mock.return_value = report

        memory = MagicMock()
        AgentLoop(memory_service=memory).run("Goal")

        memory.log_execution.assert_called_once()
        assert memory.log_task.call_count == 2
        memory.log_failure.assert_called_once_with(
            source="agent_loop",
            error="dependency_failed:task-1",
            context={"goal": "Goal", "task_id": "task-2", "status": "skipped"},
        )
        memory.log_decision.assert_called_once()

    def test_empty_goal_rejected(self) -> None:
        with patch("app.agent.agent_loop.build_execution_plan"):
            with patch("app.agent.agent_loop.run_plan"):
                try:
                    AgentLoop(memory_service=MagicMock()).run("   ")
                except ValueError as exc:
                    assert str(exc) == "goal must be a non-empty string"
                else:
                    raise AssertionError("Expected ValueError for empty goal")