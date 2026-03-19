"""Typed models for deterministic deployment planning."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def _canonicalize(value: Any) -> Any:
    """Return a deterministic representation for nested dictionaries/lists."""
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


@dataclass(frozen=True)
class DeploymentStep:
    """A single deterministic deployment action in the simulation plan."""

    index: int
    step_id: str
    action: str
    target: str
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.index <= 0:
            raise ValueError("index must be greater than 0")
        if not self.step_id:
            raise ValueError("step_id must be provided")
        if not self.action:
            raise ValueError("action must be provided")
        if not self.target:
            raise ValueError("target must be provided")
        object.__setattr__(self, "parameters", _canonicalize(dict(self.parameters)))
        object.__setattr__(self, "metadata", _canonicalize(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the step to a deterministic dictionary."""
        return {
            "index": self.index,
            "step_id": self.step_id,
            "action": self.action,
            "target": self.target,
            "parameters": _canonicalize(self.parameters),
            "metadata": _canonicalize(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentPlan:
    """Deterministic deployment plan generated from a deployment context."""

    execution_id: str
    environment: str
    steps: list[DeploymentStep]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("execution_id must be provided")
        if not self.environment:
            raise ValueError("environment must be provided")
        if not self.steps:
            raise ValueError("steps must contain at least one deployment step")
        if any(not isinstance(step, DeploymentStep) for step in self.steps):
            raise TypeError("steps must contain DeploymentStep instances")

        ordered_steps = sorted(self.steps, key=lambda step: step.index)
        object.__setattr__(self, "steps", ordered_steps)
        object.__setattr__(self, "metadata", _canonicalize(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the plan to a deterministic dictionary."""
        return {
            "execution_id": self.execution_id,
            "environment": self.environment,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": _canonicalize(self.metadata),
        }

    def to_json(self) -> str:
        """Serialize the plan to a stable JSON payload."""
        return json.dumps(self.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# Agent 26 — provider-based deployment request / result contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeploymentRequest:
    """Input contract for a provider-based deployment run."""

    plan_id: str
    steps: list[dict]
    environment: str
    dry_run: bool = True

    def __post_init__(self) -> None:
        if not self.plan_id:
            raise ValueError("plan_id must be provided")
        if not self.environment:
            raise ValueError("environment must be provided")


@dataclass(frozen=True)
class DeploymentResult:
    """Structured result produced by a provider-based deployment run."""

    success: bool
    executed_steps: list[dict]
    errors: list[str]
