"""Tests for PlanValidator — input validation before planning."""

import pytest

from app.planning.models import TaskNode
from app.planning.validator import PlanValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_task(task_id: str, deps: list[str] | None = None) -> TaskNode:
    return TaskNode(id=task_id, description=f"Task {task_id}", dependencies=deps or [])


# ---------------------------------------------------------------------------
# PlanValidator tests
# ---------------------------------------------------------------------------


class TestPlanValidator:
    def setup_method(self) -> None:
        self.validator = PlanValidator()

    def test_valid_empty_list(self) -> None:
        self.validator.validate([])  # must not raise

    def test_valid_single_task_no_deps(self) -> None:
        self.validator.validate([make_task("t1")])

    def test_valid_tasks_with_deps(self) -> None:
        tasks = [
            make_task("t1"),
            make_task("t2", deps=["t1"]),
            make_task("t3", deps=["t1", "t2"]),
        ]
        self.validator.validate(tasks)  # must not raise

    def test_valid_multi_branch(self) -> None:
        tasks = [
            make_task("a"),
            make_task("b"),
            make_task("c", deps=["a"]),
            make_task("d", deps=["b"]),
            make_task("e", deps=["c", "d"]),
        ]
        self.validator.validate(tasks)

    # --- duplicate ID ---

    def test_duplicate_id_raises(self) -> None:
        tasks = [make_task("dup"), make_task("dup")]
        with pytest.raises(ValueError, match="Duplicate task ID"):
            self.validator.validate(tasks)

    def test_duplicate_id_error_includes_id(self) -> None:
        tasks = [make_task("clash"), make_task("clash")]
        with pytest.raises(ValueError, match="clash"):
            self.validator.validate(tasks)

    def test_no_false_positive_similar_ids(self) -> None:
        """IDs that look similar but differ must not trigger duplicate error."""
        tasks = [make_task("task_1"), make_task("task_10"), make_task("task_100")]
        self.validator.validate(tasks)

    # --- missing dependency ---

    def test_missing_dep_raises(self) -> None:
        tasks = [make_task("t1", deps=["nonexistent"])]
        with pytest.raises(ValueError, match="unknown dependency"):
            self.validator.validate(tasks)

    def test_missing_dep_error_includes_ids(self) -> None:
        tasks = [make_task("task_a", deps=["ghost_id"])]
        with pytest.raises(ValueError) as exc_info:
            self.validator.validate(tasks)
        msg = str(exc_info.value)
        assert "task_a" in msg
        assert "ghost_id" in msg

    def test_multiple_missing_deps_catches_first(self) -> None:
        """Validator stops at the first unknown dependency it encounters."""
        tasks = [make_task("t1", deps=["missing_x", "missing_y"])]
        with pytest.raises(ValueError):
            self.validator.validate(tasks)

    def test_self_reference_dep_raises(self) -> None:
        """A task referencing itself is technically valid at the validator level
        (it exists as a task ID) but is caught by the cycle detector."""
        tasks = [make_task("t1"), make_task("t2", deps=["t2"])]
        # t2 references itself — it IS in the task list, so no missing-dep error
        self.validator.validate(tasks)

    # --- duplicate checked before missing dep ---

    def test_duplicate_checked_before_missing_dep(self) -> None:
        """Duplicate check happens first; missing dep error should not surface yet."""
        tasks = [
            make_task("dup", deps=["ghost"]),
            make_task("dup", deps=["ghost"]),
        ]
        with pytest.raises(ValueError, match="Duplicate"):
            self.validator.validate(tasks)
