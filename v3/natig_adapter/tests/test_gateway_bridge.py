from __future__ import annotations

from v3.cyber_gateway import CyberGateway
from v3.natig_adapter.dnp3_codec import encode_group41v1
from v3.natig_adapter.gateway_bridge import AdapterBinding, Dnp3GatewayBridge


def bridge_and_gateway():
    gateway = CyberGateway()
    return Dnp3GatewayBridge(gateway), gateway


def process(
    bridge,
    payload,
    *,
    point_index=0,
    operation="select",
    receive_time_s=10.0,
    master_address=1,
    outstation_address=4,
):
    return bridge.process_group41v1(
        payload,
        point_index=point_index,
        operation=operation,
        receive_time_s=receive_time_s,
        master_address=master_address,
        outstation_address=outstation_address,
    )


def test_exact_select_operate_reconstructs_one_semantic_transaction():
    bridge, gateway = bridge_and_gateway()
    body = encode_group41v1(point_index=0, value=-10.0)
    selected = process(bridge, body)
    operated = process(
        bridge, body, operation="operate", receive_time_s=10.1
    )
    assert selected["adapter_decision"] == "selected"
    assert operated["adapter_decision"] == "accepted"
    assert selected["semantic_message"] == operated["semantic_message"]
    message = operated["semantic_message"]
    assert message["message_id"].startswith("dnp3-o4-t00000001-ao0-")
    assert message["event_time_s"] == 10.0
    assert message["sequence"] == 1
    assert message["payload"] == {
        "value": -10.0,
        "unit": "kW",
        "valid_until_s": 15.0,
        "quality": ["online"],
    }
    assert gateway.pending_count() == 1


def test_q_point_maps_through_codec_and_gateway():
    bridge, gateway = bridge_and_gateway()
    body = encode_group41v1(point_index=1, value=10.0)
    process(bridge, body, point_index=1)
    operated = process(
        bridge,
        body,
        point_index=1,
        operation="operate",
        receive_time_s=10.1,
    )
    assert operated["gateway_result"]["opender_settings"]["CONST_Q"] == 0.05
    assert gateway.pending_count() == 1


def test_binding_rejects_wrong_master_and_outstation():
    bridge, _ = bridge_and_gateway()
    body = encode_group41v1(point_index=0, value=10.0)
    assert process(bridge, body, master_address=9)["reason"] == (
        "wrong_master_address"
    )
    assert process(bridge, body, outstation_address=9)["reason"] == (
        "wrong_outstation_address"
    )


def test_operate_requires_adapter_select():
    bridge, gateway = bridge_and_gateway()
    body = encode_group41v1(point_index=0, value=10.0)
    result = process(bridge, body, operation="operate")
    assert result["reason"] == "adapter_select_required"
    assert gateway.pending_count() == 0


def test_operate_must_match_exact_selected_object_body():
    bridge, gateway = bridge_and_gateway()
    selected = encode_group41v1(point_index=0, value=10.0)
    modified = encode_group41v1(point_index=0, value=11.0)
    process(bridge, selected)
    result = process(
        bridge, modified, operation="operate", receive_time_s=10.1
    )
    assert result["reason"] == "adapter_select_mismatch"
    assert gateway.pending_count() == 0


def test_operate_consumes_selection_even_when_gateway_rejects_expiry():
    bridge, gateway = bridge_and_gateway()
    body = encode_group41v1(point_index=0, value=10.0)
    process(bridge, body)
    result = process(
        bridge, body, operation="operate", receive_time_s=15.1
    )
    assert result["reason"] == "gateway_rejected_operate"
    assert result["gateway_result"]["reason"] == "expired_command"
    replay = process(
        bridge, body, operation="operate", receive_time_s=15.2
    )
    assert replay["reason"] == "adapter_select_required"
    assert gateway.pending_count() == 0


def test_new_select_replaces_prior_select_for_same_point():
    bridge, _ = bridge_and_gateway()
    first = encode_group41v1(point_index=0, value=10.0)
    second = encode_group41v1(point_index=0, value=20.0)
    process(bridge, first)
    selected = process(bridge, second, receive_time_s=10.1)
    assert selected["transaction_sequence"] == 2
    stale_operate = process(
        bridge, first, operation="operate", receive_time_s=10.2
    )
    assert stale_operate["reason"] == "adapter_select_mismatch"


def test_transaction_identity_is_deterministic_for_same_trace():
    body = encode_group41v1(point_index=0, value=-10.0)
    messages = []
    for _ in range(2):
        bridge, _gateway = bridge_and_gateway()
        messages.append(process(bridge, body)["semantic_message"])
    assert messages[0] == messages[1]


def test_malformed_and_unsupported_objects_fail_before_gateway():
    bridge, gateway = bridge_and_gateway()
    assert process(bridge, b"\x00")["reason"] == "invalid_dnp3_object"
    valid = encode_group41v1(point_index=0, value=10.0)
    assert process(bridge, valid, point_index=2)["reason"] == (
        "invalid_dnp3_object"
    )
    assert process(bridge, valid, operation="direct_operate")["reason"] == (
        "unsupported_operation"
    )
    assert gateway.pending_count() == 0


def test_custom_binding_cannot_bypass_frozen_gateway_authority():
    gateway = CyberGateway()
    bridge = Dnp3GatewayBridge(
        gateway,
        binding=AdapterBinding(
            master_address=7,
            outstation_address=4,
            source="trusted_master",
            target="DER_EV4_BESS",
        ),
    )
    body = encode_group41v1(point_index=0, value=10.0)
    selected = process(bridge, body, master_address=7)
    assert selected["reason"] == "gateway_rejected_select"
    assert selected["gateway_result"]["reason"] == "unauthorized_source"
