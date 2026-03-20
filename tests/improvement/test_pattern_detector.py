from app.improvement.models import AnalysisSummary
from app.improvement.pattern_detector import PatternDetector


def test_pattern_detector_detects_repeated_failures_and_retry_patterns() -> None:
    detector = PatternDetector()
    summary = AnalysisSummary(
        total_executions=10,
        failure_rate=0.7,
        retry_patterns={"step_3": 4},
        step_latency={"step_2": 1500.0},
        common_failure_points=["step_3"],
        common_failure_counts={"step_3": 7},
        tool_misuse_patterns={"policy_violation": 2},
    )

    patterns = detector.detect(summary)

    keys = {(pattern.type, pattern.location) for pattern in patterns}
    assert ("repeated_failure", "execution.step_3") in keys
    assert ("redundant_retries", "execution.step_3") in keys
    assert ("inefficient_plan", "execution.step_2") in keys
    assert ("tool_misuse", "execution.policy_violation") in keys


def test_pattern_detector_is_deterministic() -> None:
    detector = PatternDetector()
    summary = AnalysisSummary(
        total_executions=4,
        failure_rate=0.5,
        retry_patterns={"step_2": 2},
        step_latency={"step_2": 1200.0},
        common_failure_points=["step_2"],
        common_failure_counts={"step_2": 2},
        tool_misuse_patterns={},
    )

    first = detector.detect(summary)
    second = detector.detect(summary)

    assert first == second
