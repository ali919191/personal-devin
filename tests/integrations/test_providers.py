"""Tests for built-in integration providers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import sys

import pytest

from app.integrations.exceptions import IntegrationExecutionError
from app.integrations.models import IntegrationRequest
from app.integrations.providers.http import HTTPIntegration
from app.integrations.providers.mock import MockIntegration
from app.integrations.providers.shell import ShellIntegration


def make_request(integration: str, payload: dict) -> IntegrationRequest:
    return IntegrationRequest(
        id="req-123",
        integration=integration,
        payload=payload,
        metadata={"suite": "providers"},
        timestamp=datetime(2026, 3, 19, tzinfo=UTC),
    )


class DeterministicHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({"path": self.path, "method": "GET"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length).decode("utf-8")
        body = json.dumps({"received": json.loads(raw)}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def http_server() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), DeterministicHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_shell_provider_executes_command_and_captures_output() -> None:
    provider = ShellIntegration()
    response = provider.execute(
        make_request(
            "shell",
            {
                "command": [sys.executable, "-c", "print('hello from shell')"],
                "timeout_seconds": 5,
            },
        )
    )

    assert response.payload["exit_code"] == 0
    assert response.payload["stdout"] == "hello from shell\n"
    assert response.payload["stderr"] == ""


def test_shell_provider_raises_on_non_zero_exit() -> None:
    provider = ShellIntegration()

    with pytest.raises(IntegrationExecutionError, match="exit code 7"):
        provider.execute(
            make_request(
                "shell",
                {"command": [sys.executable, "-c", "import sys; sys.exit(7)"]},
            )
        )


def test_shell_provider_enforces_timeout() -> None:
    provider = ShellIntegration()

    with pytest.raises(IntegrationExecutionError, match="timed out"):
        provider.execute(
            make_request(
                "shell",
                {
                    "command": [sys.executable, "-c", "import time; time.sleep(0.2)"],
                    "timeout_seconds": 0.05,
                },
            )
        )


def test_http_provider_performs_deterministic_get(http_server: str) -> None:
    provider = HTTPIntegration()
    response = provider.execute(
        make_request(
            "http",
            {
                "method": "GET",
                "url": f"{http_server}/health",
                "params": {"a": "1", "b": "2"},
                "timeout_seconds": 5,
            },
        )
    )

    assert response.payload["status_code"] == 200
    assert response.payload["body"] == {"path": "/health?a=1&b=2", "method": "GET"}
    assert response.metadata["retry_attempts"] == 0


def test_http_provider_performs_deterministic_post(http_server: str) -> None:
    provider = HTTPIntegration()
    response = provider.execute(
        make_request(
            "http",
            {
                "method": "POST",
                "url": f"{http_server}/items",
                "body": {"z": 2, "a": 1},
                "timeout_seconds": 5,
            },
        )
    )

    assert response.payload["status_code"] == 200
    assert response.payload["body"] == {"received": {"a": 1, "z": 2}}


def test_http_provider_rejects_implicit_retry_configuration() -> None:
    provider = HTTPIntegration()

    with pytest.raises(IntegrationExecutionError, match="does not perform retries"):
        provider.execute(
            make_request(
                "http",
                {"method": "GET", "url": "http://example.invalid", "retry": True},
            )
        )


def test_mock_provider_returns_repeatable_output() -> None:
    provider = MockIntegration()
    request = make_request("mock", {"operation": "lookup", "resource_id": "abc"})

    first = provider.execute(request)
    second = provider.execute(request)

    assert first == second
    assert first.payload["result"] == {"status": "ok", "resource_id": "abc"}
    assert first.metadata["deterministic"] is True


def test_mock_provider_rejects_unknown_operation() -> None:
    provider = MockIntegration()

    with pytest.raises(IntegrationExecutionError, match="unsupported mock operation"):
        provider.execute(make_request("mock", {"operation": "mutate"}))
