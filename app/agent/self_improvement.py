"""Deterministic self-improvement engine for post-run analysis."""

from __future__ import annotations

from typing import Any

from app.core.logger import get_logger
from app.memory.service import MemoryService

logger = get_logger(__name__)


class SelfImprovementEngine:
    """Analyzes runs and produces deterministic improvement recommendations."""

    def __init__(self, memory_service: MemoryService | None = None) -> None:
        self._memory = memory_service or MemoryService()

    def analyze_run(self, run_data: dict) -> dict:
        """Analyze a run payload and extract structured findings."""
        logger.info("self_improvement_analysis_started", {"has_input": bool(run_data)})

        if not isinstance(run_data, dict) or not run_data:
            analysis = {
                "classification": "unknown",
                "failure_causes": [],
                "inefficiencies": ["missing_run_data"],
                "repeated_patterns": [],
                "summary": {
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "failed_tasks": 0,
                    "skipped_tasks": 0,
                    "success_rate": 0.0,
                },
            }
            logger.info("self_improvement_analysis_completed", {"classification": "unknown"})
            return analysis

        status = str(run_data.get("status", "unknown"))
        metrics = run_data.get("metrics", {})
        tasks = run_data.get("tasks", [])

        total_tasks = int(metrics.get("total", len(tasks) if isinstance(tasks, list) else 0))
        completed_tasks = int(metrics.get("completed", 0))
        failed_tasks = int(metrics.get("failed", 0))
        skipped_tasks = int(metrics.get("skipped", 0))

        if status == "unknown":
            if total_tasks == 0:
                status = "unknown"
            elif failed_tasks == 0 and skipped_tasks == 0:
                status = "success"
            elif completed_tasks == 0:
                status = "failure"
            else:
                status = "partial"

        failure_causes = self._extract_failure_causes(tasks)
        inefficiencies = self._detect_inefficiencies(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            skipped_tasks=skipped_tasks,
        )
        repeated_patterns = self._detect_repeated_patterns(failure_causes)

        success_rate = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        analysis = {
            "classification": status,
            "failure_causes": failure_causes,
            "inefficiencies": inefficiencies,
            "repeated_patterns": repeated_patterns,
            "summary": {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "skipped_tasks": skipped_tasks,
                "success_rate": success_rate,
            },
        }
        logger.info(
            "self_improvement_analysis_completed",
            {
                "classification": status,
                "failure_causes": len(failure_causes),
                "inefficiencies": len(inefficiencies),
                "repeated_patterns": len(repeated_patterns),
            },
        )
        return analysis

    def generate_insights(self, analysis: dict) -> list[dict]:
        """Generate deterministic insights from analysis output."""
        classification = str(analysis.get("classification", "unknown"))
        failure_causes = list(analysis.get("failure_causes", []))
        inefficiencies = list(analysis.get("inefficiencies", []))
        repeated_patterns = list(analysis.get("repeated_patterns", []))

        insights: list[dict[str, Any]] = []

        for error in sorted(failure_causes):
            insights.append(
                {
                    "type": "failure_pattern",
                    "message": f"Observed failure cause: {error}",
                    "confidence": 0.95,
                    "metadata": {"error": error},
                }
            )

        for pattern in sorted(repeated_patterns, key=lambda item: (item["error"], item["count"])):
            insights.append(
                {
                    "type": "warning",
                    "message": f"Repeated failure pattern detected: {pattern['error']}",
                    "confidence": 0.9,
                    "metadata": pattern,
                }
            )

        for inefficiency in sorted(inefficiencies):
            insights.append(
                {
                    "type": "optimization",
                    "message": f"Optimization opportunity: {inefficiency}",
                    "confidence": 0.8,
                    "metadata": {"inefficiency": inefficiency},
                }
            )

        if not insights:
            insights.append(
                {
                    "type": "optimization",
                    "message": "Run is stable with no immediate optimization flags",
                    "confidence": 0.85,
                    "metadata": {"classification": classification},
                }
            )

        logger.info("self_improvement_insights_generated", {"count": len(insights)})
        return insights

    def suggest_optimizations(self, insights: list[dict]) -> list[dict]:
        """Map insights to actionable deterministic recommendations."""
        suggestions: list[dict[str, str]] = []

        for insight in insights:
            insight_type = str(insight.get("type", "warning"))
            message = str(insight.get("message", ""))

            if insight_type == "failure_pattern":
                suggestions.append(
                    {
                        "priority": "high",
                        "suggestion": "Add targeted retry or precondition checks for recurring failures",
                        "target": "execution",
                        "rationale": message,
                    }
                )
            elif insight_type == "optimization":
                suggestions.append(
                    {
                        "priority": "medium",
                        "suggestion": "Refine task decomposition and execution grouping to reduce inefficiencies",
                        "target": "planning",
                        "rationale": message,
                    }
                )
            else:
                suggestions.append(
                    {
                        "priority": "medium",
                        "suggestion": "Track repeated warnings in memory and escalate when threshold is exceeded",
                        "target": "memory",
                        "rationale": message,
                    }
                )

        if not suggestions:
            suggestions.append(
                {
                    "priority": "low",
                    "suggestion": "No immediate changes required",
                    "target": "agent",
                    "rationale": "No insights were generated",
                }
            )

        logger.info("self_improvement_suggestions_generated", {"count": len(suggestions)})
        return suggestions

    def process(self, run_data: dict) -> dict:
        """Run the full self-improvement pipeline and persist summaries."""
        analysis = self.analyze_run(run_data)
        insights = self.generate_insights(analysis)
        suggestions = self.suggest_optimizations(insights)

        self._persist_results(run_data, analysis, insights, suggestions)

        return {
            "analysis": analysis,
            "insights": insights,
            "suggestions": suggestions,
        }

    def _extract_failure_causes(self, tasks: Any) -> list[str]:
        if not isinstance(tasks, list):
            return []

        causes: set[str] = set()
        for task in tasks:
            if not isinstance(task, dict):
                continue
            status = str(task.get("status", ""))
            if status not in {"failed", "skipped"}:
                continue

            error = task.get("error") or task.get("skip_reason") or "unknown"
            causes.add(str(error))

        return sorted(causes)

    def _detect_inefficiencies(
        self,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int,
        skipped_tasks: int,
    ) -> list[str]:
        inefficiencies: list[str] = []

        if total_tasks == 0:
            inefficiencies.append("empty_execution")
            return inefficiencies

        if completed_tasks < total_tasks:
            inefficiencies.append("incomplete_completion")

        if skipped_tasks > 0:
            inefficiencies.append("skipped_tasks_present")

        if failed_tasks > 0:
            inefficiencies.append("failure_overhead_detected")

        success_rate = completed_tasks / total_tasks
        if success_rate < 0.5:
            inefficiencies.append("low_success_rate")

        return sorted(inefficiencies)

    def _detect_repeated_patterns(self, failure_causes: list[str]) -> list[dict[str, Any]]:
        historical_patterns = self._memory.get_patterns()
        repeated: list[dict[str, Any]] = []

        current = set(failure_causes)
        for pattern in sorted(
            historical_patterns,
            key=lambda item: (str(item.get("error", "")), int(item.get("count", 0))),
        ):
            error = str(pattern.get("error", "unknown"))
            count = int(pattern.get("count", 0))
            if error in current and count > 1:
                repeated.append({"error": error, "count": count})

        return repeated

    def _persist_results(
        self,
        run_data: dict,
        analysis: dict,
        insights: list[dict],
        suggestions: list[dict],
    ) -> None:
        goal = str(run_data.get("goal", "unknown")) if isinstance(run_data, dict) else "unknown"

        self._memory.log_decision(
            decision="self_improvement_summary",
            reason=f"classification={analysis.get('classification', 'unknown')}",
            context={
                "goal": goal,
                "summary": analysis.get("summary", {}),
                "classification": analysis.get("classification", "unknown"),
            },
        )

        self._memory.log_decision(
            decision="self_improvement_patterns",
            reason=f"repeated_patterns={len(analysis.get('repeated_patterns', []))}",
            context={
                "goal": goal,
                "failure_causes": analysis.get("failure_causes", []),
                "repeated_patterns": analysis.get("repeated_patterns", []),
            },
        )

        self._memory.log_decision(
            decision="self_improvement_insights",
            reason=f"insights={len(insights)} suggestions={len(suggestions)}",
            context={
                "goal": goal,
                "insights": insights,
                "suggestions": suggestions,
            },
        )