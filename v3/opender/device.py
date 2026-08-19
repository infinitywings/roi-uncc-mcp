"""Minimal standalone OpenDER BESS wrapper with explicit setting scheduling."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any

import opender
from opender.der_bess import DER_BESS


@dataclass(frozen=True)
class DeviceOutput:
    time_s: float
    p_out_kw: float
    q_out_kvar: float
    status: str
    soc: float


class ScheduledOpenDERBESS:
    """Wrap OpenDER with deterministic, simulation-time setting execution.

    OpenDER 2.2.0's internal ``NP_SET_EXE_TIME`` path holds the same mutable
    settings object and therefore observes in-place changes immediately.
    This wrapper disables that path and queues explicit setting snapshots.
    """

    def __init__(
        self, step_s: float = 1.0, *, der_file_obj: Any | None = None
    ) -> None:
        if step_s <= 0:
            raise ValueError("step_s must be positive")
        self.step_s = float(step_s)
        self.time_s = 0.0
        self.model = DER_BESS(der_file_obj=der_file_obj)
        self.model.der_file.NP_SET_EXE_TIME = 0
        self._demand_kw = 0.0
        self._gateway_controls_demand = False
        self._sequence = 0
        self._pending: list[
            tuple[
                float,
                int,
                str | None,
                dict[str, Any],
                dict[str, float],
            ]
        ] = []
        self._gateway_action_ids: set[str] = set()

    @property
    def demand_kw(self) -> float:
        """Persistent demand input used when ``step`` omits ``demand_kw``."""

        return self._demand_kw

    @staticmethod
    def _validate_demand_kw(value: Any) -> float:
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ValueError("demand_kw must be a finite number")
        return float(value)

    def _validate_settings(self, settings: dict[str, Any]) -> None:
        unknown = [
            name
            for name in settings
            if not hasattr(self.model.der_file, name)
        ]
        if unknown:
            raise AttributeError(
                f"Unknown OpenDER setting(s): {', '.join(unknown)}"
            )

    def schedule_settings(
        self, delay_s: float, **settings: Any
    ) -> dict[str, Any]:
        if (
            not isinstance(delay_s, (int, float))
            or isinstance(delay_s, bool)
            or not math.isfinite(float(delay_s))
            or delay_s < 0
        ):
            raise ValueError("delay_s must be finite and non-negative")
        self._validate_settings(settings)
        due_time_s = self.time_s + float(delay_s)
        snapshot = dict(settings)
        self._sequence += 1
        heapq.heappush(
            self._pending,
            (due_time_s, self._sequence, None, snapshot, {}),
        )
        return {
            "accepted_time_s": self.time_s,
            "due_time_s": due_time_s,
            "settings": dict(snapshot),
        }

    def schedule_gateway_action(
        self,
        *,
        action_id: str,
        delay_s: float = 0.0,
        settings: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Atomically queue one gateway action for a future device step."""

        if not isinstance(action_id, str) or not action_id:
            raise ValueError("action_id must be a non-empty string")
        if action_id in self._gateway_action_ids:
            raise ValueError(f"duplicate gateway action_id: {action_id}")
        if (
            not isinstance(delay_s, (int, float))
            or isinstance(delay_s, bool)
            or not math.isfinite(float(delay_s))
            or delay_s < 0
        ):
            raise ValueError("delay_s must be finite and non-negative")
        setting_snapshot = dict(settings or {})
        input_values = dict(inputs or {})
        self._validate_settings(setting_snapshot)
        unknown_inputs = sorted(set(input_values) - {"demand_kw"})
        if unknown_inputs:
            raise ValueError(
                "Unknown gateway input(s): " + ", ".join(unknown_inputs)
            )
        input_snapshot: dict[str, float] = {}
        if "demand_kw" in input_values:
            input_snapshot["demand_kw"] = self._validate_demand_kw(
                input_values["demand_kw"]
            )

        due_time_s = self.time_s + float(delay_s)
        self._sequence += 1
        heapq.heappush(
            self._pending,
            (
                due_time_s,
                self._sequence,
                action_id,
                setting_snapshot,
                input_snapshot,
            ),
        )
        self._gateway_action_ids.add(action_id)
        return {
            "action_id": action_id,
            "sink_queued_time_s": self.time_s,
            "sink_due_time_s": due_time_s,
            "settings": dict(setting_snapshot),
            "inputs": dict(input_snapshot),
        }

    def _apply_due_settings(self, next_time_s: float) -> list[dict[str, Any]]:
        applied = []
        while self._pending and self._pending[0][0] <= next_time_s:
            (
                due_time_s,
                sequence,
                action_id,
                settings,
                inputs,
            ) = self._pending[0]
            for name, value in settings.items():
                setattr(self.model.der_file, name, value)
            if "demand_kw" in inputs:
                self._demand_kw = inputs["demand_kw"]
                self._gateway_controls_demand = True
            heapq.heappop(self._pending)
            applied.append(
                {
                    "action_id": action_id,
                    "sequence": sequence,
                    "due_time_s": due_time_s,
                    "applied_time_s": next_time_s,
                    "settings": settings,
                    "inputs": inputs,
                }
            )
        return applied

    def step(
        self,
        *,
        v_pu: float,
        frequency_hz: float,
        demand_kw: float | None = None,
        voltage_angle_deg: float | None = None,
    ) -> tuple[DeviceOutput, list[dict[str, Any]]]:
        next_time_s = self.time_s + self.step_s
        gateway_input_due = any(
            due_time_s <= next_time_s and "demand_kw" in inputs
            for due_time_s, _, _, _, inputs in self._pending
        )
        if demand_kw is not None and (
            self._gateway_controls_demand or gateway_input_due
        ):
            raise ValueError(
                "demand_kw is owned by the gateway after AO0 is queued"
            )
        applied = self._apply_due_settings(next_time_s)
        if demand_kw is not None:
            self._demand_kw = self._validate_demand_kw(demand_kw)
        opender.DER.t_s = self.step_s
        self.model.update_der_input(
            v_pu=v_pu,
            f=frequency_hz,
            p_dem_kw=self._demand_kw,
            theta=voltage_angle_deg,
        )
        self.model.run()
        self.time_s = next_time_s
        return (
            DeviceOutput(
                time_s=self.time_s,
                p_out_kw=float(self.model.p_out_kw),
                q_out_kvar=float(self.model.q_out_kvar),
                status=str(self.model.der_status),
                soc=float(self.model.bess_soc),
            ),
            applied,
        )
