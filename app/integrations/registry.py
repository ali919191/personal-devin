"""Integration registry for deterministic integration lookup and execution."""

from __future__ import annotations

from typing import Any

from app.core.logger import get_logger
from app.integrations.base import Integration

logger = get_logger(__name__)


class IntegrationRegistry:
    """Registry that manages named integration instances."""

    def __init__(self) -> None:
        self._integrations: dict[str, Integration] = {}

    def register(self, integration: Integration) -> None:
        """Register an integration by its unique name."""
        name = getattr(integration, "name", "")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("integration.name must be a non-empty string")

        normalized_name = name.strip()
        if normalized_name in self._integrations:
            raise ValueError(f"integration already registered: {normalized_name}")

        self._integrations[normalized_name] = integration
        logger.info("integration_registered", {"integration": normalized_name})

    def get(self, name: str) -> Integration:
        """Retrieve a previously registered integration by name."""
        if name not in self._integrations:
            available = sorted(self._integrations.keys())
            raise KeyError(
                f"integration not found: {name}. available integrations: {available}"
            )
        return self._integrations[name]

    def list(self) -> list[str]:
        """Return all registered integration names in deterministic order."""
        return sorted(self._integrations.keys())

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        """Execute integration request with standard input/output contracts.

        Input contract:
            {
              "integration": str,
              "action": str,
              "payload": dict,
            }
        """
        if not isinstance(request, dict):
            raise ValueError("request must be a dictionary")

        integration_name = request.get("integration")
        action = request.get("action")
        payload = request.get("payload", {})

        if not isinstance(integration_name, str) or not integration_name.strip():
            raise ValueError("request.integration must be a non-empty string")
        if not isinstance(action, str) or not action.strip():
            raise ValueError("request.action must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError("request.payload must be a dictionary")

        integration = self.get(integration_name)
        logger.info(
            "integration_execute_started",
            {"integration": integration_name, "action": action},
        )
        result = integration.execute(action=action, payload=payload)
        logger.info(
            "integration_execute_completed",
            {
                "integration": integration_name,
                "action": action,
                "status": result.get("status"),
            },
        )
        return result
