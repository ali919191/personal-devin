"""GCP adapter scaffold for future context normalization."""

from __future__ import annotations

from typing import Any

from app.context.adapters.base import ContextAdapter
from app.context.models import EnvironmentContext


class GCPContextAdapter(ContextAdapter):
    """Placeholder adapter for future GCP mapping support."""

    def normalize(self, payload: dict[str, Any]) -> EnvironmentContext:
        raise NotImplementedError("GCP adapter is scaffolded but not implemented")
