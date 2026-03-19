"""Tests for Agent 15 AdaptationEngine: deterministic pattern→adaptation mapping."""

from app.self_improvement.adaptation_engine import AdaptationEngine
from app.self_improvement.models import ImprovementType, Pattern, SelfImprovementAdaptation


def _pattern(kind: str, signal_value=None, occurrence_count: int = 3, confidence: float = 0.8) -> Pattern:
    return Pattern(
        pattern_id=f"pattern-{kind}",
        kind=kind,
        description=f"Test pattern: {kind}",
        signal_value=signal_value if signal_value is not None else kind,
        occurrence_count=occurrence_count,
        confidence=confidence,
    )


def test_generates_adaptations_for_repeated_failure():
    pattern = _pattern("repeated_failure", signal_value="timeout")
    adaptations = AdaptationEngine().generate([pattern])
    assert len(adaptations) >= 1
    assert all(isinstance(a, SelfImprovementAdaptation) for a in adaptations)


def test_repeated_failure_produces_adjust_policy_and_increase_confidence():
    pattern = _pattern("repeated_failure", signal_value="timeout")
    adaptations = AdaptationEngine().generate([pattern])
    types = {a.action_type for a in adaptations}
    assert ImprovementType.ADJUST_POLICY in types
    assert ImprovementType.INCREASE_CONFIDENCE in types


def test_generates_adaptations_for_high_latency():
    pattern = _pattern("high_latency", signal_value=4.5)
    adaptations = AdaptationEngine().generate([pattern])
    assert len(adaptations) >= 1
    assert any(a.action_type == ImprovementType.CHANGE_STRATEGY for a in adaptations)


def test_generates_adaptations_for_low_success_rate():
    pattern = _pattern("low_success_rate", signal_value=0.5)
    adaptations = AdaptationEngine().generate([pattern])
    types = {a.action_type for a in adaptations}
    assert ImprovementType.CHANGE_STRATEGY in types
    assert ImprovementType.ADJUST_POLICY in types


def test_unknown_pattern_kind_produces_no_adaptations():
    pattern = _pattern("unknown_kind")
    adaptations = AdaptationEngine().generate([pattern])
    assert adaptations == []


def test_adaptation_references_source_pattern_id():
    pattern = _pattern("repeated_failure", signal_value="boom")
    adaptations = AdaptationEngine().generate([pattern])
    assert all(a.source_pattern_id == pattern.pattern_id for a in adaptations)


def test_confidence_score_is_derived_from_pattern():
    pattern = _pattern("repeated_failure", signal_value="boom", confidence=0.8)
    adaptations = AdaptationEngine().generate([pattern])
    for a in adaptations:
        assert a.confidence_score < pattern.confidence + 0.001


def test_output_sorted_deterministically():
    patterns = [_pattern("repeated_failure", "e1"), _pattern("high_latency", 5.0)]
    adaptations = AdaptationEngine().generate(patterns)
    assert adaptations == sorted(
        adaptations, key=lambda a: (a.action_type, a.target, a.adaptation_id)
    )


def test_deterministic_same_input_same_output():
    patterns = [_pattern("repeated_failure", "timeout"), _pattern("high_latency", 4.0)]
    first = AdaptationEngine().generate(patterns)
    second = AdaptationEngine().generate(patterns)
    assert first == second
