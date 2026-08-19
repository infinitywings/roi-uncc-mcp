#!/usr/bin/env python3
"""Run one GridPACK + two-GridLAB-D + controller benign cadence arm."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import helics as h

from run_gridlabd_cadence_arm import (
    ARMS,
    DURATION_S,
    HIGH_COMMAND_W,
    NOMINAL_COMMAND_W,
    START_TIME,
    STOP_TIME,
    ev4_recorder_rows,
    normalized_diagnostics,
    sha256,
)


def link_model_inputs(source_dir: Path, model_dir: Path) -> None:
    excluded = {
        "1c_IEEE_123_feeder.glm",
        "1c_IEEE_123_feeder_2.glm",
        "mainglm.json",
        "mainglm_2.json",
    }
    for child in source_dir.iterdir():
        if child.name in excluded:
            continue
        if child.name == "output":
            (model_dir / "output").mkdir()
            continue
        if child.suffix.lower() in {".csv", ".log", ".xml", ".png"}:
            continue
        if child.name.startswith("core."):
            continue
        (model_dir / child.name).symlink_to(child)


def overlay_glm(
    source: Path,
    destination: Path,
    minimum_timestep_s: int,
    instrument_ev4: bool,
) -> None:
    text = source.read_text(encoding="utf-8")
    text, minimum_count = re.subn(
        r"#set\s+minimum_timestep=\d+(?:\.\d+)?;",
        f"#set minimum_timestep={minimum_timestep_s}.000000;",
        text,
        count=1,
    )
    text, stop_count = re.subn(
        r"stoptime\s+'[^']+';",
        f"stoptime '{STOP_TIME}';",
        text,
        count=1,
    )
    if minimum_count != 1 or stop_count != 1:
        raise RuntimeError(f"Ambiguous GLM overlay for {source.name}")
    if instrument_ev4:
        pattern = (
            "property measured_voltage_C,constant_power_C,"
            "measured_frequency_C;\n"
            "        interval 1200;\n"
            "        file output/1c_IEEE_123_feeder_0_EV4.csv;"
        )
        replacement = (
            "property measured_voltage_C,constant_power_C,"
            "measured_frequency_C;\n"
            f"        interval {minimum_timestep_s};\n"
            "        file output/1c_IEEE_123_feeder_0_EV4.csv;"
        )
        if text.count(pattern) != 1:
            raise RuntimeError("Could not locate Feeder A EV4 recorder")
        text = text.replace(pattern, replacement)
    destination.write_text(text, encoding="utf-8")


def overlay_helics_config(
    source: Path,
    destination: Path,
    arm_name: str,
    period_s: int,
    feeder: str,
) -> dict[str, Any]:
    config = json.loads(source.read_text(encoding="utf-8"))
    config["name"] = f"{config['name']}_full_{arm_name}"
    config["coreName"] = f"{config['coreName']}_full_{arm_name}"
    config["period"] = period_s
    config["logfile"] = f"{feeder}_{arm_name}_helics.log"
    destination.write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    return config


def full_controller_config(
    path: Path, arm_name: str, arm: dict[str, int], broker_address: str
) -> None:
    config = {
        "coreInit": "--federates=1",
        "coreName": f"full_cadence_controller_{arm_name}_core",
        "coreType": "zmq",
        "broker": broker_address,
        "name": f"full_cadence_controller_{arm_name}",
        "period": arm["controller_helics_period_s"],
        "log_level": "warning",
        "subscriptions": [
            {
                "global": True,
                "key": f"gld_hlc_conn/S{phase}",
                "type": "complex",
                "unit": "VA",
            }
            for phase in ("a", "b", "c")
        ],
        "endpoints": [
            {
                "key": f"EV_Controller/EV{index}",
                "destination": f"gld_hlc_conn/EV{index}",
                "global": True,
                "type": "string",
            }
            for index in range(1, 7)
        ],
        "publications": [
            {"global": True, "key": key, "type": "string"}
            for key in (
                "swEV1_storage",
                "swEV1",
                "swEV4_storage",
                "swEV4",
            )
        ],
    }
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def pacer_config(path: Path, arm_name: str, broker_address: str) -> None:
    """Create a read-only 5-second federate matching the v2 MCP participant."""
    config = {
        "coreInit": "--federates=1",
        "coreName": f"full_cadence_pacer_{arm_name}_core",
        "coreType": "zmq",
        "broker": broker_address,
        "name": f"full_cadence_pacer_{arm_name}",
        "period": 5,
        "log_level": "warning",
        "subscriptions": [
            {
                "global": True,
                "key": f"gridpack/{key}",
                "type": "complex",
                "unit": "V",
            }
            for key in ("Va", "Vb", "Vc", "Va_2", "Vb_2", "Vc_2")
        ],
    }
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def pacer_script(path: Path) -> None:
    """Write the minimal separate process needed for concurrent HELICS pacing."""
    path.write_text(
        """#!/usr/bin/env python3
