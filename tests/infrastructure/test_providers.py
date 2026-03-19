"""Tests for infrastructure provider behavior and determinism."""

from __future__ import annotations

from dataclasses import replace

from app.core.deployment_context import DeploymentContext
from app.execution.models import ExecutionStatus
from app.execution.runner import run_plan
from app.infrastructure.base import DefaultInfrastructureContext, InfrastructureResult
from app.infrastructure.providers.aks import AKSInfrastructureProvider
from app.infrastructure.providers.local import LocalInfrastructureProvider
from app.infrastructure.providers.mock import MockInfrastructureProvider
from app.planning.models import ExecutionGroup, ExecutionPlan, PlanMetadata, TaskNode


def make_context(environment: str = "local") -> DeploymentContext:
    return DeploymentContext(
        execution_id="exec-001",
        environment=environment,
        artifacts={"image": "example:1"},
        services=["api", "worker"],
        config={"replicas": 2},
        metadata={"test": True},
    )


def make_plan() -> ExecutionPlan:
    node = TaskNode(id="task-1", description="Task", dependencies=[])
    return ExecutionPlan(
        ordered_tasks=[node],
        execution_groups=[ExecutionGroup(group_id=0, task_ids=["task-1"])],
        metadata=PlanMetadata(total_tasks=1, has_cycles=False),
    )


def test_local_provider_is_deterministic() -> None:
    provider = LocalInfrastructureProvider()
    context = make_context("local")

    first = provider.deploy(context)
    second = provider.deploy(context)

    assert first == second
    assert first.state == "deployed"
    assert first.provider == "local"


def test_aks_provider_simulates_deployment_without_external_sdk() -> None:
    provider = AKSInfrastructureProvider()
    context = make_context("aks")

    response = provider.deploy(context)

    assert response.provider == "aks"
    assert response.details["simulation"] is True
    assert response.details["cluster"] == "aks-exec-001"


def test_mock_provider_is_fully_stable() -> None:
    provider = MockInfrastructureProvider()
    context = make_context("mock")

    first = provider.status(context)
    second = provider.status(context)

    assert first == second
    assert first.details["stable"] is True


def test_providers_do_not_mutate_context() -> None:
    context = make_context("local")
    before = context.to_dict()

    LocalInfrastructureProvider().deploy(context)
    AKSInfrastructureProvider().status(replace(context, environment="aks"))
    MockInfrastructureProvider().destroy(replace(context, environment="mock"))

    after = context.to_dict()
    assert after == before


def test_execution_runner_uses_infrastructure_provider_abstraction() -> None:
    plan = make_plan()
    context = make_context("mock")

    report = run_plan(plan, infrastructure_context=context)

    assert report.status == ExecutionStatus.COMPLETED
    assert report.completed_tasks == 1


def test_execution_always_routes_through_provider_even_without_explicit_context() -> None:
    """Execution must always go through a provider; local is the default fallback."""
    plan = make_plan()

    report = run_plan(plan)

    assert report.status == ExecutionStatus.COMPLETED
    assert report.completed_tasks == 1


def test_default_infrastructure_context_satisfies_protocol() -> None:
    ctx = DefaultInfrastructureContext()
    provider = LocalInfrastructureProvider()

    result = provider.deploy(ctx)

    assert result.state == "deployed"
    assert result.provider == "local"
    assert result.environment == "local"


def test_infrastructure_result_carries_failure_fields() -> None:
    result = InfrastructureResult(
        action="deploy",
        provider="local",
        environment="local",
        state="failed",
        error="simulated_failure",
    )

    assert result.state == "failed"
    assert result.error == "simulated_failure"


def test_infrastructure_result_error_is_none_on_success() -> None:
    result = InfrastructureResult(
        action="deploy",
        provider="mock",
        environment="mock",
        state="deployed",
    )

    assert result.error is None


def test_providers_do_not_mutate_context() -> None:
    context = make_context("local")
    before = context.to_dict()

    LocalInfrastructureProvider().deploy(context)
    AKSInfrastructureProvider().status(replace(context, environment="aks"))
    MockInfrastructureProvider().destroy(replace(context, environment="mock"))

    after = context.to_dict()
    assert after == before


def test_execution_runner_uses_infrastructure_provider_abstraction() -> None:
    plan = make_plan()
    context = make_context("mock")

    report = run_plan(plan, infrastructure_context=context)

    assert report.status == ExecutionStatus.COMPLETED
    assert report.completed_tasks == 1
