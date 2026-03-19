"""Core execution engine: runs a single task and tracks its lifecycle."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.execution.models import ExecutionStatus, ExecutionTask
from app.execution.sandbox import ExecutionSandbox

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

    def __init__(self, sandbox: ExecutionSandbox | None = None) -> None:
        self._sandbox = sandbox or ExecutionSandbox()

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
            result: TaskHandlerResult | str = self._execute_handler(task, handler)

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

    def _execute_handler(
        self,
        task: ExecutionTask,
        handler: TaskHandler | None,
    ) -> TaskHandlerResult | str:
        if handler is None:
            return (True, "")

        sandbox_result = self._sandbox.execute(
            handler,
            task,
            context={
                "task_id": task.id,
                "dependencies": list(task.dependencies),
            },
        )

        if not sandbox_result["success"]:
            raise RuntimeError(sandbox_result["error"] or "sandboxed task failed")

        output = sandbox_result["output"]
        result = output.get("result")
        return self._normalize_result(result)

    def _normalize_result(self, result: Any) -> TaskHandlerResult | str:
        if isinstance(result, tuple) and len(result) == 2:
            success, message = result
            return bool(success), None if message is None else str(message)

        if isinstance(result, str):
            return result

        return str(result)
