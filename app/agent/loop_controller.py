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
                        "strategy_hint": state.get("strategy_hint", "none"),
                        "context_records": len((context or {}).get("recent", [])),
                    },
                }
            ]

        execution_plan = build_execution_plan(tasks)
        steps = [
            {
                "id": node.id,
                "action": node.description,
                "dependencies": list(node.dependencies),
                "metadata": self._safe_task_metadata(node.metadata),
            }
            for node in execution_plan.ordered_tasks
        ]
        return {
            "steps": steps,
            "current_step": 0,
        }

    def _safe_task_metadata(self, metadata: Any) -> dict[str, Any]:
        if isinstance(metadata, dict):
            return dict(metadata)
        return {}


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
        raw_plan = request.get("plan")
        plan = self._normalize_plan_for_runner(raw_plan)
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

    def _normalize_plan_for_runner(self, raw_plan: Any) -> Any:
        if hasattr(raw_plan, "ordered_tasks"):
            return raw_plan

        if isinstance(raw_plan, dict) and "action" in raw_plan:
            return self._single_step_to_execution_plan(raw_plan)

        if isinstance(raw_plan, dict) and isinstance(raw_plan.get("steps"), list):
            steps = raw_plan.get("steps")
            current_index = int(raw_plan.get("current_step", 0))
            if 0 <= current_index < len(steps):
                selected = steps[current_index]
                if isinstance(selected, dict):
                    return self._single_step_to_execution_plan(selected)

        raise ValueError("Unsupported plan format for execution runner")

    def _single_step_to_execution_plan(self, step: dict[str, Any]) -> Any:
        step_id = str(step.get("id", "step_1"))
        action = str(step.get("action", "execute_step"))
        metadata = step.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        tasks = [
            {
                "id": step_id,
                "description": action,
                "dependencies": [],
                "metadata": dict(metadata),
            }
        ]
        return build_execution_plan(tasks)


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


