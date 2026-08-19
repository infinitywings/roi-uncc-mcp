#!/usr/bin/env python3
"""Strict direct-control OpenDER gateway federate for GridEval G4."""

from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import helics as h

from v3.cyber_gateway import CyberGateway
from v3.natig_adapter.run_offline_conformance import make_device


DURATION_S = 840
COUPLING_PERIOD_S = 10
NOMINAL_VOLTAGE_V = 2401.7771
DESTINATION = "controller/der_ev4"
WIRE_FIELDS = {
    "wire_schema",
    "operation",
    "point_index",
    "semantic_message",
}
MESSAGE_FIELDS = {
    "schema_version",
    "kind",
    "message_id",
    "event_time_s",
    "source",
    "target",
    "sequence",
    "type",
    "payload",
}
PAYLOAD_FIELDS = {
    "value",
    "unit",
    "valid_until_s",
    "quality",
}
POINT_BINDINGS = {
    0: ("active_power_setpoint", "kW"),
    1: ("reactive_setpoint", "kvar"),
}


def normalize_helics_complex(value: Any) -> complex:
    """Normalize the HELICS 2.7.1 tuple API without accepting malformed data."""
    if isinstance(value, complex):
        result = value
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        real, imag = value
        if any(
            isinstance(component, bool)
            or not isinstance(component, (int, float))
            for component in (real, imag)
        ):
            raise TypeError("HELICS complex components must be numeric")
        result = complex(float(real), float(imag))
    else:
        raise TypeError(
            "HELICS complex value must be complex or a real/imag pair"
        )
    if not math.isfinite(result.real) or not math.isfinite(result.imag):
        raise ValueError("HELICS complex value must be finite")
    return result


def message_text(message: Any) -> str:
    try:
        return h.helicsMessageGetString(message)
    except (AttributeError, TypeError):
        data = message.data
        return (
            data.decode("utf-8")
            if isinstance(data, (bytes, bytearray))
            else str(data)
        )


def send_json(endpoint: Any, federate: Any, value: dict[str, Any]) -> None:
    message = h.helicsFederateCreateMessage(federate)
    h.helicsMessageSetString(
        message,
        json.dumps(value, sort_keys=True, separators=(",", ":")),
    )
    h.helicsMessageSetDestination(message, DESTINATION)
    h.helicsEndpointSendMessage(endpoint, message)


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def validate_direct_wire(wire: Any) -> tuple[int, dict[str, Any]]:
    """Validate the complete direct-command envelope before gateway ingress."""
    if not isinstance(wire, dict) or set(wire) != WIRE_FIELDS:
        raise ValueError("direct command wire fields must be exact")
    if wire["wire_schema"] != "grideval-g4-live-direct-command/1.0":
        raise ValueError("unexpected direct command wire schema")
    if wire["operation"] != "select_operate":
        raise ValueError("direct command must request SELECT+OPERATE")
    point_index = wire["point_index"]
    if (
        not isinstance(point_index, int)
        or isinstance(point_index, bool)
        or point_index not in POINT_BINDINGS
    ):
        raise ValueError("direct command point index must be 0 or 1")
    semantic = wire["semantic_message"]
    if not isinstance(semantic, dict) or set(semantic) != MESSAGE_FIELDS:
        raise ValueError("semantic command fields must be exact")
    payload = semantic.get("payload")
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_FIELDS:
        raise ValueError("semantic command payload fields must be exact")
    command_type, unit = POINT_BINDINGS[point_index]
    if (
        semantic["schema_version"] != "0.1"
        or semantic["kind"] != "command"
        or semantic["source"] != "ev_controller_v3"
        or semantic["target"] != "DER_EV4_BESS"
        or semantic["type"] != command_type
        or payload["unit"] != unit
        or payload["quality"] != ["online"]
    ):
        raise ValueError("semantic command identity is not canonical")
    for field in ("event_time_s",):
        if not _finite_number(semantic[field]) or semantic[field] < 0:
            raise ValueError(f"semantic command {field} must be non-negative")
    if (
        not isinstance(semantic["sequence"], int)
        or isinstance(semantic["sequence"], bool)
        or semantic["sequence"] <= 0
    ):
        raise ValueError("semantic command sequence must be positive")
    if not _finite_number(payload["value"]):
        raise ValueError("semantic command value must be finite")
    if (
        not _finite_number(payload["valid_until_s"])
        or float(payload["valid_until_s"])
        != float(semantic["event_time_s"]) + 30.0
    ):
        raise ValueError("semantic command validity window must be exact")
    expected_id = (
        f"live-t{int(semantic['event_time_s']):04d}-ao{point_index}"
    )
    if (
        semantic["message_id"] != expected_id
        or float(semantic["event_time_s"])
        != float(int(semantic["event_time_s"]))
    ):
        raise ValueError("semantic command message identity must be exact")
    return point_index, deepcopy(semantic)


