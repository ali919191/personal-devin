"""Tests for built-in integration providers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import sys

import pytest

from app.integrations.exceptions import IntegrationExecutionError
from app.integrations.models import IntegrationRequest
from app.integrations.providers.filesystem import FilesystemIntegration
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


# ---------------------------------------------------------------------------
# FilesystemIntegration tests
# ---------------------------------------------------------------------------


def test_filesystem_provider_writes_and_reads_file(tmp_path: Path) -> None:
    provider = FilesystemIntegration()
    target = tmp_path / "hello.txt"

    write_response = provider.execute(
        make_request("filesystem", {"action": "write", "path": str(target), "content": "hello world"})
    )
    assert write_response.payload["action"] == "write"
    assert write_response.payload["size_bytes"] == len("hello world".encode())

    read_response = provider.execute(
        make_request("filesystem", {"action": "read", "path": str(target)})
    )
    assert read_response.payload["action"] == "read"
    assert read_response.payload["content"] == "hello world"
    assert read_response.payload["size_bytes"] == len("hello world".encode())


def test_filesystem_provider_creates_parent_directories(tmp_path: Path) -> None:
    provider = FilesystemIntegration()
    nested = tmp_path / "a" / "b" / "c" / "data.txt"

    provider.execute(
        make_request("filesystem", {"action": "write", "path": str(nested), "content": "nested"})
    )

    assert nested.exists()
    assert nested.read_text() == "nested"


def test_filesystem_provider_lists_directory(tmp_path: Path) -> None:
    provider = FilesystemIntegration()
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.txt").write_text("b")
    (tmp_path / "gamma.txt").write_text("g")

    response = provider.execute(
        make_request("filesystem", {"action": "list", "path": str(tmp_path)})
    )

    assert response.payload["action"] == "list"
    assert response.payload["entries"] == ["alpha.txt", "beta.txt", "gamma.txt"]
    assert response.payload["count"] == 3


def test_filesystem_provider_raises_on_missing_file(tmp_path: Path) -> None:
    provider = FilesystemIntegration()

    with pytest.raises(IntegrationExecutionError, match="does not exist"):
        provider.execute(
            make_request("filesystem", {"action": "read", "path": str(tmp_path / "missing.txt")})
        )


def test_filesystem_provider_raises_on_missing_directory(tmp_path: Path) -> None:
    provider = FilesystemIntegration()

    with pytest.raises(IntegrationExecutionError, match="does not exist"):
        provider.execute(
            make_request("filesystem", {"action": "list", "path": str(tmp_path / "no_such_dir")})
        )


def test_filesystem_provider_raises_on_invalid_action() -> None:
    provider = FilesystemIntegration()

    with pytest.raises(IntegrationExecutionError, match="payload.action must be one of"):
        provider.execute(make_request("filesystem", {"action": "delete", "path": "/tmp/x"}))


def test_filesystem_provider_raises_when_path_missing() -> None:
    provider = FilesystemIntegration()

    with pytest.raises(IntegrationExecutionError, match="payload.path must be a non-empty string"):
        provider.execute(make_request("filesystem", {"action": "read"}))


def test_filesystem_provider_validate_config_accepts_valid_root(tmp_path: Path) -> None:
    provider = FilesystemIntegration()
    # Should not raise
    provider.validate_config({"root": str(tmp_path)})


def test_filesystem_provider_validate_config_rejects_non_string_root() -> None:
    provider = FilesystemIntegration()

    with pytest.raises(ValueError, match="root.*must be a string"):
        provider.validate_config({"root": 42})


def test_filesystem_provider_metadata_contains_action_and_path(tmp_path: Path) -> None:
    provider = FilesystemIntegration()
    target = tmp_path / "meta.txt"
    target.write_text("data")

    response = provider.execute(
        make_request("filesystem", {"action": "read", "path": str(target)})
    )

    assert response.metadata["action"] == "read"
    assert response.metadata["path"] == str(target)
    assert "timestamp" in response.metadata


# ---------------------------------------------------------------------------
# FilesystemIntegration — root sandboxing / path traversal tests
# ---------------------------------------------------------------------------


def test_filesystem_root_allows_paths_inside_sandbox(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    provider = FilesystemIntegration(root=str(sandbox))

    # Write via relative path anchored to root
    provider.execute(
        make_request("filesystem", {"action": "write", "path": "safe.txt", "content": "ok"})
    )
    assert (sandbox / "safe.txt").read_text() == "ok"


def test_filesystem_root_allows_absolute_path_inside_sandbox(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    provider = FilesystemIntegration(root=str(sandbox))

    target = sandbox / "inner.txt"
    provider.execute(
        make_request("filesystem", {"action": "write", "path": str(target), "content": "inner"})
    )
    assert target.read_text() == "inner"


def test_filesystem_root_blocks_relative_traversal(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    provider = FilesystemIntegration(root=str(sandbox))

    with pytest.raises(IntegrationExecutionError, match="path traversal blocked"):
        provider.execute(
            make_request("filesystem", {"action": "read", "path": "../../etc/passwd"})
        )


def test_filesystem_root_blocks_absolute_escape(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    # Create a file outside the sandbox to attempt to read it
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    provider = FilesystemIntegration(root=str(sandbox))

    with pytest.raises(IntegrationExecutionError, match="path traversal blocked"):
        provider.execute(
            make_request("filesystem", {"action": "read", "path": str(outside)})
        )


def test_filesystem_root_blocks_normalised_traversal(tmp_path: Path) -> None:
    """Normalised paths like 'sub/../../outside' must also be rejected."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "sub").mkdir()
    provider = FilesystemIntegration(root=str(sandbox))

    with pytest.raises(IntegrationExecutionError, match="path traversal blocked"):
        provider.execute(
            make_request("filesystem", {"action": "list", "path": "sub/../../"})
        )

