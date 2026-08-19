"""Attack action execution service with rate-limited ramping."""

from __future__ import annotations

import logging
from typing import Dict, Optional

from ..helics_interface.federate import GridFederate
from ..models.attack import AttackRequest, AttackResult
from ..models.grid_state import GridState
from ..services.attack_constraints import ConstraintService
from ..services.grid_observer import GridObserver
from ..services.ramp_controller import RampController

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Executes attack commands with rate-limited power ramping.

    Attacks set a TARGET power level, which is gradually ramped
    to prevent GridLAB-D solver crashes from sudden step changes.

    The update() method MUST be called every HELICS timestep (5s)
    to advance the ramping and publish new setpoints.
    """

    def __init__(
        self,
        federate: GridFederate,
        observer: GridObserver,
        constraints: ConstraintService,
        ramp_rate_kw_per_sec: float = 100.0,
        update_interval_sec: float = 5.0,
    ):
        self._federate = federate
        self._observer = observer
        self._constraints = constraints

        # Initialize ramp controller for gradual power changes
        self._ramp_controller = RampController(
            ramp_rate_kw_per_sec=ramp_rate_kw_per_sec,
            update_interval_sec=update_interval_sec,
        )
        self._ramp_rate = ramp_rate_kw_per_sec

    def execute(self, request: AttackRequest, *, pre_state: GridState | None = None) -> AttackResult:
        """
        Execute attack by setting TARGET power.
        Actual power ramps toward target in subsequent update() calls.
        """
        # Pre-attack snapshot (no time advancement)
        pre_state = pre_state or self._observer.observe(step=False)

        # Validate request against shared constraints
        validation_error = self._constraints.constraints.validate_attack(request.ev_id, request.real_kw)
        if validation_error:
            return AttackResult(
                timestamp=pre_state.timestamp.isoformat(),
                simulation_time_sec=pre_state.simulation_time_sec,
                ev_id=request.ev_id,
                requested_real_kw=request.real_kw,
                requested_reactive_kvar=request.reactive_kvar,
                command_payload="",
                success=False,
                error=validation_error,
                pre_attack_total_real_power_kw=pre_state.total_real_power_kw,
                pre_attack_in_violation=pre_state.is_in_violation,
            )

        allowed, reason = self._constraints.can_attack(pre_state.simulation_time_sec)
        if not allowed:
            return AttackResult(
                timestamp=pre_state.timestamp.isoformat(),
                simulation_time_sec=pre_state.simulation_time_sec,
                ev_id=request.ev_id,
                requested_real_kw=request.real_kw,
                requested_reactive_kvar=request.reactive_kvar,
                command_payload="",
                success=False,
                blocked_reason=reason,
                pre_attack_total_real_power_kw=pre_state.total_real_power_kw,
                pre_attack_in_violation=pre_state.is_in_violation,
            )

        # Set target in ramp controller (don't publish directly!)
        current_power = self._ramp_controller.get_current(request.ev_id)
        self._ramp_controller.set_target(request.ev_id, request.real_kw)

        # Record the attack
        self._observer.set_last_ev_command(request.ev_id, request.real_kw, request.reactive_kvar)
        self._constraints.record_attack(pre_state.simulation_time_sec)

        # Calculate estimated ramp time
        power_diff = abs(request.real_kw - current_power)
        estimated_ramp_time = power_diff / self._ramp_rate if power_diff > 0.1 else 0.0

        # Generate a descriptive payload (actual publishing happens in update())
        payload = f"RAMP:{request.ev_id}:{current_power:.1f}->{request.real_kw:.1f}kW"

        logger.info(
            "Attack command: %s target=%.1fkW (current=%.1fkW, ramp_time=%.1fs)",
            request.ev_id, request.real_kw, current_power, estimated_ramp_time
        )

        return AttackResult(
            timestamp=pre_state.timestamp.isoformat(),
            simulation_time_sec=pre_state.simulation_time_sec,
            ev_id=request.ev_id,
            requested_real_kw=request.real_kw,
            requested_reactive_kvar=request.reactive_kvar,
            command_payload=payload,
            success=True,
            pre_attack_total_real_power_kw=pre_state.total_real_power_kw,
            pre_attack_in_violation=pre_state.is_in_violation,
            post_attack_total_real_power_kw=None,
            post_attack_in_violation=None,
            caused_violation=False,
            # Ramping fields
            ramping=True,
            current_kw=current_power,
            target_kw=request.real_kw,
            estimated_ramp_time_sec=estimated_ramp_time,
        )

    def update(self, dt_sec: Optional[float] = None) -> Dict[str, float]:
        """
        MUST be called every HELICS timestep (5s).
        Advances ramping and publishes new setpoints to GridLAB-D.

        Returns: {ev_id: new_power_kw} for EVs that were updated
        """
        updates = self._ramp_controller.update(dt_sec)

        for ev_id, power_kw in updates.items():
            self._publish_setpoint(ev_id, power_kw)

        return updates

    def _publish_setpoint(self, ev_id: str, power_kw: float) -> None:
        """Publish power setpoint to GridLAB-D via HELICS endpoint."""
        # Use the federate's send_ev_setpoint method
        self._federate.send_ev_setpoint(ev_id, real_kw=power_kw, reactive_kvar=0.0)

    def get_ramp_status(self) -> Dict[str, dict]:
        """Get ramping status for all EVs."""
        return self._ramp_controller.get_ramp_status()

    def is_ramping(self) -> bool:
        """Check if any EV is currently ramping."""
        return self._ramp_controller.is_any_ramping()

    def get_current_powers(self) -> Dict[str, float]:
        """Get current power for all EVs."""
        return self._ramp_controller.get_all_current_powers()

    def reset(self) -> None:
        """Reset the ramp controller to initial state."""
        self._ramp_controller.reset()
