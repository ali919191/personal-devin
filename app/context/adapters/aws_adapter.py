"""AWS adapter scaffold for future context normalization."""

from __future__ import annotations

from typing import Any

from app.context.adapters.base import ContextAdapter
from app.context.models import EnvironmentContext


class AWSContextAdapter(ContextAdapter):
    """Placeholder adapter for future AWS mapping support."""

    def normalize(self, payload: dict[str, Any]) -> EnvironmentContext:
        raise NotImplementedError("AWS adapter is scaffolded but not implemented")
