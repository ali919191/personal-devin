"""Tests for Agent 10 integration control layer."""

from pathlib import Path

from app.integrations import execute_tool
from app.integrations.filesystem import FilesystemTool
from app.integrations.mock_api import MockAPITool
from app.integrations.registry import register_tool


def _register_named_tool(tool, name: str) -> str:
    tool.name = name
    register_tool(tool)
    return name


def test_successful_execution_filesystem_and_mock_api(tmp_path: Path) -> None:
    fs_name = _register_named_tool(FilesystemTool(root_dir=tmp_path), "filesystem_control_success")
    api_name = _register_named_tool(MockAPITool(), "mock_api_control_success")

    fs_result = execute_tool(
        name=fs_name,
        input={"action": "write_file", "path": "note.txt", "content": "ok"},
        context={},
    )
    api_result = execute_tool(
        name=api_name,
        input={"action": "GET", "endpoint": "/health"},
        context={},
    )

    assert fs_result.success is True
    assert fs_result.error is None
    assert fs_result.output == {"path": "note.txt", "bytes_written": 2}
    assert api_result.success is True


def test_failure_handling_no_exception_leak(tmp_path: Path) -> None:
    fs_name = _register_named_tool(FilesystemTool(root_dir=tmp_path), "filesystem_control_failure")

    result = execute_tool(fs_name, {"action": "read_file", "path": "missing.txt"}, {})

    assert result.success is False
    assert isinstance(result.error, str)


def test_trace_validation(tmp_path: Path) -> None:
    fs_name = _register_named_tool(FilesystemTool(root_dir=tmp_path), "filesystem_control_trace")

    context: dict = {}

    _ = execute_tool(fs_name, {"action": "write_file", "path": "trace.txt", "content": "x"}, context)

    assert "trace" in context
    assert isinstance(context["trace"], list)
    assert len(context["trace"]) == 1
    entry = context["trace"][0]
    assert entry["stage"] == "tool_execution"
    assert entry["tool"] == fs_name
    assert entry["success"] is True


def test_registry_enforcement_execute_tool_entrypoint(tmp_path: Path) -> None:
    fs_name = _register_named_tool(FilesystemTool(root_dir=tmp_path), "filesystem_control_entrypoint")

    result = execute_tool(
        name=fs_name,
        input={"action": "write_file", "path": "entry.txt", "content": "hello"},
        context={},
    )

    assert result.success is True
