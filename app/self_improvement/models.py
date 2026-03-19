"""Data models for Agent 14 self-improvement system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ImprovementType(str, Enum):
    """Controlled vocabulary for improvement action types."""

    ADJUST_POLICY = "adjust_policy"
    CHANGE_STRATEGY = "change_strategy"
    INCREASE_CONFIDENCE = "increase_confidence"


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
