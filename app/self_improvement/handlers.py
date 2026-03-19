"""Handler dispatch table for Agent 14 improvement actions.

Stubs are intentionally minimal — concrete logic is deferred to Agent 15
(Adaptive Execution), which will replace these with real implementations.
The mapping is the contract; the signatures are the interface.
"""

from __future__ import annotations

from typing import Any, Callable

from app.self_improvement.models import ImprovementAction, ImprovementType

HandlerResult = dict[str, Any]
ImprovementHandler = Callable[[ImprovementAction], HandlerResult]


def handle_policy_adjustment(action: ImprovementAction) -> HandlerResult:
    """Stub: adjust a policy parameter based on the improvement action."""
    return {"handler": "policy_adjustment", "target": action.target, "value": action.value, "applied": False}


def handle_strategy_change(action: ImprovementAction) -> HandlerResult:
    """Stub: switch execution strategy based on the improvement action."""
    return {"handler": "strategy_change", "target": action.target, "value": action.value, "applied": False}


def handle_confidence_increase(action: ImprovementAction) -> HandlerResult:
    """Stub: raise confidence threshold for a policy gate."""
    return {"handler": "confidence_increase", "target": action.target, "value": action.value, "applied": False}


IMPROVEMENT_HANDLERS: dict[ImprovementType, ImprovementHandler] = {
    ImprovementType.ADJUST_POLICY: handle_policy_adjustment,
    ImprovementType.CHANGE_STRATEGY: handle_strategy_change,
    ImprovementType.INCREASE_CONFIDENCE: handle_confidence_increase,
}
