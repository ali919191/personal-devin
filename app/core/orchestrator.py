"""System orchestration and control layer for Agent 16."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Callable

from app.core.logger import get_logger
from app.core.recovery import (
    RecoveryAttempt,
    RecoveryManager,
    RetryPolicy,
)
from app.core.state import SystemState, SystemStateMachine, SystemStateSnapshot
from app.execution import ExecutionReport, ExecutionStatus, run_plan
from app.memory import MemoryService
from app.planning import build_execution_plan
from app.self_improvement import AdaptationResult, run_self_improvement_loop

logger = get_logger(__name__)

PlanningEngine = Callable[[list[dict[str, Any]]], Any]
ExecutionEngine = Callable[[Any, dict[str, Any], bool], ExecutionReport]
ImprovementRunner = Callable[[Any], AdaptationResult]

_NO_RETRY = RetryPolicy(max_retries=0)
_EXECUTION_RETRY = RetryPolicy(max_retries=1)
_REFLECTION_LIMIT = 25


@dataclass(frozen=True)
class OrchestrationRequest:
    """Input contract for a single orchestration run."""

    run_id: str
    goal: str
    tasks: list[dict[str, Any]] = field(default_factory=list)
    handlers: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be provided")
        if not self.goal:
            raise ValueError("goal must be provided")


@dataclass(frozen=True)
class OrchestrationPhaseTrace:
    """Phase-level trace entry for a system run."""

    phase: str
    state: SystemState
    status: str
    started_at: str
    completed_at: str
    duration_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe phase trace representation."""
        return {
            "phase": self.phase,
            "state": self.state.value,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "metadata": dict(self.metadata),
        }


@dataclass
class OrchestrationResult:
    """Typed result for an orchestrated system run."""

    run_id: str
    trace_id: str
    state: SystemState
    state_snapshot: SystemStateSnapshot
    plan: Any = None
    execution_report: ExecutionReport | None = None
    validation_summary: dict[str, Any] = field(default_factory=dict)
    reflection_summary: dict[str, Any] = field(default_factory=dict)
    improvement_result: AdaptationResult | None = None
    phase_traces: list[OrchestrationPhaseTrace] = field(default_factory=list)
    recovery_attempts: list[RecoveryAttempt] = field(default_factory=list)
    memory_record_ids: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def status(self) -> str:
        """Return the current terminal state as a string."""
        return self.state.value


