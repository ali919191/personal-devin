"""Tests for Agent 07 self-improvement engine."""

from app.agent.self_improvement import SelfImprovementEngine


class StubMemoryService:
    """Deterministic memory stub used for self-improvement tests."""

    def __init__(self, patterns: list[dict] | None = None) -> None:
        self._patterns = patterns or []
        self.decisions: list[dict] = []

    def get_recent(self, limit: int) -> list:
        _ = limit
        return []

    def get_patterns(self) -> list[dict]:
        return [dict(item) for item in self._patterns]

    def log_decision(self, decision: str, reason: str, context: dict | None = None):
        self.decisions.append(
            {
                "decision": decision,
                "reason": reason,
                "context": context or {},
            }
        )
        return self.decisions[-1]


def test_successful_run_analysis() -> None:
    engine = SelfImprovementEngine(memory_service=StubMemoryService())
    run_data = {
        "status": "success",
        "metrics": {"total": 2, "completed": 2, "failed": 0, "skipped": 0},
        "tasks": [
            {"id": "task-1", "status": "completed", "error": None, "skip_reason": None},
            {"id": "task-2", "status": "completed", "error": None, "skip_reason": None},
        ],
    }

    analysis = engine.analyze_run(run_data)

    assert analysis["classification"] == "success"
    assert analysis["failure_causes"] == []
    assert analysis["repeated_patterns"] == []
    assert analysis["summary"]["success_rate"] == 1.0


def test_failure_detection() -> None:
    engine = SelfImprovementEngine(memory_service=StubMemoryService())
    run_data = {
        "status": "failure",
        "metrics": {"total": 2, "completed": 0, "failed": 1, "skipped": 1},
        "tasks": [
            {"id": "task-1", "status": "failed", "error": "boom", "skip_reason": None},
            {
                "id": "task-2",
                "status": "skipped",
                "error": "dependency_failed:task-1",
                "skip_reason": "dependency_failed:task-1",
            },
        ],
    }

    analysis = engine.analyze_run(run_data)

    assert analysis["classification"] == "failure"
    assert analysis["failure_causes"] == ["boom", "dependency_failed:task-1"]
    assert "low_success_rate" in analysis["inefficiencies"]


def test_repeated_pattern_detection() -> None:
    memory = StubMemoryService(patterns=[{"error": "boom", "count": 3}])
    engine = SelfImprovementEngine(memory_service=memory)
    run_data = {
        "status": "failure",
        "metrics": {"total": 1, "completed": 0, "failed": 1, "skipped": 0},
        "tasks": [
            {"id": "task-1", "status": "failed", "error": "boom", "skip_reason": None},
        ],
    }

    analysis = engine.analyze_run(run_data)

    assert analysis["repeated_patterns"] == [{"error": "boom", "count": 3}]


def test_deterministic_output_validation() -> None:
    memory = StubMemoryService(patterns=[{"error": "boom", "count": 2}])
    engine = SelfImprovementEngine(memory_service=memory)
    run_data = {
        "goal": "Run tests",
        "status": "partial",
        "metrics": {"total": 3, "completed": 2, "failed": 1, "skipped": 0},
        "tasks": [
            {"id": "task-1", "status": "completed", "error": None, "skip_reason": None},
            {"id": "task-2", "status": "completed", "error": None, "skip_reason": None},
            {"id": "task-3", "status": "failed", "error": "boom", "skip_reason": None},
        ],
    }

    first = engine.process(run_data)
    second = engine.process(run_data)

    assert first == second


def test_empty_input_handling() -> None:
    memory = StubMemoryService()
    engine = SelfImprovementEngine(memory_service=memory)

    result = engine.process({})

    assert result["analysis"]["classification"] == "unknown"
    assert result["analysis"]["inefficiencies"] == ["missing_run_data"]
    assert len(result["insights"]) >= 1
    assert len(result["suggestions"]) >= 1
    assert len(memory.decisions) == 3
