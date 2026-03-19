"""Tests for Agent 30 execution hooks (validate -> execute -> audit)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.execution.audit.audit_logger import AuditLogger
from app.execution.hooks.execution_hooks import execute_with_policy
from app.execution.policy.execution_policy import ExecutionPolicy
from app.execution.policy.policy_validator import PolicyValidationError


FIXED_TIMESTAMP = datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC)


def _clock() -> datetime:
    return FIXED_TIMESTAMP


def _id_factory(request: dict, timestamp: str) -> str:
    return f"id::{request.get('operation')}::{timestamp}"


def _read_entries(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_execute_with_policy_success_writes_audit(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path=audit_path)
    policy = ExecutionPolicy(allowed_operations=("build",), allowed_environments=("dev",))

    captured: list[dict] = []

    def engine(request: dict) -> dict:
        captured.append(request)
        return {"status": "ok", "operation": request["operation"]}

    request = {"operation": "build", "environment": "dev", "runtime_seconds": 1}
    output = execute_with_policy(
        engine,
        request,
        policy,
        audit_logger=logger,
        clock=_clock,
        record_id_factory=_id_factory,
    )

    assert output == {"status": "ok", "operation": "build"}
    assert captured == [request]

    entries = _read_entries(audit_path)
    assert len(entries) == 1
    assert entries[0]["id"] == "id::build::2026-03-19T12:00:00+00:00"
    assert entries[0]["status"] == "success"
    assert entries[0]["error"] is None
    assert entries[0]["output"] == {"status": "ok", "operation": "build"}


def test_execute_with_policy_blocked_fails_and_logs(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path=audit_path)
    policy = ExecutionPolicy(blocked_operations=("delete",))

    def engine(_: dict) -> dict:
        raise AssertionError("engine should not run when validation fails")

    request = {"operation": "delete", "environment": "dev"}

    with pytest.raises(PolicyValidationError):
        execute_with_policy(
            engine,
            request,
            policy,
            audit_logger=logger,
            clock=_clock,
            record_id_factory=_id_factory,
        )

    entries = _read_entries(audit_path)
    assert len(entries) == 1
    assert entries[0]["status"] == "failure"
    assert entries[0]["output"] is None
    assert "operation_blocked" in entries[0]["error"]


def test_execute_with_policy_engine_failure_is_logged(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path=audit_path)
    policy = ExecutionPolicy(allowed_operations=("deploy",))

    def failing_engine(_: dict) -> dict:
        raise RuntimeError("engine exploded")

    request = {"operation": "deploy", "environment": "staging"}

    with pytest.raises(RuntimeError, match="engine exploded"):
        execute_with_policy(
            failing_engine,
            request,
            policy,
            audit_logger=logger,
            clock=_clock,
            record_id_factory=_id_factory,
        )

    entries = _read_entries(audit_path)
    assert len(entries) == 1
    assert entries[0]["status"] == "failure"
    assert entries[0]["error"] == "engine exploded"


def test_execute_with_policy_is_deterministic_for_fixed_clock_and_id(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path=audit_path)
    policy = ExecutionPolicy(allowed_operations=("plan",), allowed_environments=("local",))

    request = {"operation": "plan", "environment": "local", "runtime_seconds": 0}

    def engine(_: dict) -> dict:
        return {"ok": True}

    output_a = execute_with_policy(
        engine,
        request,
        policy,
        audit_logger=logger,
        clock=_clock,
        record_id_factory=_id_factory,
    )
    output_b = execute_with_policy(
        engine,
        request,
        policy,
        audit_logger=logger,
        clock=_clock,
        record_id_factory=_id_factory,
    )

    assert output_a == output_b == {"ok": True}

    entries = _read_entries(audit_path)
    assert len(entries) == 2
    assert entries[0] == entries[1]
