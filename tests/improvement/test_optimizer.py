from app.improvement.models import Pattern
from app.improvement.optimizer import Optimizer


def test_optimizer_generates_expected_actions() -> None:
    optimizer = Optimizer()
    patterns = [
        Pattern(type="repeated_failure", location="execution.step_3", frequency=0.7, severity="high", evidence_count=7),
        Pattern(type="redundant_retries", location="execution.step_3", frequency=0.4, severity="medium", evidence_count=4),
    ]

    actions = optimizer.generate(patterns)

    assert actions[0].target == "execution.retry_limit"
    assert actions[0].change == "decrease_retry_limit_by_one"
    assert actions[1].target == "planning.strategy"
    assert actions[1].change == "increase_validation_before_execution"


def test_optimizer_is_deterministic() -> None:
    optimizer = Optimizer()
    patterns = [
        Pattern(type="tool_misuse", location="execution.policy_violation", frequency=0.5, severity="high", evidence_count=3),
    ]

    assert optimizer.generate(patterns) == optimizer.generate(patterns)
