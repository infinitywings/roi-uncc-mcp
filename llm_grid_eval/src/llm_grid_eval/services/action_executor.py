"""Attack action execution service."""

from __future__ import annotations

from datetime import datetime

from ..helics_interface.federate import GridFederate
from ..models.attack import AttackRequest, AttackResult
from ..services.attack_constraints import ConstraintService
from ..models.grid_state import GridState
from ..services.grid_observer import GridObserver


class ActionExecutor:
    def __init__(
        self,
        federate: GridFederate,
        observer: GridObserver,
        constraints: ConstraintService,
    ):
        self._federate = federate
        self._observer = observer
        self._constraints = constraints

    def execute(self, request: AttackRequest, *, pre_state: GridState | None = None) -> AttackResult:
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

        payload = self._federate.send_ev_setpoint(
            request.ev_id,
            real_kw=request.real_kw,
            reactive_kvar=request.reactive_kvar,
        )
        self._observer.set_last_ev_command(request.ev_id, request.real_kw, request.reactive_kvar)
        self._constraints.record_attack(pre_state.simulation_time_sec)

        # Post state is not advanced here (fair pacing); will be reflected in next observe/analyze.
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
        )
