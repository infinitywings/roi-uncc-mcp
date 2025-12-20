"""Shared attacker constraints loader/enforcer."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ..models.constraints import AttackerConstraints, AttackBudgetTracker


class ConstraintService:
    def __init__(self, constraints: AttackerConstraints):
        self.constraints = constraints
        self.budget = AttackBudgetTracker(constraints)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ConstraintService":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

        constraints = AttackerConstraints(
            observation_interval_sec=float(data.get("observation", {}).get("interval_sec", 5.0)),
            min_attack_cooldown_sec=float(data.get("action", {}).get("min_cooldown_sec", 30.0)),
            max_attacks_per_hour=int(data.get("action", {}).get("max_attacks_per_hour", 60)),
            min_attack_power_kw=float(data.get("power", {}).get("min_kw", 1500.0)),
            max_attack_power_kw=float(data.get("power", {}).get("max_kw", 3500.0)),
            valid_ev_ids=tuple(data.get("targets", {}).get("valid_ev_ids", ["EV1", "EV2", "EV3", "EV4", "EV5", "EV6"])),
            threshold_kw=float(data.get("grid", {}).get("threshold_kw", 4200.0)),
        )
        return cls(constraints)

    def reset_budget(self) -> None:
        self.budget = AttackBudgetTracker(self.constraints)

    def can_attack(self, simulation_time_sec: float) -> tuple[bool, str]:
        return self.budget.can_attack(simulation_time_sec)

    def record_attack(self, simulation_time_sec: float) -> None:
        self.budget.record_attack(simulation_time_sec)

    def to_dict(self) -> Dict[str, Any]:
        c = self.constraints
        return {
            "observation_interval_sec": c.observation_interval_sec,
            "min_attack_cooldown_sec": c.min_attack_cooldown_sec,
            "max_attacks_per_hour": c.max_attacks_per_hour,
            "min_attack_power_kw": c.min_attack_power_kw,
            "max_attack_power_kw": c.max_attack_power_kw,
            "valid_ev_ids": list(c.valid_ev_ids),
            "threshold_kw": c.threshold_kw,
        }

