"""Tests for DependencyGraph — DAG construction, cycle detection, and topological sort."""

import pytest

from app.planning.graph import DependencyGraph
from app.planning.models import TaskNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_task(task_id: str, deps: list[str] | None = None) -> TaskNode:
    return TaskNode(id=task_id, description=f"Task {task_id}", dependencies=deps or [])


def build_graph(tasks: list[TaskNode]) -> DependencyGraph:
    graph = DependencyGraph()
    graph.build(tasks)
    return graph


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


class TestDependencyGraphBuild:
    def test_empty_graph(self) -> None:
        graph = build_graph([])
        assert len(graph.nodes) == 0

    def test_single_node(self) -> None:
        graph = build_graph([make_task("a")])
        assert "a" in graph.nodes
        assert len(graph.nodes) == 1

    def test_multiple_independent_nodes(self) -> None:
        tasks = [make_task("a"), make_task("b"), make_task("c")]
        graph = build_graph(tasks)
        assert len(graph.nodes) == 3

    def test_nodes_preserve_task_references(self) -> None:
        task = make_task("x", deps=[])
        graph = build_graph([task])
        assert graph.nodes["x"] is task


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_no_cycle_empty(self) -> None:
        assert not build_graph([]).has_cycle()

    def test_no_cycle_single(self) -> None:
        assert not build_graph([make_task("a")]).has_cycle()

    def test_no_cycle_linear_chain(self) -> None:
        tasks = [
            make_task("a"),
            make_task("b", deps=["a"]),
            make_task("c", deps=["b"]),
        ]
        assert not build_graph(tasks).has_cycle()

    def test_no_cycle_diamond(self) -> None:
        tasks = [
            make_task("a"),
            make_task("b", deps=["a"]),
            make_task("c", deps=["a"]),
            make_task("d", deps=["b", "c"]),
        ]
        assert not build_graph(tasks).has_cycle()

    def test_cycle_two_nodes(self) -> None:
        tasks = [make_task("a", deps=["b"]), make_task("b", deps=["a"])]
        assert build_graph(tasks).has_cycle()

    def test_cycle_three_nodes(self) -> None:
        tasks = [
            make_task("a", deps=["c"]),
            make_task("b", deps=["a"]),
            make_task("c", deps=["b"]),
        ]
        assert build_graph(tasks).has_cycle()

    def test_cycle_with_innocent_node(self) -> None:
        """Cycle exists even when other nodes are clean."""
        tasks = [
            make_task("standalone"),
            make_task("x", deps=["y"]),
            make_task("y", deps=["x"]),
        ]
        assert build_graph(tasks).has_cycle()


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    def test_empty_graph(self) -> None:
        assert build_graph([]).topological_sort() == []

    def test_single_node(self) -> None:
        assert build_graph([make_task("a")]).topological_sort() == ["a"]

    def test_linear_chain_preserves_order(self) -> None:
        tasks = [make_task("a"), make_task("b", deps=["a"]), make_task("c", deps=["b"])]
        result = build_graph(tasks).topological_sort()
        assert result.index("a") < result.index("b")
        assert result.index("b") < result.index("c")

    def test_diamond_dependency_order(self) -> None:
        tasks = [
            make_task("a"),
            make_task("b", deps=["a"]),
            make_task("c", deps=["a"]),
            make_task("d", deps=["b", "c"]),
        ]
        result = build_graph(tasks).topological_sort()
        assert result.index("a") < result.index("b")
        assert result.index("a") < result.index("c")
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")

    def test_alphabetical_tiebreaking(self) -> None:
        """When multiple tasks are ready, alphabetical ID order is used."""
        tasks = [
            make_task("root"),
            make_task("c_task", deps=["root"]),
            make_task("a_task", deps=["root"]),
            make_task("b_task", deps=["root"]),
        ]
        result = build_graph(tasks).topological_sort()
        assert result[0] == "root"
        assert result[1:] == ["a_task", "b_task", "c_task"]

    def test_deterministic_across_calls(self) -> None:
        tasks = [
            make_task("root"),
            make_task("z", deps=["root"]),
            make_task("m", deps=["root"]),
            make_task("a", deps=["root"]),
        ]
        graph = build_graph(tasks)
        assert graph.topological_sort() == graph.topological_sort()

    def test_multi_branch_dag(self) -> None:
        """Valid multi-branch DAG where branches merge at a sink node."""
        tasks = [
            make_task("t1"),
            make_task("t2"),
            make_task("t3", deps=["t1"]),
            make_task("t4", deps=["t2"]),
            make_task("t5", deps=["t3", "t4"]),
        ]
        result = build_graph(tasks).topological_sort()
        assert result.index("t1") < result.index("t3")
        assert result.index("t2") < result.index("t4")
        assert result.index("t3") < result.index("t5")
        assert result.index("t4") < result.index("t5")

    def test_raises_on_cycle(self) -> None:
        tasks = [make_task("a", deps=["b"]), make_task("b", deps=["a"])]
        with pytest.raises(ValueError, match="Cycle detected in task dependencies"):
            build_graph(tasks).topological_sort()


# ---------------------------------------------------------------------------
# Execution groups
# ---------------------------------------------------------------------------


class TestExecutionGroups:
    def test_empty_graph(self) -> None:
        assert build_graph([]).execution_groups() == []

    def test_single_task_one_group(self) -> None:
        groups = build_graph([make_task("a")]).execution_groups()
        assert groups == [["a"]]

    def test_all_independent_tasks_single_group(self) -> None:
        tasks = [make_task("a"), make_task("b"), make_task("c")]
        groups = build_graph(tasks).execution_groups()
        assert len(groups) == 1
        assert sorted(groups[0]) == ["a", "b", "c"]

    def test_linear_chain_separate_groups(self) -> None:
        tasks = [make_task("a"), make_task("b", deps=["a"]), make_task("c", deps=["b"])]
        groups = build_graph(tasks).execution_groups()
        assert len(groups) == 3
        assert groups[0] == ["a"]
        assert groups[1] == ["b"]
        assert groups[2] == ["c"]

    def test_diamond_produces_three_groups(self) -> None:
        tasks = [
            make_task("a"),
            make_task("b", deps=["a"]),
            make_task("c", deps=["a"]),
            make_task("d", deps=["b", "c"]),
        ]
        groups = build_graph(tasks).execution_groups()
        assert len(groups) == 3
        assert groups[0] == ["a"]
        assert sorted(groups[1]) == ["b", "c"]
        assert groups[2] == ["d"]

    def test_groups_within_level_sorted_alphabetically(self) -> None:
        tasks = [
            make_task("root"),
            make_task("z", deps=["root"]),
            make_task("a", deps=["root"]),
        ]
        groups = build_graph(tasks).execution_groups()
        assert groups[1] == ["a", "z"]

    def test_accepts_precomputed_sorted_ids(self) -> None:
        """Passing sorted_ids skips the internal re-sort."""
        tasks = [make_task("a"), make_task("b", deps=["a"]), make_task("c", deps=["b"])]
        graph = build_graph(tasks)
        sorted_ids = graph.topological_sort()
        groups_direct = graph.execution_groups()
        groups_passed = graph.execution_groups(sorted_ids)
        assert groups_direct == groups_passed

    def test_raises_on_cycle(self) -> None:
        tasks = [make_task("a", deps=["b"]), make_task("b", deps=["a"])]
        with pytest.raises(ValueError, match="Cycle detected in task dependencies"):
            build_graph(tasks).execution_groups()
