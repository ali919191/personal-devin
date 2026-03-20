from app.improvement.models import AnalysisSummary, ImprovementAction, ImprovementPlan
from app.improvement.validator import ImprovementValidator


def _empty_summary() -> AnalysisSummary:
    return AnalysisSummary(
        total_executions=0,
        failure_rate=0.0,
        retry_patterns={},
        step_latency={},
        common_failure_points=[],
        common_failure_counts={},
        tool_misuse_patterns={},
    )


def test_validator_rejects_unsafe_changes() -> None:
    validator = ImprovementValidator()
    actions = [
        ImprovementAction(target="core.contract", change="drop_contract", reason="unsafe"),
        ImprovementAction(target="planning.strategy", change="increase_validation_before_execution", reason="safe"),
    ]

    approved, rejected = validator.validate_actions(actions)

    assert len(approved) == 1
    assert approved[0].target == "planning.strategy"
    assert len(rejected) == 1
    assert rejected[0].target == "core.contract"


def test_validator_filters_plan_actions() -> None:
    validator = ImprovementValidator()
    plan = ImprovementPlan(
        version="agent-33-v1",
        analysis=_empty_summary(),
        patterns=[],
        actions=[
            ImprovementAction(target="execution.retry_limit", change="decrease_retry_limit_by_one", reason="safe"),
            ImprovementAction(target="core.orchestrator", change="remove_module", reason="unsafe"),
        ],
    )

    validated = validator.validate(plan)

    assert len(validated.actions) == 1
    assert len(validated.rejected_actions) == 1
