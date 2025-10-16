"""HELICS federate wrapper dedicated to observation primitives and EV setpoint control."""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Any, Optional

import helics as h
import numpy as np

logger = logging.getLogger(__name__)


def _complex_to_polar_dict(value: complex, unit: str) -> Dict[str, Any]:
    """Represent a complex number with polar metadata."""
    magnitude = abs(value)
    angle = float(np.angle(value, deg=True))
    return {
        "real": float(value.real),
        "imag": float(value.imag),
        "magnitude": float(magnitude),
        "angle": angle,
        "unit": unit
    }


def _complex_to_power_dict(value: complex, unit: str) -> Dict[str, Any]:
    """Represent a complex power value in intuitive units."""
    magnitude = abs(value)
    power_factor = float(value.real / magnitude) if magnitude else 0.0
    return {
        "real_kw": float(value.real / 1000.0),
        "imag_kvar": float(value.imag / 1000.0),
        "magnitude_kva": float(magnitude / 1000.0),
        "power_factor": power_factor,
        "unit": unit
    }


class EVSetpointFederate:
    """Minimal HELICS federate for read-only monitoring plus EV capacity control."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.federate = None
        self.subscriptions: Dict[str, Dict[str, Any]] = {}
        self.ev_endpoints: Dict[str, Dict[str, Any]] = {}

        self.current_time = 0.0
        self.grid_state: Dict[str, Any] = {}
        self.ev_setpoints: Dict[str, Dict[str, Any]] = {}

        self._lock = threading.Lock()
        self._poll_thread: Optional[threading.Thread] = None
        self._running = False
        self._refresh_event = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        logger.info("Initializing EV setpoint federate")

        helics_cfg = self.config
        fi = h.helicsCreateFederateInfo()
        h.helicsFederateInfoSetCoreTypeFromString(fi, helics_cfg.get("core_type", "zmq"))
        h.helicsFederateInfoSetCoreName(fi, helics_cfg.get("federate_name", "ev_setpoint_mcp_core"))
        h.helicsFederateInfoSetBroker(fi, helics_cfg["broker_address"])
        h.helicsFederateInfoSetTimeProperty(
            fi, h.HELICS_PROPERTY_TIME_DELTA, helics_cfg.get("time_delta", 1.0)
        )
        h.helicsFederateInfoSetTimeProperty(
            fi, h.HELICS_PROPERTY_TIME_PERIOD, helics_cfg.get("period", 1.0)
        )

        fed_name = helics_cfg.get("federate_name", "ev_setpoint_mcp")
        self.federate = h.helicsCreateCombinationFederate(fed_name, fi)

        self._register_subscriptions(helics_cfg.get("subscriptions", []))
        self._register_endpoints(helics_cfg.get("ev_endpoints", []))

        h.helicsFederateEnterExecutingMode(self.federate)
        logger.info("HELICS federate %s entered execution mode", fed_name)

        # prime the state before serving requests
        self._update_state(step=0.0)

        self._running = True
        poll_interval = float(helics_cfg.get("poll_interval", 1.0))
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            args=(poll_interval,),
            daemon=True,
            name="EVSetpointFederatePoller"
        )
        self._poll_thread.start()

    def finalize(self) -> None:
        logger.info("Finalizing EV setpoint federate")
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5)

        if self.federate is not None:
            try:
                h.helicsFederateFinalize(self.federate)
            finally:
                h.helicsFederateFree(self.federate)
                self.federate = None

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def _register_subscriptions(self, subs_cfg):
        for item in subs_cfg:
            name = item["name"]
            key = item["key"]
            handle = h.helicsFederateRegisterSubscription(self.federate, key, "")
            self.subscriptions[name] = {
                "handle": handle,
                "type": item.get("type", "complex"),
                "unit": item.get("unit", "")
            }
            logger.debug("Registered subscription %s -> %s", name, key)

    def _register_endpoints(self, endpoints_cfg):
        for item in endpoints_cfg:
            name = item["name"]
            key = item["key"]
            endpoint = h.helicsFederateRegisterGlobalEndpoint(
                self.federate,
                key,
                item.get("type", "string")
            )
            destination = item.get("destination")
            if destination:
                h.helicsEndpointSetDefaultDestination(endpoint, destination)
            self.ev_endpoints[name] = {
                "handle": endpoint,
                "destination": destination,
                "phases": item.get("phases", "")
            }
            # initialize default setpoint record
            self.ev_setpoints[name] = {
                "real_va": 0.0,
                "imag_va": 0.0,
                "updated_at": None
            }
            logger.debug("Registered EV endpoint %s -> %s", name, destination)

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------
    def _poll_loop(self, interval: float) -> None:
        period = float(self.config.get("period", 1.0))
        while self._running:
            triggered = self._refresh_event.wait(interval)
            self._refresh_event.clear()
            start = time.time()
            try:
                self._update_state(step=period)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Error updating federate state: %s", exc)
            finally:
                elapsed = time.time() - start
                logger.debug(
                    "State refresh (triggered=%s) completed in %.3fs",
                    triggered,
                    elapsed
                )

    # ------------------------------------------------------------------
    # Public data access
    # ------------------------------------------------------------------
    def get_state_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "timestamp": self.grid_state.get("timestamp"),
                "voltages": dict(self.grid_state.get("voltages", {})),
                "powers": dict(self.grid_state.get("powers", {})),
                "ev_setpoints": dict(self.grid_state.get("ev_setpoints", {}))
            }

    def get_ev_limits(self) -> Dict[str, Dict[str, float]]:
        return self.config.get("setpoint_constraints", {}).get("ev_limits", {})

    # ------------------------------------------------------------------
    # Primitive support
    # ------------------------------------------------------------------
    def set_ev_capacity(self, ev_id: str, real_va: float, imag_va: float = 0.0) -> Dict[str, Any]:
        if ev_id not in self.ev_endpoints:
            raise ValueError(f"Unknown EV identifier '{ev_id}'")

        endpoint_info = self.ev_endpoints[ev_id]
        handle = endpoint_info["handle"]
        destination = endpoint_info.get("destination", "")

        payload = f"{real_va}+{imag_va}j"
        logger.info(
            "Dispatching EV capacity command %s -> %s (%s)", ev_id, destination, payload
        )
        send_start = time.time()
        h.helicsEndpointSendBytesTo(handle, payload.encode("utf-8"), destination)
        send_elapsed = time.time() - send_start
        logger.debug(
            "HELICS send completed in %.3fs for %s", send_elapsed, ev_id
        )

        # Request a near-immediate state refresh without blocking this thread.
        self._refresh_event.set()

        with self._lock:
            record = self.ev_setpoints[ev_id]
            record.update({
                "real_va": float(real_va),
                "imag_va": float(imag_va),
                "updated_at": time.time()
            })
            # Mirror into grid_state for quick access
            current_ev_state = self.grid_state.setdefault("ev_setpoints", {})
            current_ev_state[ev_id] = {
                "real_kw": float(real_va / 1000.0),
                "imag_kvar": float(imag_va / 1000.0),
                "timestamp": record["updated_at"]
            }
            snapshot = {
                "status": "accepted",
                "ev_id": ev_id,
                "command_va": {
                    "real": record["real_va"],
                    "imag": record["imag_va"]
                },
                "timestamp": record["updated_at"]
            }
        snapshot["helics_send_latency_sec"] = send_elapsed
        snapshot["refresh_queued"] = True
        return snapshot

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_state(self, step: float) -> None:
        if self.federate is None:
            return

        target_time = self.current_time + step
        self.current_time = h.helicsFederateRequestTime(self.federate, target_time)

        grid_state = {
            "timestamp": self.current_time,
            "voltages": {},
            "powers": {},
            "ev_setpoints": {}
        }

        for name, meta in self.subscriptions.items():
            handle = meta["handle"]
            meta_type = meta["type"]
            unit = meta.get("unit", "")

            if meta_type == "complex":
                value = h.helicsInputGetComplex(handle)
                if "power" in name:
                    grid_state["powers"][name] = _complex_to_power_dict(value, unit)
                else:
                    grid_state["voltages"][name] = _complex_to_polar_dict(value, unit)
            elif meta_type == "double":
                value = h.helicsInputGetDouble(handle)
                grid_state["powers"][name] = {"value": float(value), "unit": unit}
            elif meta_type == "string":
                value = h.helicsInputGetString(handle)
                grid_state["powers"][name] = {"value": value, "unit": unit}

        with self._lock:
            grid_state["ev_setpoints"] = {
                ev: {
                    "real_kw": info["real_va"] / 1000.0,
                    "imag_kvar": info["imag_va"] / 1000.0,
                    "timestamp": info["updated_at"]
                }
                for ev, info in self.ev_setpoints.items()
            }
            self.grid_state = grid_state

    # Context manager sugar -------------------------------------------------
    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.finalize()
