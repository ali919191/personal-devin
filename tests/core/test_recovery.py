"""Tests for Agent 16 failure recovery."""

from app.core.recovery import (
    DeterministicFailureError,
    FailureCategory,
    PolicyViolationError,
    RecoveryManager,
    RetryPolicy,
    TransientFailureError,
    categorize_failure,
)


def test_categorize_failure_uses_explicit_exception_types() -> None:
    assert categorize_failure(TransientFailureError("tmp")) == FailureCategory.TRANSIENT
    assert categorize_failure(DeterministicFailureError("det")) == FailureCategory.DETERMINISTIC
    assert categorize_failure(PolicyViolationError("policy")) == FailureCategory.POLICY_VIOLATION


def test_transient_failure_retries_then_succeeds() -> None:
    manager = RecoveryManager(retry_policy=RetryPolicy(max_retries=2))
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TransientFailureError("temporary")
        return "ok"

    result = manager.execute("executing", flaky)

    assert result.success is True
    assert result.value == "ok"
    assert len(result.attempts) == 1
    assert result.attempts[0].will_retry is True


def test_deterministic_failure_does_not_retry() -> None:
    manager = RecoveryManager(retry_policy=RetryPolicy(max_retries=3))
    attempts = {"count": 0}

    def broken() -> str:
        attempts["count"] += 1
        raise DeterministicFailureError("bad input")

    result = manager.execute("planning", broken)

    assert result.success is False
    assert result.failure_category == FailureCategory.DETERMINISTIC
    assert attempts["count"] == 1
    assert len(result.attempts) == 1
    assert result.attempts[0].will_retry is False


def test_policy_violation_does_not_retry() -> None:
    manager = RecoveryManager(retry_policy=RetryPolicy(max_retries=3))

    def blocked() -> str:
        raise PolicyViolationError("blocked")

    result = manager.execute("improving", blocked)

    assert result.success is False
    assert result.failure_category == FailureCategory.POLICY_VIOLATION
    assert len(result.attempts) == 1
    assert result.attempts[0].will_retry is False