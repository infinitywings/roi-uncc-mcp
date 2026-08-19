#!/usr/bin/env python3
"""Run one create-once GridLAB-D/OpenDER G3 physical-loop arm.

This runner is intended for the pinned local ``docker-cosim`` image.  It makes
an ephemeral copy-on-write model from the canonical Feeder A source, removes
the legacy EV4 storage implementation, adds one signed constant-power coupling
object, and exchanges voltage and P/Q through HELICS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import helics as h
import opender
from opender import DERCommonFileFormatBESS

from device import ScheduledOpenDERBESS


START_TIME = "2013-08-28 07:00:00"
STOP_TIME = "2013-08-28 07:14:00"
DURATION_S = 840
INTERNAL_DEVICE_STEP_S = 1
NOMINAL_VOLTAGE_V = 2401.7771
RATING_VA = 200_000.0
ENERGY_CAPACITY_WH = 205_000.0
SCENARIOS = ("null", "pulse")
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
PHYSICAL_RECORDER_NAMES = (
    "g3_der_ev4_coupling.csv",
    "g3_node650_phase_c.csv",
    "g3_swEV4_status.csv",
    "1c_IEEE_123_feeder_0_EV4.csv",
)
IMAGE_ID = (
    "sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7"
)
OPENDER_COMMIT = "fe7877c664bc6c5eb3832499bf05e0f1dd1825c8"
CANONICAL_GLM_SHA256 = (
    "553eb2c4a3082057bba78249340adbd9f1be9d9a639206aec242e793f54ef888"
)
CANONICAL_CONFIG_SHA256 = (
    "b12a953b4182db0de97ca0d2a160919fcca642d68219d7ccd9fc5bdf718454f2"
)
LEGACY_START = (
    "///////////////////////////////////////////////// EV_4 Storage "
    "///////////////////////////////////////////////////////////////////////////////////"
)
LEGACY_END = (
    "////////////////////////////////////////////////////////////////////////////////////////////\n"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def schedule(time_s: int, scenario: str) -> tuple[float, float, str]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    for name, start, stop, p_kw, q_kvar in SCHEDULE_WINDOWS:
        if start <= time_s < stop:
            if scenario == "null":
                return 0.0, 0.0, name
            return p_kw, q_kvar, name
    return 0.0, 0.0, "terminal"


def scenario_schedule(scenario: str) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "start_s": start,
            "stop_s": stop,
            "p_kw": p_kw if scenario == "pulse" else 0.0,
            "q_kvar": q_kvar if scenario == "pulse" else 0.0,
        }
        for name, start, stop, p_kw, q_kvar in SCHEDULE_WINDOWS
    ]


def link_inputs(source_dir: Path, model_dir: Path) -> None:
    excluded = {
        "1c_IEEE_123_feeder.glm",
        "mainglm.json",
        "output",
    }
    for child in source_dir.iterdir():
        if child.name in excluded:
            continue
        if child.suffix.lower() in {".csv", ".log", ".xml", ".png"}:
            continue
        if child.name.startswith("core."):
            continue
        (model_dir / child.name).symlink_to(child)
    (model_dir / "output").mkdir()


def coupling_glm(step_s: int) -> str:
    return f"""{LEGACY_START}
// G3 v3-only replacement: the legacy battery/inverter tree is absent.
object load {{
    name DER_EV4_BESS_COUPLING;
    parent l92;
    phases CN;
    nominal_voltage {NOMINAL_VOLTAGE_V};
    constant_power_C 0+0j;
    object recorder {{
        property measured_voltage_C,constant_power_C;
        interval {step_s};
        file output/g3_der_ev4_coupling.csv;
    }};
}};

object recorder {{
    parent Node650;
    property measured_power_C;
    interval {step_s};
    file output/g3_node650_phase_c.csv;
}};

