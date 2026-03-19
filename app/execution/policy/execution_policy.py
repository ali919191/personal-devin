"""Declarative execution policy model for request governance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionPolicy:
    """Declarative policy constraints for execution requests.

    Attributes:
        allowed_operations: Allowed operation names. If empty, all operations are
            considered allowed unless blocked by ``blocked_operations``.
        blocked_operations: Explicitly forbidden operation names.
        max_runtime_seconds: Optional runtime cap for requests that provide
            ``runtime_seconds``.
        allowed_environments: Allowed environment names. If empty, all
            environments are accepted.
    """

    allowed_operations: tuple[str, ...] = ()
    blocked_operations: tuple[str, ...] = ()
    max_runtime_seconds: int | None = None
    allowed_environments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self._validate_names(self.allowed_operations, "allowed_operations")
        self._validate_names(self.blocked_operations, "blocked_operations")
        self._validate_names(self.allowed_environments, "allowed_environments")

        if self.max_runtime_seconds is not None and self.max_runtime_seconds < 0:
            raise ValueError("max_runtime_seconds must be >= 0 when provided")

    @staticmethod
    def _validate_names(values: tuple[str, ...], field_name: str) -> None:
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} entries must be non-empty strings")

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ExecutionPolicy":
        """Build a policy from a plain dictionary payload."""
        return cls(
            allowed_operations=tuple(payload.get("allowed_operations", ()) or ()),
            blocked_operations=tuple(payload.get("blocked_operations", ()) or ()),
            max_runtime_seconds=payload.get("max_runtime_seconds"),
            allowed_environments=tuple(payload.get("allowed_environments", ()) or ()),
        )
