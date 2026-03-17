"""Execution orchestrator: iterates plan steps, calls executor, logs and reports."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.execution.executor import Executor, TaskHandler
from app.execution.logger import get_execution_logger
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.planning.models import ExecutionPlan, TaskNode

_logger = get_execution_logger(__name__)


def _task_node_to_execution_task(node: TaskNode) -> ExecutionTask:
    """Convert a planning-layer TaskNode into an execution-layer ExecutionTask."""
    return ExecutionTask(
        id=node.id,
        description=node.description,
        dependencies=list(node.dependencies),
    )


class Runner:
    """Orchestrates sequential execution of all tasks in an ExecutionPlan.

    Pipeline per task:
    1. Check whether any dependency failed/was skipped → skip this task.
    2. Delegate to Executor.execute_task().
    3. Log the outcome.
    4. On failure, stop immediately (stop_on_failure=True) or continue.

    Args:
        stop_on_failure: When True (default), the run halts after the first
            FAILED task and all remaining tasks are marked SKIPPED.
            When False, the runner continues even if tasks fail.
    """

    def __init__(self, stop_on_failure: bool = True) -> None:
        """Initialise the runner with an Executor instance."""
        self._executor = Executor()
        self.stop_on_failure = stop_on_failure

    def run(
        self,
        plan: ExecutionPlan,
        handlers: dict[str, TaskHandler] | None = None,
    ) -> ExecutionReport:
        """Execute all tasks in *plan* in their topological order.

        Args:
            plan: A validated ExecutionPlan from the Planning Engine. Tasks are
                consumed in ``ordered_tasks`` order (already topologically sorted).
            handlers: Optional mapping of task ID → callable. Each callable
                receives the ExecutionTask and returns either:
                - tuple[success: bool, message: str | None]
                - string (backward-compatible successful output)
                Tasks without a handler entry use the no-op default.

        Returns:
            ExecutionReport summarising the outcome of every task.
        """
        handlers = handlers or {}
        started_at = datetime.now(UTC)
        _logger.log_run_started(plan.metadata.total_tasks)

        execution_tasks: list[ExecutionTask] = [
            _task_node_to_execution_task(node) for node in plan.ordered_tasks
        ]
        task_index: dict[str, ExecutionTask] = {t.id: t for t in execution_tasks}

        halted = False

        for task in execution_tasks:
            if halted:
                task.status = ExecutionStatus.SKIPPED
                blocking_dep = self._find_blocking_dependency(task, task_index)
                if blocking_dep is not None:
                    task.skip_reason = f"dependency_failed:{blocking_dep}"
                else:
                    task.skip_reason = "run_halted_after_failure"
                task.error = task.skip_reason
                _logger.log_step_skipped(task, task.skip_reason)
                continue

            # Skip if any dependency failed or was itself skipped.
            blocking_dep = self._find_blocking_dependency(task, task_index)
            if blocking_dep is not None:
                task.status = ExecutionStatus.SKIPPED
                task.skip_reason = f"dependency_failed:{blocking_dep}"
                task.error = task.skip_reason
                _logger.log_step_skipped(
                    task,
                    task.skip_reason,
                )
                if self.stop_on_failure:
                    halted = True
                continue

            _logger.log_step_started(task)
            self._executor.execute_task(task, handler=handlers.get(task.id))

            if task.status == ExecutionStatus.COMPLETED:
                _logger.log_step_completed(task)
            else:
                _logger.log_step_failed(task)
                if self.stop_on_failure:
                    halted = True

        report = self._build_report(execution_tasks, started_at)
        _logger.log_run_summary(report)
        return report

    def _find_blocking_dependency(
        self,
        task: ExecutionTask,
        task_index: dict[str, ExecutionTask],
    ) -> str | None:
        """Return the ID of the first dependency that is not COMPLETED, or None."""
        for dep_id in task.dependencies:
            dep = task_index.get(dep_id)
            if dep is not None and dep.status != ExecutionStatus.COMPLETED:
                return dep_id
        return None

    def _build_report(
        self,
        tasks: list[ExecutionTask],
        started_at: datetime,
    ) -> ExecutionReport:
        """Aggregate per-task results into an ExecutionReport."""
        completed = sum(1 for t in tasks if t.status == ExecutionStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status == ExecutionStatus.FAILED)
        skipped = sum(1 for t in tasks if t.status == ExecutionStatus.SKIPPED)

        if failed > 0:
            overall = ExecutionStatus.FAILED
        elif skipped > 0 and completed < len(tasks):
            overall = ExecutionStatus.FAILED
        else:
            overall = ExecutionStatus.COMPLETED

        completed_at = datetime.now(UTC)
        if completed_at <= started_at:
            completed_at = started_at + timedelta(microseconds=1)

        return ExecutionReport(
            tasks=tasks,
            status=overall,
            total_tasks=len(tasks),
            completed_tasks=completed,
            failed_tasks=failed,
            skipped_tasks=skipped,
            started_at=started_at,
            completed_at=completed_at,
        )


def run_plan(
    plan: ExecutionPlan,
    handlers: dict[str, TaskHandler] | None = None,
    stop_on_failure: bool = True,
) -> ExecutionReport:
    """Convenience function: create a Runner and execute a plan in one call.

    Example::

        from app.planning.planner import build_execution_plan
        from app.execution.runner import run_plan

        tasks = [
            {"id": "step1", "description": "Initialise", "dependencies": []},
            {"id": "step2", "description": "Build", "dependencies": ["step1"]},
        ]
        plan   = build_execution_plan(tasks)
        report = run_plan(plan)

        print(report.status)           # ExecutionStatus.COMPLETED
        print(report.completed_tasks)  # 2
    """
    runner = Runner(stop_on_failure=stop_on_failure)
    return runner.run(plan, handlers=handlers)
