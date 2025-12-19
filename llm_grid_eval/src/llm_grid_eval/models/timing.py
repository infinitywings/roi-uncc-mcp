"""Timing intelligence data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MacroAssessment:
    """Macro-timing: grid load conditions."""

    score: int  # 0-100
    headroom_kw: float
    is_peak_hour: bool
    current_hour: int
    attack_feasible: bool
    reasoning: str


@dataclass(frozen=True)
class MicroAssessment:
    """Micro-timing: controller cycle position."""

    score: int  # 0-100
    cycle_position: float  # 0.0 = just after controller, 1.0 = just before
    time_since_controller_sec: float
    time_until_next_sec: float
    controller_interval_sec: float
    confidence: Literal["high", "medium", "low"]
    reasoning: str


@dataclass(frozen=True)
class CombinedAssessment:
    """Combined recommendation."""

    score: int
    recommendation: Literal["ATTACK_NOW", "ATTACK_POSSIBLE", "WAIT_FOR_LOAD", "WAIT"]
    reasoning: str


@dataclass(frozen=True)
class TimingAssessment:
    """Complete timing intelligence."""

    timestamp: str
    simulation_time_sec: float
    macro: MacroAssessment
    micro: MicroAssessment
    combined: CombinedAssessment

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "simulation_time_sec": self.simulation_time_sec,
            "macro_timing": {
                "score": self.macro.score,
                "headroom_kw": self.macro.headroom_kw,
                "is_peak_hour": self.macro.is_peak_hour,
                "current_hour": self.macro.current_hour,
                "attack_feasible": self.macro.attack_feasible,
                "reasoning": self.macro.reasoning,
            },
            "micro_timing": {
                "score": self.micro.score,
                "cycle_position": self.micro.cycle_position,
                "time_since_controller_sec": self.micro.time_since_controller_sec,
                "time_until_next_sec": self.micro.time_until_next_sec,
                "controller_interval_sec": self.micro.controller_interval_sec,
                "confidence": self.micro.confidence,
                "reasoning": self.micro.reasoning,
            },
            "combined": {
                "score": self.combined.score,
                "recommendation": self.combined.recommendation,
                "reasoning": self.combined.reasoning,
            },
        }

