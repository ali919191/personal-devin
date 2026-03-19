"""Tests for Agent 16 orchestration controller."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.orchestrator import OrchestrationController, OrchestrationRequest
from app.core.recovery import TransientFailureError
from app.core.state import SystemState
from app.execution import ExecutionReport, ExecutionStatus, ExecutionTask
from app.planning.models import ExecutionGroup, ExecutionPlan, PlanMetadata, TaskNode
from app.self_improvement.models import AdaptationResult, ImprovementType, SelfImprovementAdaptation


@dataclass
class StubMemoryRecord:
    id: str
    type: str
    data: dict[str, Any]
    timestamp: datetime


class StubMemoryService:
    def __init__(self) -> None:
        self.execution_calls: list[dict[str, Any]] = []
        self.task_calls: list[dict[str, Any]] = []
        self.failure_calls: list[dict[str, Any]] = []
        self.decision_calls: list[dict[str, Any]] = []
        self.improvement_calls: list[list[Any]] = []
        self._records: list[StubMemoryRecord] = []

    def log_execution(
        self,
        status: str,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int,
        skipped_tasks: int,
        metadata: dict | None = None,
    ) -> StubMemoryRecord:
        payload = {
            "status": status,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "skipped_tasks": skipped_tasks,
            "metadata": metadata or {},
        }
        self.execution_calls.append(payload)
        return self._append("execution", payload)

    def log_task(
        self,
        task_id: str,
        status: str,
        output: str | None = None,
        error: str | None = None,
        skip_reason: str | None = None,
    ) -> StubMemoryRecord:
        payload = {
            "task_id": task_id,
            "status": status,
            "output": output,
            "error": error,
            "skip_reason": skip_reason,
        }
        self.task_calls.append(payload)
        return self._append("task", payload)

    def log_failure(
        self,
        source: str,
        error: str,
        context: dict | None = None,
    ) -> StubMemoryRecord:
        payload = {"source": source, "error": error, "context": context or {}}
        self.failure_calls.append(payload)
        return self._append("failure", payload)

    def log_decision(
        self,
        decision: str,
        reason: str,
        context: dict | None = None,
    ) -> StubMemoryRecord:
        payload = {"decision": decision, "reason": reason, "context": context or {}}
        self.decision_calls.append(payload)
        return self._append("decision", payload)

    def store_improvements(self, improvements: list[Any]) -> list[StubMemoryRecord]:
        self.improvement_calls.append(list(improvements))
        return [
            self._append(
                "decision",
                {"improvement": getattr(improvement, "adaptation_id", "unknown")},
            )
            for improvement in improvements
        ]

    def get_recent(self, limit: int) -> list[StubMemoryRecord]:
        return list(reversed(self._records))[:limit]

    def _append(self, record_type: str, data: dict[str, Any]) -> StubMemoryRecord:
        record = StubMemoryRecord(
            id=f"{record_type}-{len(self._records) + 1:06d}",
            type=record_type,
            data=data,
            timestamp=datetime.now(UTC),
        )
        self._records.append(record)
        return record


def _make_plan(tasks: list[dict[str, Any]]) -> ExecutionPlan:
    nodes = [
        TaskNode(
            id=task["id"],
            description=task["description"],
            dependencies=task.get("dependencies", []),
        )
        for task in tasks
    ]
    return ExecutionPlan(
        ordered_tasks=nodes,
        execution_groups=[ExecutionGroup(group_id=0, task_ids=[node.id for node in nodes])],
        metadata=PlanMetadata(total_tasks=len(nodes), has_cycles=False),
    )


def _make_report(
    tasks: list[ExecutionTask],
    status: ExecutionStatus,
) -> ExecutionReport:
    return ExecutionReport(
        tasks=tasks,
        status=status,
        total_tasks=len(tasks),
        completed_tasks=sum(1 for task in tasks if task.status == ExecutionStatus.COMPLETED),
        failed_tasks=sum(1 for task in tasks if task.status == ExecutionStatus.FAILED),
        skipped_tasks=sum(1 for task in tasks if task.status == ExecutionStatus.SKIPPED),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )


def test_full_orchestration_flow_completes() -> None:
    memory = StubMemoryService()
    call_order: list[str] = []

    def planning_engine(tasks: list[dict[str, Any]]) -> ExecutionPlan:
        call_order.append("planning")
        return _make_plan(tasks)

    def execution_engine(
        plan: ExecutionPlan,
        handlers: dict[str, Any],
        stop_on_failure: bool,
    ) -> ExecutionReport:
        call_order.append("execution")
        _ = handlers, stop_on_failure
        tasks = [
            ExecutionTask(id=node.id, description=node.description, status=ExecutionStatus.COMPLETED)
            for node in plan.ordered_tasks
        ]
        return _make_report(tasks, ExecutionStatus.COMPLETED)

    def improvement_runner(memory_service: Any) -> AdaptationResult:
        call_order.append("improving")
        _ = memory_service
        return AdaptationResult()

    controller = OrchestrationController(
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        memory_service=memory,
        self_improvement_runner=improvement_runner,
    )

    result = controller.run(
        OrchestrationRequest(
            run_id="run-001",
            goal="Ship feature",
            tasks=[{"id": "task-1", "description": "Build feature", "dependencies": []}],
        )
    )

    assert result.state == SystemState.COMPLETED
    assert result.status == "completed"
    assert [trace.phase for trace in result.phase_traces] == [
        "planning",
        "executing",
        "validating",
        "reflecting",
        "improving",
    ]
    assert [transition.to_state for transition in result.state_snapshot.transitions] == [
        SystemState.PLANNING,
        SystemState.EXECUTING,
        SystemState.VALIDATING,
        SystemState.REFLECTING,
        SystemState.IMPROVING,
        SystemState.COMPLETED,
    ]
    assert call_order == ["planning", "execution", "improving"]
    assert len(memory.execution_calls) == 1
    assert len(memory.task_calls) == 1
    assert len(memory.decision_calls) == 1


def test_execution_transient_failure_retries_deterministically() -> None:
    memory = StubMemoryService()
    attempts = {"count": 0}

    def planning_engine(tasks: list[dict[str, Any]]) -> ExecutionPlan:
        return _make_plan(tasks)

    def execution_engine(
        plan: ExecutionPlan,
        handlers: dict[str, Any],
        stop_on_failure: bool,
    ) -> ExecutionReport:
        _ = plan, handlers, stop_on_failure
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TransientFailureError("temporary outage")
        return _make_report(
            [
                ExecutionTask(
                    id="task-1",
                    description="Build feature",
                    status=ExecutionStatus.COMPLETED,
                )
            ],
            ExecutionStatus.COMPLETED,
        )

    controller = OrchestrationController(
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        memory_service=memory,
        self_improvement_runner=lambda _: AdaptationResult(),
    )

    result = controller.run(
        OrchestrationRequest(
            run_id="run-002",
            goal="Retry transient execution",
            tasks=[{"id": "task-1", "description": "Build feature", "dependencies": []}],
        )
    )

    assert result.state == SystemState.COMPLETED
    assert attempts["count"] == 2
    assert len(result.recovery_attempts) == 1
    assert result.recovery_attempts[0].phase == "executing"
    assert result.recovery_attempts[0].will_retry is True


def test_failed_execution_still_reaches_improvement_then_finishes_failed() -> None:
    memory = StubMemoryService()

    def planning_engine(tasks: list[dict[str, Any]]) -> ExecutionPlan:
        return _make_plan(tasks)

    def execution_engine(
        plan: ExecutionPlan,
        handlers: dict[str, Any],
        stop_on_failure: bool,
    ) -> ExecutionReport:
        _ = plan, handlers, stop_on_failure
        task = ExecutionTask(
            id="task-1",
            description="Build feature",
            status=ExecutionStatus.FAILED,
            error="boom",
        )
        return _make_report([task], ExecutionStatus.FAILED)

    approved = SelfImprovementAdaptation(
        adaptation_id="adapt-001",
        source_pattern_id="pattern-001",
        description="Increase retry depth",
        expected_effect="fewer transient task failures",
        action_type=ImprovementType.CHANGE_STRATEGY,
        target="execution_engine",
        value={"max_retries": 2},
        confidence_score=0.8,
    )

    controller = OrchestrationController(
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        memory_service=memory,
        self_improvement_runner=lambda _: AdaptationResult(
            adaptations_approved=[approved],
        ),
    )

    result = controller.run(
        OrchestrationRequest(
            run_id="run-003",
            goal="Handle failure",
            tasks=[{"id": "task-1", "description": "Build feature", "dependencies": []}],
        )
    )

    assert result.state == SystemState.FAILED
    assert result.execution_report is not None
    assert result.execution_report.status == ExecutionStatus.FAILED
    assert len(memory.failure_calls) == 1
    assert len(memory.improvement_calls) == 1
    assert len(result.improvement_result.adaptations_approved) == 1


def test_validation_failure_escalates_to_failed_state() -> None:
    memory = StubMemoryService()

    def planning_engine(tasks: list[dict[str, Any]]) -> ExecutionPlan:
        return _make_plan(tasks)

    def execution_engine(
        plan: ExecutionPlan,
        handlers: dict[str, Any],
        stop_on_failure: bool,
    ) -> ExecutionReport:
        _ = handlers, stop_on_failure
        task = ExecutionTask(
            id=plan.ordered_tasks[0].id,
            description=plan.ordered_tasks[0].description,
            status=ExecutionStatus.COMPLETED,
        )
        report = _make_report([task], ExecutionStatus.COMPLETED)
        report.total_tasks = 2
        return report

    controller = OrchestrationController(
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        memory_service=memory,
        self_improvement_runner=lambda _: AdaptationResult(),
    )

    result = controller.run(
        OrchestrationRequest(
            run_id="run-004",
            goal="Detect invalid report",
            tasks=[{"id": "task-1", "description": "Build feature", "dependencies": []}],
        )
    )

    assert result.state == SystemState.FAILED
    assert result.error == "execution report task count does not match total_tasks"
    assert len(memory.execution_calls) == 0