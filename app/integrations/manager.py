"""Orchestration layer for deterministic integration execution."""

from __future__ import annotations

from time import perf_counter

from app.core.logger import get_logger
from app.integrations.exceptions import IntegrationError, IntegrationExecutionError
from app.integrations.models import IntegrationRequest, IntegrationResponse
from app.integrations.registry import IntegrationRegistry


class IntegrationManager:
    """Resolve providers, log lifecycle events, and return structured responses."""

    def __init__(self, registry: IntegrationRegistry) -> None:
        self._registry = registry
        self._logger = get_logger("app.integrations.manager")

    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        started_at = perf_counter()
        self._logger.info(
            "integration_request",
            data={
                "request_id": request.id,
                "integration": request.integration,
                "payload": request.payload,
                "metadata": request.metadata,
                "timestamp": request.timestamp.isoformat(),
            },
        )

        try:
            integration = self._registry.get(request.integration)
            self._logger.debug(
                "integration_resolved",
                data={"request_id": request.id, "integration": request.integration},
            )
            response = integration.execute(request)
        except Exception as exc:
            duration_seconds = perf_counter() - started_at
            self._logger.error(
                "integration_error",
                error=str(exc),
                data={
                    "request_id": request.id,
                    "integration": request.integration,
                    "success": False,
                    "duration_seconds": duration_seconds,
                },
            )
            if isinstance(exc, IntegrationError):
                raise
            raise IntegrationExecutionError(str(exc)) from exc

        duration_seconds = perf_counter() - started_at
        self._logger.info(
            "integration_response",
            data={
                "request_id": response.id,
                "integration": response.integration,
                "payload": response.payload,
                "metadata": response.metadata,
                "timestamp": response.timestamp.isoformat(),
                "success": True,
                "duration_seconds": duration_seconds,
            },
        )
        return response
