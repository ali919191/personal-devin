"""Deterministic deployment orchestrator (simulation only)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.deployment_context import DeploymentContext
from app.core.logger import get_logger
from app.deployment.models import DeploymentPlan, DeploymentRequest, DeploymentResult, DeploymentStep

if TYPE_CHECKING:
    from app.deployment.providers.base import DeploymentProvider

logger = get_logger(__name__)


class DeploymentOrchestrator:
    """Build deterministic deployment plans and execute provider-based runs.

    Can be used in two modes:

    1. **Plan generation** — call :meth:`generate_plan` with a
       :class:`~app.core.deployment_context.DeploymentContext` to produce a
       structured, simulation-only :class:`~app.deployment.models.DeploymentPlan`.

    2. **Provider-based run** — call :meth:`run` with a
       :class:`~app.deployment.models.DeploymentRequest`.  When
       ``dry_run=True`` (default) the steps are returned immediately without
       touching the provider.  When ``dry_run=False`` the request is forwarded
       to the configured provider.

    Args:
        provider: Optional :class:`~app.deployment.providers.base.DeploymentProvider`
            instance.  Defaults to
            :class:`~app.deployment.providers.local_provider.LocalDeploymentProvider`
            when not supplied.
    """

    def __init__(self, provider: DeploymentProvider | None = None) -> None:
        if provider is None:
            from app.deployment.providers.local_provider import LocalDeploymentProvider
            provider = LocalDeploymentProvider()
        self._provider: DeploymentProvider = provider

    def run(self, request: DeploymentRequest) -> DeploymentResult:
        """Execute a provider-based deployment run.

        Dry-run (default):
            Returns a successful :class:`DeploymentResult` containing the
            original steps without invoking the provider.

        Live run (``dry_run=False``):
            Delegates to ``self._provider.deploy(request.steps)`` and wraps
            the output in a :class:`DeploymentResult`.  Any exception raised
            by the provider is caught and returned as a failure result.

        Args:
            request: Immutable :class:`DeploymentRequest` describing the run.

        Returns:
            A :class:`DeploymentResult` with ``success``, ``executed_steps``,
            and ``errors`` fields populated.
        """
        if request.dry_run:
            return DeploymentResult(
                success=True,
                executed_steps=list(request.steps),
                errors=[],
            )

        try:
            executed = self._provider.deploy(request.steps)
            return DeploymentResult(
                success=True,
                executed_steps=executed,
                errors=[],
            )
        except Exception as exc:  # noqa: BLE001
            return DeploymentResult(
                success=False,
                executed_steps=[],
                errors=[str(exc)],
            )

    def generate_plan(self, context: DeploymentContext) -> DeploymentPlan:
        """Translate deployment context into an explicit, deterministic plan."""
        if not isinstance(context, DeploymentContext):
            raise TypeError("context must be a DeploymentContext instance")

        logger.info(
            "deployment_planning_started",
            {
                "execution_id": context.execution_id,
                "environment": context.environment,
                "context": context.to_dict(),
            },
        )

        steps = self._build_steps(context)
        plan = DeploymentPlan(
            execution_id=context.execution_id,
            environment=context.environment,
            steps=steps,
            metadata={
                "mode": "simulation",
                "service_count": len(context.services),
                "artifact_count": len(context.artifacts),
                "source": "execution_output_translation",
                "context_metadata": context.metadata,
            },
        )

        logger.info(
            "deployment_plan_generated",
            {
                "execution_id": plan.execution_id,
                "environment": plan.environment,
                "step_count": len(plan.steps),
                "plan": plan.to_dict(),
            },
        )

        return plan

    def _build_steps(self, context: DeploymentContext) -> list[DeploymentStep]:
        """Create deterministic deployment steps from a deployment context."""
        steps: list[DeploymentStep] = []

        steps.append(
            DeploymentStep(
                index=1,
                step_id="step-001-prepare-environment",
                action="prepare_environment",
                target=context.environment,
                parameters={
                    "environment": context.environment,
                    "services": list(context.services),
                    "global_config": context.config,
                },
                metadata={"simulation": True},
            )
        )

        for offset, service in enumerate(context.services, start=2):
            artifact = self._resolve_artifact_for_service(context, service)
            steps.append(
                DeploymentStep(
                    index=offset,
                    step_id=f"step-{offset:03d}-deploy-{service}",
                    action="deploy_service",
                    target=service,
                    parameters={
                        "environment": context.environment,
                        "artifact": artifact,
                        "service_config": context.config.get(service, {}),
                    },
                    metadata={"simulation": True, "deployment_type": "rolling"},
                )
            )

        finalize_index = len(steps) + 1
        steps.append(
            DeploymentStep(
                index=finalize_index,
                step_id=f"step-{finalize_index:03d}-verify-deployment",
                action="verify_deployment",
                target=context.environment,
                parameters={
                    "services": list(context.services),
                    "checks": ["artifact_presence", "service_plan_coverage"],
                },
                metadata={"simulation": True},
            )
        )
        return steps

    @staticmethod
    def _resolve_artifact_for_service(
        context: DeploymentContext,
        service: str,
    ) -> dict[str, Any]:
        """Resolve service artifact deterministically from context artifacts."""
        artifact_payload = context.artifacts.get(service)
        if artifact_payload is None:
            artifact_payload = context.artifacts.get("default")
        if artifact_payload is None:
            artifact_payload = {
                "reference": "unmapped-artifact",
                "reason": f"No artifact mapping found for service '{service}'",
            }
        if isinstance(artifact_payload, dict):
            return dict(artifact_payload)
        return {"reference": str(artifact_payload)}
