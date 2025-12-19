"""HELICS federate wrapper for LLM-GridEval attacker."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import helics as h

from .config import HelicsConfig

logger = logging.getLogger(__name__)


class GridFederate:
    """
    Minimal HELICS federate for:
    - Subscribing to feeder power (Sa/Sb/Sc) and transmission voltages (Va/Vb/Vc)
    - Sending EV setpoint commands to GridLAB-D endpoints (EV1..EV6)
    """

    def __init__(self, config: HelicsConfig):
        self._config = config
        self._fed = None
        self._lock = threading.Lock()
        self._current_time = 0.0

        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._endpoints: Dict[str, Dict[str, Any]] = {}

    @property
    def is_initialized(self) -> bool:
        return self._fed is not None

    @property
    def current_time(self) -> float:
        return float(self._current_time)

    @property
    def period_sec(self) -> float:
        return float(self._config.period_sec)

    def initialize(self) -> None:
        if self._fed is not None:
            return

        logger.info("Initializing HELICS federate '%s' (broker=%s)", self._config.name, self._config.broker_address)
        fi = h.helicsCreateFederateInfo()
        h.helicsFederateInfoSetCoreTypeFromString(fi, self._config.core_type)
        h.helicsFederateInfoSetCoreName(fi, f"{self._config.name}_core")
        h.helicsFederateInfoSetBroker(fi, self._config.broker_address)
        h.helicsFederateInfoSetTimeProperty(fi, h.HELICS_PROPERTY_TIME_DELTA, self.period_sec)
        h.helicsFederateInfoSetTimeProperty(fi, h.HELICS_PROPERTY_TIME_PERIOD, self.period_sec)

        with self._lock:
            self._fed = h.helicsCreateCombinationFederate(self._config.name, fi)
            self._register_subscriptions()
            self._register_endpoints()
            h.helicsFederateEnterExecutingMode(self._fed)
            self._current_time = float(h.helicsFederateGetCurrentTime(self._fed))

        logger.info("HELICS federate '%s' entered executing mode", self._config.name)

    def finalize(self) -> None:
        with self._lock:
            if self._fed is None:
                return
            try:
                h.helicsFederateFinalize(self._fed)
            finally:
                h.helicsFederateFree(self._fed)
                self._fed = None
                self._subscriptions = {}
                self._endpoints = {}

    def _register_subscriptions(self) -> None:
        assert self._fed is not None

        def sub(name: str, key: str, value_type: str):
            handle = h.helicsFederateRegisterSubscription(self._fed, key, "")
            self._subscriptions[name] = {"handle": handle, "type": value_type, "key": key}

        # Feeder power (GridLAB-D)
        sub("Sa", "gld_hlc_conn/Sa", "complex")
        sub("Sb", "gld_hlc_conn/Sb", "complex")
        sub("Sc", "gld_hlc_conn/Sc", "complex")

        # Transmission voltages (GridPACK)
        sub("Va", "gridpack/Va", "complex")
        sub("Vb", "gridpack/Vb", "complex")
        sub("Vc", "gridpack/Vc", "complex")

        # Optional blue-team switch publications (may be absent depending on run)
        sub("swEV1", "swEV1", "string")
        sub("swEV1_storage", "swEV1_storage", "string")
        sub("swEV4", "swEV4", "string")
        sub("swEV4_storage", "swEV4_storage", "string")

    def _register_endpoints(self) -> None:
        assert self._fed is not None

        for ev_id in ("EV1", "EV2", "EV3", "EV4", "EV5", "EV6"):
            endpoint = h.helicsFederateRegisterEndpoint(self._fed, f"attacker/{ev_id}", "")
            destination = f"gld_hlc_conn/{ev_id}"
            h.helicsEndpointSetDefaultDestination(endpoint, destination)
            self._endpoints[ev_id] = {"handle": endpoint, "destination": destination}

    def step(self) -> float:
        """
        Advance simulation time by one period and refresh subscription values.
        This is intentionally called by /tools/observe and /tools/analyze so
        the experiment drivers control pacing (observe-decide-wait).
        """
        if self._fed is None:
            self.initialize()

        assert self._fed is not None
        target = self._current_time + self.period_sec
        with self._lock:
            self._current_time = float(h.helicsFederateRequestTime(self._fed, target))
            return self._current_time

    def read(self) -> Dict[str, Any]:
        """Read current subscription values without advancing time."""
        if self._fed is None:
            self.initialize()

        assert self._fed is not None
        with self._lock:
            data: Dict[str, Any] = {
                "simulation_time_sec": float(self._current_time),
                "powers": {},
                "voltages": {},
                "switches": {},
            }
            for name, meta in self._subscriptions.items():
                handle = meta["handle"]
                if meta["type"] == "complex":
                    val = h.helicsInputGetComplex(handle)
                    if name in {"Sa", "Sb", "Sc"}:
                        data["powers"][name] = val
                    else:
                        data["voltages"][name] = val
                elif meta["type"] == "string":
                    data["switches"][name] = h.helicsInputGetString(handle)
            return data

    def send_ev_setpoint(self, ev_id: str, real_kw: float, reactive_kvar: float = 0.0) -> str:
        """Send an EV setpoint command as a complex string in W + jVAR."""
        if self._fed is None:
            self.initialize()

        endpoint_info = self._endpoints.get(ev_id)
        if not endpoint_info:
            raise ValueError(f"Unknown EV id '{ev_id}'")

        real_w = float(real_kw) * 1000.0
        imag_var = float(reactive_kvar) * 1000.0
        payload = f"{real_w:.1f}{imag_var:+.1f}j"

        with self._lock:
            endpoint = endpoint_info["handle"]
            destination = endpoint_info["destination"]
            h.helicsEndpointSendBytesTo(endpoint, payload.encode("utf-8"), destination)

        return payload

