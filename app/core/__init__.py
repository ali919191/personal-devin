"""Core module."""

from app.core.deployment_context import DeploymentContext
from app.core.logger import StructuredLogger, get_logger
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

__all__ = [
	"StructuredLogger",
	"get_logger",
	"DeploymentContext",
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


def __getattr__(name: str):
	if name in {
		"OrchestrationRequest",
		"OrchestrationPhaseTrace",
		"OrchestrationResult",
		"OrchestrationController",
		"run_system",
		"Orchestrator",
	}:
		from app.core.orchestrator import (
			OrchestrationController,
			OrchestrationPhaseTrace,
			OrchestrationRequest,
			OrchestrationResult,
			run_system,
		)

		mapping = {
			"OrchestrationRequest": OrchestrationRequest,
			"OrchestrationPhaseTrace": OrchestrationPhaseTrace,
			"OrchestrationResult": OrchestrationResult,
			"OrchestrationController": OrchestrationController,
			"run_system": run_system,
			"Orchestrator": OrchestrationController,
		}
		return mapping[name]

	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
