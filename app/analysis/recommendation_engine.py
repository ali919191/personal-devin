"""Recommendation generation from detected analysis patterns."""

from __future__ import annotations

from app.analysis.models import FailurePattern, Recommendation


class RecommendationEngine:
    """Converts detected patterns into prioritized recommendations."""

    def generate(
        self,
        failure_patterns: list[FailurePattern],
        inefficiencies: list[str],
        retry_loops: list[str],
    ) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for pattern in failure_patterns:
            if pattern.count < 2:
                continue
            recommendations.append(
                Recommendation(
                    recommendation_id=f"stabilize-{pattern.pattern_id}",
                    priority=1,
                    title="Stabilize recurring failure",
                    action=f"Add targeted guardrails for '{pattern.signature}' from {pattern.source}.",
                    rationale=f"Observed {pattern.count} occurrences of the same failure signature.",
                )
            )

        inefficiency_map = {
            "high_average_duration": (
                "reduce-latency",
                2,
                "Reduce average execution latency",
                "Profile slow steps and split oversized tasks to improve throughput.",
            ),
            "low_success_rate": (
                "improve-success-rate",
                1,
                "Improve task success rate",
                "Increase validation and precondition checks before task execution.",
            ),
            "retry_activity_detected": (
                "tighten-retry-policy",
                2,
                "Tighten retry policy",
                "Cap retries and add explicit fallback handling for repeat failures.",
            ),
        }

        for inefficiency in inefficiencies:
            if inefficiency not in inefficiency_map:
                continue
            rec_id, priority, title, action = inefficiency_map[inefficiency]
            recommendations.append(
                Recommendation(
                    recommendation_id=rec_id,
                    priority=priority,
                    title=title,
                    action=action,
                    rationale=f"Detected inefficiency signal: {inefficiency}",
                )
            )

        for target in retry_loops:
            recommendations.append(
                Recommendation(
                    recommendation_id=f"retry-loop-{target}",
                    priority=1,
                    title="Break retry loop",
                    action=f"Introduce circuit breaker or cooldown for target '{target}'.",
                    rationale="Repeated retries indicate unstable recovery behavior.",
                )
            )

        deduped: dict[str, Recommendation] = {}
        for recommendation in recommendations:
            existing = deduped.get(recommendation.recommendation_id)
            if existing is None or recommendation.priority < existing.priority:
                deduped[recommendation.recommendation_id] = recommendation

        return sorted(deduped.values(), key=lambda rec: (rec.priority, rec.recommendation_id))
