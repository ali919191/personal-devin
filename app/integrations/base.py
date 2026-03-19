"""Base abstractions for pluggable integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.integrations.models import IntegrationRequest, IntegrationResponse


class BaseIntegration(ABC):
    """Abstract provider contract for deterministic integrations."""

    name: str

    @abstractmethod
    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute a deterministic integration request."""
