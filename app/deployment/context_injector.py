"""Deployment context injection boundary for runtime execution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any

from app.deployment.deployment_context import DeploymentContext


def _normalize_mapping(name: str, value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        normalized = asdict(value)
    elif isinstance(value, dict):
        normalized = dict(value)
    else:
        raise TypeError(f"{name} must be a dict or dataclass instance")
    return deepcopy(normalized)


def _normalize_environment(resolved_env: dict[str, Any]) -> dict[str, Any]:
    environment = {
        "name": resolved_env.get("name") or resolved_env.get("environment"),
        "region": resolved_env.get("region"),
        "provider_type": resolved_env.get("provider_type"),
        "credentials_ref": resolved_env.get("credentials_ref", ""),
    }

    if not isinstance(environment["name"], str) or not environment["name"].strip():
        raise ValueError("resolved_env must include a non-empty name")
    if not isinstance(environment["region"], str) or not environment["region"].strip():
        raise ValueError("resolved_env must include a non-empty region")
    if not isinstance(environment["provider_type"], str) or not environment["provider_type"].strip():
        raise ValueError("resolved_env must include a non-empty provider_type")
    if not isinstance(environment["credentials_ref"], str):
        raise TypeError("resolved_env credentials_ref must be a string")

    return environment


def _normalize_config(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    explicit_variables = config.get("variables")
    explicit_metadata = config.get("metadata")

    if explicit_variables is None and explicit_metadata is None:
        variables = deepcopy(config)
        metadata: dict[str, Any] = {}
    else:
        variables = deepcopy(explicit_variables or {})
        metadata = deepcopy(explicit_metadata or {})

    if not isinstance(variables, dict):
        raise TypeError("config variables must be a dictionary")
    if not isinstance(metadata, dict):
        raise TypeError("config metadata must be a dictionary")

    execution_id = metadata.get("execution_id") or config.get("execution_id") or "default"
    metadata["execution_id"] = execution_id

    return variables, metadata


def build_deployment_context(resolved_env: dict[str, Any], config: dict[str, Any]) -> DeploymentContext:
    """Build an immutable deployment context from resolved environment data."""
    normalized_env = _normalize_environment(_normalize_mapping("resolved_env", resolved_env))
    normalized_config = _normalize_mapping("config", config)
    variables, metadata = _normalize_config(normalized_config)
    return DeploymentContext(
        environment=normalized_env,
        variables=variables,
        metadata=metadata,
    )