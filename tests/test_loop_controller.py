from app.agent.loop_controller import LoopController


class MockPlanner:
    def __init__(self):
        self.calls = []

    def create_plan(self, state):
        self.calls.append({"state": dict(state), "context": None})
        return {"step": "test", "history_size": len(state.get("history", []))}


class MockPlannerWithContext:
    def __init__(self):
        self.calls = []

    def create_plan(self, state, context):
        self.calls.append({"state": dict(state), "context": dict(context)})
        return {
            "step": "test",
            "history_size": len(state.get("history", [])),
            "attempt_count": state.get("attempt_count", 0),
            "strategy_hint": state.get("strategy_hint", "none"),
        }


class MultiStepPlanner:
    def create_plan(self, state, context=None):
        return {
            "steps": [
                {"id": "s1", "action": "collect data"},
                {"id": "s2", "action": "apply changes"},
            ],
            "current_step": 0,
        }


class RepairingPlanner(MultiStepPlanner):
    def __init__(self):
        self.repair_calls = []

    def repair_step(self, step, state, context=None):
        self.repair_calls.append({"step": dict(step), "state": dict(state)})
        repaired = dict(step)
        repaired["action"] = f"{step['action']} [repaired]"
        metadata = repaired.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata = dict(metadata)
        metadata["repair_source"] = "planner"
        repaired["metadata"] = metadata
        return repaired


class MockExecutor:
    def __init__(self, succeed_on=2):
        self.counter = 0
        self.succeed_on = succeed_on

    def run(self, plan):
        self.counter += 1
        return {"success": self.counter >= self.succeed_on, "plan": plan}


class SequenceExecutor:
    def __init__(self, sequence):
        self._sequence = list(sequence)
        self._index = 0

    def run(self, plan):
        if self._index >= len(self._sequence):
            return self._sequence[-1]
        result = dict(self._sequence[self._index])
        self._index += 1
        result["plan"] = plan
        return result


class MockMemory:
    def __init__(self):
        self.data = []
        self.retrieve_calls = []

    def save(self, record):
        self.data.append(record)

    def retrieve(self, goal):
        self.retrieve_calls.append(goal)
        return {
            "goal": goal,
            "recent": list(self.data),
            "recent_failures": [item for item in self.data if not item.get("success", False)],
            "attempt_count": len(self.data),
        }


def test_loop_success():
    memory = MockMemory()
    controller = LoopController(
        planner=MockPlanner(),
        executor=MockExecutor(succeed_on=2),
        memory=memory,
        max_iterations=5,
    )

    result = controller.run("test goal")

    assert result["status"] == "success"
    assert result["iterations"] == 2
    assert len(memory.data) == 2
    assert memory.data[0]["decision"] == "retry_same"
    assert memory.data[1]["decision"] == "advance_step"


def test_loop_failure_threshold():
    memory = MockMemory()
    controller = LoopController(
        planner=MockPlanner(),
        executor=MockExecutor(succeed_on=10),
        memory=memory,
        max_iterations=5,
        failure_threshold=2,
    )

    result = controller.run("test goal")

    assert result["status"] == "failed"
    assert result["reason"] == "failure_threshold"
    assert result["iterations"] == 2
    assert len(memory.data) == 2


def test_loop_max_iterations_stop():
    memory = MockMemory()
    controller = LoopController(
        planner=MockPlanner(),
        executor=MockExecutor(succeed_on=10),
        memory=memory,
        max_iterations=3,
        failure_threshold=10,
    )

    result = controller.run("test goal")

    assert result["status"] == "stopped"
    assert result["reason"] == "max_iterations"
    assert result["iterations"] == 3
    assert len(memory.data) == 3


def test_loop_escalates_for_policy_violation():
    planner = MockPlanner()
    memory = MockMemory()
    controller = LoopController(
        planner=planner,
        executor=SequenceExecutor(
            [{"success": False, "error_type": "policy_violation", "retryable": False}]
        ),
        memory=memory,
        max_iterations=5,
        failure_threshold=4,
    )

    result = controller.run("test goal")

    assert result["status"] == "failed"
    assert result["reason"] == "escalated"
    assert result["iterations"] == 1
    assert memory.data[0]["decision"] == "escalate"


def test_loop_passes_feedback_state_and_context_to_planner():
    planner = MockPlannerWithContext()
    memory = MockMemory()
    controller = LoopController(
        planner=planner,
        executor=SequenceExecutor(
            [
                {"success": False, "error_type": "invalid_plan", "retryable": False},
                {"success": True},
            ]
        ),
        memory=memory,
        max_iterations=5,
        failure_threshold=3,
    )

    result = controller.run("test goal")

    assert result["status"] == "success"
    assert len(planner.calls) == 2

    first_state = planner.calls[0]["state"]
    second_state = planner.calls[1]["state"]
    first_context = planner.calls[0]["context"]
    second_context = planner.calls[1]["context"]

    assert first_state["attempt_count"] == 1
    assert second_state["attempt_count"] == 2
    assert second_state["last_error_type"] == "invalid_plan"
    assert second_state["last_failure_reason"] == "invalid_plan"
    assert second_state["last_decision"] == "adjust_plan"
    assert second_state["strategy_hint"].startswith("avoid_previous_plan_pattern:")

    assert first_context["goal"] == "test goal"
    assert second_context["goal"] == "test goal"
    assert len(second_context["recent"]) >= 1


