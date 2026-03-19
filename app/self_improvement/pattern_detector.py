"""Deterministic pattern detector for Agent 15 self-improvement loop."""

from __future__ import annotations

from collections import Counter

from app.self_improvement.models import ExecutionRecord, FailureRecord, Pattern

# Thresholds — explicit, deterministic, no randomness.
_FAILURE_REPEAT_THRESHOLD = 2       # ≥2 occurrences of same error → repeated_failure
_HIGH_LATENCY_THRESHOLD = 3.0       # seconds
_LOW_SUCCESS_RATE_THRESHOLD = 0.7   # below 70% average → low_success_rate


class PatternDetector:
    """Detects recurring signals in execution and failure history using deterministic rules."""

    def detect(
        self,
        executions: list[ExecutionRecord],
        failures: list[FailureRecord],
    ) -> list[Pattern]:
        patterns: list[Pattern] = []
        patterns.extend(self._repeated_failures(failures))
        patterns.extend(self._high_latency(executions))
        patterns.extend(self._low_success_rate(executions))
        # Stable deterministic ordering: kind → signal string representation
        return sorted(patterns, key=lambda p: (p.kind, str(p.signal_value), p.pattern_id))

    # ------------------------------------------------------------------
    # Detection rules
    # ------------------------------------------------------------------

    def _repeated_failures(self, failures: list[FailureRecord]) -> list[Pattern]:
        counter: Counter[str] = Counter(f.error.strip() for f in failures)
        detected: list[Pattern] = []
        for error, count in sorted(counter.items()):
            if count < _FAILURE_REPEAT_THRESHOLD:
                continue
            confidence = min(0.95, round(0.5 + (count / 10.0), 4))
            detected.append(
                Pattern(
                    pattern_id=f"pattern-repeated-failure-{_slug(error)}",
                    kind="repeated_failure",
                    description=f"Error '{error}' occurred {count} time(s)",
                    signal_value=error,
                    occurrence_count=count,
                    confidence=confidence,
                )
            )
        return detected

    def _high_latency(self, executions: list[ExecutionRecord]) -> list[Pattern]:
        slow = [e for e in executions if e.latency > _HIGH_LATENCY_THRESHOLD]
        if not slow:
            return []
        avg_slow = round(sum(e.latency for e in slow) / len(slow), 4)
        return [
            Pattern(
                pattern_id="pattern-high-latency",
                kind="high_latency",
                description=(
                    f"{len(slow)} execution(s) exceeded latency threshold "
                    f"({_HIGH_LATENCY_THRESHOLD}s), avg={avg_slow}s"
                ),
                signal_value=avg_slow,
                occurrence_count=len(slow),
                confidence=round(min(0.9, 0.6 + len(slow) / 20.0), 4),
            )
        ]

    def _low_success_rate(self, executions: list[ExecutionRecord]) -> list[Pattern]:
        if not executions:
            return []
        avg_rate = round(sum(e.success_rate for e in executions) / len(executions), 4)
        if avg_rate >= _LOW_SUCCESS_RATE_THRESHOLD:
            return []
        return [
            Pattern(
                pattern_id="pattern-low-success-rate",
                kind="low_success_rate",
                description=f"Average success rate {avg_rate:.2%} is below threshold {_LOW_SUCCESS_RATE_THRESHOLD:.0%}",
                signal_value=avg_rate,
                occurrence_count=len(executions),
                confidence=round(min(0.9, 1.0 - avg_rate), 4),
            )
        ]


def _slug(text: str) -> str:
    """Convert an error string to a safe identifier fragment."""
    return "".join(c if c.isalnum() else "-" for c in text.lower())[:40].strip("-")
