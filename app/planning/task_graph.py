"""Directed Acyclic Graph (DAG) implementation for task dependencies."""

import heapq
from typing import Optional

from app.planning.models import Task


class TaskGraph:
    """Manages task dependencies as a DAG."""

    def __init__(self) -> None:
        """Initialize the task graph."""
        self.tasks: dict[str, Task] = {}
        self.adjacency: dict[str, set[str]] = {}
        self.in_degree: dict[str, int] = {}

    def _task_sort_key(self, task_id: str) -> tuple[int, str, str]:
        """Build a deterministic ordering key for topological sorting."""
        task = self.tasks[task_id]
        # Higher priority first, then stable lexical name, then ID.
        return (-task.priority, task.name.lower(), task_id)

    def add_task(self, task: Task) -> None:
        """Add a task to the graph."""
        task_id = str(task.id)
        if task_id not in self.tasks:
            self.tasks[task_id] = task
            self.adjacency[task_id] = set()
            self.in_degree[task_id] = 0
        else:
            raise ValueError(f"Task {task_id} already exists")

    def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """Add a dependency: task_id depends on depends_on_id."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        if depends_on_id not in self.tasks:
            raise ValueError(f"Dependency task {depends_on_id} not found")
        if task_id == depends_on_id:
            raise ValueError("Task cannot depend on itself")

        if task_id not in self.adjacency[depends_on_id]:
            self.adjacency[depends_on_id].add(task_id)
            self.in_degree[task_id] += 1
            if depends_on_id not in self.tasks[task_id].dependencies:
                self.tasks[task_id].dependencies.append(depends_on_id)

    def validate_no_cycles(self) -> bool:
        """Validate that the graph has no cycles using DFS."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle_dfs(node: str) -> bool:
            """Detect cycle using DFS."""
            visited.add(node)
            rec_stack.add(node)

            for neighbor in sorted(self.adjacency[node], key=self._task_sort_key):
                if neighbor not in visited:
                    if has_cycle_dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in sorted(self.tasks, key=self._task_sort_key):
            if node not in visited:
                if has_cycle_dfs(node):
                    return False

        return True

    def topological_sort(self) -> list[str]:
        """Sort tasks topologically using Kahn's algorithm."""
        if not self.validate_no_cycles():
            raise ValueError("Graph contains cycles")

        in_degree = self.in_degree.copy()
        queue: list[tuple[tuple[int, str, str], str]] = []
        for task_id in self.tasks:
            if in_degree[task_id] == 0:
                heapq.heappush(queue, (self._task_sort_key(task_id), task_id))
        result: list[str] = []

        while queue:
            _, node = heapq.heappop(queue)
            result.append(node)

            for neighbor in sorted(self.adjacency[node], key=self._task_sort_key):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    heapq.heappush(queue, (self._task_sort_key(neighbor), neighbor))

        if len(result) != len(self.tasks):
            raise ValueError("Topological sort failed: unreachable tasks or cycles")

        return result

    def get_execution_order(self) -> list[Task]:
        """Get tasks in execution order."""
        sorted_ids = self.topological_sort()
        return [self.tasks[task_id] for task_id in sorted_ids]

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID."""
        return self.tasks.get(task_id)

    def __repr__(self) -> str:
        """String representation."""
        return f"TaskGraph(tasks={len(self.tasks)}, edges={sum(len(v) for v in self.adjacency.values())})"
