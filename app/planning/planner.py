"""Main planner that orchestrates the planning process.

Contains two independent orchestrators:
- ``Planner``         — Agent 01: goal string → Plan (task decomposition).
- ``PlanningEngine``  — Agent 02: TaskNode list → ExecutionPlan (planning engine).
"""

from app.core.logger import get_logger
from app.planning.graph import DependencyGraph
from app.planning.models import ExecutionGroup, ExecutionPlan, Plan, PlanMetadata, TaskNode
from app.planning.task_decomposer import TaskDecomposer
from app.planning.task_graph import TaskGraph
from app.planning.validator import PlanValidator

logger = get_logger(__name__)


class Planner:
    """Orchestrates the complete planning process."""

    def __init__(self) -> None:
        """Initialize the planner."""
        self.decomposer = TaskDecomposer()

    def create_plan(self, goal: str) -> Plan:
        """Create a complete plan from a goal.

        Flow:
        1. Decompose goal into tasks
        2. Build DAG
        3. Validate DAG
        4. Return Plan

        Args:
            goal: The goal to plan for

        Returns:
            A validated Plan with ordered tasks

        Raises:
            ValueError: If the plan contains cycles or is invalid
        """
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValueError("Goal must be a non-empty string")

        logger.info("create_plan_started", {"goal": normalized_goal})

        # Step 1: Decompose goal
        logger.debug("decomposing_goal", {"goal": normalized_goal})
        plan = self.decomposer.decompose(normalized_goal)
        logger.debug("goal_decomposed", {"task_count": len(plan.tasks)})

        # Step 2: Build DAG
        logger.debug("building_dag", {"task_count": len(plan.tasks)})
        graph = TaskGraph()

        for task in plan.tasks:
            graph.add_task(task)

        for task in plan.tasks:
            for dep_id in task.dependencies:
                try:
                    graph.add_dependency(str(task.id), dep_id)
                except ValueError as e:
                    logger.error("invalid_dependency", str(e), {"task": str(task.id)})
                    raise

        logger.debug("dag_built", {"nodes": len(graph.tasks)})

        # Step 3: Validate DAG
        logger.debug("validating_dag", {})
        if not graph.validate_no_cycles():
            error_msg = "Plan contains circular dependencies"
            logger.error("cycle_detected", error_msg)
            raise ValueError(error_msg)

        logger.debug("dag_validated", {"cycles": 0})

        # Step 4: Return plan in deterministic execution order
        try:
            execution_order = graph.get_execution_order()
            plan.tasks = execution_order
            logger.info(
                "create_plan_completed",
                {
                    "task_count": len(plan.tasks),
                    "execution_order": [str(t.id) for t in execution_order[:3]],
                },
            )
            return plan
        except ValueError as e:
            logger.error("topological_sort_failed", str(e))
            raise


def create_plan(goal: str) -> Plan:
    """Convenience function to create a plan.

    Example:
        plan = create_plan("Build REST API")
    """
    planner = Planner()
    return planner.create_plan(goal)


# ---------------------------------------------------------------------------
# Agent 02 — Planning Engine
# ---------------------------------------------------------------------------


class PlanningEngine:
    """Converts a structured TaskNode list into a deterministic ExecutionPlan.

    Pipeline:
    1. Validate inputs (no duplicates, no missing dependencies).
    2. Build a DependencyGraph (DAG).
    3. Run topological sort (raises on cycle).
    4. Compute execution groups (parallelisable task sets).
    5. Return an ExecutionPlan.
    """

    def __init__(self) -> None:
        """Initialise with a shared validator instance."""
        self._validator = PlanValidator()

    def build_plan(self, tasks: list[TaskNode]) -> ExecutionPlan:
        """Convert a list of TaskNodes into a deterministic ExecutionPlan.

        Args:
            tasks: Structured task list from the Task Decomposition Engine.

        Returns:
            ExecutionPlan with ordered tasks, execution groups, and metadata.

        Raises:
            ValueError: If validation fails or the dependency graph has cycles.
        """
        logger.info("planning_engine_started", {"task_count": len(tasks)})

        # Step 1: Validate
        self._validator.validate(tasks)
        logger.debug("validation_passed", {"task_count": len(tasks)})

        # Step 2: Build graph
        graph = DependencyGraph()
        graph.build(tasks)

        # Step 3: Topological sort (raises ValueError if cycle detected)
        try:
            sorted_ids = graph.topological_sort()
        except ValueError as exc:
            logger.error("cycle_detected", str(exc))
            raise

        logger.debug("topological_sort_completed", {"ordered_count": len(sorted_ids)})

        # Step 4: Execution groups (re-uses the already-computed sorted_ids)
        raw_groups = graph.execution_groups(sorted_ids)
        execution_groups = [
            ExecutionGroup(group_id=i, task_ids=group)
            for i, group in enumerate(raw_groups)
        ]
        logger.debug("execution_groups_computed", {"group_count": len(execution_groups)})

        # Step 5: Assemble plan
        ordered_tasks = [graph.nodes[task_id] for task_id in sorted_ids]
        plan = ExecutionPlan(
            ordered_tasks=ordered_tasks,
            execution_groups=execution_groups,
            metadata=PlanMetadata(total_tasks=len(tasks), has_cycles=False),
        )

        logger.info("planning_engine_completed", {"total_tasks": plan.metadata.total_tasks})
        return plan


def build_execution_plan(tasks: list[TaskNode]) -> ExecutionPlan:
    """Convenience function to build an execution plan from a task list.

    Example::

        from app.planning.planner import build_execution_plan
        from app.planning.models import TaskNode

        tasks = [
            TaskNode(id="t1", description="Design schema", dependencies=[]),
            TaskNode(id="t2", description="Implement API", dependencies=["t1"]),
        ]
        plan = build_execution_plan(tasks)
        for task in plan.ordered_tasks:
            print(task.id, task.description)
    """
    engine = PlanningEngine()
    return engine.build_plan(tasks)
