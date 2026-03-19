from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.planning.conflict_resolver import ConflictResolver
from app.planning.models import Adaptation
from app.planning.policy import Policy


def _adaptation(
    *,
    adaptation_id: str,
    target: str,
    action: str,
    confidence: float,
    policy: str,
    priority: int,
    created_at: datetime,
) -> Adaptation:
    return Adaptation(
        id=adaptation_id,
        target=target,
        action=action,
        confidence=confidence,
        policy=policy,
        priority=priority,
        created_at=created_at,
    )


def test_conflicting_adaptations_choose_correct_winner() -> None:
    now = datetime.now(UTC)
    resolver = ConflictResolver(
        policies={
            "reliability": Policy(name="reliability", priority=80, confidence_threshold=0.6),
            "performance": Policy(name="performance", priority=50, confidence_threshold=0.5),
        }
    )

    adaptations = [
        _adaptation(
            adaptation_id="a-001",
            target="timeout",
            action="set_timeout_10",
            confidence=0.95,
            policy="performance",
            priority=1,
            created_at=now,
        ),
        _adaptation(
            adaptation_id="a-002",
            target="timeout",
            action="set_timeout_8",
            confidence=0.8,
            policy="reliability",
            priority=1,
            created_at=now + timedelta(seconds=1),
        ),
    ]

    resolved = resolver.resolve(adaptations)

    assert [item.id for item in resolved] == ["a-002"]


def test_low_confidence_removal() -> None:
    now = datetime.now(UTC)
    resolver = ConflictResolver(
        policies={
            "safety": Policy(name="safety", priority=100, confidence_threshold=0.8),
        }
    )

    adaptations = [
        _adaptation(
            adaptation_id="a-001",
            target="retry_limit",
            action="set_retry_3",
            confidence=0.75,
            policy="safety",
            priority=1,
            created_at=now,
        )
    ]

    resolved = resolver.resolve(adaptations)

    assert resolved == []


def test_policy_precedence_enforcement() -> None:
    now = datetime.now(UTC)
    resolver = ConflictResolver(
        policies={
            "policy_high": Policy(name="policy_high", priority=10, confidence_threshold=None),
            "policy_low": Policy(name="policy_low", priority=5, confidence_threshold=None),
        }
    )

    adaptations = [
        _adaptation(
            adaptation_id="a-001",
            target="preferred_tool",
            action="use_filesystem",
            confidence=0.99,
            policy="policy_low",
            priority=1,
            created_at=now,
        ),
        _adaptation(
            adaptation_id="a-002",
            target="preferred_tool",
            action="use_api",
            confidence=0.8,
            policy="policy_high",
            priority=1,
            created_at=now + timedelta(seconds=1),
        ),
    ]

    resolved = resolver.resolve(adaptations)

    assert len(resolved) == 1
    assert resolved[0].id == "a-002"


def test_deterministic_output_ordering() -> None:
    now = datetime.now(UTC)
    resolver = ConflictResolver(
        policies={
            "performance": Policy(name="performance", priority=50, confidence_threshold=0.5),
        }
    )

    adaptations = [
        _adaptation(
            adaptation_id="a-002",
            target="timeout",
            action="set_timeout_10",
            confidence=0.9,
            policy="performance",
            priority=1,
            created_at=now + timedelta(seconds=1),
        ),
        _adaptation(
            adaptation_id="a-001",
            target="retry_limit",
            action="set_retry_3",
            confidence=0.9,
            policy="performance",
            priority=1,
            created_at=now,
        ),
    ]

    resolved = resolver.resolve(adaptations)

    assert [item.id for item in resolved] == ["a-001", "a-002"]


def test_idempotency_same_input_same_output() -> None:
    now = datetime.now(UTC)
    resolver = ConflictResolver(
        policies={
            "reliability": Policy(name="reliability", priority=80, confidence_threshold=0.5),
            "preference": Policy(name="preference", priority=20, confidence_threshold=None),
        }
    )

    adaptations = [
        _adaptation(
            adaptation_id="a-001",
            target="preferred_tool",
            action="use_api",
            confidence=0.6,
            policy="preference",
            priority=1,
            created_at=now,
        ),
        _adaptation(
            adaptation_id="a-002",
            target="preferred_tool",
            action="use_filesystem",
            confidence=0.7,
            policy="reliability",
            priority=1,
            created_at=now + timedelta(seconds=1),
        ),
        _adaptation(
            adaptation_id="a-003",
            target="timeout",
            action="set_timeout_10",
            confidence=0.65,
            policy="reliability",
            priority=1,
            created_at=now + timedelta(seconds=2),
        ),
    ]

    first = resolver.resolve(adaptations)
    second = resolver.resolve(adaptations)
    third = resolver.resolve(first)

    assert first == second
    assert third == first
