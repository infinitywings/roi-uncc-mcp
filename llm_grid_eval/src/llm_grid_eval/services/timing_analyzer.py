"""Timing intelligence computation - core of the micro/macro advantage."""

from __future__ import annotations

from typing import List, Optional

from ..models.grid_state import GridState
from ..models.timing import MacroAssessment, MicroAssessment, CombinedAssessment, TimingAssessment

DEFAULT_PEAK_HOURS = [15, 16, 17, 18, 19, 20]


class TimingAnalyzer:
    """Computes two-level timing intelligence (macro + micro)."""

    def __init__(
        self,
        threshold_kw: float = 4200.0,
        controller_interval_sec: float = 60.0,
        macro_weight: float = 0.6,
        micro_weight: float = 0.4,
    ):
        self.threshold_kw = float(threshold_kw)
        self.controller_interval_sec = float(controller_interval_sec)
        self.macro_weight = float(macro_weight)
        self.micro_weight = float(micro_weight)

    def analyze(
        self,
        current_state: GridState,
        history: Optional[List[GridState]] = None,
        last_controller_action_time: Optional[float] = None,
    ) -> TimingAssessment:
        macro = self._compute_macro(current_state, history)
        micro = self._compute_micro(current_state, last_controller_action_time)
        combined = self._compute_combined(macro, micro)
        return TimingAssessment(
            timestamp=current_state.timestamp.isoformat(),
            simulation_time_sec=current_state.simulation_time_sec,
            macro=macro,
            micro=micro,
            combined=combined,
        )

    def _compute_macro(
        self,
        current: GridState,
        history: Optional[List[GridState]],
    ) -> MacroAssessment:
        headroom = self.threshold_kw - current.total_real_power_kw
        current_hour = current.timestamp.hour

        if headroom <= 0:
            base_score = 100
            reasoning = "Already in violation - maximum attack potential"
        elif headroom < 500:
            base_score = 90
            reasoning = f"Critical: Only {headroom:.0f} kW headroom"
        elif headroom < 1000:
            base_score = 75
            reasoning = f"Favorable: {headroom:.0f} kW headroom"
        elif headroom < 1500:
            base_score = 55
            reasoning = f"Moderate: {headroom:.0f} kW headroom"
        elif headroom < 2000:
            base_score = 35
            reasoning = f"Limited: {headroom:.0f} kW headroom"
        else:
            base_score = 15
            reasoning = f"Poor: {headroom:.0f} kW headroom"

        peak_hours = self._detect_peak_hours(history) if history else DEFAULT_PEAK_HOURS
        is_peak = current_hour in peak_hours
        if is_peak:
            score = min(100, base_score + 15)
            reasoning += " [PEAK HOUR +15]"
        else:
            score = base_score

        return MacroAssessment(
            score=int(score),
            headroom_kw=headroom,
            is_peak_hour=is_peak,
            current_hour=current_hour,
            attack_feasible=(headroom < 2500),
            reasoning=reasoning,
        )

    def _compute_micro(
        self,
        current: GridState,
        last_controller_time: Optional[float],
    ) -> MicroAssessment:
        sim_time = float(current.simulation_time_sec)
        interval = float(self.controller_interval_sec)

        if interval <= 0:
            return MicroAssessment(
                score=50,
                cycle_position=0.5,
                time_since_controller_sec=0.0,
                time_until_next_sec=0.0,
                controller_interval_sec=interval,
                confidence="low",
                reasoning="Invalid controller interval - micro timing unavailable",
            )

        if last_controller_time is None:
            return MicroAssessment(
                score=50,
                cycle_position=0.5,
                time_since_controller_sec=interval / 2,
                time_until_next_sec=interval / 2,
                controller_interval_sec=interval,
                confidence="low",
                reasoning="No controller timing data - assuming mid-cycle",
            )

        time_since = sim_time - float(last_controller_time)
        cycle_position = (time_since % interval) / interval
        time_until_next = interval - (time_since % interval)

        score = int(min(100, (1.0 - cycle_position) * 100))
        if cycle_position < 0.2:
            reasoning = f"Excellent: Controller just acted, {time_until_next:.0f}s window"
            confidence = "high"
        elif cycle_position < 0.4:
            reasoning = f"Good: {time_until_next:.0f}s until controller"
            confidence = "high"
        elif cycle_position < 0.6:
            reasoning = f"Moderate: {time_until_next:.0f}s until controller"
            confidence = "medium"
        elif cycle_position < 0.8:
            reasoning = f"Limited: Only {time_until_next:.0f}s until controller"
            confidence = "high"
        else:
            reasoning = f"Poor: Controller imminent in {time_until_next:.0f}s"
            confidence = "high"

        return MicroAssessment(
            score=score,
            cycle_position=float(cycle_position),
            time_since_controller_sec=float(time_since),
            time_until_next_sec=float(time_until_next),
            controller_interval_sec=interval,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _compute_combined(
        self,
        macro: MacroAssessment,
        micro: MicroAssessment,
    ) -> CombinedAssessment:
        score = int(macro.score * self.macro_weight + micro.score * self.micro_weight)

        if macro.attack_feasible and macro.score >= 50 and micro.score >= 70:
            recommendation = "ATTACK_NOW"
            reasoning = "High load + excellent timing window"
        elif macro.attack_feasible and score >= 50:
            recommendation = "ATTACK_POSSIBLE"
            reasoning = "Conditions acceptable for attack"
        elif micro.score >= 70 and macro.score < 50:
            recommendation = "WAIT_FOR_LOAD"
            reasoning = "Good timing but load too low - wait for higher demand"
        else:
            recommendation = "WAIT"
            reasoning = "Unfavorable conditions"

        return CombinedAssessment(score=score, recommendation=recommendation, reasoning=reasoning)

    def _detect_peak_hours(self, history: List[GridState]) -> List[int]:
        if not history or len(history) < 20:
            return DEFAULT_PEAK_HOURS

        hourly_loads: dict[int, list[float]] = {}
        for state in history:
            hour = state.timestamp.hour
            hourly_loads.setdefault(hour, []).append(state.total_real_power_kw)

        hourly_avg = {h: sum(loads) / len(loads) for h, loads in hourly_loads.items()}
        sorted_hours = sorted(hourly_avg.keys(), key=lambda h: hourly_avg[h], reverse=True)
        return sorted_hours[:6]

