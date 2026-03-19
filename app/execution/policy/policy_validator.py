"""Deterministic validator for execution requests against execution policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.execution.policy.execution_policy import ExecutionPolicy


@dataclass(frozen=True)
class PolicyValidationResult:
    """Result object for successful policy validation."""

    operation: str
    environment: str | None
    runtime_seconds: int | None


class PolicyValidationError(ValueError):
    """Raised when execution request violates execution policy."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class PolicyValidator:
    """Validate a request dict against an :class:`ExecutionPolicy`."""

    def validate_or_raise(
        self,
        request: dict[str, Any],
        policy: ExecutionPolicy,
    ) -> PolicyValidationResult:
        if not isinstance(request, dict):
            raise PolicyValidationError("request must be a dict", code="invalid_request_type")

        operation_value = request.get("operation")
        if not isinstance(operation_value, str) or not operation_value.strip():
            raise PolicyValidationError(
                "request.operation must be a non-empty string",
                code="missing_operation",
            )
        operation = operation_value.strip()

        environment_raw = request.get("environment")
        environment: str | None = None
        if environment_raw is not None:
            if not isinstance(environment_raw, str) or not environment_raw.strip():
                raise PolicyValidationError(
                    "request.environment must be a non-empty string when provided",
                    code="invalid_environment",
                )
            environment = environment_raw.strip()

        runtime_seconds = request.get("runtime_seconds")
        if runtime_seconds is not None:
            if not isinstance(runtime_seconds, int):
                raise PolicyValidationError(
                    "request.runtime_seconds must be an int when provided",
                    code="invalid_runtime_type",
                )
            if runtime_seconds < 0:
                raise PolicyValidationError(
                    "request.runtime_seconds must be >= 0",
                    code="invalid_runtime_value",
                )

        if policy.allowed_operations and operation not in policy.allowed_operations:
            raise PolicyValidationError(
                f"Operation '{operation}' is not allowed",
                code="operation_not_allowed",
            )

        if operation in policy.blocked_operations:
            raise PolicyValidationError(
                f"Operation '{operation}' is blocked",
                code="operation_blocked",
            )

        if policy.allowed_environments and environment not in policy.allowed_environments:
            raise PolicyValidationError(
                f"Environment '{environment}' is not allowed",
                code="environment_not_allowed",
            )

        if (
            policy.max_runtime_seconds is not None
            and runtime_seconds is not None
            and runtime_seconds > policy.max_runtime_seconds
        ):
            raise PolicyValidationError(
                (
                    "Runtime exceeds policy limit: "
                    f"{runtime_seconds}s > {policy.max_runtime_seconds}s"
                ),
                code="runtime_exceeded",
            )

        return PolicyValidationResult(
            operation=operation,
            environment=environment,
            runtime_seconds=runtime_seconds,
        )
