"""Tests for Agent 22 universal environment and context engine."""

import pytest

from app.context.exceptions import (
    InvalidEnvironmentConfigurationError,
    MissingEnvironmentContextError,
)
from app.context.service import EnvironmentContextService
from app.execution.models import ExecutionStatus
from app.execution.runner import run_plan
from app.planning.planner import build_execution_plan


def valid_environment_payload() -> dict:
    return {
        "cloud": {
            "provider": "provider-x",
            "region": "region-1",
        },
        "compute": {
            "orchestrator": "kubernetes",
            "config": {"cluster": "core"},
        },
        "network": {
            "ingress": "ingress-x",
            "topology": "private",
        },
        "identity": {
            "type": "oidc",
            "scim": True,
        },
        "data": [
            {
                "type": "warehouse",
                "engine": "engine-x",
                "connection": {"dsn": "deterministic"},
            }
        ],
        "constraints": {
            "budget": "medium",
            "compliance": ["soc2"],
        },
    }


class TestContextValidation:
    def test_valid_configuration_loads(self) -> None:
        service = EnvironmentContextService()
        context = service.load_from_payload(valid_environment_payload())

        assert context.cloud.provider == "provider-x"
        assert context.compute.orchestrator == "kubernetes"
        assert service.get_cache_key()

    def test_missing_required_field_fails_fast(self) -> None:
        payload = valid_environment_payload()
        del payload["cloud"]["provider"]

        service = EnvironmentContextService()
        with pytest.raises(MissingEnvironmentContextError):
            service.load_from_payload(payload)

    def test_invalid_structure_fails_fast(self) -> None:
        payload = valid_environment_payload()
        payload["identity"]["type"] = "invalid-identity"

        service = EnvironmentContextService()
        with pytest.raises(InvalidEnvironmentConfigurationError):
            service.load_from_payload(payload)


class TestContextIntegration:
    def test_planning_receives_context(self) -> None:
        tasks = [
            {
                "id": "task-1",
                "description": "Environment-aware task",
                "dependencies": [],
            }
        ]

        plan = build_execution_plan(tasks, environment_context=valid_environment_payload())
        metadata = plan.ordered_tasks[0].metadata

        assert metadata["environment"]["compute_orchestrator"] == "kubernetes"
        assert metadata["required_identity_type"] == "oidc"
        assert metadata["required_compliance"] == ["soc2"]

    def test_execution_validates_environment_compatibility(self) -> None:
        tasks = [
            {
                "id": "deploy",
                "description": "Deploy workload",
                "dependencies": [],
                "metadata": {
                    "required_compute_orchestrator": "serverless",
                },
            }
        ]

        plan = build_execution_plan(tasks)

        with pytest.raises(InvalidEnvironmentConfigurationError):
            run_plan(plan, environment_context=valid_environment_payload())

    def test_execution_runs_when_context_is_compatible(self) -> None:
        tasks = [
            {
                "id": "deploy",
                "description": "Deploy workload",
                "dependencies": [],
                "metadata": {
                    "required_compute_orchestrator": "kubernetes",
                    "required_identity_type": "oidc",
                    "required_data_types": ["warehouse"],
                    "required_compliance": ["soc2"],
                },
            }
        ]

        plan = build_execution_plan(tasks)
        report = run_plan(plan, environment_context=valid_environment_payload())

        assert report.status == ExecutionStatus.COMPLETED
        assert report.completed_tasks == 1
