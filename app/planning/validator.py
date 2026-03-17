"""Plan validator: validates task inputs before the planning engine processes them."""

from app.core.logger import get_logger
from app.planning.models import TaskNode

logger = get_logger(__name__)


class PlanValidator:
    """Validates a list of TaskNodes before planning.

    Checks performed (in order):
    1. No duplicate task IDs.
    2. All dependency references point to known task IDs.
    """

    def validate(self, tasks: list[TaskNode]) -> None:
        """Validate the task list; raise ValueError on the first detected issue.

        Args:
            tasks: Task list to validate.

        Raises:
            ValueError: If any validation rule is violated.
        """
        logger.info("validation_started", {"task_count": len(tasks)})
        self._check_no_duplicate_ids(tasks)
        self._check_dependencies_exist(tasks)
        logger.info("validation_completed", {"task_count": len(tasks)})

    def _check_no_duplicate_ids(self, tasks: list[TaskNode]) -> None:
        """Ensure all task IDs are unique."""
        seen: set[str] = set()
        for task in tasks:
            if task.id in seen:
                logger.error("validation_duplicate_id", f"Duplicate task ID detected: {task.id!r}")
                raise ValueError(f"Duplicate task ID detected: {task.id!r}")
            seen.add(task.id)

    def _check_dependencies_exist(self, tasks: list[TaskNode]) -> None:
        """Ensure every referenced dependency ID exists in the task list."""
        known_ids: set[str] = {task.id for task in tasks}
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id not in known_ids:
                    logger.error(
                        "validation_unknown_dependency",
                        f"Task {task.id!r} references unknown dependency {dep_id!r}",
                    )
                    raise ValueError(
                        f"Task {task.id!r} references unknown dependency {dep_id!r}"
                    )
