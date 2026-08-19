#!/usr/bin/env python3
"""Run the create-once GridEval G2 OpenDER component conformance probe."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

import matplotlib
import numpy
import opender
import pandas
from opender.der_bess import DER_BESS

from device import ScheduledOpenDERBESS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual: float, expected: float, tolerance: float = 1e-9) -> bool:
    return bool(abs(float(actual) - expected) <= tolerance)


def json_default(value: Any) -> Any:
    if isinstance(value, numpy.generic):
        return value.item()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def bess_output(
    demand_kw: float, active_limit: float | None = None
) -> dict[str, Any]:
    opender.DER.t_s = 10
    device = DER_BESS()
    device.der_input.freq_hz = 60
    device.der_file.NP_P_MAX_CHARGE = 80_000
    if active_limit is not None:
        device.der_file.AP_LIMIT_ENABLE = "ENABLED"
        device.der_file.AP_LIMIT = active_limit
    device.update_der_input(v_pu=1.0, p_dem_kw=demand_kw)
    device.run()
    return {
        "demand_kw": demand_kw,
        "p_out_kw": float(device.p_out_kw),
        "q_out_kvar": float(device.q_out_kvar),
        "status": device.der_status,
    }


def scenario_sign_and_limit() -> dict[str, Any]:
    discharge = bess_output(100.0, 0.5)
    charge = bess_output(-50.0, 0.5)
    return {
        "description": (
            "Positive output is BESS discharge/injection; negative output "
            "is BESS charge/absorption."
        ),
        "trace": [discharge, charge],
        "checks": {
            "positive_discharge_limited_to_50kw": close(
                discharge["p_out_kw"], 50.0
            ),
            "negative_charge_preserved_at_minus_50kw": close(
                charge["p_out_kw"], -50.0
            ),
            "zero_reactive_output": all(
                close(row["q_out_kvar"], 0.0)
                for row in (discharge, charge)
            ),
        },
    }


def scenario_reactive_modes() -> dict[str, Any]:
    trace = []
    for constant_q in (0.44, -0.44):
        opender.DER.t_s = 10_000
        device = DER_BESS()
        device.der_file.CONST_Q_MODE_ENABLE = "ENABLED"
        device.der_file.CONST_Q = constant_q
        device.update_der_input(
            v_pu=1.0, p_dem_kw=50.0, f=60.0
        )
        device.run()
        trace.append(
            {
                "mode": "constant_q",
                "constant_q_pu": constant_q,
                "p_out_kw": float(device.p_out_kw),
                "q_out_kvar": float(device.q_out_kvar),
            }
        )

    device = opender.DER()
    device.der_file.QV_MODE_ENABLE = "ENABLED"
    device.der_file.QV_CURVE_V1 = 0.92
    device.der_file.QV_CURVE_V2 = 0.98
    device.der_file.QV_CURVE_V3 = 1.02
    device.der_file.QV_CURVE_V4 = 1.08
    device.der_file.QV_CURVE_Q1 = 0.44
    device.der_file.QV_CURVE_Q2 = 0.0
    device.der_file.QV_CURVE_Q3 = 0.0
    device.der_file.QV_CURVE_Q4 = -0.44
    device.der_file.NP_Q_MAX_INJ = 44_000
    device.der_file.NP_Q_MAX_ABS = 44_000
    device.update_der_input(v_pu=0.95, p_dc_kw=100.0, f=60.0)
    device.run()
    trace.append(
        {
            "mode": "volt_var_q_priority",
            "v_pu": 0.95,
            "p_out_kw": float(device.p_out_kw),
            "q_out_kvar": float(device.q_out_kvar),
            "apparent_power_kva": float(
                (device.p_out_kw**2 + device.q_out_kvar**2) ** 0.5
            ),
        }
    )
    return {
        "trace": trace,
        "checks": {
            "constant_q_injection": close(
                trace[0]["q_out_kvar"], 44.0
            ),
            "constant_q_absorption": close(
                trace[1]["q_out_kvar"], -44.0
            ),
            "volt_var_q_priority": (
                close(trace[2]["p_out_kw"], 97.5, 0.05)
                and close(trace[2]["q_out_kvar"], 22.0, 0.05)
            ),
            "capability_limited_to_100kva": (
                trace[2]["apparent_power_kva"] <= 100.01
            ),
        },
    }


def scenario_bess_ramp() -> dict[str, Any]:
    opender.DER.t_s = 1
    device = DER_BESS()
    device.der_file.NP_BESS_P_RAMP_TIME = 10
    device.update_der_input(v_pu=1.0, p_dem_kw=0.0, f=60.0)
    device.run()
    trace = [{"time_s": 0, "p_out_kw": float(device.p_out_kw)}]
    device.update_der_input(p_dem_kw=100.0)
    for second in range(1, 6):
        device.run()
        trace.append(
            {"time_s": second, "p_out_kw": float(device.p_out_kw)}
        )
    return {
        "trace": trace,
        "checks": {
            "ten_kw_per_second_ramp": all(
                close(row["p_out_kw"], row["time_s"] * 10.0)
                for row in trace
            )
        },
    }


def scenario_setting_delay() -> dict[str, Any]:
    opender.DER.t_s = 1
    device = DER_BESS()
    device.der_file.NP_SET_EXE_TIME = 3
    device.der_file.AP_RT = 0
    device.update_der_input(v_pu=1.0, p_dem_kw=100.0, f=60.0)
    device.run()
    trace = [
        {
            "time_s": 0,
            "p_out_kw": float(device.p_out_kw),
            "active_limit_executed": bool(
                device.exec_delay.ap_limit_enable_exec
            ),
        }
    ]
    device.der_file.AP_LIMIT_ENABLE = "ENABLED"
    device.der_file.AP_LIMIT = 0.5
    for second in range(1, 5):
        device.run()
        trace.append(
            {
                "time_s": second,
                "p_out_kw": float(device.p_out_kw),
                "active_limit_executed": bool(
                    device.exec_delay.ap_limit_enable_exec
                ),
            }
        )
    expected = [100.0, 100.0, 100.0, 50.0, 50.0]
    observed = [row["p_out_kw"] for row in trace]
    upstream_check = all(
        close(actual, wanted)
        for actual, wanted in zip(observed, expected)
    )

    wrapper = ScheduledOpenDERBESS(step_s=1)
    wrapper.model.der_file.AP_RT = 0
    wrapper_trace = []
    output, applied = wrapper.step(
        v_pu=1.0, frequency_hz=60.0, demand_kw=100.0
    )
    wrapper_trace.append(
        {
            **output.__dict__,
            "applied_settings": applied,
        }
    )
    scheduled = wrapper.schedule_settings(
        3,
        AP_LIMIT_ENABLE="ENABLED",
        AP_LIMIT=0.5,
    )
    for _ in range(4):
        output, applied = wrapper.step(
            v_pu=1.0,
            frequency_hz=60.0,
            demand_kw=100.0,
        )
        wrapper_trace.append(
            {
                **output.__dict__,
                "applied_settings": applied,
            }
        )
    wrapper_expected = [100.0, 100.0, 100.0, 50.0, 50.0]
    wrapper_observed = [
        row["p_out_kw"] for row in wrapper_trace
    ]
    wrapper_check = all(
        close(actual, wanted)
        for actual, wanted in zip(
            wrapper_observed, wrapper_expected
        )
    )
    return {
        "configured_setting_execution_delay_s": 3,
        "upstream_trace": trace,
        "upstream_expected_p_out_kw": expected,
        "upstream_observed_p_out_kw": observed,
        "wrapper_schedule": scheduled,
        "wrapper_trace": wrapper_trace,
        "wrapper_expected_p_out_kw": wrapper_expected,
        "wrapper_observed_p_out_kw": wrapper_observed,
        "checks": {
            "upstream_delay_defect_reproduced": not upstream_check,
            "v3_wrapper_delays_setting_three_seconds": wrapper_check,
        },
        "diagnosis": (
            "SettingExecutionDelay passes one mutable DERCommonFileFormat "
            "object to TimeDelay; in-place changes are visible through both "
            "the held and current references, so the configured delay is "
            "bypassed."
        ),
    }


def scenario_trip() -> dict[str, Any]:
    opender.DER.t_s = 0.01
    device = opender.DER(
        NP_ABNORMAL_OP_CAT="CAT_II",
        MC_ENABLE=False,
        MC_LVRT_V1=0.5,
        MC_HVRT_V1=1.1,
    )
    device.update_der_input(v_pu=1.0, p_dc_pu=1.0, f=60.0)
    device.run()
    baseline = {
        "v_pu": 1.0,
        "status": device.der_status,
        "p_out_kw": float(device.p_out_kw),
    }
    device.update_der_input(v_pu=1.21, p_dc_pu=1.0)
    transition = []
    for step in range(1, 26):
        device.run()
        if step in (1, 2, 5, 10, 16, 20, 25):
            transition.append(
                {
                    "elapsed_s": step * opender.DER.t_s,
                    "v_pu": 1.21,
                    "status": device.der_status,
                    "p_out_kw": float(device.p_out_kw),
                }
            )
    first_overvoltage = transition[0]
    final = transition[-1]
    return {
        "configured_ov2_trip_time_s": device.der_file.OV2_TRIP_T,
        "trace": [baseline, *transition],
        "checks": {
            "normal_voltage_operates": (
                baseline["status"] == "Continuous Operation"
            ),
            "severe_overvoltage_enters_cease_state": (
                first_overvoltage["status"] == "Cease to Energize"
            ),
            "severe_overvoltage_trips_after_configured_delay": (
                final["status"] == "Trip"
                and close(final["p_out_kw"], 0.0)
                and final["elapsed_s"] >= device.der_file.OV2_TRIP_T
            ),
        },
    }


def scenario_soc() -> dict[str, Any]:
    opender.DER.t_s = 10
    device = DER_BESS()
    device.der_file.NP_BESS_CAPACITY = 25_000
    device.der_file.NP_P_MAX_CHARGE = 100_000
    device.update_der_input(v_pu=1.0, p_dem_kw=50.0, f=60.0)
    trace = []
    for step in range(1, 7):
        device.run()
        trace.append(
            {
                "step": step,
                "mode": "discharge",
                "p_out_kw": float(device.p_out_kw),
                "soc": float(device.bess_soc),
            }
        )
    device.update_der_input(p_dem_kw=-50.0)
    for step in range(7, 13):
        device.run()
        trace.append(
            {
                "step": step,
                "mode": "charge",
                "p_out_kw": float(device.p_out_kw),
                "soc": float(device.bess_soc),
            }
        )
    discharge_soc = [row["soc"] for row in trace[:6]]
    charge_soc = [row["soc"] for row in trace[6:]]
    return {
        "trace": trace,
        "checks": {
            "soc_stays_bounded": all(
                0.0 <= row["soc"] <= 1.0 for row in trace
            ),
            "discharge_decreases_soc_after_first_step": all(
                later < earlier
                for earlier, later in zip(
                    discharge_soc[1:], discharge_soc[2:]
                )
            ),
            "charge_increases_soc_after_transition_step": all(
                later > earlier
                for earlier, later in zip(charge_soc, charge_soc[1:])
            ),
        },
    }


def run_scenario(function: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        result = function()
        result["executed"] = True
        result["passed"] = all(result["checks"].values())
        return result
    except Exception as exc:
        return {
            "executed": False,
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "checks": {},
        }


def command(
    argv: list[str], cwd: Path | None = None
) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env={
            **os.environ,
            "MPLCONFIGDIR": os.environ.get(
                "MPLCONFIGDIR", "/tmp/grideval-opender-mpl"
            ),
            "MPLBACKEND": os.environ.get("MPLBACKEND", "Agg"),
            "PYTHONHASHSEED": "0",
        },
    )
    return {
        "argv": argv,
        "returncode": completed.returncode,
        "output": completed.stdout,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    pytest_result = command(
        [
            os.sys.executable,
            "-m",
            "pytest",
            "-q",
            str(source / "tests"),
        ]
    )
    (output_dir / "upstream_pytest.log").write_text(
        pytest_result["output"], encoding="utf-8"
    )
    official_example = command(
        [os.sys.executable, str(source / "main.py")],
        cwd=source,
    )
    (output_dir / "official_main_example.log").write_text(
        official_example["output"], encoding="utf-8"
    )
    commit = command(
        ["git", "rev-parse", "HEAD"], cwd=source
    )["output"].strip()
    tree = command(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=source
    )["output"].strip()
    freeze = command([os.sys.executable, "-m", "pip", "freeze"])

    scenarios = {
        "bess_sign_and_active_limit": run_scenario(
            scenario_sign_and_limit
        ),
        "reactive_modes_and_capability": run_scenario(
            scenario_reactive_modes
        ),
        "bess_ramp": run_scenario(scenario_bess_ramp),
        "setting_execution_delay": run_scenario(
            scenario_setting_delay
        ),
        "voltage_trip": run_scenario(scenario_trip),
        "bess_soc": run_scenario(scenario_soc),
    }
    upstream_passed = (
        pytest_result["returncode"] == 0
        and "565 passed" in pytest_result["output"]
    )
    passed_match = re.search(r"(\d+) passed", pytest_result["output"])
    official_example_passed = official_example["returncode"] == 0
    required_checks_pass = all(
        scenario["passed"] for scenario in scenarios.values()
    )
    g2_pass = upstream_passed and required_checks_pass
    result = {
        "schema_version": "1.0",
        "gate": "G2",
        "source": {
            "repository": "https://github.com/epri-dev/OpenDER.git",
            "commit": commit,
            "tree": tree,
            "setup_py_sha256": sha256(source / "setup.py"),
            "version": "2.2.0",
            "runner_sha256": sha256(Path(__file__).resolve()),
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "pandas": pandas.__version__,
            "matplotlib": matplotlib.__version__,
            "pip_freeze": freeze["output"].splitlines(),
        },
        "api": {
            "DER.update_der_input": str(
                inspect.signature(opender.DER.update_der_input)
            ),
            "DER.run": str(inspect.signature(opender.DER.run)),
            "DER.get_der_output": str(
                inspect.signature(opender.DER.get_der_output)
            ),
            "DER_BESS.update_der_input": str(
                inspect.signature(DER_BESS.update_der_input)
            ),
            "DER_BESS.bess_soc": "read-only property",
        },
        "upstream_tests": {
            "returncode": pytest_result["returncode"],
            "passed": upstream_passed,
            "passed_count": (
                int(passed_match.group(1)) if passed_match else None
            ),
            "summary": (
                f"{passed_match.group(1)} passed"
                if passed_match
                else "pytest summary unavailable"
            ),
            "log": "upstream_pytest.log",
        },
        "official_trip_enter_service_example": {
            "entrypoint": "main.py",
            "headless_backend": "Agg",
            "returncode": official_example["returncode"],
            "passed": official_example_passed,
            "log": "official_main_example.log",
        },
        "scenarios": scenarios,
        "required_checks_pass": required_checks_pass,
        "g2_pass": g2_pass and official_example_passed,
        "verdict": (
            (
                "PASS WITH WRAPPER LIMITATION: use the v3 setting queue and "
                "keep OpenDER NP_SET_EXE_TIME disabled"
            )
            if g2_pass and official_example_passed
            else (
                "HOLD: upstream suite passes, but configured setting "
                "execution delay is bypassed for in-place setting changes"
            )
        ),
        "scope_limit": (
            "Standalone behavioral-device component evidence only; no "
            "GridLAB-D, NATIG, DNP3, or attack integration."
        ),
    }
    (output_dir / "opender_component_conformance.json").write_text(
        json.dumps(
            result,
            indent=2,
            allow_nan=False,
            default=json_default,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"upstream_passed={upstream_passed} "
        f"required_checks_pass={required_checks_pass} "
        f"g2_pass={result['g2_pass']} verdict={result['verdict']}"
    )
    return 0 if result["g2_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
