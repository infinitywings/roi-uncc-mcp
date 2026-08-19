"""Strict JSON seam between the patched NATIG outstation and Python gateway."""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Mapping
from typing import Any

from v3.natig_adapter.gateway_bridge import Dnp3GatewayBridge


OUTSTATION_SCHEMA = "grideval-g4-dnp3-object-0.1"
TELEMETRY_SCHEMA = "grideval-g4-telemetry-0.1"
_OUTSTATION_KEYS = {
    "schema_version",
    "group",
    "variation",
    "operation",
    "master_address",
    "outstation_address",
    "point_index",
    "raw_count",
    "status",
}
_ANALOG_KEYS = (
    "active_power_kw",
    "reactive_power_kvar",
    "terminal_voltage_pu",
    "state_of_charge_pu",
)
_BINARY_KEYS = ("connected", "command_accepted")


class OverlayProtocolError(ValueError):
    """An overlay event does not match the frozen wire seam."""


def _strict_json(payload: str | bytes | bytearray) -> dict[str, Any]:
    def reject_duplicate_keys(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OverlayProtocolError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        parsed = json.loads(payload, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise OverlayProtocolError("payload must be one valid JSON object") from exc
    if not isinstance(parsed, dict):
        raise OverlayProtocolError("payload must be a JSON object")
    return parsed


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise OverlayProtocolError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise OverlayProtocolError(f"{label} is outside its frozen range")
    return value


def parse_outstation_event(
    payload: str | bytes | bytearray,
) -> dict[str, Any]:
    """Parse the exact opaque event emitted by the C++ overlay."""

    event = _strict_json(payload)
    if set(event) != _OUTSTATION_KEYS:
        raise OverlayProtocolError("outstation event fields do not match schema")
    if event["schema_version"] != OUTSTATION_SCHEMA:
        raise OverlayProtocolError("unsupported outstation schema")
    if event["group"] != 41 or event["variation"] != 1:
        raise OverlayProtocolError("only G41V1 is accepted")
    if event["operation"] not in {"select", "operate"}:
        raise OverlayProtocolError("only SELECT or OPERATE is accepted")
    _integer(event["master_address"], "master_address", 0, 65519)
    _integer(event["outstation_address"], "outstation_address", 0, 65519)
    _integer(event["point_index"], "point_index", 0, 1)
    _integer(event["raw_count"], "raw_count", -(2**31), 2**31 - 1)
    if _integer(event["status"], "status", 0, 255) != 0:
        raise OverlayProtocolError("G41V1 request status must be zero")
    return event


def process_outstation_event(
    bridge: Dnp3GatewayBridge,
    payload: str | bytes | bytearray,
    *,
    receive_time_s: float,
) -> dict[str, Any]:
    """Pass one validated C++ overlay event into the semantic bridge."""

    try:
        event = parse_outstation_event(payload)
    except OverlayProtocolError as exc:
        return {
            "adapter_decision": "rejected",
            "reason": "invalid_overlay_event",
            "detail": str(exc),
        }
    body = struct.pack("<iB", event["raw_count"], event["status"])
    return bridge.process_group41v1(
        body,
        point_index=event["point_index"],
        operation=event["operation"],
        receive_time_s=receive_time_s,
        master_address=event["master_address"],
        outstation_address=event["outstation_address"],
    )


def build_telemetry_frame(
    analog: Mapping[str, Any],
    binary: Mapping[str, Any],
) -> str:
    """Build the only telemetry JSON shape accepted by the C++ overlay."""

    if set(analog) != set(_ANALOG_KEYS) or set(binary) != set(_BINARY_KEYS):
        raise OverlayProtocolError("telemetry fields do not match frozen map")
    analog_values: list[float] = []
    for name in _ANALOG_KEYS:
        value = analog[name]
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise OverlayProtocolError(f"{name} must be finite")
        analog_values.append(float(value))
    binary_values: list[bool] = []
    for name in _BINARY_KEYS:
        value = binary[name]
        if not isinstance(value, bool):
            raise OverlayProtocolError(f"{name} must be Boolean")
        binary_values.append(value)
    return json.dumps(
        {
            "schema_version": TELEMETRY_SCHEMA,
            "target": "DER_EV4_BESS",
            "analog": analog_values,
            "binary": binary_values,
        },
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
