"""Serialization helpers for memory records."""

from datetime import datetime

from app.memory.models import (
    DecisionMemory,
    ExecutionRecord,
    ExecutionMemory,
    FailureMemory,
    MemoryRecord,
    TaskMemory,
)

_MEMORY_MODEL_BY_TYPE = {
    "execution": ExecutionMemory,
    "task": TaskMemory,
    "failure": FailureMemory,
    "decision": DecisionMemory,
}


class MemorySerializer:
    """Converts memory models to/from JSON-safe dictionaries."""

    @staticmethod
    def to_dict(record: MemoryRecord) -> dict:
        payload = record.model_dump()
        payload["timestamp"] = record.timestamp.isoformat()
        return payload

    @staticmethod
    def execution_record_to_dict(record: ExecutionRecord) -> dict:
        payload = record.model_dump()
        payload["timestamp"] = record.timestamp.isoformat()
        return payload

    @staticmethod
    def from_dict(payload: dict) -> MemoryRecord:
        memory_type = payload.get("type")
        if memory_type not in _MEMORY_MODEL_BY_TYPE:
            raise ValueError(f"Unsupported memory type: {memory_type!r}")

        normalized = dict(payload)
        timestamp = normalized.get("timestamp")
        if isinstance(timestamp, str):
            normalized["timestamp"] = datetime.fromisoformat(timestamp)

        model = _MEMORY_MODEL_BY_TYPE[memory_type]
        return model.model_validate(normalized)

    @staticmethod
    def execution_record_from_dict(payload: dict) -> ExecutionRecord:
        normalized = dict(payload)
        timestamp = normalized.get("timestamp")
        if isinstance(timestamp, str):
            normalized["timestamp"] = datetime.fromisoformat(timestamp)
        return ExecutionRecord.model_validate(normalized)

    @staticmethod
    def to_list(records: list[MemoryRecord]) -> list[dict]:
        return [MemorySerializer.to_dict(record) for record in records]

    @staticmethod
    def from_list(payloads: list[dict]) -> list[MemoryRecord]:
        return [MemorySerializer.from_dict(payload) for payload in payloads]
