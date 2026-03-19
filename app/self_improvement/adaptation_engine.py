"""Adaptation engine for Agent 15: converts patterns into candidate adaptations."""

from __future__ import annotations

from app.self_improvement.models import ImprovementType, Pattern, SelfImprovementAdaptation


class AdaptationEngine:
    """Generates deterministic candidate adaptations from detected patterns."""

    def generate(self, patterns: list[Pattern]) -> list[SelfImprovementAdaptation]:
        adaptations: list[SelfImprovementAdaptation] = []
        for pattern in patterns:
            candidates = self._adapt(pattern)
            adaptations.extend(candidates)
        # Stable sort: action_type → target → adaptation_id
        return sorted(
            adaptations,
            key=lambda a: (a.action_type, a.target, a.adaptation_id),
        )

    # ------------------------------------------------------------------
    # Per-kind adaptation rules
    # ------------------------------------------------------------------

    def _adapt(self, pattern: Pattern) -> list[SelfImprovementAdaptation]:
        if pattern.kind == "repeated_failure":
            return self._adapt_repeated_failure(pattern)
        if pattern.kind == "high_latency":
            return self._adapt_high_latency(pattern)
        if pattern.kind == "low_success_rate":
            return self._adapt_low_success_rate(pattern)
        return []

    def _adapt_repeated_failure(self, pattern: Pattern) -> list[SelfImprovementAdaptation]:
        return [
            SelfImprovementAdaptation(
                adaptation_id=f"adapt-retry-{pattern.pattern_id}",
                source_pattern_id=pattern.pattern_id,
                description=f"Increase retry limit to handle repeated error: {pattern.signal_value}",
                expected_effect="Reduce failure rate by retrying transient errors",
                action_type=ImprovementType.ADJUST_POLICY,
                target="retry_limit",
                value=3,
                confidence_score=round(pattern.confidence * 0.95, 4),
            ),
            SelfImprovementAdaptation(
                adaptation_id=f"adapt-guard-{pattern.pattern_id}",
                source_pattern_id=pattern.pattern_id,
                description=f"Tighten policy guard for error class: {pattern.signal_value}",
                expected_effect="Prevent recurrence by enforcing stricter precondition checks",
                action_type=ImprovementType.INCREASE_CONFIDENCE,
                target="policy_gate",
                value="strict",
                confidence_score=round(pattern.confidence * 0.85, 4),
            ),
        ]

    def _adapt_high_latency(self, pattern: Pattern) -> list[SelfImprovementAdaptation]:
        return [
            SelfImprovementAdaptation(
                adaptation_id=f"adapt-timeout-{pattern.pattern_id}",
                source_pattern_id=pattern.pattern_id,
                description="Reduce timeout threshold based on high-latency signal",
                expected_effect="Fail fast on slow steps instead of waiting for full timeout",
                action_type=ImprovementType.CHANGE_STRATEGY,
                target="timeout",
                value=int(pattern.signal_value),
                confidence_score=round(pattern.confidence * 0.9, 4),
            ),
        ]

    def _adapt_low_success_rate(self, pattern: Pattern) -> list[SelfImprovementAdaptation]:
        return [
            SelfImprovementAdaptation(
                adaptation_id=f"adapt-strategy-{pattern.pattern_id}",
                source_pattern_id=pattern.pattern_id,
                description="Switch execution strategy due to low success rate",
                expected_effect="Improve completion ratio by using a more conservative strategy",
                action_type=ImprovementType.CHANGE_STRATEGY,
                target="execution_strategy",
                value="conservative",
                confidence_score=round(pattern.confidence * 0.9, 4),
            ),
            SelfImprovementAdaptation(
                adaptation_id=f"adapt-policy-{pattern.pattern_id}",
                source_pattern_id=pattern.pattern_id,
                description="Adjust policy confidence threshold to filter low-quality plans",
                expected_effect="Reduce acceptance of plans likely to fail",
                action_type=ImprovementType.ADJUST_POLICY,
                target="confidence_threshold",
                value=0.8,
                confidence_score=round(pattern.confidence * 0.8, 4),
            ),
        ]
