"""Tests for integration manager orchestration and observability."""

from datetime import UTC, datetime
import json

import pytest

from app.integrations.base import BaseIntegration
from app.integrations.exceptions import IntegrationExecutionError, IntegrationNotFoundError
from app.integrations.manager import IntegrationManager
from app.integrations.models import IntegrationRequest, IntegrationResponse
from app.integrations.registry import IntegrationRegistry


class RecordingIntegration(BaseIntegration):
    name = "recording"

    def __init__(self) -> None:
        self.requests: list[IntegrationRequest] = []

    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        self.requests.append(request)
        return IntegrationResponse(
            id=request.id,
            integration=self.name,
            payload={"received": request.payload},
            metadata={**request.metadata, "provider": self.name},
            timestamp=request.timestamp,
        )


class FailingIntegration(BaseIntegration):
    name = "failing"

    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        raise IntegrationExecutionError("provider exploded")


def make_request(integration: str) -> IntegrationRequest:
    return IntegrationRequest(
        id="req-1",
        integration=integration,
        payload={"value": 42},
        metadata={"source": "test"},
        timestamp=datetime(2026, 3, 19, tzinfo=UTC),
    )


def test_manager_resolves_and_executes_provider(capsys: pytest.CaptureFixture[str]) -> None:
    registry = IntegrationRegistry()
    provider = RecordingIntegration()
    registry.register(provider)
    manager = IntegrationManager(registry)

    response = manager.execute(make_request("recording"))

    assert response.payload == {"received": {"value": 42}}
    assert response.metadata["provider"] == "recording"
    assert provider.requests[0].integration == "recording"

    stdout = capsys.readouterr().out.strip().splitlines()
    assert len(stdout) == 3
    request_log = json.loads(stdout[0])
    resolved_log = json.loads(stdout[1])
    response_log = json.loads(stdout[2])

    assert request_log["action"] == "integration_request"
    assert request_log["data"]["request_id"] == "req-1"
    assert request_log["data"]["integration"] == "recording"
    assert resolved_log["action"] == "integration_resolved"
    assert resolved_log["data"]["request_id"] == "req-1"
    assert resolved_log["data"]["integration"] == "recording"
    assert response_log["action"] == "integration_response"
    assert response_log["data"]["request_id"] == "req-1"
    assert response_log["data"]["integration"] == "recording"
    assert response_log["data"]["success"] is True
    assert response_log["data"]["status"] == "ok"
    assert response_log["data"]["error"] is None
    assert response_log["data"]["duration_ms"] >= 0


def test_manager_raises_not_found_for_unknown_provider(
    capsys: pytest.CaptureFixture[str],
) -> None:
    manager = IntegrationManager(IntegrationRegistry())

    with pytest.raises(IntegrationNotFoundError, match="integration not found: missing"):
        manager.execute(make_request("missing"))

    stderr = capsys.readouterr().err.strip().splitlines()
    assert len(stderr) == 1
    error_log = json.loads(stderr[0])
    assert error_log["action"] == "integration_error"
    assert error_log["data"]["request_id"] == "req-1"
    assert error_log["data"]["integration"] == "missing"
    assert error_log["data"]["success"] is False
    assert error_log["data"]["status"] == "error"
    assert error_log["data"]["duration_ms"] >= 0


def test_manager_surfaces_provider_failure(capsys: pytest.CaptureFixture[str]) -> None:
    registry = IntegrationRegistry()
    registry.register(FailingIntegration())
    manager = IntegrationManager(registry)

    with pytest.raises(IntegrationExecutionError, match="provider exploded"):
        manager.execute(make_request("failing"))

    stderr = capsys.readouterr().err.strip().splitlines()
    assert len(stderr) == 1
    error_log = json.loads(stderr[0])
    assert error_log["error"] == "provider exploded"
    assert error_log["data"]["request_id"] == "req-1"
    assert error_log["data"]["integration"] == "failing"
    assert error_log["data"]["success"] is False
    assert error_log["data"]["status"] == "error"
    assert error_log["data"]["duration_ms"] >= 0


def test_manager_rejects_disallowed_action(capsys: pytest.CaptureFixture[str]) -> None:
    from app.integrations.providers.filesystem import FilesystemIntegration

    registry = IntegrationRegistry()
    registry.register(FilesystemIntegration())
    manager = IntegrationManager(registry)

    request = IntegrationRequest(
        id="req-bad",
        integration="filesystem",
        payload={"action": "delete", "path": "/tmp/x"},
        metadata={},
        timestamp=datetime(2026, 3, 19, tzinfo=UTC),
    )

    with pytest.raises(IntegrationExecutionError, match="not permitted"):
        manager.execute(request)

    stderr = capsys.readouterr().err.strip().splitlines()
    assert len(stderr) == 1
    error_log = json.loads(stderr[0])
    assert error_log["data"]["action"] == "delete"
    assert error_log["data"]["integration"] == "filesystem"
    assert error_log["data"]["status"] == "error"
