"""Pydantic models for integration request and response payloads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class IntegrationRequest(BaseModel):
    """Structured request dispatched to an integration provider."""

    id: str = Field(..., min_length=1, description="Unique request identifier")
    integration: str = Field(..., min_length=1, description="Provider name")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific deterministic input payload",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Request metadata used for tracing and control fields",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Request creation timestamp",
    )


class IntegrationResponse(BaseModel):
    """Structured response returned by an integration provider."""

    id: str = Field(..., min_length=1, description="Request identifier")
    integration: str = Field(..., min_length=1, description="Provider name")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured output payload",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata and execution details",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Response timestamp",
    )
