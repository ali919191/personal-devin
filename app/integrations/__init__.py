"""Public interface for integrations layer."""

from app.integrations.base import Integration
from app.integrations.filesystem import FilesystemIntegration
from app.integrations.mock_api import MockAPIIntegration
from app.integrations.registry import IntegrationRegistry

__all__ = [
    "Integration",
    "IntegrationRegistry",
    "FilesystemIntegration",
    "MockAPIIntegration",
]
