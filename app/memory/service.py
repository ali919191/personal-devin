"""High-level memory service API for Agent 04."""

from datetime import UTC, datetime
from collections.abc import Callable
from typing import Any

from app.core.logger import get_logger
from app.memory.feedback_engine import FeedbackEngine
from app.memory.models import DecisionMemory, ExecutionMemory, FailureMemory, TaskMemory
from app.memory.models import ExecutionRecord
from app.memory.repository import MemoryRepository
from app.memory.serializer import MemorySerializer

logger = get_logger(__name__)


class MemoryService:
    """Business-level API for logging and retrieving memory records."""

    def __init__(
        self,
        repository: MemoryRepository | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository or MemoryRepository()
        self._feedback_engine = FeedbackEngine()
        self._now_fn = now_fn or datetime.utcnow

    def set_now_fn(self, now_fn: Callable[[], datetime]) -> None:
        """Override timestamp source for deterministic testability."""
        self._now_fn = now_fn

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

    def store_improvements(self, improvements: list) -> list[DecisionMemory]:
        """Persist approved self-improvement actions as decision records."""
        saved: list[DecisionMemory] = []
        for action in improvements:
            if hasattr(action, "__dataclass_fields__"):
                payload = {field: getattr(action, field) for field in action.__dataclass_fields__}
            elif isinstance(action, dict):
                payload = dict(action)
            else:
                payload = {"action": str(action)}
            record = self.log_decision(
                decision="improvement_action",
                reason="approved by self-improvement policy",
                context={"improvement": payload},
            )
            saved.append(record)
        return saved

    def record_execution(
        self,
        task_id: str,
        input: dict | None = None,
        plan: dict | None = None,
        result: dict | None = None,
        success: bool = False,
        errors: list[str] | None = None,
        metadata: dict | None = None,
        timestamp: datetime | None = None,
    ) -> ExecutionMemory:
        """Record a unified execution payload through the existing memory stream."""
        now_value = timestamp or self._normalize_timestamp(self._now_fn())
        execution_record = ExecutionRecord(
            task_id=task_id,
            input=input or {},
            plan=plan or {},
            result=result or {},
            success=bool(success),
            errors=[str(error) for error in (errors or [])],
            timestamp=now_value,
            metadata=metadata or {},
        )

        payload = MemorySerializer.execution_record_to_dict(execution_record)
        status = "success" if execution_record.success else "failure"

        result_payload = dict(execution_record.result)
        total_tasks = int(result_payload.get("total_tasks", 0))
        failed_tasks = int(result_payload.get("failed_tasks", 0))
        skipped_tasks = int(result_payload.get("skipped_tasks", 0))
        completed_tasks = int(result_payload.get("completed_tasks", 0))

        memory = ExecutionMemory(
            id=self._next_id("execution"),
            timestamp=execution_record.timestamp,
            data={
                "status": status,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "skipped_tasks": skipped_tasks,
                "errors": list(execution_record.errors),
                "metadata": {
                    **dict(execution_record.metadata),
                    "task_id": execution_record.task_id,
                    "input": dict(execution_record.input),
                    "plan": dict(execution_record.plan),
                },
                "execution_record": payload,
            },
        )
        self._repository.save(memory)

        logger.info(
            "execution_recorded",
            {
                "task_id": execution_record.task_id,
                "success": execution_record.success,
                "error_count": len(execution_record.errors),
            },
        )
        return memory

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

    def get_recent_history(self, limit: int) -> list[ExecutionRecord]:
        """Return normalized execution history for feedback analysis."""
        history: list[ExecutionRecord] = []
        all_execution = self._repository.get_all("execution")
        ordered = sorted(all_execution, key=lambda r: (r.timestamp, r.id), reverse=True)
        for memory in ordered[: max(limit, 0)]:
            normalized = self._execution_memory_to_record(memory)
            if normalized is not None:
                history.append(normalized)
        return history

    def get_feedback_context(self, task_id: str) -> dict[str, Any]:
        records = self.get_recent_history(limit=200)
        context = self._feedback_engine.build_context(records)
        context["task_id"] = task_id

        logger.info(
            "feedback_context_built",
            {
                "task_id": task_id,
                "record_count": len(records),
            },
        )
        return context

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

    def _normalize_timestamp(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _execution_memory_to_record(self, memory: ExecutionMemory) -> ExecutionRecord | None:
        raw_record = memory.data.get("execution_record")
        if isinstance(raw_record, dict):
            return MemorySerializer.execution_record_from_dict(raw_record)

        metadata = memory.data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        status = str(memory.data.get("status", "")).lower()
        success = status in {"success", "completed"}

        errors_field = memory.data.get("errors", [])
        if isinstance(errors_field, list):
            errors = [str(value) for value in errors_field if value]
        else:
            errors = []

        if not errors:
            error_value = memory.data.get("error")
            if error_value:
                errors = [str(error_value)]

        result = {
            "status": status,
            "total_tasks": int(memory.data.get("total_tasks", 0)),
            "completed_tasks": int(memory.data.get("completed_tasks", 0)),
            "failed_tasks": int(memory.data.get("failed_tasks", 0)),
            "skipped_tasks": int(memory.data.get("skipped_tasks", 0)),
        }

        return ExecutionRecord(
            task_id=str(metadata.get("task_id") or memory.id),
            input=dict(metadata.get("input", {})) if isinstance(metadata.get("input"), dict) else {},
            plan=dict(metadata.get("plan", {})) if isinstance(metadata.get("plan"), dict) else {},
            result=result,
            success=success,
            errors=errors,
            timestamp=memory.timestamp,
            metadata=dict(metadata),
        )

    def _next_id(self, memory_type: str) -> str:
        existing = self._repository.get_all(memory_type)
        return f"{memory_type}-{len(existing) + 1:06d}"
