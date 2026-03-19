"""Infrastructure provider contracts for the execution layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol, runtime_checkable


@runtime_checkable
class InfrastructureContext(Protocol):
    """Minimal context contract expected by infrastructure providers."""

    environment: str


ContextInput = InfrastructureContext | Mapping[str, Any]


@dataclass(frozen=True)
class InfrastructureResult:
    """Deterministic provider response contract."""

    action: Literal["deploy", "destroy", "status"]
    provider: str
    environment: str
    state: str
    details: Mapping[str, Any] = field(default_factory=dict)


class InfrastructureProvider(ABC):
    """Abstract provider interface consumed by the execution layer."""

    @abstractmethod
    def deploy(self, context: ContextInput) -> InfrastructureResult:
        """Deploy infrastructure for the supplied context."""

    @abstractmethod
    def destroy(self, context: ContextInput) -> InfrastructureResult:
        """Destroy infrastructure for the supplied context."""

    @abstractmethod
    def status(self, context: ContextInput) -> InfrastructureResult:
        """Return infrastructure status for the supplied context."""
