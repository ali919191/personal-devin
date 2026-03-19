"""Policy layer for controlled deterministic self-improvement filtering."""

from __future__ import annotations

from dataclasses import dataclass

from app.self_improvement.models import ImprovementAction


@dataclass(frozen=True)
class ImprovementPolicy:
    """Policy constraints for safe deterministic improvement approval."""

    confidence_threshold: float = 0.7

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
