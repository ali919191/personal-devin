"""Policy layer for controlled deterministic self-improvement filtering."""

from __future__ import annotations

from dataclasses import dataclass

from app.self_improvement.models import ImprovementAction, SelfImprovementAdaptation

# Confidence thresholds
_DEFAULT_AGENT14_THRESHOLD = 0.7
_DEFAULT_AGENT15_THRESHOLD = 0.6


@dataclass(frozen=True)
class ImprovementPolicy:
    """Policy constraints for safe deterministic improvement approval (Agent 14)."""

    confidence_threshold: float = _DEFAULT_AGENT14_THRESHOLD

    def approve(self, actions: list[ImprovementAction]) -> list[ImprovementAction]:
        filtered = [action for action in actions if action.confidence >= self.confidence_threshold]

        # Stabilization: prevent oscillation by keeping one highest-confidence action per target.
        best_by_target: dict[str, ImprovementAction] = {}
        for action in sorted(filtered, key=lambda item: (-item.confidence, item.type, item.target, str(item.value))):
            existing = best_by_target.get(action.target)
            if existing is None:
                best_by_target[action.target] = action
                continue
            if action.confidence > existing.confidence:
                best_by_target[action.target] = action

        approved = sorted(
            best_by_target.values(),
            key=lambda item: (item.type, item.target, str(item.value), -item.confidence),
        )
        return approved


@dataclass(frozen=True)
class AdaptationPolicy:
    """Policy validator for Agent 15 candidate adaptations."""

    confidence_threshold: float = _DEFAULT_AGENT15_THRESHOLD
    # Forbidden targets: adaptations targeting these are always rejected.
    forbidden_targets: tuple[str, ...] = ()

    def validate(
        self,
        adaptations: list[SelfImprovementAdaptation],
    ) -> tuple[list[SelfImprovementAdaptation], list[SelfImprovementAdaptation]]:
        """Split adaptations into (approved, rejected) deterministically."""
        approved: list[SelfImprovementAdaptation] = []
        rejected: list[SelfImprovementAdaptation] = []

        # Stable input ordering before validation to ensure determinism.
        ordered = sorted(adaptations, key=lambda a: (a.action_type, a.target, a.adaptation_id))

        # Keep best-confidence per (action_type, target) pair to prevent oscillation.
        seen: dict[tuple[str, str], SelfImprovementAdaptation] = {}
        for candidate in ordered:
            if candidate.confidence_score < self.confidence_threshold:
                rejected.append(candidate)
                continue
            if candidate.target in self.forbidden_targets:
                rejected.append(candidate)
                continue
            key = (candidate.action_type, candidate.target)
            existing = seen.get(key)
            if existing is None or candidate.confidence_score > existing.confidence_score:
                if existing is not None:
                    rejected.append(existing)
                seen[key] = candidate
            else:
                rejected.append(candidate)

        approved = sorted(
            seen.values(),
            key=lambda a: (a.action_type, a.target, a.adaptation_id),
        )
        rejected = sorted(
            rejected,
            key=lambda a: (a.action_type, a.target, a.adaptation_id),
        )
        return approved, rejected
