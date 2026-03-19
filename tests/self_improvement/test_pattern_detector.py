"""Tests for Agent 15 PatternDetector: deterministic rule-based detection."""

from app.self_improvement.models import ExecutionRecord, FailureRecord, Pattern
from app.self_improvement.pattern_detector import PatternDetector


def _exec(record_id: str, latency: float, failed: int = 0, total: int = 4) -> ExecutionRecord:
    return ExecutionRecord(
        record_id=record_id,
        status="success" if failed == 0 else "failure",
        latency=latency,
        failed_tasks=failed,
        total_tasks=total,
    )


def _failure(record_id: str, error: str) -> FailureRecord:
    return FailureRecord(record_id=record_id, error=error, source="test")


def test_detects_repeated_failure():
    failures = [_failure(f"f{i}", "timeout") for i in range(3)]
    patterns = PatternDetector().detect([], failures)
    kinds = [p.kind for p in patterns]
    assert "repeated_failure" in kinds


def test_repeated_failure_occurrence_count():
    failures = [_failure(f"f{i}", "oom") for i in range(4)]
    patterns = PatternDetector().detect([], failures)
    rf = next(p for p in patterns if p.kind == "repeated_failure")
    assert rf.occurrence_count == 4


def test_no_pattern_when_failure_below_threshold():
    failures = [_failure("f1", "timeout")]  # only 1 occurrence
    patterns = PatternDetector().detect([], failures)
    assert not any(p.kind == "repeated_failure" for p in patterns)


def test_detects_high_latency():
    executions = [_exec("e1", 5.0), _exec("e2", 4.5)]
    patterns = PatternDetector().detect(executions, [])
    assert any(p.kind == "high_latency" for p in patterns)


def test_no_high_latency_when_all_fast():
    executions = [_exec("e1", 1.0), _exec("e2", 0.5)]
    patterns = PatternDetector().detect(executions, [])
    assert not any(p.kind == "high_latency" for p in patterns)


def test_detects_low_success_rate():
    executions = [_exec(f"e{i}", 1.0, failed=3, total=4) for i in range(3)]
    patterns = PatternDetector().detect(executions, [])
    assert any(p.kind == "low_success_rate" for p in patterns)


def test_no_low_success_rate_when_above_threshold():
    executions = [_exec(f"e{i}", 1.0, failed=0, total=4) for i in range(3)]
    patterns = PatternDetector().detect(executions, [])
    assert not any(p.kind == "low_success_rate" for p in patterns)


def test_output_is_list_of_patterns():
    failures = [_failure(f"f{i}", "boom") for i in range(3)]
    patterns = PatternDetector().detect([], failures)
    assert all(isinstance(p, Pattern) for p in patterns)


def test_deterministic_same_input_produces_same_output():
    executions = [_exec("e1", 5.0), _exec("e2", 1.0, failed=3, total=4)]
    failures = [_failure(f"f{i}", "timeout") for i in range(3)]
    first = PatternDetector().detect(executions, failures)
    second = PatternDetector().detect(executions, failures)
    assert first == second


def test_output_is_sorted():
    executions = [_exec("e1", 5.0), _exec("e2", 1.0, failed=3, total=4)]
    failures = [_failure(f"f{i}", "timeout") for i in range(3)]
    patterns = PatternDetector().detect(executions, failures)
    assert patterns == sorted(patterns, key=lambda p: (p.kind, str(p.signal_value), p.pattern_id))


def test_distinct_errors_produce_separate_patterns():
    failures = [
        *[_failure(f"f{i}", "timeout") for i in range(3)],
        *[_failure(f"g{i}", "oom") for i in range(2)],
    ]
    patterns = PatternDetector().detect([], failures)
    rf_patterns = [p for p in patterns if p.kind == "repeated_failure"]
    # Both "timeout" (3 occurrences) and "oom" (2 occurrences) meet the threshold of 2.
    assert len(rf_patterns) == 2
    signals = {p.signal_value for p in rf_patterns}
    assert signals == {"timeout", "oom"}
