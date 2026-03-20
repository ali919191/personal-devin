from __future__ import annotations

from app.improvement.models import AnalysisSummary, Pattern


class PatternDetector:
    """Derive deterministic patterns from analysis aggregates."""

    def detect(self, summary: AnalysisSummary) -> list[Pattern]:
        if summary.total_executions <= 0:
            return []

        patterns: list[Pattern] = []

        for step_id in summary.common_failure_points:
            failures = summary.common_failure_counts.get(step_id, 0)
            frequency = round(failures / summary.total_executions, 4)
            if frequency >= 0.5:
                severity = "high"
            elif frequency >= 0.25:
                severity = "medium"
            else:
                severity = "low"

            if frequency >= 0.25:
                patterns.append(
                    Pattern(
                        type="repeated_failure",
                        location=f"execution.{step_id}",
                        frequency=frequency,
                        severity=severity,
                        evidence_count=failures,
                    )
                )

        for step_id in sorted(summary.retry_patterns.keys()):
            retries = summary.retry_patterns[step_id]
            frequency = round(retries / summary.total_executions, 4)
            if frequency >= 0.3:
                patterns.append(
                    Pattern(
                        type="redundant_retries",
                        location=f"execution.{step_id}",
                        frequency=frequency,
                        severity="medium" if frequency < 0.6 else "high",
                        evidence_count=retries,
                    )
                )

        for error_type in sorted(summary.tool_misuse_patterns.keys()):
            count = summary.tool_misuse_patterns[error_type]
            frequency = round(count / summary.total_executions, 4)
            if count > 0:
                patterns.append(
                    Pattern(
                        type="tool_misuse",
                        location=f"execution.{error_type}",
                        frequency=frequency,
                        severity="high",
                        evidence_count=count,
                    )
                )

        for step_id in sorted(summary.step_latency.keys()):
            latency = summary.step_latency[step_id]
            if latency >= 1000.0:
                patterns.append(
                    Pattern(
                        type="inefficient_plan",
                        location=f"execution.{step_id}",
                        frequency=1.0,
                        severity="medium" if latency < 2000.0 else "high",
                        evidence_count=int(latency),
                    )
                )

        patterns.sort(key=lambda p: (p.type, p.location, p.frequency, p.severity, p.evidence_count))
        return patterns
