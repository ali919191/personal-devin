"""Deterministic self-improvement engine for post-run analysis."""

from __future__ import annotations

from typing import Any

from app.core.logger import get_logger
from app.memory.service import MemoryService

logger = get_logger(__name__)

CONFIDENCE_BY_TYPE = {
    "failure_pattern": 0.9,
    "structure_signal": 0.8,
    "efficiency_signal": 0.75,
    "warning": 0.7,
    "optimization": 0.6,
}


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
                "failure_classification": [],
                "inefficiencies": ["missing_run_data"],
                "repeated_patterns": [],
                "structural_metrics": {
                    "depth": 0,
                    "width": 0,
                    "branching_factor": 0.0,
                    "dependency_chains": 0,
                },
                "execution_metrics": {
                    "parallelism_potential": 0,
                    "actual_parallelism": 0,
                    "parallelism_utilization": 0.0,
                    "completion_efficiency": 0.0,
                    "skip_propagation_depth": 0,
                },
                "structure_signals": [],
                "efficiency_signals": [],
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

        normalized_run_data = self._normalize_run_data(run_data)

        status = normalized_run_data["status"]
        metrics = normalized_run_data["metrics"]
        tasks = normalized_run_data["tasks"]

        total_tasks = int(metrics["total"])
        completed_tasks = int(metrics["completed"])
        failed_tasks = int(metrics["failed"])
        skipped_tasks = int(metrics["skipped"])

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
        failure_classification = self._classify_failures(tasks)
        inefficiencies = self._detect_inefficiencies(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            skipped_tasks=skipped_tasks,
            tasks=tasks,
        )
        repeated_patterns = self._detect_repeated_patterns(
            failure_causes=failure_causes,
            tasks=tasks,
            inefficiencies=inefficiencies,
        )
        structural_metrics = self._compute_structural_metrics(tasks)
        execution_metrics = self._compute_execution_metrics(
            tasks=tasks,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            skipped_tasks=skipped_tasks,
            structural_metrics=structural_metrics,
            run_data=normalized_run_data,
        )
        structure_signals = self._derive_structure_signals(structural_metrics)
        efficiency_signals = self._derive_efficiency_signals(
            structural_metrics=structural_metrics,
            execution_metrics=execution_metrics,
            status=status,
        )

        success_rate = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        analysis = {
            "classification": status,
            "failure_causes": failure_causes,
            "failure_classification": failure_classification,
            "inefficiencies": inefficiencies,
            "repeated_patterns": repeated_patterns,
            "structural_metrics": structural_metrics,
            "execution_metrics": execution_metrics,
            "structure_signals": structure_signals,
            "efficiency_signals": efficiency_signals,
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
        structure_signals = list(analysis.get("structure_signals", []))
        efficiency_signals = list(analysis.get("efficiency_signals", []))

        insights: list[dict[str, Any]] = []

        for error in sorted(failure_causes):
            insights.append(
                {
                    "type": "failure_pattern",
                    "message": f"Observed failure cause: {error}",
                    "confidence": CONFIDENCE_BY_TYPE["failure_pattern"],
                    "metadata": {"error": error},
                }
            )

        for pattern in sorted(
            repeated_patterns,
            key=lambda item: (
                str(item.get("kind", "")),
                str(item.get("value", "")),
                int(item.get("count", 0)),
            ),
        ):
            insights.append(
                {
                    "type": "warning",
                    "message": (
                        f"Repeated {pattern.get('kind', 'pattern')} detected: "
                        f"{pattern.get('value', 'unknown')}"
                    ),
                    "confidence": CONFIDENCE_BY_TYPE["warning"],
                    "metadata": pattern,
                }
            )

        for signal in sorted(structure_signals):
            insights.append(
                {
                    "type": "structure_signal",
                    "message": signal,
                    "confidence": CONFIDENCE_BY_TYPE["structure_signal"],
                    "metadata": {"signal": signal},
                }
            )

        for signal in sorted(efficiency_signals):
            insights.append(
                {
                    "type": "efficiency_signal",
                    "message": signal,
                    "confidence": CONFIDENCE_BY_TYPE["efficiency_signal"],
                    "metadata": {"signal": signal},
                }
            )

        for inefficiency in sorted(inefficiencies):
            insights.append(
                {
                    "type": "optimization",
                    "message": f"Optimization opportunity: {inefficiency}",
                    "confidence": CONFIDENCE_BY_TYPE["optimization"],
                    "metadata": {"inefficiency": inefficiency},
                }
            )

        if not insights:
            insights.append(
                {
                    "type": "optimization",
                    "message": "Run is stable with no immediate optimization flags",
                    "confidence": CONFIDENCE_BY_TYPE["optimization"],
                    "metadata": {"classification": classification},
                }
            )

        ordered_insights = self._order_insights(insights)
        logger.info("self_improvement_insights_generated", {"count": len(ordered_insights)})
        return ordered_insights

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
                        "rationale": f"Derived from insight: {message}",
                    }
                )
            elif insight_type == "structure_signal":
                suggestions.append(
                    {
                        "priority": "medium",
                        "suggestion": "Adjust decomposition to balance dependency depth and expand safe parallel branches",
                        "target": "planning",
                        "rationale": f"Derived from insight: {message}",
                    }
                )
            elif insight_type == "efficiency_signal":
                suggestions.append(
                    {
                        "priority": "medium",
                        "suggestion": "Align execution strategy with available parallelism to improve throughput",
                        "target": "execution",
                        "rationale": f"Derived from insight: {message}",
                    }
                )
            elif insight_type == "optimization":
                suggestions.append(
                    {
                        "priority": "medium",
                        "suggestion": "Refine task decomposition and execution grouping to reduce inefficiencies",
                        "target": "planning",
                        "rationale": f"Derived from insight: {message}",
                    }
                )
            else:
                suggestions.append(
                    {
                        "priority": "medium",
                        "suggestion": "Track repeated warnings in memory and escalate when threshold is exceeded",
                        "target": "memory",
                        "rationale": f"Derived from insight: {message}",
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

        ordered_suggestions = self._order_suggestions(suggestions)
        logger.info("self_improvement_suggestions_generated", {"count": len(ordered_suggestions)})
        return ordered_suggestions

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
        tasks: list[dict[str, Any]],
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

        if self._has_repeated_retries(tasks):
            inefficiencies.append("repeated_task_retries")

        return sorted(inefficiencies)

    def _has_repeated_retries(self, tasks: list[dict[str, Any]]) -> bool:
        for task in tasks:
            retry_count = task.get("retry_count")
            retries = task.get("retries")

            if isinstance(retry_count, int) and retry_count > 1:
                return True
            if isinstance(retries, int) and retries > 1:
                return True
        return False

    def _detect_repeated_patterns(
        self,
        failure_causes: list[str],
        tasks: list[dict[str, Any]],
        inefficiencies: list[str],
    ) -> list[dict[str, Any]]:
        historical_patterns = self._normalize_historical_patterns(self._memory.get_patterns())
        repeated: list[dict[str, Any]] = []

        current = set(failure_causes)
        for error, count in sorted(historical_patterns.items(), key=lambda item: (item[0], item[1])):
            if error in current and count > 1:
                repeated.append(
                    {
                        "kind": "failure_type",
                        "value": error,
                        "count": count,
                    }
                )

        task_error_counter: dict[str, int] = {}
        for task in tasks:
            error = task.get("error") or task.get("skip_reason")
            if error:
                key = str(error)
                task_error_counter[key] = task_error_counter.get(key, 0) + 1

        for error, count in sorted(task_error_counter.items(), key=lambda item: (item[0], item[1])):
            if count >= 2:
                repeated.append(
                    {
                        "kind": "task_error",
                        "value": error,
                        "count": count,
                    }
                )

        inefficiency_counter: dict[str, int] = {}
        for inefficiency in inefficiencies:
            inefficiency_counter[inefficiency] = inefficiency_counter.get(inefficiency, 0) + 1

        for inefficiency, count in sorted(
            inefficiency_counter.items(), key=lambda item: (item[0], item[1])
        ):
            if count >= 1:
                repeated.append(
                    {
                        "kind": "inefficiency_signal",
                        "value": inefficiency,
                        "count": count,
                    }
                )

        return sorted(
            repeated,
            key=lambda item: (
                str(item.get("kind", "")),
                str(item.get("value", "")),
                int(item.get("count", 0)),
            ),
        )

    def _normalize_historical_patterns(self, patterns: Any) -> dict[str, int]:
        if not isinstance(patterns, list):
            return {}

        # Use unique normalized error signals and a non-additive max count to avoid
        # inflating frequency when append-only memory yields duplicate pattern entries.
        normalized: dict[str, int] = {}
        for item in patterns:
            if not isinstance(item, dict):
                continue

            error = str(item.get("error", "unknown")).strip() or "unknown"
            raw_count = item.get("count", 0)
            count = raw_count if isinstance(raw_count, int) and raw_count >= 0 else 0

            existing = normalized.get(error, 0)
            if count > existing:
                normalized[error] = count

        return normalized

    def _classify_failures(self, tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
        categories: list[dict[str, str]] = []
        for task in tasks:
            status = str(task.get("status", ""))
            if status not in {"failed", "skipped"}:
                continue

            error = str(task.get("error") or "")
            skip_reason = str(task.get("skip_reason") or "")
            if skip_reason.startswith("dependency_failed:") or error.startswith("dependency_failed:"):
                category = "dependency_failure"
            elif error and error != "None":
                category = "execution_error"
            else:
                category = "unknown_failure"

            categories.append(
                {
                    "task_id": str(task.get("id", "unknown")),
                    "category": category,
                }
            )

        return sorted(categories, key=lambda item: (item["category"], item["task_id"]))

    def _normalize_run_data(self, run_data: dict) -> dict[str, Any]:
        metrics = run_data.get("metrics", {}) if isinstance(run_data.get("metrics"), dict) else {}
        tasks = run_data.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []

        normalized_tasks: list[dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            normalized_tasks.append(
                {
                    "id": str(task.get("id", "unknown")),
                    "status": str(task.get("status", "unknown")),
                    "error": task.get("error"),
                    "skip_reason": task.get("skip_reason"),
                    "retry_count": task.get("retry_count"),
                    "retries": task.get("retries"),
                    "dependencies": self._normalize_dependencies(task.get("dependencies", [])),
                }
            )

        return {
            "goal": str(run_data.get("goal", "unknown")),
            "status": str(run_data.get("status", "unknown")),
            "metrics": {
                "total": int(metrics.get("total", len(normalized_tasks))),
                "completed": int(metrics.get("completed", 0)),
                "failed": int(metrics.get("failed", 0)),
                "skipped": int(metrics.get("skipped", 0)),
                "actual_parallelism": int(metrics.get("actual_parallelism", 1))
                if normalized_tasks
                else 0,
            },
            "tasks": normalized_tasks,
        }

    def _normalize_dependencies(self, dependencies: Any) -> list[str]:
        if not isinstance(dependencies, list):
            return []
        return sorted(str(dep) for dep in dependencies)

    def _compute_structural_metrics(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        if not tasks:
            return {
                "depth": 0,
                "width": 0,
                "branching_factor": 0.0,
                "dependency_chains": 0,
            }

        task_map = {str(task.get("id", "unknown")): task for task in tasks}
        children: dict[str, list[str]] = {task_id: [] for task_id in task_map}

        for task_id, task in task_map.items():
            for dep in task.get("dependencies", []):
                if dep in children:
                    children[dep].append(task_id)

        level_cache: dict[str, int] = {}

        def level(task_id: str, stack: set[str]) -> int:
            if task_id in level_cache:
                return level_cache[task_id]
            if task_id in stack:
                return 0

            stack.add(task_id)
            task = task_map[task_id]
            dep_levels = [
                level(dep, stack)
                for dep in task.get("dependencies", [])
                if isinstance(dep, str) and dep in task_map
            ]
            stack.remove(task_id)
            computed = (max(dep_levels) + 1) if dep_levels else 1
            level_cache[task_id] = computed
            return computed

        for task_id in sorted(task_map):
            level(task_id, set())

        levels = list(level_cache.values())
        depth = max(levels) if levels else 0
        width_counter: dict[int, int] = {}
        for current in levels:
            width_counter[current] = width_counter.get(current, 0) + 1
        width = max(width_counter.values()) if width_counter else 0

        out_degrees = [len(children[task_id]) for task_id in sorted(children)]
        branch_nodes = [degree for degree in out_degrees if degree > 0]
        if branch_nodes:
            branching_factor = sum(branch_nodes) / len(branch_nodes)
        else:
            branching_factor = 0.0

        roots = [
            task_id
            for task_id, task in sorted(task_map.items())
            if not [dep for dep in task.get("dependencies", []) if dep in task_map]
        ]
        leaves = [task_id for task_id, degree in sorted((k, len(v)) for k, v in children.items()) if degree == 0]

        dependency_chains = len(roots) * len(leaves) if roots and leaves else 0

        return {
            "depth": depth,
            "width": width,
            "branching_factor": round(branching_factor, 2),
            "dependency_chains": dependency_chains,
        }

    def _compute_execution_metrics(
        self,
        tasks: list[dict[str, Any]],
        total_tasks: int,
        completed_tasks: int,
        skipped_tasks: int,
        structural_metrics: dict[str, Any],
        run_data: dict[str, Any],
    ) -> dict[str, Any]:
        if total_tasks <= 0:
            return {
                "parallelism_potential": 0,
                "actual_parallelism": 0,
                "parallelism_utilization": 0.0,
                "completion_efficiency": 0.0,
                "skip_propagation_depth": 0,
            }

        potential = int(structural_metrics.get("width", 1))
        metrics = run_data.get("metrics", {}) if isinstance(run_data.get("metrics"), dict) else {}
        raw_actual = metrics.get("actual_parallelism", 1)
        actual_parallelism = raw_actual if isinstance(raw_actual, int) and raw_actual > 0 else 1
        if actual_parallelism > potential:
            actual_parallelism = potential

        completion_efficiency = completed_tasks / total_tasks
        parallelism_utilization = actual_parallelism / potential if potential > 0 else 0.0
        skip_propagation_depth = self._compute_skip_propagation_depth(tasks) if skipped_tasks > 0 else 0

        return {
            "parallelism_potential": potential,
            "actual_parallelism": actual_parallelism,
            "parallelism_utilization": round(parallelism_utilization, 2),
            "completion_efficiency": round(completion_efficiency, 2),
            "skip_propagation_depth": skip_propagation_depth,
        }

    def _compute_skip_propagation_depth(self, tasks: list[dict[str, Any]]) -> int:
        skipped_by_id: dict[str, str] = {}
        for task in tasks:
            status = str(task.get("status", ""))
            task_id = str(task.get("id", "unknown"))
            skip_reason = str(task.get("skip_reason") or "")
            if status == "skipped" and skip_reason.startswith("dependency_failed:"):
                skipped_by_id[task_id] = skip_reason.split(":", 1)[1]

        depth_cache: dict[str, int] = {}

        def depth(task_id: str, stack: set[str]) -> int:
            if task_id in depth_cache:
                return depth_cache[task_id]
            if task_id in stack:
                return 1

            parent = skipped_by_id.get(task_id)
            if not parent:
                depth_cache[task_id] = 1
                return 1

            stack.add(task_id)
            computed = 1 + depth(parent, stack)
            stack.remove(task_id)
            depth_cache[task_id] = computed
            return computed

        if not skipped_by_id:
            return 0

        return max(depth(task_id, set()) for task_id in sorted(skipped_by_id))

    def _derive_structure_signals(self, structural_metrics: dict[str, Any]) -> list[str]:
        depth = int(structural_metrics.get("depth", 0))
        width = int(structural_metrics.get("width", 0))
        branching_factor = float(structural_metrics.get("branching_factor", 0.0))
        dependency_chains = int(structural_metrics.get("dependency_chains", 0))

        if depth == 0:
            return []

        if width == 1:
            shape = "linear chain"
        elif branching_factor > 1.0:
            shape = "branched graph"
        else:
            shape = "layered graph"

        signals = [
            f"Graph depth = {depth} ({shape})",
            (
                f"Graph width = {width}; branching factor = {branching_factor:.2f}; "
                f"dependency chains = {dependency_chains}"
            ),
        ]

        if depth >= 4:
            signals.append("High dependency chain depth increases fragility")

        return sorted(signals)

    def _derive_efficiency_signals(
        self,
        structural_metrics: dict[str, Any],
        execution_metrics: dict[str, Any],
        status: str,
    ) -> list[str]:
        width = int(structural_metrics.get("width", 0))
        potential = int(execution_metrics.get("parallelism_potential", 0))
        actual = int(execution_metrics.get("actual_parallelism", 0))
        completion_efficiency = float(execution_metrics.get("completion_efficiency", 0.0))
        skip_propagation_depth = int(execution_metrics.get("skip_propagation_depth", 0))

        if potential == 0:
            return []

        if completion_efficiency >= 0.9:
            efficiency_label = "high"
        elif completion_efficiency >= 0.5:
            efficiency_label = "medium"
        else:
            efficiency_label = "low"

        signals = [
            f"Completion efficiency = {completion_efficiency:.2f} ({efficiency_label})",
        ]

        if potential > 1 and actual <= 1:
            signals.append("No parallel execution opportunities utilized")
            if width >= 3:
                signals.append("Wide graph executed sequentially")

        if status == "success" and completion_efficiency >= 0.9 and potential > 1 and actual <= 1:
            signals.append("Execution efficiency: high but non-parallel")

        if skip_propagation_depth > 0:
            signals.append(f"Skip propagation depth = {skip_propagation_depth}")

        return sorted(signals)

    def _order_insights(self, insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        type_order = {
            "failure_pattern": 0,
            "structure_signal": 1,
            "efficiency_signal": 2,
            "warning": 3,
            "optimization": 4,
        }
        return sorted(
            insights,
            key=lambda item: (
                type_order.get(str(item.get("type", "optimization")), 99),
                str(item.get("message", "")),
            ),
        )

    def _order_suggestions(self, suggestions: list[dict[str, str]]) -> list[dict[str, str]]:
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            suggestions,
            key=lambda item: (
                priority_order.get(str(item.get("priority", "low")), 99),
                str(item.get("target", "")),
                str(item.get("suggestion", "")),
            ),
        )

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
                "type": "self_improvement_summary",
                "goal": goal,
                "summary": analysis.get("summary", {}),
                "classification": analysis.get("classification", "unknown"),
            },
        )

        self._memory.log_decision(
            decision="self_improvement_patterns",
            reason=f"repeated_patterns={len(analysis.get('repeated_patterns', []))}",
            context={
                "type": "self_improvement_pattern",
                "goal": goal,
                "failure_causes": analysis.get("failure_causes", []),
                "failure_classification": analysis.get("failure_classification", []),
                "repeated_patterns": analysis.get("repeated_patterns", []),
            },
        )

        self._memory.log_decision(
            decision="self_improvement_insights",
            reason=f"insights={len(insights)} suggestions={len(suggestions)}",
            context={
                "type": "self_improvement_insight",
                "goal": goal,
                "insights": insights,
                "suggestions": suggestions,
            },
        )