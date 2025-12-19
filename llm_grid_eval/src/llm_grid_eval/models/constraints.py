"""Attacker constraint models (shared for AI + Random)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class AttackerConstraints:
    """
    Constraints that apply equally to both AI and Random attackers.
    These ensure fair comparison - only decision logic differs.
    """

    # Observation constraints
    observation_interval_sec: float = 5.0

    # Action constraints
    min_attack_cooldown_sec: float = 30.0
    max_attacks_per_hour: int = 60

    # Power constraints
    min_attack_power_kw: float = 1500.0
    max_attack_power_kw: float = 3500.0

    # Valid targets
    valid_ev_ids: Tuple[str, ...] = ("EV1", "EV2", "EV3", "EV4", "EV5", "EV6")

    # Grid parameters
    threshold_kw: float = 4200.0

    def validate_attack(self, ev_id: str, power_kw: float) -> str | None:
        """Return an error message if invalid, None if valid."""
        if ev_id not in self.valid_ev_ids:
            return f"Invalid EV ID: {ev_id}"
        if not self.min_attack_power_kw <= power_kw <= self.max_attack_power_kw:
            return (
                f"Power {power_kw} kW outside range "
                f"[{self.min_attack_power_kw}, {self.max_attack_power_kw}]"
            )
        return None


@dataclass
class AttackBudgetTracker:
    """Tracks attack budget and cooldown in simulation time."""

    constraints: AttackerConstraints
    last_attack_time: float = -999.0  # simulation_time_sec of last attack
    attacks_this_hour: int = 0
    hour_start_time: float = 0.0

    def can_attack(self, current_time: float) -> tuple[bool, str]:
        # Cooldown
        time_since_last = current_time - self.last_attack_time
        if time_since_last < self.constraints.min_attack_cooldown_sec:
            remaining = self.constraints.min_attack_cooldown_sec - time_since_last
            return False, f"Cooldown: {remaining:.1f}s remaining"

        # Hourly budget (reset on hour boundary)
        if current_time - self.hour_start_time >= 3600:
            self.attacks_this_hour = 0
            self.hour_start_time = current_time

        if self.attacks_this_hour >= self.constraints.max_attacks_per_hour:
            return False, "Hourly budget exhausted"

        return True, "Attack allowed"

    def record_attack(self, current_time: float) -> None:
        self.last_attack_time = current_time
        self.attacks_this_hour += 1

