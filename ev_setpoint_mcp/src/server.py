"""Flask server exposing EV setpoint MCP primitives."""

from __future__ import annotations

import atexit
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Callable

from flask import Flask, jsonify, request
from flask_cors import CORS
import yaml

from .ev_federate import EVSetpointFederate
from .observation_service import ObservationService
from .action_service import ActionService

logger = logging.getLogger(__name__)


class EVSetpointMCPServer:
    """Orchestrates the Flask app, federate, and primitive handlers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = Flask(__name__)
        CORS(self.app)

        helics_cfg = config.get("helics", {})
        self.federate = EVSetpointFederate(helics_cfg)
        self.observation = ObservationService(self.federate, config)
        self.action = ActionService(self.federate, config)

        self._observation_handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "get_grid_status": self.observation.get_grid_status,
            "discover_topology": self.observation.discover_topology,
            "monitor_protection_systems": self.observation.monitor_protection_systems,
            "analyze_power_flow": self.observation.analyze_power_flow,
        }
        self._action_handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "set_ev_capacity": self.action.set_ev_capacity,
        }

        logging_cfg = config.get("logging", {})
        interaction_log = logging_cfg.get("interaction_log")
        if interaction_log:
            self._interaction_log_path = os.path.abspath(os.path.join(os.getcwd(), interaction_log))
            os.makedirs(os.path.dirname(self._interaction_log_path), exist_ok=True)
        else:
            self._interaction_log_path = None

        self._ai_config = config.get("ai", {})

        self._register_routes()
        atexit.register(self.shutdown)

    # ------------------------------------------------------------------
    def _register_routes(self) -> None:
        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({
                "status": "ok",
                "federate_running": self.federate is not None
            })

        @self.app.route("/primitive", methods=["POST"])
        def primitive():
            payload = request.get_json(silent=True) or {}
            method = payload.get("method")
            params = payload.get("params", {})
            logger.info("Received primitive request: %s", method)

            if method in self._observation_handlers:
                handler = self._observation_handlers[method]
            elif method in self._action_handlers:
                handler = self._action_handlers[method]
            else:
                return jsonify({"error": f"Unknown primitive '{method}'"}), 400

            start_ts = time.time()
            try:
                result = handler(params)
            except Exception as exc:  # pragma: no cover - runtime safety
                latency = time.time() - start_ts
                logger.exception("Primitive %s failed after %.3fs: %s", method, latency, exc)
                self._record_interaction(
                    method,
                    params,
                    status="error",
                    result={"message": str(exc), "latency_sec": latency}
                )
                return jsonify({"status": "error", "message": str(exc)}), 500

            latency = time.time() - start_ts
            logger.debug("Primitive %s completed in %.3fs", method, latency)
            self._record_interaction(
                method,
                params,
                status="success",
                result={"payload": result, "latency_sec": latency}
            )

            response_payload = {"status": "success", "result": result}
            if method in self._observation_handlers:
                response_payload["ai"] = self._ai_config

            return jsonify(response_payload)

    # ------------------------------------------------------------------
    def start(self) -> None:
        logger.info("Starting EV setpoint MCP server")
        self.federate.initialize()

        server_cfg = self.config.get("server", {})
        self.app.run(
            host=server_cfg.get("host", "0.0.0.0"),
            port=int(server_cfg.get("port", 5100)),
            debug=server_cfg.get("debug", False)
        )

    def shutdown(self) -> None:
        logger.info("Shutting down EV setpoint MCP server")
        try:
            self.federate.finalize()
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logger.error("Error during federate shutdown: %s", exc)

    # ------------------------------------------------------------------
    def _record_interaction(self, method: str, params: Dict[str, Any], status: str, result: Any) -> None:
        if not self._interaction_log_path:
            return

        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "method": method,
            "params": params,
            "status": status,
            "result": result
        }

        try:
            with open(self._interaction_log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str))
                handle.write("\n")
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.error("Could not write interaction log: %s", exc)


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    broker_override = os.getenv("HELICS_BROKER_ADDRESS")
    if broker_override:
        config.setdefault("helics", {})["broker_address"] = broker_override

    host_override = os.getenv("EV_MCP_SERVER_HOST")
    if host_override:
        config.setdefault("server", {})["host"] = host_override

    port_override = os.getenv("EV_MCP_SERVER_PORT")
    if port_override:
        config.setdefault("server", {})["port"] = int(port_override)

    return config


__all__ = ["EVSetpointMCPServer", "load_config"]
