"""Agent 14 self-improvement engine orchestration."""

from __future__ import annotations

from typing import Any

from app.self_improvement.evaluator import Evaluator
from app.self_improvement.logger import (
    EVALUATION_COMPLETED,
    IMPROVEMENTS_APPROVED,
    OPTIMIZATION_GENERATED,
    POLICY_FILTER_APPLIED,
    SELF_IMPROVEMENT_STARTED,
    log_event,
)
from app.self_improvement.models import ImprovementAction, OptimizationReport
from app.self_improvement.optimizer import Optimizer
from app.self_improvement.policy import ImprovementPolicy


class SelfImprovementEngine:
    """Deterministic self-improvement pipeline with policy-controlled outputs."""

    def __init__(
        self,
        evaluator: Evaluator | None = None,
        optimizer: Optimizer | None = None,
        policy: ImprovementPolicy | None = None,
    ) -> None:
        self._evaluator = evaluator or Evaluator()
        self._optimizer = optimizer or Optimizer()
        self._policy = policy or ImprovementPolicy()

    def run(self, memory_store: Any) -> list[ImprovementAction]:
        records = self._load_history(memory_store)
        log_event(SELF_IMPROVEMENT_STARTED, {"record_count": len(records)})

        evaluation = self._evaluator.evaluate(records)
        log_event(
            EVALUATION_COMPLETED,
            {
                "success_rate": evaluation.success_rate,
                "avg_latency": evaluation.avg_latency,
                "failure_patterns": len(evaluation.failure_patterns),
                "retry_patterns": len(evaluation.retry_patterns),
                "policy_violations": len(evaluation.policy_violations),
            },
        )

        generated = self._optimizer.optimize(evaluation)
        log_event(OPTIMIZATION_GENERATED, {"generated_count": len(generated)})

        approved = self._policy.approve(generated)
        log_event(
            POLICY_FILTER_APPLIED,
            {
                "generated_count": len(generated),
                "approved_count": len(approved),
                "confidence_threshold": self._policy.confidence_threshold,
            },
        )
        log_event(IMPROVEMENTS_APPROVED, {"approved_count": len(approved)})

        report = OptimizationReport(generated=generated, approved=approved)
        return list(report.approved)

    def _load_history(self, memory_store: Any) -> list:
        if hasattr(memory_store, "get_recent"):
            try:
                records = memory_store.get_recent(limit=200)
                if isinstance(records, list):
                    return records
            except Exception:
                return []
        return []


def run_self_improvement(memory_store: Any) -> list[ImprovementAction]:
    """Functional entrypoint for Agent 14 self-improvement pipeline."""
    return SelfImprovementEngine().run(memory_store)
