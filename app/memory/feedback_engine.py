"""Memory feedback loop utilities built on top of the analysis layer."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.analysis.pattern_detector import PatternDetector
from app.core.logger import get_logger
from app.memory.models import ExecutionRecord

logger = get_logger(__name__)


class FeedbackEngine:
    """Builds deterministic feedback context from memory history."""

    def __init__(self, pattern_detector: PatternDetector | None = None) -> None:
        self._pattern_detector = pattern_detector or PatternDetector()

    def build_context(self, records: list[ExecutionRecord]) -> dict[str, Any]:
        execution_logs = self._as_execution_logs(records)
        memory_failures = self._as_failure_memory_records(records)

        patterns = self._pattern_detector.detect_failure_patterns(execution_logs, memory_failures)
        repeated_failures = [
            {
                "source": pattern.source,
                "signature": pattern.signature,
                "count": pattern.count,
            }
            for pattern in patterns
            if pattern.count >= 2
        ]

        strategy_counter: Counter[str] = Counter()
        for record in records:
            if not record.success:
                continue
            strategy = self._strategy_for(record)
            if strategy:
                strategy_counter[strategy] += 1

        success_strategies = [
            {"strategy": strategy, "count": count}
            for strategy, count in sorted(
                strategy_counter.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

        context = {
            "total_records": len(records),
            "repeated_failures": repeated_failures,
            "success_strategies": success_strategies,
        }
        logger.info(
            "memory_feedback_context_built",
            {
                "record_count": len(records),
                "repeated_failure_count": len(repeated_failures),
                "success_strategy_count": len(success_strategies),
            },
        )
        return context

    def adjust_task(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        adjusted = dict(task)
        metadata = adjusted.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata = dict(metadata)

        repeated = context.get("repeated_failures")
        if isinstance(repeated, list) and repeated:
            signatures = sorted(
                {
                    str(item.get("signature"))
                    for item in repeated
                    if isinstance(item, dict) and item.get("signature")
                }
            )
            if signatures:
                metadata["avoid_failure_signatures"] = signatures

        strategies = context.get("success_strategies")
        if isinstance(strategies, list) and strategies:
            preferred = [
                str(item.get("strategy"))
                for item in strategies
                if isinstance(item, dict) and item.get("strategy")
            ]
            preferred = [value for value in preferred if value]
            if preferred:
                metadata["preferred_strategies"] = preferred

        adjusted["metadata"] = metadata
        logger.info(
            "memory_feedback_adjustment_applied",
            {
                "task_id": str(adjusted.get("id", "unknown")),
                "metadata_keys": sorted(metadata.keys()),
            },
        )
        return adjusted

    def _as_execution_logs(self, records: list[ExecutionRecord]) -> list[dict[str, Any]]:
        logs: list[dict[str, Any]] = []
        for record in records:
            error = record.errors[0] if record.errors else ""
            logs.append(
                {
                    "task_id": record.task_id,
                    "status": "completed" if record.success else "failed",
                    "error": error,
                    "source": str(record.metadata.get("source", "memory_feedback")),
                    "retry_count": int(record.metadata.get("retry_count", 0)),
                }
            )
        return logs

    def _as_failure_memory_records(self, records: list[ExecutionRecord]) -> list[dict[str, Any]]:
        failures: list[dict[str, Any]] = []
        for record in records:
            if record.success:
                continue
            for error in record.errors:
                failures.append(
                    {
                        "type": "failure",
                        "data": {
                            "source": str(record.metadata.get("source", "memory_feedback")),
                            "error": str(error),
                            "context": {
                                "task_id": record.task_id,
                            },
                        },
                    }
                )
        return failures

    def _strategy_for(self, record: ExecutionRecord) -> str:
        metadata_strategy = record.metadata.get("strategy")
        if metadata_strategy:
            return str(metadata_strategy)

        plan_strategy = record.plan.get("strategy")
        if plan_strategy:
            return str(plan_strategy)

        return ""
