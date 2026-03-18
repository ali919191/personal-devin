from dataclasses import dataclass
from typing import Any, Callable

from app.agent.agent_loop import AgentLoop
from app.execution.runner import run_plan
from app.improvement.engine import ImprovementEngine
from app.memory.service import MemoryService
from app.planning.planner import build_execution_plan


@dataclass
class OrchestrationRegistry:
    planning_engine: Callable[[list[dict[str, Any]]], Any]
    execution_engine: Callable[[Any], Any]
    memory_system: MemoryService
    agent_loop: AgentLoop
    improvement_engine: ImprovementEngine


def create_default_registry() -> OrchestrationRegistry:
    memory = MemoryService()
    return OrchestrationRegistry(
        planning_engine=build_execution_plan,
        execution_engine=run_plan,
        memory_system=memory,
        agent_loop=AgentLoop(memory_service=memory),
        improvement_engine=ImprovementEngine(),
    )
