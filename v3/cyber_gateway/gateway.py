"""Deterministic, standalone GridEval v3 cyber gateway.

The semantic command is the message defined by
``v3/interfaces/cyber_message.schema.json``. DNP3 SELECT and OPERATE are
transport operations and are consequently supplied separately to
``CyberGateway.ingest`` rather than added to that strict envelope.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


DEFAULT_POINT_MAP = Path(__file__).with_name("dnp3_point_map.yaml")

_TOP_LEVEL_FIELDS = {
    "schema_version",
    "kind",
    "message_id",
    "parent_message_id",
    "event_time_s",
    "source",
    "target",
    "sequence",
    "type",
    "payload",
}
_REQUIRED_TOP_LEVEL_FIELDS = _TOP_LEVEL_FIELDS - {"parent_message_id"}
_PAYLOAD_FIELDS = {"value", "unit", "valid_until_s", "quality"}
_REQUIRED_PAYLOAD_FIELDS = {"value", "unit"}
_QUALITY_VALUES = {
    "online",
    "restart",
    "communication_lost",
    "remote_forced",
    "local_forced",
    "over_range",
    "reference_error",
    "rollover",
    "discontinuity",
    "stale",
    "invalid",
}
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1
_POINT_MAP_FIELDS = {
    "schema_version",
    "campaign_stage",
    "device_id",
    "outstation",
    "sign_convention",
    "select_before_operate",
    "freshness",
    "authority",
    "commands",
    "telemetry",
}
_G4_ENABLED_COMMANDS = {
    "active_power_setpoint": {
        "dnp3_group": "analog_output",
        "index": 0,
        "dnp3_object": "G41V1",
        "wire_type": "int32",
        "value_type": "number",
        "unit": "kW",
        "minimum": -200.0,
        "maximum": 200.0,
        "raw_minimum": -200_000,
        "raw_maximum": 200_000,
        "raw_scale": 0.001,
        "opender_mapping": "active_power_demand",
    },
    "reactive_setpoint": {
        "dnp3_group": "analog_output",
        "index": 1,
        "dnp3_object": "G41V1",
        "wire_type": "int32",
        "value_type": "number",
        "unit": "kvar",
        "minimum": -88.0,
        "maximum": 88.0,
        "raw_minimum": -88_000,
        "raw_maximum": 88_000,
        "raw_scale": 0.001,
        "opender_mapping": "reactive_setpoint",
        "opender_scale": 0.005,
    },
}
_G4_DISABLED_COMMAND_POINTS = {
    "active_power_limit": ("analog_output", 2),
    "reactive_mode": ("analog_output", 3),
    "autonomous_curve": ("octet_string", 0),
}
_G4_ANALOG_TELEMETRY = {
    "active_power": (
        "analog_input",
        0,
        "G30V5",
        "float32",
        "number",
        "kW",
        -200.0,
        200.0,
    ),
    "reactive_power": (
        "analog_input",
        1,
        "G30V5",
        "float32",
        "number",
        "kvar",
        -88.0,
        88.0,
    ),
    "terminal_voltage": (
        "analog_input",
        2,
        "G30V5",
        "float32",
        "number",
        "pu",
        0.0,
        2.0,
    ),
    "state_of_charge": (
        "analog_input",
        3,
        "G30V5",
        "float32",
        "number",
        "pu",
        0.0,
        1.0,
    ),
}
_G4_BINARY_TELEMETRY = {
    "connected": ("binary_input", 0, "G1V2", "boolean", "boolean", "boolean"),
    "command_accepted": (
        "binary_input",
        1,
        "G1V2",
        "boolean",
        "boolean",
        "boolean",
    ),
}
_BAD_COMMAND_QUALITY = _QUALITY_VALUES - {"online"}


class GatewayConfigurationError(ValueError):
    """Raised when the frozen point map is internally inconsistent."""


def load_point_map(path: str | Path = DEFAULT_POINT_MAP) -> dict[str, Any]:
    """Load the JSON-compatible YAML point map without a YAML dependency."""

    point_map_path = Path(path)
    try:
        value = json.loads(point_map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GatewayConfigurationError(
            f"cannot load point map {point_map_path}: {exc}"
        ) from exc
    _validate_point_map(value)
    return value


def point_map_sha256(path: str | Path = DEFAULT_POINT_MAP) -> str:
    """Return the exact on-disk SHA-256 used to freeze a campaign manifest."""

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_point_map(point_map: Any) -> None:
    if not isinstance(point_map, dict):
        raise GatewayConfigurationError("point map must be an object")
    if set(point_map) != _POINT_MAP_FIELDS:
        raise GatewayConfigurationError("point map fields must match the G4 freeze")
    if point_map["schema_version"] != "0.1":
        raise GatewayConfigurationError("unsupported point-map schema_version")
    if point_map["campaign_stage"] != "G4":
        raise GatewayConfigurationError("campaign_stage must be G4")
    if point_map["device_id"] != "DER_EV4_BESS":
        raise GatewayConfigurationError("device_id must be DER_EV4_BESS")

    outstation = point_map["outstation"]
    if (
        not isinstance(outstation, dict)
        or set(outstation) != {"field_node", "dnp3_address"}
        or outstation.get("field_node") != "rtu_ev4"
        or outstation.get("dnp3_address") != 4
    ):
        raise GatewayConfigurationError(
            "outstation must be frozen to rtu_ev4 address 4"
        )

    if point_map["sign_convention"] != {
        "active_power_positive": "generation",
        "reactive_power_positive": "injection",
        "soc": "fraction_of_nameplate_energy",
    }:
        raise GatewayConfigurationError("invalid G4 sign convention")

    sbo = point_map["select_before_operate"]
    if (
        not isinstance(sbo, dict)
        or set(sbo) != {"required", "timeout_s", "exact_value_match"}
        or sbo.get("required") is not True
        or sbo.get("exact_value_match") is not True
        or not _is_finite_number(sbo.get("timeout_s"))
        or float(sbo["timeout_s"]) != 5.0
    ):
        raise GatewayConfigurationError(
            "G4 SBO must require exact-value match with a 5-second timeout"
        )

    freshness = point_map["freshness"]
    if (
        not isinstance(freshness, dict)
        or set(freshness) != {"maximum_age_s", "maximum_future_skew_s"}
        or not _is_finite_number(freshness.get("maximum_age_s"))
        or not _is_finite_number(freshness.get("maximum_future_skew_s"))
        or float(freshness["maximum_age_s"]) != 10.0
        or float(freshness["maximum_future_skew_s"]) != 0.0
    ):
        raise GatewayConfigurationError("freshness policy must match the G4 freeze")

    commands = point_map["commands"]
    expected_command_names = (
        set(_G4_ENABLED_COMMANDS) | set(_G4_DISABLED_COMMAND_POINTS)
    )
    if not isinstance(commands, dict) or set(commands) != expected_command_names:
        raise GatewayConfigurationError("command names must match the G4 freeze")

    occupied: set[tuple[str, int]] = set()
    for name, spec in commands.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("enabled"), bool):
            raise GatewayConfigurationError(f"invalid command spec {name}")
        group = spec.get("dnp3_group")
        index = spec.get("index")
        if (
            not isinstance(group, str)
            or not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
        ):
            raise GatewayConfigurationError(
                f"{name} requires a DNP3 group and integer index"
            )
        point = (group, index)
        if point in occupied:
            raise GatewayConfigurationError(f"duplicate DNP3 point {point}")
        occupied.add(point)

    for name, expected in _G4_ENABLED_COMMANDS.items():
        spec = commands[name]
        if spec["enabled"] is not True:
            raise GatewayConfigurationError(f"{name} must be enabled")
        expected_fields = {"enabled", "execution_delay_s", *expected}
        if set(spec) != expected_fields:
            raise GatewayConfigurationError(f"{name} fields must match the G4 freeze")
        for field, value in expected.items():
            if spec.get(field) != value:
                raise GatewayConfigurationError(
                    f"{name} {field} must match the G4 freeze"
                )
        if (
            not _is_finite_number(spec["execution_delay_s"])
            or spec["execution_delay_s"] < 0
        ):
            raise GatewayConfigurationError(
                f"{name} execution_delay_s must be finite and non-negative"
            )
        raw_minimum = spec["raw_minimum"]
        raw_maximum = spec["raw_maximum"]
        if (
            not isinstance(raw_minimum, int)
            or isinstance(raw_minimum, bool)
            or not isinstance(raw_maximum, int)
            or isinstance(raw_maximum, bool)
            or raw_minimum < _INT32_MIN
            or raw_maximum > _INT32_MAX
            or raw_minimum >= raw_maximum
        ):
            raise GatewayConfigurationError(f"{name} raw range must fit signed int32")
        scale = float(spec["raw_scale"])
        if (
            not math.isclose(
                raw_minimum * scale,
                float(spec["minimum"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            or not math.isclose(
                raw_maximum * scale,
                float(spec["maximum"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise GatewayConfigurationError(
                f"{name} engineering and raw ranges are inconsistent"
            )

    for name, (group, index) in _G4_DISABLED_COMMAND_POINTS.items():
        spec = commands[name]
        if (
            spec["enabled"] is not False
            or spec.get("dnp3_group") != group
            or spec.get("index") != index
        ):
            raise GatewayConfigurationError(
                f"{name} must remain disabled at {group} index {index}"
            )

    authority = point_map["authority"]
    if authority != {
        "ev_controller_v3": [
            "active_power_setpoint",
            "reactive_setpoint",
        ]
    }:
        raise GatewayConfigurationError("authority must match the minimal G4 allowlist")
    for source, allowed in authority.items():
        if not isinstance(source, str) or not isinstance(allowed, list):
            raise GatewayConfigurationError("invalid authority entry")
        if len(allowed) != len(set(allowed)):
            raise GatewayConfigurationError(f"authority for {source} has duplicates")
        if any(
            name not in commands or commands[name]["enabled"] is not True
            for name in allowed
        ):
            raise GatewayConfigurationError(
                f"authority for {source} references a disabled or unknown command"
            )

    telemetry = point_map["telemetry"]
    expected_telemetry_names = (
        set(_G4_ANALOG_TELEMETRY) | set(_G4_BINARY_TELEMETRY)
    )
    if not isinstance(telemetry, dict) or set(telemetry) != expected_telemetry_names:
        raise GatewayConfigurationError("telemetry names must match the G4 freeze")

    for name, expected in _G4_ANALOG_TELEMETRY.items():
        spec = telemetry[name]
        expected_fields = {
            "dnp3_group",
            "index",
            "dnp3_object",
            "wire_type",
            "value_type",
            "unit",
            "minimum",
            "maximum",
        }
        if not isinstance(spec, dict) or set(spec) != expected_fields:
            raise GatewayConfigurationError(
                f"{name} telemetry fields must match the G4 freeze"
            )
        if (
            not isinstance(spec["index"], int)
            or isinstance(spec["index"], bool)
            or spec["index"] < 0
            or not _is_finite_number(spec["minimum"])
            or not _is_finite_number(spec["maximum"])
            or spec["minimum"] >= spec["maximum"]
        ):
            raise GatewayConfigurationError(
                f"{name} telemetry index and range must be numeric"
            )
        actual = tuple(
            spec[field]
            for field in (
                "dnp3_group",
                "index",
                "dnp3_object",
                "wire_type",
                "value_type",
                "unit",
                "minimum",
                "maximum",
            )
        )
        if actual != expected:
            raise GatewayConfigurationError(
                f"{name} telemetry must be a G30V5 engineering float"
            )
        point = (spec["dnp3_group"], spec["index"])
        if point in occupied:
            raise GatewayConfigurationError(f"duplicate DNP3 point {point}")
        occupied.add(point)

    for name, expected in _G4_BINARY_TELEMETRY.items():
        spec = telemetry[name]
        expected_fields = {
            "dnp3_group",
            "index",
            "dnp3_object",
            "wire_type",
            "value_type",
            "unit",
        }
        if name == "command_accepted":
            expected_fields.add("semantics")
        if not isinstance(spec, dict) or set(spec) != expected_fields:
            raise GatewayConfigurationError(
                f"{name} telemetry fields must match the G4 freeze"
            )
        if (
            not isinstance(spec["index"], int)
            or isinstance(spec["index"], bool)
            or spec["index"] < 0
        ):
            raise GatewayConfigurationError(
                f"{name} telemetry index must be a non-negative integer"
            )
        actual = tuple(
            spec[field]
            for field in (
                "dnp3_group",
                "index",
                "dnp3_object",
                "wire_type",
                "value_type",
                "unit",
            )
        )
        if actual != expected:
            raise GatewayConfigurationError(
                f"{name} telemetry must be a G1V2 boolean"
            )
        if (
            name == "command_accepted"
            and spec["semantics"] != "gateway_validation_and_queue_acceptance"
        ):
            raise GatewayConfigurationError(
                "command_accepted semantics must be gateway acceptance"
            )
        point = (spec["dnp3_group"], spec["index"])
        if point in occupied:
            raise GatewayConfigurationError(f"duplicate DNP3 point {point}")
        occupied.add(point)


class CyberGateway:
    """Validate, arbitrate, queue, and log remote OpenDER settings.

    All clocks are caller-supplied simulation seconds. No wall-clock value,
    random value, or process-local identifier enters a decision or event.
    """

    def __init__(
        self,
        *,
        point_map: Mapping[str, Any] | None = None,
        point_map_path: str | Path = DEFAULT_POINT_MAP,
        event_log_path: str | Path | None = None,
    ) -> None:
        loaded = (
            deepcopy(dict(point_map))
            if point_map is not None
            else load_point_map(point_map_path)
        )
        _validate_point_map(loaded)
        self.point_map = loaded
        self.event_log_path = (
            Path(event_log_path) if event_log_path is not None else None
        )
        if self.event_log_path is not None:
            self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
            self.event_log_path.touch(exist_ok=True)

        self.time_s = 0.0
        self._last_ingress_time_s = 0.0
        self._event_sequence = 0
        self._actuation_sequence = 0
        self._pending: list[tuple[float, int, dict[str, Any]]] = []
        self._selections: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._accepted_sequence: dict[tuple[str, str, str], int] = {}
        self._message_fingerprints: dict[str, str] = {}
        self._seen_operations: set[tuple[str, str]] = set()
        self._sink_queued_actions: dict[str, dict[str, Any]] = {}
        self._opender_applied_actions: set[str] = set()

    def ingest(
        self,
        message: Any,
        *,
        operation: str,
        receive_time_s: float,
    ) -> dict[str, Any]:
        """Process one DNP3 SELECT or OPERATE carrying a semantic command."""

        if operation not in {"select", "operate"}:
            return self._reject(
                message, operation, receive_time_s, "unsupported_operation"
            )
        if (
            not _is_finite_number(receive_time_s)
            or receive_time_s < self.time_s
            or receive_time_s < self._last_ingress_time_s
        ):
            return self._reject(
                message, operation, receive_time_s, "invalid_receive_time"
            )
        self._last_ingress_time_s = float(receive_time_s)

        reason = self._validate_message(message, float(receive_time_s))
        if reason is not None:
            return self._reject(message, operation, receive_time_s, reason)
        assert isinstance(message, dict)
        message_id = message["message_id"]
        fingerprint = self._fingerprint(message)
        old_fingerprint = self._message_fingerprints.get(message_id)
        if old_fingerprint is not None and old_fingerprint != fingerprint:
            return self._reject(
                message, operation, receive_time_s, "message_id_collision"
            )
        if (message_id, operation) in self._seen_operations:
            return self._reject(
                message, operation, receive_time_s, "duplicate_operation"
            )

        parent_id = message.get("parent_message_id")
        if parent_id is not None:
            if parent_id == message_id:
                return self._reject(
                    message, operation, receive_time_s, "self_parent"
                )
            if parent_id not in self._message_fingerprints:
                return self._reject(
                    message, operation, receive_time_s, "unknown_parent"
                )

        stream = (message["source"], message["target"], message["type"])
        last_sequence = self._accepted_sequence.get(stream)
        if last_sequence is not None and message["sequence"] <= last_sequence:
            return self._reject(
                message, operation, receive_time_s, "non_monotonic_sequence"
            )

        self._message_fingerprints.setdefault(message_id, fingerprint)
        self._seen_operations.add((message_id, operation))
        if operation == "select":
            return self._select(message, stream, fingerprint, float(receive_time_s))
        return self._operate(message, stream, fingerprint, float(receive_time_s))

    def advance_to(
        self, simulation_time_s: float, *, sink: Any | None = None
    ) -> list[dict[str, Any]]:
        """Service due actions in stable acceptance order.

        A sink must expose ``schedule_gateway_action``. An action stays in the
        gateway heap until that call succeeds. Service is not device
        application; pass the records returned by a later OpenDER ``step`` to
        :meth:`record_opender_applications`.
        """

        if (
            not _is_finite_number(simulation_time_s)
            or simulation_time_s < self.time_s
            or simulation_time_s < self._last_ingress_time_s
        ):
            raise ValueError(
                "simulation_time_s must be finite and not precede ingress time"
            )
        self.time_s = float(simulation_time_s)
        serviced: list[dict[str, Any]] = []
        while self._pending and self._pending[0][0] <= self.time_s:
            due_time_s, sequence, action = self._pending[0]
            sink_result = None
            if sink is not None:
                scheduler = getattr(sink, "schedule_gateway_action", None)
                if not callable(scheduler):
                    raise TypeError(
                        "sink must provide schedule_gateway_action"
                    )
                try:
                    sink_result = scheduler(
                        action_id=action["action_id"],
                        delay_s=0.0,
                        settings=action["opender_settings"],
                        inputs=action["opender_inputs"],
                    )
                except Exception as exc:
                    self._event(
                        "sink_queue_failed",
                        self.time_s,
                        {
                            "action_id": action["action_id"],
                            "message_id": action["message_id"],
                            "gateway_due_time_s": due_time_s,
                            "gateway_service_time_s": self.time_s,
                            "error_type": type(exc).__name__,
                        },
                    )
                    raise
            record = {
                **action,
                "actuation_sequence": sequence,
                "gateway_due_time_s": due_time_s,
                "gateway_service_time_s": self.time_s,
                "lifecycle_stage": (
                    "sink_queued"
                    if sink_result is not None
                    else "gateway_serviced_without_sink"
                ),
            }
            if sink_result is not None:
                if (
                    not isinstance(sink_result, Mapping)
                    or sink_result.get("action_id") != action["action_id"]
                    or not _is_finite_number(
                        sink_result.get("sink_queued_time_s")
                    )
                    or not _is_finite_number(
                        sink_result.get("sink_due_time_s")
                    )
                ):
                    raise ValueError("invalid sink queue receipt")
                record["sink_queue"] = sink_result
                self._sink_queued_actions[action["action_id"]] = deepcopy(
                    record
                )
                event_type = "sink_queued"
            else:
                event_type = "gateway_action_serviced"
            heapq.heappop(self._pending)
            self._event(event_type, self.time_s, record)
            serviced.append(record)
        return serviced

    def record_opender_applications(
        self, applied_records: list[Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        """Record actual application reports returned by the OpenDER wrapper."""

        recorded: list[dict[str, Any]] = []
        for application in applied_records:
            if not isinstance(application, Mapping):
                raise ValueError("OpenDER application report must be an object")
            action_id = application.get("action_id")
            if action_id is None:
                continue
            if not isinstance(action_id, str):
                raise ValueError("OpenDER application action_id must be a string")
            queued = self._sink_queued_actions.get(action_id)
            if queued is None:
                raise ValueError(f"unknown sink-queued action_id: {action_id}")
            if action_id in self._opender_applied_actions:
                raise ValueError(f"duplicate OpenDER application: {action_id}")
            required_fields = {
                "action_id",
                "due_time_s",
                "applied_time_s",
                "settings",
                "inputs",
            }
            if not required_fields <= set(application):
                raise ValueError("incomplete OpenDER application report")
            if not isinstance(application["settings"], Mapping):
                raise ValueError("OpenDER settings report must be an object")
            if not isinstance(application["inputs"], Mapping):
                raise ValueError("OpenDER inputs report must be an object")
            reported_settings = dict(application["settings"])
            reported_inputs = dict(application["inputs"])
            if reported_settings != queued["opender_settings"]:
                raise ValueError("OpenDER applied settings mismatch")
            if reported_inputs != queued["opender_inputs"]:
                raise ValueError("OpenDER applied inputs mismatch")
            sink_due_time_s = queued["sink_queue"]["sink_due_time_s"]
            reported_due_time_s = application["due_time_s"]
            if (
                not _is_finite_number(reported_due_time_s)
                or not math.isclose(
                    float(reported_due_time_s),
                    float(sink_due_time_s),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ):
                raise ValueError("OpenDER due_time_s mismatch")
            applied_time_s = application.get("applied_time_s")
            if (
                not _is_finite_number(applied_time_s)
                or applied_time_s < queued["gateway_service_time_s"]
                or applied_time_s < float(reported_due_time_s)
            ):
                raise ValueError("invalid OpenDER applied_time_s")
            record = {
                "action_id": action_id,
                "message_id": queued["message_id"],
                "gateway_due_time_s": queued["gateway_due_time_s"],
                "gateway_service_time_s": queued[
                    "gateway_service_time_s"
                ],
                "opender_due_time_s": float(reported_due_time_s),
                "opender_applied_time_s": float(applied_time_s),
                "opender_settings": deepcopy(reported_settings),
                "opender_inputs": deepcopy(reported_inputs),
                "lifecycle_stage": "opender_applied",
            }
            self._opender_applied_actions.add(action_id)
            self._event(
                "opender_action_applied", float(applied_time_s), record
            )
            recorded.append(record)
        return recorded

    def pending_count(self) -> int:
        return len(self._pending)

    def _select(
        self,
        message: dict[str, Any],
        stream: tuple[str, str, str],
        fingerprint: str,
        receive_time_s: float,
    ) -> dict[str, Any]:
        timeout_s = float(
            self.point_map["select_before_operate"]["timeout_s"]
        )
        self._selections[stream] = {
            "message_id": message["message_id"],
            "fingerprint": fingerprint,
            "expires_at_s": receive_time_s + timeout_s,
        }
        result = {
            "gateway_decision": "selected",
            "reason": "select_accepted",
            "message_id": message["message_id"],
            "receive_time_s": receive_time_s,
            "select_expires_at_s": receive_time_s + timeout_s,
        }
        self._event("command_selected", receive_time_s, result)
        return result

    def _operate(
        self,
        message: dict[str, Any],
        stream: tuple[str, str, str],
        fingerprint: str,
        receive_time_s: float,
    ) -> dict[str, Any]:
        policy = self.point_map["select_before_operate"]
        selection = self._selections.get(stream)
        if policy["required"]:
            if selection is None:
                return self._reject(
                    message, "operate", receive_time_s, "select_required"
                )
            if receive_time_s > selection["expires_at_s"]:
                del self._selections[stream]
                return self._reject(
                    message, "operate", receive_time_s, "select_expired"
                )
            if (
                selection["message_id"] != message["message_id"]
                or selection["fingerprint"] != fingerprint
            ):
                return self._reject(
                    message, "operate", receive_time_s, "select_mismatch"
                )
            del self._selections[stream]

        spec = self.point_map["commands"][message["type"]]
        settings, inputs = self._map_to_opender(
            spec, message["payload"]["value"]
        )
        due_time_s = receive_time_s + float(spec["execution_delay_s"])
        self._actuation_sequence += 1
        action = {
            "action_id": message["message_id"],
            "message_id": message["message_id"],
            "parent_message_id": message.get("parent_message_id"),
            "source": message["source"],
            "target": message["target"],
            "source_sequence": message["sequence"],
            "command_type": message["type"],
            "value": deepcopy(message["payload"]["value"]),
            "unit": message["payload"]["unit"],
            "source_event_time_s": float(message["event_time_s"]),
            "receive_time_s": receive_time_s,
            "command_age_s": receive_time_s - float(message["event_time_s"]),
            "gateway_accepted_time_s": receive_time_s,
            "opender_settings": settings,
            "opender_inputs": inputs,
        }
        heapq.heappush(
            self._pending,
            (due_time_s, self._actuation_sequence, action),
        )
        self._accepted_sequence[stream] = message["sequence"]
        result = {
            "gateway_decision": "accepted",
            "reason": "operate_accepted",
            "lifecycle_stage": "gateway_accepted",
            "acceptance_scope": (
                "gateway_validation_and_queue_acceptance_not_device_application"
            ),
            "message_id": message["message_id"],
            "receive_time_s": receive_time_s,
            "due_time_s": due_time_s,
            "actuation_sequence": self._actuation_sequence,
            "opender_settings": deepcopy(settings),
            "opender_inputs": deepcopy(inputs),
        }
        self._event("command_accepted", receive_time_s, result)
        return result

    def _validate_message(
        self, message: Any, receive_time_s: float
    ) -> str | None:
        if not isinstance(message, dict):
            return "schema_not_object"
        fields = set(message)
        if not _REQUIRED_TOP_LEVEL_FIELDS <= fields:
            return "schema_missing_field"
        if fields - _TOP_LEVEL_FIELDS:
            return "schema_unknown_field"
        if message["schema_version"] != "0.1":
            return "unsupported_schema_version"
        if message["kind"] != "command":
            return "unsupported_kind"
        for field, maximum in (
            ("message_id", 160),
            ("source", 120),
            ("target", 120),
            ("type", 120),
        ):
            value = message[field]
            if not isinstance(value, str) or not value or len(value) > maximum:
                return f"invalid_{field}"
        parent = message.get("parent_message_id")
        if parent is not None and (
            not isinstance(parent, str) or not parent or len(parent) > 160
        ):
            return "invalid_parent_message_id"
        if not _is_finite_number(message["event_time_s"]):
            return "invalid_event_time"
        if message["event_time_s"] < 0:
            return "invalid_event_time"
        if (
            not isinstance(message["sequence"], int)
            or isinstance(message["sequence"], bool)
            or message["sequence"] < 0
        ):
            return "invalid_sequence"

        payload = message["payload"]
        if not isinstance(payload, dict):
            return "invalid_payload"
        payload_fields = set(payload)
        if not _REQUIRED_PAYLOAD_FIELDS <= payload_fields:
            return "schema_missing_payload_field"
        if payload_fields - _PAYLOAD_FIELDS:
            return "schema_unknown_payload_field"
        if not isinstance(payload["unit"], str) or len(payload["unit"]) > 32:
            return "invalid_unit"
        if "valid_until_s" in payload and (
            not _is_finite_number(payload["valid_until_s"])
            or payload["valid_until_s"] < 0
        ):
            return "invalid_valid_until"
        if "quality" in payload:
            quality = payload["quality"]
            if (
                not isinstance(quality, list)
                or any(not isinstance(item, str) for item in quality)
                or len(quality) != len(set(quality))
                or any(item not in _QUALITY_VALUES for item in quality)
            ):
                return "invalid_quality"
            if any(item in _BAD_COMMAND_QUALITY for item in quality):
                return "bad_command_quality"

        if message["target"] != self.point_map["device_id"]:
            return "wrong_target"
        spec = self.point_map["commands"].get(message["type"])
        if spec is None:
            return "unknown_command"
        if not spec["enabled"]:
            return "disabled_command"
        allowed = self.point_map["authority"].get(message["source"], [])
        if message["type"] not in allowed:
            return "unauthorized_source"

        expected_unit = spec["unit"]
        if payload["unit"] != expected_unit:
            return "unit_mismatch"
        value = payload["value"]
        value_type = spec["value_type"]
        if value_type == "boolean":
            if not isinstance(value, bool):
                return "value_type_mismatch"
        elif value_type == "number":
            if not _is_finite_number(value):
                return "value_type_mismatch"
            if value < spec["minimum"] or value > spec["maximum"]:
                return "value_out_of_range"
        elif value_type == "enum":
            if not isinstance(value, str) or value not in spec["values"]:
                return "value_not_in_enum"
        else:
            return "unsupported_value_type"

        freshness = self.point_map["freshness"]
        age_s = receive_time_s - float(message["event_time_s"])
        if age_s > float(freshness["maximum_age_s"]):
            return "stale_command"
        if age_s < -float(freshness["maximum_future_skew_s"]):
            return "future_command"
        if (
            "valid_until_s" in payload
            and receive_time_s > float(payload["valid_until_s"])
        ):
            return "expired_command"
        return None

    @staticmethod
    def _map_to_opender(
        spec: Mapping[str, Any], value: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        mapping = spec["opender_mapping"]
        if mapping == "active_power_demand":
            return {}, {"demand_kw": float(value)}
        if mapping == "active_power_limit":
            return (
                {"AP_LIMIT_ENABLE": "ENABLED", "AP_LIMIT": float(value)},
                {},
            )
        if mapping == "reactive_setpoint":
            reactive_value = float(value)
            return (
                {
                    "QV_MODE_ENABLE": "DISABLED",
                    "QP_MODE_ENABLE": "DISABLED",
                    "CONST_PF_MODE_ENABLE": "DISABLED",
                    "CONST_Q": reactive_value
                    * float(spec["opender_scale"]),
                    "CONST_Q_MODE_ENABLE": (
                        "DISABLED"
                        if reactive_value == 0.0
                        else "ENABLED"
                    ),
                },
                {},
            )
        if mapping == "reactive_mode":
            disabled = {
                "QV_MODE_ENABLE": "DISABLED",
                "QP_MODE_ENABLE": "DISABLED",
                "CONST_PF_MODE_ENABLE": "DISABLED",
            }
            if value == "disabled":
                return (
                    {**disabled, "CONST_Q_MODE_ENABLE": "DISABLED"},
                    {},
                )
            if value == "constant_q":
                return (
                    {**disabled, "CONST_Q_MODE_ENABLE": "ENABLED"},
                    {},
                )
        raise GatewayConfigurationError(f"unknown OpenDER mapping {mapping}")

    @staticmethod
    def _fingerprint(message: Mapping[str, Any]) -> str:
        canonical = json.dumps(
            message,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _reject(
        self,
        message: Any,
        operation: Any,
        receive_time_s: Any,
        reason: str,
    ) -> dict[str, Any]:
        message_id = (
            message.get("message_id")
            if isinstance(message, dict)
            and isinstance(message.get("message_id"), str)
            else None
        )
        result = {
            "gateway_decision": "rejected",
            "reason": reason,
            "message_id": message_id,
            "operation": operation,
            "receive_time_s": (
                receive_time_s if _is_finite_number(receive_time_s) else None
            ),
        }
        event_time = (
            float(receive_time_s)
            if _is_finite_number(receive_time_s)
            else self.time_s
        )
        self._event("command_rejected", event_time, result)
        return result

    def _event(
        self, event_type: str, simulation_time_s: float, details: Mapping[str, Any]
    ) -> None:
        self._event_sequence += 1
        record = {
            "event_sequence": self._event_sequence,
            "event_type": event_type,
            "simulation_time_s": simulation_time_s,
            "details": deepcopy(dict(details)),
        }
        if self.event_log_path is None:
            return
        encoded = json.dumps(
            record,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
