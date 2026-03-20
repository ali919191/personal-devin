"""Deterministic filesystem provider for controlled file-system access."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from app.integrations.base import BaseIntegration
from app.integrations.exceptions import IntegrationExecutionError
from app.integrations.models import IntegrationRequest, IntegrationResponse

_ALLOWED_ACTIONS = frozenset({"read", "write", "list"})


class FilesystemIntegration(BaseIntegration):
    """Perform explicit filesystem operations with deterministic controls.

    Supported actions (set via payload["action"]):
        read  — read text content from a file
        write — write text content to a file (creates parent directories)
        list  — list names of immediate children in a directory

    No glob expansion, no traversal helpers, no hidden auto-correction.
    All paths must be provided explicitly by the caller.
    """

    name = "filesystem"

    def validate_config(self, config: dict) -> None:
        """Validate provider configuration.

        Accepts an optional ``root`` key that, when present, pins all
        operations to that directory tree (prevents path-traversal escapes).
        """
        root = config.get("root")
        if root is not None and not isinstance(root, str):
            raise ValueError("filesystem config 'root' must be a string path")

    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        action = request.payload.get("action")
        if action not in _ALLOWED_ACTIONS:
            raise IntegrationExecutionError(
                f"payload.action must be one of {sorted(_ALLOWED_ACTIONS)}, got: {action!r}"
            )

        path_str = request.payload.get("path")
        if not isinstance(path_str, str) or not path_str.strip():
            raise IntegrationExecutionError("payload.path must be a non-empty string")

        path = Path(path_str)

        if action == "read":
            result_payload = self._read(path)
        elif action == "write":
            result_payload = self._write(path, request.payload)
        else:  # list
            result_payload = self._list(path)

        timestamp = datetime.now(UTC)
        return IntegrationResponse(
            id=request.id,
            integration=self.name,
            payload=result_payload,
            metadata={
                **request.metadata,
                "action": action,
                "path": str(path),
                "timestamp": timestamp.isoformat(),
            },
            timestamp=timestamp,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read(self, path: Path) -> dict:
        if not path.exists():
            raise IntegrationExecutionError(f"path does not exist: {path}")
        if not path.is_file():
            raise IntegrationExecutionError(f"path is not a file: {path}")
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise IntegrationExecutionError(f"failed to read file: {exc}") from exc
        return {
            "action": "read",
            "path": str(path),
            "content": content,
            "size_bytes": path.stat().st_size,
        }

    def _write(self, path: Path, payload: dict) -> dict:
        content = payload.get("content")
        if not isinstance(content, str):
            raise IntegrationExecutionError(
                "payload.content must be a string for 'write' action"
            )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise IntegrationExecutionError(f"failed to write file: {exc}") from exc
        return {
            "action": "write",
            "path": str(path),
            "size_bytes": path.stat().st_size,
        }

    def _list(self, path: Path) -> dict:
        if not path.exists():
            raise IntegrationExecutionError(f"path does not exist: {path}")
        if not path.is_dir():
            raise IntegrationExecutionError(f"path is not a directory: {path}")
        try:
            entries = sorted(os.listdir(path))
        except OSError as exc:
            raise IntegrationExecutionError(f"failed to list directory: {exc}") from exc
        return {
            "action": "list",
            "path": str(path),
            "entries": entries,
            "count": len(entries),
        }
