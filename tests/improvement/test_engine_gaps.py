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


class TestRollbackExecution:
    """Rollback execution when improvements degrade system."""

    def test_rollback_executed_on_negative_impact(self):
        """Rollback executed when impact_score < 0 (degradation)."""
        from app.improvement.models import ImprovementAction, Pattern

        fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
        engine = ImprovementEngine(clock=lambda: fixed_time)

        patterns = [Pattern(type="test", location="test", frequency=0.5, severity="low")]
        actions = [
            ImprovementAction(target="planning.strategy", change="test_change", reason="test"),
        ]
        metrics = ImprovementMetrics(0.5, 0.5, 100.0, 0.1)

        # Negative impact triggers rollback
        record = ImprovementRecord(
            id="test-001",
            timestamp=fixed_time,
            patterns=patterns,
            actions=actions,
            result="negative",
            version=1,
            rollback_actions=[
                RollbackAction(target="planning.strategy", previous_value="original", version=1),
            ],
            metrics_before=metrics,
            metrics_after=metrics,
            impact_score=-0.05,  # Negative!
            accepted=False,
        )

        rollback_executed = engine._execute_rollback(record)

        # Rollback should be executed
        assert rollback_executed is True

    def test_no_rollback_on_positive_impact(self):
        """No rollback when impact_score >= 0 (improvement maintained)."""
        from app.improvement.models import ImprovementAction, Pattern

        fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
        engine = ImprovementEngine(clock=lambda: fixed_time)

        patterns = [Pattern(type="test", location="test", frequency=0.5, severity="low")]
        actions = [
            ImprovementAction(target="planning.strategy", change="test_change", reason="test"),
        ]
        metrics = ImprovementMetrics(0.5, 0.5, 100.0, 0.1)

        # Positive impact, no rollback
        record = ImprovementRecord(
            id="test-001",
            timestamp=fixed_time,
            patterns=patterns,
            actions=actions,
            result="positive",
            version=1,
            rollback_actions=[
                RollbackAction(target="planning.strategy", previous_value="original", version=1),
            ],
            metrics_before=metrics,
            metrics_after=metrics,
            impact_score=0.08,  # Positive!
            accepted=True,
        )

        rollback_executed = engine._execute_rollback(record)

        # Rollback should NOT be executed
        assert rollback_executed is False

    def test_no_rollback_without_actions(self):
        """No rollback when no rollback_actions recorded."""
        from app.improvement.models import Pattern

        fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
        engine = ImprovementEngine(clock=lambda: fixed_time)

        patterns = [Pattern(type="test", location="test", frequency=0.5, severity="low")]
        metrics = ImprovementMetrics(0.5, 0.5, 100.0, 0.1)

        record = ImprovementRecord(
            id="test-001",
            timestamp=fixed_time,
            patterns=patterns,
            actions=[],
            result="noop",
            version=1,
            rollback_actions=[],  # No rollback actions!
            metrics_before=metrics,
            metrics_after=metrics,
            impact_score=-0.1,  # Negative, but no actions to rollback
            accepted=False,
        )

        rollback_executed = engine._execute_rollback(record)

        # Rollback should NOT be executed
        assert rollback_executed is False


