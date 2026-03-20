from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from app.core.logger import get_logger
from app.improvement.analyzer import ExecutionAnalyzer
from app.improvement.models import (
    ImprovementAction,
    ImprovementMetrics,
    ImprovementPlan,
    ImprovementRecord,
    ImprovementResult,
    RollbackAction,
    SignalRecord,
)
from app.improvement.optimizer import Optimizer
from app.improvement.pattern_detector import PatternDetector
from app.improvement.validator import ImprovementValidator

logger = get_logger(__name__)


class ImprovementEngine:
    """Deterministic self-improvement pipeline for Agent 33."""

    # Acceptance threshold: improvements must improve by at least 5% to be accepted
    MIN_IMPROVEMENT_DELTA = 0.05

    # Cooldown: enforce minimum 3 improvement cycles between applications
    COOLDOWN_CYCLES = 3

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
        clock: callable | None = None,
    ) -> None:
        self._analyzer = analyzer or ExecutionAnalyzer()
        self._pattern_detector = pattern_detector or PatternDetector()
        self._optimizer = optimizer or Optimizer()
        self._validator = validator or ImprovementValidator()
        self._clock = clock or (lambda: datetime.now(UTC))

    def run(self, memory: Any) -> ImprovementPlan:
        # Check cooldown before proceeding with improvements
        is_on_cooldown = self._is_on_cooldown(memory)

        history_before = self._read_execution_history(memory)
        metrics_before = self._compute_metrics(history_before)

        analysis = self._analyzer.analyze(history_before)
        patterns = self._pattern_detector.detect(analysis)
        proposed_actions = self._optimizer.generate(patterns)

        plan = ImprovementPlan(
            version="agent-33-v3",
            analysis=analysis,
            patterns=patterns,
            actions=proposed_actions,
        )
        validated_plan = self._validator.validate(plan)

        # Only apply improvements if NOT on cooldown
        actions_to_apply = [] if is_on_cooldown else validated_plan.actions

        for idx, action in enumerate(actions_to_apply, start=1):
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

        if is_on_cooldown:
            self._write_memory_event(
                memory,
                {
                    "event": "improvement_cooldown_active",
                    "cycles_remaining": self.COOLDOWN_CYCLES,
                },
            )

        history_after = self._read_execution_history(memory)
        metrics_after = self._compute_metrics(history_after)
        impact_score = self._compute_impact_score(metrics_before=metrics_before, metrics_after=metrics_after)

        # Determine if improvement accepted based on threshold
        accepted = self._should_accept_improvement(impact_score) and len(actions_to_apply) > 0

        # Build rollback actions for applied improvements
        rollback_actions = self._build_rollback_actions(actions_to_apply, self._next_improvement_version(memory))

        impact_result = ImprovementResult(
            action_type="self_improvement_run",
            status="applied" if len(actions_to_apply) > 0 else "cooldown" if is_on_cooldown else "noop",
            success=accepted,
            impact_score=impact_score,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            rollback_applied=False,
        )

        improvement_record = self._build_improvement_record(
            memory=memory,
            patterns=validated_plan.patterns,
            actions=actions_to_apply,
            result=impact_result.status,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            impact_score=impact_score,
            accepted=accepted,
            rollback_actions=rollback_actions,
        )

        self._write_memory_event(
            memory,
            {
                "event": "improvement_record",
                "id": improvement_record.id,
                "timestamp": improvement_record.timestamp.isoformat(),
                "version": improvement_record.version,
                "result": improvement_record.result,
                "patterns": [asdict(pattern) for pattern in improvement_record.patterns],
                "actions": [asdict(action) for action in improvement_record.actions],
                "accepted": improvement_record.accepted,
                "impact_score": improvement_record.impact_score,
                "metrics_before": asdict(metrics_before),
                "metrics_after": asdict(metrics_after),
                "rollback_actions": [asdict(rb) for rb in rollback_actions],
                "impact": asdict(impact_result),
            },
        )

        return ImprovementPlan(
            version=validated_plan.version,
            analysis=validated_plan.analysis,
            patterns=validated_plan.patterns,
            actions=actions_to_apply,
            rejected_actions=validated_plan.rejected_actions,
            record=improvement_record,
        )

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

        # Empty metrics for legacy apply() method (no before/after available)
        empty_metrics = ImprovementMetrics(
            success_rate=0.0,
            failure_rate=0.0,
            avg_step_latency=0.0,
            retry_rate=0.0,
        )

        for action in approved:
            results.append(
                ImprovementResult(
                    action_type=action.action_type or action.change,
                    status="applied",
                    target=action.target,
                    change=action.change,
                    reason=action.reason,
                    metrics_before=empty_metrics,
                    metrics_after=empty_metrics,
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
                    metrics_before=empty_metrics,
                    metrics_after=empty_metrics,
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

    def _compute_metrics(self, records: list[dict[str, Any]]) -> ImprovementMetrics:
        total = len(records)
        if total <= 0:
            return ImprovementMetrics(
                success_rate=0.0,
                failure_rate=0.0,
                avg_step_latency=0.0,
                retry_rate=0.0,
            )

        success_count = 0
        failure_count = 0
        retry_count = 0
        latency_values: list[float] = []

        for record in records:
            if self._is_success(record):
                success_count += 1
            else:
                failure_count += 1

            if str(record.get("decision", "")) == "retry_same":
                retry_count += 1

            latency = self._extract_latency_ms(record)
            if latency is not None:
                latency_values.append(latency)

        avg_latency = round(sum(latency_values) / len(latency_values), 3) if latency_values else 0.0
        return ImprovementMetrics(
            success_rate=round(success_count / total, 4),
            failure_rate=round(failure_count / total, 4),
            avg_step_latency=avg_latency,
            retry_rate=round(retry_count / total, 4),
        )

    def _compute_impact_score(
        self,
        *,
        metrics_before: ImprovementMetrics,
        metrics_after: ImprovementMetrics,
    ) -> float:
        success_delta = metrics_after.success_rate - metrics_before.success_rate
        failure_delta = metrics_before.failure_rate - metrics_after.failure_rate
        latency_before = metrics_before.avg_step_latency
        latency_after = metrics_after.avg_step_latency
        latency_delta = 0.0
        if latency_before > 0:
            latency_delta = (latency_before - latency_after) / latency_before

        score = success_delta * 0.6 + failure_delta * 0.3 + latency_delta * 0.1
        return round(score, 4)

    def _build_improvement_record(
        self,
        *,
        memory: Any,
        patterns: list,
        actions: list,
        result: str,
        metrics_before: ImprovementMetrics,
        metrics_after: ImprovementMetrics,
        impact_score: float,
        accepted: bool,
        rollback_actions: list[RollbackAction] | None = None,
    ) -> ImprovementRecord:
        version = self._next_improvement_version(memory)
        return ImprovementRecord(
            id=f"improvement-{version:06d}",
            timestamp=self._clock(),
            patterns=list(patterns),
            actions=list(actions),
            result=result,
            version=version,
            rollback_actions=rollback_actions or [],
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            impact_score=impact_score,
            accepted=accepted,
        )

    def _next_improvement_version(self, memory: Any) -> int:
        if hasattr(memory, "read_all"):
            try:
                decision_records = memory.read_all("decision")
                if isinstance(decision_records, list):
                    versions = [
                        int(record.get("version", 0))
                        for record in decision_records
                        if isinstance(record, dict) and record.get("event") == "improvement_record"
                    ]
                    if versions:
                        return max(versions) + 1
            except Exception:  # noqa: BLE001
                return 1
        return 1

    def _is_on_cooldown(self, memory: Any) -> bool:
        """Check if system is on cooldown from last improvement."""
        if not hasattr(memory, "read_all"):
            return False

        try:
            decision_records = memory.read_all("decision")
            if not isinstance(decision_records, list):
                return False

            # Find all accepted improvements
            accepted_improvements = [
                record
                for record in decision_records
                if isinstance(record, dict)
                and record.get("event") == "improvement_record"
                and record.get("accepted") is True
            ]

            if not accepted_improvements:
                return False

            # Count records since last accepted improvement
            last_accepted_idx = len(decision_records) - 1
            for i in range(len(decision_records) - 1, -1, -1):
                record = decision_records[i]
                if (isinstance(record, dict) and record.get("event") == "improvement_record"
                    and record.get("accepted") is True):
                    last_accepted_idx = i
                    break

            cycles_since_last = len(decision_records) - last_accepted_idx - 1
            return cycles_since_last < self.COOLDOWN_CYCLES

        except Exception:  # noqa: BLE001
            return False

    def _should_accept_improvement(self, impact_score: float) -> bool:
        """Check if improvement meets acceptance threshold."""
        return impact_score >= self.MIN_IMPROVEMENT_DELTA

    def _build_rollback_actions(
        self,
        actions: list[ImprovementAction],
        version: int,
    ) -> list[RollbackAction]:
        """Build rollback actions for potential reversal."""
        rollbacks: list[RollbackAction] = []
        for action in actions:
            rollbacks.append(
                RollbackAction(
                    target=action.target,
                    previous_value=f"reverted_from_v{version}",
                    version=version,
                )
            )
        return rollbacks

    def _is_success(self, record: dict[str, Any]) -> bool:
        if isinstance(record.get("success"), bool):
            return bool(record.get("success"))
        status = str(record.get("status", "")).lower()
        return status in {"success", "completed"}

    def _extract_latency_ms(self, record: dict[str, Any]) -> float | None:
        result = record.get("result")
        if not isinstance(result, dict):
            return None

        duration_ms = result.get("duration_ms")
        if isinstance(duration_ms, (int, float)):
            return float(duration_ms)

        latency_ms = result.get("latency_ms")
        if isinstance(latency_ms, (int, float)):
            return float(latency_ms)

        runtime_seconds = result.get("runtime_seconds")
        if isinstance(runtime_seconds, (int, float)):
            return float(runtime_seconds) * 1000.0

        return None

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

