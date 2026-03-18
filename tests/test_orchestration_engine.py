from dataclasses import dataclass
from typing import Any

from app.improvement.models import ImprovementResult, SignalRecord
from app.orchestration.models import OrchestrationRequest
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.registry import OrchestrationRegistry


@dataclass
class StubPlanMetadata:
    total_tasks: int


@dataclass
class StubPlan:
    metadata: StubPlanMetadata


@dataclass
class StubExecutionResult:
    status: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    skipped_tasks: int


@dataclass
class StubMemoryRecord:
    id: str


@dataclass
class StubAgentLoopResult:
    status: str


class StubMemorySystem:
    def __init__(self) -> None:
        self.execution_calls: list[dict[str, Any]] = []
        self.failure_calls: list[dict[str, Any]] = []

    def log_execution(
        self,
        status: str,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int,
        skipped_tasks: int,
        metadata: dict | None = None,
    ) -> StubMemoryRecord:
        self.execution_calls.append(
            {
                "status": status,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "skipped_tasks": skipped_tasks,
                "metadata": metadata or {},
            }
        )
        return StubMemoryRecord(id=f"execution-{len(self.execution_calls):06d}")

    def log_failure(self, source: str, error: str, context: dict | None = None) -> StubMemoryRecord:
        self.failure_calls.append(
            {
                "source": source,
                "error": error,
                "context": context or {},
            }
        )
        return StubMemoryRecord(id=f"failure-{len(self.failure_calls):06d}")


class StubAgentLoop:
    def __init__(self, status: str = "success") -> None:
        self.status = status
        self.calls: list[str] = []

    def run(self, goal: str) -> StubAgentLoopResult:
        self.calls.append(goal)
        return StubAgentLoopResult(status=self.status)


class StubImprovementEngine:
    def __init__(self) -> None:
        self.select_calls: list[list[SignalRecord]] = []
        self.apply_calls: list[list] = []

    def select_actions(self, signals):
        self.select_calls.append(list(signals))
        actions = []
        for signal in signals:
            if signal.signal_type == "low_success_rate":
                actions.append({"action_type": "retry_strategy", "source_signal": signal.signal_type})
        return actions

    def apply(self, actions):
        self.apply_calls.append(list(actions))
        results: list[ImprovementResult] = []
        for action in actions:
            results.append(ImprovementResult(action_type=action["action_type"], status="applied"))
        return results


class RecordingAgentLoop:
    def __init__(self, call_order: list[str], status: str = "success") -> None:
        self._call_order = call_order
        self._status = status

    def run(self, goal: str) -> StubAgentLoopResult:
        self._call_order.append("agent_loop")
        _ = goal
        return StubAgentLoopResult(status=self._status)


class RecordingImprovementEngine:
    def __init__(self, call_order: list[str]) -> None:
        self._call_order = call_order

    def select_actions(self, signals):
        self._call_order.append("improvement_select")
        return [{"action_type": "retry_strategy", "source_signal": signal.signal_type} for signal in signals]

    def apply(self, actions):
        self._call_order.append("improvement_apply")
        return [ImprovementResult(action_type=action["action_type"], status="applied") for action in actions]


def _build_registry(
    planning_engine,
    execution_engine,
    memory_system: StubMemorySystem | None = None,
    agent_loop: StubAgentLoop | None = None,
    improvement_engine: StubImprovementEngine | None = None,
) -> OrchestrationRegistry:
    return OrchestrationRegistry(
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        memory_system=memory_system or StubMemorySystem(),
        agent_loop=agent_loop or StubAgentLoop(),
        improvement_engine=improvement_engine or StubImprovementEngine(),
    )


