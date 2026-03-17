"""Core execution engine: runs a single task and tracks its lifecycle."""

from collections.abc import Callable
from datetime import UTC, datetime

from app.execution.models import ExecutionStatus, ExecutionTask

TaskHandlerResult = tuple[bool, str | None]
TaskHandler = Callable[["ExecutionTask"], TaskHandlerResult | str]


class Executor:
    """Executes a single ExecutionTask and returns it with updated status.

    The executor is intentionally stateless — it receives an immutable-ish
    task, applies a handler (or the default no-op), and returns the task
    with its status, output, timings, and error fields populated.

    Dependency-failure shortcircuiting is the caller's (Runner's) responsibility;
    the executor only cares about running one task cleanly.
    """

    def execute_task(
        self,
        task: ExecutionTask,
        handler: TaskHandler | None = None,
    ) -> ExecutionTask:
        """Execute *task* and return it with its final status set.

        Args:
            task: The task to execute. Must be in PENDING or RUNNING state.
            handler: Optional callable that receives the task and returns either:
                - tuple[success: bool, message: str | None]
                - string (backward-compatible shorthand for successful output)
                If it raises, the task is marked FAILED and the exception message
                is stored in ``task.error``. When omitted the task succeeds with
                empty output.

        Returns:
            The same task object with ``status``, ``output``/``error``, and
            ``started_at``/``completed_at`` populated.
        """
        task.status = ExecutionStatus.RUNNING
        task.started_at = datetime.now(UTC)
        task.error = None
        task.skip_reason = None

        try:
            result: TaskHandlerResult | str = (
                handler(task) if handler is not None else (True, "")
            )

            if isinstance(result, tuple):
                success, message = result
                if success:
                    task.output = message or ""
                    task.status = ExecutionStatus.COMPLETED
                else:
                    task.error = message or "task failed"
                    task.status = ExecutionStatus.FAILED
            else:
                task.output = result
                task.status = ExecutionStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001
            task.error = str(exc)
            task.status = ExecutionStatus.FAILED
        finally:
            task.completed_at = datetime.now(UTC)

        return task