import sys
import helics as h

import json

fed = h.helicsCreateValueFederateFromConfig(sys.argv[1])
inputs = [
    h.helicsFederateGetInputByIndex(fed, index)
    for index in range(h.helicsFederateGetInputCount(fed))
]
for subscription in inputs:
    h.helicsInputSetDefaultComplex(subscription, 0.0, 0.0)
trace = []
try:
    h.helicsFederateEnterExecutingMode(fed)
    granted = 0.0
    for target in range(5, 241, 5):
        if granted < target:
            granted = float(h.helicsFederateRequestTime(fed, target))
        values = [
            h.helicsInputGetComplex(subscription)
            for subscription in inputs
        ]
        trace.append({
            "requested_time_s": target,
            "granted_time_s": granted,
            "values": [
                {
                    "target": h.helicsInputGetTarget(subscription),
                    "updated": bool(h.helicsInputIsUpdated(subscription)),
                    "real_v": float(value.real),
                    "imag_v": float(value.imag),
                }
                for subscription, value in zip(inputs, values)
            ],
        })
finally:
    with open(sys.argv[2], "w", encoding="utf-8") as handle:
        json.dump(trace, handle, indent=2, allow_nan=False)
        handle.write("\\n")
    h.helicsFederateFinalize(fed)
    h.helicsFederateFree(fed)
    h.helicsCloseLibrary()
