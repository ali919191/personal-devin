"""Structured event logging for Agent 14 self-improvement pipeline."""

from __future__ import annotations

from app.core.logger import get_logger

SELF_IMPROVEMENT_STARTED = "SELF_IMPROVEMENT_STARTED"
EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
OPTIMIZATION_GENERATED = "OPTIMIZATION_GENERATED"
POLICY_FILTER_APPLIED = "POLICY_FILTER_APPLIED"
IMPROVEMENTS_APPROVED = "IMPROVEMENTS_APPROVED"


logger = get_logger(__name__)


def log_event(event: str, data: dict) -> None:
    """Emit structured deterministic event logs for the pipeline."""
    logger.info(event, data)