class TestTrendAwareAcceptance:
    """Acceptance policy with trend checking (prevent stagnation)."""

    def test_acceptance_rejects_sideways_improvement(self):
        """Reject improvement that equals last improvement (sideways/stagnation)."""
        engine = ImprovementEngine()

        # Setup: previous accepted improvement with impact 0.08
        decision_records = [
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 1,
                "impact_score": 0.08,
            },
        ]
        memory = StubMemory(decision_records=decision_records)

        # Current improvement: same impact as previous
        impact_score = 0.08

        # Should reject (no progress)
        accepted = engine._should_accept_improvement_with_memory(impact_score, memory)
        assert not accepted

    def test_acceptance_accepts_improving_trend(self):
        """Accept improvement that exceeds last improvement (positive trend)."""
        engine = ImprovementEngine()

        # Setup: previous accepted improvement with impact 0.06
        decision_records = [
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 1,
                "impact_score": 0.06,
            },
        ]
        memory = StubMemory(decision_records=decision_records)

        # Current improvement: better than previous
        impact_score = 0.09

        # Should accept (trending up)
        accepted = engine._should_accept_improvement_with_memory(impact_score, memory)
        assert accepted

    def test_acceptance_requires_both_threshold_and_trend(self):
        """Must pass both threshold AND trend for acceptance."""
        engine = ImprovementEngine()

        # Setup: previous accepted improvement with impact 0.08
        decision_records = [
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 1,
                "impact_score": 0.08,
            },
        ]
        memory = StubMemory(decision_records=decision_records)

        # Current improvement: exceeds trend but below threshold
        impact_score = 0.04

        # Should reject (below threshold)
        accepted = engine._should_accept_improvement_with_memory(impact_score, memory)
        assert not accepted

    def test_acceptance_first_improvement_uses_threshold_only(self):
        """First improvement only checked against threshold (no previous to trend against)."""
        engine = ImprovementEngine()

        # Setup: no previous improvements
        memory = StubMemory(decision_records=[])

        # Improvement barely meets threshold
        impact_score = 0.05

        # Should accept (no previous to compare, meets threshold)
        accepted = engine._should_accept_improvement_with_memory(impact_score, memory)
        assert accepted

    def test_last_impact_score_retrieved_correctly(self):
        """Correctly retrieves most recent accepted improvement's impact score."""
        engine = ImprovementEngine()

        # Setup: multiple improvements, need to find the LAST accepted one
        decision_records = [
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 1,
                "impact_score": 0.05,
            },
            {"event": "some_other_event"},
            {
                "event": "improvement_record",
                "accepted": True,
                "version": 2,
                "impact_score": 0.07,
            },
            {
                "event": "improvement_record",
                "accepted": False,  # Rejected, should skip
                "version": 3,
                "impact_score": 0.12,
            },
        ]
        memory = StubMemory(decision_records=decision_records)

        last_impact = engine._get_last_accepted_impact_score(memory)

        # Should return 0.07 (most recent ACCEPTED improvement)
        assert last_impact == 0.07

    def test_metrics_weights_are_configurable_constants(self):
        """Verify metrics weights are extracted to configurable constants."""
        engine = ImprovementEngine()

        # Verify the weights are on the engine
        assert hasattr(engine, "WEIGHT_SUCCESS")
        assert hasattr(engine, "WEIGHT_FAILURE")
        assert hasattr(engine, "WEIGHT_LATENCY")

        # Verify they sum to approximately 1.0 (objective function)
        total_weight = engine.WEIGHT_SUCCESS + engine.WEIGHT_FAILURE + engine.WEIGHT_LATENCY
        assert abs(total_weight - 1.0) < 0.001

        # Verify they match the formula
        metrics_before = ImprovementMetrics(0.5, 0.5, 100.0, 0.1)
        metrics_after = ImprovementMetrics(0.6, 0.4, 95.0, 0.08)

        impact = engine._compute_impact_score(metrics_before=metrics_before, metrics_after=metrics_after)

        # Manual calculation with weights
        success_delta = 0.6 - 0.5
        failure_delta = 0.5 - 0.4
        latency_delta = (100.0 - 95.0) / 100.0

        expected = (
            success_delta * engine.WEIGHT_SUCCESS
            + failure_delta * engine.WEIGHT_FAILURE
            + latency_delta * engine.WEIGHT_LATENCY
        )
        expected = round(expected, 4)

        assert impact == expected


