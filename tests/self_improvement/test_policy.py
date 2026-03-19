"""Tests for Agent 15 AdaptationPolicy: deterministic validation and filtering."""

from app.self_improvement.models import ImprovementType, SelfImprovementAdaptation
from app.self_improvement.policy import AdaptationPolicy


def _adaptation(
    adaptation_id: str,
    target: str,
    action_type: ImprovementType = ImprovementType.ADJUST_POLICY,
    confidence: float = 0.8,
) -> SelfImprovementAdaptation:
    return SelfImprovementAdaptation(
        adaptation_id=adaptation_id,
        source_pattern_id="pattern-x",
        description="test",
        expected_effect="test",
        action_type=action_type,
        target=target,
        value="v",
        confidence_score=confidence,
    )


def test_approves_above_threshold():
    a = _adaptation("a1", "retry_limit", confidence=0.75)
    approved, rejected = AdaptationPolicy(confidence_threshold=0.6).validate([a])
    assert a in approved
    assert rejected == []


def test_rejects_below_threshold():
    a = _adaptation("a1", "retry_limit", confidence=0.4)
    approved, rejected = AdaptationPolicy(confidence_threshold=0.6).validate([a])
    assert approved == []
    assert a in rejected


def test_policy_deduplicates_by_action_type_and_target():
    high = _adaptation("a1", "retry_limit", confidence=0.85)
    low = _adaptation("a2", "retry_limit", confidence=0.70)
    approved, rejected = AdaptationPolicy(confidence_threshold=0.6).validate([high, low])
    assert len(approved) == 1
    assert approved[0].adaptation_id == "a1"
    assert low in rejected


def test_forbidden_target_is_rejected():
    a = _adaptation("a1", "forbidden_target", confidence=0.99)
    approved, rejected = AdaptationPolicy(
        confidence_threshold=0.6, forbidden_targets=("forbidden_target",)
    ).validate([a])
    assert approved == []
    assert a in rejected


def test_approved_output_is_sorted():
    adaptations = [
        _adaptation("a3", "z_target", ImprovementType.CHANGE_STRATEGY, 0.8),
        _adaptation("a1", "a_target", ImprovementType.ADJUST_POLICY, 0.75),
        _adaptation("a2", "m_target", ImprovementType.INCREASE_CONFIDENCE, 0.9),
    ]
    approved, _ = AdaptationPolicy(confidence_threshold=0.6).validate(adaptations)
    assert approved == sorted(approved, key=lambda a: (a.action_type, a.target, a.adaptation_id))


def test_deterministic_same_input_same_output():
    adaptations = [
        _adaptation("a1", "retry_limit", confidence=0.8),
        _adaptation("a2", "timeout", ImprovementType.CHANGE_STRATEGY, confidence=0.65),
        _adaptation("a3", "retry_limit", confidence=0.75),
    ]
    approved1, rejected1 = AdaptationPolicy().validate(adaptations)
    approved2, rejected2 = AdaptationPolicy().validate(adaptations)
    assert approved1 == approved2
    assert rejected1 == rejected2


def test_empty_input_returns_empty_lists():
    approved, rejected = AdaptationPolicy().validate([])
    assert approved == []
    assert rejected == []