object recorder {{
    parent swEV4;
    property status;
    interval {step_s};
    file output/g3_swEV4_status.csv;
}};
{LEGACY_END}"""


def prepare_model(
    repo: Path, model_dir: Path, step_s: int, arm_name: str
) -> dict[str, Any]:
    source_dir = repo / "examples/2bus-13bus"
    source_glm = source_dir / "1c_IEEE_123_feeder.glm"
    source_config = source_dir / "mainglm.json"
    if sha256(source_glm) != CANONICAL_GLM_SHA256:
        raise RuntimeError("Canonical experimental Feeder A GLM hash changed")
    if sha256(source_config) != CANONICAL_CONFIG_SHA256:
        raise RuntimeError("Canonical experimental Feeder A config hash changed")
    link_inputs(source_dir, model_dir)

    text = source_glm.read_text(encoding="utf-8")
    text, minimum_count = re.subn(
        r"#set\s+minimum_timestep=\d+(?:\.\d+)?;",
        f"#set minimum_timestep={step_s}.000000;",
        text,
        count=1,
    )
    text, stop_count = re.subn(
        r"stoptime\s+'[^']+';", f"stoptime '{STOP_TIME}';", text, count=1
    )
    start_index = text.find(LEGACY_START)
    if start_index < 0:
        raise RuntimeError("Unique EV4 storage start marker was not found")
    end_index = text.find(LEGACY_END, start_index + len(LEGACY_START))
    if end_index < 0:
        raise RuntimeError("Unique EV4 storage end marker was not found")
    end_index += len(LEGACY_END)
    legacy_text = text[start_index:end_index]
    required_legacy_names = {
        "swEV4_storage",
        "storage_EV4",
        "battery_inv_EV4",
        "battery_EV4",
    }
    if not all(name in legacy_text for name in required_legacy_names):
        raise RuntimeError("EV4 legacy block did not contain every owner object")
    text = text[:start_index] + coupling_glm(step_s) + text[end_index:]
    if minimum_count != 1 or stop_count != 1:
        raise RuntimeError("Cadence/stoptime replacement was not unique")
    coupling_parent_pattern = (
        r"object load\s*\{\s*name DER_EV4_BESS_COUPLING;\s*"
        r"parent l92;"
    )
    if len(re.findall(coupling_parent_pattern, text)) != 1:
        raise RuntimeError(
            "OpenDER coupling object is not uniquely parented to l92"
        )

    recorder_pattern = (
        "property measured_voltage_C,constant_power_C,measured_frequency_C;\n"
        "        interval 1200;\n"
        "        file output/1c_IEEE_123_feeder_0_EV4.csv;"
    )
    recorder_replacement = (
        "property measured_voltage_C,constant_power_C,measured_frequency_C;\n"
        f"        interval {step_s};\n"
        "        file output/1c_IEEE_123_feeder_0_EV4.csv;"
    )
    if text.count(recorder_pattern) != 1:
        raise RuntimeError("EV4 terminal recorder was not located uniquely")
    text = text.replace(recorder_pattern, recorder_replacement)
    generated_glm = model_dir / source_glm.name
    generated_glm.write_text(text, encoding="utf-8")

    config = {
        "coreInit": "--federates=1",
        "coreName": f"g3_gridlabd_{arm_name}_core",
        "coreType": "zmq",
        "name": f"g3_gridlabd_{arm_name}",
        "period": step_s,
        "logfile": f"g3_gridlabd_{arm_name}_helics.log",
        "log_level": "warning",
        "publications": [
            {
                "global": True,
                "key": "g3_gridlabd/ev4_voltage_c",
                "type": "complex",
                "unit": "V",
                "info": {
                    "object": "l92",
                    "property": "measured_voltage_C",
                },
            },
            {
                "global": True,
                "key": "g3_gridlabd/der_coupling_load",
                "type": "complex",
                "unit": "VA",
                "info": {
                    "object": "DER_EV4_BESS_COUPLING",
                    "property": "constant_power_C",
                },
            },
            {
                "global": True,
                "key": "g3_gridlabd/source_power_c",
                "type": "complex",
                "unit": "VA",
                "info": {
                    "object": "Node650",
                    "property": "measured_power_C",
                },
            },
        ],
        "subscriptions": [
            {
                "required": True,
                "key": "g3_opender/feeder_load_va",
                "type": "complex",
                "unit": "VA",
                "info": {
                    "object": "DER_EV4_BESS_COUPLING",
                    "property": "constant_power_C",
                },
            }
        ],
        "endpoints": [],
    }
    config_text = json.dumps(config, sort_keys=True)
    if "swEV4" in config_text or config["endpoints"]:
        raise RuntimeError(
            "GridLAB-D HELICS config exposes legacy swEV4 control"
        )
    generated_config = model_dir / "mainglm.json"
    generated_config.write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "source_glm_sha256": sha256(source_glm),
        "source_config_sha256": sha256(source_config),
        "effective_glm_sha256": sha256(generated_glm),
        "effective_config_sha256": sha256(generated_config),
        "legacy_block_sha256": hashlib.sha256(
            legacy_text.encode("utf-8")
        ).hexdigest(),
        "legacy_owner_names": sorted(required_legacy_names),
        "effective_config": config,
    }


def adapter_config(path: Path, arm_name: str, step_s: int, broker: str) -> None:
    config = {
        "coreInit": "--federates=1",
        "coreName": f"g3_opender_{arm_name}_core",
        "coreType": "zmq",
        "broker": broker,
        "name": f"g3_opender_{arm_name}",
        "period": step_s,
        "log_level": "warning",
        "publications": [
            {
                "global": True,
                "key": "g3_opender/feeder_load_va",
                "type": "complex",
                "unit": "VA",
            }
        ],
        "subscriptions": [
            {
                "global": True,
                "key": key,
                "type": "complex",
                "unit": unit,
            }
            for key, unit in (
                ("g3_gridlabd/ev4_voltage_c", "V"),
                ("g3_gridlabd/der_coupling_load", "VA"),
                ("g3_gridlabd/source_power_c", "VA"),
            )
        ],
    }
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


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
        NP_AC_V_NOM=NOMINAL_VOLTAGE_V,
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
    device = ScheduledOpenDERBESS(
        step_s=INTERNAL_DEVICE_STEP_S, der_file_obj=settings
    )
    return device


def diagnostics(text: str, temp_root: Path) -> list[str]:
    root = str(temp_root)
    return [
        line.replace(root, "<TMP>")[:1000]
        for line in text.splitlines()
        if re.search(r"\b(WARNING|ERROR|FATAL|exception|failed)\b", line, re.I)
    ][-200:]


def parse_timestamp(timestamp: str) -> float:
    time_text = timestamp.split()[1]
    hours, minutes, seconds = time_text.split(":")
    return (
        (int(hours) - 7) * 3600
        + int(minutes) * 60
        + float(seconds)
    )


def parse_gridlabd_csv(
    path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    header: list[str] | None = None
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        if line.startswith("# timestamp,"):
            header = line[2:].split(",")
        elif line and not line.startswith("#"):
            if header is None:
                issues.append(
                    {
                        "line_number": line_number,
                        "reason": "data_before_header",
                        "line": line[:500],
                    }
                )
                continue
            try:
                values = next(csv.reader([line], strict=True))
            except (csv.Error, StopIteration) as exc:
                issues.append(
                    {
                        "line_number": line_number,
                        "reason": f"csv_error: {exc}",
                        "line": line[:500],
                    }
                )
                continue
            if len(values) != len(header):
                issues.append(
                    {
                        "line_number": line_number,
                        "reason": (
                            f"column_count_{len(values)}_expected_"
                            f"{len(header)}"
                        ),
                        "line": line[:500],
                    }
                )
                continue
            row: dict[str, Any] = dict(zip(header, values))
            try:
                row["simulation_time_s"] = parse_timestamp(
                    row["timestamp"]
                )
            except (IndexError, KeyError, TypeError, ValueError) as exc:
                issues.append(
                    {
                        "line_number": line_number,
                        "reason": f"timestamp_error: {exc}",
                        "line": line[:500],
                    }
                )
                continue
            for key, value in list(row.items()):
                if key in {"timestamp", "simulation_time_s"}:
                    continue
                try:
                    row[key] = complex(value.replace("i", "j"))
                except ValueError:
                    try:
                        row[key] = float(value)
                    except ValueError:
                        pass
            rows.append(row)
    if header is None:
        issues.append(
            {
                "line_number": None,
                "reason": "missing_timestamp_header",
                "line": None,
            }
        )
    return rows, issues


def serializable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serializable = []
    for row in rows:
        result = {}
        for key, value in row.items():
            if isinstance(value, complex):
                result[key] = {"real": value.real, "imag": value.imag}
            else:
                result[key] = value
        serializable.append(result)
    return serializable


def segment_summary(
    trace: list[dict[str, Any]], start: int, stop: int
) -> dict[str, Any]:
    rows = [row for row in trace if start <= row["time_s"] < stop]
    return {
        "start_s": start,
        "stop_s": stop,
        "count": len(rows),
        "mean_p_out_kw": sum(row["p_out_kw"] for row in rows) / len(rows),
        "mean_q_out_kvar": sum(row["q_out_kvar"] for row in rows) / len(rows),
        "mean_feeder_load_w": sum(row["feeder_load_w"] for row in rows)
        / len(rows),
        "mean_feeder_load_var": sum(row["feeder_load_var"] for row in rows)
        / len(rows),
    }


def run_arm(
    repo: Path, output_dir: Path, step_s: int, scenario: str
) -> dict[str, Any]:
    arm_name = f"{scenario}_coupling{step_s}"
    with tempfile.TemporaryDirectory(prefix=f"grideval-g3-{arm_name}-") as temp:
        temp_root = Path(temp)
        model_dir = temp_root / "model"
        model_dir.mkdir()
        overlay = prepare_model(repo, model_dir, step_s, arm_name)

        broker = h.helicsCreateBroker(
            "zmq", f"g3_{arm_name}_broker", "-f 2"
        )
        broker_address = h.helicsBrokerGetAddress(broker)
        adapter_path = temp_root / "g3_opender.json"
        adapter_config(adapter_path, arm_name, step_s, broker_address)
        env = os.environ.copy()
        env["HELICS_BROKER"] = broker_address
        gridlabd_log_path = temp_root / "gridlabd.log"
        gridlabd_log_handle = gridlabd_log_path.open(
            "w", encoding="utf-8"
        )
        process = subprocess.Popen(
            ["gridlabd", "1c_IEEE_123_feeder.glm"],
            cwd=model_dir,
            env=env,
            text=True,
            stdout=gridlabd_log_handle,
            stderr=subprocess.STDOUT,
        )

        fed = None
        trace: list[dict[str, Any]] = []
        run_error = None
        device = make_device()
        last_voltage_v = NOMINAL_VOLTAGE_V
        internal_discharge_kwh = 0.0
        internal_charge_kwh = 0.0
        try:
            fed = h.helicsCreateValueFederateFromConfig(str(adapter_path))
            publication = h.helicsFederateGetPublicationByIndex(fed, 0)
            inputs = [
                h.helicsFederateGetInputByIndex(fed, index)
                for index in range(h.helicsFederateGetInputCount(fed))
            ]
            h.helicsInputSetDefaultComplex(
                inputs[0], NOMINAL_VOLTAGE_V, 0.0
            )
            for input_handle in inputs[1:]:
                h.helicsInputSetDefaultComplex(input_handle, 0.0, 0.0)
            h.helicsFederateEnterExecutingMode(fed)
            h.helicsPublicationPublishComplex(publication, 0.0, 0.0)
            granted = 0.0
            while granted < DURATION_S:
                granted = float(
                    h.helicsFederateRequestTime(
                        fed, min(DURATION_S, granted + step_s)
                    )
                )
                voltage = h.helicsInputGetComplex(inputs[0])
                observed_load = h.helicsInputGetComplex(inputs[1])
                source_power = h.helicsInputGetComplex(inputs[2])
                if abs(voltage) > 0:
                    last_voltage_v = abs(voltage)
                output = None
                while device.time_s < granted:
                    next_second = int(device.time_s + 1)
                    p_command_kw, q_command_kvar, _ = schedule(
                        next_second, scenario
                    )
                    device.model.der_file.CONST_Q_MODE_ENABLE = (
                        "ENABLED" if q_command_kvar else "DISABLED"
                    )
                    device.model.der_file.CONST_Q = (
                        q_command_kvar / (RATING_VA / 1000.0)
                    )
                    output, _ = device.step(
                        v_pu=last_voltage_v / NOMINAL_VOLTAGE_V,
                        frequency_hz=60.0,
                        demand_kw=p_command_kw,
                        voltage_angle_deg=0.0,
                    )
                    if output.p_out_kw >= 0.0:
                        internal_discharge_kwh += output.p_out_kw / 3600.0
                    else:
                        internal_charge_kwh += -output.p_out_kw / 3600.0
                if output is None:
                    raise RuntimeError("OpenDER did not advance")
                feeder_load = complex(
                    -output.p_out_kw * 1000.0,
                    -output.q_out_kvar * 1000.0,
                )
                h.helicsPublicationPublishComplex(
                    publication, feeder_load.real, feeder_load.imag
                )
                desired_p, desired_q, segment = schedule(
                    int(granted), scenario
                )
                trace.append(
                    {
                        "time_s": granted,
                        "segment": segment,
                        "desired_p_kw": desired_p,
                        "desired_q_kvar": desired_q,
                        "p_out_kw": output.p_out_kw,
                        "q_out_kvar": output.q_out_kvar,
                        "feeder_load_w": feeder_load.real,
                        "feeder_load_var": feeder_load.imag,
                        "terminal_voltage_v": last_voltage_v,
                        "terminal_voltage_pu": (
                            last_voltage_v / NOMINAL_VOLTAGE_V
                        ),
                        "observed_gridlabd_load_w": observed_load.real,
                        "observed_gridlabd_load_var": observed_load.imag,
                        "source_power_c_w": source_power.real,
                        "source_power_c_var": source_power.imag,
                        "status": output.status,
                        "soc_pu": output.soc,
                        "input_updates": [
                            bool(h.helicsInputIsUpdated(handle))
                            for handle in inputs
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
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
            run_error = run_error or "GridLAB-D did not exit within 120 seconds"
        finally:
            gridlabd_log_handle.close()
        gridlabd_output = gridlabd_log_path.read_text(
            encoding="utf-8", errors="replace"
        )
        h.helicsBrokerFree(broker)

        effective_dir = output_dir / "effective"
        effective_dir.mkdir()
        for name in ("1c_IEEE_123_feeder.glm", "mainglm.json"):
            shutil.copy2(model_dir / name, effective_dir / name)
        shutil.copy2(adapter_path, effective_dir / adapter_path.name)
        shutil.copy2(gridlabd_log_path, output_dir / "gridlabd.log")
        physical: dict[str, list[dict[str, Any]]] = {}
        csv_parse_issues: dict[str, list[dict[str, Any]]] = {}
        for name in PHYSICAL_RECORDER_NAMES:
            source = model_dir / "output" / name
            if source.exists():
                shutil.copy2(source, output_dir / name)
                rows, issues = parse_gridlabd_csv(source)
                physical[name] = rows
                csv_parse_issues[name] = issues

        finite = all(
            math.isfinite(float(row[key]))
            for row in trace
            for key in (
                "p_out_kw",
                "q_out_kvar",
                "terminal_voltage_v",
                "soc_pu",
            )
        )
        segments = {
            name: segment_summary(trace, start, stop)
            for name, start, stop in (
                ("p_inject", 120, 180),
                ("p_absorb", 300, 360),
                ("q_inject", 480, 540),
                ("q_absorb", 660, 720),
                ("recovery", 780, 840),
            )
            if any(start <= row["time_s"] < stop for row in trace)
        }
        terminal_values = [
            row["terminal_voltage_pu"] for row in trace
        ]
        coupling_rows = physical.get("g3_der_ev4_coupling.csv", [])
        adapter_by_time = {row["time_s"]: row for row in trace}
        mapping_residuals = []
        for row in coupling_rows:
            adapter = adapter_by_time.get(
                row["simulation_time_s"] - step_s
            )
            applied = row.get("constant_power_C")
            if adapter is None or not isinstance(applied, complex):
                continue
            mapping_residuals.append(
                abs(
                    applied
                    - complex(
                        adapter["feeder_load_w"],
                        adapter["feeder_load_var"],
                    )
                )
            )

        def physical_segment(
            start: float, stop: float
        ) -> list[complex]:
            return [
                row["constant_power_C"]
                for row in coupling_rows
                if start <= row["simulation_time_s"] <= stop
                and isinstance(row.get("constant_power_C"), complex)
            ]

        p_injection_applied = physical_segment(60 + step_s, 180)
        p_absorption_applied = physical_segment(240 + step_s, 360)
        q_injection_applied = physical_segment(
            420 + max(2 * step_s, 40), 540
        )
        q_absorption_applied = physical_segment(
            600 + max(2 * step_s, 40), 720
        )
        recovery_applied = physical_segment(720 + step_s, DURATION_S)
        legacy_warning_names = (
            "swEV4_storage",
            "storage_EV4",
            "battery_inv_EV4",
            "battery_EV4",
        )
        effective_glm_text = (
            effective_dir / "1c_IEEE_123_feeder.glm"
        ).read_text(encoding="utf-8")
        effective_config_text = json.dumps(overlay["effective_config"])
        switch_rows = physical.get("g3_swEV4_status.csv", [])
        coupling_values = [
            row["constant_power_C"]
            for row in coupling_rows
            if isinstance(row.get("constant_power_C"), complex)
        ]
        expected_final_soc = 0.50 + (
            0.95 * internal_charge_kwh - internal_discharge_kwh
        ) / (ENERGY_CAPACITY_WH / 1000.0)
        observed_final_soc = trace[-1]["soc_pu"] if trace else None
        soc_energy_residual = (
            abs(observed_final_soc - expected_final_soc)
            if observed_final_soc is not None
            else None
        )
        assertions = {
            "gridlabd_completed": process.returncode == 0,
            "adapter_no_exception": run_error is None,
            "trace_reaches_duration": bool(trace)
            and trace[-1]["time_s"] == DURATION_S,
            "trace_time_monotonic": all(
                later["time_s"] > earlier["time_s"]
                for earlier, later in zip(trace, trace[1:])
            ),
            "all_required_physical_recorders_present": (
                set(physical) == set(PHYSICAL_RECORDER_NAMES)
            ),
            "physical_csvs_parse_cleanly": all(
                not issues for issues in csv_parse_issues.values()
            ),
            "physical_recorders_reach_last_exchange": all(
                rows
                and rows[-1]["simulation_time_s"] == DURATION_S - step_s
                for rows in physical.values()
            ),
            "legacy_ev4_storage_absent": all(
                name not in effective_glm_text
                for name in overlay["legacy_owner_names"]
            ),
            "exactly_one_g3_coupling_object": (
                effective_glm_text.count("name DER_EV4_BESS_COUPLING;")
                == 1
            ),
            "coupling_parent_is_l92": bool(
                re.search(
                    r"name DER_EV4_BESS_COUPLING;\s*parent l92;",
                    effective_glm_text,
                )
            ),
            "coupling_not_parented_to_ev4": not bool(
                re.search(
                    r"name DER_EV4_BESS_COUPLING;\s*parent EV4;",
                    effective_glm_text,
                )
            ),
            "swEV4_closed_for_entire_arm": bool(switch_rows)
            and all(row.get("status") == "CLOSED" for row in switch_rows),
            "helics_has_no_swEV4_target": "swEV4" not in effective_config_text,
            "helics_endpoints_empty": overlay["effective_config"]["endpoints"]
            == [],
            "finite_adapter_trace": finite,
            "no_legacy_ev4_runtime_warning": not any(
                name in line
                for line in diagnostics(gridlabd_output, temp_root)
                for name in legacy_warning_names
            ),
            "voltage_within_interface_test_range": bool(terminal_values)
            and min(terminal_values) > 0.8
            and max(terminal_values) < 1.2,
            "one_coupling_step_mapping_latency": bool(mapping_residuals)
            and max(mapping_residuals) <= 0.1,
            "soc_bounded": bool(trace)
            and all(0.10 <= row["soc_pu"] <= 1.0 for row in trace),
            "soc_energy_balance": soc_energy_residual is not None
            and soc_energy_residual <= 1e-10,
        }
        if scenario == "pulse":
            assertions.update(
                {
                    "p_injection_sign_correct": (
                        "p_inject" in segments
                        and segments["p_inject"]["mean_p_out_kw"] > 9.9
                        and segments["p_inject"]["mean_feeder_load_w"] < -9_900
                    ),
                    "p_absorption_sign_correct": (
                        "p_absorb" in segments
                        and segments["p_absorb"]["mean_p_out_kw"] < -9.9
                        and segments["p_absorb"]["mean_feeder_load_w"] > 9_900
                    ),
                    "q_injection_sign_correct": (
                        "q_inject" in segments
                        and segments["q_inject"]["mean_q_out_kvar"] > 9.0
                        and segments["q_inject"]["mean_feeder_load_var"] < -9_000
                    ),
                    "q_absorption_sign_correct": (
                        "q_absorb" in segments
                        and segments["q_absorb"]["mean_q_out_kvar"] < -9.0
                        and segments["q_absorb"]["mean_feeder_load_var"] > 9_000
                    ),
                    "gridlabd_applied_p_injection": bool(p_injection_applied)
                    and max(
                        abs(value.real + 10_000.0)
                        for value in p_injection_applied
                    )
                    <= 0.1
                    and max(abs(value.imag) for value in p_injection_applied)
                    <= 0.1,
                    "gridlabd_applied_p_absorption": bool(p_absorption_applied)
                    and max(
                        abs(value.real - 10_000.0)
                        for value in p_absorption_applied
                    )
                    <= 0.1
                    and max(abs(value.imag) for value in p_absorption_applied)
                    <= 0.1,
                    "gridlabd_applied_q_injection": bool(q_injection_applied)
                    and max(abs(value.real) for value in q_injection_applied)
                    <= 0.1
                    and max(
                        abs(value.imag + 10_000.0)
                        for value in q_injection_applied
                    )
                    <= 0.1,
                    "gridlabd_applied_q_absorption": bool(q_absorption_applied)
                    and max(abs(value.real) for value in q_absorption_applied)
                    <= 0.1
                    and max(
                        abs(value.imag - 10_000.0)
                        for value in q_absorption_applied
                    )
                    <= 0.1,
                    "gridlabd_recovery_zero": bool(recovery_applied)
                    and max(abs(value) for value in recovery_applied) <= 0.1,
                }
            )
        else:
            assertions.update(
                {
                    "null_adapter_output_zero": bool(trace)
                    and max(
                        math.hypot(
                            row["feeder_load_w"], row["feeder_load_var"]
                        )
                        for row in trace
                    )
                    <= 0.1,
                    "null_gridlabd_coupling_zero": bool(coupling_values)
                    and max(abs(value) for value in coupling_values) <= 0.1,
                }
            )
        result = {
            "schema_version": "1.0",
            "scope": (
                "G3 one-device physical-loop validation; no NATIG, "
                "cyber impairment, or attacker-effect claim"
            ),
            "arm": arm_name,
            "scenario": scenario,
            "coupling_step_s": step_s,
            "device_internal_step_s": INTERNAL_DEVICE_STEP_S,
            "duration_s": DURATION_S,
            "identity": {
                "runner_sha256": sha256(Path(__file__).resolve()),
                "device_wrapper_sha256": sha256(
                    repo / "v3/opender/device.py"
                ),
                "der_devices_config_sha256": sha256(
                    repo / "v3/configs/der_devices.yaml"
                ),
                "opender_version": opender.__version__,
                "opender_commit": OPENDER_COMMIT,
                "helics_version": h.helicsGetVersion(),
                "expected_container_image_id": IMAGE_ID,
                **{
                    key: value
                    for key, value in overlay.items()
                    if key.endswith("_sha256")
                },
            },
            "sign_convention": {
                "opender_p_positive": "generation/discharge",
                "opender_q_positive": "injection",
                "gridlabd_constant_power_positive": "consumption/absorption",
                "mapping": "S_gridlabd_VA = -1000 * (P_openDER_kW + j Q_openDER_kvar)",
            },
            "schedule": scenario_schedule(scenario),
            "segments": segments,
            "physical_mapping": {
                "expected_latency_s": step_s,
                "paired_sample_count": len(mapping_residuals),
                "max_applied_va_residual": (
                    max(mapping_residuals) if mapping_residuals else None
                ),
            },
            "energy_balance": {
                "internal_discharge_kwh": internal_discharge_kwh,
                "internal_charge_kwh": internal_charge_kwh,
                "charge_efficiency_pu": 0.95,
                "expected_final_soc_pu": expected_final_soc,
                "observed_final_soc_pu": observed_final_soc,
                "absolute_soc_residual": soc_energy_residual,
            },
            "adapter_trace": trace,
            "physical_traces": {
                key: serializable_rows(value)
                for key, value in physical.items()
            },
            "process": {
                "gridlabd_returncode": process.returncode,
                "diagnostics": diagnostics(gridlabd_output, temp_root),
                "run_error": run_error,
                "csv_parse_issues": csv_parse_issues,
            },
            "effective": {
                "configuration": overlay["effective_config"],
                "legacy_owner_names_removed": overlay["legacy_owner_names"],
                "topology": {
                    "feeder_path": "n91/linobj9192/l92",
                    "legacy_load_path": "l92/swEV4/EV4",
                    "der_path": "l92/DER_EV4_BESS_COUPLING",
                    "der_downstream_of_swEV4": False,
                    "swEV4_owner": "runner_static",
                    "swEV4_required_status": "CLOSED",
                },
            },
            "assertions": assertions,
            "artifacts": {
                path.relative_to(output_dir).as_posix(): {
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in sorted(output_dir.rglob("*"))
                if path.is_file()
            },
        }
        result["success"] = all(assertions.values())
        result_path = output_dir / "g3_physical_loop.json"
        result_path.write_text(
            json.dumps(result, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("/workspace"))
    parser.add_argument("--coupling-step", type=int, choices=(1, 5, 10, 60), required=True)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    result = run_arm(
        args.repo.resolve(), output_dir, args.coupling_step, args.scenario
    )
    print(
        f"{result['arm']}: success={result['success']} "
        f"gridlabd_rc={result['process']['gridlabd_returncode']} "
        f"trace={len(result['adapter_trace'])} "
        f"error={result['process']['run_error']}"
    )
    for key, value in result["assertions"].items():
        if not value:
            print(f"FAILED: {key}")
    h.helicsCloseLibrary()
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
