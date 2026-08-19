#!/usr/bin/env python3
"""Validate the G5 DNP3 SBO hardening fix on a rebuilt image.

Reuses the sound G5 staging (build_g5_source + stage_overlay) but launches the
federation on a HARDENED image (default grideval/natig:g5-hardened-r1), skipping
the frozen-G4 binary/source attestation because the hardened binary intentionally
differs. This is a fix-VALIDATION harness, NOT a locked-provenance run: it proves
whether the per-index (2-slot) outstation SBO removes the ao0-OPERATE-loss
artifact (expect 18/18 OPERATEs at nominal and graceful, delay-dependent
degradation, instead of the bimodal 18-or-10 of the stock binary).
"""
from __future__ import annotations
import argparse, json, subprocess, time
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
if str(HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[1]))
from v3.natig_adapter import run_live_benign as rlb
from v3.natig_adapter import run_live_g5_impairment as g5

MANIFEST = HERE / "locked_runtime_result_base_r24_r1" / "live_image_manifest.json"


def launch(image_id: str, contract: dict, output_dir: Path, runtime_command, timeout_s: int) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    py = manifest["python_runtime"]["executable"]
    container = f"grideval-g5h-{output_dir.name}"
    if not rlb.SAFE_OUTPUT_NAME.fullmatch(output_dir.name):
        raise SystemExit("output basename not container-safe")
    if rlb._run(["docker", "container", "inspect", container]).returncode == 0:
        raise SystemExit(f"refusing existing container {container}")
    rlb._run(["docker", "create", "--name", container, "--network", "none",
              "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
              "--pids-limit", "4096", "--memory", "16g", "--cpus", "4",
              image_id, "sleep", "infinity"], check=True)
    runtime_dir = output_dir / "runtime_output"; runtime_dir.mkdir()
    returncodes: dict[str, int] = {}
    try:
        rlb._run(["docker", "start", container], check=True)
        rlb._run(["docker", "exec", container, "mkdir", "-p", "/g4"], check=True)
        rlb._run(["docker", "cp", str(output_dir / "effective"), f"{container}:/g4/"],
                 timeout=300, check=True)
        commands = {
            "broker": ["helics_broker", "--slowresponding", "--federates=4",
                       "--port=9000", "--loglevel=warning"],
            "controller": [py, "/g4/effective/runtime/live_controller_federate.py",
                           "--config", "/g4/effective/config/controller.json",
                           "--trace", "/g4/effective/runtime_output/controller_trace.json"],
            "natig": runtime_command,
            "gateway": [py, "/g4/effective/runtime/live_gateway_federate.py",
                        "--config", "/g4/effective/config/gateway.json",
                        "--trace", "/g4/effective/runtime_output/gateway_trace.json"],
            "gridlabd": ["gridlabd", "/g4/effective/model/1c_IEEE_123_feeder.glm"],
        }
        cwds = {"broker": "/g4/effective", "controller": "/g4/effective",
                "natig": "/g4/effective", "gateway": "/g4/effective",
                "gridlabd": "/g4/effective/model"}
        user = f"{__import__('os').getuid()}:{__import__('os').getgid()}"
        handles = {}
        for proc in contract["required_processes"]:
            log = (runtime_dir / f"{proc}.log").open("w")
            argv = ["docker", "exec", "--user", user,
                    "-e", "HELICS_BROKER=tcp://127.0.0.1:9000",
                    "-e", "PYTHONPATH=/g4/effective/python",
                    "-w", cwds[proc], container, *commands[proc]]
            handles[proc] = (subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT), log)
            if proc == "broker":
                time.sleep(0.5)
        deadline = time.monotonic() + timeout_s
        while any(h.poll() is None for h, _ in handles.values()):
            if time.monotonic() >= deadline:
                raise SystemExit("federation timeout")
            time.sleep(0.25)
        for proc, (h, log) in handles.items():
            returncodes[proc] = int(h.returncode); log.close()
        rlb._run(["docker", "cp", f"{container}:/g4/effective/runtime_output/.",
                  str(runtime_dir)], timeout=300, check=True)
    finally:
        rlb._run(["docker", "rm", "-f", container], timeout=60)
    return {"returncodes": returncodes}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--delay-ms", type=float, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--image", default="grideval/natig:g5-hardened-r1")
    ap.add_argument("--controller-override", type=Path, default=None)
    ap.add_argument("--timeout-s", type=int, default=1800)
    args = ap.parse_args()
    jn = int(round(args.delay_ms * 1_000_000))
    out = args.output_dir.resolve()
    g5_dir = out.parent / f"g5hsrc_{args.label}"
    for d in (g5_dir, out):
        if d.exists():
            raise SystemExit(f"create-once path exists: {d}")
    contract_path = g5.build_g5_source(g5_dir, jn, jn, args.label)
    contract = json.loads(contract_path.read_text())
    stage = rlb.stage_overlay(contract, contract_path, out)  # builds effective/
    if args.controller_override:
        import shutil as _sh
        _sh.copy2(args.controller_override, out / "effective" / "runtime" / "live_controller_federate.py")
    image_id = rlb._run(["docker", "image", "inspect", "--format", "{{.Id}}", args.image],
                        check=True).stdout.strip()
    manifest = json.loads(MANIFEST.read_text())
    result = launch(image_id, contract, out, manifest["runtime_command"], args.timeout_s)
    ok = all(v == 0 for v in result["returncodes"].values())
    print(json.dumps({"label": args.label, "delay_ms": args.delay_ms, "image": args.image,
                      "image_id": image_id, "returncodes": result["returncodes"],
                      "all_rc_zero": ok}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
