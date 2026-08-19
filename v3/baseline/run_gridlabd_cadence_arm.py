#!/usr/bin/env python3
"""Run one immutable IEEE-123 GridLAB-D/controller cadence arm.

This executes inside the pinned ``docker-cosim`` image. It creates a temporary
overlay of the real Feeder A model, preserving the source tree, and removes
the GridPACK voltage subscriptions so the distribution-side timing and EV4
command path can be isolated. The source meter voltages remain unchanged.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import helics as h


ARMS = {
    "frozen60": {
        "gridlabd_helics_period_s": 60,
        "gridlabd_minimum_timestep_s": 60,
        "controller_helics_period_s": 60,
    },
    "physical10": {
        "gridlabd_helics_period_s": 10,
        "gridlabd_minimum_timestep_s": 10,
        "controller_helics_period_s": 10,
    },
}
START_TIME = "2013-08-28 07:00:00"
STOP_TIME = "2013-08-28 07:04:00"
DURATION_S = 240
# This is a diagnostic pulse, not an attacker maximum. The first 1.5 MW
# attempt produced a preserved FBS convergence failure in the isolated feeder.
# A +200 kW step is large enough to measure while remaining near the feeder's
# nominal EV scale.
HIGH_COMMAND_W = 400_000.0
NOMINAL_COMMAND_W = 200_000.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_model(
    repo: Path, model_dir: Path, arm_name: str, arm: dict[str, int]
) -> dict[str, Any]:
    source_dir = repo / "examples/2bus-13bus"
    source_glm = source_dir / "1c_IEEE_123_feeder.glm"
    source_helics = source_dir / "mainglm.json"

    for child in source_dir.iterdir():
        if child.name in {source_glm.name, source_helics.name}:
            continue
        if child.name == "output":
            (model_dir / "output").mkdir()
            continue
        # These are retained run products in the source directory. Linking
        # them would redirect recorder/save writes into the read-only source
        # mount rather than the temporary model sandbox.
        if child.suffix.lower() in {".csv", ".log", ".xml", ".png"}:
            continue
        if child.name.startswith("core."):
            continue
        (model_dir / child.name).symlink_to(child)

    glm_text = source_glm.read_text(encoding="utf-8")
    glm_text, minimum_count = re.subn(
        r"#set\s+minimum_timestep=\d+(?:\.\d+)?;",
        (
            "#set minimum_timestep="
            f"{arm['gridlabd_minimum_timestep_s']}.000000;"
        ),
        glm_text,
        count=1,
    )
    glm_text, stop_count = re.subn(
        r"stoptime\s+'[^']+';",
        f"stoptime '{STOP_TIME}';",
        glm_text,
        count=1,
    )
    if minimum_count != 1 or stop_count != 1:
        raise RuntimeError(
            "Could not create unambiguous GLM cadence/stoptime overlay"
        )
    ev4_recorder_pattern = (
        "property measured_voltage_C,constant_power_C,measured_frequency_C;\n"
        "        interval 1200;\n"
        "        file output/1c_IEEE_123_feeder_0_EV4.csv;"
    )
    ev4_recorder_replacement = (
        "property measured_voltage_C,constant_power_C,measured_frequency_C;\n"
        f"        interval {arm['gridlabd_minimum_timestep_s']};\n"
        "        file output/1c_IEEE_123_feeder_0_EV4.csv;"
    )
    if glm_text.count(ev4_recorder_pattern) != 1:
        raise RuntimeError("Could not locate the EV4 recorder uniquely")
    glm_text = glm_text.replace(
        ev4_recorder_pattern, ev4_recorder_replacement
    )
    generated_glm = model_dir / source_glm.name
    generated_glm.write_text(glm_text, encoding="utf-8")

    helics_config = json.loads(source_helics.read_text(encoding="utf-8"))
    helics_config["name"] = f"IEEE123_cadence_{arm_name}"
    helics_config["coreName"] = f"IEEE123 cadence {arm_name} core"
    helics_config["period"] = arm["gridlabd_helics_period_s"]
    helics_config["logfile"] = f"gridlabd_helics_{arm_name}.log"
    # Isolate the distribution feeder. Node650 retains its source-model
    # voltage initialization; no transmission-side claim is made by this test.
    helics_config["subscriptions"] = []
    helics_config["endpoints"] = [
        endpoint
        for endpoint in helics_config["endpoints"]
        if endpoint["key"] == "gld_hlc_conn/EV4"
    ]
    generated_helics = model_dir / source_helics.name
    generated_helics.write_text(
        json.dumps(helics_config, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "source_glm_sha256": sha256(source_glm),
        "source_helics_config_sha256": sha256(source_helics),
        "generated_glm_sha256": sha256(generated_glm),
        "generated_helics_config_sha256": sha256(generated_helics),
        "generated_helics_config": helics_config,
    }


def controller_config(
    path: Path, arm_name: str, arm: dict[str, int], broker_address: str
) -> None:
    config = {
        "coreInit": "--federates=1",
        "coreName": f"cadence_controller_{arm_name}_core",
        "coreType": "zmq",
        "broker": broker_address,
        "name": f"cadence_controller_{arm_name}",
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
                "key": "EV_Controller/EV4",
                "destination": "gld_hlc_conn/EV4",
                "global": True,
                "type": "string",
            }
        ],
        # The frozen v2 controller registers these switch publications even
        # though its Python loop does not publish values to them. Retaining
        # them prevents the feeder's optional subscriptions from becoming
        # structurally unconnected in full-coupling probes.
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


def normalized_diagnostics(text: str, temp_root: Path) -> list[str]:
    lines = []
    root_text = str(temp_root)
    for line in text.splitlines():
        if re.search(r"\b(WARNING|ERROR|FATAL|exception|failed)\b", line, re.I):
            lines.append(line.replace(root_text, "<TMP>")[:1000])
    return lines[-100:]


def ev4_recorder_rows(path: Path) -> list[dict[str, Any]]:
    header = None
    data_lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# timestamp,"):
            header = line[2:].split(",")
        elif line and not line.startswith("#"):
            data_lines.append(line)
    if header is None:
        raise RuntimeError("EV4 recorder header was not found")
    rows = []
    for values in csv.reader(data_lines):
        row = dict(zip(header, values))
        timestamp = row["timestamp"]
        time_text = timestamp.split()[1]
        hours, minutes, seconds = [
            int(value) for value in time_text.split(":")
        ]
        start_hours, start_minutes, start_seconds = (7, 0, 0)
        simulation_time_s = (
            (hours - start_hours) * 3600
            + (minutes - start_minutes) * 60
            + (seconds - start_seconds)
        )
        power = complex(row["constant_power_C"].replace("i", "j"))
        rows.append(
            {
                "simulation_time_s": simulation_time_s,
                "constant_power_c_w": float(power.real),
                "measured_voltage_c": row["measured_voltage_C"],
                "measured_frequency_c_hz": float(
                    row["measured_frequency_C"]
                ),
            }
        )
    return rows


def run_arm(repo: Path, output_dir: Path, arm_name: str) -> dict[str, Any]:
    arm = ARMS[arm_name]
    with tempfile.TemporaryDirectory(prefix=f"grideval-{arm_name}-") as temp:
        temp_root = Path(temp)
        model_dir = temp_root / "model"
        model_dir.mkdir()
        overlay = prepare_model(repo, model_dir, arm_name, arm)

        broker_name = f"gridlabd_cadence_{arm_name}_broker"
        broker = h.helicsCreateBroker("zmq", broker_name, "-f 2")
        broker_address = h.helicsBrokerGetAddress(broker)
        controller_path = temp_root / "controller.json"
        controller_config(controller_path, arm_name, arm, broker_address)

        env = os.environ.copy()
        env["HELICS_BROKER"] = broker_address
        gridlabd = subprocess.Popen(
            ["gridlabd", "1c_IEEE_123_feeder.glm"],
            cwd=model_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
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
            endpoint = h.helicsFederateGetEndpointByIndex(fed, 0)
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
                total_real_w = float(sum(value.real for value in phase_values))
                command_w = None
                if granted == 60.0:
                    command_w = HIGH_COMMAND_W
                elif granted == 120.0:
                    command_w = NOMINAL_COMMAND_W
                if command_w is not None:
                    h.helicsEndpointSendBytes(
                        endpoint, f"{command_w:.1f}+0.0j"
                    )
                controller_events.append(
                    {
                        "logical_request_time_s": logical_t,
                        "granted_time_s": granted,
                        "phase_real_power_w": [
                            float(value.real) for value in phase_values
                        ],
                        "total_real_power_w": total_real_w,
                        "input_updated": input_updated,
                        "ev4_command_w": command_w,
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

        try:
            gridlabd_output, _ = gridlabd.communicate(timeout=45)
        except subprocess.TimeoutExpired:
            gridlabd.kill()
            gridlabd_output, _ = gridlabd.communicate()
            run_error = run_error or "GridLAB-D did not exit within 45 seconds"

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

        result = {
            "schema_version": "1.0",
            "arm": arm_name,
            "arm_config": arm,
            "model": "IEEE 123 Feeder A isolated from GridPACK",
            "simulation_start": START_TIME,
            "simulation_stop": STOP_TIME,
            "simulation_duration_s": DURATION_S,
            "commands": {
                "high": {"send_time_s": 60, "ev4_w": HIGH_COMMAND_W},
                "nominal": {
                    "send_time_s": 120,
                    "ev4_w": NOMINAL_COMMAND_W,
                },
            },
            "identity": {
                "runner_sha256": sha256(Path(__file__).resolve()),
                **{
                    key: value
                    for key, value in overlay.items()
                    if key.endswith("_sha256")
                },
                "controller_config_sha256": sha256(controller_path),
                "helics_version": h.helicsGetVersion(),
            },
            "overlay_config": overlay["generated_helics_config"],
            "controller_events": controller_events,
            "gridlabd_ev4_internal_trace": recorder_rows,
            "gridlabd_returncode": gridlabd.returncode,
            "gridlabd_diagnostics": normalized_diagnostics(
                gridlabd_output, temp_root
            ),
            "run_error": run_error,
            "success": (
                run_error is None
                and gridlabd.returncode == 0
                and bool(controller_events)
                and bool(recorder_rows)
            ),
            "scope_limit": (
                "This isolates Feeder A with source-model fixed swing voltage "
                "and does not validate GridPACK coupling or transmission "
                "response."
            ),
        }
        result_path = output_dir / "gridlabd_cadence_arm.json"
        result_path.write_text(
            json.dumps(result, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("/workspace"))
    parser.add_argument("--arm", choices=sorted(ARMS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    result = run_arm(args.repo.resolve(), output_dir, args.arm)
    print(
        f"{args.arm}: success={result['success']} "
        f"gridlabd_returncode={result['gridlabd_returncode']} "
        f"events={len(result['controller_events'])} "
        f"error={result['run_error']}"
    )
    h.helicsCloseLibrary()
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
