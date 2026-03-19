"""Controlled exception types for the integrations layer."""

from __future__ import annotations


class IntegrationError(Exception):
    """Base class for integration-related failures."""


class IntegrationNotFoundError(IntegrationError):
    """Raised when a provider cannot be resolved from the registry."""


class IntegrationExecutionError(IntegrationError):
    """Raised when a provider cannot complete a request successfully."""
