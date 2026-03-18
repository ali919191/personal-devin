"""Tests for Agent 04 Memory System."""

from pathlib import Path

from app.memory.memory_store import MemoryStore
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService


def make_service(tmp_path: Path) -> MemoryService:
    store = MemoryStore(base_dir=tmp_path / "data" / "memory")
    repo = MemoryRepository(store=store)
    return MemoryService(repository=repo)


def test_save_and_retrieve_execution(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    saved = service.log_execution(
        status="completed",
        total_tasks=3,
        completed_tasks=3,
        failed_tasks=0,
        skipped_tasks=0,
        metadata={"plan": "p1"},
    )

    fetched = service._repository.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.type == "execution"
    assert fetched.data["status"] == "completed"


def test_failure_logging_and_retrieval(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.log_failure("runner", "dependency_failed:t1", {"task_id": "t2"})
    failures = service.get_failures()

    assert len(failures) == 1
    assert failures[0].data["source"] == "runner"
    assert failures[0].data["error"] == "dependency_failed:t1"


def test_query_filtering(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.log_task("t1", status="completed", output="ok")
    service.log_task("t2", status="failed", error="boom")

    completed = service._repository.query({"type": "task", "data.status": "completed"})
    failed = service._repository.query({"type": "task", "data.status": "failed"})

    assert len(completed) == 1
    assert completed[0].data["task_id"] == "t1"
    assert len(failed) == 1
    assert failed[0].data["task_id"] == "t2"


def test_file_persistence_append_only(tmp_path: Path) -> None:
    base_dir = tmp_path / "data" / "memory"

    service1 = MemoryService(repository=MemoryRepository(store=MemoryStore(base_dir=base_dir)))
    first = service1.log_decision("retry", "transient failure", {"attempt": 1})

    service2 = MemoryService(repository=MemoryRepository(store=MemoryStore(base_dir=base_dir)))
    second = service2.log_decision("fallback", "max retries reached", {"attempt": 2})

    all_decisions = service2._repository.get_all("decision")
    assert len(all_decisions) == 2
    assert all_decisions[0].id == first.id
    assert all_decisions[1].id == second.id


def test_get_recent_returns_latest_first(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.log_execution("completed", 1, 1, 0, 0)
    service.log_task("t1", "completed", output="ok")
    service.log_failure("executor", "boom")

    recent = service.get_recent(limit=2)
    assert len(recent) == 2
    assert recent[0].timestamp >= recent[1].timestamp


def test_get_patterns_counts_failure_messages(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.log_failure("runner", "dependency_failed:t1")
    service.log_failure("runner", "dependency_failed:t1")
    service.log_failure("runner", "timeout")

    patterns = service.get_patterns()
    assert patterns[0] == {"error": "dependency_failed:t1", "count": 2}
    assert patterns[1] == {"error": "timeout", "count": 1}
