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
        return []

    def append(self, memory_type: str, payload: dict) -> None:
        if memory_type == "decision":
            self.decision_events.append(dict(payload))


def test_engine_generates_validated_plan_and_logs_events() -> None:
    engine = ImprovementEngine()
    memory = StubMemory()

    plan = engine.run(memory)

    assert plan.version == "agent-33-v1"
    assert len(plan.patterns) >= 1
    assert len(plan.actions) >= 1
    assert all(action.target != "core.contract" for action in plan.actions)
    assert len(memory.decision_events) == len(plan.actions) + len(plan.rejected_actions)
    assert all(event["event"] == "self_improvement_applied" for event in memory.decision_events)


def test_engine_is_deterministic() -> None:
    engine = ImprovementEngine()
    first_memory = StubMemory()
    second_memory = StubMemory()

    first = engine.run(first_memory)
    second = engine.run(second_memory)

    assert first == second
