"""Data models for Agent 14/15 self-improvement system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ImprovementType(str, Enum):
    """Controlled vocabulary for improvement action types."""

    ADJUST_POLICY = "adjust_policy"
    CHANGE_STRATEGY = "change_strategy"
    INCREASE_CONFIDENCE = "increase_confidence"


# ---------------------------------------------------------------------------
# Agent 14 models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvaluationResult:
    """Deterministic summary of execution history quality signals."""

    success_rate: float
    avg_latency: float
    failure_patterns: list[str] = field(default_factory=list)
    retry_patterns: list[str] = field(default_factory=list)
    policy_violations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImprovementAction:
    """Improvement proposal produced from evaluated history."""

    type: ImprovementType
    target: str
    value: Any
    confidence: float


@dataclass(frozen=True)
class OptimizationReport:
    """Optimization result including generated and approved actions."""

    generated: list[ImprovementAction] = field(default_factory=list)
    approved: list[ImprovementAction] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent 15 models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionRecord:
    """Normalized view of a single execution extracted from memory."""

    record_id: str
    status: str
    latency: float
    failed_tasks: int
    total_tasks: int
    errors: list[str] = field(default_factory=list)
    timestamp: datetime | None = None

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 1.0
        return round((self.total_tasks - self.failed_tasks) / self.total_tasks, 4)


@dataclass(frozen=True)
class FailureRecord:
    """Normalized failure signal extracted from a memory failure entry."""

    record_id: str
    error: str
    source: str
    timestamp: datetime | None = None


@dataclass(frozen=True)
class Pattern:
    """Detected recurring signal across execution history."""

    pattern_id: str
    kind: str          # "repeated_failure" | "high_latency" | "low_success_rate"
    description: str
    signal_value: Any
    occurrence_count: int
    confidence: float


@dataclass(frozen=True)
class SelfImprovementAdaptation:
    """Candidate adaptation generated from a detected pattern."""

    adaptation_id: str
    source_pattern_id: str
    description: str
    expected_effect: str
    action_type: ImprovementType
    target: str
    value: Any
    confidence_score: float


@dataclass
class AdaptationResult:
    """Result of the full Agent 15 self-improvement loop run."""

    patterns_detected: list[Pattern] = field(default_factory=list)
    adaptations_generated: list[SelfImprovementAdaptation] = field(default_factory=list)
    adaptations_approved: list[SelfImprovementAdaptation] = field(default_factory=list)
    adaptations_rejected: list[SelfImprovementAdaptation] = field(default_factory=list)
