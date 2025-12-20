"""
Rate-limited power ramping for EV stations.
Prevents GridLAB-D solver crashes by ensuring gradual power changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class EVRampState:
    """Tracks current and target power for one EV station."""
    current_kw: float = 0.0
    target_kw: float = 0.0

    def needs_update(self) -> bool:
        return abs(self.current_kw - self.target_kw) > 0.1


class RampController:
    """
    Controls gradual ramping of EV power setpoints.

    Ramp rate: 100 kW/s (configurable)
    At 5s update interval: max 500 kW change per step
    Time to ramp 2500 kW: ~25 seconds

    Usage:
        controller = RampController(ramp_rate_kw_per_sec=100)
        controller.set_target("EV3", 2500.0)

        # Every 5 seconds in HELICS loop:
        updates = controller.update(dt_sec=5.0)
        for ev_id, power_kw in updates.items():
            publish_to_helics(ev_id, power_kw)
    """

    DEFAULT_INITIAL_POWERS = {
        "EV1": 220.0, "EV2": 200.0, "EV3": 200.0,
        "EV4": 220.0, "EV5": 200.0, "EV6": 200.0,
    }

    def __init__(
        self,
        ramp_rate_kw_per_sec: float = 100.0,
        update_interval_sec: float = 5.0,
        initial_powers: Optional[Dict[str, float]] = None,
    ):
        self._ramp_rate = ramp_rate_kw_per_sec
        self._update_interval = update_interval_sec
        self._max_change_per_step = ramp_rate_kw_per_sec * update_interval_sec

        powers = initial_powers or self.DEFAULT_INITIAL_POWERS
        self._ev_states: Dict[str, EVRampState] = {
            ev_id: EVRampState(current_kw=power, target_kw=power)
            for ev_id, power in powers.items()
        }

    def set_target(self, ev_id: str, target_kw: float) -> None:
        """Set target power (ramping starts on next update)."""
        if ev_id not in self._ev_states:
            # Create new state for unknown EV
            self._ev_states[ev_id] = EVRampState(
                current_kw=0.0,
                target_kw=target_kw
            )
            logger.info("New EV %s, target set to %.1f kW", ev_id, target_kw)
        else:
            old_target = self._ev_states[ev_id].target_kw
            self._ev_states[ev_id].target_kw = target_kw
            if abs(old_target - target_kw) > 0.1:
                logger.info(
                    "EV %s target changed: %.1f -> %.1f kW",
                    ev_id, old_target, target_kw
                )

    def get_current(self, ev_id: str) -> float:
        """Get current actual power."""
        if ev_id not in self._ev_states:
            return 0.0
        return self._ev_states[ev_id].current_kw

    def get_target(self, ev_id: str) -> float:
        """Get target power."""
        if ev_id not in self._ev_states:
            return 0.0
        return self._ev_states[ev_id].target_kw

    def update(self, dt_sec: Optional[float] = None) -> Dict[str, float]:
        """
        Advance ramping by dt seconds. Returns {ev_id: new_power} for changed EVs.

        Logic:
        - max_change = ramp_rate * dt
        - For each EV where current != target:
            - Move current toward target by at most max_change
            - Add to updates dict
        """
        if dt_sec is None:
            dt_sec = self._update_interval

        max_change = self._ramp_rate * dt_sec
        updates: Dict[str, float] = {}

        for ev_id, state in self._ev_states.items():
            if not state.needs_update():
                continue

            diff = state.target_kw - state.current_kw
            if abs(diff) <= max_change:
                # Can reach target in this step
                state.current_kw = state.target_kw
                logger.info(
                    "EV %s reached target: %.1f kW",
                    ev_id, state.current_kw
                )
            else:
                # Move toward target by max_change
                if diff > 0:
                    state.current_kw += max_change
                else:
                    state.current_kw -= max_change
                logger.debug(
                    "EV %s ramping: %.1f -> %.1f kW (target: %.1f)",
                    ev_id, state.current_kw - (max_change if diff > 0 else -max_change),
                    state.current_kw, state.target_kw
                )

            updates[ev_id] = state.current_kw

        return updates

    def get_all_current_powers(self) -> Dict[str, float]:
        """Get current power for all EVs."""
        return {ev_id: state.current_kw for ev_id, state in self._ev_states.items()}

    def get_ramp_status(self) -> Dict[str, dict]:
        """Get detailed status: {ev_id: {current_kw, target_kw, ramping, remaining_kw}}"""
        result = {}
        for ev_id, state in self._ev_states.items():
            remaining = abs(state.target_kw - state.current_kw)
            result[ev_id] = {
                "current_kw": state.current_kw,
                "target_kw": state.target_kw,
                "ramping": remaining > 0.1,
                "remaining_kw": remaining,
                "estimated_time_sec": remaining / self._ramp_rate if remaining > 0.1 else 0.0,
            }
        return result

    def is_any_ramping(self) -> bool:
        """Check if any EV is currently ramping."""
        return any(state.needs_update() for state in self._ev_states.values())

    def reset(self, initial_powers: Optional[Dict[str, float]] = None) -> None:
        """Reset all EVs to initial state."""
        powers = initial_powers or self.DEFAULT_INITIAL_POWERS
        self._ev_states = {
            ev_id: EVRampState(current_kw=power, target_kw=power)
            for ev_id, power in powers.items()
        }
        logger.info("RampController reset to initial powers")
