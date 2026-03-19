"""Deterministic mock infrastructure provider for unit tests."""

from __future__ import annotations

from app.infrastructure.base import ContextInput, InfrastructureProvider, InfrastructureResult


class MockInfrastructureProvider(InfrastructureProvider):
    """Returns static responses regardless of context input."""

    _PROVIDER_NAME = "mock"

    def deploy(self, context: ContextInput) -> InfrastructureResult:
        _ = context
        return InfrastructureResult(
            action="deploy",
            provider=self._PROVIDER_NAME,
            environment="mock",
            state="deployed",
            details={"id": "mock-deploy-001", "stable": True},
        )

    def destroy(self, context: ContextInput) -> InfrastructureResult:
        _ = context
        return InfrastructureResult(
            action="destroy",
            provider=self._PROVIDER_NAME,
            environment="mock",
            state="destroyed",
            details={"id": "mock-destroy-001", "stable": True},
        )

    def status(self, context: ContextInput) -> InfrastructureResult:
        _ = context
        return InfrastructureResult(
            action="status",
            provider=self._PROVIDER_NAME,
            environment="mock",
            state="healthy",
            details={"id": "mock-status-001", "stable": True},
        )
