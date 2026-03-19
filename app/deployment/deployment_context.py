"""Immutable deployment runtime context for execution-layer injection."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import json
from hashlib import sha256
from typing import Any


def _freeze_value(value: Any) -> Any:
    """Convert nested values into immutable, deterministic structures."""
    if isinstance(value, FrozenDict):
        return value
    if isinstance(value, Mapping):
        return FrozenDict(value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    return value


def _thaw_value(value: Any) -> Any:
    """Convert frozen values back into plain Python containers."""
    if isinstance(value, FrozenDict):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


class FrozenDict(Mapping[str, Any]):
    """Hashable mapping used to enforce deep immutability."""

    __slots__ = ("_data", "_items", "_hash")

    def __init__(self, value: Mapping[str, Any]) -> None:
        if not isinstance(value, Mapping):
            raise TypeError("FrozenDict value must be a mapping")
        normalized = {str(key): _freeze_value(value[key]) for key in sorted(value, key=str)}
        self._data = normalized
        self._items = tuple(normalized.items())
        self._hash = hash(self._items)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        return self._hash

    def __repr__(self) -> str:
        return f"FrozenDict({self._data!r})"

    def to_dict(self) -> dict[str, Any]:
        return {key: _thaw_value(value) for key, value in self._data.items()}


def _fingerprint_payload_from_sections(
    environment: Mapping[str, Any],
    variables: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    sanitized_metadata = {
        str(key): _thaw_value(value)
        for key, value in metadata.items()
        if key not in {"execution_id", "context_fingerprint"}
    }
    return {
        "environment": FrozenDict(environment).to_dict(),
        "variables": FrozenDict(variables).to_dict(),
        "metadata": sanitized_metadata,
    }


def _fingerprint_payload_to_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class DeploymentContext:
    """Single authoritative deployment context for runtime execution."""

    environment: FrozenDict
    variables: FrozenDict
    metadata: FrozenDict

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment", self._coerce_mapping("environment", self.environment))
        object.__setattr__(self, "variables", self._coerce_mapping("variables", self.variables))
        object.__setattr__(self, "metadata", self._coerce_mapping("metadata", self.metadata))
        self._validate_required_fields()

    @staticmethod
    def _coerce_mapping(name: str, value: Mapping[str, Any] | FrozenDict) -> FrozenDict:
        if not isinstance(value, Mapping):
            raise TypeError(f"{name} must be a mapping")
        return value if isinstance(value, FrozenDict) else FrozenDict(value)

    def _validate_required_fields(self) -> None:
        name = self.environment.get("name")
        region = self.environment.get("region")
        provider_type = self.environment.get("provider_type")
        execution_id = self.metadata.get("execution_id")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("environment.name must be a non-empty string")
        if not isinstance(region, str) or not region.strip():
            raise ValueError("environment.region must be a non-empty string")
        if not isinstance(provider_type, str) or not provider_type.strip():
            raise ValueError("environment.provider_type must be a non-empty string")
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ValueError("metadata.execution_id must be a non-empty string")

    @property
    def environment_name(self) -> str:
        return str(self.environment["name"])

    @property
    def region(self) -> str:
        return str(self.environment["region"])

    @property
    def provider_type(self) -> str:
        return str(self.environment["provider_type"])

    @property
    def credentials_ref(self) -> str:
        return str(self.environment.get("credentials_ref", ""))

    @property
    def execution_id(self) -> str:
        return str(self.metadata["execution_id"])

    @property
    def fingerprint(self) -> str:
        fingerprint = self.metadata.get("context_fingerprint")
        if isinstance(fingerprint, str) and fingerprint:
            return fingerprint
        return context_fingerprint(self)

    @property
    def services(self) -> tuple[str, ...]:
        services = self.variables.get("services", ())
        if isinstance(services, tuple):
            return tuple(str(service) for service in services)
        raise TypeError("variables.services must be a list or tuple of strings")

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            "environment": self.environment.to_dict(),
            "variables": self.variables.to_dict(),
            "metadata": self.metadata.to_dict(),
        }

    def to_json(self) -> str:
        return _fingerprint_payload_to_json(self.to_dict())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DeploymentContext":
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        return cls(
            environment=payload.get("environment", {}),
            variables=payload.get("variables", {}),
            metadata=payload.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DeploymentContext":
        if not isinstance(payload, str):
            raise TypeError("payload must be a string")
        return cls.from_dict(json.loads(payload))


def context_fingerprint(context: DeploymentContext) -> str:
    """Return a deterministic hash for debugging and replay tracking."""
    if not isinstance(context, DeploymentContext):
        raise TypeError("context must be a DeploymentContext instance")
    payload = _fingerprint_payload_from_sections(
        context.environment,
        context.variables,
        context.metadata,
    )
    return sha256(_fingerprint_payload_to_json(payload).encode("utf-8")).hexdigest()