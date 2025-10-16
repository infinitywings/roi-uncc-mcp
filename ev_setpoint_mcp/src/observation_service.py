"""Observation primitives backed by the EV setpoint federate."""

from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ObservationService:
    """Implements observation primitives defined in MCP_PRIMITIVES."""

    def __init__(self, federate, config: Dict[str, Any]):
        self._federate = federate
        self._topology_cfg = config.get("observation", {}).get("topology", {})
        self._vulnerability_cfg = config.get("observation", {}).get("vulnerabilities", {})
        self._protection_cfg = config.get("protection", {})

    # --------------------------------------------------------------
    def get_grid_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self._federate.get_state_snapshot()
        voltages = self._normalize_voltages(snapshot.get("voltages", {}))
        powers = self._normalize_powers(snapshot.get("powers", {}))
        ev_setpoints = snapshot.get("ev_setpoints", {})

        total_kw = sum(val["real_kw"] for val in powers.values())
        total_kvar = sum(val["imag_kvar"] for val in powers.values())

        voltage_mags = [val["magnitude"] for val in voltages.values() if "magnitude" in val]
        imbalance_pct = 0.0
        if voltage_mags:
            avg = sum(voltage_mags) / len(voltage_mags)
            if avg:
                imbalance_pct = max(abs(v - avg) / avg for v in voltage_mags) * 100.0

        return {
            "timestamp": snapshot.get("timestamp"),
            "grid_state": {
                "voltages": voltages,
                "powers": powers,
                "ev_setpoints_kw": {
                    ev: data.get("real_kw", 0.0) for ev, data in ev_setpoints.items()
                },
            },
            "system_metrics": {
                "total_real_power_kw": total_kw,
                "total_reactive_power_kvar": total_kvar,
                "voltage_imbalance_pct": imbalance_pct
            }
        }

    # --------------------------------------------------------------
    def discover_topology(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "topology": self._topology_cfg,
            "vulnerabilities": self._vulnerability_cfg
        }

    # --------------------------------------------------------------
    def monitor_protection_systems(self, params: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self._federate.get_state_snapshot()
        voltages = self._normalize_voltages(snapshot.get("voltages", {}))
        powers = self._normalize_powers(snapshot.get("powers", {}))

        phase_nominal = self._protection_cfg.get("phase_nominal_volts", 2401.7771)
        undervoltage_pu = self._protection_cfg.get("undervoltage_pu", 0.95)
        overvoltage_pu = self._protection_cfg.get("overvoltage_pu", 1.05)
        feeder_upper_kw = self._protection_cfg.get("feeder_load_upper_kw", 4200.0)
        feeder_lower_kw = self._protection_cfg.get("feeder_load_lower_kw", 2600.0)

        protection_status = {
            "undervoltage_relays": {},
            "overvoltage_relays": {},
            "breakers": {}
        }

        for phase, data in voltages.items():
            magnitude = data.get("magnitude", phase_nominal)
            pu = magnitude / phase_nominal if phase_nominal else 0.0
            margin = pu - undervoltage_pu
            protection_status["undervoltage_relays"][phase] = {
                "armed": pu < 1.2,
                "pu_voltage": pu,
                "margin": margin
            }
            protection_status["overvoltage_relays"][phase] = {
                "armed": pu > 0.8,
                "pu_voltage": pu,
                "margin": overvoltage_pu - pu
            }

        total_kw = sum(val["real_kw"] for val in powers.values())
        breaker_status = "closed" if total_kw <= feeder_upper_kw else "open"
        protection_status["breakers"]["feeder_head"] = {
            "status": breaker_status,
            "can_trip": True,
            "last_operation": None,
            "setpoints_kw": {
                "upper": feeder_upper_kw,
                "lower": feeder_lower_kw
            }
        }

        return {"protection_status": protection_status}

    # --------------------------------------------------------------
    def analyze_power_flow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self._federate.get_state_snapshot()
        powers = self._normalize_powers(snapshot.get("powers", {}))
        total_kw = sum(val["real_kw"] for val in powers.values())
        total_kvar = sum(val["imag_kvar"] for val in powers.values())
        feeder_limit_kw = self._protection_cfg.get("feeder_load_upper_kw", 4200.0)

        constraints = {
            "feeder_limit_kw": feeder_limit_kw,
            "current_total_kw": total_kw,
            "headroom_kw": feeder_limit_kw - total_kw
        }

        power_flow = {
            "convergence": True,
            "iterations": 1,
            "mismatch": 0.0,
            "aggregate_power_kw": total_kw,
            "aggregate_reactive_kvar": total_kvar
        }

        return {
            "power_flow": power_flow,
            "constraints": constraints,
            "sensitivities": {}
        }

    # --------------------------------------------------------------
    @staticmethod
    def _normalize_voltages(raw: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Normalize voltage data from transmission (GridPACK) measurements.

        Subscription names: transmission_voltage_A, transmission_voltage_B, transmission_voltage_C
        These come from gridpack/Va, gridpack/Vb, gridpack/Vc publications.
        """
        formatted = {}
        for name, data in raw.items():
            # Map transmission voltages to readable labels
            if "transmission_voltage" in name:
                phase = name.replace("transmission_voltage_", "")
                label = f"Node650_phase{phase}"  # At tie point to distribution
            else:
                label = name

            if isinstance(data, dict):
                formatted[label] = {
                    "magnitude": data.get("magnitude"),
                    "angle_deg": data.get("angle"),
                    "unit": data.get("unit", "V")
                }
        return formatted

    @staticmethod
    def _normalize_powers(raw: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Normalize power data from feeder (GridLAB-D) measurements.

        Subscription names: feeder_power_A, feeder_power_B, feeder_power_C
        These come from gld_hlc_conn/Sa, gld_hlc_conn/Sb, gld_hlc_conn/Sc publications.
        Measured at Node650 (swing bus / tie point to transmission).
        """
        formatted = {}
        for name, data in raw.items():
            # Map feeder powers to readable labels
            if "feeder_power" in name:
                phase = name.replace("feeder_power_", "")
                label = f"Node650_phase{phase}"  # At swing bus
            else:
                label = name

            if isinstance(data, dict):
                formatted[label] = {
                    "real_kw": data.get("real_kw", 0.0),
                    "imag_kvar": data.get("imag_kvar", 0.0),
                    "magnitude_kva": data.get("magnitude_kva", 0.0),
                    "power_factor": data.get("power_factor", 0.0),
                    "unit": data.get("unit", "kVA")
                }
        return formatted

