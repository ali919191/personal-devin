"""Deterministic failure recovery and retry policy for Agent 16."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, TypeVar

from app.core.logger import get_logger

logger = get_logger(__name__)

ResultT = TypeVar("ResultT")


class FailureCategory(str, Enum):
    """Supported deterministic failure classes for orchestration phases."""

    TRANSIENT = "transient"
    DETERMINISTIC = "deterministic"
    POLICY_VIOLATION = "policy_violation"


class TransientFailureError(RuntimeError):
    """An operation may succeed if retried."""


class DeterministicFailureError(RuntimeError):
    """An operation will continue to fail until the input changes."""


class PolicyViolationError(RuntimeError):
    """An operation is blocked by explicit system policy."""


@dataclass(frozen=True)
class RetryPolicy:
    """Retry policy with deterministic limits."""

    max_retries: int = 1

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")


@dataclass(frozen=True)
class RecoveryAttempt:
    """Single failed attempt recorded by the recovery manager."""

    phase: str
    attempt_number: int
    category: FailureCategory
    error: str
    will_retry: bool

    def to_dict(self) -> dict[str, str | int | bool]:
        """Return a JSON-safe attempt record."""
        return {
            "phase": self.phase,
            "attempt_number": self.attempt_number,
            "category": self.category.value,
            "error": self.error,
            "will_retry": self.will_retry,
        }


@dataclass
class RecoveryResult(Generic[ResultT]):
    """Outcome of a recovery-managed operation."""

    success: bool
    value: ResultT | None = None
    attempts: list[RecoveryAttempt] = field(default_factory=list)
    final_error: str = ""
    failure_category: FailureCategory | None = None


def categorize_failure(error: Exception) -> FailureCategory:
    """Map an exception to a deterministic failure category."""
    if isinstance(error, PolicyViolationError):
        return FailureCategory.POLICY_VIOLATION
    if isinstance(error, TransientFailureError):
        return FailureCategory.TRANSIENT
    if isinstance(error, DeterministicFailureError):
        return FailureCategory.DETERMINISTIC
    return FailureCategory.DETERMINISTIC


class RecoveryManager:
    """Execute operations with deterministic categorization and retry behavior."""

    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self._retry_policy = retry_policy or RetryPolicy()

    def execute(
        self,
        phase: str,
        operation: Callable[[], ResultT],
        retry_policy: RetryPolicy | None = None,
    ) -> RecoveryResult[ResultT]:
        """Run an operation, retrying only transient failures within policy limits."""
        active_policy = retry_policy or self._retry_policy
        attempts: list[RecoveryAttempt] = []
        attempt_number = 1

        while True:
            try:
                value = operation()
                logger.info(
                    "recovery_operation_completed",
                    {
                        "phase": phase,
                        "attempt_number": attempt_number,
                        "failed_attempts": len(attempts),
                        "max_retries": active_policy.max_retries,
                    },
                )
                return RecoveryResult(success=True, value=value, attempts=attempts)
            except Exception as exc:  # noqa: BLE001
                category = categorize_failure(exc)
                will_retry = (
                    category == FailureCategory.TRANSIENT
                    and attempt_number <= active_policy.max_retries
                )
                attempt = RecoveryAttempt(
                    phase=phase,
                    attempt_number=attempt_number,
                    category=category,
                    error=str(exc),
                    will_retry=will_retry,
                )
                attempts.append(attempt)

                log_payload = attempt.to_dict()
                if will_retry:
                    logger.warning("recovery_retry_scheduled", log_payload)
                    attempt_number += 1
                    continue

                logger.error(
                    "recovery_operation_failed",
                    error=str(exc),
                    data=log_payload,
                )
                return RecoveryResult(
                    success=False,
                    attempts=attempts,
                    final_error=str(exc),
                    failure_category=category,
                )