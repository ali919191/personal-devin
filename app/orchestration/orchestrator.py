"""Deprecated compatibility orchestrator.

Canonical orchestration ownership moved to app.core.orchestrator in Agent 16.
This module remains as a compatibility layer for existing imports.
"""

from __future__ import annotations

from typing import Any
from warnings import warn

from app.core.logger import get_logger
from app.orchestration.models import OrchestrationRequest, OrchestrationResult, RunContext, TraceEntry
from app.orchestration.registry import OrchestrationRegistry, create_default_registry

logger = get_logger(__name__)


class Orchestrator:
    def __init__(self, registry: OrchestrationRegistry | None = None) -> None:
        warn(
            "app.orchestration.Orchestrator is deprecated; use app.core.Orchestrator",
            DeprecationWarning,
            stacklevel=2,
        )
        self._registry = registry or create_default_registry()

    def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        timestamps: dict[str, int] = {}
        step = 0
        trace_step = 0

        def mark(event: str) -> None:
            nonlocal step
            step += 1
            timestamps[event] = step

        def append_trace(
            stage: str,
            status: str,
            metadata: dict[str, Any] | None = None,
            error: str | None = None,
        ) -> None:
            nonlocal trace_step
            trace_step += 1
            entry_metadata = dict(metadata or {})
            if error:
                entry_metadata["error"] = error
            context.trace.append(
                TraceEntry(
                    stage=stage,
                    status=status,
                    step=trace_step,
                    metadata=entry_metadata,
                )
            )

        context = RunContext(
            run_id=request.run_id,
            goal=request.goal,
            plan=None,
            execution_result=None,
            memory_refs=[],
            improvements=[],
            trace=[],
            status="running",
            timestamps=timestamps,
        )

        self._log_stage("orchestration", "start", request.run_id, {"goal": request.goal})

        mark("planning_started")
        append_trace("planning", "start", {"run_id": request.run_id})
        self._log_stage("planning", "start", request.run_id)
        try:
            tasks = request.tasks or [
                {
                    "id": "task-1",
                    "description": request.goal,
                    "dependencies": [],
                }
            ]
            plan = self._registry.planning_engine(tasks)
            self._validate_plan(plan)
            context.plan = plan
            mark("planning_completed")
            append_trace("planning", "completed", {"run_id": request.run_id, "status": "ok"})
            self._log_stage("planning", "end", request.run_id, {"status": "ok"})
        except Exception as exc:
            mark("planning_failed")
            context.status = "failed"
            append_trace("planning", "error", {"run_id": request.run_id}, str(exc))
            self._log_stage_error("planning", request.run_id, str(exc))
            self._log_stage("orchestration", "end", request.run_id, {"status": "failed"})
            return OrchestrationResult(
                run_id=request.run_id,
                status="failed",
                context=context,
                error=str(exc),
            )

        mark("execution_started")
        append_trace("execution", "start", {"run_id": request.run_id})
        self._log_stage("execution", "start", request.run_id)
        execution_error = ""
        try:
            execution_result = self._registry.execution_engine(context.plan)
        except Exception as exc:
            execution_error = str(exc)
            execution_result = {
                "status": "failed",
                "total_tasks": self._safe_total_tasks(context.plan),
                "completed_tasks": 0,
                "failed_tasks": self._safe_total_tasks(context.plan),
                "skipped_tasks": 0,
            }
            append_trace("execution", "error", {"run_id": request.run_id}, execution_error)
            self._log_stage_error("execution", request.run_id, execution_error)

        context.execution_result = execution_result
        execution_status = self._extract_execution_status(execution_result)
        if execution_status == "failed":
            context.status = "failed"
        mark("execution_completed")
        append_trace("execution", "completed", {"run_id": request.run_id, "status": execution_status})
        self._log_stage("execution", "end", request.run_id, {"status": execution_status})

        mark("memory_store_started")
        append_trace("memory_store", "start", {"run_id": request.run_id})
        self._log_stage("memory_store", "start", request.run_id)
        try:
            total_tasks = self._extract_metric(execution_result, "total_tasks")
            completed_tasks = self._extract_metric(execution_result, "completed_tasks")
            failed_tasks = self._extract_metric(execution_result, "failed_tasks")
            skipped_tasks = self._extract_metric(execution_result, "skipped_tasks")

            execution_memory = self._registry.memory_system.log_execution(
                status=execution_status,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                skipped_tasks=skipped_tasks,
                metadata={
                    "run_id": request.run_id,
                    "goal": request.goal,
                },
            )
            context.memory_refs.append(execution_memory.id)

            if execution_status == "failed":
                failure_memory = self._registry.memory_system.log_failure(
                    source="orchestrator",
                    error=execution_error or "execution_failed",
                    context={"run_id": request.run_id, "goal": request.goal},
                )
                context.memory_refs.append(failure_memory.id)
        except Exception as exc:
            append_trace("memory_store", "error", {"run_id": request.run_id}, str(exc))
            self._log_stage_error("memory_store", request.run_id, str(exc))
        mark("memory_store_completed")
        append_trace("memory_store", "completed", {"run_id": request.run_id, "refs": len(context.memory_refs)})
        self._log_stage("memory_store", "end", request.run_id, {"refs": len(context.memory_refs)})

        mark("reflection_started")
        append_trace("reflection", "start", {"run_id": request.run_id})
        self._log_stage("reflection", "start", request.run_id)
        try:
            loop_result = self._registry.agent_loop.run(request.goal)
            loop_status = getattr(loop_result, "status", "success")
            if loop_status in {"failure", "failed"}:
                context.status = "failed"
            elif loop_status == "partial" and context.status != "failed":
                context.status = "partial"
        except Exception as exc:
            context.status = "failed"
            append_trace("reflection", "error", {"run_id": request.run_id}, str(exc))
            self._log_stage_error("reflection", request.run_id, str(exc))
        mark("reflection_completed")
        append_trace("reflection", "completed", {"run_id": request.run_id, "status": context.status})
        self._log_stage("reflection", "end", request.run_id, {"status": context.status})

        mark("improvement_started")
        append_trace("improvement", "start", {"run_id": request.run_id})
        self._log_stage("improvement", "start", request.run_id)
        try:
            actions = self._registry.improvement_engine.select_actions(request.signals)
            context.improvements = self._registry.improvement_engine.apply(actions)
        except Exception as exc:
            context.status = "failed"
            append_trace("improvement", "error", {"run_id": request.run_id}, str(exc))
            self._log_stage_error("improvement", request.run_id, str(exc))
        mark("improvement_completed")
        append_trace(
            "improvement",
            "completed",
            {"run_id": request.run_id, "applied_count": len(context.improvements)},
        )
        self._log_stage(
            "improvement",
            "end",
            request.run_id,
            {"applied_count": len(context.improvements)},
        )

        if context.status == "running":
            context.status = "success"

        mark("orchestration_completed")
        self._log_stage("orchestration", "end", request.run_id, {"status": context.status})

        return OrchestrationResult(
            run_id=request.run_id,
            status=context.status,
            context=context,
            error="",
        )

    def _validate_plan(self, plan: Any) -> None:
        total_tasks = self._safe_total_tasks(plan)
        if total_tasks <= 0:
            raise ValueError("plan must contain at least one task")

    def _safe_total_tasks(self, plan: Any) -> int:
        metadata = getattr(plan, "metadata", None)
        value = getattr(metadata, "total_tasks", 0)
        return int(value) if isinstance(value, int) else 0

    def _extract_execution_status(self, execution_result: Any) -> str:
        raw_status = self._extract_field(execution_result, "status")
        if hasattr(raw_status, "value"):
            raw_status = getattr(raw_status, "value")
        status = str(raw_status or "failed").lower()
        return "failed" if status in {"failed", "failure"} else "success"

    def _extract_metric(self, execution_result: Any, key: str) -> int:
        value = self._extract_field(execution_result, key)
        return int(value) if isinstance(value, int) else 0

    def _extract_field(self, payload: Any, key: str) -> Any:
        if isinstance(payload, dict):
            return payload.get(key)
        return getattr(payload, key, None)

    def _log_stage(
        self,
        stage: str,
        status: str,
        run_id: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "stage": stage,
            "status": status,
            "run_id": run_id,
        }
        if extra:
            payload.update(extra)
        logger.info("orchestration_stage", payload)

    def _log_stage_error(self, stage: str, run_id: str, error: str) -> None:
        logger.error(
            "orchestration_stage",
            error=error,
            data={
                "stage": stage,
                "status": "error",
                "run_id": run_id,
            },
        )
