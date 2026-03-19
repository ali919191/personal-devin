"""Agent 14/15 self-improvement public exports."""

from app.self_improvement.adaptation_engine import AdaptationEngine
from app.self_improvement.analyzer import Analyzer
from app.self_improvement.engine import SelfImprovementEngine, run_self_improvement
from app.self_improvement.evaluator import Evaluator
from app.self_improvement.handlers import IMPROVEMENT_HANDLERS, HandlerResult, ImprovementHandler
from app.self_improvement.loop import SelfImprovementLoop, run_self_improvement_loop
from app.self_improvement.models import (
    AdaptationResult,
    EvaluationResult,
    ExecutionRecord,
    FailureRecord,
    ImprovementAction,
    ImprovementType,
    OptimizationReport,
    Pattern,
    SelfImprovementAdaptation,
)
from app.self_improvement.optimizer import Optimizer
from app.self_improvement.pattern_detector import PatternDetector
from app.self_improvement.policy import AdaptationPolicy, ImprovementPolicy

__all__ = [
    # Agent 14
    "SelfImprovementEngine",
    "run_self_improvement",
    "Evaluator",
    "Optimizer",
    "ImprovementPolicy",
    "EvaluationResult",
    "ImprovementAction",
    "ImprovementType",
    "OptimizationReport",
    "IMPROVEMENT_HANDLERS",
    "HandlerResult",
    "ImprovementHandler",
    # Agent 15
    "SelfImprovementLoop",
    "run_self_improvement_loop",
    "Analyzer",
    "PatternDetector",
    "AdaptationEngine",
    "AdaptationPolicy",
    "ExecutionRecord",
    "FailureRecord",
    "Pattern",
    "SelfImprovementAdaptation",
    "AdaptationResult",
]
