from __future__ import annotations

import json
from copy import deepcopy

import pytest

from v3.cyber_gateway import (
    CyberGateway,
    GatewayConfigurationError,
    load_point_map,
    point_map_sha256,
)


def command(
    *,
    message_id: str = "cmd-1",
    sequence: int = 1,
    event_time_s: float = 10.0,
    source: str = "ev_controller_v3",
    target: str = "DER_EV4_BESS",
    command_type: str = "active_power_setpoint",
    value=10.0,
    unit: str = "kW",
    valid_until_s: float | None = 20.0,
    parent_message_id: str | None = None,
):
    message = {
        "schema_version": "0.1",
        "kind": "command",
        "message_id": message_id,
        "event_time_s": event_time_s,
        "source": source,
        "target": target,
        "sequence": sequence,
        "type": command_type,
        "payload": {"value": value, "unit": unit},
    }
    if valid_until_s is not None:
        message["payload"]["valid_until_s"] = valid_until_s
    if parent_message_id is not None:
        message["parent_message_id"] = parent_message_id
    return message


def sbo(gateway: CyberGateway, message, select_time=10.0, operate_time=10.1):
    selected = gateway.ingest(
        message, operation="select", receive_time_s=select_time
    )
    operated = gateway.ingest(
        message, operation="operate", receive_time_s=operate_time
    )
    return selected, operated


def test_frozen_point_map_is_loadable_and_has_unique_nonempty_digest():
    point_map = load_point_map()
    assert point_map["device_id"] == "DER_EV4_BESS"
    assert len(point_map_sha256()) == 64
    points = [
        (spec["dnp3_group"], spec["index"])
        for spec in point_map["commands"].values()
    ]
    assert len(points) == len(set(points))
    assert point_map["commands"]["active_power_setpoint"]["index"] == 0
    assert point_map["commands"]["active_power_setpoint"]["dnp3_object"] == "G41V1"
    assert point_map["commands"]["active_power_setpoint"]["raw_scale"] == 0.001
    assert point_map["commands"]["reactive_setpoint"]["index"] == 1
    assert point_map["commands"]["reactive_setpoint"]["dnp3_object"] == "G41V1"
    assert point_map["commands"]["reactive_setpoint"]["raw_scale"] == 0.001
    assert all(group != "binary_output" for group, _ in points)
    assert {
        name
        for name, spec in point_map["commands"].items()
        if spec["enabled"]
    } == {"active_power_setpoint", "reactive_setpoint"}
    assert point_map["authority"] == {
        "ev_controller_v3": [
            "active_power_setpoint",
            "reactive_setpoint",
        ]
    }
    assert [
        (
            name,
            spec["dnp3_group"],
            spec["index"],
            spec["dnp3_object"],
            spec["wire_type"],
            spec["unit"],
        )
        for name, spec in point_map["telemetry"].items()
    ] == [
        ("active_power", "analog_input", 0, "G30V5", "float32", "kW"),
        ("reactive_power", "analog_input", 1, "G30V5", "float32", "kvar"),
        ("terminal_voltage", "analog_input", 2, "G30V5", "float32", "pu"),
        ("state_of_charge", "analog_input", 3, "G30V5", "float32", "pu"),
        ("connected", "binary_input", 0, "G1V2", "boolean", "boolean"),
        (
            "command_accepted",
            "binary_input",
            1,
            "G1V2",
            "boolean",
            "boolean",
        ),
    ]
    assert point_map["telemetry"]["command_accepted"]["semantics"] == (
        "gateway_validation_and_queue_acceptance"
    )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (
            lambda m: m["commands"]["active_power_limit"].update(enabled=True),
            "active_power_limit must remain disabled",
        ),
        (
            lambda m: m["authority"]["ev_controller_v3"].append(
                "active_power_limit"
            ),
            "authority must match",
        ),
        (
            lambda m: m["commands"]["active_power_setpoint"].update(
                raw_scale=0.0001
            ),
            "raw_scale must match",
        ),
        (
            lambda m: m["commands"]["active_power_setpoint"].update(
                raw_maximum=2**31
            ),
            "raw_maximum must match",
        ),
        (
            lambda m: m["commands"]["reactive_setpoint"].update(
                dnp3_object="G41V2"
            ),
            "dnp3_object must match",
        ),
        (
            lambda m: m["commands"]["reactive_setpoint"].update(index=0),
            "duplicate DNP3 point",
        ),
        (
            lambda m: m["telemetry"]["reactive_power"].update(index=0),
            "telemetry must be",
        ),
        (
            lambda m: m["telemetry"]["active_power"].update(raw_scale=0.01),
            "telemetry fields must match",
        ),
        (
            lambda m: m["telemetry"]["active_power"].update(index=False),
            "index and range must be numeric",
        ),
        (
            lambda m: m["telemetry"]["connected"].update(
                wire_type="bit_field"
            ),
            "G1V2 boolean",
        ),
        (
            lambda m: m["telemetry"].pop("command_accepted"),
            "telemetry names must match",
        ),
        (
            lambda m: m["select_before_operate"].update(
                exact_value_match=False
            ),
            "exact-value match",
        ),
    ],
)
def test_point_map_contract_mutations_fail_closed(mutation, error):
    point_map = load_point_map()
    mutation(point_map)
    with pytest.raises(GatewayConfigurationError, match=error):
        CyberGateway(point_map=point_map)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda m: m.update(extra=True), "schema_unknown_field"),
        (lambda m: m.pop("target"), "schema_missing_field"),
        (
            lambda m: m["payload"].update(extra=True),
            "schema_unknown_payload_field",
        ),
        (lambda m: m.update(schema_version="9"), "unsupported_schema_version"),
        (lambda m: m.update(kind="telemetry"), "unsupported_kind"),
        (lambda m: m.update(sequence=True), "invalid_sequence"),
        (lambda m: m.update(event_time_s=float("inf")), "invalid_event_time"),
        (lambda m: m["payload"].update(value=True), "value_type_mismatch"),
        (lambda m: m["payload"].update(unit="percent"), "unit_mismatch"),
    ],
)
def test_strict_typed_schema_rejections(mutation, reason):
    gateway = CyberGateway()
    message = command()
    mutation(message)
    result = gateway.ingest(
        message, operation="select", receive_time_s=10.0
    )
    assert result["gateway_decision"] == "rejected"
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"source": "grideval_attacker_v3"}, "unauthorized_source"),
        ({"target": "DER_EV1_SECOND_STAGE"}, "wrong_target"),
        ({"value": 200.001}, "value_out_of_range"),
        ({"event_time_s": 0.0}, "stale_command"),
        ({"event_time_s": 10.1}, "future_command"),
    ],
)
def test_authority_target_range_and_freshness(changes, reason):
    gateway = CyberGateway()
    message_fields = {
        key: value
        for key, value in changes.items()
        if key not in {"value"}
    }
    message = command(**message_fields)
    if "value" in changes:
        message["payload"]["value"] = changes["value"]
    receive_time_s = 10.0001 if reason == "stale_command" else 10.0
    result = gateway.ingest(
        message, operation="select", receive_time_s=receive_time_s
    )
    assert result["reason"] == reason


