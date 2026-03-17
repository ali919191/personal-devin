"""Tests for planning public API: build_execution_plan."""

import pytest

from app.planning.models import ExecutionPlan
from app.planning.planner import build_execution_plan


def make_task_dict(task_id: str, deps: list[str] | None = None) -> dict:
    return {
        "id": task_id,
        "description": f"Task {task_id}",
        "dependencies": deps or [],
    }


class TestBuildExecutionPlan:
    def test_output_is_execution_plan(self) -> None:
        plan = build_execution_plan([make_task_dict("t1")])
        assert isinstance(plan, ExecutionPlan)

    def test_output_contract_fields(self) -> None:
        plan = build_execution_plan([
            make_task_dict("a"),
            make_task_dict("b", deps=["a"]),
        ])

        assert hasattr(plan, "ordered_tasks")
        assert hasattr(plan, "execution_groups")
        assert hasattr(plan, "metadata")
        assert hasattr(plan.metadata, "total_tasks")
        assert hasattr(plan.metadata, "has_cycles")

    def test_single_public_interface_accepts_dicts(self) -> None:
        plan = build_execution_plan([
            {"id": "a", "description": "Task A", "dependencies": []},
            {"id": "b", "description": "Task B", "dependencies": ["a"]},
        ])
        ids = [task.id for task in plan.ordered_tasks]
        assert ids == ["a", "b"]

    def test_linear_chain_order(self) -> None:
        plan = build_execution_plan([
            make_task_dict("a"),
            make_task_dict("b", deps=["a"]),
            make_task_dict("c", deps=["b"]),
        ])
        ids = [task.id for task in plan.ordered_tasks]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_diamond_execution_groups(self) -> None:
        plan = build_execution_plan([
            make_task_dict("a"),
            make_task_dict("b", deps=["a"]),
            make_task_dict("c", deps=["a"]),
            make_task_dict("d", deps=["b", "c"]),
        ])
        assert [group.task_ids for group in plan.execution_groups] == [
            ["a"],
            ["b", "c"],
            ["d"],
        ]

    def test_deterministic_output_same_input_twice(self) -> None:
        tasks = [
            make_task_dict("root"),
            make_task_dict("z", deps=["root"]),
            make_task_dict("m", deps=["root"]),
            make_task_dict("a", deps=["root"]),
        ]
        plan1 = build_execution_plan(tasks)
        plan2 = build_execution_plan(tasks)

        assert plan1 == plan2
        assert [task.id for task in plan1.ordered_tasks] == [
            task.id for task in plan2.ordered_tasks
        ]
        assert [group.task_ids for group in plan1.execution_groups] == [
            group.task_ids for group in plan2.execution_groups
        ]

    def test_complex_dag(self) -> None:
        plan = build_execution_plan([
            make_task_dict("a"),
            make_task_dict("b"),
            make_task_dict("c", deps=["a"]),
            make_task_dict("d", deps=["a"]),
            make_task_dict("e", deps=["b"]),
            make_task_dict("f", deps=["c", "e"]),
            make_task_dict("g", deps=["d", "f"]),
        ])
        ids = [task.id for task in plan.ordered_tasks]
        assert ids.index("a") < ids.index("c")
        assert ids.index("a") < ids.index("d")
        assert ids.index("b") < ids.index("e")
        assert ids.index("c") < ids.index("f")
        assert ids.index("e") < ids.index("f")
        assert ids.index("d") < ids.index("g")
        assert ids.index("f") < ids.index("g")

    def test_cycle_raises_explicit_exception(self) -> None:
        with pytest.raises(ValueError, match="Cycle detected in task dependencies"):
            build_execution_plan([
                make_task_dict("a", deps=["b"]),
                make_task_dict("b", deps=["a"]),
            ])

    def test_unknown_dependency_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown dependency"):
            build_execution_plan([make_task_dict("a", deps=["ghost"])])

    def test_duplicate_task_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Duplicate"):
            build_execution_plan([make_task_dict("dup"), make_task_dict("dup")])

    def test_invalid_input_non_list(self) -> None:
        with pytest.raises(ValueError, match="list of dictionaries"):
            build_execution_plan("not-a-list")  # type: ignore[arg-type]

    def test_invalid_input_non_dict_item(self) -> None:
        with pytest.raises(ValueError, match="must be a dictionary"):
            build_execution_plan([make_task_dict("ok"), "bad-item"])  # type: ignore[list-item]

    def test_invalid_input_missing_required_fields(self) -> None:
        with pytest.raises(ValueError, match="Invalid task at index 0"):
            build_execution_plan([{"id": "only-id"}])

    def test_invalid_input_missing_dependencies_key(self) -> None:
        with pytest.raises(ValueError, match="Invalid task at index 0"):
            build_execution_plan([{"id": "a", "description": "Task A"}])

    def test_empty_input(self) -> None:
        plan = build_execution_plan([])
        assert plan.ordered_tasks == []
        assert plan.execution_groups == []
        assert plan.metadata.total_tasks == 0
        assert plan.metadata.has_cycles is False
