"""Deterministic local infrastructure simulation provider."""

from __future__ import annotations

from app.core.logger import get_logger
from app.infrastructure.base import InfrastructureContext, InfrastructureProvider, InfrastructureResult

_logger = get_logger(__name__)


class LocalInfrastructureProvider(InfrastructureProvider):
    """Simulates local deployments with deterministic output."""

    _PROVIDER_NAME = "local"

    def deploy(self, context: InfrastructureContext) -> InfrastructureResult:
        _logger.info("infra.deploy.start", {
            "provider": self._PROVIDER_NAME,
            "environment": context.environment,
            "execution_id": context.execution_id,
        })
        services = tuple(context.services)
        result = InfrastructureResult(
            action="deploy",
            provider=self._PROVIDER_NAME,
            environment=context.environment,
            state="deployed",
            details={
                "mode": "local-simulation",
                "services": services,
                "service_count": len(services),
            },
        )
        _logger.info("infra.deploy.result", {
            "provider": self._PROVIDER_NAME,
            "state": result.state,
            "environment": result.environment,
        })
        return result

    def destroy(self, context: InfrastructureContext) -> InfrastructureResult:
        _logger.info("infra.destroy.start", {
            "provider": self._PROVIDER_NAME,
            "environment": context.environment,
            "execution_id": context.execution_id,
        })
        result = InfrastructureResult(
            action="destroy",
            provider=self._PROVIDER_NAME,
            environment=context.environment,
            state="destroyed",
            details={"mode": "local-simulation", "cleanup": "complete"},
        )
        _logger.info("infra.destroy.result", {
            "provider": self._PROVIDER_NAME,
            "state": result.state,
            "environment": result.environment,
        })
        return result

    def status(self, context: InfrastructureContext) -> InfrastructureResult:
        _logger.info("infra.status.start", {
            "provider": self._PROVIDER_NAME,
            "environment": context.environment,
            "execution_id": context.execution_id,
        })
        result = InfrastructureResult(
            action="status",
            provider=self._PROVIDER_NAME,
            environment=context.environment,
            state="healthy",
            details={"mode": "local-simulation", "ready": True},
        )
        _logger.info("infra.status.result", {
            "provider": self._PROVIDER_NAME,
            "state": result.state,
            "environment": result.environment,
        })
        return result
