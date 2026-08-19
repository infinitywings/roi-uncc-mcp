from __future__ import annotations

import json

import pytest
from opender import DERCommonFileFormatBESS

from v3.cyber_gateway import CyberGateway
from v3.opender.device import ScheduledOpenDERBESS


RATING_VA = 200_000.0


def make_device() -> ScheduledOpenDERBESS:
    settings = DERCommonFileFormatBESS(
        NP_PHASE="SINGLE",
        NP_P_MAX=RATING_VA,
        NP_P_MAX_OVER_PF=RATING_VA * 0.9,
        NP_P_MAX_UNDER_PF=RATING_VA * 0.9,
        NP_VA_MAX=RATING_VA,
        NP_Q_MAX_INJ=RATING_VA * 0.44,
        NP_Q_MAX_ABS=RATING_VA * 0.44,
        NP_P_MAX_CHARGE=RATING_VA,
        NP_APPARENT_POWER_CHARGE_MAX=RATING_VA,
        NP_AC_V_NOM=2401.7771,
        NP_V_DC=3602.66565,
        NP_BESS_CAPACITY=205_000.0,
        NP_BESS_SOC_MIN=0.10,
        NP_BESS_SOC_MAX=1.0,
        SOC_INIT=0.50,
        NP_EFFICIENCY=0.95,
        NP_BESS_P_RAMP_TIME=0,
        NP_MODE_TRANSITION_TIME=0,
        NP_SET_EXE_TIME=0,
        AP_RT=0,
        AP_LIMIT_ENABLE="ENABLED",
        AP_LIMIT=1.0,
        PF_MODE_ENABLE="DISABLED",
        PV_MODE_ENABLE="DISABLED",
        QV_MODE_ENABLE="DISABLED",
        QP_MODE_ENABLE="DISABLED",
        CONST_PF_MODE_ENABLE="DISABLED",
        CONST_Q_MODE_ENABLE="DISABLED",
        CONST_Q=0.0,
    )
    return ScheduledOpenDERBESS(step_s=1.0, der_file_obj=settings)


def command(
    *,
    message_id: str,
    sequence: int,
    event_time_s: float,
    command_type: str,
    value,
    unit: str,
):
    return {
        "schema_version": "0.1",
        "kind": "command",
        "message_id": message_id,
        "event_time_s": event_time_s,
        "source": "ev_controller_v3",
        "target": "DER_EV4_BESS",
        "sequence": sequence,
        "type": command_type,
        "payload": {
            "value": value,
            "unit": unit,
            "valid_until_s": event_time_s + 10.0,
            "quality": ["online"],
        },
    }


def sbo(gateway: CyberGateway, message, time_s: float):
    gateway.ingest(message, operation="select", receive_time_s=time_s)
    return gateway.ingest(
        message, operation="operate", receive_time_s=time_s
    )


def step(device: ScheduledOpenDERBESS):
    return device.step(v_pu=1.0, frequency_hz=60.0)


def test_gateway_ao0_persists_and_lifecycle_waits_for_real_step(tmp_path):
    log_path = tmp_path / "events.jsonl"
    gateway = CyberGateway(event_log_path=log_path)
    device = make_device()
    p_command = command(
        message_id="p-10",
        sequence=1,
        event_time_s=0.0,
        command_type="active_power_setpoint",
        value=10.0,
        unit="kW",
    )
    assert sbo(gateway, p_command, 0.0)["gateway_decision"] == "accepted"
    serviced = gateway.advance_to(0.0, sink=device)
    assert serviced[0]["sink_queue"]["sink_queued_time_s"] == 0.0
    assert device.demand_kw == 0.0
    assert "opender_action_applied" not in log_path.read_text(encoding="utf-8")

    first_output, first_applied = step(device)
    assert first_applied[0]["action_id"] == "p-10"
    assert first_applied[0]["inputs"] == {"demand_kw": 10.0}
    assert device.demand_kw == 10.0
    gateway.record_opender_applications(first_applied)

    second_output, second_applied = step(device)
    assert second_applied == []
    assert device.demand_kw == 10.0
    assert first_output.p_out_kw == pytest.approx(10.0, abs=0.01)
    assert second_output.p_out_kw == pytest.approx(10.0, abs=0.01)
    with pytest.raises(ValueError, match="owned by the gateway"):
        device.step(v_pu=1.0, frequency_hz=60.0, demand_kw=-10.0)

    event_types = [
        json.loads(line)["event_type"]
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert event_types == [
        "command_selected",
        "command_accepted",
        "sink_queued",
        "opender_action_applied",
    ]


def test_gateway_ao1_is_one_atomic_constant_q_action():
    gateway = CyberGateway()
    device = make_device()
    q_command = command(
        message_id="q-10",
        sequence=1,
        event_time_s=0.0,
        command_type="reactive_setpoint",
        value=10.0,
        unit="kvar",
    )
    accepted = sbo(gateway, q_command, 0.0)
    expected = {
        "QV_MODE_ENABLE": "DISABLED",
        "QP_MODE_ENABLE": "DISABLED",
        "CONST_PF_MODE_ENABLE": "DISABLED",
        "CONST_Q": 0.05,
        "CONST_Q_MODE_ENABLE": "ENABLED",
    }
    assert accepted["opender_settings"] == expected
    gateway.advance_to(0.0, sink=device)
    _, applied = step(device)
    assert len(applied) == 1
    assert applied[0]["action_id"] == "q-10"
    assert applied[0]["settings"] == expected
    assert device.model.der_file.QV_MODE_ENABLE is False
    assert device.model.der_file.QP_MODE_ENABLE is False
    assert device.model.der_file.CONST_PF_MODE_ENABLE is False
    assert device.model.der_file.CONST_Q == pytest.approx(0.05)
    assert device.model.der_file.CONST_Q_MODE_ENABLE is True
