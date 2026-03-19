from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.agent.agent_loop import AgentLoop
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.memory.memory_store import MemoryStore
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.planning.models import ExecutionGroup, ExecutionPlan, PlanMetadata, TaskNode


def _fixed_now() -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC)


def _make_service(tmp_path: Path) -> MemoryService:
    store = MemoryStore(base_dir=tmp_path / "data" / "memory")
    repository = MemoryRepository(store=store)
    return MemoryService(repository=repository)


def _make_plan() -> ExecutionPlan:
    node = TaskNode(id="task-1", description="Goal", dependencies=[])
    return ExecutionPlan(
        ordered_tasks=[node],
        execution_groups=[ExecutionGroup(group_id=0, task_ids=[node.id])],
        metadata=PlanMetadata(total_tasks=1, has_cycles=False),
    )


def _make_report(status: ExecutionStatus) -> ExecutionReport:
    now = datetime.now(UTC)
    task = ExecutionTask(
        id="task-1",
        description="Task",
        dependencies=[],
        status=status,
        started_at=now,
        completed_at=now,
    )
    return ExecutionReport(
        tasks=[task],
        status=status,
        total_tasks=1,
        completed_tasks=1 if status == ExecutionStatus.COMPLETED else 0,
        failed_tasks=1 if status == ExecutionStatus.FAILED else 0,
        skipped_tasks=0,
        started_at=now,
        completed_at=now,
    )


def test_execution_is_stored_and_recent_history_returns_records(tmp_path: Path) -> None:
    service = _make_service(tmp_path)

    service.record_execution(
        task_id="task-123",
        input={"goal": "run"},
        plan={"task_ids": ["task-123"]},
        result={"status": "success", "total_tasks": 1, "completed_tasks": 1, "failed_tasks": 0, "skipped_tasks": 0},
        success=True,
        errors=[],
        metadata={"source": "test"},
    )

    history = service.get_recent_history(limit=10)

    assert len(history) == 1
    assert history[0].task_id == "task-123"
    assert history[0].success is True


def test_feedback_context_generated_from_failures(tmp_path: Path) -> None:
    service = _make_service(tmp_path)

    service.record_execution(
        task_id="task-a",
        result={"status": "failed", "total_tasks": 1, "completed_tasks": 0, "failed_tasks": 1, "skipped_tasks": 0},
        success=False,
        errors=["timeout"],
        metadata={"source": "integration-test"},
    )
    service.record_execution(
        task_id="task-b",
        result={"status": "failed", "total_tasks": 1, "completed_tasks": 0, "failed_tasks": 1, "skipped_tasks": 0},
        success=False,
        errors=["timeout"],
        metadata={"source": "integration-test"},
    )

    context = service.get_feedback_context("task-current")

    assert context["task_id"] == "task-current"
    assert context["repeated_failures"]
    assert context["repeated_failures"][0]["signature"] == "timeout"


@patch("app.agent.agent_loop.run_plan")
@patch("app.agent.agent_loop.plan_task")
def test_agent_loop_passes_context_to_planner(plan_mock, run_plan_mock, tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.record_execution(
        task_id="older-failure-1",
        result={"status": "failed", "total_tasks": 1, "completed_tasks": 0, "failed_tasks": 1, "skipped_tasks": 0},
        success=False,
        errors=["timeout"],
        metadata={"source": "integration-test"},
    )
    service.record_execution(
        task_id="older-failure-2",
        result={"status": "failed", "total_tasks": 1, "completed_tasks": 0, "failed_tasks": 1, "skipped_tasks": 0},
        success=False,
        errors=["timeout"],
        metadata={"source": "integration-test"},
    )

    plan_mock.return_value = _make_plan()
    run_plan_mock.return_value = _make_report(ExecutionStatus.COMPLETED)

    loop = AgentLoop(
        memory_service=service,
        self_improvement_engine=MagicMock(),
        now_fn=_fixed_now,
    )

    result = loop.run("Goal")

    assert result.status == "success"
    assert plan_mock.call_count == 1
    planner_context = plan_mock.call_args.kwargs["context"]
    assert planner_context["repeated_failures"][0]["signature"] == "timeout"


def test_feedback_context_is_deterministic(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.record_execution(
        task_id="task-a",
        result={"status": "failed", "total_tasks": 1, "completed_tasks": 0, "failed_tasks": 1, "skipped_tasks": 0},
        success=False,
        errors=["dependency_error"],
        metadata={"source": "integration-test"},
    )
    service.record_execution(
        task_id="task-b",
        result={"status": "failed", "total_tasks": 1, "completed_tasks": 0, "failed_tasks": 1, "skipped_tasks": 0},
        success=False,
        errors=["dependency_error"],
        metadata={"source": "integration-test"},
    )

    first = service.get_feedback_context("same-task")
    second = service.get_feedback_context("same-task")

    assert first == second


def test_record_execution_uses_injected_now_fn(tmp_path: Path) -> None:
    fixed = datetime(2030, 1, 1, tzinfo=UTC)
    service = MemoryService(
        repository=MemoryRepository(store=MemoryStore(base_dir=tmp_path / "data" / "memory")),
        now_fn=lambda: fixed,
    )

    saved = service.record_execution(
        task_id="clocked-task",
        result={"status": "success", "total_tasks": 1, "completed_tasks": 1, "failed_tasks": 0, "skipped_tasks": 0},
        success=True,
    )
    history = service.get_recent_history(limit=1)

    assert saved.timestamp == fixed
    assert history[0].timestamp == fixed
