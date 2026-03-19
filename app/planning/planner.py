"""Planning Engine public interface.

This module intentionally exposes a single public entry point:
`build_execution_plan(tasks: list[dict]) -> ExecutionPlan`.
"""

from copy import deepcopy

from pydantic import ValidationError

from app.core.logger import get_logger
from app.planning.graph import DependencyGraph, PlanningCycleError
from app.planning.models import ExecutionGroup, ExecutionPlan, PlanMetadata, TaskNode
from app.planning.validator import PlanValidator

logger = get_logger(__name__)


class _PlanningEngine:
    """Internal orchestrator for converting TaskNode lists into ExecutionPlan."""

    def __init__(self) -> None:
        self._validator = PlanValidator()

    def build_plan(self, tasks: list[TaskNode]) -> ExecutionPlan:
        logger.info("planning_engine_started", {"task_count": len(tasks)})

        self._validator.validate(tasks)

        graph = DependencyGraph()
        graph.build(tasks)

        ordered_ids, grouped_ids = graph.traverse_levels()

        execution_groups = [
            ExecutionGroup(group_id=index, task_ids=task_ids)
            for index, task_ids in enumerate(grouped_ids)
        ]
        ordered_tasks = [graph.nodes[task_id] for task_id in ordered_ids]

        plan = ExecutionPlan(
            ordered_tasks=ordered_tasks,
            execution_groups=execution_groups,
            metadata=PlanMetadata(total_tasks=len(tasks), has_cycles=False),
        )

        logger.info(
            "planning_engine_completed",
            {
                "total_tasks": plan.metadata.total_tasks,
                "group_count": len(plan.execution_groups),
            },
        )
        return plan


def _normalize_tasks(raw_tasks: list[dict]) -> list[TaskNode]:
    """Convert list[dict] input into validated TaskNode objects."""
    if not isinstance(raw_tasks, list):
        raise ValueError("tasks must be a list of dictionaries")

    normalized: list[TaskNode] = []
    for index, raw_task in enumerate(raw_tasks):
        if not isinstance(raw_task, dict):
            raise ValueError(f"tasks[{index}] must be a dictionary")
        try:
            normalized.append(TaskNode.from_dict(raw_task))
        except ValidationError as exc:
            raise ValueError(f"Invalid task at index {index}: {exc}") from exc

    return normalized


def build_execution_plan(tasks: list[dict]) -> ExecutionPlan:
    """Build a deterministic execution plan from a list of task dictionaries.

    Input contract:
        tasks: list[dict] with shape
            {
                "id": str,
                "description": str,
                "dependencies": list[str]  # optional
            }

    Raises:
        ValueError: For malformed input, duplicate IDs, or unknown dependencies.
        PlanningCycleError: If the dependency graph contains a cycle.
    """
    logger.info("build_execution_plan_started", {"raw_task_count": len(tasks)})

    nodes = _normalize_tasks(tasks)
    engine = _PlanningEngine()

    try:
        plan = engine.build_plan(nodes)
    except PlanningCycleError:
        logger.error("build_execution_plan_failed_cycle", "Dependency cycle detected")
        raise

    logger.info("build_execution_plan_completed", {"total_tasks": plan.metadata.total_tasks})
    return plan


def plan(task: dict, context: dict | None = None) -> ExecutionPlan:
    """Build a deterministic single-task plan with optional feedback context."""
    if not isinstance(task, dict):
        raise ValueError("task must be a dictionary")

    normalized_task = deepcopy(task)
    if context is None:
        return build_execution_plan([normalized_task])

    metadata = normalized_task.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)

    repeated_failures = context.get("repeated_failures")
    if isinstance(repeated_failures, list):
        signatures = sorted(
            {
                str(item.get("signature"))
                for item in repeated_failures
                if isinstance(item, dict) and item.get("signature")
            }
        )
        if signatures:
            metadata["avoid_failure_signatures"] = signatures

    success_strategies = context.get("success_strategies")
    if isinstance(success_strategies, list):
        strategies = [
            str(item.get("strategy"))
            for item in success_strategies
            if isinstance(item, dict) and item.get("strategy")
        ]
        strategies = [strategy for strategy in strategies if strategy]
        if strategies:
            metadata["preferred_strategies"] = strategies

    if metadata:
        normalized_task["metadata"] = metadata

    logger.info(
        "planner_feedback_context_applied",
        {
            "task_id": str(normalized_task.get("id", "unknown")),
            "context_keys": sorted(context.keys()),
        },
    )
    return build_execution_plan([normalized_task])
