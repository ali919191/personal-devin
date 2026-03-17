"""Tests for PlanningEngine — end-to-end plan building and output contract."""

import pytest

from app.planning.models import ExecutionPlan, TaskNode
from app.planning.planner import PlanningEngine, build_execution_plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_task(task_id: str, deps: list[str] | None = None) -> TaskNode:
    return TaskNode(id=task_id, description=f"Task {task_id}", dependencies=deps or [])


# ---------------------------------------------------------------------------
# PlanningEngine tests
# ---------------------------------------------------------------------------


class TestPlanningEngine:
    def setup_method(self) -> None:
        self.engine = PlanningEngine()

    # --- output contract ---

    def test_output_is_execution_plan(self) -> None:
        plan = self.engine.build_plan([make_task("t1")])
        assert isinstance(plan, ExecutionPlan)

    def test_output_contract_fields(self) -> None:
        """All required output-contract fields are present."""
        tasks = [make_task("a"), make_task("b", deps=["a"])]
        plan = self.engine.build_plan(tasks)

        assert hasattr(plan, "ordered_tasks")
        assert hasattr(plan, "execution_groups")
        assert hasattr(plan, "metadata")
        assert hasattr(plan.metadata, "total_tasks")
        assert hasattr(plan.metadata, "has_cycles")

    def test_metadata_total_tasks(self) -> None:
        tasks = [make_task("a"), make_task("b"), make_task("c")]
        plan = self.engine.build_plan(tasks)
        assert plan.metadata.total_tasks == 3

    def test_metadata_has_cycles_false(self) -> None:
        plan = self.engine.build_plan([make_task("a"), make_task("b", deps=["a"])])
        assert plan.metadata.has_cycles is False

    # --- single task ---

    def test_single_task(self) -> None:
        plan = self.engine.build_plan([make_task("only")])
        assert len(plan.ordered_tasks) == 1
        assert plan.ordered_tasks[0].id == "only"
        assert len(plan.execution_groups) == 1
        assert plan.execution_groups[0].task_ids == ["only"]

    # --- linear chain ---

    def test_linear_chain_order(self) -> None:
        tasks = [make_task("a"), make_task("b", deps=["a"]), make_task("c", deps=["b"])]
        plan = self.engine.build_plan(tasks)
        ids = [t.id for t in plan.ordered_tasks]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_linear_chain_groups(self) -> None:
        tasks = [make_task("a"), make_task("b", deps=["a"]), make_task("c", deps=["b"])]
        plan = self.engine.build_plan(tasks)
        assert len(plan.execution_groups) == 3
        assert plan.execution_groups[0].group_id == 0
        assert plan.execution_groups[0].task_ids == ["a"]

    # --- parallel independent tasks ---

    def test_parallel_tasks_single_group(self) -> None:
        tasks = [make_task("x"), make_task("y"), make_task("z")]
        plan = self.engine.build_plan(tasks)
        assert len(plan.execution_groups) == 1
        assert sorted(plan.execution_groups[0].task_ids) == ["x", "y", "z"]

    # --- diamond dependency ---

    def test_diamond_dependency(self) -> None:
        tasks = [
            make_task("a"),
            make_task("b", deps=["a"]),
            make_task("c", deps=["a"]),
            make_task("d", deps=["b", "c"]),
        ]
        plan = self.engine.build_plan(tasks)
        ids = [t.id for t in plan.ordered_tasks]
        assert ids.index("a") < ids.index("b")
        assert ids.index("a") < ids.index("c")
        assert ids.index("b") < ids.index("d")
        assert ids.index("c") < ids.index("d")

    def test_diamond_execution_groups(self) -> None:
        tasks = [
            make_task("a"),
            make_task("b", deps=["a"]),
            make_task("c", deps=["a"]),
            make_task("d", deps=["b", "c"]),
        ]
        plan = self.engine.build_plan(tasks)
        assert len(plan.execution_groups) == 3
        assert plan.execution_groups[0].task_ids == ["a"]
        assert sorted(plan.execution_groups[1].task_ids) == ["b", "c"]
        assert plan.execution_groups[2].task_ids == ["d"]

    # --- multi-branch DAG (requirement 5) ---

    def test_multi_branch_dag(self) -> None:
        """Valid multi-branch DAG with two independent chains merging at a sink."""
        tasks = [
            make_task("t1"),
            make_task("t2"),
            make_task("t3", deps=["t1"]),
            make_task("t4", deps=["t2"]),
            make_task("t5", deps=["t3", "t4"]),
        ]
        plan = self.engine.build_plan(tasks)
        ids = [t.id for t in plan.ordered_tasks]
        assert ids.index("t1") < ids.index("t3")
        assert ids.index("t2") < ids.index("t4")
        assert ids.index("t3") < ids.index("t5")
        assert ids.index("t4") < ids.index("t5")
        assert plan.metadata.total_tasks == 5

    # --- dependency satisfaction in output order ---

    def test_all_dependencies_satisfied_in_ordered_output(self) -> None:
        """For every task in ordered_tasks, all its dependencies appear before it."""
        tasks = [
            make_task("a"),
            make_task("b", deps=["a"]),
            make_task("c", deps=["a"]),
            make_task("d", deps=["b", "c"]),
            make_task("e", deps=["d"]),
        ]
        plan = self.engine.build_plan(tasks)
        seen: set[str] = set()
        for task in plan.ordered_tasks:
            for dep_id in task.dependencies:
                assert dep_id in seen, f"{dep_id!r} not yet seen when processing {task.id!r}"
            seen.add(task.id)

    # --- cycle detection (requirement 2) ---

    def test_cycle_raises_value_error(self) -> None:
        tasks = [make_task("a", deps=["b"]), make_task("b", deps=["a"])]
        with pytest.raises(ValueError, match="cycle"):
            self.engine.build_plan(tasks)

    def test_three_node_cycle_raises(self) -> None:
        tasks = [
            make_task("a", deps=["c"]),
            make_task("b", deps=["a"]),
            make_task("c", deps=["b"]),
        ]
        with pytest.raises(ValueError):
            self.engine.build_plan(tasks)

    # --- missing dependency (requirement 3) ---

    def test_missing_dependency_raises(self) -> None:
        tasks = [make_task("t1", deps=["nonexistent"])]
        with pytest.raises(ValueError, match="unknown dependency"):
            self.engine.build_plan(tasks)

    # --- duplicate task ID (requirement 4) ---

    def test_duplicate_task_id_raises(self) -> None:
        tasks = [make_task("dup"), make_task("dup")]
        with pytest.raises(ValueError, match="Duplicate"):
            self.engine.build_plan(tasks)

    # --- determinism ---

    def test_deterministic_output(self) -> None:
        """Same input always produces the same ordered_tasks and groups."""
        tasks = [
            make_task("root"),
            make_task("z", deps=["root"]),
            make_task("m", deps=["root"]),
            make_task("a", deps=["root"]),
        ]
        plan1 = self.engine.build_plan(tasks)
        plan2 = self.engine.build_plan(tasks)
        assert [t.id for t in plan1.ordered_tasks] == [t.id for t in plan2.ordered_tasks]
        assert (
            [g.task_ids for g in plan1.execution_groups]
            == [g.task_ids for g in plan2.execution_groups]
        )

    def test_alphabetical_tiebreaking_in_order(self) -> None:
        """When tasks are concurrently ready, alphabetical ID order determines output."""
        tasks = [
            make_task("root"),
            make_task("c_step", deps=["root"]),
            make_task("a_step", deps=["root"]),
            make_task("b_step", deps=["root"]),
        ]
        plan = self.engine.build_plan(tasks)
        ids = [t.id for t in plan.ordered_tasks]
        assert ids[0] == "root"
        assert ids[1:] == ["a_step", "b_step", "c_step"]

    # --- empty input ---

    def test_empty_task_list(self) -> None:
        plan = self.engine.build_plan([])
        assert plan.ordered_tasks == []
        assert plan.execution_groups == []
        assert plan.metadata.total_tasks == 0
        assert plan.metadata.has_cycles is False

    # --- execution group sequential IDs ---

    def test_execution_groups_sequential_group_ids(self) -> None:
        tasks = [make_task("a"), make_task("b", deps=["a"]), make_task("c", deps=["b"])]
        plan = self.engine.build_plan(tasks)
        for i, group in enumerate(plan.execution_groups):
            assert group.group_id == i


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def test_build_execution_plan_convenience() -> None:
    tasks = [make_task("a"), make_task("b", deps=["a"])]
    plan = build_execution_plan(tasks)
    assert isinstance(plan, ExecutionPlan)
    ids = [t.id for t in plan.ordered_tasks]
    assert ids.index("a") < ids.index("b")
