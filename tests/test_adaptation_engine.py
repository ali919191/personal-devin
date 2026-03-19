from __future__ import annotations

from datetime import UTC, datetime

from app.adaptation import (
    Adaptation,
    AdaptationEngine,
    AdaptationPolicy,
    AdaptationRegistry,
    PreferredToolPolicy,
    RetryLimitPolicy,
    TimeoutPolicy,
)
from app.feedback.models import FeedbackSignal


def test_adaptation_generation() -> None:
    engine = AdaptationEngine()
    improvements = [
        {"action_type": "retry_strategy", "source": "impr-001", "confidence": 0.9},
        {"action_type": "optimize_execution", "source": "impr-002", "confidence": 0.8},
        {"action_type": "increase_logging", "source": "impr-003", "confidence": 0.7},
    ]

    adaptations = engine.generate(improvements)

    assert [adaptation.type for adaptation in adaptations] == [
        "retry_limit",
        "timeout_seconds",
        "preferred_tool",
    ]
    assert adaptations[0].payload == {"retry_limit": 3}
    assert adaptations[1].payload == {"timeout": 10}
    assert adaptations[2].payload == {"preferred_tool": "api"}


def test_policy_validation() -> None:
    retry_policy = RetryLimitPolicy()
    timeout_policy = TimeoutPolicy()
    tool_policy = PreferredToolPolicy()

    retry_adaptation = Adaptation(
        id="adaptation-001",
        source="impr-001",
        type="retry_limit",
        payload={"retry_limit": 3},
        confidence=0.9,
    )
    timeout_adaptation = Adaptation(
        id="adaptation-002",
        source="impr-002",
        type="timeout_seconds",
        payload={"timeout": 10},
        confidence=0.8,
    )
    tool_adaptation = Adaptation(
        id="adaptation-003",
        source="impr-003",
        type="preferred_tool",
        payload={"preferred_tool": "api"},
        confidence=0.7,
    )

    assert retry_policy.validate(retry_adaptation) is True
    assert timeout_policy.validate(timeout_adaptation) is True
    assert tool_policy.validate(tool_adaptation) is True


def test_application_correctness() -> None:
    engine = AdaptationEngine()
    improvements = [
        {"action_type": "retry_strategy", "source": "impr-001", "confidence": 0.9},
        {"action_type": "optimize_execution", "source": "impr-002", "confidence": 0.8},
        {"action_type": "increase_logging", "source": "impr-003", "confidence": 0.7},
    ]

    adaptations = engine.generate(improvements)
    valid_adaptations = engine.filter_valid(adaptations)
    modifiers = engine.apply(valid_adaptations, execution_context={"run_id": "run-001"})

    assert modifiers == {
        "retry_limit": 3,
        "timeout": 10,
        "preferred_tool": "api",
    }


def test_invalid_adaptation_rejection() -> None:
    engine = AdaptationEngine()
    invalid_adaptations = [
        Adaptation(
            id="adaptation-001",
            source="impr-001",
            type="retry_limit",
            payload={"retry_limit": 999},
            confidence=0.9,
        ),
        Adaptation(
            id="adaptation-002",
            source="impr-002",
            type="timeout_seconds",
            payload={"timeout": -1},
            confidence=0.8,
        ),
        Adaptation(
            id="adaptation-003",
            source="impr-003",
            type="preferred_tool",
            payload={"preferred_tool": "unknown"},
            confidence=0.7,
        ),
        Adaptation(
            id="adaptation-004",
            source="impr-004",
            type="unregistered_type",
            payload={"value": 1},
            confidence=0.5,
        ),
    ]

    valid_adaptations = engine.filter_valid(invalid_adaptations)

    assert valid_adaptations == []


def test_deterministic_output() -> None:
    engine = AdaptationEngine()
    improvements = [
        {"action_type": "retry_strategy", "source": "impr-001", "confidence": 0.9},
        {"action_type": "retry_strategy", "source": "impr-002", "confidence": 0.8},
    ]

    first = engine.apply(engine.filter_valid(engine.generate(improvements)), execution_context={})
    second = engine.apply(engine.filter_valid(engine.generate(improvements)), execution_context={})

    assert first == second


def test_custom_policy_registration() -> None:
    class StepOrderingHintPolicy(AdaptationPolicy):
        def validate(self, adaptation: Adaptation) -> bool:
            if adaptation.type != "step_order_hint":
                return False
            hint = adaptation.payload.get("order")
            return isinstance(hint, str) and hint in {"dependency_first", "latency_first"}

        def apply(self, adaptation: Adaptation, context: dict) -> dict:
            _ = context
            return {"step_order_hint": adaptation.payload["order"]}

    registry = AdaptationRegistry()
    registry.register("retry_limit", RetryLimitPolicy())
    registry.register("timeout_seconds", TimeoutPolicy())
    registry.register("preferred_tool", PreferredToolPolicy())
    registry.register("step_order_hint", StepOrderingHintPolicy())

    adaptation = Adaptation(
        id="adaptation-010",
        source="impr-010",
        type="step_order_hint",
        payload={"order": "dependency_first"},
        confidence=0.95,
    )

    policy = registry.get("step_order_hint")
    assert policy.validate(adaptation) is True
    assert policy.apply(adaptation, context={}) == {"step_order_hint": "dependency_first"}


def test_process_feedback_generates_direct_adaptations() -> None:
    engine = AdaptationEngine()
    signal = FeedbackSignal(
        execution_id="iter-123",
        score=0.0,
        success=False,
        failure_type="execution_failure",
        improvement_suggestions=[
            "add_task_level_retry_with_backoff",
            "introduce_precondition_validation",
        ],
        confidence=0.75,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
    )

    adaptations = engine.process_feedback(signal)

    assert [item.type for item in adaptations] == ["retry_limit", "preferred_tool"]
    assert [item.source for item in adaptations] == ["feedback:iter-123", "feedback:iter-123"]


def test_process_feedback_is_deterministic() -> None:
    engine = AdaptationEngine()
    signal = FeedbackSignal(
        execution_id="iter-789",
        score=0.5,
        success=False,
        failure_type="partial_match",
        improvement_suggestions=[
            "add_post_execution_output_sanitization",
            "add_post_execution_output_sanitization",
        ],
        confidence=0.9,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
    )

    first = engine.process_feedback(signal)
    second = engine.process_feedback(signal)

    assert first == second
    assert [item.type for item in first] == ["timeout_seconds"]
