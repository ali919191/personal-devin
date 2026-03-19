from __future__ import annotations

from copy import deepcopy

from app.analysis import AnalysisRegistry, Analyzer, FailurePattern, PatternDetector, Recommendation, RecommendationEngine


def _sample_execution_logs() -> list[dict]:
    return [
        {
            "task_id": "plan",
            "status": "completed",
            "duration_ms": 1200,
            "retry_count": 0,
            "source": "execution",
        },
        {
            "task_id": "execute",
            "status": "failed",
            "duration_ms": 3200,
            "retry_count": 2,
            "error": "timeout",
            "source": "execution",
        },
        {
            "task_id": "execute",
            "status": "failed",
            "duration_ms": 2900,
            "retry_count": 3,
            "error": "timeout",
            "source": "execution",
        },
        {
            "task_id": "persist",
            "status": "completed",
            "duration_ms": 800,
            "retry_count": 0,
            "source": "execution",
        },
    ]


def _sample_memory_records() -> list[dict]:
    return [
        {
            "id": "failure-000001",
            "type": "failure",
            "timestamp": "2026-03-18T10:00:00+00:00",
            "data": {
                "source": "executor",
                "error": "timeout",
                "context": {"task_id": "execute"},
            },
        },
        {
            "id": "failure-000002",
            "type": "failure",
            "timestamp": "2026-03-18T10:01:00+00:00",
            "data": {
                "source": "executor",
                "error": "timeout",
                "context": {"task_id": "execute"},
            },
        },
    ]


def test_pattern_detection_correctness() -> None:
    detector = PatternDetector()
    logs = _sample_execution_logs()
    memory = _sample_memory_records()

    failure_patterns = detector.detect_failure_patterns(logs, memory)
    inefficiencies = detector.detect_inefficiencies(logs)
    retry_loops = detector.detect_retry_loops(logs)

    assert len(failure_patterns) >= 2
    assert failure_patterns[0].signature == "timeout"
    assert "low_success_rate" in inefficiencies
    assert "retry_activity_detected" in inefficiencies
    assert "execute" in retry_loops


def test_recommendation_generation() -> None:
    engine = RecommendationEngine()
    patterns = [
        FailurePattern(
            pattern_id="failure-001",
            source="execution",
            signature="timeout",
            count=3,
        )
    ]
    inefficiencies = ["low_success_rate", "retry_activity_detected"]
    retry_loops = ["execute"]

    recommendations = engine.generate(patterns, inefficiencies, retry_loops)

    assert recommendations
    assert recommendations[0].priority == 1
    ids = [rec.recommendation_id for rec in recommendations]
    assert "stabilize-failure-001" in ids
    assert "improve-success-rate" in ids
    assert "retry-loop-execute" in ids


def test_analysis_no_side_effects() -> None:
    analyzer = Analyzer()
    logs = _sample_execution_logs()
    memory = _sample_memory_records()

    logs_before = deepcopy(logs)
    memory_before = deepcopy(memory)

    report = analyzer.analyze("exec-001", logs, memory)

    assert logs == logs_before
    assert memory == memory_before
    assert report.execution_id == "exec-001"
    assert 0.0 <= report.success_rate <= 1.0
    assert 0.0 <= report.confidence_score <= 1.0


def test_analyzer_deterministic_output() -> None:
    analyzer = Analyzer()
    logs = _sample_execution_logs()
    memory = _sample_memory_records()

    first = analyzer.analyze("exec-002", logs, memory)
    second = analyzer.analyze("exec-002", logs, memory)

    assert first == second


def test_registry_pluggable_architecture() -> None:
    registry = AnalysisRegistry()
    detector = PatternDetector()
    recommendation_engine = RecommendationEngine()

    registry.register_detector("failure_patterns", detector.detect_failure_patterns)
    registry.register_detector("inefficiencies", lambda logs, memory: ["custom_inefficiency"])
    registry.register_detector("retry_loops", lambda logs, memory: [])
    registry.register_recommendation_engine(
        "custom",
        lambda patterns, inefficiencies, retry_loops: [
            Recommendation(
                recommendation_id="custom-reco",
                priority=2,
                title="Custom recommendation",
                action="Apply custom optimization",
                rationale=f"detected:{','.join(sorted(inefficiencies))}",
            )
        ],
    )
    registry.register_recommendation_engine("default", recommendation_engine.generate)

    analyzer = Analyzer(registry=registry)
    report = analyzer.analyze("exec-003", _sample_execution_logs(), _sample_memory_records())

    assert "custom_inefficiency" in report.inefficiencies
    assert any(rec.recommendation_id == "custom-reco" for rec in report.recommendations)