def test_valid_until_and_disabled_command_are_rejected():
    gateway = CyberGateway()
    expired = command(valid_until_s=9.9)
    assert (
        gateway.ingest(expired, operation="select", receive_time_s=10.0)[
            "reason"
        ]
        == "expired_command"
    )
    disabled_commands = [
        command(
            message_id="limit",
            command_type="active_power_limit",
            value=0.5,
            unit="pu",
        ),
        command(
            message_id="mode",
            command_type="reactive_mode",
            value="constant_q",
            unit="enum",
        ),
        command(
            message_id="curve",
            command_type="autonomous_curve",
            value={"version": 1},
            unit="json",
        ),
    ]
    for disabled in disabled_commands:
        assert (
            gateway.ingest(
                disabled,
                operation="select",
                receive_time_s=10.0,
            )["reason"]
            == "disabled_command"
        )


@pytest.mark.parametrize(
    "quality",
    [["stale"], ["invalid"], ["communication_lost"], ["online", "stale"]],
)
def test_bad_command_quality_is_rejected(quality):
    gateway = CyberGateway()
    message = command()
    message["payload"]["quality"] = quality
    result = gateway.ingest(
        message, operation="select", receive_time_s=10.0
    )
    assert result["reason"] == "bad_command_quality"


def test_online_command_quality_is_accepted():
    gateway = CyberGateway()
    message = command()
    message["payload"]["quality"] = ["online"]
    assert (
        gateway.ingest(message, operation="select", receive_time_s=10.0)[
            "gateway_decision"
        ]
        == "selected"
    )


