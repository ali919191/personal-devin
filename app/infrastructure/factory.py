"""Deterministic infrastructure provider resolution."""

from __future__ import annotations

from app.infrastructure.base import InfrastructureProvider
from app.infrastructure.providers.aks import AKSInfrastructureProvider
from app.infrastructure.providers.local import LocalInfrastructureProvider
from app.infrastructure.providers.mock import MockInfrastructureProvider

_PROVIDER_MAP: dict[str, type[InfrastructureProvider]] = {
    "aks": AKSInfrastructureProvider,
    "local": LocalInfrastructureProvider,
    "mock": MockInfrastructureProvider,
}


def get_provider(env: str) -> InfrastructureProvider:
    """Return a fresh provider instance using deterministic environment mapping."""
    normalized = env.strip().lower()
    if normalized not in _PROVIDER_MAP:
        raise ValueError(f"Unsupported infrastructure environment: {env}")
    return _PROVIDER_MAP[normalized]()
