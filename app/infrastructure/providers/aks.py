"""AKS deployment simulation provider (stub-only, no SDK usage)."""

from __future__ import annotations

from app.core.logger import get_logger
from app.infrastructure.base import InfrastructureContext, InfrastructureProvider, InfrastructureResult

_logger = get_logger(__name__)


class AKSInfrastructureProvider(InfrastructureProvider):
    """Simulates AKS lifecycle operations deterministically."""

    _PROVIDER_NAME = "aks"

    def deploy(self, context: InfrastructureContext) -> InfrastructureResult:
        _logger.info("infra.deploy.start", {
            "provider": self._PROVIDER_NAME,
            "environment": context.environment,
            "execution_id": context.execution_id,
        })
        result = InfrastructureResult(
            action="deploy",
            provider=self._PROVIDER_NAME,
            environment=context.environment,
            state="deployed",
            details={
                "cluster": f"aks-{context.execution_id}",
                "node_pool": "system",
                "services": tuple(context.services),
                "simulation": True,
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
            details={"cluster": f"aks-{context.execution_id}", "simulation": True},
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
            state="ready",
            details={"cluster": f"aks-{context.execution_id}", "simulation": True},
        )
        _logger.info("infra.status.result", {
            "provider": self._PROVIDER_NAME,
            "state": result.state,
            "environment": result.environment,
        })
        return result
