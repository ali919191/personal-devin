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
    assert analysis["failure_classification"] == [
        {"task_id": "task-2", "category": "dependency_failure"},
        {"task_id": "task-1", "category": "execution_error"},
    ]
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

    assert {"kind": "failure_type", "value": "boom", "count": 3} in analysis[
        "repeated_patterns"
    ]


def test_repeated_pattern_detection_uses_unique_normalized_signals() -> None:
    memory = StubMemoryService(
        patterns=[
            {"error": "boom", "count": 2},
            {"error": "boom", "count": 2},
            {"error": " boom ", "count": 9},
        ]
    )
    engine = SelfImprovementEngine(memory_service=memory)
    run_data = {
        "status": "failure",
        "metrics": {"total": 1, "completed": 0, "failed": 1, "skipped": 0},
        "tasks": [
            {"id": "task-1", "status": "failed", "error": "boom", "skip_reason": None},
        ],
    }

    analysis = engine.analyze_run(run_data)

    matches = [
        item
        for item in analysis["repeated_patterns"]
        if item.get("kind") == "failure_type" and item.get("value") == "boom"
    ]

    assert matches == [{"kind": "failure_type", "value": "boom", "count": 9}]


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
    type_order = {
        "failure_pattern": 0,
        "structure_signal": 1,
        "efficiency_signal": 2,
        "warning": 3,
        "optimization": 4,
    }
    assert [insight["type"] for insight in first["insights"]] == sorted(
        [insight["type"] for insight in first["insights"]],
        key=lambda value: type_order[value],
    )
    assert [suggestion["priority"] for suggestion in first["suggestions"]] == sorted(
        [suggestion["priority"] for suggestion in first["suggestions"]],
        key=lambda value: {"high": 0, "medium": 1, "low": 2}[value],
    )


def test_empty_input_handling() -> None:
    memory = StubMemoryService()
    engine = SelfImprovementEngine(memory_service=memory)

    result = engine.process({})

    assert result["analysis"]["classification"] == "unknown"
    assert result["analysis"]["inefficiencies"] == ["missing_run_data"]
    assert len(result["insights"]) >= 1
    assert len(result["suggestions"]) >= 1
    assert len(memory.decisions) == 3
    assert memory.decisions[2]["context"]["type"] == "self_improvement_insight"


def test_confidence_model_is_fixed() -> None:
    engine = SelfImprovementEngine(memory_service=StubMemoryService())
    analysis = {
        "classification": "partial",
        "failure_causes": ["boom"],
        "structure_signals": ["Graph depth = 3 (linear chain)"],
        "efficiency_signals": ["Completion efficiency = 0.67 (medium)"],
        "repeated_patterns": [{"kind": "task_error", "value": "boom", "count": 2}],
        "inefficiencies": ["skipped_tasks_present"],
    }

    insights = engine.generate_insights(analysis)

    confidence_by_type = {insight["type"]: insight["confidence"] for insight in insights}
    assert confidence_by_type["failure_pattern"] == 0.9
    assert confidence_by_type["structure_signal"] == 0.8
    assert confidence_by_type["efficiency_signal"] == 0.75
    assert confidence_by_type["warning"] == 0.7
    assert confidence_by_type["optimization"] == 0.6


def test_inefficiency_detects_repeated_task_retries() -> None:
    engine = SelfImprovementEngine(memory_service=StubMemoryService())
    run_data = {
        "status": "partial",
        "metrics": {"total": 2, "completed": 1, "failed": 1, "skipped": 0},
        "tasks": [
            {
                "id": "task-1",
                "status": "completed",
                "error": None,
                "skip_reason": None,
                "retry_count": 2,
            },
            {
                "id": "task-2",
                "status": "failed",
                "error": "boom",
                "skip_reason": None,
            },
        ],
    }

    analysis = engine.analyze_run(run_data)

    assert "repeated_task_retries" in analysis["inefficiencies"]


def test_success_run_produces_structure_and_efficiency_signals() -> None:
    engine = SelfImprovementEngine(memory_service=StubMemoryService())
    run_data = {
        "status": "success",
        "metrics": {
            "total": 5,
            "completed": 5,
            "failed": 0,
            "skipped": 0,
            "actual_parallelism": 1,
        },
        "tasks": [
            {"id": "A", "status": "completed", "error": None, "skip_reason": None, "dependencies": []},
            {"id": "B", "status": "completed", "error": None, "skip_reason": None, "dependencies": ["A"]},
            {"id": "C", "status": "completed", "error": None, "skip_reason": None, "dependencies": ["B"]},
            {"id": "D", "status": "completed", "error": None, "skip_reason": None, "dependencies": ["C"]},
            {"id": "E", "status": "completed", "error": None, "skip_reason": None, "dependencies": ["D"]},
        ],
    }

    result = engine.process(run_data)

    insight_types = [insight["type"] for insight in result["insights"]]
    insight_messages = [insight["message"] for insight in result["insights"]]

    assert "structure_signal" in insight_types
    assert "efficiency_signal" in insight_types
    assert any("Graph depth = 5 (linear chain)" in message for message in insight_messages)
    assert any("Completion efficiency = 1.00 (high)" in message for message in insight_messages)
    assert all("Run is stable with no immediate optimization flags" != message for message in insight_messages)


def test_wide_success_run_reports_parallelism_gap() -> None:
    engine = SelfImprovementEngine(memory_service=StubMemoryService())
    run_data = {
        "status": "success",
        "metrics": {
            "total": 4,
            "completed": 4,
            "failed": 0,
            "skipped": 0,
            "actual_parallelism": 1,
        },
        "tasks": [
            {"id": "A", "status": "completed", "error": None, "skip_reason": None, "dependencies": []},
            {"id": "B", "status": "completed", "error": None, "skip_reason": None, "dependencies": []},
            {"id": "C", "status": "completed", "error": None, "skip_reason": None, "dependencies": []},
            {"id": "D", "status": "completed", "error": None, "skip_reason": None, "dependencies": []},
        ],
    }

    result = engine.process(run_data)
    insight_messages = [insight["message"] for insight in result["insights"]]

    assert "No parallel execution opportunities utilized" in insight_messages
    assert "Wide graph executed sequentially" in insight_messages
    assert "Execution efficiency: high but non-parallel" in insight_messages
