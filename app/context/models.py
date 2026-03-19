"""Provider-agnostic environment context schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CloudContext(BaseModel):
    """Cloud location metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(..., min_length=1)
    region: str = Field(..., min_length=1)


class ComputeContext(BaseModel):
    """Compute capability metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    orchestrator: Literal["kubernetes", "vm", "serverless"]
    config: dict[str, Any]


class NetworkContext(BaseModel):
    """Network capability metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ingress: str = Field(..., min_length=1)
    topology: Literal["private", "public", "hybrid"]


class IdentityContext(BaseModel):
    """Identity capability metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["oidc", "saml", "custom"]
    scim: bool


class DataSourceContext(BaseModel):
    """Data-source capability metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["warehouse", "relational", "lake", "api"]
    engine: str = Field(..., min_length=1)
    connection: dict[str, Any]


class ConstraintContext(BaseModel):
    """Operational constraints for planning and execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    budget: Literal["low", "medium", "high"]
    compliance: list[str] = Field(..., min_length=1)

    @field_validator("compliance")
    @classmethod
    def _validate_compliance(cls, value: list[str]) -> list[str]:
        normalized = [entry.strip() for entry in value]
        if any(not entry for entry in normalized):
            raise ValueError("constraints.compliance cannot contain empty values")
        return normalized


class EnvironmentContext(BaseModel):
    """Universal, capability-based environment context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cloud: CloudContext
    compute: ComputeContext
    network: NetworkContext
    identity: IdentityContext
    data: list[DataSourceContext] = Field(..., min_length=1)
    constraints: ConstraintContext

    @field_validator("data")
    @classmethod
    def _validate_data_sources(cls, value: list[DataSourceContext]) -> list[DataSourceContext]:
        if not value:
            raise ValueError("data must contain at least one source")
        return value

    def get_compute_type(self) -> str:
        """Return the configured compute orchestrator capability."""
        return self.compute.orchestrator

    def get_identity_type(self) -> str:
        """Return the configured identity capability."""
        return self.identity.type

    def get_budget(self) -> str:
        """Return the configured budget constraint."""
        return self.constraints.budget

    def get_compliance_controls(self) -> list[str]:
        """Return compliance controls in deterministic order."""
        return sorted(self.constraints.compliance)

    def get_data_types(self) -> list[str]:
        """Return supported data-source types in deterministic order."""
        return sorted([source.type for source in self.data])

    def supports(self, capability: str, value: str) -> bool:
        """Capability-based feature check used by planning and execution layers."""
        if capability == "compute":
            return value == self.get_compute_type()
        if capability == "identity":
            return value == self.get_identity_type()
        if capability == "network_topology":
            return value == self.network.topology
        if capability == "data_type":
            return value in self.get_data_types()
        if capability == "compliance":
            return value in self.get_compliance_controls()
        return False
