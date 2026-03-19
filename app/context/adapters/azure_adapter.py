"""Azure adapter scaffold for future context normalization."""

from __future__ import annotations

from typing import Any

from app.context.adapters.base import ContextAdapter
from app.context.models import EnvironmentContext


class AzureContextAdapter(ContextAdapter):
    """Placeholder adapter for future Azure mapping support."""

    def normalize(self, payload: dict[str, Any]) -> EnvironmentContext:
        raise NotImplementedError("Azure adapter is scaffolded but not implemented")
