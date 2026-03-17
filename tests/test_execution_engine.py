"""Tests for Agent 03 — Execution Engine."""

import pytest

from app.execution.executor import Executor
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.execution.runner import Runner, run_plan
from app.planning.models import ExecutionPlan, ExecutionGroup, PlanMetadata, TaskNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_node(task_id: str, deps: list[str] | None = None) -> TaskNode:
    return TaskNode(id=task_id, description=f"Task {task_id}", dependencies=deps or [])


def make_plan(*nodes: TaskNode) -> ExecutionPlan:
    """Build a minimal ExecutionPlan from ordered TaskNodes (no real DAG needed for tests)."""
    node_list = list(nodes)
    return ExecutionPlan(
        ordered_tasks=node_list,
        execution_groups=[ExecutionGroup(group_id=0, task_ids=[n.id for n in node_list])],
        metadata=PlanMetadata(total_tasks=len(node_list), has_cycles=False),
    )


def always_fail(task: ExecutionTask) -> str:
    raise RuntimeError(f"Simulated failure for {task.id}")


def make_output(msg: str):
    def handler(task: ExecutionTask) -> str:
        return msg
    return handler


def tuple_success(msg: str):
    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        return (True, msg)

    return handler


def tuple_fail(msg: str):
    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        return (False, msg)

    return handler


# ---------------------------------------------------------------------------
# Executor unit tests
# ---------------------------------------------------------------------------


class TestExecutor:
    def setup_method(self) -> None:
        self.executor = Executor()

    def _make_task(self, task_id: str = "t1") -> ExecutionTask:
        return ExecutionTask(id=task_id, description="A task")

    def test_default_handler_completes_task(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task)
        assert result.status == ExecutionStatus.COMPLETED

    def test_default_handler_empty_output(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task)
        assert result.output == ""

    def test_custom_handler_sets_output(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task, handler=make_output("hello"))
        assert result.output == "hello"
        assert result.status == ExecutionStatus.COMPLETED

    def test_tuple_handler_success_sets_output(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task, handler=tuple_success("ok"))
        assert result.status == ExecutionStatus.COMPLETED
        assert result.output == "ok"

    def test_tuple_handler_failure_marks_failed(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task, handler=tuple_fail("boom"))
        assert result.status == ExecutionStatus.FAILED
        assert result.error == "boom"

    def test_failing_handler_marks_failed(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task, handler=always_fail)
        assert result.status == ExecutionStatus.FAILED

    def test_failing_handler_stores_error(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task, handler=always_fail)
        assert result.error is not None
        assert "Simulated failure" in result.error

    def test_timestamps_set_on_success(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task)
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    def test_timestamps_set_on_failure(self) -> None:
        task = self._make_task()
        result = self.executor.execute_task(task, handler=always_fail)
        assert result.started_at is not None
        assert result.completed_at is not None


# ---------------------------------------------------------------------------
# Runner tests — requirement 1: executes simple plan
# ---------------------------------------------------------------------------


class TestRunnerSimplePlan:
    def test_single_task_completes(self) -> None:
        plan = make_plan(make_node("t1"))
        report = run_plan(plan)
        assert report.status == ExecutionStatus.COMPLETED
        assert report.completed_tasks == 1
        assert report.failed_tasks == 0

    def test_multiple_independent_tasks_all_complete(self) -> None:
        plan = make_plan(make_node("a"), make_node("b"), make_node("c"))
        report = run_plan(plan)
        assert report.status == ExecutionStatus.COMPLETED
        assert report.completed_tasks == 3

    def test_linear_chain_all_complete(self) -> None:
        plan = make_plan(
            make_node("t1"),
            make_node("t2", deps=["t1"]),
            make_node("t3", deps=["t2"]),
        )
        report = run_plan(plan)
        assert report.status == ExecutionStatus.COMPLETED
        assert report.completed_tasks == 3

    def test_empty_plan(self) -> None:
        plan = make_plan()
        report = run_plan(plan)
        assert report.status == ExecutionStatus.COMPLETED
        assert report.total_tasks == 0
        assert report.completed_tasks == 0


# ---------------------------------------------------------------------------
# Runner tests — requirement 2: handles failed step
# ---------------------------------------------------------------------------


