from __future__ import annotations

from app.integrations.tool import Tool, ToolResult


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        name = getattr(tool, "name", "")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("tool.name must be a non-empty string")
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def list(self) -> list[str]:
        return sorted(self._tools.keys())


_REGISTRY = ToolRegistry()


def register_tool(tool: Tool) -> None:
    _REGISTRY.register(tool)


def execute_tool(name: str, input: dict, context: dict) -> ToolResult:
    tool = _REGISTRY.get(name)
    return tool.execute(input=input, context=context)
