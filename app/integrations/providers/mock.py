"""Deterministic provider for tests and offline development."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC
from typing import Any

from app.integrations.base import BaseIntegration
from app.integrations.exceptions import IntegrationExecutionError
from app.integrations.models import IntegrationRequest, IntegrationResponse


class MockIntegration(BaseIntegration):
    """Return predictable outputs for deterministic tests."""

    name = "mock"

    def execute(self, request: IntegrationRequest) -> IntegrationResponse:
        operation = request.payload.get("operation", "echo")
        if not isinstance(operation, str) or not operation.strip():
            raise IntegrationExecutionError("payload.operation must be a non-empty string")

        canonical_payload = json.dumps(request.payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(
            f"{request.integration}:{request.id}:{canonical_payload}".encode("utf-8")
        ).hexdigest()
        timestamp = request.timestamp.astimezone(UTC)

        output: dict[str, Any] = {
            "operation": operation,
            "digest": digest,
            "echo": request.payload,
        }
        if operation == "lookup":
            output["result"] = {
                "status": "ok",
                "resource_id": request.payload.get("resource_id", "resource-unknown"),
            }
        elif operation == "status":
            output["result"] = {"status": "ok", "healthy": True}
        elif operation != "echo":
            raise IntegrationExecutionError(f"unsupported mock operation: {operation}")

        return IntegrationResponse(
            id=request.id,
            integration=self.name,
            payload=output,
            metadata={**request.metadata, "deterministic": True},
            timestamp=timestamp,
        )
