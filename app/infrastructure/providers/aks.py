"""AKS deployment simulation provider (stub-only, no SDK usage)."""

from __future__ import annotations

from typing import Any, Mapping

from app.infrastructure.base import ContextInput, InfrastructureProvider, InfrastructureResult


class AKSInfrastructureProvider(InfrastructureProvider):
    """Simulates AKS lifecycle operations deterministically."""

    _PROVIDER_NAME = "aks"

    def deploy(self, context: ContextInput) -> InfrastructureResult:
        payload = _canonicalize_context(context)
        services = tuple(payload.get("services", []))
        execution_id = str(payload.get("execution_id", "unknown"))
        return InfrastructureResult(
            action="deploy",
            provider=self._PROVIDER_NAME,
            environment=str(payload.get("environment", "aks")),
            state="deployed",
            details={
                "cluster": f"aks-{execution_id}",
                "node_pool": "system",
                "services": services,
                "simulation": True,
            },
        )

    def destroy(self, context: ContextInput) -> InfrastructureResult:
        payload = _canonicalize_context(context)
        execution_id = str(payload.get("execution_id", "unknown"))
        return InfrastructureResult(
            action="destroy",
            provider=self._PROVIDER_NAME,
            environment=str(payload.get("environment", "aks")),
            state="destroyed",
            details={"cluster": f"aks-{execution_id}", "simulation": True},
        )

    def status(self, context: ContextInput) -> InfrastructureResult:
        payload = _canonicalize_context(context)
        execution_id = str(payload.get("execution_id", "unknown"))
        return InfrastructureResult(
            action="status",
            provider=self._PROVIDER_NAME,
            environment=str(payload.get("environment", "aks")),
            state="ready",
            details={"cluster": f"aks-{execution_id}", "simulation": True},
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
