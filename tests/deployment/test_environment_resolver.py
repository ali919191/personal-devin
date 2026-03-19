"""Tests for Agent 27 — EnvironmentResolver and resolve_deployment_context.

Covers:
- test_resolve_valid_environment          : known env returns correct config
- test_resolve_invalid_environment        : unknown env raises ValueError
- test_deterministic_output               : same input always produces same output
- test_no_mutation_of_input               : resolver does not mutate config or request
- test_context_integration                : resolve_deployment_context produces
                                            fully qualified DeploymentContext
- Additional coverage for edge cases,
  security contract, and resolver construction
"""

from __future__ import annotations

import pytest

from app.core.deployment_context import DeploymentContext
from app.deployment.environment_resolver import (
    DEFAULT_ENVIRONMENT_CONFIG,
    DEFAULT_RESOLVER,
    EnvironmentConfig,
    EnvironmentResolver,
    resolve_deployment_context,
)
from app.deployment.models import DeploymentRequest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_CUSTOM_CONFIG: dict[str, EnvironmentConfig] = {
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
}


def _make_resolver(config: dict[str, EnvironmentConfig] | None = None) -> EnvironmentResolver:
    return EnvironmentResolver(config if config is not None else _CUSTOM_CONFIG)


def _make_request(environment: str = "dev") -> DeploymentRequest:
    return DeploymentRequest(plan_id="plan-001", steps=[], environment=environment)


def _make_base_fields(
    *,
    artifacts: dict | None = None,
    services: list | None = None,
    config: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "artifacts": artifacts or {"image": "app:1.0"},
        "services": services or ["api"],
        "config": config or {"replicas": 2},
        "metadata": metadata or {"trigger": "ci"},
    }


# ---------------------------------------------------------------------------
# 1. test_resolve_valid_environment
# ---------------------------------------------------------------------------


def test_resolve_valid_environment_dev() -> None:
    resolver = _make_resolver()
    cfg = resolver.resolve("dev")

    assert cfg.name == "dev"
    assert cfg.region == "local"
    assert cfg.provider_type == "local"
    assert cfg.credentials_ref == "local://dev"


def test_resolve_valid_environment_staging() -> None:
    resolver = _make_resolver()
    cfg = resolver.resolve("staging")

    assert cfg.name == "staging"
    assert cfg.region == "us-east-1"
    assert cfg.provider_type == "aws"
    assert cfg.credentials_ref == "iam://staging-role"


def test_resolve_valid_environment_prod() -> None:
    resolver = _make_resolver()
    cfg = resolver.resolve("prod")

    assert cfg.name == "prod"
    assert cfg.region == "us-east-1"
    assert cfg.provider_type == "aws"
    assert cfg.credentials_ref == "iam://prod-role"


# ---------------------------------------------------------------------------
# 2. test_resolve_invalid_environment
# ---------------------------------------------------------------------------


def test_resolve_invalid_environment_raises() -> None:
    resolver = _make_resolver()
    with pytest.raises(ValueError, match="Unknown environment"):
        resolver.resolve("uat")


def test_resolve_invalid_environment_includes_known_list() -> None:
    resolver = _make_resolver()
    with pytest.raises(ValueError, match="dev"):
        resolver.resolve("nonexistent")


def test_resolve_empty_string_raises() -> None:
    resolver = _make_resolver()
    with pytest.raises(ValueError):
        resolver.resolve("")


def test_resolve_whitespace_only_raises() -> None:
    resolver = _make_resolver()
    with pytest.raises(ValueError):
        resolver.resolve("   ")


def test_resolve_case_sensitive() -> None:
    """Environment lookup is case-sensitive; 'Dev' != 'dev'."""
    resolver = _make_resolver()
    with pytest.raises(ValueError, match="Unknown environment"):
        resolver.resolve("Dev")


def test_resolve_case_sensitive_prod_upper() -> None:
    resolver = _make_resolver()
    with pytest.raises(ValueError, match="Unknown environment"):
        resolver.resolve("PROD")


# ---------------------------------------------------------------------------
# 3. test_deterministic_output
# ---------------------------------------------------------------------------


def test_deterministic_output_same_call() -> None:
    resolver = _make_resolver()
    first = resolver.resolve("staging")
    second = resolver.resolve("staging")

    assert first == second


