"""Retry and failure classification utilities for agent loop hardening."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailureType(str, Enum):
    """Classified failure categories used by loop retry policy."""

    TRANSIENT = "TRANSIENT"
    LOGIC = "LOGIC"
    VALIDATION = "VALIDATION"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Deterministic retry policy for classified loop failures."""

    max_attempts: int = 3

    def should_retry(self, failure_type: FailureType, attempt: int) -> bool:
        """Return True only for transient failures under max-attempts limit."""
        if attempt >= self.max_attempts:
            return False
        return failure_type == FailureType.TRANSIENT


def classify_failure(exception: Exception) -> FailureType:
    """Classify exception into deterministic failure types."""
    if isinstance(exception, (TimeoutError, ConnectionError, OSError)):
        return FailureType.TRANSIENT
    if isinstance(exception, (ValueError, AssertionError)):
        return FailureType.VALIDATION
    return FailureType.LOGIC
