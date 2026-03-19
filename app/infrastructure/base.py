"""Infrastructure provider contracts for the execution layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol, runtime_checkable


@runtime_checkable
class InfrastructureContext(Protocol):
    """Strict context contract required by all infrastructure providers.

    Agent 27 extension
    ------------------
    ``region``, ``provider_type``, and ``credentials_ref`` are added so the
    environment adapter can pass structured targeting information through the
    provider boundary without embedding raw secret values.
    """

    environment: str
    execution_id: str
    services: list[str]

    # Agent 27 — environment adapter fields
    region: str
    provider_type: str
    credentials_ref: str


@dataclass(frozen=True)
class DefaultInfrastructureContext:
    """Fallback context for plans that do not supply an explicit infrastructure context."""

    environment: str = "local"
    execution_id: str = "default"
    services: list[str] = field(default_factory=list)

    # Agent 27 — environment adapter fields
    region: str = "local"
    provider_type: str = "local"
    credentials_ref: str = ""


@dataclass(frozen=True)
class InfrastructureResult:
    """Deterministic provider response contract."""

    action: Literal["deploy", "destroy", "status"]
    provider: str
    environment: str
    state: Literal["deployed", "destroyed", "healthy", "ready", "failed", "pending"]
    details: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None


class InfrastructureProvider(ABC):
    """Abstract provider interface consumed by the execution layer."""

    @abstractmethod
    def deploy(self, context: InfrastructureContext) -> InfrastructureResult:
        """Deploy infrastructure for the supplied context."""

    @abstractmethod
    def destroy(self, context: InfrastructureContext) -> InfrastructureResult:
        """Destroy infrastructure for the supplied context."""

    @abstractmethod
    def status(self, context: InfrastructureContext) -> InfrastructureResult:
        """Return infrastructure status for the supplied context."""