def test_deterministic_output_independent_resolvers() -> None:
    """Two resolvers with the same config must produce identical results."""
    r1 = _make_resolver()
    r2 = _make_resolver()

    assert r1.resolve("prod") == r2.resolve("prod")


def test_deterministic_context_integration() -> None:
    resolver = _make_resolver()
    request = _make_request("staging")
    base = _make_base_fields()

    ctx1 = resolve_deployment_context("exec-x", request, base, resolver=resolver)
    ctx2 = resolve_deployment_context("exec-x", request, base, resolver=resolver)

    assert ctx1 == ctx2


def test_deterministic_output_no_external_dependency() -> None:
    """Resolver must not depend on any mutable global state; repeated calls are stable."""
    resolver = _make_resolver()
    results = [resolver.resolve("dev") for _ in range(10)]

    assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# 4. test_no_mutation_of_input
# ---------------------------------------------------------------------------


def test_no_mutation_of_config_dict() -> None:
    config_copy = dict(_CUSTOM_CONFIG)
    resolver = EnvironmentResolver(config_copy)

    # Mutate the original dict after construction
    config_copy["injected"] = EnvironmentConfig(
        name="injected",
        region="local",
        provider_type="mock",
        credentials_ref="local://injected",
    )

    # The resolver must NOT see the post-construction mutation
    with pytest.raises(ValueError, match="Unknown environment"):
        resolver.resolve("injected")


def test_no_mutation_of_request() -> None:
    resolver = _make_resolver()
    request = _make_request("dev")
    base = _make_base_fields()

    original_env = request.environment
    resolve_deployment_context("exec-001", request, base, resolver=resolver)

    assert request.environment == original_env


def test_no_mutation_of_base_context_fields() -> None:
    resolver = _make_resolver()
    request = _make_request("dev")
    base = _make_base_fields(
        artifacts={"image": "app:1.0"},
        services=["api", "worker"],
        config={"replicas": 3},
        metadata={"trigger": "manual"},
    )
    snapshot = {
        "artifacts": dict(base["artifacts"]),
        "services": list(base["services"]),
        "config": dict(base["config"]),
        "metadata": dict(base["metadata"]),
    }

    resolve_deployment_context("exec-002", request, base, resolver=resolver)

    assert base["artifacts"] == snapshot["artifacts"]
    assert base["services"] == snapshot["services"]
    assert base["config"] == snapshot["config"]
    assert base["metadata"] == snapshot["metadata"]


def test_environment_config_is_immutable() -> None:
    cfg = EnvironmentConfig(
        name="dev", region="local", provider_type="local", credentials_ref="local://dev"
    )
    with pytest.raises(Exception):  # frozen dataclass raises FrozenInstanceError
        cfg.region = "us-east-1"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 5. test_context_integration
# ---------------------------------------------------------------------------


def test_context_integration_fields_sourced_from_resolver() -> None:
    """Resolved context must use region/provider_type/credentials_ref from config."""
    resolver = _make_resolver()
    request = _make_request("staging")
    base = _make_base_fields()

    ctx = resolve_deployment_context("exec-staging-01", request, base, resolver=resolver)

    assert isinstance(ctx, DeploymentContext)
    assert ctx.execution_id == "exec-staging-01"
    assert ctx.environment == "staging"
    assert ctx.region == "us-east-1"
    assert ctx.provider_type == "aws"
    assert ctx.credentials_ref == "iam://staging-role"


def test_context_integration_preserves_base_fields() -> None:
    """artifacts, services, config, metadata must come from base_context_fields."""
    resolver = _make_resolver()
    request = _make_request("dev")
    base = _make_base_fields(
        artifacts={"image": "myapp:2.1"},
        services=["frontend", "backend"],
        config={"replicas": 5, "timeout": 30},
        metadata={"triggered_by": "scheduler"},
    )

    ctx = resolve_deployment_context("exec-dev-01", request, base, resolver=resolver)

    assert ctx.artifacts == {"image": "myapp:2.1"}
    assert set(ctx.services) == {"frontend", "backend"}
    assert ctx.config == {"replicas": 5, "timeout": 30}
    assert ctx.metadata == {"triggered_by": "scheduler"}


