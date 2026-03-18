"""Base abstractions for deterministic integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


class Integration(ABC):
    """Abstract integration contract for deterministic, controlled actions."""

    name: str

    @abstractmethod
    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute an integration action and return the standard response contract.

        Response contract:
            {
              "status": "success" | "error",
              "data": dict,
              "error": str | None,
            }
        """

    def _success(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "success", "data": data, "error": None}

    def _error(self, error: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"status": "error", "data": data or {}, "error": error}

    def _validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dictionary")
        return payload
