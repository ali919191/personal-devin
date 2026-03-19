"""Data models for Agent 12 adaptive execution layer."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Adaptation:
    """Policy-driven adaptation derived from improvement output."""

    id: str
    source: str
    type: str
    payload: dict = field(default_factory=dict)
    confidence: float = 0.0
