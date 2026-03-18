"""High-level memory service API for Agent 04."""

from datetime import UTC, datetime

from app.memory.models import DecisionMemory, ExecutionMemory, FailureMemory, TaskMemory
from app.memory.repository import MemoryRepository


class MemoryService:
    """Business-level API for logging and retrieving memory records."""

    def __init__(self, repository: MemoryRepository | None = None) -> None:
        self._repository = repository or MemoryRepository()

    def log_execution(
        self,
        status: str,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int,
        skipped_tasks: int,
        metadata: dict | None = None,
    ) -> ExecutionMemory:
        record = ExecutionMemory(
            id=self._next_id("execution"),
            timestamp=datetime.now(UTC),
            data={
                "status": status,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "skipped_tasks": skipped_tasks,
                "metadata": metadata or {},
            },
        )
        self._repository.save(record)
        return record

    def log_task(
        self,
        task_id: str,
        status: str,
        output: str | None = None,
        error: str | None = None,
        skip_reason: str | None = None,
    ) -> TaskMemory:
        record = TaskMemory(
            id=self._next_id("task"),
            timestamp=datetime.now(UTC),
            data={
                "task_id": task_id,
                "status": status,
                "output": output,
                "error": error,
                "skip_reason": skip_reason,
            },
        )
        self._repository.save(record)
        return record

    def log_failure(
        self,
        source: str,
        error: str,
        context: dict | None = None,
    ) -> FailureMemory:
        record = FailureMemory(
            id=self._next_id("failure"),
            timestamp=datetime.now(UTC),
            data={
                "source": source,
                "error": error,
                "context": context or {},
            },
        )
        self._repository.save(record)
        return record

    def log_decision(
        self,
        decision: str,
        reason: str,
        context: dict | None = None,
    ) -> DecisionMemory:
        record = DecisionMemory(
            id=self._next_id("decision"),
            timestamp=datetime.now(UTC),
            data={
                "decision": decision,
                "reason": reason,
                "context": context or {},
            },
        )
        self._repository.save(record)
        return record

    def get_recent(self, limit: int) -> list:
        all_records = []
        for memory_type in ("execution", "task", "failure", "decision"):
            all_records.extend(self._repository.get_all(memory_type))

        sorted_records = sorted(
            all_records,
            key=lambda r: (r.timestamp, r.id),
            reverse=True,
        )
        return sorted_records[:limit]

    def get_failures(self) -> list[FailureMemory]:
        return [
            memory
            for memory in self._repository.get_all("failure")
            if isinstance(memory, FailureMemory)
        ]

    def get_patterns(self) -> list[dict]:
        failures = self.get_failures()
        counter: dict[str, int] = {}
        for failure in failures:
            key = str(failure.data.get("error", "unknown"))
            counter[key] = counter.get(key, 0) + 1

        patterns = [
            {"error": error, "count": count}
            for error, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        ]
        return patterns

    def _next_id(self, memory_type: str) -> str:
        existing = self._repository.get_all(memory_type)
        return f"{memory_type}-{len(existing) + 1:06d}"