def test_context_integration_base_fields_override_not_bleed_into_resolver_fields() -> None:
    """If base_context_fields accidentally contains region/provider_type, resolver wins."""
    resolver = _make_resolver()
    request = _make_request("prod")
    base: dict = {
        "artifacts": {},
        "services": [],
        "config": {},
        "metadata": {},
        # These must be IGNORED — resolver is the authority
        "region": "ap-southeast-2",
        "provider_type": "azure",
        "credentials_ref": "vault://rogue",
    }

    ctx = resolve_deployment_context("exec-prod-01", request, base, resolver=resolver)

    # Must reflect the resolver's prod config, not the rogue base_context_fields values
    assert ctx.region == "us-east-1"
    assert ctx.provider_type == "aws"
    assert ctx.credentials_ref == "iam://prod-role"


def test_context_integration_is_immutable() -> None:
    resolver = _make_resolver()
    ctx = resolve_deployment_context(
        "exec-x", _make_request("dev"), _make_base_fields(), resolver=resolver
    )
    with pytest.raises(Exception):
        ctx.environment = "prod"  # type: ignore[misc]


def test_context_integration_unknown_env_raises() -> None:
    resolver = _make_resolver()
    request = _make_request("unknown-env")
    with pytest.raises(ValueError, match="Unknown environment"):
        resolve_deployment_context("exec-x", request, {}, resolver=resolver)


def test_context_integration_empty_base_fields_uses_defaults() -> None:
    """Empty base_context_fields must produce empty/default collections, not errors."""
    resolver = _make_resolver()
    request = _make_request("dev")

    ctx = resolve_deployment_context("exec-x", request, {}, resolver=resolver)

    assert ctx.artifacts == {}
    assert ctx.services == []
    assert ctx.config == {}
    assert ctx.metadata == {}


# ---------------------------------------------------------------------------
# Default config / DEFAULT_RESOLVER smoke tests
# ---------------------------------------------------------------------------


def test_default_environment_config_contains_required_keys() -> None:
    for key in ("dev", "staging", "prod"):
        assert key in DEFAULT_ENVIRONMENT_CONFIG, f"Missing required key: {key!r}"


def test_default_resolver_resolves_all_default_environments() -> None:
    for env_name in DEFAULT_ENVIRONMENT_CONFIG:
        cfg = DEFAULT_RESOLVER.resolve(env_name)
        assert cfg.name == env_name


def test_default_resolver_no_raw_secrets() -> None:
    """credentials_ref values must look like references, not raw secrets."""
    for env_name, cfg in DEFAULT_ENVIRONMENT_CONFIG.items():
        assert "\n" not in cfg.credentials_ref, (
            f"Newline found in credentials_ref for {env_name!r} — "
            "this looks like a raw secret (e.g. PEM key)"
        )
        assert len(cfg.credentials_ref) < 500, (
            f"credentials_ref for {env_name!r} is suspiciously long"
        )


def test_environment_config_provider_types_are_known() -> None:
    """All provider_type values must match the set accepted by DeploymentContext."""
    known = {"azure", "aws", "local", "aks", "mock"}
    for env_name, cfg in DEFAULT_ENVIRONMENT_CONFIG.items():
        assert cfg.provider_type in known, (
            f"Unexpected provider_type {cfg.provider_type!r} for {env_name!r}"
        )


# ---------------------------------------------------------------------------
# Resolver construction guard tests
# ---------------------------------------------------------------------------


def test_resolver_rejects_empty_config() -> None:
    with pytest.raises(ValueError, match="at least one"):
        EnvironmentResolver({})


def test_resolver_rejects_non_dict_config() -> None:
    with pytest.raises(TypeError):
        EnvironmentResolver("not-a-dict")  # type: ignore[arg-type]


def test_resolver_rejects_non_config_values() -> None:
    with pytest.raises(TypeError, match="EnvironmentConfig"):
        EnvironmentResolver({"dev": "not-a-config"})  # type: ignore[dict-item]


def test_resolver_registered_environments_returns_frozenset() -> None:
    resolver = _make_resolver()
    envs = resolver.registered_environments

    assert isinstance(envs, frozenset)
    assert "dev" in envs
    assert "staging" in envs
    assert "prod" in envs