Decision = Literal["retry_same", "adjust_plan", "abort", "escalate", "advance_step"]


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
        self.strategy_stats: dict[str, dict[str, dict[str, float | int]]] = {}

    def run(self, goal: str) -> dict[str, Any]:
        iteration = 0
        failures = 0
        decision: Decision = "retry_same"
        context = self._retrieve_context(goal)
        self._merge_strategy_stats(self._build_strategy_stats_from_context(context))

        state: dict[str, Any] = {
            "goal": goal,
            "history": [],
            "memory_context": context,
            "active_plan": None,
            "step_history": [],
            "current_step_failures": {},
            "attempt_count": 0,
            "last_failure_reason": None,
            "last_error_type": None,
            "last_retryable": None,
            "last_decision": None,
            "strategy_hint": "none",
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
            plan = self._ensure_step_plan(state, context)
            current_step = self._current_step(plan)

            if current_step is None:
                self._log_event(
                    event="all_steps_completed",
                    iteration_id=iteration_id,
                    input_payload={"plan": plan},
                    output_payload={"status": "success"},
                    decision="stop_success",
                )
                return {
                    "status": "success",
                    "iterations": iteration - 1,
                    "result": {
                        "success": True,
                        "steps_completed": len(plan.get("steps", [])) if isinstance(plan, dict) else 0,
                    },
                }

            self._log_event(
                event="plan_generated",
                iteration_id=iteration_id,
                input_payload={"state": self._state_snapshot(state), "context": context},
                output_payload={"plan": self._safe_payload(plan), "current_step": current_step},
                decision="execute",
            )

            # 2. EXECUTE (step-level)
            result = self.executor.run(current_step)
            self._log_event(
                event="plan_executed",
                iteration_id=iteration_id,
                input_payload={"current_step": self._safe_payload(current_step)},
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

            strategy_pattern = str(classification.get("error_type", "none"))
            if success:
                decision = "advance_step"
                self._advance_step(plan, state)
            else:
                self._increment_step_failure(state, current_step)
                decision = self._decide_next_step(state, classification)

            state["last_decision"] = decision
            state["strategy_hint"] = self._build_strategy_hint(decision, classification)

            self._update_strategy_stats(
                pattern=strategy_pattern,
                decision=decision,
                success=success,
            )

            # 5. MEMORY STORE
            record = {
                "iteration_id": iteration_id,
                "timestamp": self._clock().isoformat(),
                "goal": goal,
                "plan": self._safe_payload(plan),
                "current_step": self._safe_payload(current_step),
                "result": result,
                "classification": classification,
                "success": success,
                "decision": decision,
                "strategy_pattern": strategy_pattern,
                "strategy_hint": state["strategy_hint"],
                "strategy_stats": self._strategy_snapshot(),
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
                    "current_step": self._safe_payload(current_step),
                    "result": result,
                    "classification": classification,
                    "decision": decision,
                    "strategy_hint": state["strategy_hint"],
                }
            )
            state["step_history"].append(
                {
                    "step": self._safe_payload(current_step),
                    "result": result,
                    "decision": decision,
                    "timestamp": self._clock().isoformat(),
                }
            )

            if success and self._all_steps_completed(plan):
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
                    "result": {
                        **result,
                        "steps_completed": len(plan.get("steps", [])) if isinstance(plan, dict) else 0,
                    },
                }

            if success:
                context = self._retrieve_context(goal)
                state["memory_context"] = context
                self._log_event(
                    event="continue_next_step",
                    iteration_id=iteration_id,
                    input_payload={"decision": decision, "next_step": plan.get("current_step", 0)},
                    output_payload={"next_iteration": iteration + 1},
                    decision="repeat",
                )
                continue

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

            if decision == "adjust_plan":
                self._apply_step_adjustment(plan, state)

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

    def _ensure_step_plan(self, state: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        active = state.get("active_plan")
        if isinstance(active, dict) and isinstance(active.get("steps"), list):
            if state.get("last_decision") == "adjust_plan":
                raw_plan = self._create_plan(state, context)
                active = self._normalize_step_plan(raw_plan, fallback=active)
                state["active_plan"] = active
                return active
            return active

        raw_plan = self._create_plan(state, context)
        active = self._normalize_step_plan(raw_plan)
        state["active_plan"] = active
        return active

    def _normalize_step_plan(
        self,
        raw_plan: Any,
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if isinstance(raw_plan, dict) and isinstance(raw_plan.get("steps"), list):
            steps = [self._normalize_step(step, index) for index, step in enumerate(raw_plan["steps"])]
            current = int(raw_plan.get("current_step", 0))
            if current < 0:
                current = 0
            if current > len(steps):
                current = len(steps)
            return {"steps": steps, "current_step": current}

        if hasattr(raw_plan, "ordered_tasks"):
            steps: list[dict[str, Any]] = []
            for index, task in enumerate(getattr(raw_plan, "ordered_tasks", [])):
                step = {
                    "id": str(getattr(task, "id", f"step_{index + 1}")),
                    "action": str(getattr(task, "description", f"step_{index + 1}")),
                    "dependencies": list(getattr(task, "dependencies", [])),
                    "metadata": dict(getattr(task, "metadata", {}) or {}),
                }
                steps.append(self._normalize_step(step, index))
            return {"steps": steps, "current_step": 0}

        if isinstance(raw_plan, dict):
            step = self._normalize_step(raw_plan, 0)
            return {"steps": [step], "current_step": 0}

        if fallback is not None:
            return {
                "steps": [self._normalize_step(step, idx) for idx, step in enumerate(fallback.get("steps", []))],
                "current_step": int(fallback.get("current_step", 0)),
            }

        return {
            "steps": [self._normalize_step({"id": "step_1", "action": str(raw_plan)}, 0)],
            "current_step": 0,
        }

    def _normalize_step(self, step: Any, index: int) -> dict[str, Any]:
        if not isinstance(step, dict):
            return {
                "id": f"step_{index + 1}",
                "action": str(step),
                "metadata": {},
            }

        step_id = str(step.get("id", f"step_{index + 1}"))
        action = str(step.get("action") or step.get("description") or f"step_{index + 1}")
        metadata = step.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        dependencies = step.get("dependencies")
        if not isinstance(dependencies, list):
            dependencies = []

        return {
            "id": step_id,
            "action": action,
            "dependencies": [str(value) for value in dependencies],
            "metadata": dict(metadata),
        }

    def _current_step(self, plan: dict[str, Any]) -> dict[str, Any] | None:
        steps = plan.get("steps")
        if not isinstance(steps, list):
            return None
        index = int(plan.get("current_step", 0))
        if index < 0 or index >= len(steps):
            return None
        step = steps[index]
        if not isinstance(step, dict):
            return None
        return step

    def _all_steps_completed(self, plan: dict[str, Any]) -> bool:
        steps = plan.get("steps")
        if not isinstance(steps, list):
            return False
        index = int(plan.get("current_step", 0))
        return index >= len(steps)

    def _advance_step(self, plan: dict[str, Any], state: dict[str, Any]) -> None:
        current = int(plan.get("current_step", 0))
        plan["current_step"] = current + 1
        if state.get("current_step_failures") is None or not isinstance(
            state.get("current_step_failures"), dict
        ):
            state["current_step_failures"] = {}

    def _increment_step_failure(self, state: dict[str, Any], step: dict[str, Any] | None) -> None:
        key = "unknown_step"
        if isinstance(step, dict):
            key = str(step.get("id", "unknown_step"))
        failures = state.get("current_step_failures")
        if not isinstance(failures, dict):
            failures = {}
            state["current_step_failures"] = failures
        failures[key] = int(failures.get(key, 0)) + 1

    def _apply_step_adjustment(self, plan: dict[str, Any], state: dict[str, Any]) -> None:
        step = self._current_step(plan)
        if not isinstance(step, dict):
            return
        action = str(step.get("action", "execute_step"))
        if "[adjusted]" in action:
            return
        step["action"] = f"{action} [adjusted]"
        metadata = step.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["strategy_hint"] = state.get("strategy_hint", "none")
        step["metadata"] = metadata

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
        context = state.get("memory_context")
        if not isinstance(context, dict):
            context = {}

        if error_type in {"policy_violation", "security_violation"}:
            return "escalate"

        return self._select_best_decision(state, classification, context)

    def _select_best_decision(
        self,
        state: dict[str, Any],
        classification: dict[str, Any],
        context: dict[str, Any],
    ) -> Decision:
        pattern = str(classification.get("error_type", "runtime_error"))
        retryable = bool(classification.get("retryable", False))

        candidates: list[Decision]
        if pattern == "invalid_plan":
            candidates = ["adjust_plan", "abort"]
        elif retryable:
            candidates = ["retry_same", "adjust_plan", "abort"]
        else:
            candidates = ["adjust_plan", "abort"]

        # If recent history already shows repeated retry failures for this pattern,
        # de-prioritize retry_same deterministically.
        retry_failures = self._count_recent_pattern_failures(context, pattern, "retry_same")
        if retry_failures >= 2 and "retry_same" in candidates:
            candidates = [candidate for candidate in candidates if candidate != "retry_same"]
            candidates.append("retry_same")

        scored: list[tuple[float, Decision]] = []
        for candidate in candidates:
            scored.append((self._decision_score(pattern, candidate, state), candidate))

        scored.sort(key=lambda item: (-item[0], self._decision_rank(item[1])))
        return scored[0][1]

    def _decision_score(self, pattern: str, decision: Decision, state: dict[str, Any]) -> float:
        pattern_stats = self.strategy_stats.get(pattern, {})
        decision_stats = pattern_stats.get(decision, {})

        attempts = int(decision_stats.get("attempts", 0))
        successes = int(decision_stats.get("successes", 0))
        success_rate = float(decision_stats.get("success_rate", 0.0))
        confidence = float(decision_stats.get("confidence", 1.0))

        prior = {
            "retry_same": 0.60,
            "adjust_plan": 0.55,
            "abort": 0.20,
            "escalate": 0.10,
        }[decision]

        attempts_penalty = min(attempts * 0.02, 0.20)
        success_bonus = min(successes * 0.03, 0.30)

        # After repeated failures near threshold, bias toward changing strategy.
        attempt_count = int(state.get("attempt_count", 0))
        if decision == "retry_same" and attempt_count >= self.failure_threshold:
            confidence = max(0.10, confidence - 0.25)

        return prior + success_rate * confidence + success_bonus - attempts_penalty

    def _decision_rank(self, decision: Decision) -> int:
        order = {
            "adjust_plan": 0,
            "retry_same": 1,
            "abort": 2,
            "escalate": 3,
        }
        return order[decision]

    def _count_recent_pattern_failures(
        self,
        context: dict[str, Any],
        pattern: str,
        decision: Decision,
    ) -> int:
        recent = context.get("recent_failures", [])
        if not isinstance(recent, list):
            return 0

        count = 0
        for record in recent:
            if not isinstance(record, dict):
                continue
            record_pattern = str(record.get("strategy_pattern") or "")
            record_decision = str(record.get("decision") or "")
            if record_pattern == pattern and record_decision == decision:
                count += 1
        return count

    def _build_strategy_stats_from_context(
        self,
        context: dict[str, Any],
    ) -> dict[str, dict[str, dict[str, float | int]]]:
        recent = context.get("recent", [])
        if not isinstance(recent, list):
            return {}

        stats: dict[str, dict[str, dict[str, float | int]]] = {}
        for record in recent:
            if not isinstance(record, dict):
                continue

            classification = record.get("classification")
            pattern = "none"
            if isinstance(classification, dict):
                pattern = str(classification.get("error_type", "none"))

            decision = str(record.get("decision", ""))
            if decision not in {"retry_same", "adjust_plan", "abort", "escalate"}:
                continue

            success = bool(record.get("success", False))
            if pattern not in stats:
                stats[pattern] = {}
            if decision not in stats[pattern]:
                stats[pattern][decision] = {
                    "attempts": 0,
                    "successes": 0,
                    "success_rate": 0.0,
                    "confidence": 1.0,
                }

            item = stats[pattern][decision]
            item["attempts"] = int(item["attempts"]) + 1
            if success:
                item["successes"] = int(item["successes"]) + 1

            attempts = int(item["attempts"])
            successes = int(item["successes"])
            item["success_rate"] = successes / attempts if attempts > 0 else 0.0
            item["confidence"] = self._update_confidence(
                current=float(item.get("confidence", 1.0)),
                decision=decision,  # type: ignore[arg-type]
                success=success,
            )

        return stats

    def _merge_strategy_stats(
        self,
        incoming: dict[str, dict[str, dict[str, float | int]]],
    ) -> None:
        for pattern, decision_map in incoming.items():
            if pattern not in self.strategy_stats:
                self.strategy_stats[pattern] = {}
            for decision, stats in decision_map.items():
                if decision not in self.strategy_stats[pattern]:
                    self.strategy_stats[pattern][decision] = dict(stats)

    def _update_strategy_stats(self, pattern: str, decision: Decision, success: bool) -> None:
        if pattern not in self.strategy_stats:
            self.strategy_stats[pattern] = {}
        if decision not in self.strategy_stats[pattern]:
            self.strategy_stats[pattern][decision] = {
                "attempts": 0,
                "successes": 0,
                "success_rate": 0.0,
                "confidence": 1.0,
            }

        stats = self.strategy_stats[pattern][decision]
        stats["attempts"] = int(stats.get("attempts", 0)) + 1
        if success:
            stats["successes"] = int(stats.get("successes", 0)) + 1

        attempts = int(stats["attempts"])
        successes = int(stats["successes"])
        stats["success_rate"] = successes / attempts if attempts > 0 else 0.0
        stats["confidence"] = self._update_confidence(
            current=float(stats.get("confidence", 1.0)),
            decision=decision,
            success=success,
        )

    def _update_confidence(self, current: float, decision: Decision, success: bool) -> float:
        if success:
            return min(2.0, current + 0.10)

        penalty = 0.20 if decision == "retry_same" else 0.10
        return max(0.10, current - penalty)

    def _strategy_snapshot(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for pattern in sorted(self.strategy_stats.keys()):
            for decision in sorted(self.strategy_stats[pattern].keys()):
                stats = self.strategy_stats[pattern][decision]
                rows.append(
                    {
                        "pattern": pattern,
                        "decision": decision,
                        "attempts": int(stats.get("attempts", 0)),
                        "successes": int(stats.get("successes", 0)),
                        "success_rate": float(stats.get("success_rate", 0.0)),
                        "confidence": float(stats.get("confidence", 1.0)),
                    }
                )
        return rows

    def _build_strategy_hint(self, decision: Decision, classification: dict[str, Any]) -> str:
        pattern = str(classification.get("error_type", "runtime_error"))
        if decision == "adjust_plan":
            return f"avoid_previous_plan_pattern:{pattern}"
        if decision == "advance_step":
            return "advance_to_next_step"
        if decision == "retry_same":
            return f"retry_with_same_plan:{pattern}"
        if decision == "escalate":
            return f"escalate_issue:{pattern}"
        return "finalize_goal"

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
        active_plan = state.get("active_plan")
        current_step = None
        if isinstance(active_plan, dict):
            current_step = active_plan.get("current_step")
        step_history = state.get("step_history", [])
        current_step_failures = state.get("current_step_failures", {})
        return {
            "goal": str(state.get("goal", "")),
            "attempt_count": int(state.get("attempt_count", 0)),
            "last_failure_reason": state.get("last_failure_reason"),
            "last_error_type": state.get("last_error_type"),
            "last_retryable": state.get("last_retryable"),
            "last_decision": state.get("last_decision"),
            "strategy_hint": state.get("strategy_hint"),
            "history_size": len(history) if isinstance(history, list) else 0,
            "step_history_size": len(step_history) if isinstance(step_history, list) else 0,
            "current_step": int(current_step) if isinstance(current_step, int) else 0,
            "current_step_failures": self._safe_payload(current_step_failures),
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
