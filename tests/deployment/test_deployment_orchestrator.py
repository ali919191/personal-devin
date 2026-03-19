import json

import pytest

from app.core.deployment_context import DeploymentContext
from app.deployment.models import DeploymentPlan
from app.deployment.orchestrator import DeploymentOrchestrator


def test_valid_context_generates_expected_deployment_plan() -> None:
    context = DeploymentContext(
        execution_id="exec-001",
        environment="staging",
        artifacts={
            "api": {"image": "api:1.0.0"},
            "worker": {"image": "worker:1.0.0"},
        },
        services=["worker", "api"],
        config={"api": {"replicas": 2}, "worker": {"replicas": 1}},
        metadata={"trigger": "manual"},
    )
    orchestrator = DeploymentOrchestrator()

    plan = orchestrator.generate_plan(context)

    assert isinstance(plan, DeploymentPlan)
    assert plan.execution_id == "exec-001"
    assert plan.environment == "staging"
    assert len(plan.steps) == 4
    assert [step.action for step in plan.steps] == [
        "prepare_environment",
        "deploy_service",
        "deploy_service",
        "verify_deployment",
    ]
    assert plan.steps[1].target == "api"
    assert plan.steps[2].target == "worker"


def test_missing_required_fields_fail() -> None:
    with pytest.raises(TypeError):
        DeploymentContext(  # type: ignore[call-arg]
            execution_id="exec-002",
            environment="prod",
            artifacts={},
            services=["api"],
            config={},
        )

    orchestrator = DeploymentOrchestrator()
    with pytest.raises(TypeError):
        orchestrator.generate_plan({"execution_id": "bad-input"})  # type: ignore[arg-type]


def test_orchestrator_is_deterministic_for_same_input() -> None:
    context = DeploymentContext(
        execution_id="exec-003",
        environment="production",
        artifacts={
            "api": {"image": "api:2.1.0", "digest": "sha256:abc"},
            "worker": {"image": "worker:2.1.0", "digest": "sha256:def"},
        },
        services=["api", "worker"],
        config={"worker": {"replicas": 1}, "api": {"replicas": 3}},
        metadata={"source": "execution-engine"},
    )
    orchestrator = DeploymentOrchestrator()

    first_plan = orchestrator.generate_plan(context)
    second_plan = orchestrator.generate_plan(context)

    assert first_plan.to_dict() == second_plan.to_dict()
    assert first_plan.to_json() == second_plan.to_json()


def test_plan_serialization_is_json_safe() -> None:
    context = DeploymentContext(
        execution_id="exec-004",
        environment="dev",
        artifacts={"default": {"package": "build-004.tar.gz"}},
        services=["api"],
        config={"api": {"replicas": 1}},
        metadata={"request_id": "req-123"},
    )
    orchestrator = DeploymentOrchestrator()

    plan = orchestrator.generate_plan(context)
    serialized = plan.to_json()
    payload = json.loads(serialized)

    assert payload["execution_id"] == "exec-004"
    assert payload["environment"] == "dev"
    assert payload["metadata"]["mode"] == "simulation"
    assert payload["steps"][-1]["action"] == "verify_deployment"
