from dataclasses import dataclass


@dataclass(frozen=True)
class SignalRecord:
    signal_type: str
    signal_value: str


@dataclass(frozen=True)
class ImprovementAction:
    action_type: str
    source_signal: str


@dataclass(frozen=True)
class ImprovementResult:
    action_type: str
    status: str
