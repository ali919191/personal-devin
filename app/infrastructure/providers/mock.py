"""Deterministic mock infrastructure provider for unit tests."""

from __future__ import annotations

from app.core.logger import get_logger
from app.infrastructure.base import InfrastructureContext, InfrastructureProvider, InfrastructureResult

_logger = get_logger(__name__)


class MockInfrastructureProvider(InfrastructureProvider):
    """Returns static responses regardless of context input."""

    _PROVIDER_NAME = "mock"

    def deploy(self, context: InfrastructureContext) -> InfrastructureResult:
        _logger.info("infra.deploy.start", {
            "provider": self._PROVIDER_NAME,
            "environment": context.environment,
            "execution_id": context.execution_id,
        })
        result = InfrastructureResult(
            action="deploy",
            provider=self._PROVIDER_NAME,
            environment="mock",
            state="deployed",
            details={"id": "mock-deploy-001", "stable": True},
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
            environment="mock",
            state="destroyed",
            details={"id": "mock-destroy-001", "stable": True},
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
            environment="mock",
            state="healthy",
            details={"id": "mock-status-001", "stable": True},
        )
        _logger.info("infra.status.result", {
            "provider": self._PROVIDER_NAME,
            "state": result.state,
            "environment": result.environment,
        })
        return result
