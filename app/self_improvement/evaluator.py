"""Evaluation layer for deterministic self-improvement inputs."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.memory.models import MemoryRecord
from app.self_improvement.models import EvaluationResult


class Evaluator:
    """Evaluates execution history to produce deterministic quality signals."""

    def evaluate(self, memory_records: list[MemoryRecord | dict[str, Any]]) -> EvaluationResult:
        execution_entries = self._extract_entries(memory_records, expected_type="execution")
        task_entries = self._extract_entries(memory_records, expected_type="task")
        failure_entries = self._extract_entries(memory_records, expected_type="failure")
        decision_entries = self._extract_entries(memory_records, expected_type="decision")

        success_rate = self._success_rate(execution_entries)
        avg_latency = self._avg_latency(execution_entries)

        failure_patterns = self._top_patterns(
            [str(entry.get("error", "unknown")) for entry in failure_entries],
            prefix="failure",
        )

        retry_patterns = self._top_patterns(
            [
                str(entry.get("task_id", "unknown"))
                for entry in task_entries
                if isinstance(entry.get("retry_count"), int) and int(entry.get("retry_count")) > 0
            ],
            prefix="retry",
        )

        policy_violations = self._top_patterns(
            [
                str(entry.get("decision", "unknown"))
                for entry in decision_entries
                if str(entry.get("decision", "")).startswith("violation:")
            ],
            prefix="policy_violation",
        )

        return EvaluationResult(
            success_rate=round(success_rate, 4),
            avg_latency=round(avg_latency, 4),
            failure_patterns=failure_patterns,
            retry_patterns=retry_patterns,
            policy_violations=policy_violations,
        )

    def _extract_entries(
        self,
        records: list[MemoryRecord | dict[str, Any]],
        expected_type: str,
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for record in records:
            if isinstance(record, MemoryRecord):
                if record.type != expected_type:
                    continue
                if isinstance(record.data, dict):
                    entries.append(dict(record.data))
                continue

            if not isinstance(record, dict):
                continue
            if str(record.get("type")) != expected_type:
                continue
            payload = record.get("data", {})
            if isinstance(payload, dict):
                entries.append(dict(payload))
        return entries

    def _success_rate(self, execution_entries: list[dict[str, Any]]) -> float:
        if not execution_entries:
            return 1.0
        succeeded = sum(1 for entry in execution_entries if str(entry.get("status", "")).lower() == "success")
        return succeeded / len(execution_entries)

    def _avg_latency(self, execution_entries: list[dict[str, Any]]) -> float:
        latencies = [
            float(entry.get("latency", 0.0))
            for entry in execution_entries
            if isinstance(entry.get("latency", 0), (int, float))
        ]
        if not latencies:
            return 0.0
        return sum(latencies) / len(latencies)

    def _top_patterns(self, values: list[str], prefix: str) -> list[str]:
        if not values:
            return []
        counter = Counter(value.strip() or "unknown" for value in values)
        ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        return [f"{prefix}:{name}:{count}" for name, count in ordered]
