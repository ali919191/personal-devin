"""Deterministic append-only file storage for memory records."""

import json
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
