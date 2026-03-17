"""Directed Acyclic Graph construction and deterministic traversal for planning."""

import heapq

from app.core.logger import get_logger
from app.planning.models import TaskNode

logger = get_logger(__name__)


class PlanningCycleError(ValueError):
    """Raised when planning encounters a cycle in task dependencies."""


class DependencyGraph:
    """Builds and queries a DAG from TaskNode inputs.

    Workflow::

        graph = DependencyGraph()
        graph.build(tasks)
        ordered_ids = graph.topological_sort()
        groups = graph.execution_groups(ordered_ids)
    """

    def __init__(self) -> None:
        """Initialize an empty graph."""
        self._nodes: dict[str, TaskNode] = {}
        # adjacency: dep_id -> set of task_ids that depend on it (forward edges)
        self._adjacency: dict[str, set[str]] = {}
        self._in_degree: dict[str, int] = {}

    def build(self, tasks: list[TaskNode]) -> None:
        """Populate the graph from a list of TaskNodes.

        Args:
            tasks: Validated, duplicate-free task list (see PlanValidator).
        """
        self._nodes.clear()
        self._adjacency.clear()
        self._in_degree.clear()

        logger.info("graph_build_started", {"task_count": len(tasks)})

        for task in tasks:
            self._nodes[task.id] = task
            self._adjacency[task.id] = set()
            self._in_degree[task.id] = 0

        for task in tasks:
            for dep_id in task.dependencies:
                self._adjacency[dep_id].add(task.id)
                self._in_degree[task.id] += 1

        logger.info(
            "graph_build_completed",
            {
                "node_count": len(self._nodes),
                "edge_count": sum(len(neighbors) for neighbors in self._adjacency.values()),
            },
        )

    def has_cycle(self) -> bool:
        """Return True if the graph contains a directed cycle.

        Uses recursive DFS with a recursion-stack to detect back edges.
        Traversal order over neighbours is sorted for determinism.
        """
        logger.debug("graph_cycle_check_started", {"node_count": len(self._nodes)})
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def _dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            for neighbor in sorted(self._adjacency[node_id]):
                if neighbor not in visited:
                    if _dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node_id)
            return False

        for node_id in sorted(self._nodes):
            if node_id not in visited and _dfs(node_id):
                logger.error("graph_cycle_check_failed", "Dependency cycle detected")
                return True
        logger.debug("graph_cycle_check_completed", {"has_cycle": False})
        return False

    def traverse_levels(self) -> tuple[list[str], list[list[str]]]:
        """Topologically traverse the graph in deterministic level-order.

        Returns both the overall ordered IDs and execution groups produced during
        traversal. This avoids post-processing groups after sorting.
        """
        logger.info("graph_traversal_started", {"node_count": len(self._nodes)})

        if self.has_cycle():
            raise PlanningCycleError("Cycle detected in task dependencies")

        in_degree = self._in_degree.copy()
        current_ready: list[str] = [
            node_id for node_id, degree in in_degree.items() if degree == 0
        ]
        heapq.heapify(current_ready)

        ordered: list[str] = []
        groups: list[list[str]] = []

        while current_ready:
            level_size = len(current_ready)
            group: list[str] = []
            next_ready: list[str] = []

            for _ in range(level_size):
                node_id = heapq.heappop(current_ready)
                ordered.append(node_id)
                group.append(node_id)

                for neighbor in sorted(self._adjacency[node_id]):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        heapq.heappush(next_ready, neighbor)

            groups.append(group)
            current_ready = next_ready

        if len(ordered) != len(self._nodes):
            raise PlanningCycleError("Cycle detected in task dependencies")

        logger.info(
            "graph_traversal_completed",
            {
                "ordered_count": len(ordered),
                "group_count": len(groups),
            },
        )
        return ordered, groups

    def topological_sort(self) -> list[str]:
        """Return task IDs in deterministic topological order (Kahn's algorithm).

        Ties between concurrently-ready tasks are broken by alphabetical ID order
        so the output is stable across runs for the same input.

        Returns:
            List of task IDs where every dependency appears before its dependent.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        ordered_ids, _ = self.traverse_levels()
        return ordered_ids

    def execution_groups(self, sorted_ids: list[str] | None = None) -> list[list[str]]:
        """Group task IDs by topological levels discovered during traversal.

        Level 0 contains tasks with no dependencies. Level N contains tasks
        whose dependencies are all resolved by prior levels.

        Args:
            sorted_ids: Pre-computed topological order. If None, computed
                internally (which re-runs cycle detection).

        Returns:
            List of groups; each group is a sorted list of task IDs.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        if sorted_ids is not None:
            logger.debug(
                "graph_execution_groups_sorted_ids_ignored",
                {"reason": "groups are computed during level traversal"},
            )
        _, groups = self.traverse_levels()
        return groups

    @property
    def nodes(self) -> dict[str, TaskNode]:
        """Read-only view of all task nodes keyed by task ID."""
        return self._nodes
