"""Observation primitives backed by the EV setpoint federate."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ObservationService:
    """Implements observation primitives defined in MCP_PRIMITIVES."""

    def __init__(self, federate, config: Dict[str, Any]):
        self._federate = federate
        self._topology_cfg = config.get("observation", {}).get("topology", {})
        self._vulnerability_cfg = config.get("observation", {}).get("vulnerabilities", {})
        self._protection_cfg = config.get("protection", {})
        self._observation_history: List[Dict[str, Any]] = []
        self._max_history_length = 100
        self._controller_action_history: List[Dict[str, Any]] = []
        self._attack_outcome_history: List[Dict[str, Any]] = []

    # --------------------------------------------------------------
    def get_grid_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self._federate.get_state_snapshot()
        voltages = self._normalize_voltages(snapshot.get("voltages", {}))
        powers = self._normalize_powers(snapshot.get("powers", {}))
        ev_setpoints = snapshot.get("ev_setpoints", {})
        switch_states = self._normalize_switch_states(snapshot.get("switch_states", {}))
        recent_commands = self._format_recent_commands(snapshot.get("recent_ev_commands", []))

        total_kw = sum(val["real_kw"] for val in powers.values())
        total_kvar = sum(val["imag_kvar"] for val in powers.values())

        voltage_mags = [val["magnitude"] for val in voltages.values() if "magnitude" in val]
        imbalance_pct = 0.0
        if voltage_mags:
            avg = sum(voltage_mags) / len(voltage_mags)
            if avg:
                imbalance_pct = max(abs(v - avg) / avg for v in voltage_mags) * 100.0

        sim_time = snapshot.get("simulation_time_sec", 0)

        self._observation_history.append(
            {
                "simulation_time_sec": sim_time,
                "total_real_power_kw": total_kw,
                "timestamp": snapshot.get("timestamp"),
            }
        )
        if len(self._observation_history) > self._max_history_length:
            self._observation_history = self._observation_history[-self._max_history_length:]

        controller_timing = self._infer_controller_timing(
            snapshot.get("recent_ev_commands", []), sim_time
        )
        load_patterns = self._analyze_load_patterns()
        attack_opportunity = self._calculate_attack_opportunity(
            total_kw, controller_timing, load_patterns
        )

        threshold_kw = self._protection_cfg.get("feeder_load_upper_kw", 4200)

        return {
            "timestamp": snapshot.get("timestamp"),
            "simulation_time_sec": sim_time,
            "grid_state": {
                "voltages": voltages,
                "powers": powers,
                "ev_setpoints_kw": {
                    ev: data.get("real_kw", 0.0) for ev, data in ev_setpoints.items()
                },
                "blue_team_switches": switch_states,
                "recent_ev_commands": recent_commands
            },
            "system_metrics": {
                "total_real_power_kw": total_kw,
                "total_reactive_power_kvar": total_kvar,
                "voltage_imbalance_pct": imbalance_pct,
                "threshold_kw": threshold_kw,
                "headroom_kw": threshold_kw - total_kw
            },
            "defender_timing": controller_timing,
            "load_patterns": load_patterns,
            "attack_opportunity": attack_opportunity,
            "observation_history_length": len(self._observation_history)
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
    def _infer_controller_timing(
        self, recent_commands: List[Dict[str, Any]], current_sim_time: float
    ) -> Dict[str, Any]:
        """Infer controller timing from recent commands."""
        if not recent_commands or len(recent_commands) < 2:
            return {
                "last_action_sim_time": None,
                "inferred_interval_sec": None,
                "next_expected_action_sim_time": None,
                "time_until_next_action_sec": None,
                "confidence": "low"
            }

        controller_timestamps: List[float] = []
        for cmd in recent_commands:
            ts = cmd.get("timestamp")
            if not ts:
                continue
            if cmd.get("real_kw", 0) <= 300:
                if isinstance(ts, str):
                    try:
                        controller_timestamps.append(
                            datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                        )
                    except Exception:
                        continue
                elif isinstance(ts, (int, float)):
                    controller_timestamps.append(float(ts))

        if len(controller_timestamps) < 2:
            return {
                "last_action_sim_time": controller_timestamps[0] if controller_timestamps else None,
                "inferred_interval_sec": 60.0,
                "next_expected_action_sim_time": None,
                "time_until_next_action_sec": None,
                "confidence": "low"
            }

        intervals: List[float] = []
        for i in range(len(controller_timestamps) - 1):
            t1 = controller_timestamps[i]
            t2 = controller_timestamps[i + 1]
            intervals.append(abs(t2 - t1))

        inferred_interval = sum(intervals) / len(intervals) if intervals else 60.0
        confidence = "high" if len(intervals) >= 3 else "medium"
        last_action_time = controller_timestamps[-1]
        next_expected = last_action_time + inferred_interval
        time_until_next = max(0, next_expected - current_sim_time)

        return {
            "last_action_sim_time": last_action_time,
            "inferred_interval_sec": inferred_interval,
            "next_expected_action_sim_time": next_expected,
            "time_until_next_action_sec": time_until_next,
            "confidence": confidence
        }

    # --------------------------------------------------------------
    def _analyze_load_patterns(self) -> Dict[str, Any]:
        """Analyze historical load to find peaks and trend."""
        if len(self._observation_history) < 5:
            return {
                "peak_hours_detected": [15, 16, 17],
                "current_trend": "unknown",
                "load_percentile": None,
                "attack_window_quality": "unknown",
                "current_hour": 0,
                "headroom_kw": None
            }

        load_data = []
        for obs in self._observation_history[-50:]:
            total_kw = obs.get("total_real_power_kw", 0)
            sim_time = obs.get("simulation_time_sec", 0)
            hour = int((sim_time / 3600) % 24)
            load_data.append({"hour": hour, "load_kw": total_kw, "sim_time": sim_time})

        hourly_loads: Dict[int, List[float]] = {}
        for d in load_data:
            hourly_loads.setdefault(d["hour"], []).append(d["load_kw"])
        hourly_avg = {h: sum(v) / len(v) for h, v in hourly_loads.items()}
        sorted_hours = sorted(hourly_avg.keys(), key=lambda h: hourly_avg[h], reverse=True)
        peak_hours = sorted_hours[:3] if len(sorted_hours) >= 3 else sorted_hours

        all_loads = [d["load_kw"] for d in load_data]
        current_load = load_data[-1]["load_kw"]
        loads_below = sum(1 for l in all_loads if l < current_load)
        load_percentile = (loads_below / len(all_loads)) * 100 if all_loads else 50

        recent_loads = [d["load_kw"] for d in load_data[-5:]]
        if len(recent_loads) >= 3:
            if recent_loads[-1] > recent_loads[0] * 1.05:
                trend = "increasing"
            elif recent_loads[-1] < recent_loads[0] * 0.95:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "unknown"

        threshold_kw = self._protection_cfg.get("feeder_load_upper_kw", 4200)
        headroom = threshold_kw - current_load
        current_hour = load_data[-1]["hour"]

        if current_hour in peak_hours and headroom < 1500:
            window_quality = "excellent"
        elif current_hour in peak_hours:
            window_quality = "good"
        elif headroom < 1000:
            window_quality = "moderate"
        else:
            window_quality = "poor"

        return {
            "peak_hours_detected": peak_hours,
            "current_trend": trend,
            "load_percentile": load_percentile,
            "current_hour": current_hour,
            "headroom_kw": headroom,
            "attack_window_quality": window_quality
        }

    # --------------------------------------------------------------
    def _calculate_attack_opportunity(
        self,
        current_load_kw: float,
        controller_timing: Dict[str, Any],
        load_patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine macro- and micro-timing to score attack opportunity."""
        threshold = self._protection_cfg.get("feeder_load_upper_kw", 4200)
        headroom = threshold - current_load_kw

        if headroom <= 0:
            macro_score = 100
        elif headroom < 500:
            macro_score = 90
        elif headroom < 1000:
            macro_score = 70
        elif headroom < 1500:
            macro_score = 50
        elif headroom < 2000:
            macro_score = 30
        else:
            macro_score = 10

        time_until_next = controller_timing.get("time_until_next_action_sec")
        interval = controller_timing.get("inferred_interval_sec") or 60
        if time_until_next is None:
            micro_score = 50
        elif interval > 0:
            cycle_position = time_until_next / interval
            micro_score = min(100, cycle_position * 100)
        else:
            micro_score = 50

        combined_score = (macro_score * 0.6) + (micro_score * 0.4)

        if combined_score >= 70 and macro_score >= 50:
            recommendation = "ATTACK_NOW"
            reasoning = "High load + good timing window"
        elif combined_score >= 50 and macro_score >= 40:
            recommendation = "ATTACK_POSSIBLE"
            reasoning = "Moderate conditions, attack may succeed"
        elif micro_score >= 80 and macro_score >= 30:
            recommendation = "WAIT_FOR_LOAD"
            reasoning = "Good timing but load too low"
        else:
            recommendation = "WAIT"
            reasoning = "Poor conditions, conserve attack budget"

        return {
            "macro_score": macro_score,
            "micro_score": micro_score,
            "combined_score": combined_score,
            "recommendation": recommendation,
            "reasoning": reasoning,
            "current_load_kw": current_load_kw,
            "threshold_kw": threshold,
            "headroom_kw": headroom,
            "attack_window_quality": load_patterns.get("attack_window_quality")
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

    @staticmethod
    def _normalize_switch_states(raw: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        normalized = {}
        for name, value in raw.items():
            label = name.replace("switch_", "")
            status = (value or "").strip().upper()
            normalized[label] = {
                "status": status,
                "is_closed": status in {"CLOSED", "1", "ON", "TRUE"}
            }
        return normalized

    @staticmethod
    def _format_recent_commands(history: Any) -> Any:
        formatted = []
        for entry in history or []:
            formatted.append({
                "timestamp": entry.get("timestamp"),
                "ev_id": entry.get("ev_id"),
                "real_kw": entry.get("real_kw"),
                "imag_kvar": entry.get("imag_kvar"),
                "interaction_id": (entry.get("metadata") or {}).get("interaction_id"),
                "sequence": (entry.get("metadata") or {}).get("sequence"),
                "step": (entry.get("metadata") or {}).get("step")
            })
        return formatted
