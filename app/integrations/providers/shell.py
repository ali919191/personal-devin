"""Deterministic local shell execution provider."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

from app.integrations.base import BaseIntegration
from app.integrations.exceptions import IntegrationExecutionError
from app.integrations.models import IntegrationRequest, IntegrationResponse


class ShellIntegration(BaseIntegration):
    """Execute explicitly provided shell commands with deterministic controls."""

    name = "shell"

    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        command = request.payload.get("command")
        if not isinstance(command, list) or not command or not all(
            isinstance(part, str) and part for part in command
        ):
            raise IntegrationExecutionError("payload.command must be a non-empty list of strings")

        cwd = request.payload.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise IntegrationExecutionError("payload.cwd must be a string when provided")

        env = request.payload.get("env")
        if env is not None:
            if not isinstance(env, dict) or not all(
                isinstance(key, str) and isinstance(value, str) for key, value in env.items()
            ):
                raise IntegrationExecutionError("payload.env must be a string-to-string mapping")

        timeout = request.payload.get("timeout_seconds")
        if timeout is None:
            timeout_value = None
        elif isinstance(timeout, (int, float)) and timeout > 0:
            timeout_value = float(timeout)
        else:
            raise IntegrationExecutionError("payload.timeout_seconds must be a positive number")

        started_at = datetime.now(UTC)
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_value,
            )
        except subprocess.TimeoutExpired as exc:
            raise IntegrationExecutionError(
                f"shell command timed out after {timeout_value} seconds"
            ) from exc
        except OSError as exc:
            raise IntegrationExecutionError(str(exc)) from exc

        finished_at = datetime.now(UTC)
        if completed.returncode != 0:
            raise IntegrationExecutionError(
                f"shell command failed with exit code {completed.returncode}: {completed.stderr.strip()}"
            )

        return IntegrationResponse(
            id=request.id,
            integration=self.name,
            payload={
                "command": command,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "exit_code": completed.returncode,
            },
            metadata={
                **request.metadata,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": (finished_at - started_at).total_seconds(),
                "timed_out": False,
            },
            timestamp=finished_at,
        )
