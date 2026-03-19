"""Data models for Agent 11 observability and analysis outputs."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionTraceSummary:
    """Aggregated execution trace metrics extracted from observed logs."""

    total_events: int
    successful_events: int
    failed_events: int
    retry_events: int
    average_duration_ms: float


@dataclass(frozen=True)
class FailurePattern:
    """Repeated failure signature detected from logs and memory."""

    pattern_id: str
    source: str
    signature: str
    count: int


@dataclass(frozen=True)
class Recommendation:
    """Prioritized recommendation emitted by the analysis engine."""

    recommendation_id: str
    priority: int
    title: str
    action: str
    rationale: str


@dataclass(frozen=True)
class AnalysisReport:
    """Top-level analysis output contract for one execution ID."""

    execution_id: str
    success_rate: float
    failure_patterns: list[FailurePattern] = field(default_factory=list)
    inefficiencies: list[str] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    confidence_score: float = 0.0
    trace_summary: ExecutionTraceSummary = field(
        default_factory=lambda: ExecutionTraceSummary(
            total_events=0,
            successful_events=0,
            failed_events=0,
            retry_events=0,
            average_duration_ms=0.0,
        )
    )
