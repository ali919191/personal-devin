"""Core module."""

from app.core.logger import StructuredLogger, get_logger
from app.core.orchestrator import (
	OrchestrationController,
	OrchestrationPhaseTrace,
	OrchestrationRequest,
	OrchestrationResult,
	run_system,
)
from app.core.recovery import (
	DeterministicFailureError,
	FailureCategory,
	PolicyViolationError,
	RecoveryAttempt,
	RecoveryManager,
	RecoveryResult,
	RetryPolicy,
	TransientFailureError,
	categorize_failure,
)
from app.core.state import (
	InvalidStateTransitionError,
	StateTransition,
	SystemState,
	SystemStateMachine,
	SystemStateSnapshot,
)

Orchestrator = OrchestrationController

__all__ = [
	"StructuredLogger",
	"get_logger",
	"SystemState",
	"StateTransition",
	"SystemStateSnapshot",
	"SystemStateMachine",
	"InvalidStateTransitionError",
	"FailureCategory",
	"RetryPolicy",
	"RecoveryAttempt",
	"RecoveryResult",
	"RecoveryManager",
	"TransientFailureError",
	"DeterministicFailureError",
	"PolicyViolationError",
	"categorize_failure",
	"OrchestrationRequest",
	"OrchestrationPhaseTrace",
	"OrchestrationResult",
	"OrchestrationController",
	"Orchestrator",
	"run_system",
]
