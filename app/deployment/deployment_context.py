"""Immutable deployment runtime context for execution-layer injection."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
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