from __future__ import annotations

from typing import Any

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

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        integration_name = request.get("integration")
        action = request.get("action")
        payload = request.get("payload", {})
        context = request.get("context", {})

        tool_input = dict(payload)
        tool_input["action"] = action

        tool = self.get(str(integration_name))
        result = tool.execute(input=tool_input, context=context)
        if result.success:
            return {"status": "success", "data": result.output, "error": None}
        return {"status": "error", "data": {}, "error": result.error}


_REGISTRY = ToolRegistry()


def register_tool(tool: Tool) -> None:
    _REGISTRY.register(tool)


def execute_tool(name: str, input: dict, context: dict) -> ToolResult:
    tool = _REGISTRY.get(name)
    return tool.execute(input=input, context=context)


# Backward-compatible alias for existing imports.
IntegrationRegistry = ToolRegistry


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """Compatibility wrapper mapping legacy request contract to ToolResult contract."""
    integration_name = request.get("integration")
    action = request.get("action")
    payload = request.get("payload", {})
    context = request.get("context", {})

    tool_input = dict(payload)
    tool_input["action"] = action

    result = execute_tool(str(integration_name), tool_input, context)
    if result.success:
        return {"status": "success", "data": result.output, "error": None}
    return {"status": "error", "data": {}, "error": result.error}
