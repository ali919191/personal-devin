"""JSONL append-only audit logger for execution records."""

from __future__ import annotations

import json
from pathlib import Path

from app.execution.audit.audit_models import ExecutionRecord


class AuditLogger:
    """Write immutable execution records to a deterministic JSONL file."""

    def __init__(self, log_path: Path | None = None) -> None:
        if log_path is None:
            repo_root = Path(__file__).resolve().parents[3]
            log_path = repo_root / "logs" / "execution_audit.jsonl"
        self._log_path = log_path

    @property
    def log_path(self) -> Path:
        return self._log_path

    def write_record(self, record: ExecutionRecord) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
