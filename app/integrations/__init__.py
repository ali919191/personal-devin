"""Public interface for integrations layer."""

from app.integrations.filesystem import FilesystemTool
from app.integrations.mock_api import MockAPITool
from app.integrations.registry import IntegrationRegistry, ToolRegistry, execute_tool, register_tool
from app.integrations.tool import Tool, ToolResult

# Backward-compatible aliases for existing imports.
FilesystemIntegration = FilesystemTool
MockAPIIntegration = MockAPITool

__all__ = [
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "register_tool",
    "execute_tool",
    "IntegrationRegistry",
    "FilesystemTool",
    "MockAPITool",
    "FilesystemIntegration",
    "MockAPIIntegration",
]
