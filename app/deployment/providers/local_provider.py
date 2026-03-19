"""Local deployment provider — simulates step execution in-process."""

from __future__ import annotations

from app.deployment.providers.base import DeploymentProvider


class LocalDeploymentProvider(DeploymentProvider):
    """In-process simulation provider with no external side effects.

    Each step is echoed back with a ``"executed"`` status marker,
    producing a deterministic one-to-one mapping of input to output.
    """

    def deploy(self, steps: list[dict]) -> list[dict]:
        """Simulate execution of each step locally.

        Args:
            steps: Ordered list of step dictionaries.

        Returns:
            List of result records where each entry wraps the original
            step under the ``"step"`` key and carries ``"status": "executed"``.
        """
        return [{"step": step, "status": "executed"} for step in steps]