def test_strategy_stats_persisted_in_memory_records():
    planner = MockPlannerWithContext()
    memory = MockMemory()
    controller = LoopController(
        planner=planner,
        executor=SequenceExecutor(
            [
                {"success": False, "error_type": "runtime_error", "retryable": True},
                {"success": False, "error_type": "runtime_error", "retryable": True},
                {"success": True},
            ]
        ),
        memory=memory,
        max_iterations=5,
        failure_threshold=4,
    )

    result = controller.run("test goal")

    assert result["status"] == "success"
    assert len(memory.data) == 3
    assert "strategy_stats" in memory.data[-1]

    rows = memory.data[-1]["strategy_stats"]
    runtime_rows = [row for row in rows if row["pattern"] == "runtime_error"]
    assert len(runtime_rows) >= 1
    assert all("success_rate" in row for row in runtime_rows)


def test_retry_same_confidence_downgrades_after_repeated_failures():
    planner = MockPlannerWithContext()
    memory = MockMemory()
    controller = LoopController(
        planner=planner,
        executor=SequenceExecutor(
            [
                {"success": False, "error_type": "runtime_error", "retryable": True},
                {"success": False, "error_type": "runtime_error", "retryable": True},
                {"success": False, "error_type": "runtime_error", "retryable": True},
            ]
        ),
        memory=memory,
        max_iterations=3,
        failure_threshold=3,
    )

    result = controller.run("test goal")

    assert result["status"] in {"failed", "stopped"}
    retry_rows = [
        row
        for row in memory.data[-1]["strategy_stats"]
        if row["pattern"] == "runtime_error" and row["decision"] == "retry_same"
    ]
    if retry_rows:
        assert retry_rows[0]["confidence"] < 1.0


def test_loop_completes_all_steps_before_success():
    memory = MockMemory()
    controller = LoopController(
        planner=MultiStepPlanner(),
        executor=SequenceExecutor(
            [
                {"success": True},
                {"success": True},
            ]
        ),
        memory=memory,
        max_iterations=5,
        failure_threshold=3,
    )

    result = controller.run("test goal")

    assert result["status"] == "success"
    assert result["iterations"] == 2
    assert result["result"]["steps_completed"] == 2
    assert memory.data[0]["current_step"]["id"] == "s1"
    assert memory.data[1]["current_step"]["id"] == "s2"
    assert memory.data[0]["decision"] == "advance_step"
    assert memory.data[1]["decision"] == "advance_step"


def test_loop_tracks_current_step_failures():
    memory = MockMemory()
    controller = LoopController(
        planner=MultiStepPlanner(),
        executor=SequenceExecutor(
            [
                {"success": False, "error_type": "runtime_error", "retryable": True},
                {"success": True},
                {"success": True},
            ]
        ),
        memory=memory,
        max_iterations=6,
        failure_threshold=4,
    )

    result = controller.run("test goal")

    assert result["status"] == "success"
    assert memory.data[0]["current_step"]["id"] == "s1"
    assert memory.data[0]["decision"] in {"retry_same", "adjust_plan"}
    assert memory.data[1]["current_step"]["id"] == "s1"
    assert memory.data[1]["decision"] == "advance_step"
    assert memory.data[2]["current_step"]["id"] == "s2"


def test_loop_repairs_failing_step_without_resetting_plan():
    planner = RepairingPlanner()
    memory = MockMemory()
    controller = LoopController(
        planner=planner,
        executor=SequenceExecutor(
            [
                {"success": False, "error_type": "runtime_error", "retryable": True},
                {"success": False, "error_type": "runtime_error", "retryable": True},
                {"success": True},
                {"success": True},
            ]
        ),
        memory=memory,
        max_iterations=8,
        failure_threshold=6,
        step_failure_threshold=2,
    )

    result = controller.run("test goal")

    assert result["status"] == "success"
    assert len(planner.repair_calls) >= 1

    repair_record = memory.data[1]
    assert repair_record["decision"] == "repair_step"
    assert repair_record["repair_applied"] is True
    assert repair_record["original_step"]["id"] == "s1"
    assert "[repaired]" in repair_record["repaired_step"]["action"]

    # Ensure we preserved the remaining plan structure and did not reset step 2.
    assert repair_record["plan"]["steps"][1]["id"] == "s2"
    assert repair_record["plan"]["steps"][1]["action"] == "apply changes"