def test_sbo_requires_exact_unexpired_select_and_consumes_it():
    gateway = CyberGateway()
    message = command()
    no_select = gateway.ingest(
        message, operation="operate", receive_time_s=10.0
    )
    assert no_select["reason"] == "select_required"

    message = command(message_id="cmd-2", sequence=2)
    assert (
        gateway.ingest(message, operation="select", receive_time_s=10.0)[
            "gateway_decision"
        ]
        == "selected"
    )
    modified = deepcopy(message)
    modified["payload"]["value"] = 0.5
    mismatch = gateway.ingest(
        modified, operation="operate", receive_time_s=10.1
    )
    assert mismatch["reason"] == "message_id_collision"

    operated = gateway.ingest(
        message, operation="operate", receive_time_s=10.2
    )
    assert operated["gateway_decision"] == "accepted"
    replay = gateway.ingest(
        message, operation="operate", receive_time_s=10.3
    )
    assert replay["reason"] == "duplicate_operation"

    expiring = command(
        message_id="cmd-3",
        sequence=3,
        event_time_s=20.0,
        valid_until_s=30.0,
    )
    gateway.ingest(expiring, operation="select", receive_time_s=20.0)
    expired = gateway.ingest(
        expiring, operation="operate", receive_time_s=25.0001
    )
    assert expired["reason"] == "select_expired"


def test_sequence_and_lineage_rules():
    gateway = CyberGateway()
    first = command(message_id="original", sequence=4)
    assert sbo(gateway, first)[1]["gateway_decision"] == "accepted"

    non_monotonic = command(message_id="old", sequence=4)
    assert (
        gateway.ingest(
            non_monotonic, operation="select", receive_time_s=10.2
        )["reason"]
        == "non_monotonic_sequence"
    )
    orphan = command(
        message_id="derived",
        sequence=5,
        parent_message_id="does-not-exist",
    )
    assert (
        gateway.ingest(orphan, operation="select", receive_time_s=10.2)[
            "reason"
        ]
        == "unknown_parent"
    )
    derived = command(
        message_id="derived",
        sequence=5,
        parent_message_id="original",
    )
    assert (
        sbo(gateway, derived, 10.2, 10.3)[1]["gateway_decision"]
        == "accepted"
    )


@pytest.mark.parametrize(
    ("command_type", "value", "unit", "settings", "inputs"),
    [
        (
            "active_power_setpoint",
            -50.0,
            "kW",
            {},
            {"demand_kw": -50.0},
        ),
        (
            "reactive_setpoint",
            -40.0,
            "kvar",
            {
                "QV_MODE_ENABLE": "DISABLED",
                "QP_MODE_ENABLE": "DISABLED",
                "CONST_PF_MODE_ENABLE": "DISABLED",
                "CONST_Q": -0.2,
                "CONST_Q_MODE_ENABLE": "ENABLED",
            },
            {},
        ),
    ],
)
def test_exact_opender_setting_mapping(
    command_type, value, unit, settings, inputs
):
    gateway = CyberGateway()
    message = command(
        command_type=command_type, value=value, unit=unit
    )
    accepted = sbo(gateway, message)[1]
    assert accepted["opender_settings"] == settings
    assert accepted["opender_inputs"] == inputs
    applied = gateway.advance_to(10.1)
    assert applied[0]["opender_settings"] == settings
    assert applied[0]["opender_inputs"] == inputs


def test_zero_reactive_setpoint_atomically_disables_constant_q():
    gateway = CyberGateway()
    message = command(
        command_type="reactive_setpoint",
        value=0.0,
        unit="kvar",
    )
    settings = sbo(gateway, message)[1]["opender_settings"]
    assert settings == {
        "QV_MODE_ENABLE": "DISABLED",
        "QP_MODE_ENABLE": "DISABLED",
        "CONST_PF_MODE_ENABLE": "DISABLED",
        "CONST_Q": 0.0,
        "CONST_Q_MODE_ENABLE": "DISABLED",
    }


def test_queue_order_is_due_time_then_acceptance_order():
    point_map = load_point_map()
    point_map["commands"]["active_power_setpoint"]["execution_delay_s"] = 2.0
    gateway = CyberGateway(point_map=point_map)
    first = command(message_id="first", sequence=1, value=0.5)
    second = command(message_id="second", sequence=2, value=0.6)
    sbo(gateway, first, 10.0, 10.1)
    sbo(gateway, second, 10.1, 10.1)
    assert gateway.advance_to(12.0) == []
    applied = gateway.advance_to(12.1)
    assert [row["message_id"] for row in applied] == ["first", "second"]
    assert [row["actuation_sequence"] for row in applied] == [1, 2]


def test_receive_and_advance_times_are_monotonic():
    gateway = CyberGateway()
    message = command()
    gateway.ingest(message, operation="select", receive_time_s=10.0)
    earlier = gateway.ingest(
        command(message_id="earlier", sequence=2),
        operation="select",
        receive_time_s=9.9,
    )
    assert earlier["reason"] == "invalid_receive_time"
    with pytest.raises(ValueError, match="not precede ingress"):
        gateway.advance_to(9.9)


