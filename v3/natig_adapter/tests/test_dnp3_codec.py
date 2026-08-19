from __future__ import annotations

import math
import struct
from copy import deepcopy

import pytest

from v3.cyber_gateway import load_point_map
from v3.natig_adapter.dnp3_codec import (
    Dnp3CodecError,
    decode_group1v2,
    decode_group30v5,
    decode_group41v1,
    encode_group1v2,
    encode_group30v5,
    encode_group41v1,
)


@pytest.mark.parametrize("point_index", [0, 1])
@pytest.mark.parametrize("value", [False, True])
def test_g1v2_binary_roundtrip(point_index, value):
    body = encode_group1v2(
        point_index=point_index,
        value=value,
        flags=0x01,
    )
    assert body == bytes([0x81 if value else 0x01])
    decoded = decode_group1v2(body, point_index=point_index)
    assert decoded.point_index == point_index
    assert decoded.telemetry_type == (
        "connected" if point_index == 0 else "command_accepted"
    )
    assert decoded.flags == 0x01
    assert decoded.value is value
    assert decoded.unit == "boolean"


def test_g1v2_rejects_nonminimal_points_shapes_and_types():
    with pytest.raises(Dnp3CodecError, match="not readable"):
        encode_group1v2(point_index=2, value=True)
    with pytest.raises(Dnp3CodecError, match="boolean"):
        encode_group1v2(point_index=0, value=1)
    with pytest.raises(Dnp3CodecError, match=r"\[0, 127\]"):
        encode_group1v2(point_index=0, value=True, flags=0x80)
    with pytest.raises(Dnp3CodecError, match="exactly 1 byte"):
        decode_group1v2(b"", point_index=0)


@pytest.mark.parametrize("point_index", [0, 1])
@pytest.mark.parametrize("value", [-10.0, 10.0])
def test_g41v1_signed_pq_pulses_roundtrip(point_index, value):
    payload = encode_group41v1(point_index=point_index, value=value)
    expected_count = -10_000 if value < 0 else 10_000
    assert payload == struct.pack("<iB", expected_count, 0)
    decoded = decode_group41v1(payload, point_index=point_index)
    assert decoded.point_index == point_index
    assert decoded.raw_count == expected_count
    assert decoded.value == value
    assert decoded.unit == ("kW" if point_index == 0 else "kvar")


def test_g41v1_little_endian_negative_count_is_explicit():
    assert encode_group41v1(point_index=0, value=-10.0) == bytes.fromhex(
        "f0d8ffff00"
    )


@pytest.mark.parametrize(
    ("point_index", "value"),
    [(0, -200.001), (0, 200.001), (1, -88.001), (1, 88.001)],
)
def test_g41v1_rejects_engineering_range(point_index, value):
    with pytest.raises(Dnp3CodecError, match="outside point range"):
        encode_group41v1(point_index=point_index, value=value)


@pytest.mark.parametrize("point_index", [-1, 2, 3, 60, 118, True])
def test_g41v1_rejects_every_non_allowlisted_output_index(point_index):
    with pytest.raises(Dnp3CodecError):
        decode_group41v1(
            struct.pack("<iB", 10_000, 0), point_index=point_index
        )


def test_stock_status_95_index_remap_defect_is_reproduced_then_rejected():
    point_index = 2
    stock_status = 95
    assert stock_status == 95 and point_index - 2 == 0
    hostile_body = struct.pack("<iB", 10_000, stock_status)

    with pytest.raises(Dnp3CodecError, match="not writable"):
        decode_group41v1(hostile_body, point_index=point_index)
    with pytest.raises(Dnp3CodecError, match="status must be 0"):
        decode_group41v1(hostile_body, point_index=0)


def test_status_cannot_select_or_remap_a_point():
    with pytest.raises(Dnp3CodecError, match="status must be 0"):
        encode_group41v1(point_index=0, value=10.0, status=95)
    with pytest.raises(Dnp3CodecError, match="status must be 0"):
        decode_group41v1(
            struct.pack("<iB", 10_000, 1), point_index=0
        )


@pytest.mark.parametrize(
    ("point_index", "value", "unit"),
    [
        (0, -123.25, "kW"),
        (1, 44.125, "kvar"),
        (2, 1.0125, "pu"),
        (3, 0.625, "pu"),
    ],
)
def test_g30v5_float32_roundtrip(point_index, value, unit):
    payload = encode_group30v5(
        point_index=point_index, value=value, flags=0x01
    )
    assert payload == struct.pack("<Bf", 0x01, value)
    decoded = decode_group30v5(payload, point_index=point_index)
    assert decoded.flags == 0x01
    assert decoded.value == pytest.approx(value, abs=1e-6)
    assert decoded.unit == unit
    assert decoded.telemetry_type == (
        "active_power",
        "reactive_power",
        "terminal_voltage",
        "state_of_charge",
    )[point_index]


def test_g30v5_little_endian_layout_is_flags_then_float():
    assert encode_group30v5(point_index=0, value=10.0) == bytes.fromhex(
        "0100002041"
    )


@pytest.mark.parametrize("point_index", [-1, 4, 100, True])
def test_g30v5_rejects_unknown_input_index(point_index):
    with pytest.raises(Dnp3CodecError):
        decode_group30v5(
            struct.pack("<Bf", 1, 0.5), point_index=point_index
        )


@pytest.mark.parametrize(
    "payload",
    [b"", b"\x00" * 4, b"\x00" * 6],
)
def test_object_bodies_require_exact_length(payload):
    with pytest.raises(Dnp3CodecError, match="exactly 5 bytes"):
        decode_group41v1(payload, point_index=0)
    with pytest.raises(Dnp3CodecError, match="exactly 5 bytes"):
        decode_group30v5(payload, point_index=0)


@pytest.mark.parametrize("bad_value", [True, math.nan, math.inf, -math.inf])
def test_nonfinite_and_boolean_values_are_rejected(bad_value):
    with pytest.raises(Dnp3CodecError):
        encode_group41v1(point_index=0, value=bad_value)
    with pytest.raises(Dnp3CodecError):
        encode_group30v5(point_index=0, value=bad_value)


def test_nonfinite_float32_payload_is_rejected():
    with pytest.raises(Dnp3CodecError, match="finite"):
        decode_group30v5(struct.pack("<Bf", 1, math.nan), point_index=0)


def test_codec_rejects_mutated_point_map_instead_of_using_a_second_table():
    point_map = deepcopy(load_point_map())
    point_map["telemetry"]["active_power"]["index"] = 3
    with pytest.raises(Dnp3CodecError, match="invalid G4 point map"):
        encode_group30v5(
            point_index=0,
            value=10.0,
            point_map=point_map,
        )
