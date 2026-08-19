from __future__ import annotations

import json
import math

import pytest

from v3.cyber_gateway import CyberGateway
from v3.natig_adapter.gateway_bridge import Dnp3GatewayBridge
from v3.natig_adapter.overlay_protocol import (
    OUTSTATION_SCHEMA,
    OverlayProtocolError,
    build_telemetry_frame,
    parse_outstation_event,
    process_outstation_event,
)


def event(**changes):
    value = {
        "schema_version": OUTSTATION_SCHEMA,
        "group": 41,
        "variation": 1,
        "operation": "select",
        "master_address": 1,
        "outstation_address": 4,
        "point_index": 0,
        "raw_count": -10_000,
        "status": 0,
    }
    value.update(changes)
    return json.dumps(value, separators=(",", ":"))


def test_cpp_overlay_event_select_operate_reaches_gateway_exactly_once():
    gateway = CyberGateway()
    bridge = Dnp3GatewayBridge(gateway)
    selected = process_outstation_event(
        bridge, event(), receive_time_s=10.0
    )
    operated = process_outstation_event(
        bridge,
        event(operation="operate"),
        receive_time_s=10.1,
    )
    assert selected["adapter_decision"] == "selected"
    assert operated["adapter_decision"] == "accepted"
    assert operated["semantic_message"]["payload"]["value"] == -10.0
    assert gateway.pending_count() == 1


@pytest.mark.parametrize(
    "change",
    [
        {"group": 40},
        {"variation": 2},
        {"operation": "direct_operate"},
        {"point_index": 2},
        {"point_index": 118},
        {"status": 95},
        {"master_address": 9},
        {"outstation_address": 9},
        {"raw_count": True},
        {"extra": "field"},
    ],
)
def test_hostile_overlay_shapes_cannot_remap_or_expand_authority(change):
    gateway = CyberGateway()
    bridge = Dnp3GatewayBridge(gateway)
    result = process_outstation_event(
        bridge, event(**change), receive_time_s=10.0
    )
    assert result["adapter_decision"] == "rejected"
    assert gateway.pending_count() == 0


def test_wrong_bound_station_is_rejected_by_bridge_not_reinterpreted():
    gateway = CyberGateway()
    bridge = Dnp3GatewayBridge(gateway)
    result = process_outstation_event(
        bridge, event(master_address=2), receive_time_s=10.0
    )
    assert result["reason"] == "wrong_master_address"
    assert gateway.pending_count() == 0


def test_operate_must_match_selected_raw_count_and_point():
    gateway = CyberGateway()
    bridge = Dnp3GatewayBridge(gateway)
    process_outstation_event(bridge, event(), receive_time_s=10.0)
    mismatch = process_outstation_event(
        bridge,
        event(operation="operate", raw_count=-9_999),
        receive_time_s=10.1,
    )
    assert mismatch["reason"] == "adapter_select_mismatch"
    assert gateway.pending_count() == 0


def test_telemetry_frame_has_exact_four_analog_two_binary_order():
    frame = build_telemetry_frame(
        {
            "active_power_kw": -10.0,
            "reactive_power_kvar": 2.5,
            "terminal_voltage_pu": 1.01,
            "state_of_charge_pu": 0.6,
        },
        {"connected": True, "command_accepted": False},
    )
    assert json.loads(frame) == {
        "schema_version": "grideval-g4-telemetry-0.1",
        "target": "DER_EV4_BESS",
        "analog": [-10.0, 2.5, 1.01, 0.6],
        "binary": [True, False],
    }


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True])
def test_telemetry_rejects_nonfinite_or_boolean_analog(bad):
    with pytest.raises(OverlayProtocolError):
        build_telemetry_frame(
            {
                "active_power_kw": bad,
                "reactive_power_kvar": 0.0,
                "terminal_voltage_pu": 1.0,
                "state_of_charge_pu": 0.5,
            },
            {"connected": True, "command_accepted": False},
        )


def test_parser_rejects_duplicate_json_keys():
    duplicate = event().replace('"status":0}', '"status":95,"status":0}')
    with pytest.raises(OverlayProtocolError, match="duplicate"):
        parse_outstation_event(duplicate)
