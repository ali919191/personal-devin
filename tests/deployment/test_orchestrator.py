"""Tests for the Agent 26 provider-based DeploymentOrchestrator.run() path."""

from __future__ import annotations

import pytest

from app.deployment.models import DeploymentRequest, DeploymentResult
from app.deployment.orchestrator import DeploymentOrchestrator
from app.deployment.providers.base import DeploymentProvider
from app.deployment.providers.local_provider import LocalDeploymentProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FailingProvider(DeploymentProvider):
    """Provider that always raises to exercise failure-handling path."""

    def deploy(self, steps: list[dict]) -> list[dict]:
        raise RuntimeError("provider_error: simulated failure")


class _SpyProvider(DeploymentProvider):
    """Provider that records calls and delegates to LocalDeploymentProvider."""

    def __init__(self) -> None:
        self._delegate = LocalDeploymentProvider()
        self.calls: list[list[dict]] = []

    def deploy(self, steps: list[dict]) -> list[dict]:
        self.calls.append(list(steps))
        return self._delegate.deploy(steps)


# ---------------------------------------------------------------------------
# dry_run tests
# ---------------------------------------------------------------------------

def test_dry_run_returns_steps_without_calling_provider() -> None:
    """dry_run=True must return original steps and never invoke the provider."""
    spy = _SpyProvider()
    orchestrator = DeploymentOrchestrator(provider=spy)

    steps = [{"action": "deploy", "target": "api"}, {"action": "verify", "target": "api"}]
    request = DeploymentRequest(plan_id="plan-001", steps=steps, environment="staging", dry_run=True)

    result = orchestrator.run(request)

    assert isinstance(result, DeploymentResult)
    assert result.success is True
    assert result.executed_steps == steps
    assert result.errors == []
    # Provider must NOT have been called
    assert spy.calls == []


def test_dry_run_with_empty_steps_succeeds() -> None:
    request = DeploymentRequest(plan_id="plan-002", steps=[], environment="local", dry_run=True)
    result = DeploymentOrchestrator().run(request)

    assert result.success is True
    assert result.executed_steps == []
    assert result.errors == []


def test_dry_run_is_default() -> None:
    """DeploymentRequest.dry_run must default to True."""
    request = DeploymentRequest(plan_id="plan-003", steps=[{"x": 1}], environment="dev")
    assert request.dry_run is True


# ---------------------------------------------------------------------------
# live-run tests (dry_run=False)
# ---------------------------------------------------------------------------

def test_live_run_calls_provider_and_returns_results() -> None:
    """Live run must invoke the provider and surface its output."""
    spy = _SpyProvider()
    orchestrator = DeploymentOrchestrator(provider=spy)

    steps = [{"action": "deploy", "target": "worker"}]
    request = DeploymentRequest(plan_id="plan-004", steps=steps, environment="production", dry_run=False)

    result = orchestrator.run(request)

    assert result.success is True
    assert len(result.executed_steps) == 1
    assert result.executed_steps[0] == {"step": steps[0], "status": "executed"}
    assert result.errors == []
    # Provider must have been called exactly once with the input steps
    assert spy.calls == [steps]


def test_live_run_local_provider_maps_all_steps() -> None:
    """LocalDeploymentProvider returns one result record per input step."""
    orchestrator = DeploymentOrchestrator(provider=LocalDeploymentProvider())
    steps = [{"action": "a"}, {"action": "b"}, {"action": "c"}]
    request = DeploymentRequest(plan_id="plan-005", steps=steps, environment="dev", dry_run=False)

    result = orchestrator.run(request)

    assert result.success is True
    assert len(result.executed_steps) == len(steps)
    for original, record in zip(steps, result.executed_steps):
        assert record["step"] == original
        assert record["status"] == "executed"


# ---------------------------------------------------------------------------
# failure-handling tests
# ---------------------------------------------------------------------------

def test_provider_failure_returns_failure_result() -> None:
    """A provider exception must be caught and returned as a failure result."""
    orchestrator = DeploymentOrchestrator(provider=_FailingProvider())
    request = DeploymentRequest(plan_id="plan-006", steps=[{"x": 1}], environment="prod", dry_run=False)

    result = orchestrator.run(request)

    assert result.success is False
    assert result.executed_steps == []
    assert len(result.errors) == 1
    assert "provider_error" in result.errors[0]


def test_provider_failure_does_not_raise() -> None:
    """Orchestrator.run() must never propagate provider exceptions."""
    orchestrator = DeploymentOrchestrator(provider=_FailingProvider())
    request = DeploymentRequest(plan_id="plan-007", steps=[], environment="staging", dry_run=False)

    # Should not raise
    result = orchestrator.run(request)
    assert result.success is False


# ---------------------------------------------------------------------------
# model validation tests
# ---------------------------------------------------------------------------

def test_deployment_request_requires_plan_id() -> None:
    with pytest.raises(ValueError, match="plan_id"):
        DeploymentRequest(plan_id="", steps=[], environment="dev")


def test_deployment_request_requires_environment() -> None:
    with pytest.raises(ValueError, match="environment"):
        DeploymentRequest(plan_id="plan-x", steps=[], environment="")


# ---------------------------------------------------------------------------
# default provider tests
# ---------------------------------------------------------------------------

def test_default_provider_is_local() -> None:
    """DeploymentOrchestrator with no args must use LocalDeploymentProvider."""
    orchestrator = DeploymentOrchestrator()
    assert isinstance(orchestrator._provider, LocalDeploymentProvider)


def test_determinism_same_request_same_result() -> None:
    """Running the same request twice must produce identical results."""
    orchestrator = DeploymentOrchestrator(provider=LocalDeploymentProvider())
    steps = [{"action": "deploy", "target": "svc-a"}, {"action": "verify", "target": "svc-a"}]
    request = DeploymentRequest(plan_id="plan-008", steps=steps, environment="staging", dry_run=False)

    result_a = orchestrator.run(request)
    result_b = orchestrator.run(request)

    assert result_a.success == result_b.success
    assert result_a.executed_steps == result_b.executed_steps
    assert result_a.errors == result_b.errors
