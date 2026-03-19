"""Registry for adaptation types and their policies."""

from __future__ import annotations

from app.adaptation.models import Adaptation
from app.adaptation.policies import (
    AdaptationPolicy,
    PreferredToolPolicy,
    RetryLimitPolicy,
    TimeoutPolicy,
)


class AdaptationRegistry:
    """Central mapping of adaptation type to policy implementation."""

    def __init__(self) -> None:
        self._policies: dict[str, AdaptationPolicy] = {}

    def register(self, adaptation_type: str, policy: AdaptationPolicy) -> None:
        if not isinstance(adaptation_type, str) or not adaptation_type.strip():
            raise ValueError("adaptation_type must be a non-empty string")
        if adaptation_type in self._policies:
            raise ValueError(f"policy already registered for adaptation type: {adaptation_type}")
        self._policies[adaptation_type] = policy

    def get(self, adaptation_type: str) -> AdaptationPolicy:
        return self._policies[adaptation_type]

    def has(self, adaptation_type: str) -> bool:
        return adaptation_type in self._policies

    def list_types(self) -> list[str]:
        return sorted(self._policies.keys())


def create_default_registry() -> AdaptationRegistry:
    registry = AdaptationRegistry()
    registry.register("retry_limit", RetryLimitPolicy())
    registry.register("timeout_seconds", TimeoutPolicy())
    registry.register("preferred_tool", PreferredToolPolicy())
    return registry