class TestRunnerFailedStep:
    def test_failed_step_marks_report_failed(self) -> None:
        plan = make_plan(make_node("t1"), make_node("t2"))
        report = run_plan(plan, handlers={"t1": always_fail})
        assert report.status == ExecutionStatus.FAILED
        assert report.failed_tasks == 1

    def test_stop_on_failure_skips_remaining(self) -> None:
        plan = make_plan(make_node("t1"), make_node("t2"), make_node("t3"))
        report = run_plan(
            plan,
            handlers={"t1": always_fail},
            stop_on_failure=True,
        )
        assert report.failed_tasks == 1
        assert report.skipped_tasks == 2

    def test_continue_on_failure_runs_all_independent_tasks(self) -> None:
        """In continue mode independent tasks after a failure still run."""
        plan = make_plan(make_node("a"), make_node("b"), make_node("c"))
        report = run_plan(
            plan,
            handlers={"a": always_fail},
            stop_on_failure=False,
        )
        assert report.failed_tasks == 1
        assert report.completed_tasks == 2

    def test_dependent_task_skipped_when_dep_fails(self) -> None:
        """A task whose dependency failed should be SKIPPED, not run."""
        plan = make_plan(make_node("t1"), make_node("t2", deps=["t1"]))
        report = run_plan(plan, handlers={"t1": always_fail})
        t2_task = next(t for t in report.tasks if t.id == "t2")
        assert t2_task.status == ExecutionStatus.SKIPPED

    def test_skipped_task_contains_reason(self) -> None:
        plan = make_plan(make_node("t1"), make_node("t2", deps=["t1"]))
        report = run_plan(plan, handlers={"t1": always_fail})
        t2_task = next(t for t in report.tasks if t.id == "t2")
        assert t2_task.skip_reason is not None
        assert t2_task.error is not None
        assert "did not complete successfully" in t2_task.error

    def test_failed_task_stores_error_in_report(self) -> None:
        plan = make_plan(make_node("t1"))
        report = run_plan(plan, handlers={"t1": always_fail})
        t1_task = report.tasks[0]
        assert t1_task.error is not None
        assert "Simulated failure" in t1_task.error


# ---------------------------------------------------------------------------
# Runner tests — requirement 3: maintains order
# ---------------------------------------------------------------------------


class TestRunnerOrder:
    def test_tasks_executed_in_plan_order(self) -> None:
        execution_order: list[str] = []

        def recorder(task: ExecutionTask) -> str:
            execution_order.append(task.id)
            return ""

        plan = make_plan(
            make_node("first"),
            make_node("second"),
            make_node("third"),
        )
        run_plan(plan, handlers={"first": recorder, "second": recorder, "third": recorder})
        assert execution_order == ["first", "second", "third"]

    def test_dependency_always_before_dependent(self) -> None:
        execution_order: list[str] = []

        def recorder(task: ExecutionTask) -> str:
            execution_order.append(task.id)
            return ""

        plan = make_plan(
            make_node("root"),
            make_node("child", deps=["root"]),
            make_node("leaf", deps=["child"]),
        )
        run_plan(
            plan,
            handlers={"root": recorder, "child": recorder, "leaf": recorder},
        )
        assert execution_order.index("root") < execution_order.index("child")
        assert execution_order.index("child") < execution_order.index("leaf")

    def test_all_deps_satisfied_before_task_runs(self) -> None:
        """No task runs before its dependency is COMPLETED."""
        completed_ids: set[str] = set()

        def recording_handler(task: ExecutionTask) -> str:
            for dep_id in task.dependencies:
                assert dep_id in completed_ids, (
                    f"{dep_id!r} was not yet completed when {task.id!r} ran"
                )
            completed_ids.add(task.id)
            return ""

        nodes = [
            make_node("a"),
            make_node("b", deps=["a"]),
            make_node("c", deps=["a"]),
            make_node("d", deps=["b", "c"]),
        ]
        plan = make_plan(*nodes)
        run_plan(plan, handlers={n.id: recording_handler for n in nodes})

    def test_same_input_plan_produces_same_execution_order(self) -> None:
        def make_recorder(out: list[str]):
            def recorder(task: ExecutionTask) -> str:
                out.append(task.id)
                return ""

            return recorder

        plan = make_plan(
            make_node("root"),
            make_node("left", deps=["root"]),
            make_node("right", deps=["root"]),
            make_node("merge", deps=["left", "right"]),
        )

        order1: list[str] = []
        order2: list[str] = []

        run_plan(
            plan,
            handlers={
                "root": make_recorder(order1),
                "left": make_recorder(order1),
                "right": make_recorder(order1),
                "merge": make_recorder(order1),
            },
        )
        run_plan(
            plan,
            handlers={
                "root": make_recorder(order2),
                "left": make_recorder(order2),
                "right": make_recorder(order2),
                "merge": make_recorder(order2),
            },
        )

        assert order1 == order2


