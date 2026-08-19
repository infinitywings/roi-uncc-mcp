#!/usr/bin/env python3
"""Real OpenDER G4 gateway combination federate for a benign live run."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import helics as h

from v3.cyber_gateway import CyberGateway
from v3.natig_adapter.dnp3_codec import (
    encode_group41v1,
)
from v3.natig_adapter.gateway_bridge import Dnp3GatewayBridge
from v3.natig_adapter.run_offline_conformance import make_device


DURATION_S = 840
COUPLING_PERIOD_S = 10
NOMINAL_VOLTAGE_V = 2401.7771
DESTINATION = "natig/der_ev4"


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


def process_commands(
    endpoint: Any,
    bridge: Dnp3GatewayBridge,
    receive_time_s: float,
) -> list[dict[str, Any]]:
    records = []
    while h.helicsEndpointHasMessage(endpoint):
        message = h.helicsEndpointGetMessage(endpoint)
        wire = json.loads(message_text(message))
        if wire.get("schema_version") != "grideval-g4-dnp3-object-0.1":
            raise ValueError("unexpected gateway wire schema")
        if set(wire) != {
            "schema_version",
            "group",
            "variation",
            "operation",
            "master_address",
            "outstation_address",
            "point_index",
            "raw_count",
            "status",
        }:
            raise ValueError("DNP3 gateway wire fields must be exact")
        if (
            wire["group"] != 41
            or wire["variation"] != 1
            or wire["status"] != 0
            or wire["operation"] not in {"select", "operate"}
            or wire["point_index"] not in {0, 1}
            or not isinstance(wire["raw_count"], int)
            or isinstance(wire["raw_count"], bool)
        ):
            raise ValueError("invalid strict G41V1 callback")
        payload = encode_group41v1(
            point_index=wire["point_index"],
            value=wire["raw_count"] * 0.001,
            status=wire["status"],
        )
        if int.from_bytes(payload[:4], "little", signed=True) != wire[
            "raw_count"
        ]:
            raise ValueError("G41V1 callback raw count is not exact")
        result = bridge.process_group41v1(
            payload,
            point_index=wire["point_index"],
            operation=wire["operation"],
            receive_time_s=receive_time_s,
            master_address=wire["master_address"],
            outstation_address=wire["outstation_address"],
        )
        expected = (
            "selected"
            if wire["operation"] == "select"
            else "accepted"
        )
        if result["adapter_decision"] != expected:
            raise RuntimeError(
                f"benign command was not {expected}: {result}"
            )
        records.append(
            {
                "receive_time_s": receive_time_s,
                "wire": wire,
                "result": result,
            }
        )
    return records


def telemetry_wire(
    output: Any,
    command_accepted: bool,
    terminal_voltage_v: float,
) -> dict[str, Any]:
    analog_values = [
        output.p_out_kw,
        output.q_out_kvar,
        terminal_voltage_v / NOMINAL_VOLTAGE_V,
        output.soc,
    ]
    binary_values = [
        output.status == "Continuous Operation",
        command_accepted,
    ]
    return {
        "schema_version": "grideval-g4-telemetry-0.1",
        "target": "DER_EV4_BESS",
        "analog": analog_values,
        "binary": binary_values,
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
    bridge = Dnp3GatewayBridge(gateway)
    trace: dict[str, Any] = {
        "scope": "G4 benign gateway/OpenDER trace; no attacker",
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
                endpoint, bridge, granted
            )
            trace["commands"].extend(command_records)
            if any(
                record["wire"]["operation"] == "operate"
                for record in command_records
            ):
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
