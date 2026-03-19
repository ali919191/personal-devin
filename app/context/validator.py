"""Strict validation for environment context payloads and compatibility."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from app.context.exceptions import (
    InvalidEnvironmentConfigurationError,
    MissingEnvironmentContextError,
)
from app.context.models import EnvironmentContext

if TYPE_CHECKING:
    from app.planning.models import ExecutionPlan


class EnvironmentContextValidator:
    """Deterministic validator for required fields and environment compatibility."""

    _REQUIRED_TOP_LEVEL: set[str] = {
        "cloud",
        "compute",
        "network",
        "identity",
        "data",
        "constraints",
    }

    _REQUIRED_NESTED: dict[str, set[str]] = {
        "cloud": {"provider", "region"},
        "compute": {"orchestrator", "config"},
        "network": {"ingress", "topology"},
        "identity": {"type", "scim"},
        "constraints": {"budget", "compliance"},
    }

    _REQUIRED_DATA_ITEM: set[str] = {"type", "engine", "connection"}

    def validate_required_fields(self, payload: dict | None) -> None:
        """Raise explicit errors when required fields are missing."""
        if payload is None:
            raise MissingEnvironmentContextError("environment context is required")
        if not isinstance(payload, dict):
            raise InvalidEnvironmentConfigurationError(
                "environment context must be a dictionary"
            )

        missing_top_level = sorted(self._REQUIRED_TOP_LEVEL - set(payload.keys()))
        if missing_top_level:
            raise MissingEnvironmentContextError(
                "missing environment fields: " + ", ".join(missing_top_level)
            )

        for section, required_fields in self._REQUIRED_NESTED.items():
            section_payload = payload.get(section)
            if not isinstance(section_payload, dict):
                raise MissingEnvironmentContextError(
                    f"missing environment fields: {section}"
                )
            missing_section = sorted(required_fields - set(section_payload.keys()))
            if missing_section:
                missing_fields = ", ".join(
                    f"{section}.{field_name}" for field_name in missing_section
                )
                raise MissingEnvironmentContextError(
                    "missing environment fields: " + missing_fields
                )

        data_payload = payload.get("data")
        if not isinstance(data_payload, list) or not data_payload:
            raise MissingEnvironmentContextError("missing environment fields: data")
        for index, item in enumerate(data_payload):
            if not isinstance(item, dict):
                raise InvalidEnvironmentConfigurationError(
                    f"data[{index}] must be a dictionary"
                )
            missing_data_fields = sorted(self._REQUIRED_DATA_ITEM - set(item.keys()))
            if missing_data_fields:
                missing_fields = ", ".join(
                    f"data[{index}].{field_name}" for field_name in missing_data_fields
                )
                raise MissingEnvironmentContextError(
                    "missing environment fields: " + missing_fields
                )

    def validate_model(self, payload: dict) -> EnvironmentContext:
        """Validate payload shape and values using the typed model."""
        try:
            return EnvironmentContext.model_validate(payload)
        except ValidationError as exc:
            raise InvalidEnvironmentConfigurationError(str(exc)) from exc

    def validate_plan_compatibility(
        self,
        plan: ExecutionPlan | Any,
        environment: EnvironmentContext,
    ) -> None:
        """Ensure plan metadata requirements are compatible with environment capabilities."""
        for task in plan.ordered_tasks:
            metadata = task.metadata if isinstance(task.metadata, dict) else {}

            required_orchestrator = metadata.get("required_compute_orchestrator")
            if (
                required_orchestrator is not None
                and not environment.supports("compute", required_orchestrator)
            ):
                raise InvalidEnvironmentConfigurationError(
                    f"task '{task.id}' requires orchestrator '{required_orchestrator}', "
                    f"got '{environment.get_compute_type()}'"
                )

            required_identity = metadata.get("required_identity_type")
            if required_identity is not None and not environment.supports(
                "identity", required_identity
            ):
                raise InvalidEnvironmentConfigurationError(
                    f"task '{task.id}' requires identity '{required_identity}', "
                    f"got '{environment.get_identity_type()}'"
                )

            required_topology = metadata.get("required_network_topology")
            if required_topology is not None and not environment.supports(
                "network_topology", required_topology
            ):
                raise InvalidEnvironmentConfigurationError(
                    f"task '{task.id}' requires network topology '{required_topology}', "
                    f"got '{environment.network.topology}'"
                )

            required_data_types = metadata.get("required_data_types")
            if required_data_types is not None:
                if not isinstance(required_data_types, list) or any(
                    not isinstance(item, str) or not item for item in required_data_types
                ):
                    raise InvalidEnvironmentConfigurationError(
                        f"task '{task.id}' has invalid required_data_types"
                    )
                missing_data_types = sorted(
                    {
                        data_type
                        for data_type in required_data_types
                        if not environment.supports("data_type", data_type)
                    }
                )
                if missing_data_types:
                    raise InvalidEnvironmentConfigurationError(
                        f"task '{task.id}' requires unavailable data types: "
                        + ", ".join(missing_data_types)
                    )

            required_compliance = metadata.get("required_compliance")
            if required_compliance is not None:
                if not isinstance(required_compliance, list) or any(
                    not isinstance(item, str) or not item for item in required_compliance
                ):
                    raise InvalidEnvironmentConfigurationError(
                        f"task '{task.id}' has invalid required_compliance"
                    )
                missing_compliance = sorted(
                    {
                        item
                        for item in required_compliance
                        if not environment.supports("compliance", item)
                    }
                )
                if missing_compliance:
                    raise InvalidEnvironmentConfigurationError(
                        f"task '{task.id}' requires unavailable compliance controls: "
                        + ", ".join(missing_compliance)
                    )
