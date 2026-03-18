"""Filesystem integration constrained to a safe root directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from app.integrations.base import Integration

logger = get_logger(__name__)


class FilesystemIntegration(Integration):
    """Deterministic filesystem integration with root-constrained access."""

    name = "filesystem"

    def __init__(self, root_dir: str | Path) -> None:
        root = Path(root_dir).resolve()
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise ValueError("root_dir must be a directory")
        self._root = root

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = self._validate_payload(payload)
        sanitized_payload = self._sanitize_payload(action, payload)
        logger.info(
            "filesystem_action_started",
            {"action": action, "payload": sanitized_payload},
        )

        try:
            if action == "read_file":
                result = self._read_file(payload)
            elif action == "write_file":
                result = self._write_file(payload)
            elif action == "list_dir":
                result = self._list_dir(payload)
            else:
                return self._error(f"unsupported filesystem action: {action}")
        except Exception as exc:  # pragma: no cover - guarded by tests via behavior
            logger.error(
                "filesystem_action_failed",
                error=str(exc),
                data={"action": action, "payload": sanitized_payload},
            )
            return self._error(str(exc))

        logger.info(
            "filesystem_action_completed",
            {"action": action, "result_keys": sorted(result.keys())},
        )
        return self._success(result)

    def _resolve_path(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("payload.path must be a non-empty string")

        candidate = (self._root / relative_path).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError("path traversal is not allowed")
        return candidate

    def _read_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        file_path = self._resolve_path(str(payload.get("path", "")))
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"file not found: {payload.get('path')}")

        content = file_path.read_text(encoding="utf-8")
        return {"path": str(file_path.relative_to(self._root)), "content": content}

    def _write_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        file_path = self._resolve_path(str(payload.get("path", "")))
        content = payload.get("content", "")
        if not isinstance(content, str):
            raise ValueError("payload.content must be a string")

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return {
            "path": str(file_path.relative_to(self._root)),
            "bytes_written": len(content.encode("utf-8")),
        }

    def _list_dir(self, payload: dict[str, Any]) -> dict[str, Any]:
        relative_path = payload.get("path", ".")
        if not isinstance(relative_path, str):
            raise ValueError("payload.path must be a string")

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

    def _sanitize_payload(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {"path": payload.get("path")}
        if action == "write_file" and "content" in payload:
            content = payload.get("content")
            if isinstance(content, str):
                sanitized["content_length"] = len(content)
            else:
                sanitized["content_type"] = type(content).__name__
        return sanitized
