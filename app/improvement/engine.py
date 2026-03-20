from __future__ import annotations

from typing import Any

from app.core.logger import get_logger
from app.improvement.analyzer import ExecutionAnalyzer
from app.improvement.models import ImprovementAction, ImprovementPlan, ImprovementResult, SignalRecord
from app.improvement.optimizer import Optimizer
from app.improvement.pattern_detector import PatternDetector
from app.improvement.validator import ImprovementValidator

logger = get_logger(__name__)


class ImprovementEngine:
    """Deterministic self-improvement pipeline for Agent 33."""

    _SIGNAL_ACTIONS: dict[str, tuple[str, str, str]] = {
        "low_success_rate": (
            "planning.strategy",
            "increase_validation_before_execution",
            "retry_strategy",
        ),
        "high_latency": (
            "planning.step_order",
            "reorder_high_latency_steps_last",
            "optimize_execution",
        ),
        "frequent_failures": (
            "execution.retry_limit",
            "decrease_retry_limit_by_one",
            "increase_logging",
        ),
    }

    def __init__(
        self,
        analyzer: ExecutionAnalyzer | None = None,
        pattern_detector: PatternDetector | None = None,
        optimizer: Optimizer | None = None,
        validator: ImprovementValidator | None = None,
    ) -> None:
        self._analyzer = analyzer or ExecutionAnalyzer()
        self._pattern_detector = pattern_detector or PatternDetector()
        self._optimizer = optimizer or Optimizer()
        self._validator = validator or ImprovementValidator()

    def run(self, memory: Any) -> ImprovementPlan:
        history = self._read_execution_history(memory)
        analysis = self._analyzer.analyze(history)
        patterns = self._pattern_detector.detect(analysis)
        proposed_actions = self._optimizer.generate(patterns)

        plan = ImprovementPlan(
            version="agent-33-v1",
            analysis=analysis,
            patterns=patterns,
            actions=proposed_actions,
        )
        validated_plan = self._validator.validate(plan)

        for idx, action in enumerate(validated_plan.actions, start=1):
            self._log_application(action=action, result="success")
            self._write_memory_event(
                memory,
                {
                    "sequence": idx,
                    "event": "self_improvement_applied",
                    "pattern": action.source_signal,
                    "action": action.change,
                    "result": "success",
                    "target": action.target,
                    "reason": action.reason,
                },
            )

        for idx, action in enumerate(validated_plan.rejected_actions, start=1):
            self._log_application(action=action, result="rejected")
            self._write_memory_event(
                memory,
                {
                    "sequence": idx,
                    "event": "self_improvement_applied",
                    "pattern": action.source_signal,
                    "action": action.change,
                    "result": "rejected",
                    "target": action.target,
                    "reason": action.reason,
                },
            )

        return validated_plan

    def select_actions(self, signals: list[SignalRecord]) -> list[ImprovementAction]:
        actions: list[ImprovementAction] = []
        for signal in signals:
            mapping = self._SIGNAL_ACTIONS.get(signal.signal_type)
            if mapping is None:
                continue
            target, change, action_type = mapping
            actions.append(
                ImprovementAction(
                    source_signal=signal.signal_type,
                    action_type=action_type,
                )
            )
        return actions

    def apply(self, actions: list[ImprovementAction]) -> list[ImprovementResult]:
        normalized_actions = [self._normalize_action_for_apply(action) for action in actions]
        approved, rejected = self._validator.validate_actions(normalized_actions)
        results: list[ImprovementResult] = []

        for action in approved:
            results.append(
                ImprovementResult(
                    action_type=action.action_type or action.change,
                    status="applied",
                    target=action.target,
                    change=action.change,
                    reason=action.reason,
                )
            )

        for action in rejected:
            results.append(
                ImprovementResult(
                    action_type=action.action_type or action.change,
                    status="rejected",
                    target=action.target,
                    change=action.change,
                    reason=action.reason,
                )
            )

        return results

    def _normalize_action_for_apply(self, action: ImprovementAction) -> ImprovementAction:
        if action.target and action.change:
            return action

        legacy_map: dict[str, tuple[str, str]] = {
            "retry_strategy": ("planning.strategy", "increase_validation_before_execution"),
            "optimize_execution": ("planning.step_order", "reorder_high_latency_steps_last"),
            "increase_logging": ("execution.retry_limit", "decrease_retry_limit_by_one"),
        }
        action_type = action.action_type or action.change
        mapped = legacy_map.get(action_type)
        if mapped is None:
            return action

        target, change = mapped
        return ImprovementAction(
            target=target,
            change=change,
            reason=action.reason or f"legacy:{action_type}",
            action_type=action_type,
            source_signal=action.source_signal,
        )

    def _read_execution_history(self, memory: Any) -> list[dict[str, Any]]:
        if hasattr(memory, "read_all"):
            try:
                records = memory.read_all("execution")
                if isinstance(records, list):
                    return [self._safe_record(item) for item in records if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                return []

        if hasattr(memory, "get_recent"):
            try:
                records = memory.get_recent(100)
                if isinstance(records, list):
                    return [self._safe_record(item) for item in records if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                return []

        if hasattr(memory, "retrieve"):
            try:
                payload = memory.retrieve("*")
                if isinstance(payload, dict) and isinstance(payload.get("recent"), list):
                    return [self._safe_record(item) for item in payload["recent"] if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                return []

        return []

    def _safe_record(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            str(key): value
            for key, value in record.items()
            if isinstance(key, str)
        }
        return normalized

    def _write_memory_event(self, memory: Any, event: dict[str, Any]) -> None:
        if hasattr(memory, "append"):
            try:
                memory.append("decision", event)
                return
            except Exception:  # noqa: BLE001
                pass

        if hasattr(memory, "save"):
            try:
                memory.save(event)
            except Exception:  # noqa: BLE001
                return

    def _log_application(self, action: ImprovementAction, result: str) -> None:
        logger.info(
            "self_improvement_applied",
            {
                "event": "self_improvement_applied",
                "pattern": action.source_signal,
                "action": action.change,
                "target": action.target,
                "result": result,
            },
        )

