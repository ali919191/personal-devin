from dataclasses import dataclass, field
from typing import Any

from app.improvement.models import ImprovementResult, SignalRecord


@dataclass
class OrchestrationRequest:
    run_id: str
    goal: str
    tasks: list[dict[str, Any]] = field(default_factory=list)
    signals: list[SignalRecord] = field(default_factory=list)


@dataclass
class RunContext:
    run_id: str
    goal: str
    plan: Any
    execution_result: Any
    memory_refs: list[str]
    improvements: list[ImprovementResult]
    trace: list["TraceEntry"]
    status: str
    timestamps: dict[str, int]


@dataclass
class TraceEntry:
    stage: str
    status: str
    step: int
    metadata: dict[str, Any]


@dataclass
class OrchestrationResult:
    run_id: str
    status: str
    context: RunContext
    error: str
