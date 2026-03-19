"""Base adapter contract for future provider-specific mappings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.context.models import EnvironmentContext


class ContextAdapter(ABC):
    """Abstract adapter for normalizing provider payloads."""

    @abstractmethod
    def normalize(self, payload: dict[str, Any]) -> EnvironmentContext:
        """Normalize provider-specific payloads into the universal context schema."""
        raise NotImplementedError
