from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ImprovementMetrics:
    """Standardized metrics schema for deterministic impact measurement."""
    success_rate: float
    failure_rate: float
    avg_step_latency: float
    retry_rate: float


@dataclass(frozen=True)
class RollbackAction:
    """Stores previous state for rollback if improvement degrades system."""
    target: str
    previous_value: str
    version: int


@dataclass(frozen=True)
class SignalRecord:
    signal_type: str
    signal_value: str


@dataclass(frozen=True)
class AnalysisSummary:
    total_executions: int
    failure_rate: float
    retry_patterns: dict[str, int]
    step_latency: dict[str, float]
    common_failure_points: list[str]
    common_failure_counts: dict[str, int]
    tool_misuse_patterns: dict[str, int]


@dataclass(frozen=True)
class Pattern:
    type: str
    location: str
    frequency: float
    severity: str
    evidence_count: int = 0


@dataclass
class ImprovementAction:
    target: str = ""
    change: str = ""
    reason: str = ""
    action_type: str = ""
    source_signal: str = ""

    def __post_init__(self) -> None:
        if not self.action_type and self.change:
            self.action_type = self.change
        if not self.change and self.action_type:
            self.change = self.action_type


@dataclass(frozen=True)
class ImprovementRecord:
    id: str
    timestamp: datetime
    patterns: list[Pattern]
    actions: list[ImprovementAction]
    result: str
    version: int
    rollback_actions: list[RollbackAction] = field(default_factory=list)
    metrics_before: ImprovementMetrics | None = None
    metrics_after: ImprovementMetrics | None = None
    impact_score: float = 0.0
    accepted: bool = False


@dataclass(frozen=True)
class ImprovementPlan:
    version: str
    analysis: AnalysisSummary
    patterns: list[Pattern]
    actions: list[ImprovementAction]
    rejected_actions: list[ImprovementAction] = field(default_factory=list)
    record: ImprovementRecord | None = None


@dataclass
class ImprovementResult:
    action_type: str
    status: str
    target: str = ""
    change: str = ""
    reason: str = ""
    success: bool | None = None
    impact_score: float = 0.0
    metrics_before: ImprovementMetrics | None = None
    metrics_after: ImprovementMetrics | None = None
    rollback_applied: bool = False
