"""Agent 31 deterministic loop controller.

Lifecycle:
Plan -> Execute -> Evaluate -> Decide -> Repeat
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.logger import get_logger
from app.execution.hooks.execution_hooks import execute_with_policy
from app.execution.policy.execution_policy import ExecutionPolicy
from app.execution.runner import run_plan
from app.memory.memory_store import MemoryStore
from app.planning.planner import build_execution_plan


class PlannerProtocol(Protocol):
    """Planner interface expected by the loop controller."""

    def create_plan(self, state: dict[str, Any]) -> Any:
        """Build an execution plan from explicit state."""


class ExecutorProtocol(Protocol):
    """Executor interface expected by the loop controller."""

    def run(self, plan: Any) -> dict[str, Any]:
        """Execute a plan and return a dict result payload."""


class MemoryProtocol(Protocol):
    """Memory persistence interface expected by the loop controller."""

    def save(self, record: dict[str, Any]) -> None:
        """Persist a loop record."""


class PlanningEngine:
    """Adapter over the existing planning engine module."""

    def create_plan(self, state: dict[str, Any]) -> Any:
        tasks = state.get("tasks")
        if not isinstance(tasks, list) or len(tasks) == 0:
            goal = str(state.get("goal", ""))
            tasks = [
                {
                    "id": "goal_task",
                    "description": goal or "execute_goal",
                    "dependencies": [],
                    "metadata": {"source": "loop_controller"},
                }
            ]
        return build_execution_plan(tasks)


class ExecutionRunner:
    """Adapter over the existing execution runner using policy hook entrypoint."""

    def __init__(self, policy: ExecutionPolicy | None = None) -> None:
        self._policy = policy or ExecutionPolicy(
            allowed_operations=("run_plan",),
            allowed_environments=("local",),
        )

    def run(self, plan: Any) -> dict[str, Any]:
        request = {
            "operation": "run_plan",
            "environment": "local",
            "runtime_seconds": 0,
            "plan": plan,
        }

        output = execute_with_policy(
            execution_engine=self._execute_with_existing_runner,
            request=request,
            policy=self._policy,
        )
        if isinstance(output, dict):
            return output
        return {"success": False, "status": "failed", "error": "invalid_execution_output"}

    def _execute_with_existing_runner(self, request: dict[str, Any]) -> dict[str, Any]:
        plan = request.get("plan")
        report = run_plan(plan)
        status = str(report.status.value)
        payload = {
            "success": status == "completed",
            "status": status,
            "total_tasks": report.total_tasks,
            "completed_tasks": report.completed_tasks,
            "failed_tasks": report.failed_tasks,
            "skipped_tasks": report.skipped_tasks,
            "tasks": [task.model_dump(mode="json") for task in report.tasks],
            "started_at": report.started_at.isoformat(),
            "completed_at": report.completed_at.isoformat() if report.completed_at else None,
        }
        return payload


class FileMemoryStore:
    """Adapter over the existing file-based memory store."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or MemoryStore()

    def save(self, record: dict[str, Any]) -> None:
        self._store.store_execution(record)


