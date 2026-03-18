"""Tests for Agent 06 integrations layer."""

from pathlib import Path

import pytest

from app.integrations import FilesystemIntegration, IntegrationRegistry, MockAPIIntegration
from app.integrations.base import Integration


class DummyIntegration(Integration):
    name = "dummy"

    def execute(self, action: str, payload: dict) -> dict:
        if action == "ok":
            return self._success({"echo": payload})
        return self._error("bad action")


def test_registry_register_get_and_list() -> None:
    registry = IntegrationRegistry()
    integration = DummyIntegration()

    registry.register(integration)

    assert registry.get("dummy") is integration
    assert registry.list() == ["dummy"]


def test_registry_prevents_duplicate_registration() -> None:
    registry = IntegrationRegistry()
    registry.register(DummyIntegration())

    with pytest.raises(ValueError, match="integration already registered"):
        registry.register(DummyIntegration())


def test_registry_get_missing_name_has_clear_error() -> None:
    registry = IntegrationRegistry()

    with pytest.raises(KeyError, match="integration not found"):
        registry.get("missing")


def test_registry_execute_contract_success() -> None:
    registry = IntegrationRegistry()
    registry.register(DummyIntegration())

    result = registry.execute(
        {
            "integration": "dummy",
            "action": "ok",
            "payload": {"a": 1},
        }
    )

    assert result == {
        "status": "success",
        "data": {"echo": {"a": 1}},
        "error": None,
    }


def test_filesystem_write_read_and_list(tmp_path: Path) -> None:
    fs = FilesystemIntegration(root_dir=tmp_path)

    write_result = fs.execute(
        "write_file",
        {"path": "docs/note.txt", "content": "hello world"},
    )
    assert write_result["status"] == "success"
    assert write_result["data"]["path"] == "docs/note.txt"

    read_result = fs.execute("read_file", {"path": "docs/note.txt"})
    assert read_result == {
        "status": "success",
        "data": {"path": "docs/note.txt", "content": "hello world"},
        "error": None,
    }

    list_result = fs.execute("list_dir", {"path": "docs"})
    assert list_result["status"] == "success"
    assert list_result["data"]["entries"] == [{"name": "note.txt", "type": "file"}]


def test_filesystem_blocks_path_traversal(tmp_path: Path) -> None:
    fs = FilesystemIntegration(root_dir=tmp_path)

    result = fs.execute("read_file", {"path": "../outside.txt"})

    assert result["status"] == "error"
    assert result["error"] == "path traversal is not allowed"


def test_filesystem_unknown_action_returns_error(tmp_path: Path) -> None:
    fs = FilesystemIntegration(root_dir=tmp_path)

    result = fs.execute("delete_file", {"path": "x"})

    assert result == {
        "status": "error",
        "data": {},
        "error": "unsupported filesystem action: delete_file",
    }


def test_mock_api_get_is_deterministic() -> None:
    mock_api = MockAPIIntegration()

    first = mock_api.execute("GET", {"endpoint": "/health"})
    second = mock_api.execute("GET", {"endpoint": "/health"})

    assert first == second
    assert first["status"] == "success"
    assert first["data"]["response"] == {"service": "mock_api", "status": "ok"}


def test_mock_api_post_is_deterministic() -> None:
    mock_api = MockAPIIntegration()
    payload = {"endpoint": "/projects", "data": {"name": "Gamma", "priority": 1}}

    first = mock_api.execute("POST", payload)
    second = mock_api.execute("POST", payload)

    assert first == second
    assert first["status"] == "success"
    assert first["data"]["resource_id"].startswith("mock-")


def test_mock_api_errors_are_reported() -> None:
    mock_api = MockAPIIntegration()

    bad_method = mock_api.execute("PUT", {"endpoint": "/health"})
    assert bad_method == {
        "status": "error",
        "data": {},
        "error": "unsupported mock_api action: PUT",
    }

    bad_endpoint = mock_api.execute("GET", {"endpoint": "health"})
    assert bad_endpoint["status"] == "error"
    assert bad_endpoint["error"] == "payload.endpoint must be a string starting with '/'"
