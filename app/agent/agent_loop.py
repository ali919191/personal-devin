"""Deterministic Agent 05 orchestration loop."""

from app.agent.schemas import AgentResult, ReflectionResult
from app.core.logger import get_logger
from app.execution.runner import run_plan
from app.memory.service import MemoryService
from app.planning import build_execution_plan

logger = get_logger(__name__)


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

        status = self._classify(execution_report)
        logger.info("validation_completed", {"goal": normalized_goal, "status": status})

        reflection = self._reflect(execution_report)
        logger.info(
            "reflection_completed",
            {
                "goal": normalized_goal,
                "failed_tasks": reflection.failed_tasks,
                "success_rate": reflection.success_rate,
            },
        )

        self._persist(normalized_goal, plan, execution_report, reflection, status)
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

    def _classify(self, execution_report) -> str:
        if execution_report.total_tasks == 0:
            return "success"

        if execution_report.completed_tasks == execution_report.total_tasks:
            return "success"

        if execution_report.completed_tasks == 0:
            return "failure"

        return "partial"

    def _reflect(self, execution_report) -> ReflectionResult:
        failed_tasks = [
            task.id
            for task in execution_report.tasks
            if task.status.value in {"failed", "skipped"}
        ]

        total_tasks = execution_report.total_tasks
        success_rate = (
            execution_report.completed_tasks / total_tasks if total_tasks > 0 else 1.0
        )

        if not failed_tasks:
            notes = "All tasks succeeded"
        elif execution_report.completed_tasks > 0:
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
        execution_report,
        reflection: ReflectionResult,
        status: str,
    ) -> None:
        self._memory.log_execution(
            status=status,
            total_tasks=execution_report.total_tasks,
            completed_tasks=execution_report.completed_tasks,
            failed_tasks=execution_report.failed_tasks,
            skipped_tasks=execution_report.skipped_tasks,
            metadata={
                "goal": goal,
                "plan": {
                    "ordered_tasks": [task.model_dump() for task in plan.ordered_tasks],
                    "execution_groups": [group.model_dump() for group in plan.execution_groups],
                },
                "reflection": reflection.model_dump(),
            },
        )

        for task in execution_report.tasks:
            self._memory.log_task(
                task_id=task.id,
                status=task.status.value,
                output=task.output,
                error=task.error,
                skip_reason=task.skip_reason,
            )

            if task.status.value in {"failed", "skipped"}:
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