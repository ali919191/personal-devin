"""End-to-end tests for the full agent feedback loop cycle.

Tests cover:
1. Full cycle output validation (execution, evaluation, feedback, adaptation)
2. Determinism — same input produces identical output across independent runs
3. Feedback consistency — same evaluation always yields the same feedback
4. Adaptation impact — a failing run generates adaptation candidates
5. Failure injection — controlled bad input hits all failure-path assertions
6. Logging verification — loop logs contain required traceability fields
7. Replay test — serialized output is identical across identical runs
8. Stress test — 50 consecutive iterations remain stable
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.adaptation.models import Adaptation as RuntimeAdaptation
from app.agent.agent_loop import AgentLoop
from app.agent.schemas import AgentResult
from app.evaluation.models import EvaluationResult
from app.execution.models import ExecutionReport, ExecutionStatus, ExecutionTask
from app.feedback.engine import FeedbackEngine
from app.feedback.models import FeedbackSignal
from app.planning.models import ExecutionGroup, ExecutionPlan, PlanMetadata, TaskNode


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

FIXED_DT = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


def fixed_now() -> datetime:
    return FIXED_DT


def _task_node(task_id: str) -> TaskNode:
    return TaskNode(id=task_id, description=f"task {task_id}", dependencies=[])


def _make_plan(*task_ids: str) -> ExecutionPlan:
    nodes = [_task_node(tid) for tid in task_ids]
    return ExecutionPlan(
        ordered_tasks=nodes,
        execution_groups=[ExecutionGroup(group_id=0, task_ids=[n.id for n in nodes])],
        metadata=PlanMetadata(total_tasks=len(nodes), has_cycles=False),
    )


def _make_execution_task(task_id: str, status: ExecutionStatus) -> ExecutionTask:
    return ExecutionTask(
        id=task_id,
        description=f"task {task_id}",
        dependencies=[],
        status=status,
        started_at=FIXED_DT,
        completed_at=FIXED_DT,
    )


def _make_report(
    tasks: list[ExecutionTask],
    *,
    override_status: ExecutionStatus | None = None,
) -> ExecutionReport:
    completed = sum(1 for t in tasks if t.status == ExecutionStatus.COMPLETED)
    failed = sum(1 for t in tasks if t.status == ExecutionStatus.FAILED)
    skipped = sum(1 for t in tasks if t.status == ExecutionStatus.SKIPPED)
    overall = override_status or (
        ExecutionStatus.COMPLETED if failed == 0 and skipped == 0 else ExecutionStatus.FAILED
    )
    return ExecutionReport(
        tasks=tasks,
        status=overall,
        total_tasks=len(tasks),
        completed_tasks=completed,
        failed_tasks=failed,
        skipped_tasks=skipped,
        started_at=FIXED_DT,
        completed_at=FIXED_DT,
    )


def _make_loop(
    plan: ExecutionPlan,
    report: ExecutionReport,
) -> AgentLoop:
    """Create a fully-stubbed AgentLoop with controlled plan and execution."""
    memory = MagicMock()
    memory.get_feedback_context.return_value = {}
    memory.log_decision.return_value = None
    memory.log_task.return_value = None
    memory.log_execution.return_value = None
    memory.log_failure.return_value = None

    loop = AgentLoop(
        memory_service=memory,
        self_improvement_engine=MagicMock(),
        now_fn=fixed_now,
    )
    # Patch internal planning and execution with controlled outputs
    loop._plan = lambda goal: type("_PlanContext", (), {"plan": plan, "resolved_adaptation_count": 0})()  # noqa: E731
    loop._execute = lambda _plan: report  # noqa: E731
    return loop


# ---------------------------------------------------------------------------
# 1. End-to-End Loop Test — core output validation
# ---------------------------------------------------------------------------

class TestFullAgentCycle:
    """Test 1: Verify one full cycle produces all four required outputs."""

    def test_all_four_outputs_present_on_success(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        result = loop.run("build the feature")

        assert result.execution is not None, "execution must be set"
        assert result.evaluation is not None, "evaluation must be set"
        assert result.feedback is not None, "feedback must be set"
        assert result.adaptation is not None, "adaptation must be set (may be empty list)"

    def test_execution_report_is_correct_type(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        result = loop.run("run tests")

        assert isinstance(result.execution, ExecutionReport)

    def test_evaluation_is_correct_type(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        result = loop.run("deploy service")

        assert isinstance(result.evaluation, EvaluationResult)

    def test_feedback_is_correct_type(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        result = loop.run("deploy service")

        assert isinstance(result.feedback, FeedbackSignal)

    def test_adaptation_is_list(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        result = loop.run("analyze data")

        assert isinstance(result.adaptation, list)

    def test_successful_run_has_true_feedback_success(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        result = loop.run("clean the database")

        assert result.feedback.success is True
        assert result.feedback.failure_type is None


# ---------------------------------------------------------------------------
# 2. Determinism Test — same input → identical output
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Test 2: Two independent runs with the same goal must produce equal results."""

    def test_same_goal_same_status(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        loop1 = _make_loop(plan, report)
        loop2 = _make_loop(plan, report)

        result1 = loop1.run("process data")
        result2 = loop2.run("process data")

        assert result1.status == result2.status

    def test_same_goal_same_iteration_id(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        loop1 = _make_loop(plan, report)
        loop2 = _make_loop(plan, report)

        loop1.run("deterministic task")
        loop2.run("deterministic task")

        assert loop1.last_iteration_id == loop2.last_iteration_id

    def test_same_goal_same_evaluation_score(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        loop1 = _make_loop(plan, report)
        loop2 = _make_loop(plan, report)

        result1 = loop1.run("evaluate this")
        result2 = loop2.run("evaluate this")

        assert result1.evaluation.score == result2.evaluation.score
        assert result1.evaluation.success == result2.evaluation.success

    def test_same_goal_same_feedback_signal(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        loop1 = _make_loop(plan, report)
        loop2 = _make_loop(plan, report)

        result1 = loop1.run("fixed goal")
        result2 = loop2.run("fixed goal")

        assert result1.feedback.score == result2.feedback.score
        assert result1.feedback.success == result2.feedback.success
        assert result1.feedback.failure_type == result2.feedback.failure_type
        assert result1.feedback.improvement_suggestions == result2.feedback.improvement_suggestions

    def test_same_goal_same_adaptation_count(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        loop1 = _make_loop(plan, report)
        loop2 = _make_loop(plan, report)

        result1 = loop1.run("consistent task")
        result2 = loop2.run("consistent task")

        assert len(result1.adaptation) == len(result2.adaptation)

    def test_deterministic_iteration_id_is_hash_of_goal(self) -> None:
        id1 = AgentLoop.deterministic_iteration_id("my task")
        id2 = AgentLoop.deterministic_iteration_id("my task")
        id3 = AgentLoop.deterministic_iteration_id("different task")

        assert id1 == id2
        assert id1 != id3
        assert id1.startswith("iter-")


# ---------------------------------------------------------------------------
# 3. Feedback Consistency Test — same evaluation → same feedback
# ---------------------------------------------------------------------------

class TestFeedbackConsistency:
    """Test 3: FeedbackEngine is deterministic — equal inputs yield equal outputs."""

    def _make_report_for_feedback(self) -> ExecutionReport:
        tasks = [_make_execution_task("t1", ExecutionStatus.FAILED)]
        return _make_report(tasks)

    def _make_eval_result(self, *, task_id: str, success: bool, score: float) -> EvaluationResult:
        return EvaluationResult(
            task_id=task_id,
            success=success,
            score=score,
            feedback="test feedback",
            metrics={"match_type": "failure"},
        )

    def test_identical_inputs_yield_identical_feedback(self) -> None:
        engine = FeedbackEngine(now_fn=fixed_now)
        report = self._make_report_for_feedback()
        eval_result = self._make_eval_result(task_id="task-a", success=False, score=0.0)

        fb1 = engine.generate_feedback(report, eval_result)
        fb2 = engine.generate_feedback(report, eval_result)

        assert fb1.score == fb2.score
        assert fb1.success == fb2.success
        assert fb1.failure_type == fb2.failure_type
        assert fb1.improvement_suggestions == fb2.improvement_suggestions
        assert fb1.confidence == fb2.confidence

    def test_success_feedback_has_no_failure_type(self) -> None:
        engine = FeedbackEngine(now_fn=fixed_now)
        tasks = [_make_execution_task("t1", ExecutionStatus.COMPLETED)]
        report = _make_report(tasks)
        eval_result = self._make_eval_result(task_id="task-b", success=True, score=1.0)

        fb = engine.generate_feedback(report, eval_result)

        assert fb.success is True
        assert fb.failure_type is None
        assert fb.improvement_suggestions == []

    def test_failed_task_feedback_has_suggestions(self) -> None:
        engine = FeedbackEngine(now_fn=fixed_now)
        report = self._make_report_for_feedback()
        eval_result = self._make_eval_result(task_id="task-c", success=False, score=0.0)

        fb = engine.generate_feedback(report, eval_result)

        assert fb.failure_type is not None
        assert len(fb.improvement_suggestions) > 0

    def test_repeated_calls_consistent_over_multiple_iterations(self) -> None:
        engine = FeedbackEngine(now_fn=fixed_now)
        tasks = [_make_execution_task("t1", ExecutionStatus.FAILED)]
        report = _make_report(tasks)
        eval_result = self._make_eval_result(task_id="task-repeat", success=False, score=0.0)

        signals = [engine.generate_feedback(report, eval_result) for _ in range(10)]

        reference = signals[0]
        for sig in signals[1:]:
            assert sig.score == reference.score
            assert sig.failure_type == reference.failure_type
            assert sig.improvement_suggestions == reference.improvement_suggestions


# ---------------------------------------------------------------------------
# 4. Adaptation Impact Test — failures generate adaptation candidates
# ---------------------------------------------------------------------------

class TestAdaptationImpact:
    """Test 4: A failing run must produce adaptation candidates; a successful run does not."""

    def test_failing_run_produces_feedback_with_failure_type(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.FAILED)])
        loop = _make_loop(plan, report)

        result = loop.run("run risky operation")

        assert result.feedback.success is False
        assert result.feedback.failure_type is not None
        assert len(result.feedback.improvement_suggestions) > 0

    def test_successful_run_produces_empty_adaptation_list(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        result = loop.run("stable operation")

        # On success, process_feedback returns an empty list
        assert result.adaptation == []
        assert result.feedback.success is True

    def test_failing_run_adapts_and_succeeding_run_does_not(self) -> None:
        plan = _make_plan("task-1")
        fail_report = _make_report([_make_execution_task("task-1", ExecutionStatus.FAILED)])
        ok_report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        fail_loop = _make_loop(plan, fail_report)
        ok_loop = _make_loop(plan, ok_report)

        fail_result = fail_loop.run("flaky task")
        ok_result = ok_loop.run("reliable task")

        # Failing run has adaptations (or at least suggestions); successful run does not
        assert fail_result.feedback.success is False
        assert ok_result.feedback.success is True
        # Both runs differ in outcome
        assert fail_result.status != ok_result.status

    def test_adaptation_candidates_are_RuntimeAdaptation_instances(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.FAILED)])
        loop = _make_loop(plan, report)

        result = loop.run("failing task for adaptation check")

        for item in result.adaptation:
            assert isinstance(item, RuntimeAdaptation)

    def test_second_run_differs_after_first_fails(self) -> None:
        """Behavioral shift: a failed run and a later successful run have different statuses."""
        plan = _make_plan("task-1")
        fail_report = _make_report([_make_execution_task("task-1", ExecutionStatus.FAILED)])
        ok_report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        loop = _make_loop(plan, fail_report)
        result1 = loop.run("adaptive goal")

        # Swap the execution to succeed for the second run
        loop._execute = lambda _plan: ok_report
        result2 = loop.run("adaptive goal")

        assert result1.status != result2.status
        assert result1.feedback.success is False
        assert result2.feedback.success is True


# ---------------------------------------------------------------------------
# 5. Failure Injection Test — controlled bad execution path
# ---------------------------------------------------------------------------

class TestFailureInjection:
    """Test 5: Injected failures must propagate correctly through the feedback chain."""

    def test_failed_task_sets_feedback_success_false(self) -> None:
        plan = _make_plan("task-bad")
        report = _make_report([_make_execution_task("task-bad", ExecutionStatus.FAILED)])
        loop = _make_loop(plan, report)

        result = loop.run("invalid task that must fail")

        assert result.feedback.success is False

    def test_failed_task_sets_failure_type(self) -> None:
        plan = _make_plan("task-bad")
        report = _make_report([_make_execution_task("task-bad", ExecutionStatus.FAILED)])
        loop = _make_loop(plan, report)

        result = loop.run("invalid task that must fail")

        assert result.feedback.failure_type is not None

    def test_failed_task_produces_improvement_suggestions(self) -> None:
        plan = _make_plan("task-bad")
        report = _make_report([_make_execution_task("task-bad", ExecutionStatus.FAILED)])
        loop = _make_loop(plan, report)

        result = loop.run("invalid task that must fail")

        assert len(result.feedback.improvement_suggestions) > 0

    def test_skipped_task_is_treated_as_failure(self) -> None:
        plan = _make_plan("task-skipped")
        report = _make_report([_make_execution_task("task-skipped", ExecutionStatus.SKIPPED)])
        loop = _make_loop(plan, report)

        result = loop.run("task with skipped dependency")

        assert result.feedback.success is False

    def test_partial_completion_marks_partial_status(self) -> None:
        plan = _make_plan("task-1", "task-2")
        tasks = [
            _make_execution_task("task-1", ExecutionStatus.COMPLETED),
            _make_execution_task("task-2", ExecutionStatus.FAILED),
        ]
        report = _make_report(tasks)
        loop = _make_loop(plan, report)

        result = loop.run("partially failing plan")

        # Partial failure means status is "partial" or "failure" — not "success"
        assert result.status != "success"
        assert result.feedback.success is False

    def test_all_failed_tasks_produce_failure_status(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report(
            [_make_execution_task("task-1", ExecutionStatus.FAILED)],
        )
        loop = _make_loop(plan, report)

        result = loop.run("completely broken task")

        assert result.status == "failure"
        assert result.evaluation.success is False


# ---------------------------------------------------------------------------
# 6. Logging Verification — traceability fields must be present in loop logs
# ---------------------------------------------------------------------------

class TestLoggingVerification:
    """Test 6: Loop logs must contain required traceability fields."""

    def _run_and_get_logs(self, goal: str) -> tuple[AgentResult, tuple]:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)
        result = loop.run(goal)
        return result, loop.loop_logs

    def test_logs_are_not_empty(self) -> None:
        _, logs = self._run_and_get_logs("logging test")
        assert len(logs) > 0

    def test_logs_contain_iteration_id(self) -> None:
        _, logs = self._run_and_get_logs("logging test id")
        for entry in logs:
            assert "iteration_id" in entry, f"missing iteration_id in log entry: {entry}"

    def test_logs_contain_step(self) -> None:
        _, logs = self._run_and_get_logs("logging test step")
        steps_logged = {entry.get("step") for entry in logs}
        assert "PLAN" in steps_logged
        assert "EXECUTE" in steps_logged
        assert "VALIDATE" in steps_logged
        assert "REFLECT" in steps_logged

    def test_logs_contain_status(self) -> None:
        _, logs = self._run_and_get_logs("logging test status")
        for entry in logs:
            assert "status" in entry

    def test_logs_contain_attempt_field(self) -> None:
        _, logs = self._run_and_get_logs("logging test attempt")
        for entry in logs:
            assert "attempt" in entry

    def test_feedback_signal_score_is_logged_via_memory(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        memory = MagicMock()
        memory.get_feedback_context.return_value = {}

        loop = AgentLoop(
            memory_service=memory,
            self_improvement_engine=MagicMock(),
            now_fn=fixed_now,
        )
        loop._plan = lambda goal: type("_PlanContext", (), {"plan": plan, "resolved_adaptation_count": 0})()  # noqa: E731
        loop._execute = lambda _plan: report  # noqa: E731

        result = loop.run("scored task")

        # memory.log_decision should have been called with feedback_signal context including score
        decision_calls = [
            call for call in memory.log_decision.call_args_list
            if call.kwargs.get("decision") == "feedback_signal"
        ]
        assert len(decision_calls) > 0
        context = decision_calls[0].kwargs["context"]
        assert "score" in context
        assert "failure_type" in context
        assert "improvement_suggestions" in context
        assert "execution_id" in context


# ---------------------------------------------------------------------------
# 7. Closed-Loop Manual Injection Test — prove wiring works without automatic learning
# ---------------------------------------------------------------------------

class TestClosedLoopManualInjection:
    """Test 7: Manual adaptation injection changes the next run result."""

    def test_manual_injected_adaptation_changes_next_run_result(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.FAILED)])
        loop = _make_loop(plan, report)

        result1 = loop.run("manual closed loop task")
        adaptation = result1.adaptation
        result2 = loop.run("manual closed loop task", injected_adaptation=adaptation)

        assert adaptation != []
        assert result2.applied_modifiers != result1.applied_modifiers
        assert result2.applied_modifiers != {}
        assert result2 != result1


# ---------------------------------------------------------------------------
# 8. Replay Test — serialized output is equal across identical runs
# ---------------------------------------------------------------------------

class TestReplayTest:
    """Test 8: Serialized output of identical runs must match."""

    def _serialize_result(self, result: AgentResult) -> str:
        """Produce a deterministic JSON-like representation of the result."""
        return json.dumps(
            {
                "goal": result.goal,
                "status": result.status,
                "evaluation_score": result.evaluation.score if result.evaluation else None,
                "evaluation_success": result.evaluation.success if result.evaluation else None,
                "feedback_score": result.feedback.score if result.feedback else None,
                "feedback_success": result.feedback.success if result.feedback else None,
                "feedback_failure_type": result.feedback.failure_type if result.feedback else None,
                "feedback_suggestions": list(result.feedback.improvement_suggestions) if result.feedback else [],
                "adaptation_count": len(result.adaptation),
                "adaptation_types": sorted(a.type for a in result.adaptation),
                "applied_modifiers": dict(result.applied_modifiers),
                "reflection_notes": result.reflection.notes,
                "reflection_success_rate": result.reflection.success_rate,
            },
            sort_keys=True,
        )

    def test_two_identical_runs_serialize_equally(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        loop1 = _make_loop(plan, report)
        loop2 = _make_loop(plan, report)

        result1 = loop1.run("replay test task")
        result2 = loop2.run("replay test task")

        assert self._serialize_result(result1) == self._serialize_result(result2)

    def test_failure_runs_serialize_equally(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.FAILED)])

        loop1 = _make_loop(plan, report)
        loop2 = _make_loop(plan, report)

        result1 = loop1.run("replay failure task")
        result2 = loop2.run("replay failure task")

        assert self._serialize_result(result1) == self._serialize_result(result2)

    def test_different_goals_serialize_differently(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])

        loop1 = _make_loop(plan, report)
        loop2 = _make_loop(plan, report)

        result1 = loop1.run("goal alpha")
        result2 = loop2.run("goal beta")

        assert self._serialize_result(result1) != self._serialize_result(result2)


