from app.agent.loop_controller import LoopController


class MockPlanner:
    def create_plan(self, state):
        return {"step": "test", "history_size": len(state.get("history", []))}


class MockExecutor:
    def __init__(self, succeed_on=2):
        self.counter = 0
        self.succeed_on = succeed_on

    def run(self, plan):
        self.counter += 1
        return {"success": self.counter >= self.succeed_on, "plan": plan}


class MockMemory:
    def __init__(self):
        self.data = []

    def save(self, record):
        self.data.append(record)


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