class OrchestrationController:
    """Coordinates planning, execution, memory, and self-improvement."""

    def __init__(
        self,
        planning_engine: PlanningEngine | None = None,
        execution_engine: ExecutionEngine | None = None,
        memory_service: MemoryService | None = None,
        self_improvement_runner: ImprovementRunner | None = None,
        recovery_manager: RecoveryManager | None = None,
        stop_on_failure: bool = True,
        reflection_limit: int = _REFLECTION_LIMIT,
    ) -> None:
        self._planning_engine = planning_engine or build_execution_plan
        self._execution_engine = execution_engine or self._default_execution_engine
        self._memory_service = memory_service or MemoryService()
        self._self_improvement_runner = (
            self_improvement_runner or run_self_improvement_loop
        )
        self._recovery_manager = recovery_manager or RecoveryManager()
        self._stop_on_failure = stop_on_failure
        self._reflection_limit = reflection_limit

    def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Execute the full deterministic system lifecycle."""
        trace_id = f"trace-{request.run_id}"
        state_machine = SystemStateMachine(request.run_id, trace_id)
        phase_traces: list[OrchestrationPhaseTrace] = []
        recovery_attempts: list[RecoveryAttempt] = []
        memory_record_ids: list[str] = []
        error = ""

        logger.info(
            "orchestration_run_started",
            {"run_id": request.run_id, "trace_id": trace_id, "goal": request.goal},
        )

        plan = self._run_phase(
            phase="planning",
            target_state=SystemState.PLANNING,
            operation=lambda: self._planning_engine(self._default_tasks(request)),
            state_machine=state_machine,
            phase_traces=phase_traces,
            recovery_attempts=recovery_attempts,
            retry_policy=_NO_RETRY,
            trace_id=trace_id,
        )
        if plan is None:
            error = self._phase_error(phase_traces)
            return self._build_result(
                request=request,
                state_machine=state_machine,
                phase_traces=phase_traces,
                recovery_attempts=recovery_attempts,
                memory_record_ids=memory_record_ids,
                error=error,
            )

        execution_report = self._run_phase(
            phase="executing",
            target_state=SystemState.EXECUTING,
            operation=lambda: self._execution_engine(
                plan,
                dict(request.handlers),
                self._stop_on_failure,
            ),
            state_machine=state_machine,
            phase_traces=phase_traces,
            recovery_attempts=recovery_attempts,
            retry_policy=_EXECUTION_RETRY,
            trace_id=trace_id,
        )
        if execution_report is None:
            error = self._phase_error(phase_traces)
            return self._build_result(
                request=request,
                state_machine=state_machine,
                phase_traces=phase_traces,
                recovery_attempts=recovery_attempts,
                memory_record_ids=memory_record_ids,
                plan=plan,
                error=error,
            )

        validation_summary = self._run_phase(
            phase="validating",
            target_state=SystemState.VALIDATING,
            operation=lambda: self._validate_execution_report(execution_report),
            state_machine=state_machine,
            phase_traces=phase_traces,
            recovery_attempts=recovery_attempts,
            retry_policy=_NO_RETRY,
            trace_id=trace_id,
        )
        if validation_summary is None:
            error = self._phase_error(phase_traces)
            return self._build_result(
                request=request,
                state_machine=state_machine,
                phase_traces=phase_traces,
                recovery_attempts=recovery_attempts,
                memory_record_ids=memory_record_ids,
                plan=plan,
                execution_report=execution_report,
                error=error,
            )

        reflection_summary = self._run_phase(
            phase="reflecting",
            target_state=SystemState.REFLECTING,
            operation=lambda: self._reflect(
                request=request,
                execution_report=execution_report,
                trace_id=trace_id,
                memory_record_ids=memory_record_ids,
            ),
            state_machine=state_machine,
            phase_traces=phase_traces,
            recovery_attempts=recovery_attempts,
            retry_policy=_NO_RETRY,
            trace_id=trace_id,
        )
        if reflection_summary is None:
            error = self._phase_error(phase_traces)
            return self._build_result(
                request=request,
                state_machine=state_machine,
                phase_traces=phase_traces,
                recovery_attempts=recovery_attempts,
                memory_record_ids=memory_record_ids,
                plan=plan,
                execution_report=execution_report,
                validation_summary=validation_summary,
                error=error,
            )

        improvement_result = self._run_phase(
            phase="improving",
            target_state=SystemState.IMPROVING,
            operation=lambda: self._improve(memory_record_ids),
            state_machine=state_machine,
            phase_traces=phase_traces,
            recovery_attempts=recovery_attempts,
            retry_policy=_NO_RETRY,
            trace_id=trace_id,
        )
        if improvement_result is None:
            error = self._phase_error(phase_traces)
            return self._build_result(
                request=request,
                state_machine=state_machine,
                phase_traces=phase_traces,
                recovery_attempts=recovery_attempts,
                memory_record_ids=memory_record_ids,
                plan=plan,
                execution_report=execution_report,
                validation_summary=validation_summary,
                reflection_summary=reflection_summary,
                error=error,
            )

        terminal_state = (
            SystemState.FAILED
            if execution_report.status == ExecutionStatus.FAILED
            else SystemState.COMPLETED
        )
        terminal_reason = (
            "execution_report_failed"
            if terminal_state == SystemState.FAILED
            else "run_completed"
        )
        state_machine.transition_to(
            terminal_state,
            reason=terminal_reason,
            metadata={"trace_id": trace_id},
        )
        logger.info(
            "orchestration_run_completed",
            {
                "run_id": request.run_id,
                "trace_id": trace_id,
                "state": terminal_state.value,
            },
        )

        return self._build_result(
            request=request,
            state_machine=state_machine,
            phase_traces=phase_traces,
            recovery_attempts=recovery_attempts,
            memory_record_ids=memory_record_ids,
            plan=plan,
            execution_report=execution_report,
            validation_summary=validation_summary,
            reflection_summary=reflection_summary,
            improvement_result=improvement_result,
        )

    def _run_phase(
        self,
        phase: str,
        target_state: SystemState,
        operation: Callable[[], Any],
        state_machine: SystemStateMachine,
        phase_traces: list[OrchestrationPhaseTrace],
        recovery_attempts: list[RecoveryAttempt],
        retry_policy: RetryPolicy,
        trace_id: str,
    ) -> Any | None:
        state_machine.transition_to(
            target_state,
            reason=f"{phase}_started",
            metadata={"trace_id": trace_id},
        )

        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        logger.info(
            "orchestrator_phase_started",
            {"phase": phase, "trace_id": trace_id, "state": target_state.value},
        )

        recovery_result = self._recovery_manager.execute(
            phase=phase,
            operation=operation,
            retry_policy=retry_policy,
        )
        recovery_attempts.extend(recovery_result.attempts)

        completed_at = datetime.now(UTC)
        duration_seconds = round(perf_counter() - started_clock, 6)
        metadata = {
            "trace_id": trace_id,
            "failed_attempts": len(recovery_result.attempts),
        }

        if not recovery_result.success:
            metadata["error"] = recovery_result.final_error
            if recovery_result.failure_category is not None:
                metadata["failure_category"] = recovery_result.failure_category.value

            phase_traces.append(
                OrchestrationPhaseTrace(
                    phase=phase,
                    state=target_state,
                    status="failed",
                    started_at=started_at.isoformat(),
                    completed_at=completed_at.isoformat(),
                    duration_seconds=duration_seconds,
                    metadata=metadata,
                )
            )
            state_machine.transition_to(
                SystemState.FAILED,
                reason=f"{phase}_failed",
                metadata={"trace_id": trace_id, "error": recovery_result.final_error},
            )
            logger.error(
                "orchestrator_phase_failed",
                error=recovery_result.final_error,
                data={"phase": phase, "trace_id": trace_id},
            )
            return None

        phase_traces.append(
            OrchestrationPhaseTrace(
                phase=phase,
                state=target_state,
                status="completed",
                started_at=started_at.isoformat(),
                completed_at=completed_at.isoformat(),
                duration_seconds=duration_seconds,
                metadata=metadata,
            )
        )
        logger.info(
            "orchestrator_phase_completed",
            {
                "phase": phase,
                "trace_id": trace_id,
                "duration_seconds": duration_seconds,
                "state": target_state.value,
            },
        )
        return recovery_result.value

    def _default_tasks(self, request: OrchestrationRequest) -> list[dict[str, Any]]:
        if request.tasks:
            return list(request.tasks)
        return [
            {
                "id": "task-1",
                "description": request.goal,
                "dependencies": [],
            }
        ]

    def _default_execution_engine(
        self,
        plan: Any,
        handlers: dict[str, Any],
        stop_on_failure: bool,
    ) -> ExecutionReport:
        return run_plan(plan, handlers=handlers, stop_on_failure=stop_on_failure)

    def _validate_execution_report(
        self,
        execution_report: ExecutionReport,
    ) -> dict[str, Any]:
        task_count = len(execution_report.tasks)
        if task_count != execution_report.total_tasks:
            raise ValueError("execution report task count does not match total_tasks")

        counted_total = (
            execution_report.completed_tasks
            + execution_report.failed_tasks
            + execution_report.skipped_tasks
        )
        if counted_total != execution_report.total_tasks:
            raise ValueError("execution report counts do not add up to total_tasks")

        if execution_report.failed_tasks > 0 and execution_report.status != ExecutionStatus.FAILED:
            raise ValueError("failed execution report must have failed status")

        if (
            execution_report.failed_tasks == 0
            and execution_report.skipped_tasks == 0
            and execution_report.status != ExecutionStatus.COMPLETED
        ):
            raise ValueError("successful execution report must have completed status")

        return {
            "status": execution_report.status.value,
            "total_tasks": execution_report.total_tasks,
            "completed_tasks": execution_report.completed_tasks,
            "failed_tasks": execution_report.failed_tasks,
            "skipped_tasks": execution_report.skipped_tasks,
        }

    def _reflect(
        self,
        request: OrchestrationRequest,
        execution_report: ExecutionReport,
        trace_id: str,
        memory_record_ids: list[str],
    ) -> dict[str, Any]:
        execution_memory = self._memory_service.log_execution(
            status=execution_report.status.value,
            total_tasks=execution_report.total_tasks,
            completed_tasks=execution_report.completed_tasks,
            failed_tasks=execution_report.failed_tasks,
            skipped_tasks=execution_report.skipped_tasks,
            metadata={"run_id": request.run_id, "goal": request.goal, "trace_id": trace_id},
        )
        memory_record_ids.append(execution_memory.id)

        for task in execution_report.tasks:
            task_memory = self._memory_service.log_task(
                task_id=task.id,
                status=task.status.value,
                output=task.output,
                error=task.error,
                skip_reason=task.skip_reason,
            )
            memory_record_ids.append(task_memory.id)

        if execution_report.status == ExecutionStatus.FAILED:
            failure_memory = self._memory_service.log_failure(
                source="orchestrator",
                error=self._failure_reason(execution_report),
                context={"run_id": request.run_id, "trace_id": trace_id},
            )
            memory_record_ids.append(failure_memory.id)

        recent_records = self._memory_service.get_recent(limit=self._reflection_limit)
        reflection_record = self._memory_service.log_decision(
            decision="reflection_snapshot",
            reason="prepared deterministic context for self-improvement",
            context={
                "run_id": request.run_id,
                "trace_id": trace_id,
                "recent_record_count": len(recent_records),
            },
        )
        memory_record_ids.append(reflection_record.id)

        return {
            "recent_record_count": len(recent_records),
            "memory_record_count": len(memory_record_ids),
            "reflection_record_id": reflection_record.id,
        }

    def _improve(self, memory_record_ids: list[str]) -> AdaptationResult:
        improvement_result = self._self_improvement_runner(self._memory_service)
        stored = self._memory_service.store_improvements(
            improvement_result.adaptations_approved
        )
        memory_record_ids.extend(record.id for record in stored)
        return improvement_result

    def _failure_reason(self, execution_report: ExecutionReport) -> str:
        for task in execution_report.tasks:
            if task.error:
                return task.error
        return "execution_failed"

    def _phase_error(
        self,
        phase_traces: list[OrchestrationPhaseTrace],
    ) -> str:
        for trace in reversed(phase_traces):
            error = trace.metadata.get("error")
            if isinstance(error, str) and error:
                return error
        return "orchestration_failed"

    def _build_result(
        self,
        request: OrchestrationRequest,
        state_machine: SystemStateMachine,
        phase_traces: list[OrchestrationPhaseTrace],
        recovery_attempts: list[RecoveryAttempt],
        memory_record_ids: list[str],
        plan: Any = None,
        execution_report: ExecutionReport | None = None,
        validation_summary: dict[str, Any] | None = None,
        reflection_summary: dict[str, Any] | None = None,
        improvement_result: AdaptationResult | None = None,
        error: str = "",
    ) -> OrchestrationResult:
        return OrchestrationResult(
            run_id=request.run_id,
            trace_id=f"trace-{request.run_id}",
            state=state_machine.state,
            state_snapshot=state_machine.snapshot(),
            plan=plan,
            execution_report=execution_report,
            validation_summary=dict(validation_summary or {}),
            reflection_summary=dict(reflection_summary or {}),
            improvement_result=improvement_result,
            phase_traces=list(phase_traces),
            recovery_attempts=list(recovery_attempts),
            memory_record_ids=list(memory_record_ids),
            error=error,
        )


def run_system(request: OrchestrationRequest) -> OrchestrationResult:
    """Convenience entrypoint for full-system orchestration."""
    return OrchestrationController().run(request)