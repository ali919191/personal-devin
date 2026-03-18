from dataclasses import asdict

from app.improvement.engine import ImprovementEngine
from app.improvement.models import ImprovementAction, SignalRecord


def test_signal_immutability() -> None:
    engine = ImprovementEngine()
    signals = [
        SignalRecord(signal_type="low_success_rate", signal_value="0.42"),
        SignalRecord(signal_type="high_latency", signal_value="1200ms"),
    ]
    before = [asdict(signal) for signal in signals]

    _ = engine.select_actions(signals)

    after = [asdict(signal) for signal in signals]
    assert after == before


def test_deterministic_behavior() -> None:
    engine = ImprovementEngine()
    signals = [
        SignalRecord(signal_type="low_success_rate", signal_value="0.40"),
        SignalRecord(signal_type="high_latency", signal_value="900ms"),
    ]

    first = engine.select_actions(signals)
    second = engine.select_actions(signals)

    assert first == second


def test_registry_mapping_known_signal() -> None:
    engine = ImprovementEngine()
    signals = [SignalRecord(signal_type="frequent_failures", signal_value="many")]

    actions = engine.select_actions(signals)

    assert actions == [
        ImprovementAction(
            action_type="increase_logging",
            source_signal="frequent_failures",
        )
    ]


def test_unknown_signal_handling() -> None:
    engine = ImprovementEngine()
    signals = [SignalRecord(signal_type="unknown_signal", signal_value="n/a")]

    actions = engine.select_actions(signals)

    assert actions == []


def test_stable_ordering_matches_input_sequence() -> None:
    engine = ImprovementEngine()
    signals = [
        SignalRecord(signal_type="high_latency", signal_value="1100ms"),
        SignalRecord(signal_type="low_success_rate", signal_value="0.45"),
        SignalRecord(signal_type="frequent_failures", signal_value="7"),
    ]

    actions = engine.select_actions(signals)

    assert [action.action_type for action in actions] == [
        "optimize_execution",
        "retry_strategy",
        "increase_logging",
    ]
    assert [action.source_signal for action in actions] == [
        "high_latency",
        "low_success_rate",
        "frequent_failures",
    ]


def test_no_signal_creation() -> None:
    engine = ImprovementEngine()
    signals = [
        SignalRecord(signal_type="low_success_rate", signal_value="0.3"),
        SignalRecord(signal_type="high_latency", signal_value="1000ms"),
        SignalRecord(signal_type="unknown_signal", signal_value="x"),
    ]

    actions = engine.select_actions(signals)
    input_signal_types = [signal.signal_type for signal in signals]

    assert len(actions) == 2
    assert all(action.source_signal in input_signal_types for action in actions)


def test_apply_marks_all_actions_as_applied() -> None:
    engine = ImprovementEngine()
    actions = [
        ImprovementAction(action_type="retry_strategy", source_signal="low_success_rate"),
        ImprovementAction(action_type="optimize_execution", source_signal="high_latency"),
    ]

    results = engine.apply(actions)

    assert [result.action_type for result in results] == [
        "retry_strategy",
        "optimize_execution",
    ]
    assert [result.status for result in results] == ["applied", "applied"]


def test_duplicate_signals_produce_duplicate_actions() -> None:
    engine = ImprovementEngine()
    signals = [
        SignalRecord(signal_type="low_success_rate", signal_value="0.3"),
        SignalRecord(signal_type="low_success_rate", signal_value="0.3"),
    ]

    actions = engine.select_actions(signals)

    assert len(actions) == 2
