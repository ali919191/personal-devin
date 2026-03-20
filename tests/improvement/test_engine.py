from datetime import UTC, datetime

from app.improvement.engine import ImprovementEngine


class StubMemory:
    def __init__(self) -> None:
        self.records = [
            {
                "success": False,
                "decision": "retry_same",
                "current_step": {"id": "step_3"},
                "result": {"duration_ms": 1200, "error_type": "runtime_error"},
                "classification": {"error_type": "runtime_error"},
            },
            {
                "success": False,
                "decision": "retry_same",
                "current_step": {"id": "step_3"},
                "result": {"duration_ms": 1500, "error_type": "policy_violation"},
                "classification": {"error_type": "policy_violation"},
            },
            {
                "success": True,
                "decision": "advance_step",
                "current_step": {"id": "step_1"},
                "result": {"duration_ms": 150},
            },
            {
                "success": False,
                "decision": "retry_same",
                "current_step": {"id": "step_3"},
                "result": {"duration_ms": 1300, "error_type": "runtime_error"},
                "classification": {"error_type": "runtime_error"},
            },
        ]
        self.decision_events: list[dict] = []

    def read_all(self, memory_type: str):
        if memory_type == "execution":
            return list(self.records)
        if memory_type == "decision":
            return list(self.decision_events)
        return []

    def append(self, memory_type: str, payload: dict) -> None:
        if memory_type == "decision":
            self.decision_events.append(dict(payload))


def test_engine_generates_validated_plan_and_logs_events() -> None:
    engine = ImprovementEngine()
    memory = StubMemory()

    plan = engine.run(memory)

    assert plan.version == "agent-33-v3"
    assert plan.record is not None
    assert plan.record.version == 1
    assert plan.record.id == "improvement-000001"
    assert len(plan.patterns) >= 1
    assert len(plan.actions) >= 1
    assert all(action.target != "core.contract" for action in plan.actions)
    # Events: applied actions + rejected actions + improvement_record
    expected_events = len(plan.actions) + len(plan.rejected_actions) + 1
    # If on cooldown, add one more event
    cooldown_events = 1 if engine._is_on_cooldown(memory) else 0
    assert len(memory.decision_events) == expected_events + cooldown_events
    assert memory.decision_events[-1]["event"] == "improvement_record"
    assert "impact" in memory.decision_events[-1]
    assert "metrics_before" in memory.decision_events[-1]
    assert "metrics_after" in memory.decision_events[-1]
    assert "rollback_actions" in memory.decision_events[-1]
    assert "accepted" in memory.decision_events[-1]


def test_engine_is_deterministic() -> None:
    fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
    engine = ImprovementEngine(clock=lambda: fixed_time)
    first_memory = StubMemory()
    second_memory = StubMemory()

    first = engine.run(first_memory)
    second = engine.run(second_memory)

    assert first == second


def test_engine_versions_increment_from_history() -> None:
    fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
    engine = ImprovementEngine(clock=lambda: fixed_time)
    memory = StubMemory()
    memory.decision_events.append({"event": "improvement_record", "version": 3})

    plan = engine.run(memory)

    assert plan.record is not None
    assert plan.record.version == 4
    assert plan.record.id == "improvement-000004"
