"""Policy definitions for deterministic adaptation conflict resolution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    """Policy metadata used by the conflict resolver."""

    name: str
    priority: int
    confidence_threshold: float | None = None


def default_policies() -> dict[str, Policy]:
    """Return deterministic default policy ranking and thresholds."""
    return {
        "safety": Policy(name="safety", priority=100, confidence_threshold=0.7),
        "reliability": Policy(name="reliability", priority=80, confidence_threshold=0.6),
        "performance": Policy(name="performance", priority=50, confidence_threshold=0.5),
        "preference": Policy(name="preference", priority=20, confidence_threshold=None),
    }
