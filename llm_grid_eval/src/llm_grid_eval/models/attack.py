"""Attack request/response data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AttackRequest:
    ev_id: str
    real_kw: float
    reactive_kvar: float = 0.0


@dataclass(frozen=True)
class AttackResult:
    """Result of an attempted attack command."""

    timestamp: str
    simulation_time_sec: float
    ev_id: str
    requested_real_kw: float
    requested_reactive_kvar: float
    command_payload: str

    success: bool
    blocked_reason: Optional[str] = None
    error: Optional[str] = None

    # State snapshots (best-effort)
    pre_attack_total_real_power_kw: float = 0.0
    pre_attack_in_violation: bool = False
    post_attack_total_real_power_kw: Optional[float] = None
    post_attack_in_violation: Optional[bool] = None

    # Attribution: true if this attack is credited with starting a violation
    caused_violation: bool = False

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "simulation_time_sec": self.simulation_time_sec,
            "action": {
                "ev_id": self.ev_id,
                "real_kw": self.requested_real_kw,
                "reactive_kvar": self.requested_reactive_kvar,
                "payload": self.command_payload,
            },
            "success": self.success,
            "blocked_reason": self.blocked_reason,
            "error": self.error,
            "pre_attack_state": {
                "total_real_power_kw": self.pre_attack_total_real_power_kw,
                "in_violation": self.pre_attack_in_violation,
            },
            "post_attack_state": {
                "total_real_power_kw": self.post_attack_total_real_power_kw,
                "in_violation": self.post_attack_in_violation,
                "caused_violation": self.caused_violation,
            },
        }

