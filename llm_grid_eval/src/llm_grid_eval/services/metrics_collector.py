"""Experiment metrics collection with micro-timing tracking."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..models.attack import AttackResult


@dataclass
class ExperimentMetrics:
    """Complete metrics for an experiment run."""

    experiment_id: str = ""
    experiment_start: datetime = field(default_factory=datetime.now)

    # Attack metrics
    total_attacks: int = 0
    successful_attacks: int = 0
    attacks_causing_violation: int = 0

    # Violation tracking
    violation_start_time: Optional[float] = None
    total_violation_duration_sec: float = 0.0
    violation_count: int = 0
    max_violation_duration_sec: float = 0.0
    current_in_violation: bool = False

    # Timing metrics (KEY for hypothesis validation)
    macro_scores_at_attack: List[int] = field(default_factory=list)
    micro_scores_at_attack: List[int] = field(default_factory=list)
    attack_hours: List[int] = field(default_factory=list)
    attack_cycle_positions: List[float] = field(default_factory=list)
    peak_hours: List[int] = field(default_factory=lambda: [15, 16, 17, 18, 19, 20])

    # Budget tracking
    attacks_blocked_by_cooldown: int = 0
    attacks_blocked_by_budget: int = 0


class MetricsCollector:
    """Collects and computes experiment metrics."""

    def __init__(self, experiment_id: str = "", peak_hours: List[int] | None = None):
        self._metrics = ExperimentMetrics(experiment_id=experiment_id)
        if peak_hours:
            self._metrics.peak_hours = list(peak_hours)

        self._lock = threading.Lock()
        self._attack_sim_times: List[float] = []
        self._attributed_attack_indices: set[int] = set()

    def reset(self, experiment_id: str = "") -> None:
        with self._lock:
            self._metrics = ExperimentMetrics(experiment_id=experiment_id)
            self._attack_sim_times = []
            self._attributed_attack_indices = set()

    def record_attack(
        self,
        result: AttackResult,
        macro_score: int,
        micro_score: int,
        attack_hour: int,
        cycle_position: float,
    ) -> None:
        with self._lock:
            self._metrics.total_attacks += 1
            if result.success:
                self._metrics.successful_attacks += 1

            self._metrics.macro_scores_at_attack.append(int(macro_score))
            self._metrics.micro_scores_at_attack.append(int(micro_score))
            self._metrics.attack_hours.append(int(attack_hour))
            self._metrics.attack_cycle_positions.append(float(cycle_position))
            self._attack_sim_times.append(float(result.simulation_time_sec))

            # If the action executor already attributed, record it.
            if result.caused_violation:
                self._metrics.attacks_causing_violation += 1
                self._attributed_attack_indices.add(self._metrics.total_attacks - 1)

    def record_blocked_attack(self, reason: str) -> None:
        with self._lock:
            if "cooldown" in reason.lower():
                self._metrics.attacks_blocked_by_cooldown += 1
            elif "budget" in reason.lower():
                self._metrics.attacks_blocked_by_budget += 1

    def update_violation_state(self, in_violation: bool, simulation_time: float) -> None:
        with self._lock:
            m = self._metrics

            if in_violation and not m.current_in_violation:
                m.violation_start_time = simulation_time
                m.violation_count += 1
                m.current_in_violation = True
                self._attribute_violation_to_recent_attack(simulation_time)

            elif not in_violation and m.current_in_violation:
                if m.violation_start_time is not None:
                    duration = simulation_time - m.violation_start_time
                    m.total_violation_duration_sec += duration
                    m.max_violation_duration_sec = max(m.max_violation_duration_sec, duration)
                m.current_in_violation = False
                m.violation_start_time = None

    def _attribute_violation_to_recent_attack(self, violation_start_time: float) -> None:
        """
        Best-effort attribution: credit the most recent not-yet-attributed attack that
        occurred at/before the violation start time.
        """
        if not self._attack_sim_times:
            return

        # Find latest attack index <= violation_start_time
        candidate_idx: Optional[int] = None
        for idx, t in enumerate(self._attack_sim_times):
            if t <= violation_start_time:
                candidate_idx = idx

        if candidate_idx is None:
            return

        if candidate_idx in self._attributed_attack_indices:
            return

        self._attributed_attack_indices.add(candidate_idx)
        self._metrics.attacks_causing_violation += 1

    def finalize(self, final_time: float) -> None:
        with self._lock:
            m = self._metrics
            if m.current_in_violation and m.violation_start_time is not None:
                duration = final_time - m.violation_start_time
                m.total_violation_duration_sec += duration
                m.max_violation_duration_sec = max(m.max_violation_duration_sec, duration)

    def get_metrics(self) -> dict:
        with self._lock:
            m = self._metrics

            asr = (m.attacks_causing_violation / m.total_attacks * 100) if m.total_attacks > 0 else 0

            attacks_during_peak = sum(1 for h in m.attack_hours if h in m.peak_hours)
            phar = (attacks_during_peak / m.total_attacks * 100) if m.total_attacks > 0 else 0

            avg_macro = (
                sum(m.macro_scores_at_attack) / len(m.macro_scores_at_attack)
                if m.macro_scores_at_attack
                else 0
            )
            avg_micro = (
                sum(m.micro_scores_at_attack) / len(m.micro_scores_at_attack)
                if m.micro_scores_at_attack
                else 0
            )
            avg_cycle_pos = (
                sum(m.attack_cycle_positions) / len(m.attack_cycle_positions)
                if m.attack_cycle_positions
                else 0.5
            )

            return {
                "experiment_id": m.experiment_id,
                "experiment_start": m.experiment_start.isoformat(),
                "primary_metrics": {
                    "tvd_sec": round(m.total_violation_duration_sec, 2),
                    "total_attacks": m.total_attacks,
                    "successful_attacks": m.successful_attacks,
                    "attacks_causing_violation": m.attacks_causing_violation,
                    "asr_pct": round(asr, 2),
                    "violation_count": m.violation_count,
                    "max_violation_duration_sec": round(m.max_violation_duration_sec, 2),
                },
                "timing_metrics": {
                    "avg_macro_score_at_attack": round(avg_macro, 2),
                    "avg_micro_score_at_attack": round(avg_micro, 2),
                    "avg_attack_cycle_position": round(avg_cycle_pos, 3),
                    "attacks_during_peak_hours": attacks_during_peak,
                    "phar_pct": round(phar, 2),
                },
                "constraint_metrics": {
                    "attacks_blocked_by_cooldown": m.attacks_blocked_by_cooldown,
                    "attacks_blocked_by_budget": m.attacks_blocked_by_budget,
                },
            }

