"""Deterministic mock API tool with no real network calls."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from app.integrations.tool import Tool, ToolResult


class MockAPITool(Tool):
    """Mock external API tool for deterministic testing."""

    name = "mock_api"

    def __init__(self) -> None:
        self._static_get_responses = {
            "/health": {"service": "mock_api", "status": "ok"},
            "/projects": {
                "items": [
                    {"id": "project-1", "name": "Alpha"},
                    {"id": "project-2", "name": "Beta"},
                ]
            },
        }

    def execute(self, input: Dict[str, Any], context: Dict[str, Any]) -> ToolResult:
        result: ToolResult
        try:
            action = str(input.get("action", "")).upper()
            if action == "GET":
                output = self._handle_get(input)
                result = ToolResult(success=True, output=output)
            elif action == "POST":
                output = self._handle_post(input)
                result = ToolResult(success=True, output=output)
            else:
                result = ToolResult(success=False, error=f"unsupported mock_api action: {input.get('action', '')}")
        except Exception as e:
            result = ToolResult(success=False, error=str(e))

        self._append_trace(context=context, input=input, result=result)
        return result

    def _handle_get(self, input: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = self._validate_endpoint(input.get("endpoint"))
        if endpoint not in self._static_get_responses:
            raise ValueError(f"unknown mock endpoint: {endpoint}")

        return {
            "method": "GET",
            "endpoint": endpoint,
            "response": self._static_get_responses[endpoint],
        }

    def _handle_post(self, input: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = self._validate_endpoint(input.get("endpoint"))
        body = input.get("data", {})
        if not isinstance(body, dict):
            raise ValueError("input.data must be a dictionary")

        canonical_body = json.dumps(body, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{endpoint}:{canonical_body}".encode("utf-8")).hexdigest()
        resource_id = f"mock-{digest[:12]}"

        return {
            "method": "POST",
            "endpoint": endpoint,
            "resource_id": resource_id,
            "accepted": True,
            "echo": body,
        }

    def _validate_endpoint(self, endpoint: Any) -> str:
        if not isinstance(endpoint, str) or not endpoint.startswith("/"):
            raise ValueError("input.endpoint must be a string starting with '/'")
        return endpoint

    def _append_trace(self, context: Dict[str, Any], input: Dict[str, Any], result: ToolResult) -> None:
        trace = context.get("trace")
        if not isinstance(trace, list):
            context["trace"] = []
            trace = context["trace"]

        trace.append(
            {
                "stage": "tool_execution",
                "tool": self.name,
                "input": input,
                "success": result.success,
                "error": result.error,
            }
        )
