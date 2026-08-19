"""Byte codec for the GridEval-owned G4 NATIG adapter.

This is intentionally an object-body codec, not a complete DNP3 stack.
Object headers and index prefixes remain the responsibility of the pinned
NATIG DNP3 implementation. The byte order is frozen to little-endian to match
``appendINT32`` and the x86 ``appendFloat`` helper in the pinned checkout.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from v3.cyber_gateway import (
    DEFAULT_POINT_MAP,
    GatewayConfigurationError,
    load_point_map,
)
from v3.cyber_gateway.gateway import _validate_point_map


GROUP41V1_SIZE = 5
GROUP30V5_SIZE = 5
GROUP1V2_SIZE = 1
COMMAND_STATUS_ACCEPTED = 0
ONLINE_FLAG = 0x01
_BINARY_VALUE_FLAG = 0x80
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1
_G4_COMMAND_NAMES = {"active_power_setpoint", "reactive_setpoint"}
_G4_TELEMETRY_NAMES = {
    "active_power",
    "reactive_power",
    "terminal_voltage",
    "state_of_charge",
}
_G4_BINARY_NAMES = {"connected", "command_accepted"}


class Dnp3CodecError(ValueError):
    """The object body or its declared point metadata is invalid."""


@dataclass(frozen=True)
class Group41v1Command:
    point_index: int
    command_type: str
    raw_count: int
    status: int
    value: float
    unit: str


@dataclass(frozen=True)
class Group30v5Value:
    point_index: int
    telemetry_type: str
    flags: int
    value: float
    unit: str


@dataclass(frozen=True)
class Group1v2Value:
    point_index: int
    telemetry_type: str
    flags: int
    value: bool
    unit: str


def _point_map(
    point_map: Mapping[str, Any] | None,
    point_map_path: str | Path,
) -> dict[str, Any]:
    try:
        loaded = (
            load_point_map(point_map_path)
            if point_map is None
            else dict(point_map)
        )
        _validate_point_map(loaded)
    except GatewayConfigurationError as exc:
        raise Dnp3CodecError(f"invalid G4 point map: {exc}") from exc
    return loaded


def _finite_number(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise Dnp3CodecError(f"{label} must be a finite number")
    return float(value)


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise Dnp3CodecError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise Dnp3CodecError(
            f"{label} must be in [{minimum}, {maximum}]"
        )
    return value


def _command_spec(
    point_index: Any, point_map: Mapping[str, Any]
) -> tuple[str, Mapping[str, Any]]:
    index = _integer(point_index, "point_index", 0, 65535)
    matches = [
        (name, spec)
        for name, spec in point_map["commands"].items()
        if spec.get("enabled")
        and spec.get("dnp3_group") == "analog_output"
        and spec.get("index") == index
        and name in _G4_COMMAND_NAMES
    ]
    if len(matches) != 1:
        raise Dnp3CodecError(
            f"AO{index} is not writable in the G4 adapter"
        )
    return matches[0]


def encode_group41v1(
    *,
    point_index: int,
    value: float,
    status: int = COMMAND_STATUS_ACCEPTED,
    point_map: Mapping[str, Any] | None = None,
    point_map_path: str | Path = DEFAULT_POINT_MAP,
) -> bytes:
    """Encode a G41V1 signed-int32 command object body.

    The command request status must be zero. Nonzero values belong to DNP3
    response processing and never imply gateway acceptance.
    """

    status_value = _integer(status, "status", 0, 255)
    if status_value != COMMAND_STATUS_ACCEPTED:
        raise Dnp3CodecError("G41V1 command request status must be 0")
    loaded = _point_map(point_map, point_map_path)
    _, spec = _command_spec(point_index, loaded)
    engineering_value = _finite_number(value, "value")
    if engineering_value < spec["minimum"] or engineering_value > spec["maximum"]:
        raise Dnp3CodecError("engineering value is outside point range")
    scale = _finite_number(spec.get("raw_scale"), "raw_scale")
    if scale <= 0:
        raise Dnp3CodecError("raw_scale must be positive")
    raw_count = int(round(engineering_value / scale))
    reconstructed = raw_count * scale
    if not math.isclose(
        reconstructed, engineering_value, rel_tol=0.0, abs_tol=scale / 2
    ):
        raise Dnp3CodecError("engineering value is not representable")
    raw_minimum = _integer(
        spec["raw_minimum"], "raw_minimum", _INT32_MIN, _INT32_MAX
    )
    raw_maximum = _integer(
        spec["raw_maximum"], "raw_maximum", _INT32_MIN, _INT32_MAX
    )
    if raw_count < raw_minimum or raw_count > raw_maximum:
        raise Dnp3CodecError("raw count is outside point range")
    return struct.pack("<iB", raw_count, status_value)


def decode_group41v1(
    payload: bytes | bytearray | memoryview,
    *,
    point_index: int,
    point_map: Mapping[str, Any] | None = None,
    point_map_path: str | Path = DEFAULT_POINT_MAP,
) -> Group41v1Command:
    """Decode and validate one G41V1 object body for AO0 or AO1."""

    body = bytes(payload)
    if len(body) != GROUP41V1_SIZE:
        raise Dnp3CodecError("G41V1 object body must be exactly 5 bytes")
    loaded = _point_map(point_map, point_map_path)
    command_type, spec = _command_spec(point_index, loaded)
    raw_count, status = struct.unpack("<iB", body)
    if status != COMMAND_STATUS_ACCEPTED:
        raise Dnp3CodecError("G41V1 command request status must be 0")
    if raw_count < spec["raw_minimum"] or raw_count > spec["raw_maximum"]:
        raise Dnp3CodecError("raw count is outside point range")
    value = raw_count * float(spec["raw_scale"])
    if value < spec["minimum"] or value > spec["maximum"]:
        raise Dnp3CodecError("engineering value is outside point range")
    return Group41v1Command(
        point_index=point_index,
        command_type=command_type,
        raw_count=raw_count,
        status=status,
        value=value,
        unit=spec["unit"],
    )


def _telemetry_spec(
    point_index: Any,
    point_map: Mapping[str, Any],
) -> tuple[int, str, str, float, float]:
    index = _integer(point_index, "point_index", 0, 65535)
    matches = [
        (name, spec)
        for name, spec in point_map["telemetry"].items()
        if name in _G4_TELEMETRY_NAMES
        and spec.get("dnp3_group") == "analog_input"
        and spec.get("dnp3_object") == "G30V5"
        and spec.get("index") == index
    ]
    if len(matches) != 1:
        raise Dnp3CodecError(
            f"AI{index} is not readable in the G4 adapter"
        )
    name, spec = matches[0]
    return (
        index,
        name,
        spec["unit"],
        float(spec["minimum"]),
        float(spec["maximum"]),
    )


def encode_group30v5(
    *,
    point_index: int,
    value: float,
    flags: int = ONLINE_FLAG,
    point_map: Mapping[str, Any] | None = None,
    point_map_path: str | Path = DEFAULT_POINT_MAP,
) -> bytes:
    """Encode a G30V5 flags-plus-float32 object body."""

    loaded = _point_map(point_map, point_map_path)
    _, _, _, minimum, maximum = _telemetry_spec(point_index, loaded)
    engineering_value = _finite_number(value, "value")
    if engineering_value < minimum or engineering_value > maximum:
        raise Dnp3CodecError("telemetry value is outside point range")
    flag_value = _integer(flags, "flags", 0, 255)
    try:
        return struct.pack("<Bf", flag_value, engineering_value)
    except (OverflowError, struct.error) as exc:
        raise Dnp3CodecError("telemetry value is not float32") from exc


def decode_group30v5(
    payload: bytes | bytearray | memoryview,
    *,
    point_index: int,
    point_map: Mapping[str, Any] | None = None,
    point_map_path: str | Path = DEFAULT_POINT_MAP,
) -> Group30v5Value:
    """Decode and validate one G30V5 flags-plus-float32 object body."""

    body = bytes(payload)
    if len(body) != GROUP30V5_SIZE:
        raise Dnp3CodecError("G30V5 object body must be exactly 5 bytes")
    loaded = _point_map(point_map, point_map_path)
    index, name, unit, minimum, maximum = _telemetry_spec(point_index, loaded)
    flags, value = struct.unpack("<Bf", body)
    if not math.isfinite(value):
        raise Dnp3CodecError("telemetry value must be finite")
    if value < minimum or value > maximum:
        raise Dnp3CodecError("telemetry value is outside point range")
    return Group30v5Value(
        point_index=index,
        telemetry_type=name,
        flags=flags,
        value=value,
        unit=unit,
    )


def _binary_spec(
    point_index: Any,
    point_map: Mapping[str, Any],
) -> tuple[int, str, str]:
    index = _integer(point_index, "point_index", 0, 65535)
    matches = [
        (name, spec)
        for name, spec in point_map["telemetry"].items()
        if name in _G4_BINARY_NAMES
        and spec.get("dnp3_group") == "binary_input"
        and spec.get("dnp3_object") == "G1V2"
        and spec.get("index") == index
    ]
    if len(matches) != 1:
        raise Dnp3CodecError(
            f"BI{index} is not readable in the G4 adapter"
        )
    name, spec = matches[0]
    return index, name, spec["unit"]


def encode_group1v2(
    *,
    point_index: int,
    value: bool,
    flags: int = ONLINE_FLAG,
    point_map: Mapping[str, Any] | None = None,
    point_map_path: str | Path = DEFAULT_POINT_MAP,
) -> bytes:
    """Encode G1V2 value bit 7 plus status flags in bits 0 through 6."""

    loaded = _point_map(point_map, point_map_path)
    _binary_spec(point_index, loaded)
    if not isinstance(value, bool):
        raise Dnp3CodecError("value must be boolean")
    flag_value = _integer(flags, "flags", 0, 0x7F)
    return bytes([flag_value | (_BINARY_VALUE_FLAG if value else 0)])


def decode_group1v2(
    payload: bytes | bytearray | memoryview,
    *,
    point_index: int,
    point_map: Mapping[str, Any] | None = None,
    point_map_path: str | Path = DEFAULT_POINT_MAP,
) -> Group1v2Value:
    """Decode one stock-NATIG-compatible G1V2 binary object body."""

    body = bytes(payload)
    if len(body) != GROUP1V2_SIZE:
        raise Dnp3CodecError("G1V2 object body must be exactly 1 byte")
    loaded = _point_map(point_map, point_map_path)
    index, name, unit = _binary_spec(point_index, loaded)
    encoded = body[0]
    return Group1v2Value(
        point_index=index,
        telemetry_type=name,
        flags=encoded & 0x7F,
        value=bool(encoded & _BINARY_VALUE_FLAG),
        unit=unit,
    )
