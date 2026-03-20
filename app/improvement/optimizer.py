from __future__ import annotations

from app.improvement.models import ImprovementAction, Pattern


class Optimizer:
    """Map patterns to deterministic, bounded improvement actions."""

    def generate(self, patterns: list[Pattern]) -> list[ImprovementAction]:
        actions: list[ImprovementAction] = []

        for pattern in sorted(patterns, key=lambda p: (p.type, p.location, p.frequency, p.severity)):
            if pattern.type == "repeated_failure":
                actions.append(
                    ImprovementAction(
                        target="planning.strategy",
                        change="increase_validation_before_execution",
                        reason=f"{pattern.location} repeated failures",
                        source_signal=pattern.type,
                    )
                )
            elif pattern.type == "redundant_retries":
                actions.append(
                    ImprovementAction(
                        target="execution.retry_limit",
                        change="decrease_retry_limit_by_one",
                        reason=f"{pattern.location} redundant retries",
                        source_signal=pattern.type,
                    )
                )
            elif pattern.type == "inefficient_plan":
                actions.append(
                    ImprovementAction(
                        target="planning.step_order",
                        change="reorder_high_latency_steps_last",
                        reason=f"{pattern.location} high latency",
                        source_signal=pattern.type,
                    )
                )
            elif pattern.type == "tool_misuse":
                actions.append(
                    ImprovementAction(
                        target="execution.tooling",
                        change="substitute_safer_tool_profile",
                        reason=f"{pattern.location} misuse detected",
                        source_signal=pattern.type,
                    )
                )

        actions.sort(key=lambda a: (a.target, a.change, a.reason, a.source_signal))
        return actions
