"""Optimization layer mapping evaluations to improvement actions."""

from __future__ import annotations

from app.self_improvement.models import EvaluationResult, ImprovementAction, ImprovementType


class Optimizer:
    """Generates deterministic improvement actions from evaluation results."""

    def optimize(self, evaluation: EvaluationResult) -> list[ImprovementAction]:
        actions: list[ImprovementAction] = []

        if evaluation.success_rate < 0.8:
            actions.append(
                ImprovementAction(
                    type=ImprovementType.ADJUST_POLICY,
                    target="retry_limit",
                    value=3,
                    confidence=0.85,
                )
            )

        if evaluation.avg_latency > 2.0:
            actions.append(
                ImprovementAction(
                    type=ImprovementType.CHANGE_STRATEGY,
                    target="timeout",
                    value=10,
                    confidence=0.8,
                )
            )

        if evaluation.failure_patterns:
            actions.append(
                ImprovementAction(
                    type=ImprovementType.INCREASE_CONFIDENCE,
                    target="policy_gate",
                    value="strict",
                    confidence=0.75,
                )
            )

        if evaluation.policy_violations:
            actions.append(
                ImprovementAction(
                    type=ImprovementType.ADJUST_POLICY,
                    target="policy_violation_guard",
                    value="enabled",
                    confidence=0.9,
                )
            )

        if evaluation.retry_patterns:
            actions.append(
                ImprovementAction(
                    type=ImprovementType.CHANGE_STRATEGY,
                    target="retry_backoff",
                    value="exponential",
                    confidence=0.7,
                )
            )

        return sorted(actions, key=lambda action: (action.type, action.target, str(action.value), -action.confidence))
