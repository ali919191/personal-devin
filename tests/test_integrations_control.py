"""Tests for Agent 10 integration control layer."""

from pathlib import Path

from app.integrations import FilesystemTool, MockAPITool, ToolRegistry, execute_tool, register_tool


def test_successful_execution_filesystem_and_mock_api(tmp_path: Path) -> None:
    registry = ToolRegistry()
    fs = FilesystemTool(root_dir=tmp_path)
    api = MockAPITool()

    registry.register(fs)
    registry.register(api)

    fs_result = registry.execute(
        {
            "integration": "filesystem",
            "action": "write_file",
            "payload": {"path": "note.txt", "content": "ok"},
            "context": {},
        }
    )
    api_result = registry.execute(
        {
            "integration": "mock_api",
            "action": "GET",
            "payload": {"endpoint": "/health"},
            "context": {},
        }
    )

    assert fs_result["status"] == "success"
    assert api_result["status"] == "success"


def test_failure_handling_no_exception_leak(tmp_path: Path) -> None:
    fs = FilesystemTool(root_dir=tmp_path)

    result = fs.execute({"action": "read_file", "path": "missing.txt"}, {})

    assert result.success is False
    assert isinstance(result.error, str)


def test_trace_validation(tmp_path: Path) -> None:
    fs = FilesystemTool(root_dir=tmp_path)
    context: dict = {}

    _ = fs.execute({"action": "write_file", "path": "trace.txt", "content": "x"}, context)

    assert "trace" in context
    assert isinstance(context["trace"], list)
    assert len(context["trace"]) == 1
    entry = context["trace"][0]
    assert entry["stage"] == "tool_execution"
    assert entry["tool"] == "filesystem"
    assert entry["success"] is True


def test_registry_enforcement_execute_tool_entrypoint(tmp_path: Path) -> None:
    fs = FilesystemTool(root_dir=tmp_path)
    register_tool(fs)

    result = execute_tool(
        name="filesystem",
        input={"action": "write_file", "path": "entry.txt", "content": "hello"},
        context={},
    )

    assert result.success is True