def process_commands(
    endpoint: Any,
    gateway: CyberGateway,
    receive_time_s: float,
) -> list[dict[str, Any]]:
    records = []
    while h.helicsEndpointHasMessage(endpoint):
        message = h.helicsEndpointGetMessage(endpoint)
        _point_index, semantic = validate_direct_wire(
            json.loads(message_text(message))
        )
        select_result = gateway.ingest(
            deepcopy(semantic),
            operation="select",
            receive_time_s=receive_time_s,
        )
        if select_result["gateway_decision"] != "selected":
            raise RuntimeError(
                f"benign direct command was not selected: {select_result}"
            )
        operate_result = gateway.ingest(
            deepcopy(semantic),
            operation="operate",
            receive_time_s=receive_time_s,
        )
        if operate_result["gateway_decision"] != "accepted":
            raise RuntimeError(
                f"benign direct command was not accepted: {operate_result}"
            )
        records.append(
            {
                "receive_time_s": receive_time_s,
                "semantic_message": semantic,
                "select_result": select_result,
                "operate_result": operate_result,
            }
        )
    return records


def telemetry_wire(
    output: Any,
    command_accepted: bool,
    terminal_voltage_v: float,
) -> dict[str, Any]:
    return {
        "schema_version": "grideval-g4-telemetry-0.1",
        "target": "DER_EV4_BESS",
        "analog": [
            output.p_out_kw,
            output.q_out_kvar,
            terminal_voltage_v / NOMINAL_VOLTAGE_V,
            output.soc,
        ],
        "binary": [
            output.status == "Continuous Operation",
            command_accepted,
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    if args.trace.exists():
        raise FileExistsError(args.trace)

    fed = h.helicsCreateCombinationFederateFromConfig(str(args.config))
    endpoint = h.helicsFederateGetEndpointByIndex(fed, 0)
    publication = h.helicsFederateGetPublicationByIndex(fed, 0)
    voltage_input = h.helicsFederateGetInputByIndex(fed, 0)
    h.helicsInputSetDefaultComplex(
        voltage_input, NOMINAL_VOLTAGE_V, 0.0
    )

    device = make_device()
    gateway = CyberGateway()
    trace: dict[str, Any] = {
        "scope": (
            "G4 benign live direct gateway/OpenDER trace; "
            "no NATIG, attacker, or impairment"
        ),
        "commands": [],
        "steps": [],
    }
    last_voltage_v = NOMINAL_VOLTAGE_V
    last_output = None
    command_accepted = False
    try:
        h.helicsFederateEnterExecutingMode(fed)
        h.helicsPublicationPublishComplex(publication, 0.0, 0.0)
        granted = 0.0
        same_time_grants = 0
        while granted < DURATION_S:
            command_records = process_commands(
                endpoint, gateway, granted
            )
            trace["commands"].extend(command_records)
            if command_records:
                command_accepted = True
            gateway.advance_to(granted, sink=device)
            next_grant = float(
                h.helicsFederateRequestTime(
                    fed, min(DURATION_S, granted + COUPLING_PERIOD_S)
                )
            )
            if next_grant < granted:
                raise RuntimeError("HELICS granted time moved backwards")
            if next_grant == granted:
                same_time_grants += 1
                if same_time_grants > 1000:
                    raise RuntimeError("excessive same-time HELICS grants")
                continue
            same_time_grants = 0
            voltage = normalize_helics_complex(
                h.helicsInputGetComplex(voltage_input)
            )
            if abs(voltage) > 0.0:
                last_voltage_v = abs(voltage)
            applied = []
            while device.time_s < next_grant:
                last_output, device_applied = device.step(
                    v_pu=last_voltage_v / NOMINAL_VOLTAGE_V,
                    frequency_hz=60.0,
                    voltage_angle_deg=0.0,
                )
                applied.extend(device_applied)
            gateway.record_opender_applications(applied)
            if last_output is None:
                raise RuntimeError("OpenDER did not advance")
            if not all(
                math.isfinite(value)
                for value in (
                    last_output.p_out_kw,
                    last_output.q_out_kvar,
                    last_output.soc,
                )
            ):
                raise RuntimeError("OpenDER produced non-finite telemetry")
            feeder_load = complex(
                -1000.0 * last_output.p_out_kw,
                -1000.0 * last_output.q_out_kvar,
            )
            h.helicsPublicationPublishComplex(
                publication, feeder_load.real, feeder_load.imag
            )
            telemetry = telemetry_wire(
                last_output, command_accepted, last_voltage_v
            )
            send_json(endpoint, fed, telemetry)
            trace["steps"].append(
                {
                    "granted_time_s": next_grant,
                    "device_time_s": last_output.time_s,
                    "terminal_voltage_v": last_voltage_v,
                    "p_out_kw": last_output.p_out_kw,
                    "q_out_kvar": last_output.q_out_kvar,
                    "soc_pu": last_output.soc,
                    "status": last_output.status,
                    "feeder_load_va": {
                        "real": feeder_load.real,
                        "imag": feeder_load.imag,
                    },
                    "applied": applied,
                    "telemetry": telemetry,
                }
            )
            granted = next_grant
    finally:
        try:
            h.helicsFederateFinalize(fed)
        finally:
            h.helicsFederateFree(fed)

    trace["command_message_count"] = len(trace["commands"])
    trace["step_count"] = len(trace["steps"])
    args.trace.write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "command_message_count": trace["command_message_count"],
                "step_count": trace["step_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
