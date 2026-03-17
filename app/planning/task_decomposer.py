"""Task decomposer: converts goals into structured plans."""

from uuid import uuid4

from app.core.logger import get_logger
from app.planning.models import Plan, Task
from app.planning.task_graph import TaskGraph

logger = get_logger(__name__)


class TaskDecomposer:
    """Decomposes natural language goals into structured task plans."""

    # Rule-based decomposition templates for common goal patterns
    GOAL_PATTERNS = {
        "api": {
            "tasks": [
                {
                    "name": "Design API specification",
                    "description": "Define API endpoints, request/response schemas, and authentication",
                    "priority": 90,
                },
                {
                    "name": "Set up project structure",
                    "description": "Create directory structure and configure project dependencies",
                    "priority": 85,
                },
                {
                    "name": "Implement core endpoints",
                    "description": "Build main API endpoints with business logic",
                    "priority": 80,
                },
                {
                    "name": "Add authentication",
                    "description": "Implement user authentication and authorization",
                    "priority": 75,
                },
                {
                    "name": "Add error handling",
                    "description": "Implement comprehensive error handling and validation",
                    "priority": 70,
                },
                {
                    "name": "Write tests",
                    "description": "Create unit and integration tests",
                    "priority": 65,
                },
                {
                    "name": "Document API",
                    "description": "Create API documentation and usage examples",
                    "priority": 60,
                },
            ],
            "dependencies_graph": {
                0: [],
                1: [0],
                2: [1],
                3: [2],
                4: [3],
                5: [2],
                6: [5],
            },
        },
        "database": {
            "tasks": [
                {
                    "name": "Design database schema",
                    "description": "Define tables, relationships, and constraints",
                    "priority": 95,
                },
                {
                    "name": "Set up database server",
                    "description": "Install and configure database",
                    "priority": 90,
                },
                {
                    "name": "Create database migrations",
                    "description": "Develop schema migration scripts",
                    "priority": 85,
                },
                {
                    "name": "Build data access layer",
                    "description": "Implement database queries and ORM",
                    "priority": 80,
                },
                {
                    "name": "Add indexing and optimization",
                    "description": "Add indexes and query optimization",
                    "priority": 70,
                },
                {
                    "name": "Test database operations",
                    "description": "Create database tests",
                    "priority": 65,
                },
            ],
            "dependencies_graph": {
                0: [],
                1: [0],
                2: [1],
                3: [2],
                4: [3],
                5: [3],
            },
        },
        "frontend": {
            "tasks": [
                {
                    "name": "Design UI mockups",
                    "description": "Create wireframes and visual designs",
                    "priority": 85,
                },
                {
                    "name": "Set up frontend project",
                    "description": "Initialize project structure and dependencies",
                    "priority": 80,
                },
                {
                    "name": "Build component library",
                    "description": "Create reusable UI components",
                    "priority": 75,
                },
                {
                    "name": "Implement main pages",
                    "description": "Build application pages and layouts",
                    "priority": 70,
                },
                {
                    "name": "Integrate with backend",
                    "description": "Connect frontend to API endpoints",
                    "priority": 65,
                },
                {
                    "name": "Add styling and responsive design",
                    "description": "Implement CSS and responsive layouts",
                    "priority": 60,
                },
                {
                    "name": "Test frontend",
                    "description": "Create unit and integration tests",
                    "priority": 55,
                },
            ],
            "dependencies_graph": {
                0: [],
                1: [0],
                2: [1],
                3: [2],
                4: [3],
                5: [3],
                6: [4, 5],
            },
        },
    }

    def decompose(self, goal: str) -> Plan:
        """Decompose a goal into a structured plan."""
        logger.info("decompose_goal_started", {"goal": goal})

        # Find matching pattern
        matched_pattern = None
        for pattern_key in self.GOAL_PATTERNS:
            if pattern_key.lower() in goal.lower():
                matched_pattern = pattern_key
                break

        if matched_pattern:
            logger.debug("pattern_matched", {"pattern": matched_pattern})
            plan = self._build_plan_from_pattern(goal, matched_pattern)
        else:
            logger.debug("no_pattern_matched", {"goal": goal})
            plan = self._build_generic_plan(goal)

        logger.info("decompose_goal_completed", {"task_count": len(plan.tasks)})
        return plan

    def _build_plan_from_pattern(self, goal: str, pattern: str) -> Plan:
        """Build plan from a predefined pattern."""
        pattern_data = self.GOAL_PATTERNS[pattern]
        plan = Plan(goal=goal)

        task_map: dict[int, str] = {}

        for idx, task_data in enumerate(pattern_data["tasks"]):
            task = Task(
                name=task_data["name"],
                description=task_data["description"],
                priority=task_data["priority"],
            )
            task_map[idx] = str(task.id)
            plan.tasks.append(task)

        dependencies_graph = pattern_data["dependencies_graph"]
        for task_idx, deps in dependencies_graph.items():
            task = plan.tasks[task_idx]
            task.dependencies = [task_map[dep_idx] for dep_idx in deps]

        return plan

    def _build_generic_plan(self, goal: str) -> Plan:
        """Build a generic plan for unmatched goals."""
        plan = Plan(goal=goal)

        task_stages = [
            {
                "name": "Analyze requirements",
                "description": f"Understand the requirements for: {goal}",
                "priority": 100,
            },
            {
                "name": "Design solution",
                "description": "Create a design/architecture for the solution",
                "priority": 90,
            },
            {
                "name": "Implement solution",
                "description": "Build the solution according to design",
                "priority": 80,
            },
            {
                "name": "Test solution",
                "description": "Verify the solution works correctly",
                "priority": 70,
            },
            {
                "name": "Document solution",
                "description": "Create documentation for the solution",
                "priority": 60,
            },
        ]

        task_ids = []
        for idx, stage_data in enumerate(task_stages):
            task = Task(
                name=stage_data["name"],
                description=stage_data["description"],
                priority=stage_data["priority"],
            )
            if idx > 0:
                task.dependencies = [task_ids[idx - 1]]
            task_ids.append(str(task.id))
            plan.tasks.append(task)

        return plan


def decompose_goal(goal: str) -> Plan:
    """Convenience function to decompose a goal."""
    decomposer = TaskDecomposer()
    return decomposer.decompose(goal)
