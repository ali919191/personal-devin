from app.improvement.analyzer import ExecutionAnalyzer


def test_analyzer_computes_failure_retry_and_latency_summary() -> None:
    analyzer = ExecutionAnalyzer()
    records = [
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
            "result": {"duration_ms": 800, "error_type": "policy_violation"},
            "classification": {"error_type": "policy_violation"},
        },
        {
            "success": True,
            "decision": "advance_step",
            "current_step": {"id": "step_1"},
            "result": {"duration_ms": 200},
        },
    ]

    summary = analyzer.analyze(records)

    assert summary.total_executions == 3
    assert summary.failure_rate == 0.6667
    assert summary.retry_patterns["step_3"] == 2
    assert summary.step_latency["step_3"] == 1000.0
    assert summary.common_failure_points[0] == "step_3"
    assert summary.common_failure_counts["step_3"] == 2
    assert summary.tool_misuse_patterns["policy_violation"] == 1
