"""Execution history analyzer for Agent 15 self-improvement loop."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.self_improvement.models import ExecutionRecord, FailureRecord


class Analyzer:
    """Loads and normalizes execution history from a memory store into typed records."""

    _EXECUTION_TYPE = "execution"
    _FAILURE_TYPE = "failure"

    def load_executions(self, memory_store: Any, limit: int = 200) -> list[ExecutionRecord]:
        """Extract and normalize execution records from the memory store."""
        raw = self._fetch(memory_store, limit)
        records: list[ExecutionRecord] = []
        for entry in raw:
            if self._record_type(entry) != self._EXECUTION_TYPE:
                continue
            data = self._data(entry)
            record = ExecutionRecord(
                record_id=self._field(entry, "id", f"exec-{len(records)}"),
                status=str(data.get("status", "unknown")),
                latency=float(data.get("latency", 0.0)),
                failed_tasks=int(data.get("failed_tasks", 0)),
                total_tasks=int(data.get("total_tasks", 0)),
                errors=self._errors(data),
                timestamp=self._timestamp(entry),
            )
            records.append(record)
        return records

    def load_failures(self, memory_store: Any, limit: int = 200) -> list[FailureRecord]:
        """Extract and normalize failure records from the memory store."""
        raw = self._fetch(memory_store, limit)
        records: list[FailureRecord] = []
        for entry in raw:
            if self._record_type(entry) != self._FAILURE_TYPE:
                continue
            data = self._data(entry)
            record = FailureRecord(
                record_id=self._field(entry, "id", f"failure-{len(records)}"),
                error=str(data.get("error", "unknown")),
                source=str(data.get("source", "unknown")),
                timestamp=self._timestamp(entry),
            )
            records.append(record)
        return records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch(self, memory_store: Any, limit: int) -> list:
        if hasattr(memory_store, "get_recent"):
            try:
                result = memory_store.get_recent(limit=limit)
                if isinstance(result, list):
                    return result
            except Exception:
                pass
        return []

    def _record_type(self, entry: Any) -> str:
        if hasattr(entry, "type"):
            return str(entry.type)
        if isinstance(entry, dict):
            return str(entry.get("type", ""))
        return ""

    def _data(self, entry: Any) -> dict:
        if hasattr(entry, "data") and isinstance(entry.data, dict):
            return dict(entry.data)
        if isinstance(entry, dict):
            payload = entry.get("data", {})
            if isinstance(payload, dict):
                return dict(payload)
        return {}

    def _field(self, entry: Any, key: str, default: str) -> str:
        if hasattr(entry, key):
            return str(getattr(entry, key))
        if isinstance(entry, dict):
            return str(entry.get(key, default))
        return default

    def _timestamp(self, entry: Any) -> datetime | None:
        raw = None
        if hasattr(entry, "timestamp"):
            raw = entry.timestamp
        elif isinstance(entry, dict):
            raw = entry.get("timestamp")
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
        try:
            parsed = datetime.fromisoformat(str(raw))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return None

    def _errors(self, data: dict) -> list[str]:
        errors = data.get("errors", [])
        if isinstance(errors, list):
            return [str(e) for e in errors if e is not None]
        error_field = data.get("error")
        if error_field:
            return [str(error_field)]
        return []
