"""Public interface for the integrations layer."""

from app.integrations.base import BaseIntegration
from app.integrations.exceptions import (
    IntegrationError,
    IntegrationExecutionError,
    IntegrationNotFoundError,
)
from app.integrations.manager import IntegrationManager
from app.integrations.models import IntegrationRequest, IntegrationResponse
from app.integrations.registry import IntegrationRegistry

__all__ = [
    "BaseIntegration",
    "IntegrationError",
    "IntegrationExecutionError",
    "IntegrationNotFoundError",
    "IntegrationManager",
    "IntegrationRegistry",
    "IntegrationRequest",
    "IntegrationResponse",
]
