"""Agent 15 self-improvement loop orchestrator."""

from __future__ import annotations

from typing import Any

from app.self_improvement.adaptation_engine import AdaptationEngine
from app.self_improvement.analyzer import Analyzer
from app.self_improvement.logger import (
    ANALYSIS_COMPLETED,
    ADAPTATIONS_APPROVED,
    ADAPTATIONS_GENERATED,
    LOOP_COMPLETED,
    LOOP_STARTED,
    PATTERNS_DETECTED,
    POLICY_VALIDATED,
    log_event,
)
from app.self_improvement.models import AdaptationResult, SelfImprovementAdaptation
from app.self_improvement.pattern_detector import PatternDetector
from app.self_improvement.policy import AdaptationPolicy

_DEFAULT_MEMORY_LIMIT = 200


class SelfImprovementLoop:
    """Deterministic self-improvement loop: load → analyze → detect → adapt → validate."""

    def __init__(
        self,
        analyzer: Analyzer | None = None,
        detector: PatternDetector | None = None,
        engine: AdaptationEngine | None = None,
        policy: AdaptationPolicy | None = None,
        memory_limit: int = _DEFAULT_MEMORY_LIMIT,
    ) -> None:
        self._analyzer = analyzer or Analyzer()
        self._detector = detector or PatternDetector()
        self._engine = engine or AdaptationEngine()
        self._policy = policy or AdaptationPolicy()
        self._memory_limit = memory_limit

    def run(self, memory_store: Any) -> AdaptationResult:
        """Execute the full self-improvement loop and return an AdaptationResult."""
        log_event(LOOP_STARTED, {"memory_limit": self._memory_limit})

        executions = self._analyzer.load_executions(memory_store, limit=self._memory_limit)
        failures = self._analyzer.load_failures(memory_store, limit=self._memory_limit)
        log_event(ANALYSIS_COMPLETED, {"executions": len(executions), "failures": len(failures)})

        patterns = self._detector.detect(executions, failures)
        log_event(PATTERNS_DETECTED, {"pattern_count": len(patterns), "kinds": [p.kind for p in patterns]})

        adaptations = self._engine.generate(patterns)
        log_event(ADAPTATIONS_GENERATED, {"count": len(adaptations)})

        approved, rejected = self._policy.validate(adaptations)
        log_event(POLICY_VALIDATED, {"approved": len(approved), "rejected": len(rejected)})
        log_event(ADAPTATIONS_APPROVED, {"approved_ids": [a.adaptation_id for a in approved]})

        result = AdaptationResult(
            patterns_detected=patterns,
            adaptations_generated=adaptations,
            adaptations_approved=approved,
            adaptations_rejected=rejected,
        )

        log_event(
            LOOP_COMPLETED,
            {
                "patterns": len(patterns),
                "generated": len(adaptations),
                "approved": len(approved),
                "rejected": len(rejected),
            },
        )
        return result


def run_self_improvement_loop(memory_store: Any) -> AdaptationResult:
    """Functional entrypoint for Agent 15 self-improvement loop."""
    return SelfImprovementLoop().run(memory_store)
