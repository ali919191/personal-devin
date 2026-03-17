"""Directed Acyclic Graph construction and topological ordering for the planning engine."""

from app.planning.models import TaskNode


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

        for task in tasks:
            self._nodes[task.id] = task
            self._adjacency[task.id] = set()
            self._in_degree[task.id] = 0

        for task in tasks:
            for dep_id in task.dependencies:
                self._adjacency[dep_id].add(task.id)
                self._in_degree[task.id] += 1

    def has_cycle(self) -> bool:
        """Return True if the graph contains a directed cycle.

        Uses recursive DFS with a recursion-stack to detect back edges.
        Traversal order over neighbours is sorted for determinism.
        """
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
                return True
        return False

    def topological_sort(self) -> list[str]:
        """Return task IDs in deterministic topological order (Kahn's algorithm).

        Ties between concurrently-ready tasks are broken by alphabetical ID order
        so the output is stable across runs for the same input.

        Returns:
            List of task IDs where every dependency appears before its dependent.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        if self.has_cycle():
            raise ValueError("Topological sort failed: graph contains a cycle")

        in_degree = self._in_degree.copy()
        ready: list[str] = sorted(nid for nid, deg in in_degree.items() if deg == 0)
        result: list[str] = []

        while ready:
            node_id = ready.pop(0)
            result.append(node_id)
            newly_ready: list[str] = []
            for neighbor in sorted(self._adjacency[node_id]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    newly_ready.append(neighbor)
            ready = sorted(ready + newly_ready)

        if len(result) != len(self._nodes):
            raise ValueError(
                "Topological sort incomplete: unreachable nodes detected"
            )

        return result

    def execution_groups(self, sorted_ids: list[str] | None = None) -> list[list[str]]:
        """Group task IDs by their parallelisable execution level.

        Tasks within the same group have no inter-dependencies and can run
        concurrently. Groups are ordered from independent (level 0) to most
        dependent (highest level). Task IDs inside each group are sorted
        alphabetically for determinism.

        Args:
            sorted_ids: Pre-computed topological order. If None, computed
                internally (which re-runs cycle detection).

        Returns:
            List of groups; each group is a sorted list of task IDs.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        if sorted_ids is None:
            sorted_ids = self.topological_sort()

        level: dict[str, int] = {}
        for node_id in sorted_ids:
            task = self._nodes[node_id]
            if not task.dependencies:
                level[node_id] = 0
            else:
                level[node_id] = max(level[dep] for dep in task.dependencies) + 1

        max_level = max(level.values()) if level else 0
        groups: list[list[str]] = []
        for lvl in range(max_level + 1):
            group = sorted(nid for nid, lv in level.items() if lv == lvl)
            if group:
                groups.append(group)
        return groups

    @property
    def nodes(self) -> dict[str, TaskNode]:
        """Read-only view of all task nodes keyed by task ID."""
        return self._nodes
