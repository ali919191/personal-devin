"""Adaptive execution engine converting improvements to policy-controlled modifiers."""

from __future__ import annotations

from typing import Any

from app.adaptation.models import Adaptation
from app.adaptation.registry import AdaptationRegistry, create_default_registry
from app.core.logger import get_logger

logger = get_logger(__name__)


class AdaptationEngine:
    """Generates and applies deterministic, policy-gated execution adaptations."""

    def __init__(self, registry: AdaptationRegistry | None = None) -> None:
        self._registry = registry or create_default_registry()

    def generate(self, improvement_output: list[dict[str, Any]]) -> list[Adaptation]:
        adaptations: list[Adaptation] = []

        for index, item in enumerate(improvement_output, start=1):
            action_type = str(item.get("action_type", "")).strip()
            source = str(item.get("source", "unknown"))
            confidence_raw = item.get("confidence", 0.0)
            confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.0

            adaptation_type, payload = self._map_action_to_adaptation(action_type)
            if adaptation_type is None or payload is None:
                logger.info(
                    "adaptation_generation_skipped",
                    {
                        "source": source,
                        "action_type": action_type,
                        "reason": "unmapped_action",
                    },
                )
                continue

            adaptation = Adaptation(
                id=f"adaptation-{index:03d}",
                source=source,
                type=adaptation_type,
                payload=payload,
                confidence=round(confidence, 4),
            )
            adaptations.append(adaptation)
            logger.info(
                "adaptation_generated",
                {
                    "adaptation_id": adaptation.id,
                    "source": adaptation.source,
                    "type": adaptation.type,
                    "confidence": adaptation.confidence,
                },
            )

        return adaptations

    def filter_valid(self, adaptations: list[Adaptation]) -> list[Adaptation]:
        valid: list[Adaptation] = []

        for adaptation in adaptations:
            if not self._registry.has(adaptation.type):
                logger.warning(
                    "adaptation_rejected",
                    {
                        "adaptation_id": adaptation.id,
                        "source": adaptation.source,
                        "type": adaptation.type,
                        "reason": "no_policy_registered",
                    },
                )
                continue

            policy = self._registry.get(adaptation.type)
            is_valid = policy.validate(adaptation)
            logger.info(
                "adaptation_validation",
                {
                    "adaptation_id": adaptation.id,
                    "source": adaptation.source,
                    "type": adaptation.type,
                    "policy": policy.__class__.__name__,
                    "valid": is_valid,
                },
            )
            if is_valid:
                valid.append(adaptation)

        return valid

    def apply(self, adaptations: list[Adaptation], execution_context: dict[str, Any]) -> dict[str, Any]:
        modifiers: dict[str, Any] = {}

        for adaptation in adaptations:
            if not self._registry.has(adaptation.type):
                continue

            policy = self._registry.get(adaptation.type)
            result = policy.apply(adaptation, execution_context)
            modifiers.update(result)
            logger.info(
                "adaptation_applied",
                {
                    "adaptation_id": adaptation.id,
                    "source": adaptation.source,
                    "type": adaptation.type,
                    "policy": policy.__class__.__name__,
                    "result": result,
                },
            )

        return modifiers

    def _map_action_to_adaptation(self, action_type: str) -> tuple[str | None, dict[str, Any] | None]:
        mapping: dict[str, tuple[str, dict[str, Any]]] = {
            "retry_strategy": ("retry_limit", {"retry_limit": 3}),
            "optimize_execution": ("timeout_seconds", {"timeout": 10}),
            "increase_logging": ("preferred_tool", {"preferred_tool": "api"}),
        }
        return mapping.get(action_type, (None, None))
