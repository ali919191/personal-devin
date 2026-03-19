"""Tests for Agent 15 Analyzer: execution and failure record extraction."""

from datetime import UTC, datetime

from app.self_improvement.analyzer import Analyzer
from app.self_improvement.models import ExecutionRecord, FailureRecord


class _Store:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    def get_recent(self, limit: int) -> list[dict]:
        return self._records[:limit]


def _exec(record_id: str, status: str, latency: float, failed: int, total: int) -> dict:
    return {
        "id": record_id,
        "type": "execution",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "data": {
            "status": status,
            "latency": latency,
            "failed_tasks": failed,
            "total_tasks": total,
        },
    }


def _failure(record_id: str, error: str, source: str = "agent_loop") -> dict:
    return {
        "id": record_id,
        "type": "failure",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "data": {"error": error, "source": source},
    }


def test_load_executions_returns_typed_records():
    store = _Store([_exec("e1", "success", 1.0, 0, 3), _exec("e2", "failure", 2.5, 2, 3)])
    records = Analyzer().load_executions(store)
    assert len(records) == 2
    assert all(isinstance(r, ExecutionRecord) for r in records)


def test_load_executions_ignores_non_execution_records():
    store = _Store([_failure("f1", "timeout"), _exec("e1", "success", 1.0, 0, 3)])
    records = Analyzer().load_executions(store)
    assert len(records) == 1
    assert records[0].record_id == "e1"


def test_load_failures_returns_typed_records():
    store = _Store([_failure("f1", "timeout"), _failure("f2", "oom")])
    records = Analyzer().load_failures(store)
    assert len(records) == 2
    assert all(isinstance(r, FailureRecord) for r in records)


def test_execution_record_success_rate():
    store = _Store([_exec("e1", "success", 1.0, 1, 4)])
    records = Analyzer().load_executions(store)
    assert records[0].success_rate == 0.75


def test_execution_record_full_success_rate():
    store = _Store([_exec("e1", "success", 1.0, 0, 5)])
    records = Analyzer().load_executions(store)
    assert records[0].success_rate == 1.0


def test_empty_store_returns_empty_lists():
    store = _Store([])
    assert Analyzer().load_executions(store) == []
    assert Analyzer().load_failures(store) == []


def test_timestamp_is_utc_aware():
    store = _Store([_exec("e1", "success", 1.0, 0, 2)])
    records = Analyzer().load_executions(store)
    ts = records[0].timestamp
    assert ts is not None
    assert ts.tzinfo is not None


def test_load_respects_limit():
    store = _Store([_exec(f"e{i}", "success", 1.0, 0, 1) for i in range(10)])
    records = Analyzer().load_executions(store, limit=3)
    assert len(records) == 3
