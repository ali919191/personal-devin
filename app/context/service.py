"""Deterministic loading, caching, and projection of environment context."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.context.exceptions import (
    InvalidEnvironmentConfigurationError,
    MissingEnvironmentContextError,
)
from app.context.models import EnvironmentContext
from app.context.validator import EnvironmentContextValidator
from app.core.logger import get_logger

logger = get_logger(__name__)


class EnvironmentContextService:
    """Universal context loader and immutable cache owner."""

    def __init__(self, validator: EnvironmentContextValidator | None = None) -> None:
        self._validator = validator or EnvironmentContextValidator()
        self._context: EnvironmentContext | None = None
        self._cache_key: str | None = None

    def load_from_payload(self, payload: dict[str, Any] | None) -> EnvironmentContext:
        """Validate, cache, and return immutable environment context."""
        self._validator.validate_required_fields(payload)
        assert payload is not None

        context = self._validator.validate_model(payload)
        cache_key = self._build_cache_key(payload)

        if self._cache_key is None or self._cache_key != cache_key:
            self._context = context
            self._cache_key = cache_key

        logger.info(
            "environment_loaded",
            {
                "event": "environment_loaded",
                "provider": context.cloud.provider,
                "capabilities": ["compute", "identity", "data"],
            },
        )
        return self.get_context()

    def load_from_file(self, file_path: str | Path) -> EnvironmentContext:
        """Load environment context from a JSON file."""
        path = Path(file_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise InvalidEnvironmentConfigurationError(
                "environment file must contain a JSON object"
            )
        return self.load_from_payload(payload)

    def get_context(self) -> EnvironmentContext:
        """Return immutable context or fail fast if not loaded."""
        if self._context is None:
            raise MissingEnvironmentContextError("environment context has not been loaded")
        return self._context.model_copy(deep=True)

    def get_cache_key(self) -> str:
        """Return deterministic cache key for current context."""
        if self._cache_key is None:
            raise MissingEnvironmentContextError("environment context has not been loaded")
        return self._cache_key

    def get_planning_context(self) -> dict[str, Any]:
        """Return deterministic projection consumed by planning."""
        context = self.get_context()
        return {
            "cloud_provider": context.cloud.provider,
            "cloud_region": context.cloud.region,
            "compute_orchestrator": context.compute.orchestrator,
            "identity_type": context.identity.type,
            "budget": context.constraints.budget,
            "compliance": sorted(context.constraints.compliance),
            "cache_key": self.get_cache_key(),
        }

    def get_execution_context(self) -> dict[str, Any]:
        """Return deterministic projection consumed by execution."""
        context = self.get_context()
        return {
            "provider": context.cloud.provider,
            "region": context.cloud.region,
            "network_topology": context.network.topology,
            "data_types": sorted([entry.type for entry in context.data]),
            "cache_key": self.get_cache_key(),
        }

    def _build_cache_key(self, payload: dict[str, Any]) -> str:
        canonical_payload = json.dumps(deepcopy(payload), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
