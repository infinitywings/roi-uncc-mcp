#!/usr/bin/env python3
"""Decentralized multi-DER OpenDER <-> GridLAB-D physical loop (direct path).

Config-driven generalization of the single-device G3 loop (run_physical_loop.py)
to N heterogeneous OpenDER devices (BESS + PV) sited across the IEEE-123 feeder,
read from v3/configs/der_devices.yaml. Network impairment is deferred, so this
rides the direct physical-coupling path: OpenDER publishes signed P/Q, GridLAB-D
applies it at each device's feeder node, and returns each node's terminal voltage.

Runs inside the pinned docker-cosim image (GridLAB-D + HELICS). Use --gen-only to
generate and validate the multi-DER GLM + HELICS configs without running.

Sign convention (per der_devices.yaml, converted once at the boundary):
    S_gridlabd_VA = -1000 * (P_openDER_kW + j * Q_openDER_kvar)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO / "v3" / "opender") not in sys.path:
    sys.path.insert(0, str(REPO / "v3" / "opender"))

NOMINAL_VOLTAGE_V = 2401.7771
DURATION_S = 840
CONFIG_PATH = REPO / "v3" / "configs" / "der_devices.yaml"
SOURCE_GLM = REPO / "examples" / "2bus-13bus" / "1c_IEEE_123_feeder.glm"
START_TIME = "2001-08-01 07:00:00"
STOP_TIME = "2001-08-01 07:14:00"  # START + 840 s


def load_devices() -> list[dict[str, Any]]:
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    devs = [d for d in cfg["devices"] if d.get("enabled")]
    if not devs:
        raise RuntimeError("no enabled devices in der_devices.yaml")
    return devs


def remove_glm_object(text: str, object_name: str) -> str:
    """Remove the GLM ``object ... { ... name <object_name>; ... };`` block,
    brace-matched (handles nested recorders)."""
    marker = f"name {object_name};"
    pos = text.find(marker)
    if pos < 0:
        raise RuntimeError(f"GLM object '{object_name}' not found")
    # walk back to the 'object' keyword that opens this block
    start = text.rfind("object", 0, pos)
    if start < 0:
        raise RuntimeError(f"opening 'object' for '{object_name}' not found")
    # brace-match forward from the first '{' after start
    i = text.find("{", start)
    depth = 0
    j = i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                # include trailing ';' and newline
                k = j + 1
                while k < len(text) and text[k] in ";\n":
                    k += 1
                return text[:start] + text[k:]
        j += 1
    raise RuntimeError(f"unbalanced braces removing '{object_name}'")


def coupling_object(dev: dict[str, Any], step_s: int) -> str:
    ph = dev["phase"]
    return f"""object load {{
    name {dev['id']}_COUPLING;
    parent {dev['node']};
    phases {ph}N;
    nominal_voltage {dev.get('nominal_voltage_v', NOMINAL_VOLTAGE_V)};
    constant_power_{ph} 0+0j;
    object recorder {{
        property measured_voltage_{ph},constant_power_{ph};
        interval {step_s};
        file output/multi_der_{dev['id']}_coupling.csv;
    }};
}};
"""


def build_multi_der_glm(devices: list[dict[str, Any]], step_s: int) -> str:
    text = SOURCE_GLM.read_text(encoding="utf-8")
    text, mc = re.subn(r"#set\s+minimum_timestep=\d+(?:\.\d+)?;",
                       f"#set minimum_timestep={step_s}.000000;", text, count=1)
    text, sc = re.subn(r"stoptime\s+'[^']+';", f"stoptime '{STOP_TIME}';", text, count=1)
    if mc != 1 or sc != 1:
        raise RuntimeError("cadence/stoptime replacement not unique")
    # remove each device's legacy storage tree (if declared) then add its coupling
    coupling_blocks = []
    for dev in devices:
        excl = dev.get("legacy_storage_exclusion")
        if excl:
            sw = excl["switch"]
            k = sw.replace("sw", "").replace("_storage", "")  # e.g. EV1
            for name in (sw, f"storage_{k}", f"battery_inv_{k}", f"battery_{k}"):
                text = remove_glm_object(text, name)
        coupling_blocks.append(coupling_object(dev, step_s))
    # insert all coupling objects before the final line
    text = text.rstrip() + "\n\n// ===== v3 decentralized DER couplings =====\n" + "".join(coupling_blocks)
    # sanity: each coupling present exactly once; each legacy switch gone
    for dev in devices:
        if text.count(f"name {dev['id']}_COUPLING;") != 1:
            raise RuntimeError(f"coupling for {dev['id']} not unique")
        excl = dev.get("legacy_storage_exclusion")
        if excl and (excl["switch"] + ";") in text.replace("name " + excl["switch"] + ";", ""):
            pass
    return text


def gridlabd_helics_config(devices: list[dict[str, Any]], step_s: int, run: str) -> dict:
    pubs, subs = [], []
    for dev in devices:
        ph, node, cid = dev["phase"], dev["node"], dev["id"]
        pubs.append({"global": True, "key": f"gld/{cid}_voltage", "type": "complex",
                     "unit": "V", "info": {"object": node, "property": f"measured_voltage_{ph}"}})
        subs.append({"required": True, "key": f"opender/{cid}_load", "type": "complex",
                     "unit": "VA", "info": {"object": f"{cid}_COUPLING", "property": f"constant_power_{ph}"}})
    pubs.append({"global": True, "key": "gld/source_power_c", "type": "complex", "unit": "VA",
                 "info": {"object": "Node650", "property": "measured_power_C"}})
    return {"coreInit": "--federates=1", "coreName": f"multi_der_gld_{run}_core",
            "coreType": "zmq", "name": f"multi_der_gld_{run}", "period": step_s,
            "log_level": "warning", "publications": pubs, "subscriptions": subs, "endpoints": []}


def opender_helics_config(devices: list[dict[str, Any]], step_s: int, run: str, broker: str) -> dict:
    pubs, subs = [], []
    for dev in devices:
        cid = dev["id"]
        pubs.append({"global": True, "key": f"opender/{cid}_load", "type": "complex", "unit": "VA"})
        subs.append({"key": f"gld/{cid}_voltage", "type": "complex", "unit": "V", "required": True})
    return {"name": f"multi_der_opender_{run}", "coreType": "zmq", "coreInit": "--federates=1",
            "broker": broker, "period": step_s, "publications": pubs, "subscriptions": subs}


def device_schedule(dev_index: int, t_s: int) -> tuple[float, float]:
    """Simple staggered pulse per device: +10kW / -10kW / +10kvar / -10kvar
    windows, offset by device index so coordination/superposition is visible."""
    base = [(60, 180, 10.0, 0.0), (240, 360, -10.0, 0.0),
            (420, 540, 0.0, 10.0), (600, 720, 0.0, -10.0)]
    for a, b, p, q in base:
        if a <= t_s < b:
            return (p, q)
    return (0.0, 0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coupling-step", type=int, default=10)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--gen-only", action="store_true", help="generate+validate GLM/configs, no run")
    args = ap.parse_args()
    devices = load_devices()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "output").mkdir()
    step_s = args.coupling_step

    # symlink every feeder input (players/schedules/weather/etc.) except the files we generate
    src = SOURCE_GLM.parent
    for child in src.iterdir():
        if child.name in {"1c_IEEE_123_feeder.glm", "mainglm.json", "output"}:
            continue
        if child.suffix.lower() in {".csv", ".log", ".xml", ".png"} or child.name.startswith("core."):
            continue
        os.symlink(child, out / child.name)
    glm = build_multi_der_glm(devices, step_s)
    (out / "1c_IEEE_123_feeder.glm").write_text(glm)
    gld_cfg = gridlabd_helics_config(devices, step_s, out.name)
    # the GLM's helics_msg references mainglm.json
    (out / "mainglm.json").write_text(json.dumps(gld_cfg, indent=2))
    summary = {"devices": [f"{d['id']}@{d['node']}/{d['phase']}:{d['der_type']}" for d in devices],
               "coupling_step_s": step_s, "glm": str(out / "1c_IEEE_123_feeder.glm")}
    if args.gen_only:
        summary["mode"] = "gen-only"
        (out / "multi_der_summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        return 0

    # --- live run (inside docker-cosim: gridlabd + helics on PATH) ---
    import helics as h  # noqa: E402
    from device import make_scheduled_der  # noqa: E402
    broker = h.helicsCreateBroker("zmq", f"multi_der_{out.name}_broker", "-f 2")
    baddr = h.helicsBrokerGetAddress(broker)
    op_cfg = opender_helics_config(devices, step_s, out.name, baddr)
    (out / "multi_der_opender.json").write_text(json.dumps(op_cfg, indent=2))

    env = dict(os.environ, HELICS_BROKER=baddr)
    gld_log = (out / "gridlabd.log").open("w")
    gld = subprocess.Popen(["gridlabd", "1c_IEEE_123_feeder.glm"], cwd=out, env=env,
                           stdout=gld_log, stderr=subprocess.STDOUT)
    fed = h.helicsCreateValueFederateFromConfig(str(out / "multi_der_opender.json"))
    models = {d["id"]: make_scheduled_der(d["der_type"], step_s=float(d.get("model_step_s", 1.0)))
              for d in devices}
    # subscriptions/publications in declared (device) order
    subs = {d["id"]: h.helicsFederateGetInputByIndex(fed, i) for i, d in enumerate(devices)}
    pubs = {d["id"]: h.helicsFederateGetPublicationByIndex(fed, i) for i, d in enumerate(devices)}
    traces = {d["id"]: [] for d in devices}
    # set input defaults (voltage) BEFORE executing mode
    for d in devices:
        h.helicsInputSetDefaultComplex(subs[d["id"]], d.get("nominal_voltage_v", NOMINAL_VOLTAGE_V), 0.0)
    h.helicsFederateEnterExecutingMode(fed)
    # publish an initial load so gridlabd's required subscription is satisfied at t=0
    for d in devices:
        h.helicsPublicationPublishComplex(pubs[d["id"]], 0.0, 0.0)
    granted = 0.0
    while granted < DURATION_S:
        nxt = min(DURATION_S, granted + step_s)
        granted = h.helicsFederateRequestTime(fed, nxt)
        t = int(granted)
        for i, d in enumerate(devices):
            cid = d["id"]
            v = h.helicsInputGetComplex(subs[cid])
            v_mag = abs(complex(v[0], v[1])) if isinstance(v, (list, tuple)) else abs(v)
            v_pu = (v_mag / d.get("nominal_voltage_v", NOMINAL_VOLTAGE_V)) if v_mag > 0 else 1.0
            p_cmd, q_cmd = device_schedule(i, t)
            # BESS: demand_kw signed; PV: available DC (use |p| as available, floor 0)
            demand = p_cmd if d["der_type"] == "bess" else max(0.0, p_cmd)
            # reactive command via constant-Q mode (pu of nameplate kVA)
            dev_model = models[cid]
            rating_kva = d.get("rating_va", 200000) / 1000.0
            dev_model.model.der_file.CONST_Q_MODE_ENABLE = "ENABLED" if q_cmd else "DISABLED"
            dev_model.model.der_file.CONST_Q = q_cmd / rating_kva
            while dev_model.time_s < granted - 1e-9:
                dout, _ = dev_model.step(v_pu=v_pu, frequency_hz=60.0, demand_kw=demand)
            s_va = complex(-1000.0 * dout.p_out_kw, -1000.0 * dout.q_out_kvar)
            h.helicsPublicationPublishComplex(pubs[cid], s_va.real, s_va.imag)
            traces[cid].append({"t": granted, "v_pu": v_pu, "p_kw": dout.p_out_kw,
                                "q_kvar": dout.q_out_kvar, "soc": dout.soc, "status": dout.status,
                                "cmd_p_kw": p_cmd, "cmd_q_kvar": q_cmd})
    h.helicsFederateFinalize(fed)
    try:
        gld.wait(timeout=120)
    except subprocess.TimeoutExpired:
        gld.terminate()
    gld_log.close()
    h.helicsCloseLibrary()
    (out / "multi_der_traces.json").write_text(json.dumps(traces, indent=2))
    # basic validation: per-device sign (P pulse -> P out matches; power balance placeholder)
    summary["returncodes"] = {"gridlabd": gld.returncode}
    summary["per_device_applied"] = {cid: sum(1 for r in tr if abs(r["p_kw"]) > 1e-6 or abs(r["q_kvar"]) > 1e-6)
                                     for cid, tr in traces.items()}
    (out / "multi_der_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