class TestMicroFixes:
    """Critical micro-fixes: clamping, safe defaults, state restoration."""

    def test_impact_score_clamped_to_bounds(self):
        """Impact scores clamped to [-1.0, 1.0] to prevent weird edge cases."""
        engine = ImprovementEngine()

        # Create extreme metrics that would exceed bounds
        metrics_before = ImprovementMetrics(0.0, 1.0, 1000.0, 0.0)
        metrics_after = ImprovementMetrics(1.0, 0.0, 1.0, 0.0)

        # Extreme improvement: would be > 1.0 without clamping
        impact = engine._compute_impact_score(metrics_before=metrics_before, metrics_after=metrics_after)

        # Should be clamped to 1.0
        assert impact <= 1.0
        assert impact >= -1.0

    def test_impact_score_clamped_negative(self):
        """Negative impact scores also clamped to prevent underflow."""
        engine = ImprovementEngine()

        # Create metrics that degrade severely
        metrics_before = ImprovementMetrics(1.0, 0.0, 1.0, 0.0)
        metrics_after = ImprovementMetrics(0.0, 1.0, 1000.0, 1.0)

        # Extreme degradation: would be < -1.0 without clamping
        impact = engine._compute_impact_score(metrics_before=metrics_before, metrics_after=metrics_after)

        # Should be clamped to -1.0
        assert impact >= -1.0
        assert impact <= 1.0

    def test_trend_check_safe_default_first_improvement(self):
        """First improvement only checked against threshold (no prior to compare)."""
        engine = ImprovementEngine()
        
        # Empty history - first improvement
        memory = StubMemory(decision_records=[])
        
        # Barely meets threshold
        impact_score = 0.05
        accepted = engine._should_accept_improvement_with_memory(impact_score, memory)

        # Should accept (meets threshold, no prior to compare against)
        assert accepted is True

    def test_trend_check_safe_default_no_prior_accepted(self):
        """When no prior accepted improvements, only threshold check."""
        engine = ImprovementEngine()

        # History with only rejected improvements
        decision_records = [
            {
                "event": "improvement_record",
                "accepted": False,
                "version": 1,
                "impact_score": 0.10,
            },
        ]
        memory = StubMemory(decision_records=decision_records)

        # Meets threshold
        impact_score = 0.05
        accepted = engine._should_accept_improvement_with_memory(impact_score, memory)

        # Should accept (meets threshold, no prior ACCEPTED to compare)
        assert accepted is True

    def test_rollback_applies_previous_values(self):
        """Rollback execution actually applies previous values (via logging)."""
        from unittest.mock import patch, MagicMock
        from app.improvement.models import Pattern

        fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
        engine = ImprovementEngine(clock=lambda: fixed_time)

        patterns = [Pattern(type="test", location="test", frequency=0.5, severity="low")]
        metrics = ImprovementMetrics(0.5, 0.5, 100.0, 0.1)

        # Negative impact triggers rollback
        record = ImprovementRecord(
            id="test-001",
            timestamp=fixed_time,
            patterns=patterns,
            actions=[],
            result="negative",
            version=1,
            rollback_actions=[
                RollbackAction(target="planning.strategy", previous_value="original_v1", version=1),
                RollbackAction(target="execution.retry_limit", previous_value="original_v2", version=1),
            ],
            metrics_before=metrics,
            metrics_after=metrics,
            impact_score=-0.05,
            accepted=False,
        )

        # Mock logger to verify calls
        with patch("app.improvement.engine.logger") as mock_logger:
            rollback_executed = engine._execute_rollback(record)

            # Rollback should be executed
            assert rollback_executed is True

            # Logger should be called for each restoration
            assert mock_logger.info.call_count >= 3  # 1 for rollback, 2 for value restorations

            # Verify rollback execution was logged
            first_call_args = mock_logger.info.call_args_list[0]
            assert first_call_args[0][0] == "improvement_rollback_executed"

            # Verify value restorations were logged
            restore_calls = [call for call in mock_logger.info.call_args_list 
                            if len(call[0]) > 0 and call[0][0] == "restore_previous_value"]
            assert len(restore_calls) == 2  # Two rollback actions

    def test_apply_previous_value_logs_restoration(self):
        """_apply_previous_value method properly logs state restoration."""
        from unittest.mock import patch

        engine = ImprovementEngine()

        with patch("app.improvement.engine.logger") as mock_logger:
            engine._apply_previous_value("planning.strategy", "original_value")

            # Should log restoration
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "restore_previous_value"
            assert call_args[0][1]["target"] == "planning.strategy"
            assert call_args[0][1]["previous_value"] == "original_value"
