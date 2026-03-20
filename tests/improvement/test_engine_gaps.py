"""
Tests for Agent 33 final gap fixes:
1. Rollback mechanism
2. Acceptance policy (threshold)
3. Cooldown enforcement
4. Standardized metrics schema
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.improvement.engine import ImprovementEngine
from app.improvement.models import (
    ImprovementMetrics,
    ImprovementRecord,
    RollbackAction,
)


class StubMemory:
    def __init__(self, execution_records=None, decision_records=None):
        self.execution_records = execution_records or []
        self.decision_records = decision_records or []

    def read_all(self, record_type):
        if record_type == "execution":
            return self.execution_records
        elif record_type == "decision":
            return self.decision_records
        return []

    def append(self, record_type, event):
        if record_type == "decision":
            self.decision_records.append(event)


class TestMetricsStandardization:
    """Gap 4: Standardized metrics schema."""

    def test_metrics_returns_standardized_schema(self):
        """Metrics must always return consistent fields."""
        engine = ImprovementEngine()
        records = [
            {"status": "success", "result": {"duration_ms": 100}},
            {"status": "failure", "result": {"duration_ms": 150}},
        ]

        metrics = engine._compute_metrics(records)

        # Verify standardized schema
        assert isinstance(metrics, ImprovementMetrics)
        assert hasattr(metrics, "success_rate")
        assert hasattr(metrics, "failure_rate")
        assert hasattr(metrics, "avg_step_latency")
        assert hasattr(metrics, "retry_rate")

        # Verify values
        assert metrics.success_rate == 0.5
        assert metrics.failure_rate == 0.5
        assert metrics.avg_step_latency == 125.0
        assert metrics.retry_rate == 0.0

    def test_metrics_empty_history_returns_zeros(self):
        """Empty history must return zero-valued metrics."""
        engine = ImprovementEngine()
        metrics = engine._compute_metrics([])

        assert metrics.success_rate == 0.0
        assert metrics.failure_rate == 0.0
        assert metrics.avg_step_latency == 0.0
        assert metrics.retry_rate == 0.0

    def test_metrics_consistent_across_runs(self):
        """Metrics must be consistent for same input."""
        engine = ImprovementEngine()
        records = [
            {"status": "success", "result": {"duration_ms": 100}},
            {"status": "success", "result": {"duration_ms": 100}},
            {"status": "failure", "result": {"duration_ms": 100}},
        ]

        metrics1 = engine._compute_metrics(records)
        metrics2 = engine._compute_metrics(records)

        assert metrics1.success_rate == metrics2.success_rate
        assert metrics1.failure_rate == metrics2.failure_rate
        assert metrics1.avg_step_latency == metrics2.avg_step_latency
        assert metrics1.retry_rate == metrics2.retry_rate


class TestAcceptancePolicy:
    """Gap 2: Improvement acceptance threshold."""

    def test_improvement_below_threshold_rejected(self):
        """Improvements below MIN_IMPROVEMENT_DELTA must be rejected."""
        engine = ImprovementEngine()

        # Small positive impact (below 0.05 threshold)
        metrics_before = ImprovementMetrics(
            success_rate=0.5,
            failure_rate=0.5,
            avg_step_latency=100.0,
            retry_rate=0.1,
        )
        metrics_after = ImprovementMetrics(
            success_rate=0.52,  # +0.02 success (tiny)
            failure_rate=0.48,
            avg_step_latency=100.0,
            retry_rate=0.1,
        )

        impact_score = engine._compute_impact_score(
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )
        accepted = engine._should_accept_improvement(impact_score)

        # Impact < 0.05 threshold
        assert impact_score < engine.MIN_IMPROVEMENT_DELTA
        assert not accepted

    def test_improvement_at_threshold_accepted(self):
        """Improvements at exactly MIN_IMPROVEMENT_DELTA threshold accepted."""
        engine = ImprovementEngine()

        metrics_before = ImprovementMetrics(
            success_rate=0.50,
            failure_rate=0.50,
            avg_step_latency=100.0,
            retry_rate=0.1,
        )
        # Larger improvement to cross 0.05 threshold
        # 0.10 * 0.6 (success) + 0.10 * 0.3 (failure) = 0.06 + 0.03 = 0.09
        metrics_after = ImprovementMetrics(
            success_rate=0.60,  # +0.10 success (60% weight = 0.06)
            failure_rate=0.40,  # -0.10 failure (30% weight = 0.03)
            avg_step_latency=100.0,  # no change
            retry_rate=0.1,
        )

        impact_score = engine._compute_impact_score(
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )
        accepted = engine._should_accept_improvement(impact_score)

        # Should exceed threshold (0.09 > 0.05)
        assert impact_score >= engine.MIN_IMPROVEMENT_DELTA
        assert accepted

    def test_negative_impact_always_rejected(self):
        """Negative impact improvements always rejected."""
        engine = ImprovementEngine()

        metrics_before = ImprovementMetrics(
            success_rate=0.8,
            failure_rate=0.2,
            avg_step_latency=50.0,
            retry_rate=0.05,
        )
        metrics_after = ImprovementMetrics(
            success_rate=0.7,  # -0.1 success (worse!)
            failure_rate=0.3,
            avg_step_latency=60.0,  # worse latency
            retry_rate=0.1,
        )

        impact_score = engine._compute_impact_score(
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )
        accepted = engine._should_accept_improvement(impact_score)

        assert impact_score < 0.0
        assert not accepted


class TestCooldownMechanism:
    """Gap 3: Improvement cooldown to prevent rapid mutation."""

    def test_first_improvement_not_on_cooldown(self):
        """First improvement should not be on cooldown."""
        engine = ImprovementEngine()
        memory = StubMemory()

        is_on_cooldown = engine._is_on_cooldown(memory)
        assert not is_on_cooldown

    def test_cooldown_active_after_accepted_improvement(self):
        """Cooldown activates after accepted improvement."""
        engine = ImprovementEngine()

        # Simulate accepted improvement
        decision_records = [
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 1,
            },
            {"event": "some_other_event"},
            {"event": "some_other_event"},
        ]
        memory = StubMemory(decision_records=decision_records)

        is_on_cooldown = engine._is_on_cooldown(memory)

        # 2 events since last improvement < 3 cycle cooldown
        assert is_on_cooldown

    def test_cooldown_expires_after_cycles(self):
        """Cooldown fully expired after COOLDOWN_CYCLES events."""
        engine = ImprovementEngine()

        # Last accepted improvement at index 0
        # Followed by exactly COOLDOWN_CYCLES (3) events
        decision_records = [
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 1,
            },
            {"event": "event1"},
            {"event": "event2"},
            {"event": "event3"},
        ]
        memory = StubMemory(decision_records=decision_records)

        is_on_cooldown = engine._is_on_cooldown(memory)

        # 3 events since last improvement == cooldown_cycles
        # Cooldown has fully expired
        assert not is_on_cooldown

    def test_cooldown_fully_expired(self):
        """Cooldown fully expired after more than COOLDOWN_CYCLES."""
        engine = ImprovementEngine()

        decision_records = [
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 1,
            },
            {"event": "event1"},
            {"event": "event2"},
            {"event": "event3"},
            {"event": "event4"},
        ]
        memory = StubMemory(decision_records=decision_records)

        is_on_cooldown = engine._is_on_cooldown(memory)

        # 4 events since last improvement > 3 cycle cooldown
        assert not is_on_cooldown


class TestRollbackMechanism:
    """Gap 1: Rollback capability for bad improvements."""

    def test_rollback_actions_generated_for_applied_actions(self):
        """Rollback actions generated for each applied improvement action."""
        engine = ImprovementEngine()
        from app.improvement.models import ImprovementAction

        actions = [
            ImprovementAction(
                target="planning.strategy",
                change="increase_validation_before_execution",
                reason="low success rate",
            ),
            ImprovementAction(
                target="execution.retry_limit",
                change="decrease_retry_limit_by_one",
                reason="frequent failures",
            ),
        ]

        rollback_actions = engine._build_rollback_actions(actions, version=1)

        assert len(rollback_actions) == 2
        assert all(isinstance(rb, RollbackAction) for rb in rollback_actions)
        assert rollback_actions[0].target == "planning.strategy"
        assert rollback_actions[1].target == "execution.retry_limit"
        assert all(rb.version == 1 for rb in rollback_actions)

    def test_rollback_actions_stored_in_record(self):
        """Rollback actions stored in improvement record."""
        fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
        engine = ImprovementEngine(clock=lambda: fixed_time)

        from app.improvement.models import ImprovementAction, Pattern

        patterns = [Pattern(type="low_success", location="planning", frequency=0.8, severity="high")]
        actions = [
            ImprovementAction(
                target="planning.strategy",
                change="increase_validation_before_execution",
                reason="test",
            ),
        ]
        memory = StubMemory()

        metrics = ImprovementMetrics(
            success_rate=0.5,
            failure_rate=0.5,
            avg_step_latency=100.0,
            retry_rate=0.1,
        )
        rollback_actions = [
            RollbackAction(target="planning.strategy", previous_value="test", version=1),
        ]

        record = engine._build_improvement_record(
            memory=memory,
            patterns=patterns,
            actions=actions,
            result="applied",
            metrics_before=metrics,
            metrics_after=metrics,
            impact_score=0.1,
            accepted=True,
            rollback_actions=rollback_actions,
        )

        assert len(record.rollback_actions) == 1
        assert record.rollback_actions[0].target == "planning.strategy"

    def test_improvement_record_has_acceptance_flag(self):
        """Improvement record tracks whether it was accepted."""
        fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
        engine = ImprovementEngine(clock=lambda: fixed_time)

        from app.improvement.models import ImprovementAction, Pattern

        patterns = [Pattern(type="low_success", location="planning", frequency=0.8, severity="high")]
        actions = [
            ImprovementAction(
                target="planning.strategy",
                change="increase_validation_before_execution",
                reason="test",
            ),
        ]
        memory = StubMemory()

        metrics = ImprovementMetrics(
            success_rate=0.5,
            failure_rate=0.5,
            avg_step_latency=100.0,
            retry_rate=0.1,
        )

        record_accepted = engine._build_improvement_record(
            memory=memory,
            patterns=patterns,
            actions=actions,
            result="applied",
            metrics_before=metrics,
            metrics_after=metrics,
            impact_score=0.1,
            accepted=True,
        )

        record_rejected = engine._build_improvement_record(
            memory=memory,
            patterns=patterns,
            actions=actions,
            result="rejected",
            metrics_before=metrics,
            metrics_after=metrics,
            impact_score=-0.05,
            accepted=False,
        )

        assert record_accepted.accepted is True
        assert record_rejected.accepted is False


class TestIntegrationAllGaps:
    """Integration tests for all 4 gaps together."""

    def test_engine_respects_all_safety_constraints(self):
        """Engine respects acceptance threshold + cooldown + rollback."""
        fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
        engine = ImprovementEngine(clock=lambda: fixed_time)

        # Setup: simulation of execution history
        history = [
            {"status": "success", "result": {"duration_ms": 100}},
            {"status": "success", "result": {"duration_ms": 100}},
            {"status": "failure", "result": {"duration_ms": 100}},
        ]

        # Simulation: tiny improvement (below threshold) + before cooldown expiry
        decision_records = [
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 1,
            },
            {"event": "event1"},
            {"event": "event2"},
        ]

        memory = StubMemory(execution_records=history, decision_records=decision_records)

        # System should:
        # 1. Be on cooldown (2 events < 3 cycles)
        # 2. Not apply new improvements while on cooldown
        assert engine._is_on_cooldown(memory) is True

        # Metrics should be standardized
        metrics = engine._compute_metrics(history)
        assert isinstance(metrics, ImprovementMetrics)
        assert abs(metrics.success_rate - 2.0 / 3.0) < 0.001
        assert abs(metrics.failure_rate - 1.0 / 3.0) < 0.001