def test_full_successful_run() -> None:
    memory = StubMemorySystem()
    agent_loop = StubAgentLoop(status="success")
    improvement = StubImprovementEngine()

    registry = _build_registry(
        planning_engine=lambda tasks: StubPlan(metadata=StubPlanMetadata(total_tasks=len(tasks))),
        execution_engine=lambda plan: StubExecutionResult(
            status="completed",
            total_tasks=plan.metadata.total_tasks,
            completed_tasks=plan.metadata.total_tasks,
            failed_tasks=0,
            skipped_tasks=0,
        ),
        memory_system=memory,
        agent_loop=agent_loop,
        improvement_engine=improvement,
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(run_id="run-001", goal="Ship feature")

    result = orchestrator.run(request)

    assert result.status == "success"
    assert result.context.status == "success"
    assert len(memory.execution_calls) == 1
    assert agent_loop.calls == ["Ship feature"]
    assert len(result.context.improvements) == 0


def test_planning_failure() -> None:
    registry = _build_registry(
        planning_engine=lambda tasks: (_ for _ in ()).throw(ValueError("planning failed")),
        execution_engine=lambda plan: StubExecutionResult(
            status="completed",
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            skipped_tasks=0,
        ),
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(run_id="run-002", goal="Bad plan")

    result = orchestrator.run(request)

    assert result.status == "failed"
    assert result.error == "planning failed"
    assert result.context.plan is None
    assert result.context.execution_result is None


def test_execution_failure_continues_to_reflection() -> None:
    memory = StubMemorySystem()
    agent_loop = StubAgentLoop(status="partial")

    registry = _build_registry(
        planning_engine=lambda tasks: StubPlan(metadata=StubPlanMetadata(total_tasks=1)),
        execution_engine=lambda plan: StubExecutionResult(
            status="failed",
            total_tasks=1,
            completed_tasks=0,
            failed_tasks=1,
            skipped_tasks=0,
        ),
        memory_system=memory,
        agent_loop=agent_loop,
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(run_id="run-003", goal="Execution failure")

    result = orchestrator.run(request)

    assert result.status == "failed"
    assert agent_loop.calls == ["Execution failure"]
    assert len(memory.execution_calls) == 1
    assert len(memory.failure_calls) == 1


def test_partial_failure_integrity_execution_failure_still_improves() -> None:
    memory = StubMemorySystem()
    agent_loop = StubAgentLoop(status="partial")
    improvement = StubImprovementEngine()

    registry = _build_registry(
        planning_engine=lambda tasks: StubPlan(metadata=StubPlanMetadata(total_tasks=1)),
        execution_engine=lambda plan: (_ for _ in ()).throw(RuntimeError("boom")),
        memory_system=memory,
        agent_loop=agent_loop,
        improvement_engine=improvement,
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(
        run_id="run-003b",
        goal="Execution failure with improvement",
        signals=[SignalRecord(signal_type="low_success_rate", signal_value="0.3")],
    )

    result = orchestrator.run(request)

    assert result.status == "failed"
    assert len(memory.execution_calls) == 1
    assert len(memory.failure_calls) == 1
    assert len(agent_loop.calls) == 1
    assert len(improvement.select_calls) == 1
    assert len(improvement.apply_calls) == 1
    assert len(result.context.improvements) == 1


def test_memory_integration_records_references() -> None:
    memory = StubMemorySystem()

    registry = _build_registry(
        planning_engine=lambda tasks: StubPlan(metadata=StubPlanMetadata(total_tasks=1)),
        execution_engine=lambda plan: StubExecutionResult(
            status="completed",
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            skipped_tasks=0,
        ),
        memory_system=memory,
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(run_id="run-004", goal="Store state")

    result = orchestrator.run(request)

    assert result.context.memory_refs == ["execution-000001"]
    assert memory.execution_calls[0]["metadata"]["run_id"] == "run-004"


def test_improvement_triggered() -> None:
    improvement = StubImprovementEngine()

    registry = _build_registry(
        planning_engine=lambda tasks: StubPlan(metadata=StubPlanMetadata(total_tasks=1)),
        execution_engine=lambda plan: StubExecutionResult(
            status="completed",
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            skipped_tasks=0,
        ),
        improvement_engine=improvement,
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(
        run_id="run-005",
        goal="Improve execution",
        signals=[SignalRecord(signal_type="low_success_rate", signal_value="0.4")],
    )

    result = orchestrator.run(request)

    assert len(result.context.improvements) == 1
    assert result.context.improvements[0].action_type == "retry_strategy"
    assert result.context.improvements[0].status == "applied"


def test_deterministic_output() -> None:
    registry = _build_registry(
        planning_engine=lambda tasks: StubPlan(metadata=StubPlanMetadata(total_tasks=len(tasks))),
        execution_engine=lambda plan: StubExecutionResult(
            status="completed",
            total_tasks=plan.metadata.total_tasks,
            completed_tasks=plan.metadata.total_tasks,
            failed_tasks=0,
            skipped_tasks=0,
        ),
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(
        run_id="run-006",
        goal="Determinism",
        tasks=[{"id": "task-1", "description": "Determinism", "dependencies": []}],
    )

    first = orchestrator.run(request)
    second = orchestrator.run(request)

    assert first.status == second.status
    assert first.context.status == second.context.status
    assert first.context.timestamps == second.context.timestamps
    assert first.context.trace == second.context.trace
    assert len(first.context.memory_refs) == len(second.context.memory_refs)
    assert first.context.memory_refs[0].startswith("execution-")
    assert second.context.memory_refs[0].startswith("execution-")
    assert first.error == second.error


def test_trace_integrity() -> None:
    registry = _build_registry(
        planning_engine=lambda tasks: StubPlan(metadata=StubPlanMetadata(total_tasks=len(tasks))),
        execution_engine=lambda plan: StubExecutionResult(
            status="completed",
            total_tasks=plan.metadata.total_tasks,
            completed_tasks=plan.metadata.total_tasks,
            failed_tasks=0,
            skipped_tasks=0,
        ),
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(run_id="run-trace", goal="Trace check")

    result = orchestrator.run(request)

    assert len(result.context.trace) >= 5
    assert result.context.trace[0]["stage"] == "planning"
    assert result.context.trace[0]["status"] == "start"


def test_registry_injection_is_used_for_all_components() -> None:
    call_order: list[str] = []
    memory = StubMemorySystem()
    agent_loop = RecordingAgentLoop(call_order=call_order, status="success")
    improvement = RecordingImprovementEngine(call_order=call_order)

    def planning_engine(tasks):
        call_order.append("planning")
        return StubPlan(metadata=StubPlanMetadata(total_tasks=len(tasks)))

    def execution_engine(plan):
        call_order.append("execution")
        return StubExecutionResult(
            status="completed",
            total_tasks=plan.metadata.total_tasks,
            completed_tasks=plan.metadata.total_tasks,
            failed_tasks=0,
            skipped_tasks=0,
        )

    registry = OrchestrationRegistry(
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        memory_system=memory,
        agent_loop=agent_loop,
        improvement_engine=improvement,
    )

    orchestrator = Orchestrator(registry=registry)
    request = OrchestrationRequest(
        run_id="run-007",
        goal="Registry injection",
        signals=[SignalRecord(signal_type="low_success_rate", signal_value="0.4")],
    )

    result = orchestrator.run(request)

    assert result.status == "success"
    assert call_order == [
        "planning",
        "execution",
        "agent_loop",
        "improvement_select",
        "improvement_apply",
    ]
