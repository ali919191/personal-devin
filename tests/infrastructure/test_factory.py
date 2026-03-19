"""Tests for infrastructure provider factory resolution."""

import pytest

from app.infrastructure.factory import get_provider
from app.infrastructure.providers.aks import AKSInfrastructureProvider
from app.infrastructure.providers.local import LocalInfrastructureProvider
from app.infrastructure.providers.mock import MockInfrastructureProvider


def test_factory_resolves_local_provider() -> None:
    provider = get_provider("local")
    assert isinstance(provider, LocalInfrastructureProvider)


def test_factory_resolves_aks_provider() -> None:
    provider = get_provider("aks")
    assert isinstance(provider, AKSInfrastructureProvider)


def test_factory_resolves_mock_provider() -> None:
    provider = get_provider("mock")
    assert isinstance(provider, MockInfrastructureProvider)


def test_factory_resolution_is_case_insensitive_and_deterministic() -> None:
    first = get_provider(" AKS ")
    second = get_provider("aks")
    assert first is second


def test_factory_rejects_unknown_environment() -> None:
    with pytest.raises(ValueError, match="Unsupported infrastructure environment"):
        get_provider("aws")
