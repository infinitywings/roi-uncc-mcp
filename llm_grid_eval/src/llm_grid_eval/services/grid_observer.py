"""Grid observation service - converts HELICS measurements to GridState snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Tuple

from ..helics_interface.federate import GridFederate
from ..models.grid_state import EVStation, GridState, Voltages


EV_META: Dict[str, Dict[str, object]] = {
    "EV1": {"phase": "CN", "has_storage": True, "max_power_kw": 4000.0},
    "EV2": {"phase": "BN", "has_storage": False, "max_power_kw": 4000.0},
    "EV3": {"phase": "AN", "has_storage": False, "max_power_kw": 4000.0},
    "EV4": {"phase": "CN", "has_storage": True, "max_power_kw": 4000.0},
    "EV5": {"phase": "BN", "has_storage": False, "max_power_kw": 4000.0},
    "EV6": {"phase": "AN", "has_storage": False, "max_power_kw": 4000.0},
}


class GridObserver:
    def __init__(
        self,
        federate: GridFederate,
        *,
        threshold_kw: float,
        nominal_voltage_v: float,
        simulation_start_iso: str,
    ):
        self._federate = federate
        self._threshold_kw = float(threshold_kw)
        self._nominal_voltage_v = float(nominal_voltage_v)
        self._sim_start = datetime.fromisoformat(simulation_start_iso)
        self._last_ev_commands: Dict[str, Tuple[float, float]] = {}

    def set_last_ev_command(self, ev_id: str, real_kw: float, reactive_kvar: float = 0.0) -> None:
        self._last_ev_commands[ev_id] = (float(real_kw), float(reactive_kvar))

    def observe(self, *, step: bool = True) -> GridState:
        if step:
            self._federate.step()
        raw = self._federate.read()

        sim_time = float(raw.get("simulation_time_sec", 0.0))
        timestamp = self._sim_start + timedelta(seconds=sim_time)

        powers = raw.get("powers", {}) or {}
        total_real_kw = sum(float(p.real) for p in powers.values()) / 1000.0
        total_reactive_kvar = sum(float(p.imag) for p in powers.values()) / 1000.0

        volts = raw.get("voltages", {}) or {}
        va = volts.get("Va", 0 + 0j)
        vb = volts.get("Vb", 0 + 0j)
        vc = volts.get("Vc", 0 + 0j)
        nominal = self._nominal_voltage_v or 1.0
        voltage_state = Voltages(
            VA_pu=(abs(va) / nominal) if nominal else 0.0,
            VB_pu=(abs(vb) / nominal) if nominal else 0.0,
            VC_pu=(abs(vc) / nominal) if nominal else 0.0,
        )

        evs: Dict[str, EVStation] = {}
        for ev_id, meta in EV_META.items():
            last = self._last_ev_commands.get(ev_id, (0.0, 0.0))
            real_kw, reactive_kvar = last
            evs[ev_id] = EVStation(
                ev_id=ev_id,
                real_kw=real_kw,
                reactive_kvar=reactive_kvar,
                enabled=real_kw > 0,
                phase=str(meta["phase"]),
                has_storage=bool(meta["has_storage"]),
                max_power_kw=float(meta["max_power_kw"]),
            )

        switches_raw = raw.get("switches", {}) or {}
        switches = {k: str(v) for k, v in switches_raw.items()}

        return GridState(
            timestamp=timestamp,
            simulation_time_sec=sim_time,
            voltages=voltage_state,
            total_real_power_kw=total_real_kw,
            total_reactive_power_kvar=total_reactive_kvar,
            frequency_hz=60.0,
            ev_stations=evs,
            switches=switches,
            threshold_kw=self._threshold_kw,
        )

