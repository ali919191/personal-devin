"""Agent 31 deterministic loop controller.

Lifecycle:
Plan -> Execute -> Evaluate -> Decide -> Repeat
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from app.core.logger import get_logger
from app.execution.hooks.execution_hooks import execute_with_policy
from app.execution.policy.execution_policy import ExecutionPolicy
from app.execution.runner import run_plan
from app.memory.memory_store import MemoryStore
from app.planning.planner import build_execution_plan


class PlannerProtocol(Protocol):
    """Planner interface expected by the loop controller."""

    def create_plan(self, state: dict[str, Any], context: dict[str, Any] | None = None) -> Any:
        """Build an execution plan from explicit state."""


class ExecutorProtocol(Protocol):
    """Executor interface expected by the loop controller."""

    def run(self, plan: Any) -> dict[str, Any]:
        """Execute a plan and return a dict result payload."""


class MemoryProtocol(Protocol):
    """Memory persistence interface expected by the loop controller."""

    def save(self, record: dict[str, Any]) -> None:
        """Persist a loop record."""

    def retrieve(self, goal: str) -> dict[str, Any]:
        """Retrieve deterministic memory context for a goal."""


class PlanningEngine:
    """Adapter over the existing planning engine module."""

    def create_plan(self, state: dict[str, Any], context: dict[str, Any] | None = None) -> Any:
        tasks = state.get("tasks")
        if not isinstance(tasks, list) or len(tasks) == 0:
            goal = str(state.get("goal", ""))
            adjustment_suffix = ""
            if state.get("last_decision") == "adjust_plan":
                adjustment_suffix = " [adjusted]"

            tasks = [
                {
                    "id": "goal_task",
                    "description": (goal or "execute_goal") + adjustment_suffix,
                    "dependencies": [],
                    "metadata": {
                        "source": "loop_controller",
                        "attempt_count": int(state.get("attempt_count", 0)),
                        "last_failure_reason": state.get("last_failure_reason"),
                        "context_records": len((context or {}).get("recent", [])),
                    },
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

        try:
            output = execute_with_policy(
                execution_engine=self._execute_with_existing_runner,
                request=request,
                policy=self._policy,
            )
        except Exception as exc:  # noqa: BLE001
            return self._classify_exception(exc)

        if isinstance(output, dict):
            normalized = dict(output)
            normalized.setdefault("error_type", "none" if normalized.get("success") else "runtime_error")
            normalized.setdefault("retryable", False if normalized.get("success") else True)
            return normalized
        return {
            "success": False,
            "status": "failed",
            "error_type": "invalid_output",
            "retryable": False,
            "error": "invalid_execution_output",
        }

    def _classify_exception(self, exc: Exception) -> dict[str, Any]:
        name = exc.__class__.__name__.lower()
        message = str(exc)
        if "policy" in name:
            return {
                "success": False,
                "status": "failed",
                "error_type": "policy_violation",
                "retryable": False,
                "error": message,
            }
        if "valueerror" in name or "typeerror" in name:
            return {
                "success": False,
                "status": "failed",
                "error_type": "invalid_plan",
                "retryable": False,
                "error": message,
            }
        return {
            "success": False,
            "status": "failed",
            "error_type": "runtime_error",
            "retryable": True,
            "error": message,
        }

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

    def retrieve(self, goal: str) -> dict[str, Any]:
        recent = self._store.get_recent(50)
        matching = [item for item in recent if str(item.get("goal", "")) == goal]
        failures = [item for item in matching if not bool(item.get("success", False))]
        return {
            "goal": goal,
            "recent": matching,
            "recent_failures": failures,
            "attempt_count": len(matching),
        }


Decision = Literal["retry_same", "adjust_plan", "abort", "escalate"]


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
        decision: Decision = "retry_same"
        context = self._retrieve_context(goal)

        state: dict[str, Any] = {
            "goal": goal,
            "history": [],
            "memory_context": context,
            "attempt_count": 0,
            "last_failure_reason": None,
            "last_error_type": None,
            "last_retryable": None,
            "last_decision": None,
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
            state["attempt_count"] = iteration
            plan = self._create_plan(state, context)
            self._log_event(
                event="plan_generated",
                iteration_id=iteration_id,
                input_payload={"state": self._state_snapshot(state), "context": context},
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
            classification = self._classify_result(result)
            success = classification["success"]
            state["last_failure_reason"] = classification.get("reason")
            state["last_error_type"] = classification.get("error_type")
            state["last_retryable"] = classification.get("retryable")
            self._log_event(
                event="result_evaluated",
                iteration_id=iteration_id,
                input_payload={"result": result},
                output_payload=classification,
                decision="persist_memory",
            )

            # 4. DECISION
            decision = self._decide_next_step(state, classification)
            state["last_decision"] = decision

            # 5. MEMORY STORE
            record = {
                "iteration_id": iteration_id,
                "timestamp": self._clock().isoformat(),
                "goal": goal,
                "plan": self._safe_payload(plan),
                "result": result,
                "classification": classification,
                "success": success,
                "decision": decision,
            }
            self.memory.save(record)
            self._log_event(
                event="memory_persisted",
                iteration_id=iteration_id,
                input_payload={"record": record},
                output_payload={"saved": True},
                decision="decide_next_step",
            )

            # 6. TRACK HISTORY
            state["history"].append(
                {
                    "plan": self._safe_payload(plan),
                    "result": result,
                    "classification": classification,
                    "decision": decision,
                }
            )

            if success and decision == "abort":
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

            if decision == "escalate":
                self._log_event(
                    event="escalation_requested",
                    iteration_id=iteration_id,
                    input_payload={"classification": classification, "failures": failures},
                    output_payload={"status": "failed"},
                    decision="stop_escalate",
                )
                return {
                    "status": "failed",
                    "iterations": iteration,
                    "reason": "escalated",
                    "error_type": classification.get("error_type"),
                }

            if decision == "abort":
                self._log_event(
                    event="abort_requested",
                    iteration_id=iteration_id,
                    input_payload={"classification": classification, "failures": failures},
                    output_payload={"status": "failed"},
                    decision="stop_abort",
                )
                return {
                    "status": "failed",
                    "iterations": iteration,
                    "reason": "abort",
                    "error_type": classification.get("error_type"),
                }

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

            context = self._retrieve_context(goal)
            state["memory_context"] = context
            self._log_event(
                event="continue_iteration",
                iteration_id=iteration_id,
                input_payload={"failures": failures, "decision": decision},
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

    def _retrieve_context(self, goal: str) -> dict[str, Any]:
        if hasattr(self.memory, "retrieve"):
            try:
                context = self.memory.retrieve(goal)
                if isinstance(context, dict):
                    return self._safe_payload(context)
            except Exception:  # noqa: BLE001
                return {"goal": goal, "recent": [], "recent_failures": [], "attempt_count": 0}

        store = getattr(self.memory, "_store", None)
        if isinstance(store, MemoryStore):
            recent = store.get_recent(20)
            return {
                "goal": goal,
                "recent": [self._safe_payload(item) for item in recent],
                "recent_failures": [
                    self._safe_payload(item) for item in recent if not bool(item.get("success", False))
                ],
                "attempt_count": len(recent),
            }
        return {"goal": goal, "recent": [], "recent_failures": [], "attempt_count": 0}

    def _create_plan(self, state: dict[str, Any], context: dict[str, Any]) -> Any:
        try:
            return self.planner.create_plan(state, context)
        except TypeError:
            return self.planner.create_plan(state)

    def _classify_result(self, result: dict[str, Any]) -> dict[str, Any]:
        success = bool(result.get("success", False))
        error_type = str(result.get("error_type", "none" if success else "runtime_error"))
        retryable = bool(result.get("retryable", not success and error_type == "runtime_error"))
        reason = str(result.get("error") or result.get("status") or ("success" if success else error_type))
        return {
            "success": success,
            "error_type": error_type,
            "retryable": retryable,
            "reason": reason,
        }

    def _decide_next_step(self, state: dict[str, Any], classification: dict[str, Any]) -> Decision:
        if bool(classification.get("success", False)):
            return "abort"

        error_type = str(classification.get("error_type", "runtime_error"))
        retryable = bool(classification.get("retryable", False))
        attempt_count = int(state.get("attempt_count", 0))

        if error_type in {"policy_violation", "security_violation"}:
            return "escalate"

        if error_type == "invalid_plan":
            return "adjust_plan"

        if retryable and attempt_count < self.failure_threshold:
            return "retry_same"

        if retryable:
            return "adjust_plan"

        return "abort"

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
            "attempt_count": int(state.get("attempt_count", 0)),
            "last_failure_reason": state.get("last_failure_reason"),
            "last_error_type": state.get("last_error_type"),
            "last_retryable": state.get("last_retryable"),
            "last_decision": state.get("last_decision"),
            "history_size": len(history) if isinstance(history, list) else 0,
            "memory_context_size": len(memory_context.get("recent", []))
            if isinstance(memory_context, dict)
            else 0,
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
