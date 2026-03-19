"""Registry for pluggable integration providers."""

from __future__ import annotations

from app.integrations.base import BaseIntegration
from app.integrations.exceptions import IntegrationNotFoundError


class IntegrationRegistry:
    """Registers and resolves integration providers by name."""

    def __init__(self) -> None:
        self._integrations: dict[str, BaseIntegration] = {}

    def register(self, integration: BaseIntegration) -> None:
        name = getattr(integration, "name", "")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("integration.name must be a non-empty string")
        if name in self._integrations:
            raise ValueError(f"integration already registered: {name}")
        self._integrations[name] = integration

    def get(self, name: str) -> BaseIntegration:
        try:
            return self._integrations[name]
        except KeyError as exc:
            raise IntegrationNotFoundError(f"integration not found: {name}") from exc

    def list(self) -> list[str]:
        return sorted(self._integrations.keys())
