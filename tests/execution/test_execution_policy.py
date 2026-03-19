"""Tests for Agent 30 execution policy + validator."""

from __future__ import annotations

import pytest

from app.execution.policy.execution_policy import ExecutionPolicy
from app.execution.policy.policy_validator import PolicyValidationError, PolicyValidator


class TestPolicyValidator:
    def setup_method(self) -> None:
        self.validator = PolicyValidator()

    def test_allowed_execution_passes(self) -> None:
        policy = ExecutionPolicy(
            allowed_operations=("build", "deploy"),
            blocked_operations=("delete",),
            allowed_environments=("dev", "staging"),
            max_runtime_seconds=60,
        )
        request = {"operation": "build", "environment": "dev", "runtime_seconds": 30}

        result = self.validator.validate_or_raise(request, policy)

        assert result.operation == "build"
        assert result.environment == "dev"
        assert result.runtime_seconds == 30

    def test_blocked_execution_fails(self) -> None:
        policy = ExecutionPolicy(blocked_operations=("destroy",))
        request = {"operation": "destroy", "environment": "dev"}

        with pytest.raises(PolicyValidationError, match="blocked") as exc_info:
            self.validator.validate_or_raise(request, policy)

        assert exc_info.value.code == "operation_blocked"

    def test_runtime_limit_violation_fails(self) -> None:
        policy = ExecutionPolicy(max_runtime_seconds=10)
        request = {"operation": "deploy", "runtime_seconds": 11}

        with pytest.raises(PolicyValidationError, match="Runtime exceeds") as exc_info:
            self.validator.validate_or_raise(request, policy)

        assert exc_info.value.code == "runtime_exceeded"

    def test_environment_constraint_violation_fails(self) -> None:
        policy = ExecutionPolicy(allowed_environments=("prod",))
        request = {"operation": "deploy", "environment": "dev"}

        with pytest.raises(PolicyValidationError, match="not allowed") as exc_info:
            self.validator.validate_or_raise(request, policy)

        assert exc_info.value.code == "environment_not_allowed"

    def test_invalid_request_type_raises_explicit_error(self) -> None:
        policy = ExecutionPolicy()

        with pytest.raises(PolicyValidationError, match="request must be a dict") as exc_info:
            self.validator.validate_or_raise("not-a-dict", policy)  # type: ignore[arg-type]

        assert exc_info.value.code == "invalid_request_type"


def test_policy_from_dict() -> None:
    payload = {
        "allowed_operations": ["plan", "execute"],
        "blocked_operations": ["drop"],
        "max_runtime_seconds": 120,
        "allowed_environments": ["local"],
    }

    policy = ExecutionPolicy.from_dict(payload)

    assert policy.allowed_operations == ("plan", "execute")
    assert policy.blocked_operations == ("drop",)
    assert policy.max_runtime_seconds == 120
    assert policy.allowed_environments == ("local",)
