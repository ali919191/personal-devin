"""Adaptation policy primitives and built-in policy implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.adaptation.models import Adaptation


class AdaptationPolicy:
    """Base policy contract for adaptation validation and application."""

    def validate(self, adaptation: Adaptation) -> bool:
        raise NotImplementedError

    def apply(self, adaptation: Adaptation, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class NumericBounds:
    minimum: int
    maximum: int


class RetryLimitPolicy(AdaptationPolicy):
    """Controls retry_limit modifier updates with strict integer bounds."""

    def __init__(self, bounds: NumericBounds | None = None) -> None:
        self._bounds = bounds or NumericBounds(minimum=1, maximum=5)

    def validate(self, adaptation: Adaptation) -> bool:
        if adaptation.type != "retry_limit":
            return False
        if not isinstance(adaptation.payload, dict):
            return False
        value = adaptation.payload.get("retry_limit")
        if not isinstance(value, int):
            return False
        if value < self._bounds.minimum or value > self._bounds.maximum:
            return False
        return 0.0 <= adaptation.confidence <= 1.0

    def apply(self, adaptation: Adaptation, context: dict[str, Any]) -> dict[str, Any]:
        _ = context
        return {"retry_limit": adaptation.payload["retry_limit"]}


class TimeoutPolicy(AdaptationPolicy):
    """Controls timeout_seconds modifier updates with strict integer bounds."""

    def __init__(self, bounds: NumericBounds | None = None) -> None:
        self._bounds = bounds or NumericBounds(minimum=1, maximum=120)

    def validate(self, adaptation: Adaptation) -> bool:
        if adaptation.type != "timeout_seconds":
            return False
        if not isinstance(adaptation.payload, dict):
            return False
        value = adaptation.payload.get("timeout")
        if not isinstance(value, int):
            return False
        if value < self._bounds.minimum or value > self._bounds.maximum:
            return False
        return 0.0 <= adaptation.confidence <= 1.0

    def apply(self, adaptation: Adaptation, context: dict[str, Any]) -> dict[str, Any]:
        _ = context
        return {"timeout": adaptation.payload["timeout"]}


class PreferredToolPolicy(AdaptationPolicy):
    """Controls preferred_tool modifier updates to known, allowed tool values."""

    def __init__(self, allowed_tools: set[str] | None = None) -> None:
        self._allowed_tools = allowed_tools or {"api", "filesystem"}

    def validate(self, adaptation: Adaptation) -> bool:
        if adaptation.type != "preferred_tool":
            return False
        if not isinstance(adaptation.payload, dict):
            return False
        value = adaptation.payload.get("preferred_tool")
        if not isinstance(value, str) or value not in self._allowed_tools:
            return False
        return 0.0 <= adaptation.confidence <= 1.0

    def apply(self, adaptation: Adaptation, context: dict[str, Any]) -> dict[str, Any]:
        _ = context
        return {"preferred_tool": adaptation.payload["preferred_tool"]}
