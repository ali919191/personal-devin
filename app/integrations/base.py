"""Base abstractions for pluggable integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.integrations.models import IntegrationRequest, IntegrationResponse


class BaseIntegration(ABC):
    """Abstract provider contract for deterministic integrations."""

    name: str

    def validate_config(self, config: dict) -> None:
        """Validate provider configuration before use.

        Override in subclasses to enforce provider-specific config constraints.
        The default implementation is a no-op (all configs accepted).
        Raise ValueError with a descriptive message on validation failure.
        """

    @abstractmethod
    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute a deterministic integration request."""
