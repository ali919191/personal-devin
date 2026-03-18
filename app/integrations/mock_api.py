"""Deterministic mock API integration with no real network calls."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.logger import get_logger
from app.integrations.base import Integration

logger = get_logger(__name__)


class MockAPIIntegration(Integration):
    """Mock external API integration for deterministic testing."""

    name = "mock_api"

    def __init__(self) -> None:
        self._static_get_responses = {
            "/health": {"service": "mock_api", "status": "ok"},
            "/projects": {
                "items": [
                    {"id": "project-1", "name": "Alpha"},
                    {"id": "project-2", "name": "Beta"},
                ]
            },
        }

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = self._validate_payload(payload)
        logger.info(
            "mock_api_action_started",
            {
                "action": action,
                "payload": self._sanitize_payload(payload),
            },
        )

        try:
            normalized_action = action.upper()
            if normalized_action == "GET":
                result = self._handle_get(payload)
            elif normalized_action == "POST":
                result = self._handle_post(payload)
            else:
                return self._error(f"unsupported mock_api action: {action}")
        except Exception as exc:  # pragma: no cover - behavior asserted via output
            logger.error(
                "mock_api_action_failed",
                error=str(exc),
                data={"action": action},
            )
            return self._error(str(exc))

        logger.info(
            "mock_api_action_completed",
            {"action": normalized_action, "result_keys": sorted(result.keys())},
        )
        return self._success(result)

    def _handle_get(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = self._validate_endpoint(payload.get("endpoint"))
        if endpoint not in self._static_get_responses:
            raise ValueError(f"unknown mock endpoint: {endpoint}")

        return {
            "method": "GET",
            "endpoint": endpoint,
            "response": self._static_get_responses[endpoint],
        }

    def _handle_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = self._validate_endpoint(payload.get("endpoint"))
        body = payload.get("data", {})
        if not isinstance(body, dict):
            raise ValueError("payload.data must be a dictionary")

        canonical_body = json.dumps(body, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{endpoint}:{canonical_body}".encode("utf-8")).hexdigest()
        resource_id = f"mock-{digest[:12]}"

        return {
            "method": "POST",
            "endpoint": endpoint,
            "resource_id": resource_id,
            "accepted": True,
            "echo": body,
        }

    def _validate_endpoint(self, endpoint: Any) -> str:
        if not isinstance(endpoint, str) or not endpoint.startswith("/"):
            raise ValueError("payload.endpoint must be a string starting with '/'")
        return endpoint

    def _sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = {"endpoint": payload.get("endpoint")}
        if "data" in payload:
            data = payload.get("data")
            if isinstance(data, dict):
                sanitized["data_keys"] = sorted(data.keys())
            else:
                sanitized["data_type"] = type(data).__name__
        return sanitized
