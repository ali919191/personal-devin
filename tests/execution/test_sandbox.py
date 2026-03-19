"""Tests for Agent 29 execution sandboxing."""

from __future__ import annotations

import builtins
from pathlib import Path

from app.execution.models import ExecutionTask
from app.execution.sandbox import _BUILTINS_LOCK, ExecutionSandbox


def make_task(task_id: str = "task-1") -> ExecutionTask:
    return ExecutionTask(id=task_id, description=f"Task {task_id}")


def test_allowed_execution_returns_success() -> None:
    sandbox = ExecutionSandbox()

    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        return (True, f"handled:{task.id}")

    result = sandbox.execute(handler, make_task(), context={"trace_id": "t-1"})

    assert result["success"] is True
    assert result["output"]["result"] == (True, "handled:task-1")
    assert result["output"]["context"] == {"trace_id": "t-1"}
    assert result["error"] is None


def test_open_is_blocked() -> None:
    sandbox = ExecutionSandbox()

    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        open("file.txt")
        return (True, task.id)

    result = sandbox.execute(handler, make_task(), context={})

    assert result["success"] is False
    assert result["output"]["context"] == {}
    assert "open" in str(result["error"])


def test_os_import_is_blocked() -> None:
    sandbox = ExecutionSandbox()

    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        import os

        return (True, os.getcwd())

    result = sandbox.execute(handler, make_task(), context={})

    assert result["success"] is False
    assert result["output"]["context"] == {}
    assert result["error"] == "Module 'os' is not allowed"


def test_math_import_is_allowed() -> None:
    sandbox = ExecutionSandbox()

    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        import math

        return (True, math.sqrt(4))

    result = sandbox.execute(handler, make_task(), context={})

    assert result["success"] is True
    assert result["output"]["result"] == (True, 2.0)
    assert result["output"]["context"] == {}
    assert result["error"] is None


def test_handler_globals_are_not_rewritten() -> None:
    sandbox = ExecutionSandbox()
    original_globals = globals()

    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        return (True, task.id)

    result = sandbox.execute(handler, make_task("globals"), context={})

    assert result["success"] is True
    assert handler.__globals__ is original_globals


def test_builtins_are_restored_after_execution(tmp_path: Path) -> None:
    sandbox = ExecutionSandbox()

    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        open("sandbox.txt")
        return (True, task.id)

    sandbox.execute(handler, make_task(), context={})

    file_path = tmp_path / "outside.txt"
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write("restored")

    with open(file_path, encoding="utf-8") as handle:
        assert handle.read() == "restored"

    assert builtins.open is open


def test_same_input_produces_same_output() -> None:
    sandbox = ExecutionSandbox()

    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        import json

        payload = {"id": task.id, "total": sum([1, 2, 3])}
        return (True, json.dumps(payload, sort_keys=True))

    first = sandbox.execute(handler, make_task("stable"), context={"marker": 1})
    second = sandbox.execute(handler, make_task("stable"), context={"marker": 1})

    assert first == second


def test_context_is_copied_before_execution() -> None:
    sandbox = ExecutionSandbox()
    original_context = {"trace": {"id": "run-1"}}

    def handler(task: ExecutionTask) -> tuple[bool, str | None]:
        return (True, task.id)

    result = sandbox.execute(handler, make_task(), context=original_context)

    assert original_context == {"trace": {"id": "run-1"}}
    assert result["output"]["context"] == {"trace": {"id": "run-1"}}
    assert result["output"]["context"] is not original_context
    assert result["output"]["context"]["trace"] is not original_context["trace"]


def test_builtins_lock_is_reentrant() -> None:
    with _BUILTINS_LOCK:
        with _BUILTINS_LOCK:
            assert True
