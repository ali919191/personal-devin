"""Deterministic append-only file storage for memory records."""

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from app.core.logger import get_logger

logger = get_logger(__name__)

_FILE_BY_TYPE = {
    "execution": "executions.json",
    "task": "tasks.json",
    "failure": "failures.json",
    "decision": "decisions.json",
}


class MemoryStore:
    """Low-level JSON storage with append-only semantics."""

    def __init__(self, base_dir: str | Path = "data/memory") -> None:
        self.base_dir = Path(base_dir)
        self._lock = Lock()
        self._ensure_layout()

    def append(self, memory_type: str, payload: dict) -> None:
        file_path = self._file_path(memory_type)
        memory_id = str(payload.get("id", "unknown"))

        with self._lock:
            existing = self._read_all_unlocked(memory_type)
            existing.append(payload)
            self._atomic_write(file_path, existing)

        logger.info(
            "memory_write_completed",
            {"type": memory_type, "id": memory_id, "status": "ok"},
        )

    def read_all(self, memory_type: str) -> list[dict]:
        with self._lock:
            data = self._read_all_unlocked(memory_type)

        logger.info(
            "memory_read_completed",
            {"type": memory_type, "id": "n/a", "status": "ok"},
        )
        return data

    def store_execution(self, record: dict) -> None:
        """Store a unified execution record in the execution stream."""
        self.append("execution", record)

    def get_recent(self, limit: int) -> list[dict]:
        """Return recent execution records sorted deterministically newest-first."""
        execution_records = self.read_all("execution")
        ordered = sorted(
            execution_records,
            key=self._execution_sort_key,
            reverse=True,
        )
        return ordered[: max(limit, 0)]

    def get_failures(self) -> list[dict]:
        """Return execution records classified as failures."""
        return [record for record in self.read_all("execution") if not self._is_success(record)]

    def get_successes(self) -> list[dict]:
        """Return execution records classified as successes."""
        return [record for record in self.read_all("execution") if self._is_success(record)]

    def _read_all_unlocked(self, memory_type: str) -> list[dict]:
        file_path = self._file_path(memory_type)
        if not file_path.exists():
            self._atomic_write(file_path, [])
            logger.info(
                "memory_read_completed",
                {"type": memory_type, "id": "n/a", "status": "initialized"},
            )
            return []

        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"Memory file {file_path} must contain a JSON list")
        return data

    def _ensure_layout(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for memory_type in _FILE_BY_TYPE:
            path = self._file_path(memory_type)
            if not path.exists():
                self._atomic_write(path, [])

    def _execution_sort_key(self, payload: dict) -> tuple[datetime, str]:
        timestamp = payload.get("timestamp")
        parsed = self._parse_timestamp(timestamp)
        memory_id = str(payload.get("id", ""))
        return parsed, memory_id

    def _parse_timestamp(self, raw_value: object) -> datetime:
        if isinstance(raw_value, datetime):
            if raw_value.tzinfo is None:
                return raw_value.replace(tzinfo=UTC)
            return raw_value.astimezone(UTC)
        if isinstance(raw_value, str):
            try:
                parsed = datetime.fromisoformat(raw_value)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC)
            except ValueError:
                return datetime.min.replace(tzinfo=UTC)
        return datetime.min.replace(tzinfo=UTC)

    def _is_success(self, payload: dict) -> bool:
        if isinstance(payload.get("success"), bool):
            return bool(payload.get("success"))

        status = str(payload.get("status", "")).lower()
        if status in {"success", "completed"}:
            return True
        if status in {"failure", "failed", "error"}:
            return False

        data = payload.get("data")
        if isinstance(data, dict):
            data_status = str(data.get("status", "")).lower()
            if data_status in {"success", "completed"}:
                return True
            if data_status in {"failure", "failed", "error"}:
                return False

            execution_record = data.get("execution_record")
            if isinstance(execution_record, dict) and isinstance(execution_record.get("success"), bool):
                return bool(execution_record.get("success"))

        return False

    def _file_path(self, memory_type: str) -> Path:
        if memory_type not in _FILE_BY_TYPE:
            raise ValueError(f"Unsupported memory type: {memory_type!r}")
        return self.base_dir / _FILE_BY_TYPE[memory_type]

    def _atomic_write(self, path: Path, payload: list[dict]) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        temp_path.replace(path)
