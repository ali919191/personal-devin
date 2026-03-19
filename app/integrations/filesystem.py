"""Filesystem tool constrained to a safe root directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.integrations.tool import Tool, ToolResult


class FilesystemTool(Tool):
    """Deterministic filesystem tool with root-constrained access."""

    name = "filesystem"

    def __init__(self, root_dir: str | Path) -> None:
        root = Path(root_dir).resolve()
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise ValueError("root_dir must be a directory")
        self._root = root

    def execute(self, input: Dict[str, Any], context: Dict[str, Any]) -> ToolResult:
        result: ToolResult
        try:
            action = str(input.get("action", ""))
            if action == "read_file":
                output = self._read_file(input)
                result = ToolResult(success=True, output=output)
            elif action == "write_file":
                output = self._write_file(input)
                result = ToolResult(success=True, output=output)
            elif action == "list_dir":
                output = self._list_dir(input)
                result = ToolResult(success=True, output=output)
            else:
                result = ToolResult(success=False, error=f"unsupported filesystem action: {action}")
        except Exception as e:
            result = ToolResult(success=False, error=str(e))

        self._append_trace(context=context, input=input, result=result)
        return result

    def _resolve_path(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("input.path must be a non-empty string")

        candidate = (self._root / relative_path).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError("path traversal is not allowed")
        return candidate

    def _read_file(self, input: Dict[str, Any]) -> Dict[str, Any]:
        file_path = self._resolve_path(str(input.get("path", "")))
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"file not found: {input.get('path')}")

        content = file_path.read_text(encoding="utf-8")
        return {"path": str(file_path.relative_to(self._root)), "content": content}

    def _write_file(self, input: Dict[str, Any]) -> Dict[str, Any]:
        file_path = self._resolve_path(str(input.get("path", "")))
        content = input.get("content", "")
        if not isinstance(content, str):
            raise ValueError("input.content must be a string")

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return {
            "path": str(file_path.relative_to(self._root)),
            "bytes_written": len(content.encode("utf-8")),
        }

    def _list_dir(self, input: Dict[str, Any]) -> Dict[str, Any]:
        relative_path = input.get("path", ".")
        if not isinstance(relative_path, str):
            raise ValueError("input.path must be a string")

        dir_path = self._resolve_path(relative_path)
        if not dir_path.exists() or not dir_path.is_dir():
            raise FileNotFoundError(f"directory not found: {relative_path}")

        entries = []
        for item in sorted(dir_path.iterdir(), key=lambda p: p.name):
            entries.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                }
            )

        return {
            "path": str(dir_path.relative_to(self._root)),
            "entries": entries,
        }

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


# Backward-compatible alias for existing imports.
FilesystemIntegration = FilesystemTool
