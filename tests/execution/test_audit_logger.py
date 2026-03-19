"""Tests for Agent 30 append-only audit logger."""

from __future__ import annotations

import json
from pathlib import Path

from app.execution.audit.audit_logger import AuditLogger
from app.execution.audit.audit_models import ExecutionError, ExecutionRecord


def _read_lines(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in text if line]


def test_audit_logger_writes_single_record(tmp_path: Path) -> None:
    log_path = tmp_path / "execution_audit.jsonl"
    logger = AuditLogger(log_path=log_path)

    record = ExecutionRecord(
        id="rec-001",
        timestamp="2026-03-19T00:00:00+00:00",
        input={"operation": "build"},
        output={"ok": True},
        status="success",
        error=None,
    )

    logger.write_record(record)

    lines = _read_lines(log_path)
    assert len(lines) == 1
    assert lines[0]["schema_version"] == "v1"
    assert lines[0]["id"] == "rec-001"
    assert lines[0]["status"] == "success"


def test_audit_logger_is_append_only(tmp_path: Path) -> None:
    log_path = tmp_path / "execution_audit.jsonl"
    logger = AuditLogger(log_path=log_path)

    first = ExecutionRecord(
        id="rec-001",
        timestamp="2026-03-19T00:00:00+00:00",
        input={"operation": "build"},
        output={"ok": True},
        status="success",
        error=None,
    )
    second = ExecutionRecord(
        id="rec-002",
        timestamp="2026-03-19T00:00:01+00:00",
        input={"operation": "deploy"},
        output=None,
        status="failure",
        error=ExecutionError(type="ValueError", message="boom"),
    )

    logger.write_record(first)
    logger.write_record(second)

    lines = _read_lines(log_path)
    assert [entry["id"] for entry in lines] == ["rec-001", "rec-002"]
    assert lines[0]["schema_version"] == "v1"
    assert lines[1]["schema_version"] == "v1"
    assert lines[0]["output"] == {"ok": True}
    assert lines[1]["error"]["type"] == "ValueError"
    assert "message" in lines[1]["error"]
    assert lines[1]["error"]["message"] == "boom"


def test_audit_logger_uses_deterministic_default_path() -> None:
    logger = AuditLogger()
    assert str(logger.log_path).endswith("logs/execution_audit.jsonl")


def test_audit_logger_uses_env_override_when_no_explicit_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / "from-env" / "audit.jsonl"
    monkeypatch.setenv("EXECUTION_AUDIT_LOG_PATH", str(env_path))

    logger = AuditLogger()

    assert logger.log_path == env_path
