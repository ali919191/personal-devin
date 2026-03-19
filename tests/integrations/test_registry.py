"""Tests for integration registry behavior."""

import pytest

from app.integrations.base import BaseIntegration
from app.integrations.exceptions import IntegrationNotFoundError
from app.integrations.models import IntegrationRequest, IntegrationResponse
from app.integrations.registry import IntegrationRegistry


class DummyIntegration(BaseIntegration):
    name = "dummy"

    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        return IntegrationResponse(
            id=request.id,
            integration=self.name,
            payload={"ok": True},
            metadata=request.metadata,
            timestamp=request.timestamp,
        )


def test_registry_registers_and_lists_integrations() -> None:
    registry = IntegrationRegistry()

    registry.register(DummyIntegration())

    assert registry.list() == ["dummy"]
    assert isinstance(registry.get("dummy"), DummyIntegration)


def test_registry_rejects_duplicate_names() -> None:
    registry = IntegrationRegistry()
    registry.register(DummyIntegration())

    with pytest.raises(ValueError, match="integration already registered"):
        registry.register(DummyIntegration())


def test_registry_raises_controlled_error_for_missing_integration() -> None:
    registry = IntegrationRegistry()

    with pytest.raises(IntegrationNotFoundError, match="integration not found: missing"):
        registry.get("missing")
