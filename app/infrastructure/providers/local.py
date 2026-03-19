"""Deterministic local infrastructure simulation provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.infrastructure.base import ContextInput, InfrastructureProvider, InfrastructureResult


class LocalInfrastructureProvider(InfrastructureProvider):
    """Simulates local deployments with deterministic output."""

    _PROVIDER_NAME = "local"

    def deploy(self, context: ContextInput) -> InfrastructureResult:
        payload = _canonicalize_context(context)
        services = tuple(payload.get("services", []))
        return InfrastructureResult(
            action="deploy",
            provider=self._PROVIDER_NAME,
            environment=str(payload.get("environment", "local")),
            state="deployed",
            details={
                "mode": "local-simulation",
                "services": services,
                "service_count": len(services),
            },
        )

    def destroy(self, context: ContextInput) -> InfrastructureResult:
        payload = _canonicalize_context(context)
        return InfrastructureResult(
            action="destroy",
            provider=self._PROVIDER_NAME,
            environment=str(payload.get("environment", "local")),
            state="destroyed",
            details={"mode": "local-simulation", "cleanup": "complete"},
        )

    def status(self, context: ContextInput) -> InfrastructureResult:
        payload = _canonicalize_context(context)
        return InfrastructureResult(
            action="status",
            provider=self._PROVIDER_NAME,
            environment=str(payload.get("environment", "local")),
            state="healthy",
            details={"mode": "local-simulation", "ready": True},
        )


def _canonicalize_context(context: ContextInput) -> dict[str, Any]:
    payload = _to_payload(context)
    return _canonicalize(payload)


def _to_payload(context: ContextInput) -> dict[str, Any]:
    if isinstance(context, Mapping):
        payload = dict(context)
    else:
        payload = context.to_dict() if hasattr(context, "to_dict") else {}
        if "environment" not in payload:
            payload["environment"] = getattr(context, "environment", "")
    return payload


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value