# ---------------------------------------------------------------------------
# Runner tests — requirement 4: correct execution report
# ---------------------------------------------------------------------------


class TestExecutionReport:
    def test_report_is_execution_report_instance(self) -> None:
        plan = make_plan(make_node("t1"))
        report = run_plan(plan)
        assert isinstance(report, ExecutionReport)

    def test_report_total_tasks(self) -> None:
        plan = make_plan(make_node("a"), make_node("b"), make_node("c"))
        report = run_plan(plan)
        assert report.total_tasks == 3

    def test_report_completed_count(self) -> None:
        plan = make_plan(make_node("a"), make_node("b"))
        report = run_plan(plan)
        assert report.completed_tasks == 2
        assert report.failed_tasks == 0
        assert report.skipped_tasks == 0

    def test_report_contains_all_tasks(self) -> None:
        plan = make_plan(make_node("x"), make_node("y"), make_node("z"))
        report = run_plan(plan)
        ids = {t.id for t in report.tasks}
        assert ids == {"x", "y", "z"}

    def test_report_timings_populated(self) -> None:
        plan = make_plan(make_node("t1"))
        report = run_plan(plan)
        assert report.started_at is not None
        assert report.completed_at is not None
        assert report.completed_at >= report.started_at

    def test_report_task_statuses_on_success(self) -> None:
        plan = make_plan(make_node("t1"), make_node("t2"))
        report = run_plan(plan)
        for task in report.tasks:
            assert task.status == ExecutionStatus.COMPLETED

    def test_report_mixed_statuses(self) -> None:
        plan = make_plan(
            make_node("t1"),
            make_node("t2"),
            make_node("t3"),
        )
        report = run_plan(
            plan,
            handlers={"t1": always_fail},
            stop_on_failure=True,
        )
        statuses = {t.id: t.status for t in report.tasks}
        assert statuses["t1"] == ExecutionStatus.FAILED
        assert statuses["t2"] == ExecutionStatus.SKIPPED
        assert statuses["t3"] == ExecutionStatus.SKIPPED

    def test_report_custom_outputs_stored(self) -> None:
        plan = make_plan(make_node("t1"))
        report = run_plan(plan, handlers={"t1": make_output("result_data")})
        assert report.tasks[0].output == "result_data"


# ---------------------------------------------------------------------------
# Integration: planning → execution pipeline
# ---------------------------------------------------------------------------


class TestPlanningToExecution:
    """Verify that ExecutionPlan output from Planning Engine flows into Runner."""

    def test_full_pipeline_simple(self) -> None:
        from app.planning.planner import build_execution_plan

        tasks = [
            {"id": "design", "description": "Design schema", "dependencies": []},
            {"id": "build", "description": "Build API", "dependencies": ["design"]},
            {"id": "test", "description": "Run tests", "dependencies": ["build"]},
        ]
        plan = build_execution_plan(tasks)
        report = run_plan(plan)

        assert report.status == ExecutionStatus.COMPLETED
        assert report.completed_tasks == 3
        assert report.total_tasks == 3

    def test_full_pipeline_with_failure(self) -> None:
        from app.planning.planner import build_execution_plan

        tasks = [
            {"id": "step1", "description": "Step 1", "dependencies": []},
            {"id": "step2", "description": "Step 2", "dependencies": ["step1"]},
        ]
        plan = build_execution_plan(tasks)
        report = run_plan(plan, handlers={"step1": always_fail})

        assert report.status == ExecutionStatus.FAILED
        assert report.failed_tasks == 1
        assert report.skipped_tasks == 1

    def test_full_pipeline_parallel_tasks(self) -> None:
        from app.planning.planner import build_execution_plan

        tasks = [
            {"id": "root", "description": "Root task", "dependencies": []},
            {"id": "branch_a", "description": "Branch A", "dependencies": ["root"]},
            {"id": "branch_b", "description": "Branch B", "dependencies": ["root"]},
            {
                "id": "merge",
                "description": "Merge",
                "dependencies": ["branch_a", "branch_b"],
            },
        ]
        plan = build_execution_plan(tasks)
        report = run_plan(plan)

        assert report.status == ExecutionStatus.COMPLETED
        assert report.completed_tasks == 4
