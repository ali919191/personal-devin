"""Orchestrates observability analysis for execution and memory data."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.analysis.models import AnalysisReport, ExecutionTraceSummary, FailurePattern, Recommendation
from app.analysis.registry import AnalysisRegistry, create_default_registry
from app.core.logger import get_logger
from app.memory.models import MemoryRecord

logger = get_logger(__name__)


class Analyzer:
    """Analyzes observed runtime artifacts without mutating runtime systems."""

    def __init__(self, registry: AnalysisRegistry | None = None) -> None:
        self._registry = registry or create_default_registry()

    def analyze(
        self,
        execution_id: str,
        execution_logs: list[dict[str, Any]],
        memory_records: list[MemoryRecord | dict[str, Any]],
    ) -> AnalysisReport:
        logger.info(
            "analysis_run_start",
            {
                "execution_id": execution_id,
                "log_count": len(execution_logs),
                "memory_count": len(memory_records),
            },
        )

        logs = self._normalize_logs(execution_logs)
        memory = self._normalize_memory(memory_records)

        trace_summary = self._build_trace_summary(logs)
        success_rate = (
            trace_summary.successful_events / trace_summary.total_events
            if trace_summary.total_events
            else 0.0
        )

        failure_patterns: list[FailurePattern] = []
        inefficiencies: list[str] = []
        retry_loops: list[str] = []

        for detector_name, detector in self._registry.list_detectors():
            output = detector(logs, memory)
            if detector_name == "failure_patterns":
                failure_patterns = list(output)
            elif detector_name == "inefficiencies":
                inefficiencies = sorted(set(str(item) for item in output))
            elif detector_name == "retry_loops":
                retry_loops = sorted(set(str(item) for item in output))

        recommendations: list[Recommendation] = []
        for _, recommendation_engine in self._registry.list_recommendation_engines():
            recommendations.extend(recommendation_engine(failure_patterns, inefficiencies, retry_loops))

        deduped_recommendations: dict[str, Recommendation] = {}
        for recommendation in recommendations:
            current = deduped_recommendations.get(recommendation.recommendation_id)
            if current is None or recommendation.priority < current.priority:
                deduped_recommendations[recommendation.recommendation_id] = recommendation

        ordered_recommendations = sorted(
            deduped_recommendations.values(),
            key=lambda rec: (rec.priority, rec.recommendation_id),
        )

        confidence_score = self._calculate_confidence(
            trace_summary=trace_summary,
            failure_patterns=failure_patterns,
            inefficiencies=inefficiencies,
            recommendations=ordered_recommendations,
        )

        report = AnalysisReport(
            execution_id=execution_id,
            success_rate=round(success_rate, 4),
            failure_patterns=failure_patterns,
            inefficiencies=inefficiencies,
            recommendations=ordered_recommendations,
            confidence_score=confidence_score,
            trace_summary=trace_summary,
        )

        logger.info(
            "analysis_run_end",
            {
                "execution_id": execution_id,
                "success_rate": report.success_rate,
                "failure_pattern_count": len(report.failure_patterns),
                "inefficiency_count": len(report.inefficiencies),
                "recommendation_count": len(report.recommendations),
                "confidence_score": report.confidence_score,
            },
        )

        return report

    def _normalize_logs(self, execution_logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for entry in execution_logs:
            clone = dict(deepcopy(entry))
            normalized.append(clone)
        return normalized

    def _normalize_memory(self, memory_records: list[MemoryRecord | dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for record in memory_records:
            if isinstance(record, MemoryRecord):
                payload = record.model_dump()
                payload["timestamp"] = record.timestamp.isoformat()
                normalized.append(payload)
            else:
                payload = dict(deepcopy(record))
                timestamp = payload.get("timestamp")
                if timestamp is not None:
                    payload["timestamp"] = str(timestamp)
                normalized.append(payload)
        return normalized

    def _build_trace_summary(self, execution_logs: list[dict[str, Any]]) -> ExecutionTraceSummary:
        total_events = len(execution_logs)
        successful_events = sum(
            1
            for entry in execution_logs
            if str(entry.get("status", "")).lower() in {"success", "completed"}
        )
        failed_events = sum(
            1
            for entry in execution_logs
            if str(entry.get("status", "")).lower() in {"failed", "error"}
        )
        retry_events = sum(
            int(entry.get("retry_count", 0))
            for entry in execution_logs
            if isinstance(entry.get("retry_count", 0), int)
        )

        duration_values = [
            int(entry.get("duration_ms"))
            for entry in execution_logs
            if isinstance(entry.get("duration_ms"), int)
        ]
        average_duration = (
            round(sum(duration_values) / len(duration_values), 4)
            if duration_values
            else 0.0
        )

        return ExecutionTraceSummary(
            total_events=total_events,
            successful_events=successful_events,
            failed_events=failed_events,
            retry_events=retry_events,
            average_duration_ms=average_duration,
        )

    def _calculate_confidence(
        self,
        trace_summary: ExecutionTraceSummary,
        failure_patterns: list[FailurePattern],
        inefficiencies: list[str],
        recommendations: list[Recommendation],
    ) -> float:
        score = 0.45
        score += min(trace_summary.total_events, 20) * 0.01
        if failure_patterns:
            score += 0.12
        if inefficiencies:
            score += 0.08
        if recommendations:
            score += 0.1
        if trace_summary.total_events > 0 and trace_summary.failed_events == 0:
            score += 0.05
        return round(min(score, 0.99), 4)
