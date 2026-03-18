from __future__ import annotations

from typing import Any

from app.core.logger import get_logger
from app.orchestration.models import OrchestrationRequest, OrchestrationResult, RunContext
from app.orchestration.registry import OrchestrationRegistry, create_default_registry

logger = get_logger(__name__)


class Orchestrator:
    def __init__(self, registry: OrchestrationRegistry | None = None) -> None:
        self._registry = registry or create_default_registry()

    def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        timestamps: dict[str, int] = {}
        step = 0

        def mark(event: str) -> None:
            nonlocal step
            step += 1
            timestamps[event] = step

        context = RunContext(
            run_id=request.run_id,
            goal=request.goal,
            plan=None,
            execution_result=None,
            memory_refs=[],
            improvements=[],
            status="running",
            timestamps=timestamps,
        )

        logger.info("orchestration_started", {"run_id": request.run_id, "goal": request.goal})

        mark("planning_started")
        logger.info("planning_started", {"run_id": request.run_id})
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
            logger.info("planning_completed", {"run_id": request.run_id, "status": "ok"})
        except Exception as exc:
            mark("planning_failed")
            context.status = "failed"
            logger.error("planning_failed", error=str(exc), data={"run_id": request.run_id})
            logger.info("orchestration_completed", {"run_id": request.run_id, "status": "failed"})
            return OrchestrationResult(
                run_id=request.run_id,
                status="failed",
                context=context,
                error=str(exc),
            )

        mark("execution_started")
        logger.info("execution_started", {"run_id": request.run_id})
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
            logger.error("execution_failed", error=execution_error, data={"run_id": request.run_id})

        context.execution_result = execution_result
        execution_status = self._extract_execution_status(execution_result)
        if execution_status == "failed":
            context.status = "failed"
        mark("execution_completed")
        logger.info(
            "execution_completed",
            {"run_id": request.run_id, "status": execution_status},
        )

        mark("memory_store_started")
        logger.info("memory_store_started", {"run_id": request.run_id})
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
            logger.error("memory_store_failed", error=str(exc), data={"run_id": request.run_id})
        mark("memory_store_completed")
        logger.info("memory_store_completed", {"run_id": request.run_id, "refs": len(context.memory_refs)})

        mark("reflection_started")
        logger.info("reflection_started", {"run_id": request.run_id})
        try:
            loop_result = self._registry.agent_loop.run(request.goal)
            loop_status = getattr(loop_result, "status", "success")
            if loop_status in {"failure", "failed"}:
                context.status = "failed"
            elif loop_status == "partial" and context.status != "failed":
                context.status = "partial"
        except Exception as exc:
            context.status = "failed"
            logger.error("reflection_failed", error=str(exc), data={"run_id": request.run_id})
        mark("reflection_completed")
        logger.info("reflection_completed", {"run_id": request.run_id, "status": context.status})

        mark("improvement_started")
        logger.info("improvement_started", {"run_id": request.run_id})
        try:
            actions = self._registry.improvement_engine.select_actions(request.signals)
            context.improvements = self._registry.improvement_engine.apply(actions)
        except Exception as exc:
            context.status = "failed"
            logger.error("improvement_failed", error=str(exc), data={"run_id": request.run_id})
        mark("improvement_completed")
        logger.info(
            "improvement_completed",
            {
                "run_id": request.run_id,
                "applied_count": len(context.improvements),
            },
        )

        if context.status == "running":
            context.status = "success"

        mark("orchestration_completed")
        logger.info("orchestration_completed", {"run_id": request.run_id, "status": context.status})

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
