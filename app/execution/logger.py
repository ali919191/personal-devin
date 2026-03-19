"""Structured execution logger providing step-level and summary logging."""

from typing import TYPE_CHECKING

from app.core.logger import StructuredLogger, get_logger

if TYPE_CHECKING:
    from app.execution.models import ExecutionReport, ExecutionTask


class ExecutionLogger:
    """Wraps the core StructuredLogger with execution-specific logging methods.

    All log entries are emitted as JSON via the underlying StructuredLogger,
    maintaining consistency with the rest of the system.
    """

    def __init__(self, name: str) -> None:
        """Initialise with a module-scoped logger."""
        self._logger: StructuredLogger = get_logger(name)

    def log_run_started(
        self,
        total_tasks: int,
        *,
        execution_id: str,
        fingerprint: str,
    ) -> None:
        """Log the start of an execution run."""
        self._logger.info(
            "execution_started",
            {
                "execution_id": execution_id,
                "fingerprint": fingerprint,
                "total_tasks": total_tasks,
            },
        )

    def log_step_started(self, task: "ExecutionTask") -> None:
        """Log that a task has started executing."""
        self._logger.info(
            "execution_step_started",
            {
                "task_id": task.id,
                "status": task.status,
                "description": task.description,
            },
        )

    def log_step_completed(self, task: "ExecutionTask") -> None:
        """Log successful task completion."""
        self._logger.info(
            "execution_step_completed",
            {"task_id": task.id, "status": task.status, "output": task.output},
        )

    def log_step_failed(self, task: "ExecutionTask") -> None:
        """Log a task failure with its error message."""
        self._logger.error(
            "execution_step_failed",
            task.error or "unknown error",
            {"task_id": task.id, "status": task.status},
        )

    def log_step_skipped(self, task: "ExecutionTask", reason: str) -> None:
        """Log that a task was skipped (e.g. a dependency failed)."""
        self._logger.warning(
            "execution_step_skipped",
            {"task_id": task.id, "status": task.status, "reason": reason},
        )

    def log_run_summary(self, report: "ExecutionReport") -> None:
        """Log a summary of the completed execution run."""
        self._logger.info(
            "execution_run_summary",
            {
                "status": report.status,
                "total_tasks": report.total_tasks,
                "completed_tasks": report.completed_tasks,
                "failed_tasks": report.failed_tasks,
                "skipped_tasks": report.skipped_tasks,
            },
        )

    def log_run_failed(
        self,
        *,
        execution_id: str,
        fingerprint: str,
        error: str,
    ) -> None:
        """Log a run-level failure anchored to the deployment context fingerprint."""
        self._logger.error(
            "execution_failed",
            error,
            {
                "execution_id": execution_id,
                "fingerprint": fingerprint,
            },
        )


def get_execution_logger(name: str) -> ExecutionLogger:
    """Return a module-scoped ExecutionLogger instance."""
    return ExecutionLogger(name)
