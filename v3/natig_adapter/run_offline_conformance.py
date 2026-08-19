#!/usr/bin/env python3
"""Run deterministic G4 offline DNP3-adapter conformance.

This experiment compares two local command paths into independent real
``ScheduledOpenDERBESS`` instances:

1. semantic envelope -> CyberGateway -> OpenDER
2. G41V1 -> Dnp3GatewayBridge -> CyberGateway -> OpenDER

It intentionally does not instantiate NATIG, ns-3, HELICS, or GridLAB-D.
Passing this runner is evidence of offline adapter conformance only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from opender import DERCommonFileFormatBESS

from v3.cyber_gateway import CyberGateway
from v3.natig_adapter.dnp3_codec import (
    ONLINE_FLAG,
    decode_group1v2,
    decode_group30v5,
    decode_group41v1,
    encode_group1v2,
    encode_group30v5,
    encode_group41v1,
)
from v3.natig_adapter.gateway_bridge import Dnp3GatewayBridge
from v3.opender.device import DeviceOutput, ScheduledOpenDERBESS


SCOPE = (
    "offline adapter conformance only; no NATIG, ns-3, HELICS, or "
    "GridLAB-D equivalence"
)
DURATION_S = 840
DEVICE_STEP_S = 1.0
TERMINAL_VOLTAGE_PU = 1.0
FREQUENCY_HZ = 60.0
RATING_VA = 200_000.0
ENERGY_CAPACITY_WH = 205_000.0

# Exact pulse schedule frozen by v3/opender_federate/run_physical_loop.py.
SCHEDULE_WINDOWS = (
    ("baseline", 0, 60, 0.0, 0.0),
    ("p_inject", 60, 180, 10.0, 0.0),
    ("p_recovery", 180, 240, 0.0, 0.0),
    ("p_absorb", 240, 360, -10.0, 0.0),
    ("pre_q_recovery", 360, 420, 0.0, 0.0),
    ("q_inject", 420, 540, 0.0, 10.0),
    ("q_recovery", 540, 600, 0.0, 0.0),
    ("q_absorb", 600, 720, 0.0, -10.0),
    ("final_recovery", 720, 840, 0.0, 0.0),
)

COMMANDS = (
    (0, "active_power_setpoint", "kW"),
    (1, "reactive_setpoint", "kvar"),
)
TELEMETRY = (
    (0, "active_power", "kW"),
    (1, "reactive_power", "kvar"),
    (2, "terminal_voltage", "pu"),
    (3, "state_of_charge", "pu"),
)
BINARY_TELEMETRY = (
    (0, "connected", "boolean"),
    (1, "command_accepted", "boolean"),
)
FLOAT32_RESIDUAL_BOUNDS = {
    "AI0_active_power_kW": 2.0e-5,
    "AI1_reactive_power_kvar": 2.0e-5,
    "AI2_terminal_voltage_pu": 2.0e-7,
    "AI3_state_of_charge_pu": 2.0e-7,
}
TRACE_ABS_TOLERANCE = 1.0e-12
APPLICATION_DELAY_LOWER_S = DEVICE_STEP_S
APPLICATION_DELAY_UPPER_S = DEVICE_STEP_S


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _signature(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def make_device() -> ScheduledOpenDERBESS:
    """Construct the same physical OpenDER BESS used by canonical G3."""

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
        NP_BESS_CAPACITY=ENERGY_CAPACITY_WH,
        NP_BESS_SOC_MIN=0.10,
        NP_BESS_SOC_MAX=1.0,
        SOC_INIT=0.50,
        NP_EFFICIENCY=0.95,
        NP_BESS_P_RAMP_TIME=0,
        NP_MODE_TRANSITION_TIME=15,
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
    return ScheduledOpenDERBESS(
        step_s=DEVICE_STEP_S, der_file_obj=settings
    )


def _semantic_command(
    *,
    point_index: int,
    value: float,
    time_s: float,
    sequence: int,
) -> dict[str, Any]:
    _, command_type, unit = COMMANDS[point_index]
    return {
        "schema_version": "0.1",
        "kind": "command",
        "message_id": f"direct-t{int(time_s):04d}-ao{point_index}",
        "event_time_s": time_s,
        "source": "ev_controller_v3",
        "target": "DER_EV4_BESS",
        "sequence": sequence,
        "type": command_type,
        "payload": {
            "value": value,
            "unit": unit,
            "valid_until_s": time_s + 5.0,
            "quality": ["online"],
        },
    }


def _direct_sbo(
    gateway: CyberGateway,
    *,
    point_index: int,
    value: float,
    time_s: float,
    sequence: int,
) -> dict[str, Any]:
    message = _semantic_command(
        point_index=point_index,
        value=value,
        time_s=time_s,
        sequence=sequence,
    )
    selected = gateway.ingest(
        message, operation="select", receive_time_s=time_s
    )
    operated = gateway.ingest(
        message, operation="operate", receive_time_s=time_s
    )
    assert selected["gateway_decision"] == "selected", selected
    assert operated["gateway_decision"] == "accepted", operated
    return {
        "point_index": point_index,
        "requested_value": value,
        "semantic_message": message,
        "select": selected,
        "operate": operated,
    }


def _dnp3_sbo(
    bridge: Dnp3GatewayBridge,
    *,
    point_index: int,
    value: float,
    time_s: float,
) -> dict[str, Any]:
    body = encode_group41v1(point_index=point_index, value=value)
    decoded = decode_group41v1(body, point_index=point_index)
    assert decoded.value == value
    assert decoded.status == 0
    selected = bridge.process_group41v1(
        body,
        point_index=point_index,
        operation="select",
        receive_time_s=time_s,
        master_address=1,
        outstation_address=4,
    )
    operated = bridge.process_group41v1(
        body,
        point_index=point_index,
        operation="operate",
        receive_time_s=time_s,
        master_address=1,
        outstation_address=4,
    )
    assert selected["adapter_decision"] == "selected", selected
    assert selected["gateway_result"]["gateway_decision"] == "selected"
    assert operated["adapter_decision"] == "accepted", operated
    assert operated["gateway_result"]["gateway_decision"] == "accepted"
    assert selected["semantic_message"] == operated["semantic_message"]
    semantic = operated["semantic_message"]
    assert semantic["payload"]["value"] == value
    assert semantic["type"] == COMMANDS[point_index][1]
    assert semantic["payload"]["unit"] == COMMANDS[point_index][2]
    return {
        "point_index": point_index,
        "requested_value": value,
        "g41v1_hex": body.hex(),
        "decoded_value": decoded.value,
        "select": selected,
        "operate": operated,
    }


def _output_row(output: DeviceOutput) -> dict[str, Any]:
    return {
        "time_s": output.time_s,
        "p_out_kw": output.p_out_kw,
        "q_out_kvar": output.q_out_kvar,
        "status": output.status,
        "soc_pu": output.soc,
    }


def _telemetry_values(output: DeviceOutput) -> tuple[float, ...]:
    return (
        output.p_out_kw,
        output.q_out_kvar,
        TERMINAL_VOLTAGE_PU,
        output.soc,
    )


def _lifecycle_records(
    command_records: list[dict[str, Any]],
    serviced_records: list[dict[str, Any]],
    applied_records: list[dict[str, Any]],
    *,
    path: str,
    transition_s: int,
    window: str,
) -> list[dict[str, Any]]:
    service_by_id = {
        record["action_id"]: record for record in serviced_records
    }
    applied_by_id = {
        record["action_id"]: record for record in applied_records
    }
    lifecycle = []
    for command in command_records:
        operated = command["operate"]
        gateway_result = (
            operated
            if path == "direct"
            else operated["gateway_result"]
        )
        action_id = gateway_result["message_id"]
        service = service_by_id[action_id]
        applied = applied_by_id[action_id]
        delay = (
            applied["applied_time_s"]
            - gateway_result["receive_time_s"]
        )
        assert service["sink_queue"]["action_id"] == action_id
        assert service["gateway_service_time_s"] == transition_s
        assert service["sink_queue"]["sink_queued_time_s"] == transition_s
        assert APPLICATION_DELAY_LOWER_S <= delay <= (
            APPLICATION_DELAY_UPPER_S
        )
        lifecycle.append(
            {
                "path": path,
                "window": window,
                "transition_s": transition_s,
                "point_index": command["point_index"],
                "requested_value": command["requested_value"],
                "action_id": action_id,
                "select_status": "selected",
                "operate_status": "accepted",
                "sink_status": "queued",
                "application_status": "applied",
                "gateway_due_time_s": service["gateway_due_time_s"],
                "gateway_service_time_s": service[
                    "gateway_service_time_s"
                ],
                "device_applied_time_s": applied["applied_time_s"],
                "accept_to_apply_s": delay,
            }
        )
    return lifecycle


def run_once() -> dict[str, Any]:
    """Execute one 840-second paired path comparison and assert conformance."""

    direct_gateway = CyberGateway()
    dnp3_gateway = CyberGateway()
    bridge = Dnp3GatewayBridge(dnp3_gateway)
    direct_device = make_device()
    dnp3_device = make_device()
    windows_by_start = {
        start: (name, p_kw, q_kvar)
        for name, start, _stop, p_kw, q_kvar in SCHEDULE_WINDOWS
    }

    direct_trace: list[dict[str, Any]] = []
    dnp3_trace: list[dict[str, Any]] = []
    telemetry_trace: list[dict[str, Any]] = []
    lifecycle: list[dict[str, Any]] = []
    command_roundtrips: list[dict[str, Any]] = []
    last_command_accepted = False
    residual_maxima = {
        key: 0.0 for key in FLOAT32_RESIDUAL_BOUNDS
    }

    for transition_s in range(DURATION_S):
        direct_commands: list[dict[str, Any]] = []
        dnp3_commands: list[dict[str, Any]] = []
        window = None
        if transition_s in windows_by_start:
            window, p_kw, q_kvar = windows_by_start[transition_s]
            transition_index = len(lifecycle) // 4 + 1
            for point_index, value in enumerate((p_kw, q_kvar)):
                direct_command = _direct_sbo(
                    direct_gateway,
                    point_index=point_index,
                    value=value,
                    time_s=float(transition_s),
                    sequence=transition_index,
                )
                dnp3_command = _dnp3_sbo(
                    bridge,
                    point_index=point_index,
                    value=value,
                    time_s=float(transition_s),
                )
                direct_commands.append(direct_command)
                dnp3_commands.append(dnp3_command)
                command_roundtrips.append(
                    {
                        "transition_s": transition_s,
                        "window": window,
                        "point_index": point_index,
                        "requested_value": value,
                        "direct_semantic_value": direct_command[
                            "semantic_message"
                        ]["payload"]["value"],
                        "dnp3_decoded_value": dnp3_command[
                            "decoded_value"
                        ],
                        "g41v1_hex": dnp3_command["g41v1_hex"],
                    }
                )
            last_command_accepted = True

        direct_serviced = direct_gateway.advance_to(
            float(transition_s), sink=direct_device
        )
        dnp3_serviced = dnp3_gateway.advance_to(
            float(transition_s), sink=dnp3_device
        )
        direct_output, direct_applied = direct_device.step(
            v_pu=TERMINAL_VOLTAGE_PU, frequency_hz=FREQUENCY_HZ
        )
        dnp3_output, dnp3_applied = dnp3_device.step(
            v_pu=TERMINAL_VOLTAGE_PU, frequency_hz=FREQUENCY_HZ
        )
        direct_gateway.record_opender_applications(direct_applied)
        dnp3_gateway.record_opender_applications(dnp3_applied)

        if window is not None:
            assert len(direct_serviced) == len(direct_applied) == 2
            assert len(dnp3_serviced) == len(dnp3_applied) == 2
            lifecycle.extend(
                _lifecycle_records(
                    direct_commands,
                    direct_serviced,
                    direct_applied,
                    path="direct",
                    transition_s=transition_s,
                    window=window,
                )
            )
            lifecycle.extend(
                _lifecycle_records(
                    dnp3_commands,
                    dnp3_serviced,
                    dnp3_applied,
                    path="dnp3",
                    transition_s=transition_s,
                    window=window,
                )
            )
        else:
            assert direct_serviced == []
            assert dnp3_serviced == []
            assert direct_applied == []
            assert dnp3_applied == []

        direct_row = _output_row(direct_output)
        dnp3_row = _output_row(dnp3_output)
        direct_trace.append(direct_row)
        dnp3_trace.append(dnp3_row)

        telemetry_row = {
            "time_s": dnp3_output.time_s,
            "analog_points": {},
            "binary_points": {},
        }
        for (point_index, telemetry_type, unit), raw_value in zip(
            TELEMETRY, _telemetry_values(dnp3_output)
        ):
            body = encode_group30v5(
                point_index=point_index, value=raw_value
            )
            decoded = decode_group30v5(body, point_index=point_index)
            assert decoded.telemetry_type == telemetry_type
            assert decoded.unit == unit
            assert decoded.flags == ONLINE_FLAG
            residual = abs(decoded.value - raw_value)
            key = (
                f"AI{point_index}_{telemetry_type}_"
                f"{unit.replace('/', '_per_')}"
            )
            bound = FLOAT32_RESIDUAL_BOUNDS[key]
            assert residual <= bound, {
                "point": key,
                "raw": raw_value,
                "decoded": decoded.value,
                "residual": residual,
                "bound": bound,
            }
            residual_maxima[key] = max(residual_maxima[key], residual)
            telemetry_row["analog_points"][f"AI{point_index}"] = {
                "raw_value": raw_value,
                "g30v5_hex": body.hex(),
                "decoded_value": decoded.value,
                "residual": residual,
                "bound": bound,
            }
        binary_values = (
            dnp3_output.status == "Continuous Operation",
            last_command_accepted,
        )
        for (
            point_index,
            telemetry_type,
            unit,
        ), raw_value in zip(BINARY_TELEMETRY, binary_values):
            body = encode_group1v2(
                point_index=point_index,
                value=raw_value,
                flags=ONLINE_FLAG,
            )
            decoded = decode_group1v2(body, point_index=point_index)
            assert decoded.telemetry_type == telemetry_type
            assert decoded.unit == unit
            assert decoded.flags == ONLINE_FLAG
            assert decoded.value is raw_value
            telemetry_row["binary_points"][f"BI{point_index}"] = {
                "raw_value": raw_value,
                "g1v2_hex": body.hex(),
                "decoded_value": decoded.value,
            }
        telemetry_trace.append(telemetry_row)

    assert direct_gateway.pending_count() == 0
    assert dnp3_gateway.pending_count() == 0
    assert len(direct_trace) == len(dnp3_trace) == DURATION_S
    assert len(telemetry_trace) == DURATION_S
    assert len(command_roundtrips) == len(SCHEDULE_WINDOWS) * 2
    assert len(lifecycle) == len(SCHEDULE_WINDOWS) * 2 * 2

    trace_maxima = {
        "p_out_kw": 0.0,
        "q_out_kvar": 0.0,
        "soc_pu": 0.0,
    }
    for direct_row, dnp3_row in zip(direct_trace, dnp3_trace):
        assert direct_row["time_s"] == dnp3_row["time_s"]
        assert direct_row["status"] == dnp3_row["status"]
        for field in trace_maxima:
            difference = abs(direct_row[field] - dnp3_row[field])
            trace_maxima[field] = max(trace_maxima[field], difference)
            assert difference <= TRACE_ABS_TOLERANCE

    core = {
        "scope": SCOPE,
        "schedule": [
            {
                "name": name,
                "start_s": start,
                "stop_s": stop,
                "p_kw": p_kw,
                "q_kvar": q_kvar,
            }
            for name, start, stop, p_kw, q_kvar in SCHEDULE_WINDOWS
        ],
        "configuration": {
            "duration_s": DURATION_S,
            "device_step_s": DEVICE_STEP_S,
            "terminal_voltage_pu": TERMINAL_VOLTAGE_PU,
            "frequency_hz": FREQUENCY_HZ,
            "command_object": "G41V1 signed int32 plus status",
            "telemetry_object": "G30V5 flags plus float32",
        },
        "command_roundtrips": command_roundtrips,
        "lifecycle": lifecycle,
        "direct_trace": direct_trace,
        "dnp3_trace": dnp3_trace,
        "dnp3_telemetry_trace": telemetry_trace,
        "metrics": {
            "schedule_window_count": len(SCHEDULE_WINDOWS),
            "commands_per_path": len(SCHEDULE_WINDOWS) * 2,
            "lifecycle_records": len(lifecycle),
            "steps_per_path": DURATION_S,
            "analog_telemetry_objects_encoded_decoded": DURATION_S * 4,
            "binary_telemetry_objects_encoded_decoded": DURATION_S * 2,
            "telemetry_objects_encoded_decoded": DURATION_S * 6,
            "trace_max_abs_difference": trace_maxima,
            "telemetry_max_abs_residual": residual_maxima,
            "telemetry_residual_bounds": FLOAT32_RESIDUAL_BOUNDS,
            "application_delay_bounds_s": [
                APPLICATION_DELAY_LOWER_S,
                APPLICATION_DELAY_UPPER_S,
            ],
        },
    }
    core["run_signature_sha256"] = _signature(core)
    return core


def run_experiment() -> dict[str, Any]:
    """Run twice and require a byte-identical canonical result."""

    first = run_once()
    second = run_once()
    assert first == second
    return {
        "verdict": "PASS",
        "scope": SCOPE,
        "repeatability": {
            "runs": 2,
            "exact_canonical_match": True,
            "run_signature_sha256": first["run_signature_sha256"],
        },
        "result": first,
    }


def _markdown(result: dict[str, Any], source_hashes: dict[str, str]) -> str:
    metrics = result["result"]["metrics"]
    residuals = metrics["telemetry_max_abs_residual"]
    bounds = metrics["telemetry_residual_bounds"]
    trace = metrics["trace_max_abs_difference"]
    lines = [
        "# G4 Offline Adapter Conformance Report",
        "",
        f"Verdict: **{result['verdict']}**",
        "",
        f"Scope: {result['scope']}.",
        "",
        "This is not evidence of live NATIG/DNP3 transport, ns-3 network, "
        "HELICS timing, or GridLAB-D feeder equivalence.",
        "",
        "## Executed comparison",
        "",
        "- Path A: semantic envelope -> CyberGateway -> real scheduled OpenDER BESS.",
        "- Path B: G41V1 -> Dnp3GatewayBridge -> CyberGateway -> a second real scheduled OpenDER BESS.",
        f"- Canonical G3 pulse schedule: {DURATION_S} seconds, "
        f"{len(SCHEDULE_WINDOWS)} windows, 1-second OpenDER steps.",
        f"- Commands: {metrics['commands_per_path']} AO0/AO1 SBO transactions per path.",
        f"- Telemetry: {metrics['telemetry_objects_encoded_decoded']} "
        "object roundtrips: AI0-AI3 G30V5 plus BI0-BI1 G1V2 on every step.",
        "",
        "## Assertions",
        "",
        "- Every G41V1 command roundtrip preserved the requested engineering value.",
        "- Every SELECT was selected, every OPERATE accepted, every action queued, and every action applied.",
        f"- All command applications occurred in exactly {DEVICE_STEP_S:g} second.",
        "- The two real OpenDER traces were equivalent within "
        f"{TRACE_ABS_TOLERANCE:.1e} absolute tolerance.",
        "- Every telemetry object retained the online flag and stayed within its preregistered float32 residual bound.",
        "- BI0 connected and BI1 command-accepted values survived every stock-compatible G1V2 roundtrip.",
        "- A complete second run matched the first canonical result exactly.",
        "",
        "## Maximum residuals",
        "",
        "| Quantity | Observed | Bound |",
        "|---|---:|---:|",
    ]
    for key in sorted(residuals):
        lines.append(f"| {key} | {residuals[key]:.12g} | {bounds[key]:.12g} |")
    lines.extend(
        [
            f"| direct vs DNP3 P (kW) | {trace['p_out_kw']:.12g} | {TRACE_ABS_TOLERANCE:.12g} |",
            f"| direct vs DNP3 Q (kvar) | {trace['q_out_kvar']:.12g} | {TRACE_ABS_TOLERANCE:.12g} |",
            f"| direct vs DNP3 SOC (pu) | {trace['soc_pu']:.12g} | {TRACE_ABS_TOLERANCE:.12g} |",
            "",
            "## Repeatability and provenance",
            "",
            f"- Two-run signature: `{result['repeatability']['run_signature_sha256']}`",
        ]
    )
    for path, digest in sorted(source_hashes.items()):
        lines.append(f"- `{path}`: `{digest}`")
    return "\n".join(lines) + "\n"


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    """Write create-once JSON and Markdown evidence."""

    output_dir.mkdir(parents=True, exist_ok=False)
    v3_root = Path(__file__).resolve().parents[1]
    source_paths = (
        Path(__file__).resolve(),
        v3_root / "cyber_gateway/gateway.py",
        v3_root / "cyber_gateway/dnp3_point_map.yaml",
        v3_root / "natig_adapter/dnp3_codec.py",
        v3_root / "natig_adapter/gateway_bridge.py",
        v3_root / "opender/device.py",
        v3_root / "opender_federate/run_physical_loop.py",
    )
    hashes = {
        str(path.relative_to(v3_root)): _sha256(path) for path in source_paths
    }
    artifact = {**result, "source_sha256": hashes}
    (output_dir / "offline_conformance.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "OFFLINE_CONFORMANCE_REPORT.md").write_text(
        _markdown(artifact, hashes), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="create-once evidence directory; omit for assertion-only run",
    )
    args = parser.parse_args()
    result = run_experiment()
    if args.output_dir is not None:
        write_outputs(result, args.output_dir)
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "scope": result["scope"],
                "repeatability": result["repeatability"],
                "metrics": result["result"]["metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
