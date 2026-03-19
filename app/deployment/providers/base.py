"""Abstract base class for deployment providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class DeploymentProvider(ABC):
    """Abstract deployment provider interface.

    Implementors must execute the given steps and return a list of
    per-step result records.  No external side effects are permitted
    outside the explicit deploy contract.
    """

    @abstractmethod
    def deploy(self, steps: list[dict]) -> list[dict]:
        """Execute deployment steps and return executed step records.

        Args:
            steps: Ordered list of step dictionaries from a DeploymentRequest.

        Returns:
            List of result records, one per input step.
        """
