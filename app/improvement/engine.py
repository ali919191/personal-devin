from typing import List

from app.improvement.models import ImprovementAction, ImprovementResult, SignalRecord
from app.improvement.registry import REGISTRY


class ImprovementEngine:
    def select_actions(self, signals: List[SignalRecord]) -> List[ImprovementAction]:
        actions: List[ImprovementAction] = []

        for signal in signals:
            mapped_actions = REGISTRY.get(signal.signal_type, [])
            for action_type in mapped_actions:
                actions.append(
                    ImprovementAction(
                        action_type=action_type,
                        source_signal=signal.signal_type,
                    )
                )

        return actions

    def apply(self, actions: List[ImprovementAction]) -> List[ImprovementResult]:
        results: List[ImprovementResult] = []

        for action in actions:
            results.append(
                ImprovementResult(
                    action_type=action.action_type,
                    status="applied",
                )
            )

        return results
