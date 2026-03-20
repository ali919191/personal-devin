"""Data models for Agent 20 feedback loop engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class FeedbackSignal:
    """Structured feedback generated from execution + evaluation output."""

    execution_id: str
    score: float
    success: bool
    failure_type: str | None
    improvement_suggestions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class FeedbackBatch:
    """Container for deterministic ordered feedback signals."""

    signals: list[FeedbackSignal] = field(default_factory=list)