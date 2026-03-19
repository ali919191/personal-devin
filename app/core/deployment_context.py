"""Deployment context contract for deterministic deployment planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Allowed provider types for Agent 27 environment adapter.
_KNOWN_PROVIDER_TYPES: frozenset[str] = frozenset({"azure", "aws", "local", "aks", "mock"})

# Maximum length for a credentials reference.  Real secrets are never stored
# here — only opaque reference keys/paths (e.g. "vault://aws/deploy-role").
_MAX_CREDENTIALS_REF_LEN: int = 500


def _canonicalize(value: Any) -> Any:
    """Return a deterministic representation for nested dictionaries/lists."""
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


@dataclass(frozen=True)
class DeploymentContext:
    """Immutable input contract for deterministic deployment planning.

    Agent 27 extension fields
    -------------------------
    region : str
        Target deployment region (e.g. "us-east-1", "eu-west-1", "local").
        Defaults to ``"local"`` for non-cloud deployments.
    provider_type : str
        Infrastructure provider discriminator: ``"azure"``, ``"aws"``,
        ``"aks"``, ``"local"``, or ``"mock"``.
    credentials_ref : str
        An opaque *reference* to credentials — never the credential value
        itself.  Acceptable formats: ``"vault://path/to/secret"``,
        ``"iam://arn:aws:iam::123456789012:role/deploy"``,
        ``"k8s-secret://ns/name"``, etc.  Empty string means no external
        credentials are needed (local/mock providers).

    Security contract
    -----------------
    - Raw secrets MUST NOT be placed in this field.
    - No ``.env`` reads, no ``os.environ`` access — only opaque references.
    - Validation rejects values that look like raw secret material
      (newlines, or suspiciously long base64-like blobs).
    """

    execution_id: str
    environment: str
    artifacts: dict[str, Any]
    services: list[str]
    config: dict[str, Any]
    metadata: dict[str, Any]

    # Agent 27 — structured environment adapter fields (all optional, backward-compat)
    region: str = "local"
    provider_type: str = "local"
    credentials_ref: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise ValueError("execution_id must be a non-empty string")
        if not isinstance(self.environment, str) or not self.environment.strip():
            raise ValueError("environment must be a non-empty string")
        if not isinstance(self.artifacts, dict):
            raise TypeError("artifacts must be a dictionary")
        if not isinstance(self.services, list):
            raise TypeError("services must be a list")
        if not isinstance(self.config, dict):
            raise TypeError("config must be a dictionary")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dictionary")

        # Agent 27 — validate adapter fields
        if not isinstance(self.region, str) or not self.region.strip():
            raise ValueError("region must be a non-empty string")
        if not isinstance(self.provider_type, str) or not self.provider_type.strip():
            raise ValueError("provider_type must be a non-empty string")
        if self.provider_type not in _KNOWN_PROVIDER_TYPES:
            raise ValueError(
                f"provider_type must be one of {sorted(_KNOWN_PROVIDER_TYPES)}, "
                f"got: {self.provider_type!r}"
            )
        _validate_credentials_ref(self.credentials_ref)

        normalized_services = sorted(self._normalize_services(self.services))
        object.__setattr__(self, "artifacts", _canonicalize(dict(self.artifacts)))
        object.__setattr__(self, "services", normalized_services)
        object.__setattr__(self, "config", _canonicalize(dict(self.config)))
        object.__setattr__(self, "metadata", _canonicalize(dict(self.metadata)))

    @staticmethod
    def _normalize_services(services: list[Any]) -> list[str]:
        normalized: list[str] = []
        for service in services:
            if not isinstance(service, str) or not service.strip():
                raise ValueError("services must contain non-empty strings")
            normalized.append(service.strip())
        if len(normalized) != len(set(normalized)):
            raise ValueError("services must not contain duplicates")
        return normalized

    # ------------------------------------------------------------------
    # Agent 27 — DeploymentRequest → structured context mapping
    # ------------------------------------------------------------------

    @classmethod
    def from_deployment_request(
        cls,
        *,
        execution_id: str,
        environment: str,
        region: str = "local",
        provider_type: str = "local",
        credentials_ref: str = "",
        artifacts: dict[str, Any] | None = None,
        services: list[str] | None = None,
        config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "DeploymentContext":
        """Build a structured :class:`DeploymentContext` from flat request fields.

        This is the canonical mapping point that Agent 27 uses to bridge a
        :class:`~app.deployment.models.DeploymentRequest` (which carries only a
        bare ``environment`` string) to a fully-typed, immutable context that
        includes ``region``, ``provider_type``, and ``credentials_ref``.

        Args:
            execution_id:     Unique identifier for this execution run.
            environment:      Target environment name (dev / staging / prod / …).
            region:           Cloud region or ``"local"`` for non-cloud targets.
            provider_type:    Infrastructure provider (``"azure"``, ``"aws"``,
                              ``"aks"``, ``"local"``, ``"mock"``).
            credentials_ref:  Opaque reference to credentials — never the raw
                              secret value.
            artifacts:        Optional artifact map; defaults to empty dict.
            services:         Optional service list; defaults to empty list.
            config:           Optional config map; defaults to empty dict.
            metadata:         Optional metadata map; defaults to empty dict.
        """
        return cls(
            execution_id=execution_id,
            environment=environment,
            region=region,
            provider_type=provider_type,
            credentials_ref=credentials_ref,
            artifacts=artifacts or {},
            services=services or [],
            config=config or {},
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, serializable context representation."""
        return {
            "execution_id": self.execution_id,
            "environment": self.environment,
            "region": self.region,
            "provider_type": self.provider_type,
            "credentials_ref": self.credentials_ref,
            "artifacts": _canonicalize(self.artifacts),
            "services": list(self.services),
            "config": _canonicalize(self.config),
            "metadata": _canonicalize(self.metadata),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_credentials_ref(ref: str) -> None:
    """Reject values that look like raw secret material instead of references.

    Rules (fail-safe, not exhaustive):
    - Must be a string.
    - Must not exceed ``_MAX_CREDENTIALS_REF_LEN`` characters.
    - Must not contain newline characters (present in PEM/SSH keys).
    - Must not contain null bytes.

    These checks guard against accidentally placing a raw credential value in
    the reference field.  They are necessary but not sufficient — code-review
    must enforce the semantic contract.
    """
    if not isinstance(ref, str):
        raise TypeError("credentials_ref must be a string")
    if len(ref) > _MAX_CREDENTIALS_REF_LEN:
        raise ValueError(
            f"credentials_ref exceeds maximum reference length ({_MAX_CREDENTIALS_REF_LEN} chars); "
            "store a reference key/path, not the secret value itself"
        )
    if "\n" in ref or "\r" in ref:
        raise ValueError(
            "credentials_ref must not contain newline characters; "
            "it must be an opaque reference, not a raw secret (e.g. PEM key)"
        )
    if "\x00" in ref:
        raise ValueError("credentials_ref must not contain null bytes")