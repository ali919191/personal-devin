"""Repository abstraction for memory persistence queries."""

from app.core.logger import get_logger
from app.memory.memory_store import MemoryStore
from app.memory.models import MemoryRecord
from app.memory.serializer import MemorySerializer

logger = get_logger(__name__)

_MEMORY_TYPES: tuple[str, ...] = ("execution", "task", "failure", "decision")


class MemoryRepository:
    """Persistence repository with basic query operations."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or MemoryStore()

    def save(self, memory: MemoryRecord) -> None:
        payload = MemorySerializer.to_dict(memory)
        self._store.append(memory.type, payload)
        logger.info(
            "memory_repository_save",
            {"type": memory.type, "id": memory.id, "status": "ok"},
        )

    def get_all(self, memory_type: str) -> list[MemoryRecord]:
        payloads = self._store.read_all(memory_type)
        records = MemorySerializer.from_list(payloads)
        logger.info(
            "memory_repository_get_all",
            {"type": memory_type, "id": "n/a", "status": "ok"},
        )
        return records

    def get_by_id(self, memory_id: str) -> MemoryRecord | None:
        for memory_type in _MEMORY_TYPES:
            for record in self.get_all(memory_type):
                if record.id == memory_id:
                    logger.info(
                        "memory_repository_get_by_id",
                        {"type": record.type, "id": memory_id, "status": "found"},
                    )
                    return record

        logger.info(
            "memory_repository_get_by_id",
            {"type": "n/a", "id": memory_id, "status": "not_found"},
        )
        return None

    def query(self, filters: dict) -> list[MemoryRecord]:
        memory_type = filters.get("type")
        selected_types = (memory_type,) if memory_type else _MEMORY_TYPES

        results: list[MemoryRecord] = []
        for selected_type in selected_types:
            for record in self.get_all(selected_type):
                if self._matches(record, filters):
                    results.append(record)

        logger.info(
            "memory_repository_query",
            {
                "type": str(memory_type or "all"),
                "id": "n/a",
                "status": f"ok:{len(results)}",
            },
        )
        return results

    def _matches(self, record: MemoryRecord, filters: dict) -> bool:
        for key, expected in filters.items():
            if key == "type":
                if record.type != expected:
                    return False
            elif key.startswith("data."):
                data_key = key.split(".", 1)[1]
                if record.data.get(data_key) != expected:
                    return False
            else:
                if getattr(record, key, None) != expected:
                    return False
        return True