""",
        encoding="utf-8",
    )


def prepare_full_model(
    repo: Path, model_dir: Path, arm_name: str, arm: dict[str, int]
) -> dict[str, Any]:
    source_dir = repo / "examples/2bus-13bus"
    link_model_inputs(source_dir, model_dir)
    feeder_a_glm = source_dir / "1c_IEEE_123_feeder.glm"
    feeder_b_glm = source_dir / "1c_IEEE_123_feeder_2.glm"
    feeder_a_json = source_dir / "mainglm.json"
    feeder_b_json = source_dir / "mainglm_2.json"
    overlay_glm(
        feeder_a_glm,
        model_dir / feeder_a_glm.name,
        arm["gridlabd_minimum_timestep_s"],
        True,
    )
    overlay_glm(
        feeder_b_glm,
        model_dir / feeder_b_glm.name,
        (
            120
            if arm_name == "frozen60"
            else arm["gridlabd_minimum_timestep_s"]
        ),
        False,
    )
    config_a = overlay_helics_config(
        feeder_a_json,
        model_dir / feeder_a_json.name,
        arm_name,
        arm["gridlabd_helics_period_s"],
        "feeder_a",
    )
    config_b = overlay_helics_config(
        feeder_b_json,
        model_dir / feeder_b_json.name,
        arm_name,
        arm["gridlabd_helics_period_s"],
        "feeder_b",
    )
    return {
        "source_hashes": {
            str(path.relative_to(repo)): sha256(path)
            for path in (
                feeder_a_glm,
                feeder_b_glm,
                feeder_a_json,
                feeder_b_json,
                source_dir / "gpk-left-fed.cpp",
                source_dir / "build/gpk-left-fed.x",
                source_dir / "input.xml",
                source_dir / "Tr2bus.raw",
            )
        },
        "generated_hashes": {
            child.name: sha256(child)
            for child in (
                model_dir / feeder_a_glm.name,
                model_dir / feeder_b_glm.name,
                model_dir / feeder_a_json.name,
                model_dir / feeder_b_json.name,
            )
        },
        "feeder_a_config": config_a,
        "feeder_b_config": config_b,
    }


def wait_process(
    process: subprocess.Popen[Any], name: str, timeout_s: int = 60
) -> tuple[int, str | None]:
    try:
        return process.wait(timeout=timeout_s), None
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        return process.returncode, f"{name} did not exit within {timeout_s}s"


def run_arm(
    repo: Path,
    output_dir: Path,
    arm_name: str,
    pulse: str,
    gridpack_executable: Path | None = None,
) -> dict[str, Any]:
    arm = ARMS[arm_name]
    with tempfile.TemporaryDirectory(
        prefix=f"grideval-full-{arm_name}-"
    ) as temp:
        temp_root = Path(temp)
        model_dir = temp_root / "model"
        model_dir.mkdir()
        overlay = prepare_full_model(repo, model_dir, arm_name, arm)

        broker_name = f"full_cadence_{arm_name}_broker"
        broker = h.helicsCreateBroker("zmq", broker_name, "-f 5")
        broker_address = h.helicsBrokerGetAddress(broker)
        controller_path = temp_root / "controller.json"
        full_controller_config(
            controller_path, arm_name, arm, broker_address
        )
        pacer_config_path = temp_root / "pacer.json"
        pacer_config(pacer_config_path, arm_name, broker_address)
        pacer_script_path = temp_root / "pacer.py"
        pacer_script(pacer_script_path)
        pacer_trace_path = temp_root / "pacer_trace.json"

        env = os.environ.copy()
        env["HELICS_BROKER"] = broker_address
        selected_gridpack = (
            gridpack_executable.resolve()
            if gridpack_executable is not None
            else model_dir / "build/gpk-left-fed.x"
        )
        process_specs = {
            "gridpack": [str(selected_gridpack)],
            "feeder_a": ["gridlabd", "1c_IEEE_123_feeder.glm"],
            "feeder_b": ["gridlabd", "1c_IEEE_123_feeder_2.glm"],
            "pacer": [
                "python3",
                str(pacer_script_path),
                str(pacer_config_path),
                str(pacer_trace_path),
            ],
        }
        processes = {}
        log_handles = {}
        log_paths = {}
        for name, command in process_specs.items():
            log_path = temp_root / f"{name}.out"
            log_handle = log_path.open("w", encoding="utf-8")
            log_paths[name] = log_path
            log_handles[name] = log_handle
            processes[name] = subprocess.Popen(
                command,
                cwd=model_dir,
                env=env,
                text=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )

        fed = None
        controller_events = []
        run_error = None
        try:
            fed = h.helicsCreateCombinationFederateFromConfig(
                str(controller_path)
            )
            subscriptions = [
                h.helicsFederateGetInputByIndex(fed, index)
                for index in range(h.helicsFederateGetInputCount(fed))
            ]
            for subscription in subscriptions:
                h.helicsInputSetDefaultComplex(subscription, 0.0, 0.0)
            endpoints = {}
            for index in range(h.helicsFederateGetEndpointCount(fed)):
                endpoint = h.helicsFederateGetEndpointByIndex(fed, index)
                name = h.helicsEndpointGetName(endpoint).split("/")[-1]
                endpoints[name] = endpoint
            h.helicsFederateEnterExecutingMode(fed)

            granted = 0.0
            observed_grants: set[float] = set()
            for logical_t in range(10, DURATION_S + 1, 10):
                if granted < logical_t:
                    granted = float(
                        h.helicsFederateRequestTime(fed, logical_t)
                    )
                if granted in observed_grants:
                    continue
                observed_grants.add(granted)
                input_updated = [
                    bool(h.helicsInputIsUpdated(subscription))
                    for subscription in subscriptions
                ]
                phase_values = [
                    h.helicsInputGetComplex(subscription)
                    for subscription in subscriptions
                ]
                commands: dict[str, float] = {}
                # Match v2's Hour-7 CAUTION behavior on the first controller
                # grant: EV1/EV2 remain nominal and EV3-EV6 are shed.
                if pulse == "none" and granted == 60:
                    commands = {
                        f"EV{index}": 0.0 for index in range(3, 7)
                    }
                if pulse == "bounded" and granted == 60:
                    commands = {"EV4": HIGH_COMMAND_W}
                elif pulse == "bounded" and granted == 120:
                    commands = {"EV4": NOMINAL_COMMAND_W}
                for ev_id, command_w in commands.items():
                    h.helicsEndpointSendBytes(
                        endpoints[ev_id], f"{command_w:.1f}+0.0j"
                    )
                controller_events.append(
                    {
                        "logical_request_time_s": logical_t,
                        "granted_time_s": granted,
                        "phase_real_power_w": [
                            float(value.real) for value in phase_values
                        ],
                        "total_real_power_w": float(
                            sum(value.real for value in phase_values)
                        ),
                        "input_updated": input_updated,
                        "ev_commands_w": commands,
                    }
                )
        except Exception as exc:
            run_error = f"{type(exc).__name__}: {exc}"
        finally:
            if fed is not None:
                try:
                    h.helicsFederateFinalize(fed)
                finally:
                    h.helicsFederateFree(fed)

        returncodes = {}
        process_errors = {}
        for name, process in processes.items():
            returncode, process_error = wait_process(process, name)
            returncodes[name] = returncode
            if process_error:
                process_errors[name] = process_error
        for handle in log_handles.values():
            handle.close()

        h.helicsBrokerDisconnect(broker)
        h.helicsBrokerFree(broker)
        recorder_path = (
            model_dir / "output/1c_IEEE_123_feeder_0_EV4.csv"
        )
        recorder_rows = (
            ev4_recorder_rows(recorder_path)
            if recorder_path.exists()
            else []
        )
        diagnostics = {
            name: normalized_diagnostics(
                path.read_text(encoding="utf-8"), temp_root
            )
            for name, path in log_paths.items()
        }
        pacer_trace = (
            json.loads(pacer_trace_path.read_text(encoding="utf-8"))
            if pacer_trace_path.exists()
            else []
        )
        success = (
            run_error is None
            and not process_errors
            and all(code == 0 for code in returncodes.values())
            and bool(controller_events)
            and bool(recorder_rows)
        )
        result = {
            "schema_version": "1.0",
            "arm": arm_name,
            "arm_config": arm,
            "model": (
                "GridPACK two-bus transmission + two IEEE-123 GridLAB-D "
                "feeders + EV4 controller"
            ),
            "simulation_start": START_TIME,
            "simulation_stop": STOP_TIME,
            "simulation_duration_s": DURATION_S,
            "commands": {
                "mode": pulse,
                "high": (
                    {"send_time_s": 60, "ev4_w": HIGH_COMMAND_W}
                    if pulse == "bounded"
                    else None
                ),
                "nominal": (
                    {"send_time_s": 120, "ev4_w": NOMINAL_COMMAND_W}
                    if pulse == "bounded"
                    else None
                ),
            },
            "identity": {
                "runner_sha256": sha256(Path(__file__).resolve()),
                "selected_gridpack_executable": str(selected_gridpack),
                "selected_gridpack_executable_sha256": sha256(
                    selected_gridpack
                ),
                "controller_config_sha256": sha256(controller_path),
                "pacer_config_sha256": sha256(pacer_config_path),
                "helics_version": h.helicsGetVersion(),
                **overlay,
            },
            "controller_events": controller_events,
            "gridlabd_ev4_internal_trace": recorder_rows,
            "gridpack_voltage_trace": pacer_trace,
            "process_returncodes": returncodes,
            "process_diagnostics": diagnostics,
            "process_errors": process_errors,
            "run_error": run_error,
            "success": success,
        }
        (output_dir / "full_coupling_cadence_arm.json").write_text(
            json.dumps(result, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("/workspace"))
    parser.add_argument("--arm", choices=sorted(ARMS), required=True)
    parser.add_argument(
        "--pulse",
        choices=("none", "no_commands", "bounded"),
        default="bounded",
    )
    parser.add_argument("--gridpack-executable", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    result = run_arm(
        args.repo.resolve(),
        output_dir,
        args.arm,
        args.pulse,
        args.gridpack_executable,
    )
    print(
        f"{args.arm}: success={result['success']} "
        f"returncodes={result['process_returncodes']} "
        f"events={len(result['controller_events'])} "
        f"error={result['run_error'] or result['process_errors']}"
    )
    h.helicsCloseLibrary()
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
