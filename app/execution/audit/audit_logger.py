"""JSONL append-only audit logger for execution records."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.execution.audit.audit_models import ExecutionRecord

_AUDIT_LOG_ENV_VAR = "EXECUTION_AUDIT_LOG_PATH"


class AuditLogger:
    """Write immutable execution records to a deterministic JSONL file."""

    def __init__(self, log_path: Path | None = None) -> None:
        self._log_path = self._resolve_log_path(log_path)

    @staticmethod
    def _resolve_log_path(explicit_path: Path | None) -> Path:
        if explicit_path is not None:
            return explicit_path

        env_path = os.environ.get(_AUDIT_LOG_ENV_VAR)
        if env_path:
            return Path(env_path)

        repo_root = Path(__file__).resolve().parents[3]
        return repo_root / "logs" / "execution_audit.jsonl"

    @property
    def log_path(self) -> Path:
        return self._log_path

    def write_record(self, record: ExecutionRecord) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        payload = f"{line}\n".encode("utf-8")

        fd = os.open(
            self._log_path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o644,
        )
        try:
            total_written = 0
            while total_written < len(payload):
                written = os.write(fd, payload[total_written:])
                if written <= 0:
                    raise OSError("failed to write audit record")
                total_written += written
        finally:
            os.close(fd)
