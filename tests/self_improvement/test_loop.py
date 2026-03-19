"""Tests for Agent 15 SelfImprovementLoop: full pipeline integration."""

from app.self_improvement.loop import SelfImprovementLoop, run_self_improvement_loop
from app.self_improvement.models import AdaptationResult, SelfImprovementAdaptation
from app.self_improvement.policy import AdaptationPolicy


class _MemoryStore:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    def get_recent(self, limit: int) -> list[dict]:
        return self._records[:limit]


def _exec_record(record_id: str, latency: float, failed: int = 0, total: int = 4) -> dict:
    return {
        "id": record_id,
        "type": "execution",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "data": {
            "status": "success" if failed == 0 else "failure",
            "latency": latency,
            "failed_tasks": failed,
            "total_tasks": total,
        },
    }


def _failure_record(record_id: str, error: str) -> dict:
    return {
        "id": record_id,
        "type": "failure",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "data": {"error": error, "source": "test"},
    }


def _mixed_store() -> _MemoryStore:
    """Store with repeated failures, high latency, and low success rate."""
    return _MemoryStore([
        *[_failure_record(f"f{i}", "timeout") for i in range(3)],
        _exec_record("e1", 5.5, failed=3, total=4),
        _exec_record("e2", 4.0, failed=3, total=4),
        _exec_record("e3", 1.0, failed=0, total=4),
    ])


def test_full_loop_returns_adaptation_result():
    result = SelfImprovementLoop().run(_mixed_store())
    assert isinstance(result, AdaptationResult)


def test_full_loop_detects_patterns():
    result = SelfImprovementLoop().run(_mixed_store())
    assert len(result.patterns_detected) >= 1


def test_full_loop_generates_adaptations():
    result = SelfImprovementLoop().run(_mixed_store())
    assert len(result.adaptations_generated) >= 1


def test_approved_are_subset_of_generated():
    result = SelfImprovementLoop().run(_mixed_store())
    approved_ids = {a.adaptation_id for a in result.adaptations_approved}
    generated_ids = {a.adaptation_id for a in result.adaptations_generated}
    assert approved_ids.issubset(generated_ids)


def test_approved_plus_rejected_equals_generated():
    result = SelfImprovementLoop().run(_mixed_store())
    assert len(result.adaptations_approved) + len(result.adaptations_rejected) == len(result.adaptations_generated)


def test_all_approved_meet_confidence_threshold():
    policy = AdaptationPolicy(confidence_threshold=0.6)
    result = SelfImprovementLoop(policy=policy).run(_mixed_store())
    for a in result.adaptations_approved:
        assert a.confidence_score >= 0.6


def test_strict_policy_rejects_all_low_confidence():
    policy = AdaptationPolicy(confidence_threshold=0.999)
    result = SelfImprovementLoop(policy=policy).run(_mixed_store())
    assert result.adaptations_approved == []
    assert len(result.adaptations_rejected) == len(result.adaptations_generated)


def test_empty_store_produces_empty_result():
    result = SelfImprovementLoop().run(_MemoryStore([]))
    assert result.patterns_detected == []
    assert result.adaptations_generated == []
    assert result.adaptations_approved == []


def test_deterministic_same_input_same_output():
    store = _mixed_store()
    first = SelfImprovementLoop().run(store)
    second = SelfImprovementLoop().run(store)
    assert first.patterns_detected == second.patterns_detected
    assert first.adaptations_generated == second.adaptations_generated
    assert first.adaptations_approved == second.adaptations_approved


def test_functional_entrypoint_returns_adaptation_result():
    result = run_self_improvement_loop(_mixed_store())
    assert isinstance(result, AdaptationResult)


def test_approved_adaptations_are_typed():
    result = SelfImprovementLoop().run(_mixed_store())
    assert all(isinstance(a, SelfImprovementAdaptation) for a in result.adaptations_approved)
