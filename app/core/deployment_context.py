"""Deployment context contract for deterministic deployment planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _canonicalize(value: Any) -> Any:
    """Return a deterministic representation for nested dictionaries/lists."""
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


@dataclass(frozen=True)
class DeploymentContext:
    """Immutable input contract for deterministic deployment planning."""

    execution_id: str
    environment: str
    artifacts: dict[str, Any]
    services: list[str]
    config: dict[str, Any]
    metadata: dict[str, Any]

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

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, serializable context representation."""
        return {
            "execution_id": self.execution_id,
            "environment": self.environment,
            "artifacts": _canonicalize(self.artifacts),
            "services": list(self.services),
            "config": _canonicalize(self.config),
            "metadata": _canonicalize(self.metadata),
        }