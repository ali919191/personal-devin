"""Deterministic Agent 05 orchestration loop."""

from typing import Any

from app.agent.schemas import AgentResult, ReflectionResult
from app.core.logger import get_logger
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.execution.runner import run_plan
from app.memory.service import MemoryService
from app.planning import build_execution_plan

logger = get_logger(__name__)

SUCCESS = "success"
PARTIAL = "partial"
FAILURE = "failure"


class AgentLoop:
    """Orchestrates plan, execute, validate, reflect, and persist steps."""

    def __init__(self, memory_service: MemoryService | None = None) -> None:
        self._memory = memory_service or MemoryService()

    def run(self, goal: str) -> AgentResult:
        """Run the deterministic agent loop for a single goal string."""
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValueError("goal must be a non-empty string")

        logger.info("planning_started", {"goal": normalized_goal})
        tasks = self._goal_to_tasks(normalized_goal)
        plan = build_execution_plan(tasks)

        logger.info(
            "execution_started",
            {"goal": normalized_goal, "task_count": plan.metadata.total_tasks},
        )
        execution_report = run_plan(plan)
        metrics = self._extract_metrics(execution_report)

        status = self._classify(metrics)
        logger.info("validation_completed", {"goal": normalized_goal, "status": status})

        reflection = self._reflect(metrics)
        logger.info(
            "reflection_completed",
            {
                "goal": normalized_goal,
                "failed_tasks": reflection.failed_tasks,
                "success_rate": reflection.success_rate,
            },
        )

        self._persist(normalized_goal, plan, metrics, reflection, status)
        logger.info("memory_persisted", {"goal": normalized_goal, "status": status})

        return AgentResult(
            goal=normalized_goal,
            status=status,
            plan=plan,
            execution=execution_report,
            reflection=reflection,
        )

    def _goal_to_tasks(self, goal: str) -> list[dict]:
        return [
            {
                "id": "task-1",
                "description": goal,
                "dependencies": [],
            }
        ]

    def _extract_metrics(self, execution_report: ExecutionReport) -> dict[str, Any]:
        tasks = getattr(execution_report, "tasks", [])
        if tasks is None:
            tasks = []

        return {
            "total": execution_report.total_tasks,
            "completed": execution_report.completed_tasks,
            "failed": execution_report.failed_tasks,
            "skipped": execution_report.skipped_tasks,
            "tasks": tasks,
        }

    def _classify(self, metrics: dict[str, Any]) -> str:
        total = int(metrics["total"])
        completed = int(metrics["completed"])
        failed = int(metrics["failed"])
        skipped = int(metrics["skipped"])

        if total == 0:
            return SUCCESS

        if failed == 0 and skipped == 0:
            return SUCCESS

        if completed == 0:
            return FAILURE

        return PARTIAL

    def _reflect(self, metrics: dict[str, Any]) -> ReflectionResult:
        tasks: list[ExecutionTask] = list(metrics["tasks"])
        failed_tasks = [
            task.id
            for task in tasks
            if task.status in {ExecutionStatus.FAILED, ExecutionStatus.SKIPPED}
        ]

        total_tasks = int(metrics["total"])
        completed_tasks = int(metrics["completed"])
        success_rate = completed_tasks / total_tasks if total_tasks > 0 else 1.0

        if not failed_tasks:
            notes = "All tasks succeeded"
        elif completed_tasks > 0:
            notes = "Partial failure detected"
        else:
            notes = "Execution failed"

        return ReflectionResult(
            failed_tasks=failed_tasks,
            success_rate=success_rate,
            notes=notes,
        )

    def _persist(
        self,
        goal: str,
        plan,
        metrics: dict[str, Any],
        reflection: ReflectionResult,
        status: str,
    ) -> None:
        self._memory.log_execution(
            status=status,
            total_tasks=int(metrics["total"]),
            completed_tasks=int(metrics["completed"]),
            failed_tasks=int(metrics["failed"]),
            skipped_tasks=int(metrics["skipped"]),
            metadata={
                "goal": goal,
                "plan": {
                    "task_ids": [task.id for task in plan.ordered_tasks],
                    "total_tasks": len(plan.ordered_tasks),
                },
                "reflection": reflection.model_dump(),
            },
        )

        tasks: list[ExecutionTask] = list(metrics["tasks"])
        for task in tasks:
            self._memory.log_task(
                task_id=task.id,
                status=task.status.value,
                output=task.output,
                error=task.error,
                skip_reason=task.skip_reason,
            )

            if task.status in {ExecutionStatus.FAILED, ExecutionStatus.SKIPPED}:
                self._memory.log_failure(
                    source="agent_loop",
                    error=task.error or task.skip_reason or "unknown",
                    context={
                        "goal": goal,
                        "task_id": task.id,
                        "status": task.status.value,
                    },
                )

        self._memory.log_decision(
            decision=status,
            reason=reflection.notes,
            context={
                "goal": goal,
                "failed_tasks": reflection.failed_tasks,
                "success_rate": reflection.success_rate,
            },
        )