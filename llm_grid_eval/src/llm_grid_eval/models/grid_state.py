"""Grid state data models - immutable snapshots of simulation state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict


@dataclass(frozen=True)
class Voltages:
    """Three-phase voltage measurements in per-unit."""

    VA_pu: float
    VB_pu: float
    VC_pu: float


@dataclass(frozen=True)
class EVStation:
    """State for a single EV charging station (best-effort / observed-by-attacker)."""

    ev_id: str
    real_kw: float
    reactive_kvar: float
    enabled: bool
    phase: str
    has_storage: bool
    max_power_kw: float = 4000.0


@dataclass(frozen=True)
class GridState:
    """Immutable snapshot of grid state at a point in time."""

    timestamp: datetime
    simulation_time_sec: float
    voltages: Voltages
    total_real_power_kw: float
    total_reactive_power_kvar: float
    frequency_hz: float
    ev_stations: Dict[str, EVStation]
    switches: Dict[str, str]
    threshold_kw: float = 4200.0

    @property
    def headroom_kw(self) -> float:
        return self.threshold_kw - self.total_real_power_kw

    @property
    def is_in_violation(self) -> bool:
        return self.total_real_power_kw > self.threshold_kw

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "simulation_time_sec": self.simulation_time_sec,
            "grid_state": {
                "voltages": {
                    "VA_pu": self.voltages.VA_pu,
                    "VB_pu": self.voltages.VB_pu,
                    "VC_pu": self.voltages.VC_pu,
                },
                "total_real_power_kw": self.total_real_power_kw,
                "total_reactive_power_kvar": self.total_reactive_power_kvar,
                "frequency_hz": self.frequency_hz,
                "threshold_kw": self.threshold_kw,
                "headroom_kw": self.headroom_kw,
                "in_violation": self.is_in_violation,
            },
            "ev_stations": {
                ev_id: {
                    "real_kw": ev.real_kw,
                    "reactive_kvar": ev.reactive_kvar,
                    "enabled": ev.enabled,
                    "phase": ev.phase,
                    "has_storage": ev.has_storage,
                    "max_power_kw": ev.max_power_kw,
                }
                for ev_id, ev in self.ev_stations.items()
            },
            "switches": dict(self.switches),
        }

