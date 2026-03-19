"""Tests for Agent 14 self-improvement system."""

from app.self_improvement.engine import SelfImprovementEngine
from app.self_improvement.evaluator import Evaluator
from app.self_improvement.models import EvaluationResult, ImprovementAction
from app.self_improvement.optimizer import Optimizer
from app.self_improvement.policy import ImprovementPolicy


class StubMemoryStore:
    def __init__(self, records: list[dict]) -> None:
        self._records = [dict(item) for item in records]

    def get_recent(self, limit: int) -> list[dict]:
        return [dict(item) for item in self._records[:limit]]


def _sample_records() -> list[dict]:
    return [
        {
            "type": "execution",
            "data": {"status": "success", "latency": 1.2},
        },
        {
            "type": "execution",
            "data": {"status": "failure", "latency": 2.8},
        },
        {
            "type": "failure",
            "data": {"error": "timeout"},
        },
        {
            "type": "task",
            "data": {"task_id": "task-1", "retry_count": 2},
        },
        {
            "type": "decision",
            "data": {"decision": "violation:policy_gate"},
        },
    ]


def test_evaluation_correctness() -> None:
    evaluation = Evaluator().evaluate(_sample_records())

    assert isinstance(evaluation, EvaluationResult)
    assert evaluation.success_rate == 0.5
    assert evaluation.avg_latency == 2.0
    assert evaluation.failure_patterns == ["failure:timeout:1"]
    assert evaluation.retry_patterns == ["retry:task-1:1"]
    assert evaluation.policy_violations == ["policy_violation:violation:policy_gate:1"]


def test_optimization_generation() -> None:
    evaluation = EvaluationResult(
        success_rate=0.5,
        avg_latency=2.5,
        failure_patterns=["failure:timeout:2"],
        retry_patterns=["retry:task-1:2"],
        policy_violations=[],
    )

    actions = Optimizer().optimize(evaluation)

    assert actions
    assert all(isinstance(action, ImprovementAction) for action in actions)
    assert any(action.type == "adjust_policy" for action in actions)
    assert any(action.type == "change_strategy" for action in actions)
    assert any(action.type == "increase_confidence" for action in actions)


def test_policy_filtering() -> None:
    actions = [
        ImprovementAction(type="adjust_policy", target="retry_limit", value=3, confidence=0.85),
        ImprovementAction(type="adjust_policy", target="retry_limit", value=2, confidence=0.7),
        ImprovementAction(type="change_strategy", target="timeout", value=10, confidence=0.65),
        ImprovementAction(type="increase_confidence", target="policy_gate", value="strict", confidence=0.9),
    ]

    approved = ImprovementPolicy(confidence_threshold=0.7).approve(actions)

    assert all(action.confidence >= 0.7 for action in approved)
    assert [action for action in approved if action.target == "retry_limit"] == [
        ImprovementAction(type="adjust_policy", target="retry_limit", value=3, confidence=0.85)
    ]


def test_determinism_same_input_same_output() -> None:
    store = StubMemoryStore(_sample_records())
    engine = SelfImprovementEngine()

    first = engine.run(store)
    second = engine.run(store)

    assert first == second


def test_no_invalid_improvements() -> None:
    low_confidence_records = [
        {
            "type": "execution",
            "data": {"status": "success", "latency": 1.0},
        }
    ]
    store = StubMemoryStore(low_confidence_records)
    engine = SelfImprovementEngine(policy=ImprovementPolicy(confidence_threshold=0.95))

    approved = engine.run(store)

    assert approved == []
