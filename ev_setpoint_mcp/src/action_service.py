"""Single action primitive for EV capacity management (Attack Mode)."""

from __future__ import annotations

import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ActionService:
    """Expose the `set_ev_capacity` primitive for adversarial EV setpoint injection.

    This service operates in ATTACK MODE - it allows AI adversaries to inject
    malicious EV charging setpoints that compete with the legitimate controller.

    Attack strategies enabled:
    - Overload attacks: Inject excessive load (up to 4 MW per EV)
    - Reverse power injection: Negative setpoints to disrupt power flow
    - Phase imbalance: Target specific phases to cause voltage issues
    - Timing attacks: Coordinate with peak demand periods
    """

    def __init__(self, federate, config: Dict[str, Any]):
        self._federate = federate
        self._constraints = config.get("setpoint_constraints", {})
        self._attack_mode = self._constraints.get("attack_mode", False)
        self._default_max = self._constraints.get("default_max_kw", 200.0)
        self._default_min = self._constraints.get("default_min_kw", 0.0)

        logger.info(
            "ActionService initialized in %s mode (max=%s kW, min=%s kW)",
            "ATTACK" if self._attack_mode else "NORMAL",
            self._default_max,
            self._default_min
        )

    def set_ev_capacity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params:
            raise ValueError("Missing params for set_ev_capacity")

        ev_id = params.get("ev_id")
        if not ev_id:
            raise ValueError("`ev_id` is required")

        real_kw = float(params.get("real_power_kw", 0.0))
        reactive_kvar = float(params.get("reactive_power_kvar", 0.0))

        limits = self._constraints.get("ev_limits", {}).get(ev_id, {})

        # In attack mode, use attack_max_kw; otherwise use normal_max_kw
        if self._attack_mode:
            min_kw = float(limits.get("min_kw", self._default_min))
            max_kw = float(limits.get("attack_max_kw", self._default_max))
            normal_max_kw = float(limits.get("normal_max_kw", 200.0))
        else:
            min_kw = 0.0
            max_kw = float(limits.get("normal_max_kw", self._default_max))
            normal_max_kw = max_kw

        # Validate within attack limits (but warn if exceeds normal operation)
        if real_kw < min_kw or real_kw > max_kw:
            raise ValueError(
                f"Requested real_power_kw {real_kw} is outside attack bounds "
                f"[{min_kw}, {max_kw}] for {ev_id}"
            )

        # Log attack classification
        attack_type = self._classify_attack(ev_id, real_kw, reactive_kvar, limits, normal_max_kw)
        logger.warning(
            "ATTACK INJECTION: %s | EV=%s | P=%s kW | Q=%s kvar | Type=%s",
            "MALICIOUS" if attack_type != "normal" else "BENIGN",
            ev_id,
            real_kw,
            reactive_kvar,
            attack_type
        )

        real_va = real_kw * 1000.0
        imag_va = reactive_kvar * 1000.0

        start_ts = time.time()
        logger.debug(
            "set_ev_capacity dispatch started | ev_id=%s | real_kw=%.3f | reactive_kvar=%.3f",
            ev_id,
            real_kw,
            reactive_kvar
        )
        result = self._federate.set_ev_capacity(ev_id, real_va=real_va, imag_va=imag_va)
        latency = time.time() - start_ts
        logger.debug(
            "set_ev_capacity dispatch finished | ev_id=%s | latency=%.3fs",
            ev_id,
            latency
        )
        result.update({
            "requested_kw": real_kw,
            "requested_kvar": reactive_kvar,
            "duration_s": params.get("duration_s"),
            "attack_type": attack_type,
            "attack_mode": self._attack_mode,
            "phase": limits.get("phases", "unknown"),
            "has_storage": limits.get("has_storage", False),
            "handler_latency_sec": latency
        })
        return result

    def _classify_attack(
        self,
        ev_id: str,
        real_kw: float,
        reactive_kvar: float,
        limits: Dict[str, Any],
        normal_max_kw: float
    ) -> str:
        """Classify the attack type based on setpoint characteristics."""

        if real_kw < 0:
            return "reverse_power_injection"

        if real_kw > normal_max_kw * 1.5:
            return "overload_attack"

        if abs(reactive_kvar) > normal_max_kw * 0.5:
            return "reactive_power_attack"

        if real_kw > normal_max_kw * 1.1:
            return "mild_overload"

        return "normal"