class LoopController:
    """Deterministic sequential orchestration loop for Agent 31."""

    def __init__(
        self,
        planner: PlannerProtocol,
        executor: ExecutorProtocol,
        memory: MemoryProtocol,
        max_iterations: int = 10,
        failure_threshold: int = 3,
        clock: Callable[[], datetime] | None = None,
    ):
        self.planner = planner
        self.executor = executor
        self.memory = memory
        self.max_iterations = max_iterations
        self.failure_threshold = failure_threshold
        self._clock = clock or (lambda: datetime.now(UTC))
        self.logger = get_logger(__name__)

    def run(self, goal: str) -> dict[str, Any]:
        iteration = 0
        failures = 0

        state: dict[str, Any] = {
            "goal": goal,
            "history": [],
            "memory_context": self._load_memory_context(limit=20),
        }

        while iteration < self.max_iterations:
            iteration += 1
            iteration_id = f"iter-{iteration:04d}"

            self._log_event(
                event="iteration_start",
                iteration_id=iteration_id,
                input_payload={"goal": goal, "state": self._state_snapshot(state)},
                output_payload={},
                decision="plan",
            )

            # 1. PLAN
            plan = self.planner.create_plan(state)
            self._log_event(
                event="plan_generated",
                iteration_id=iteration_id,
                input_payload={"state": self._state_snapshot(state)},
                output_payload=self._safe_payload(plan),
                decision="execute",
            )

            # 2. EXECUTE
            result = self.executor.run(plan)
            self._log_event(
                event="plan_executed",
                iteration_id=iteration_id,
                input_payload=self._safe_payload(plan),
                output_payload=result,
                decision="evaluate",
            )

            # 3. EVALUATE
            success = bool(result.get("success", False))
            self._log_event(
                event="result_evaluated",
                iteration_id=iteration_id,
                input_payload={"result": result},
                output_payload={"success": success},
                decision="persist_memory",
            )

            # 4. MEMORY STORE
            record = {
                "iteration_id": iteration_id,
                "timestamp": self._clock().isoformat(),
                "goal": goal,
                "plan": self._safe_payload(plan),
                "result": result,
                "success": success,
            }
            self.memory.save(record)
            self._log_event(
                event="memory_persisted",
                iteration_id=iteration_id,
                input_payload={"record": record},
                output_payload={"saved": True},
                decision="decide_next_step",
            )

            # 5. TRACK HISTORY
            state["history"].append({"plan": self._safe_payload(plan), "result": result})

            # 6. DECISION
            if success:
                self._log_event(
                    event="goal_achieved",
                    iteration_id=iteration_id,
                    input_payload={"result": result},
                    output_payload={"status": "success"},
                    decision="stop_success",
                )
                return {
                    "status": "success",
                    "iterations": iteration,
                    "result": result,
                }

            failures += 1

            if failures >= self.failure_threshold:
                self._log_event(
                    event="failure_threshold_exceeded",
                    iteration_id=iteration_id,
                    input_payload={"failures": failures, "result": result},
                    output_payload={"status": "failed"},
                    decision="stop_failure_threshold",
                )
                return {
                    "status": "failed",
                    "iterations": iteration,
                    "reason": "failure_threshold",
                }

            state["memory_context"] = self._load_memory_context(limit=20)
            self._log_event(
                event="continue_iteration",
                iteration_id=iteration_id,
                input_payload={"failures": failures},
                output_payload={"next_iteration": iteration + 1},
                decision="repeat",
            )

        self._log_event(
            event="max_iterations_reached",
            iteration_id=f"iter-{iteration:04d}",
            input_payload={"iterations": iteration, "failures": failures},
            output_payload={"status": "stopped"},
            decision="stop_max_iterations",
        )
        return {
            "status": "stopped",
            "iterations": iteration,
            "reason": "max_iterations",
        }

    def _load_memory_context(self, limit: int) -> list[dict[str, Any]]:
        store = getattr(self.memory, "_store", None)
        if isinstance(store, MemoryStore):
            recent = store.get_recent(limit)
            return [self._safe_payload(item) for item in recent]
        return []

    def _log_event(
        self,
        *,
        event: str,
        iteration_id: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        decision: str,
    ) -> None:
        self.logger.info(
            event,
            {
                "iteration_id": iteration_id,
                "input": self._safe_payload(input_payload),
                "output": self._safe_payload(output_payload),
                "decision": decision,
                "timestamp": self._clock().isoformat(),
            },
        )

    def _safe_payload(self, payload: Any) -> Any:
        if hasattr(payload, "model_dump"):
            try:
                return payload.model_dump(mode="json")
            except TypeError:
                return payload.model_dump()
        if isinstance(payload, dict):
            return {str(key): self._safe_payload(value) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self._safe_payload(value) for value in payload]
        if isinstance(payload, tuple):
            return [self._safe_payload(value) for value in payload]
        if isinstance(payload, (str, int, float, bool)) or payload is None:
            return payload
        return str(payload)

    def _state_snapshot(self, state: dict[str, Any]) -> dict[str, Any]:
        history = state.get("history", [])
        memory_context = state.get("memory_context", [])
        return {
            "goal": str(state.get("goal", "")),
            "history_size": len(history) if isinstance(history, list) else 0,
            "memory_context_size": len(memory_context) if isinstance(memory_context, list) else 0,
        }


def build_default_loop_controller(
    *,
    max_iterations: int = 10,
    failure_threshold: int = 3,
    memory_store: MemoryStore | None = None,
    clock: Callable[[], datetime] | None = None,
) -> LoopController:
    """Create a LoopController wired to existing planning/execution/memory layers."""
    planner = PlanningEngine()
    executor = ExecutionRunner()
    memory = FileMemoryStore(memory_store)
    return LoopController(
        planner=planner,
        executor=executor,
        memory=memory,
        max_iterations=max_iterations,
        failure_threshold=failure_threshold,
        clock=clock,
    )
