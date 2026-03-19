"""Tests for integrations tools and deterministic registry behavior."""

from pathlib import Path

import pytest

from app.integrations import Tool, ToolRegistry, ToolResult, execute_tool
from app.integrations.filesystem import FilesystemTool
from app.integrations.mock_api import MockAPITool
from app.integrations.registry import register_tool


class DummyTool(Tool):
    name = "dummy"

    def execute(self, input: dict, context: dict) -> ToolResult:
        if input.get("action") == "ok":
            echo_payload = {key: value for key, value in input.items() if key != "action"}
            return ToolResult(success=True, output={"echo": echo_payload})
        return ToolResult(success=False, error="bad action")


def _register_named_tool(tool: Tool, name: str) -> str:
    tool.name = name
    register_tool(tool)
    return name


def test_registry_register_get_and_list() -> None:
    registry = ToolRegistry()
    tool = DummyTool()

    registry.register(tool)

    assert registry.get("dummy") is tool
    assert registry.list() == ["dummy"]


def test_registry_prevents_duplicate_registration() -> None:
    registry = ToolRegistry()
    registry.register(DummyTool())

    with pytest.raises(ValueError, match="tool already registered"):
        registry.register(DummyTool())


def test_registry_get_missing_name_has_clear_error() -> None:
    registry = ToolRegistry()

    with pytest.raises(KeyError):
        registry.get("missing")


def test_execute_tool_contract_success() -> None:
    class DummyExecuteTool(Tool):
        name = "dummy_execute_tool_success"

        def execute(self, input: dict, context: dict) -> ToolResult:
            return ToolResult(success=True, output={"echo": input})

    register_tool(DummyExecuteTool())

    result = execute_tool("dummy_execute_tool_success", {"action": "ok", "a": 1}, {})

    assert result.success is True
    assert result.error is None
    assert result.output == {"echo": {"action": "ok", "a": 1}}


def test_filesystem_write_read_and_list(tmp_path: Path) -> None:
    tool_name = _register_named_tool(FilesystemTool(root_dir=tmp_path), "filesystem_test_write_read")

    context: dict = {}

    write_result = execute_tool(
        tool_name,
        {"action": "write_file", "path": "docs/note.txt", "content": "hello world"},
        context,
    )
    assert write_result.success is True
    assert write_result.output["path"] == "docs/note.txt"

    read_result = execute_tool(tool_name, {"action": "read_file", "path": "docs/note.txt"}, context)
    assert read_result.success is True
    assert read_result.output == {"path": "docs/note.txt", "content": "hello world"}

    list_result = execute_tool(tool_name, {"action": "list_dir", "path": "docs"}, context)
    assert list_result.success is True
    assert list_result.output["entries"] == [{"name": "note.txt", "type": "file"}]


def test_filesystem_blocks_path_traversal(tmp_path: Path) -> None:
    tool_name = _register_named_tool(FilesystemTool(root_dir=tmp_path), "filesystem_test_traversal")

    context: dict = {}

    result = execute_tool(tool_name, {"action": "read_file", "path": "../outside.txt"}, context)

    assert result.success is False
    assert result.error == "path traversal is not allowed"


def test_filesystem_unknown_action_returns_error(tmp_path: Path) -> None:
    tool_name = _register_named_tool(FilesystemTool(root_dir=tmp_path), "filesystem_test_unknown_action")

    result = execute_tool(tool_name, {"action": "delete_file", "path": "x"}, {})

    assert result.success is False
    assert result.error == "unsupported filesystem action: delete_file"


def test_mock_api_get_is_deterministic() -> None:
    tool_name = _register_named_tool(MockAPITool(), "mock_api_test_get")

    first = execute_tool(tool_name, {"action": "GET", "endpoint": "/health"}, {})
    second = execute_tool(tool_name, {"action": "GET", "endpoint": "/health"}, {})

    assert first.success is True
    assert second.success is True
    assert first.output == second.output
    assert first.output["response"] == {"service": "mock_api", "status": "ok"}


def test_mock_api_post_is_deterministic() -> None:
    tool_name = _register_named_tool(MockAPITool(), "mock_api_test_post")

    payload = {"action": "POST", "endpoint": "/projects", "data": {"name": "Gamma", "priority": 1}}

    first = execute_tool(tool_name, payload, {})
    second = execute_tool(tool_name, payload, {})

    assert first.success is True
    assert second.success is True
    assert first.output == second.output
    assert first.output["resource_id"].startswith("mock-")


def test_mock_api_errors_are_reported() -> None:
    tool_name = _register_named_tool(MockAPITool(), "mock_api_test_errors")

    bad_method = execute_tool(tool_name, {"action": "PUT", "endpoint": "/health"}, {})
    assert bad_method.success is False
    assert bad_method.error == "unsupported mock_api action: PUT"

    bad_endpoint = execute_tool(tool_name, {"action": "GET", "endpoint": "health"}, {})
    assert bad_endpoint.success is False
    assert bad_endpoint.error == "input.endpoint must be a string starting with '/'"
