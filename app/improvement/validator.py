from __future__ import annotations

from app.improvement.models import ImprovementAction, ImprovementPlan


class ImprovementValidator:
    """Reject unsafe or out-of-bound improvement actions."""

    _ALLOWED_TARGETS = {
        "planning.strategy",
        "planning.step_order",
        "execution.retry_limit",
        "execution.tooling",
    }

    _ALLOWED_CHANGES = {
        "increase_validation_before_execution",
        "decrease_retry_limit_by_one",
        "reorder_high_latency_steps_last",
        "substitute_safer_tool_profile",
    }

    _FORBIDDEN_TOKENS = {
        "remove_module",
        "delete_module",
        "core.contract",
        "core.orchestrator",
        "drop_contract",
    }

    def validate_actions(self, actions: list[ImprovementAction]) -> tuple[list[ImprovementAction], list[ImprovementAction]]:
        approved: list[ImprovementAction] = []
        rejected: list[ImprovementAction] = []

        for action in actions:
            if self._is_safe(action):
                approved.append(action)
            else:
                rejected.append(action)
        return approved, rejected

    def validate(self, plan: ImprovementPlan) -> ImprovementPlan:
        approved, rejected = self.validate_actions(plan.actions)
        return ImprovementPlan(
            version=plan.version,
            analysis=plan.analysis,
            patterns=plan.patterns,
            actions=approved,
            rejected_actions=rejected,
        )

    def _is_safe(self, action: ImprovementAction) -> bool:
        if action.target not in self._ALLOWED_TARGETS:
            return False
        if action.change not in self._ALLOWED_CHANGES:
            return False

        combined = f"{action.target}|{action.change}|{action.reason}".lower()
        return all(token not in combined for token in self._FORBIDDEN_TOKENS)