class FakeSink:
    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail

    def schedule_gateway_action(
        self, *, action_id, delay_s, settings, inputs
    ):
        self.calls.append(
            {
                "action_id": action_id,
                "delay_s": delay_s,
                "settings": settings,
                "inputs": inputs,
            }
        )
        if self.fail:
            raise RuntimeError("injected failure")
        return {
            "action_id": action_id,
            "sink_queued_time_s": 10.1,
            "sink_due_time_s": 10.1,
        }


def test_sink_receives_zero_delay_at_gateway_due_boundary():
    gateway = CyberGateway()
    message = command()
    sbo(gateway, message)
    sink = FakeSink()
    serviced = gateway.advance_to(10.1, sink=sink)
    assert sink.calls == [
        {
            "action_id": "cmd-1",
            "delay_s": 0.0,
            "settings": {},
            "inputs": {"demand_kw": 10.0},
        }
    ]
    assert serviced[0]["gateway_service_time_s"] == 10.1
    assert serviced[0]["sink_queue"]["action_id"] == "cmd-1"


def test_pending_action_is_not_popped_when_sink_queueing_fails():
    gateway = CyberGateway()
    sbo(gateway, command())
    sink = FakeSink(fail=True)
    with pytest.raises(RuntimeError, match="injected"):
        gateway.advance_to(10.1, sink=sink)
    assert gateway.pending_count() == 1
    sink.fail = False
    assert gateway.advance_to(10.1, sink=sink)[0]["action_id"] == "cmd-1"
    assert gateway.pending_count() == 0


def test_actual_application_requires_known_sink_queued_action():
    gateway = CyberGateway()
    sbo(gateway, command())
    gateway.advance_to(10.1, sink=FakeSink())
    applied = gateway.record_opender_applications(
        [
            {
                "action_id": "cmd-1",
                "due_time_s": 10.1,
                "applied_time_s": 11.0,
                "settings": {},
                "inputs": {"demand_kw": 10.0},
            }
        ]
    )
    assert applied[0]["opender_applied_time_s"] == 11.0
    with pytest.raises(ValueError, match="duplicate"):
        gateway.record_opender_applications(
            [
                {
                    "action_id": "cmd-1",
                    "applied_time_s": 11.0,
                }
            ]
        )


@pytest.mark.parametrize(
    ("field", "bad_value", "error"),
    [
        (
            "settings",
            {"AP_LIMIT_ENABLE": "ENABLED"},
            "settings mismatch",
        ),
        ("inputs", {"demand_kw": -10.0}, "inputs mismatch"),
        ("due_time_s", 10.100001, "due_time_s mismatch"),
    ],
)
def test_application_report_mismatch_fails_closed(field, bad_value, error):
    gateway = CyberGateway()
    sbo(gateway, command())
    gateway.advance_to(10.1, sink=FakeSink())
    report = {
        "action_id": "cmd-1",
        "due_time_s": 10.1,
        "applied_time_s": 11.0,
        "settings": {},
        "inputs": {"demand_kw": 10.0},
    }
    report[field] = bad_value
    with pytest.raises(ValueError, match=error):
        gateway.record_opender_applications([report])


def test_non_object_application_report_fails_closed():
    gateway = CyberGateway()
    with pytest.raises(ValueError, match="must be an object"):
        gateway.record_opender_applications([None])


def test_gateway_acceptance_is_not_actual_device_application():
    gateway = CyberGateway()
    accepted = sbo(gateway, command())[1]
    assert accepted["lifecycle_stage"] == "gateway_accepted"
    assert accepted["acceptance_scope"] == (
        "gateway_validation_and_queue_acceptance_not_device_application"
    )
    assert gateway._opender_applied_actions == set()


def test_event_log_appends_canonical_lines_without_truncation(tmp_path):
    log_path = tmp_path / "events.jsonl"
    log_path.write_text('{"preexisting":true}\n', encoding="utf-8")
    gateway = CyberGateway(event_log_path=log_path)
    message = command()
    sbo(gateway, message)
    gateway.advance_to(10.1)
    rows = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0] == {"preexisting": True}
    assert [row["event_type"] for row in rows[1:]] == [
        "command_selected",
        "command_accepted",
        "gateway_action_serviced",
    ]
    assert [row["event_sequence"] for row in rows[1:]] == [1, 2, 3]


def test_same_trace_produces_byte_identical_logs(tmp_path):
    paths = [tmp_path / "a.jsonl", tmp_path / "b.jsonl"]
    for path in paths:
        gateway = CyberGateway(event_log_path=path)
        first = command(message_id="one", sequence=1, value=0.5)
        second = command(message_id="two", sequence=2, value=0.8)
        sbo(gateway, first, 10.0, 10.1)
        sbo(gateway, second, 10.2, 10.3)
        gateway.advance_to(11.0)
    assert paths[0].read_bytes() == paths[1].read_bytes()
