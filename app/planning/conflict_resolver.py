"""Deterministic conflict resolution for adaptation candidates."""

from __future__ import annotations

from collections import defaultdict

from app.core.logger import get_logger
from app.planning.models import Adaptation
from app.planning.policy import Policy, default_policies

logger = get_logger(__name__)


class ConflictResolver:
    """Resolve competing adaptations with deterministic policy-first ordering."""

    def __init__(self, policies: dict[str, Policy] | None = None) -> None:
        self._policies = policies or default_policies()

    def resolve(self, adaptations: list[Adaptation]) -> list[Adaptation]:
        grouped: dict[str, list[Adaptation]] = defaultdict(list)
        dropped: list[dict[str, str]] = []
        selected: list[str] = []
        reasoning: list[str] = []
        conflicts_detected = 0

        for adaptation in adaptations:
            grouped[adaptation.target].append(adaptation)

        for target, candidates in sorted(grouped.items(), key=lambda item: item[0]):
            if len({candidate.action for candidate in candidates}) > 1:
                conflicts_detected += 1
                reasoning.append(f"target={target}:multiple_actions")

            valid_candidates: list[Adaptation] = []
            for candidate in candidates:
                policy = self._policies.get(candidate.policy)
                if policy is None:
                    conflicts_detected += 1
                    dropped.append({"id": candidate.id, "reason": "policy_missing"})
                    reasoning.append(f"drop={candidate.id}:policy_missing")
                    continue

                threshold = policy.confidence_threshold
                if threshold is not None and candidate.confidence < threshold:
                    conflicts_detected += 1
                    dropped.append({"id": candidate.id, "reason": "below_confidence_threshold"})
                    reasoning.append(
                        f"drop={candidate.id}:confidence={candidate.confidence}<threshold={threshold}"
                    )
                    continue

                valid_candidates.append(candidate)

            if not valid_candidates:
                continue

            # Resolution pipeline:
            # 1) Policy precedence (higher priority wins)
            # 2) Confidence score tie-break (higher wins)
            # 3) Stable fallback ordering (created_at, id)
            ranked = sorted(
                valid_candidates,
                key=lambda candidate: (
                    -self._policies[candidate.policy].priority,
                    -candidate.confidence,
                    candidate.created_at,
                    candidate.id,
                ),
            )

            winner = ranked[0]
            selected.append(winner.id)
            if len(ranked) > 1:
                for loser in ranked[1:]:
                    dropped.append({"id": loser.id, "reason": "superseded"})
                    reasoning.append(f"drop={loser.id}:superseded_by={winner.id}")

        resolved: list[Adaptation] = []
        selected_set = set(selected)
        for adaptation in adaptations:
            if adaptation.id in selected_set:
                resolved.append(adaptation)

        # Stable final output ordering for deterministic behavior.
        resolved = sorted(
            resolved,
            key=lambda adaptation: (
                -self._policies[adaptation.policy].priority,
                -adaptation.confidence,
                adaptation.created_at,
                adaptation.id,
            ),
        )

        logger.info(
            "conflict_resolution",
            {
                "event": "conflict_resolution",
                "input_count": len(adaptations),
                "output_count": len(resolved),
                "conflicts_detected": conflicts_detected,
                "dropped": dropped,
                "selected": selected,
                "reasoning": reasoning,
            },
        )

        return resolved