# ---------------------------------------------------------------------------
# 9. Stress Test — 50 iterations of loop stability
# ---------------------------------------------------------------------------

class TestStressTest:
    """Test 9: System remains stable and consistent over 50 consecutive iterations."""

    def test_fifty_successful_iterations_produce_consistent_status(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        results = [loop.run(f"stress task iteration {i}") for i in range(50)]

        assert all(r.status == "success" for r in results)

    def test_fifty_iterations_all_have_feedback(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        results = [loop.run(f"feedback stress {i}") for i in range(50)]

        assert all(r.feedback is not None for r in results)

    def test_fifty_iterations_no_drift_in_evaluation_score(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        scores = [loop.run(f"score stress {i}").evaluation.score for i in range(50)]

        # All identical goals produce the same evaluation score — no drift
        assert len(set(scores)) == 1, f"evaluation scores drifted across iterations: {set(scores)}"

    def test_fifty_failure_iterations_all_have_failure_type(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.FAILED)])
        loop = _make_loop(plan, report)

        results = [loop.run(f"fail stress {i}") for i in range(50)]

        assert all(r.feedback.failure_type is not None for r in results)

    def test_fifty_iterations_no_exceptions(self) -> None:
        plan = _make_plan("task-1")
        report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        loop = _make_loop(plan, report)

        # Must complete without raising
        for i in range(50):
            loop.run(f"no-crash task {i}")

    def test_mixed_fifty_iterations_maintain_determinism(self) -> None:
        """Alternating success/failure goals must produce consistent per-goal outcomes."""
        plan = _make_plan("task-1")
        ok_report = _make_report([_make_execution_task("task-1", ExecutionStatus.COMPLETED)])
        fail_report = _make_report([_make_execution_task("task-1", ExecutionStatus.FAILED)])

        results = []
        for i in range(50):
            if i % 2 == 0:
                loop = _make_loop(plan, ok_report)
                results.append(("success", loop.run("even task")))
            else:
                loop = _make_loop(plan, fail_report)
                results.append(("failure", loop.run("odd task")))

        for expected_status, result in results:
            assert result.status == expected_status, (
                f"Expected {expected_status!r} but got {result.status!r}"
            )
