"""Agent 27 — Environment Resolver.

Deterministic mapping layer: logical environment name → fully qualified
DeploymentContext fields (region, provider_type, credentials_ref).

Design constraints
------------------
- NO secrets.  credentials_ref is an opaque reference key only.
- NO .env reads.  NO os.environ access.  NO file I/O.
- NO network calls.  NO randomness.
- Same input ALWAYS produces the same output.
- Unknown environments raise ValueError — no silent fallbacks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.deployment_context import DeploymentContext
from app.deployment.models import DeploymentRequest


# ---------------------------------------------------------------------------
# EnvironmentConfig — single-environment definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvironmentConfig:
    """Immutable configuration record for a single logical environment.

    Fields
    ------
    name : str
        Logical environment name (e.g. "dev", "staging", "prod").
    region : str
        Target deployment region (e.g. "us-east-1", "eu-west-1", "local").
    provider_type : str
        Infrastructure provider discriminator accepted by
        :class:`~app.core.deployment_context.DeploymentContext`.
        Must be one of: ``"aws"``, ``"azure"``, ``"aks"``, ``"local"``,
        ``"mock"``.
    credentials_ref : str
        Opaque reference to the credentials needed by ``provider_type``.
        This MUST be a reference key or path — never the raw secret value.
        Examples: ``"iam://staging-role"``, ``"vault://prod/aws"``,
        ``"k8s-secret://infra/creds"``, ``"local://dev"``.
    """

    name: str
    region: str
    provider_type: str
    credentials_ref: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("EnvironmentConfig.name must be a non-empty string")
        if not self.region or not self.region.strip():
            raise ValueError("EnvironmentConfig.region must be a non-empty string")
        if not self.provider_type or not self.provider_type.strip():
            raise ValueError("EnvironmentConfig.provider_type must be a non-empty string")
        if not isinstance(self.credentials_ref, str):
            raise TypeError("EnvironmentConfig.credentials_ref must be a string")


# ---------------------------------------------------------------------------
# DEFAULT_ENVIRONMENT_CONFIG — version-controlled in-code mapping
# ---------------------------------------------------------------------------

#: Static mapping of logical environment names to their resolved configuration.
#:
#: This is the ONLY source of truth for environment → infrastructure mapping
#: in this codebase.  Modifications must be committed and code-reviewed — there
#: is intentionally no runtime file-read or environment-variable override path.
#:
#: credentials_ref values are opaque reference keys.  The actual credential
#: material lives outside this codebase (IAM role, Vault path, k8s Secret, etc.)
DEFAULT_ENVIRONMENT_CONFIG: dict[str, EnvironmentConfig] = {
    "dev": EnvironmentConfig(
        name="dev",
        region="local",
        provider_type="local",
        credentials_ref="local://dev",
    ),
    "staging": EnvironmentConfig(
        name="staging",
        region="us-east-1",
        provider_type="aws",
        credentials_ref="iam://staging-role",
    ),
    "prod": EnvironmentConfig(
        name="prod",
        region="us-east-1",
        provider_type="aws",
        credentials_ref="iam://prod-role",
    ),
    "local": EnvironmentConfig(
        name="local",
        region="local",
        provider_type="local",
        credentials_ref="local://local",
    ),
    "test": EnvironmentConfig(
        name="test",
        region="local",
        provider_type="mock",
        credentials_ref="local://test",
    ),
}


# ---------------------------------------------------------------------------
# EnvironmentResolver — resolution engine
# ---------------------------------------------------------------------------


class EnvironmentResolver:
    """Maps a logical environment name to its :class:`EnvironmentConfig`.

    The resolver is constructed with an explicit mapping so it is fully
    testable with arbitrary configurations without touching global state.

    Parameters
    ----------
    config:
        Dictionary mapping environment names (case-sensitive) to their
        :class:`EnvironmentConfig` records.  Pass
        :data:`DEFAULT_ENVIRONMENT_CONFIG` for production use.
    """

    def __init__(self, config: dict[str, EnvironmentConfig]) -> None:
        if not isinstance(config, dict):
            raise TypeError("config must be a dict[str, EnvironmentConfig]")
        if not config:
            raise ValueError("config must contain at least one environment entry")
        for key, value in config.items():
            if not isinstance(key, str):
                raise TypeError(f"config key must be str, got {type(key).__name__!r}")
            if not isinstance(value, EnvironmentConfig):
                raise TypeError(
                    f"config[{key!r}] must be an EnvironmentConfig, "
                    f"got {type(value).__name__!r}"
                )
        # Store an immutable snapshot — callers cannot mutate the resolver state
        # after construction.
        self._config: dict[str, EnvironmentConfig] = dict(config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, environment: str) -> EnvironmentConfig:
        """Return the :class:`EnvironmentConfig` for *environment*.

        Parameters
        ----------
        environment:
            Logical environment name (case-sensitive).

        Returns
        -------
        EnvironmentConfig
            The resolved configuration record.

        Raises
        ------
        ValueError
            If *environment* is not registered in the resolver's config.
            There is intentionally no fallback — unknown environments must
            be explicitly defined and committed.
        """
        if not isinstance(environment, str) or not environment.strip():
            raise ValueError("environment must be a non-empty string")
        env_key = environment.strip()
        if env_key not in self._config:
            known = sorted(self._config.keys())
            raise ValueError(
                f"Unknown environment: {env_key!r}. "
                f"Registered environments: {known}"
            )
        return self._config[env_key]

    @property
    def registered_environments(self) -> frozenset[str]:
        """Return the set of environment names known to this resolver."""
        return frozenset(self._config.keys())


# ---------------------------------------------------------------------------
# Module-level default resolver (convenience singleton)
# ---------------------------------------------------------------------------

#: Default resolver backed by :data:`DEFAULT_ENVIRONMENT_CONFIG`.
#: Use this in production code.  Tests should construct their own
#: :class:`EnvironmentResolver` with a controlled config.
DEFAULT_RESOLVER: EnvironmentResolver = EnvironmentResolver(DEFAULT_ENVIRONMENT_CONFIG)


# ---------------------------------------------------------------------------
# Integration helper — DeploymentRequest → DeploymentContext
# ---------------------------------------------------------------------------


def resolve_deployment_context(
    execution_id: str,
    request: DeploymentRequest,
    base_context_fields: dict[str, Any],
    *,
    resolver: EnvironmentResolver | None = None,
) -> DeploymentContext:
    """Resolve a :class:`~app.deployment.models.DeploymentRequest` into a
    fully qualified :class:`~app.core.deployment_context.DeploymentContext`.

    This is the canonical bridge between the thin
    :class:`~app.deployment.models.DeploymentRequest` (which carries only an
    environment name string) and the rich, immutable
    :class:`~app.core.deployment_context.DeploymentContext` required by the
    infrastructure execution layer.

    Resolution rules
    ----------------
    - ``environment``, ``region``, ``provider_type``, ``credentials_ref`` are
      always sourced from the resolved :class:`EnvironmentConfig`.  Any values
      for these keys supplied in *base_context_fields* are **ignored** so that
      the resolver remains the single source of truth.
    - ``execution_id`` is supplied directly — it is caller-owned.
    - ``artifacts``, ``services``, ``config``, ``metadata`` are taken from
      *base_context_fields* (defaulting to empty collections if absent).

    Parameters
    ----------
    execution_id:
        Unique identifier for this execution run.
    request:
        The incoming deployment request.  Only ``request.environment`` is
        consumed here; other fields are owned by the orchestrator.
    base_context_fields:
        Additional fields to populate the context: ``artifacts``,
        ``services``, ``config``, ``metadata``.  Unknown keys are ignored.
    resolver:
        Optional :class:`EnvironmentResolver` to use.  Defaults to
        :data:`DEFAULT_RESOLVER`.  Supply a custom resolver in tests to
        keep them hermetic.

    Returns
    -------
    DeploymentContext
        Fully qualified, immutable deployment context ready for execution.

    Raises
    ------
    ValueError
        If ``request.environment`` is not registered with the resolver.
    """
    active_resolver = resolver if resolver is not None else DEFAULT_RESOLVER
    env_config = active_resolver.resolve(request.environment)

    return DeploymentContext(
        execution_id=execution_id,
        environment=env_config.name,
        region=env_config.region,
        provider_type=env_config.provider_type,
        credentials_ref=env_config.credentials_ref,
        artifacts=dict(base_context_fields.get("artifacts") or {}),
        services=list(base_context_fields.get("services") or []),
        config=dict(base_context_fields.get("config") or {}),
        metadata=dict(base_context_fields.get("metadata") or {}),
    )
