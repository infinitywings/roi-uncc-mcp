#!/usr/bin/env python3
"""Replay a captured GridPACK voltage boundary against IEEE-123 Feeder A."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import helics as h

from run_full_coupling_cadence_arm import prepare_full_model, wait_process
from run_gridlabd_cadence_arm import (
    ARMS,
    DURATION_S,
    START_TIME,
    STOP_TIME,
    normalized_diagnostics,
    sha256,
)


BALANCED_V = (
    complex(138000.0, 0.0),
    complex(-69000.0, -119511.45),
    complex(-69000.0, 119511.45),
)
CAPTURED_COPHASAL_V = (
    complex(138000.0, 0.0),
    complex(137999.42091810756, -0.3343322291079476),
    complex(137998.89009471014, -0.585079150397072),
)


def publisher_config(path: Path, profile: str, broker_address: str) -> None:
    config = {
        "coreInit": "--federates=1",
        "coreName": f"voltage_replay_{profile}_core",
        "coreType": "zmq",
        "broker": broker_address,
        "name": f"voltage_replay_{profile}",
        "period": 5,
        "log_level": "warning",
        "publications": [
            {
                "global": True,
                "key": f"gridpack/V{phase}",
                "type": "complex",
                "unit": "V",
            }
            for phase in ("a", "b", "c")
        ],
        "subscriptions": [
            {
                "global": True,
                "key": f"gld_hlc_conn/S{phase}",
                "type": "complex",
                "unit": "VA",
            }
            for phase in ("a", "b", "c")
        ],
    }
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def publish_voltages(
    publications: list[Any], values: tuple[complex, complex, complex]
) -> None:
    for publication, value in zip(publications, values):
        h.helicsPublicationPublishComplex(
            publication, float(value.real), float(value.imag)
        )


def run_replay(
    repo: Path, output_dir: Path, profile: str
) -> dict[str, Any]:
    arm = ARMS["frozen60"]
    with tempfile.TemporaryDirectory(
        prefix=f"grideval-voltage-replay-{profile}-"
    ) as temp:
        temp_root = Path(temp)
        model_dir = temp_root / "model"
        model_dir.mkdir()
        overlay = prepare_full_model(repo, model_dir, "frozen60", arm)

        broker_name = f"voltage_replay_{profile}_broker"
        broker = h.helicsCreateBroker("zmq", broker_name, "-f 2")
        broker_address = h.helicsBrokerGetAddress(broker)
        config_path = temp_root / "publisher.json"
        publisher_config(config_path, profile, broker_address)

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
        trace = []
        run_error = None
        try:
            fed = h.helicsCreateValueFederateFromConfig(str(config_path))
            publications = [
                h.helicsFederateGetPublicationByIndex(fed, index)
                for index in range(h.helicsFederateGetPublicationCount(fed))
            ]
            subscriptions = [
                h.helicsFederateGetInputByIndex(fed, index)
                for index in range(h.helicsFederateGetInputCount(fed))
            ]
            for subscription in subscriptions:
                h.helicsInputSetDefaultComplex(subscription, 0.0, 0.0)
            h.helicsFederateEnterExecutingMode(fed)
            publish_voltages(publications, BALANCED_V)

            granted = 0.0
            for target in range(5, DURATION_S + 1, 5):
                granted = float(h.helicsFederateRequestTime(fed, target))
                if profile == "captured_cophasal" and granted == 55:
                    publish_voltages(publications, CAPTURED_COPHASAL_V)
                loads = [
                    h.helicsInputGetComplex(subscription)
                    for subscription in subscriptions
                ]
                trace.append(
                    {
                        "requested_time_s": target,
                        "granted_time_s": granted,
                        "published_profile": (
                            "captured_cophasal"
                            if profile == "captured_cophasal"
                            and granted >= 55
                            else "balanced"
                        ),
                        "feeder_phase_power_va": [
                            {"real": value.real, "imag": value.imag}
                            for value in loads
                        ],
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
            process_error = None
        except subprocess.TimeoutExpired:
            gridlabd.kill()
            gridlabd_output, _ = gridlabd.communicate()
            process_error = "GridLAB-D did not exit within 45 seconds"

        h.helicsBrokerDisconnect(broker)
        h.helicsBrokerFree(broker)
        diagnostics = normalized_diagnostics(gridlabd_output, temp_root)
        expected_success = profile == "balanced"
        observed_success = (
            run_error is None
            and process_error is None
            and gridlabd.returncode == 0
        )
        result = {
            "schema_version": "1.0",
            "profile": profile,
            "model": "IEEE-123 Feeder A with replayed source voltages",
            "simulation_start": START_TIME,
            "simulation_stop": STOP_TIME,
            "simulation_duration_s": DURATION_S,
            "voltage_profiles": {
                "balanced_v": [
                    {"real": value.real, "imag": value.imag}
                    for value in BALANCED_V
                ],
                "captured_cophasal_v": [
                    {"real": value.real, "imag": value.imag}
                    for value in CAPTURED_COPHASAL_V
                ],
                "captured_profile_publish_time_s": (
                    55 if profile == "captured_cophasal" else None
                ),
                "feeder_first_receive_time_s": 60,
            },
            "identity": {
                "runner_sha256": sha256(Path(__file__).resolve()),
                "publisher_config_sha256": sha256(config_path),
                "helics_version": h.helicsGetVersion(),
                **overlay,
            },
            "boundary_trace": trace,
            "gridlabd_returncode": gridlabd.returncode,
            "gridlabd_diagnostics": diagnostics,
            "run_error": run_error,
            "process_error": process_error,
            "observed_success": observed_success,
            "expected_success": expected_success,
            "hypothesis_confirmed": observed_success == expected_success,
        }
        (output_dir / "voltage_boundary_replay.json").write_text(
            json.dumps(result, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("/workspace"))
    parser.add_argument(
        "--profile",
        choices=("balanced", "captured_cophasal"),
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    result = run_replay(
        args.repo.resolve(), output_dir, args.profile
    )
    print(
        f"{args.profile}: observed_success={result['observed_success']} "
        f"returncode={result['gridlabd_returncode']} "
        f"hypothesis_confirmed={result['hypothesis_confirmed']} "
        f"error={result['run_error'] or result['process_error']}"
    )
    h.helicsCloseLibrary()
    return 0 if result["hypothesis_confirmed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
