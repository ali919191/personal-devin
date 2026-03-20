from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.improvement.models import AnalysisSummary


class ExecutionAnalyzer:
    """Build deterministic aggregates from execution records."""

    def analyze(self, records: list[dict[str, Any]]) -> AnalysisSummary:
        total = len(records)
        failure_count = 0

        retry_counts: dict[str, int] = defaultdict(int)
        latency_sum: dict[str, float] = defaultdict(float)
        latency_count: dict[str, int] = defaultdict(int)
        failure_points: dict[str, int] = defaultdict(int)
        tool_misuse: dict[str, int] = defaultdict(int)

        for record in records:
            if self._is_failure(record):
                failure_count += 1

            step_id = self._step_id(record)
            if self._is_retry(record):
                retry_counts[step_id] += 1

            latency = self._latency_ms(record)
            if latency is not None:
                latency_sum[step_id] += latency
                latency_count[step_id] += 1

            if self._is_failure(record):
                failure_points[step_id] += 1

            error_type = self._error_type(record)
            if error_type in {"policy_violation", "invalid_operation", "tool_misuse"}:
                tool_misuse[error_type] += 1

        step_latency = {
            key: round(latency_sum[key] / latency_count[key], 3)
            for key in sorted(latency_sum.keys())
            if latency_count[key] > 0
        }

        ordered_failure_points = sorted(
            failure_points.items(),
            key=lambda item: (-item[1], item[0]),
        )

        failure_rate = round((failure_count / total), 4) if total > 0 else 0.0

        return AnalysisSummary(
            total_executions=total,
            failure_rate=failure_rate,
            retry_patterns={key: retry_counts[key] for key in sorted(retry_counts.keys())},
            step_latency=step_latency,
            common_failure_points=[name for name, _ in ordered_failure_points],
            common_failure_counts={name: count for name, count in ordered_failure_points},
            tool_misuse_patterns={key: tool_misuse[key] for key in sorted(tool_misuse.keys())},
        )

    def _is_failure(self, record: dict[str, Any]) -> bool:
        if isinstance(record.get("success"), bool):
            return not bool(record["success"])
        status = str(record.get("status", "")).lower()
        return status in {"failed", "failure", "error"}

    def _is_retry(self, record: dict[str, Any]) -> bool:
        decision = str(record.get("decision", ""))
        return decision == "retry_same"

    def _step_id(self, record: dict[str, Any]) -> str:
        current_step = record.get("current_step")
        if isinstance(current_step, dict):
            return str(current_step.get("id", "unknown_step"))
        return "unknown_step"

    def _latency_ms(self, record: dict[str, Any]) -> float | None:
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

    def _error_type(self, record: dict[str, Any]) -> str:
        classification = record.get("classification")
        if isinstance(classification, dict):
            return str(classification.get("error_type", "none"))

        result = record.get("result")
        if isinstance(result, dict):
            return str(result.get("error_type", "none"))

        return "none"
