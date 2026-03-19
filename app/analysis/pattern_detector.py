"""Pattern detection primitives for execution and memory observations."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.analysis.models import FailurePattern


class PatternDetector:
    """Detects deterministic failure and inefficiency patterns."""

    def detect_failure_patterns(
        self,
        execution_logs: list[dict[str, Any]],
        memory_records: list[dict[str, Any]],
    ) -> list[FailurePattern]:
        counts: Counter[tuple[str, str]] = Counter()

        for entry in execution_logs:
            status = str(entry.get("status", "")).lower()
            if status not in {"failed", "error"}:
                continue
            signature = str(entry.get("error") or entry.get("message") or "unknown_error")
            source = str(entry.get("source") or "execution_log")
            counts[(source, signature)] += 1

        for record in memory_records:
            if str(record.get("type")) != "failure":
                continue
            data = record.get("data")
            if not isinstance(data, dict):
                continue
            source = f"memory:{data.get('source', 'unknown')}"
            signature = str(data.get("error") or "unknown_error")
            counts[(source, signature)] += 1

        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
        patterns: list[FailurePattern] = []
        for idx, ((source, signature), count) in enumerate(ordered, start=1):
            patterns.append(
                FailurePattern(
                    pattern_id=f"failure-{idx:03d}",
                    source=source,
                    signature=signature,
                    count=count,
                )
            )
        return patterns

    def detect_inefficiencies(self, execution_logs: list[dict[str, Any]]) -> list[str]:
        if not execution_logs:
            return []

        total = len(execution_logs)
        successful = sum(1 for entry in execution_logs if str(entry.get("status", "")).lower() in {"success", "completed"})
        retry_events = sum(int(entry.get("retry_count", 0)) for entry in execution_logs if isinstance(entry.get("retry_count", 0), int))

        duration_values = [
            int(entry.get("duration_ms"))
            for entry in execution_logs
            if isinstance(entry.get("duration_ms"), int)
        ]

        inefficiencies: list[str] = []
        if duration_values:
            average_duration = sum(duration_values) / len(duration_values)
            if average_duration > 2000:
                inefficiencies.append("high_average_duration")

        success_rate = successful / total if total else 0.0
        if success_rate < 0.7:
            inefficiencies.append("low_success_rate")

        if retry_events > 0:
            inefficiencies.append("retry_activity_detected")

        return sorted(set(inefficiencies))

    def detect_retry_loops(self, execution_logs: list[dict[str, Any]]) -> list[str]:
        explicit_loops = {
            str(entry.get("task_id") or entry.get("action") or "unknown")
            for entry in execution_logs
            if isinstance(entry.get("retry_count"), int) and int(entry.get("retry_count")) >= 3
        }

        failed_by_target: Counter[str] = Counter()
        for entry in execution_logs:
            status = str(entry.get("status", "")).lower()
            if status not in {"failed", "error"}:
                continue
            target = str(entry.get("task_id") or entry.get("action") or "unknown")
            failed_by_target[target] += 1

        repeated_failures = {target for target, count in failed_by_target.items() if count >= 3}
        return sorted(explicit_loops | repeated_failures)
