"""Main planner that orchestrates the planning process."""

from app.core.logger import get_logger
from app.planning.models import Plan
from app.planning.task_decomposer import TaskDecomposer
from app.planning.task_graph import TaskGraph

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
        logger.info("create_plan_started", {"goal": goal})

        # Step 1: Decompose goal
        logger.debug("decomposing_goal", {"goal": goal})
        plan = self.decomposer.decompose(goal)
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

        # Step 4: Get execution order
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

    def add_task_to_plan(self, plan: Plan, new_task_index: int) -> Plan:
        """Add a task to an existing plan (helper for dynamic planning)."""
        logger.debug(
            "adding_task_to_plan",
            {"plan_id": str(plan.id), "task_count": len(plan.tasks)},
        )

        graph = TaskGraph()
        for task in plan.tasks:
            graph.add_task(task)

        for task in plan.tasks:
            for dep_id in task.dependencies:
                graph.add_dependency(str(task.id), dep_id)

        execution_order = graph.get_execution_order()
        plan.tasks = execution_order

        return plan


def create_plan(goal: str) -> Plan:
    """Convenience function to create a plan.

    Example:
        plan = create_plan("Build REST API")
    """
    planner = Planner()
    return planner.create_plan(goal)
