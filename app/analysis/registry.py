"""Pluggable registry for analysis detectors and recommendation engines."""

from __future__ import annotations

from typing import Any, Callable

from app.analysis.pattern_detector import PatternDetector
from app.analysis.recommendation_engine import RecommendationEngine

Detector = Callable[[list[dict[str, Any]], list[dict[str, Any]]], list[Any]]
RecommendationGenerator = Callable[[list[Any], list[str], list[str]], list[Any]]


class AnalysisRegistry:
    """Registers detector and recommendation components for analyzer composition."""

    def __init__(self) -> None:
        self._detectors: dict[str, Detector] = {}
        self._recommendation_engines: dict[str, RecommendationGenerator] = {}

    def register_detector(self, name: str, detector: Detector) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("detector name must be a non-empty string")
        if name in self._detectors:
            raise ValueError(f"detector already registered: {name}")
        self._detectors[name] = detector

    def register_recommendation_engine(self, name: str, engine: RecommendationGenerator) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("recommendation engine name must be a non-empty string")
        if name in self._recommendation_engines:
            raise ValueError(f"recommendation engine already registered: {name}")
        self._recommendation_engines[name] = engine

    def list_detectors(self) -> list[tuple[str, Detector]]:
        return [(name, self._detectors[name]) for name in sorted(self._detectors)]

    def list_recommendation_engines(self) -> list[tuple[str, RecommendationGenerator]]:
        return [(name, self._recommendation_engines[name]) for name in sorted(self._recommendation_engines)]


def create_default_registry() -> AnalysisRegistry:
    detector = PatternDetector()
    recommendation_engine = RecommendationEngine()

    registry = AnalysisRegistry()
    registry.register_detector("failure_patterns", detector.detect_failure_patterns)
    registry.register_detector("inefficiencies", lambda logs, memory: detector.detect_inefficiencies(logs))
    registry.register_detector("retry_loops", lambda logs, memory: detector.detect_retry_loops(logs))
    registry.register_recommendation_engine("default", recommendation_engine.generate)
    return registry
