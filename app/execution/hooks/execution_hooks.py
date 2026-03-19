"""Policy + audit wrapper around an existing execution engine callable."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Callable

from app.execution.audit.audit_logger import AuditLogger
from app.execution.audit.audit_models import ExecutionError, ExecutionRecord
from app.execution.policy.execution_policy import ExecutionPolicy
from app.execution.policy.policy_validator import PolicyValidationError, PolicyValidator

ExecutionEngine = Callable[[dict[str, Any]], Any]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_record_id(request: dict[str, Any], timestamp: str) -> str:
    payload = f"{timestamp}|{request}".encode("utf-8")
    return sha256(payload).hexdigest()[:16]


def execute_with_policy(
    execution_engine: ExecutionEngine,
    request: dict[str, Any],
    policy: ExecutionPolicy,
    *,
    validator: PolicyValidator | None = None,
    audit_logger: AuditLogger | None = None,
    clock: Clock | None = None,
    record_id_factory: Callable[[dict[str, Any], str], str] | None = None,
) -> Any:
    """Validate, execute, and append a structured audit record.

    Flow:
    1. Validate request against policy
    2. Execute existing engine callable
    3. Persist audit record
    4. Return engine output or re-raise failures
    """
    active_validator = validator or PolicyValidator()
    active_audit_logger = audit_logger or AuditLogger()
    active_clock = clock or _default_clock
    active_record_id_factory = record_id_factory or _default_record_id

    request_snapshot = deepcopy(request)
    timestamp = active_clock().isoformat()

    try:
        active_validator.validate_or_raise(request_snapshot, policy)
        output = execution_engine(request_snapshot)
        record = ExecutionRecord(
            id=active_record_id_factory(request_snapshot, timestamp),
            timestamp=timestamp,
            input=request_snapshot,
            output=deepcopy(output),
            status="success",
            error=None,
        )
        active_audit_logger.write_record(record)
        return output
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, PolicyValidationError):
            error_payload = ExecutionError(
                type=exc.__class__.__name__,
                message=f"{exc.code}:{exc}",
            )
        else:
            error_payload = ExecutionError(
                type=exc.__class__.__name__,
                message=str(exc),
            )

        record = ExecutionRecord(
            id=active_record_id_factory(request_snapshot, timestamp),
            timestamp=timestamp,
            input=request_snapshot,
            output=None,
            status="failure",
            error=error_payload,
        )
        active_audit_logger.write_record(record)
        raise
