"""Tests for Agent 28 deployment context injection boundary."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.deployment.context_injector import build_deployment_context
from app.deployment.deployment_context import DeploymentContext
from app.execution.models import ExecutionStatus, ExecutionTask
from app.execution.runner import run_plan
from app.planning.models import ExecutionGroup, ExecutionPlan, PlanMetadata, TaskNode


def make_plan() -> ExecutionPlan:
    node = TaskNode(id="task-1", description="Task", dependencies=[])
    return ExecutionPlan(
        ordered_tasks=[node],
        execution_groups=[ExecutionGroup(group_id=0, task_ids=[node.id])],
        metadata=PlanMetadata(total_tasks=1, has_cycles=False),
    )


def make_context_inputs() -> tuple[dict, dict]:
    return (
        {
            "name": "staging",
            "region": "us-east-1",
            "provider_type": "mock",
            "credentials_ref": "iam://staging-role",
        },
        {
            "variables": {
                "services": ["api", "worker"],
                "retries": 2,
            },
            "metadata": {
                "execution_id": "exec-028",
                "trigger": "test",
            },
        },
    )


def test_context_is_deeply_immutable() -> None:
    resolved_env, config = make_context_inputs()
    context = build_deployment_context(resolved_env, config)

    assert isinstance(context.environment, Mapping)

    with pytest.raises(TypeError):
        context.environment["name"] = "prod"  # type: ignore[index]

    with pytest.raises(TypeError):
        context.variables["services"] += ("admin",)  # type: ignore[index]


def test_context_is_deterministic_for_same_input() -> None:
    resolved_env, config = make_context_inputs()

    first = build_deployment_context(resolved_env, config)
    second = build_deployment_context(resolved_env, config)

    assert first == second
    assert hash(first) == hash(second)


def test_injector_copies_inputs_before_freezing() -> None:
    resolved_env, config = make_context_inputs()
    context = build_deployment_context(resolved_env, config)

    resolved_env["name"] = "prod"
    config["variables"]["services"].append("admin")
    config["metadata"]["execution_id"] = "mutated"

    assert context.environment_name == "staging"
    assert context.services == ("api", "worker")
    assert context.execution_id == "exec-028"


def test_execution_runner_requires_only_deployment_context_for_injection() -> None:
    plan = make_plan()
    observed_context: list[ExecutionTask] = []

    def handler(task: ExecutionTask) -> str:
        observed_context.append(task)
        return "ok"

    report = run_plan(
        plan,
        handlers={"task-1": handler},
        deployment_context=build_deployment_context(*make_context_inputs()),
    )

    assert report.status == ExecutionStatus.COMPLETED
    assert len(observed_context) == 1


def test_execution_runner_cannot_access_raw_config_object() -> None:
    plan = make_plan()
    resolved_env, config = make_context_inputs()
    report = run_plan(
        plan,
        deployment_context=build_deployment_context(resolved_env, config),
    )

    config["variables"]["services"].append("late-mutation")

    assert report.status == ExecutionStatus.COMPLETED


def test_injection_integrity_preserves_context_values() -> None:
    context = build_deployment_context(*make_context_inputs())

    assert isinstance(context, DeploymentContext)
    assert context.environment_name == "staging"
    assert context.region == "us-east-1"
    assert context.provider_type == "mock"
    assert context.credentials_ref == "iam://staging-role"
    assert context.services == ("api", "worker")
    assert context.execution_id == "exec-028"