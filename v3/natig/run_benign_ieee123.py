#!/usr/bin/env python3
"""Run one isolated, no-attack NATIG IEEE-123 component proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any


CONTROL = "/rd2c/integration/control"
NS3 = "/rd2c/ns-3-dev"
NATIG = "/rd2c/PUSH/NATIG"
SOURCE_PRESET = f"{NATIG}/RC/code/3G-conf-123/grid.json"
PHYSICAL_DIRS = ("gen", "inverter", "load", "oh", "pow", "switch")
MODEL_FILES = (
    "IEEE_123_Diesels.glm",
    "IEEE_123_Dynamic.glm",
    "IEEE_123_Inverters_Mixed.glm",
    "IEEE_123_Recorders.glm",
)
EXPECTED_COMMIT = "e163b350e243c6386477e35dead979a4cb2b7c60"
EXPECTED_TREE = "9f10cb55d5eaa4c20a95f292b84a266e9992bc1a"


def command(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout,
        )
        return {
            "argv": argv,
            "returncode": completed.returncode,
            "elapsed_s": time.monotonic() - started,
            "output": completed.stdout,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return {
            "argv": argv,
            "returncode": 124,
            "elapsed_s": time.monotonic() - started,
            "output": output,
            "timed_out": True,
        }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(root)),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def read_if_present(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def normalized_sha256(path: Path) -> str:
    """Hash scientific content while excluding GridLAB-D wall-clock headers."""
    excluded = ("# date......", "# user......", "# host......")
    lines = [
        line
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not line.startswith(excluded)
    ]
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def active_recorder_paths(glm: Path) -> list[str]:
    paths: list[str] = []
    pattern = re.compile(r'^(?:file|filename)\s+"?([^";\s]+\.csv)')
    for raw_line in glm.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("//"):
            continue
        match = pattern.search(line)
        if match:
            paths.append(match.group(1))
    return sorted(set(paths))


def timestamp_seconds(line: str) -> float | None:
    if not line or line.startswith("#"):
        return None
    first = line.split(",", 1)[0]
    match = re.search(r"\b(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)\b", first)
    if not match:
        return None
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def recorder_evidence(
    output: Path,
    expected_paths: list[str],
) -> dict[str, Any]:
    files: dict[str, Any] = {}
    snapshot_paths = {"pow/output_current.csv", "pow/output_voltage.csv"}
    for relative in expected_paths:
        path = (
            output / "physical" / relative
            if "/" in relative
            else output / "physical" / relative
        )
        lines = read_if_present(path).splitlines()
        data_times = [
            value
            for value in (
                timestamp_seconds(line)
                for line in lines
            )
            if value is not None
        ]
        noncomment_rows = sum(
            bool(line.strip()) and not line.startswith("#") for line in lines
        )
        is_snapshot = relative in snapshot_paths
        files[relative] = {
            "kind": "snapshot" if is_snapshot else "timeseries",
            "present": path.is_file(),
            "size": path.stat().st_size if path.is_file() else None,
            "data_rows": len(data_times),
            "noncomment_rows": noncomment_rows,
            "snapshot_run_marker": (
                any(
                    re.match(r"^# .* run at \d{4}-\d{2}-\d{2} ", line)
                    for line in lines
                )
                if is_snapshot
                else None
            ),
            "first_clock_s": min(data_times) if data_times else None,
            "last_clock_s": max(data_times) if data_times else None,
            "span_s": (
                max(data_times) - min(data_times)
                if len(data_times) >= 2
                else None
            ),
        }
    spans = [
        item["span_s"]
        for item in files.values()
        if item["kind"] == "timeseries" and item["span_s"] is not None
    ]
    return {
        "expected_count": len(expected_paths),
        "present_count": sum(item["present"] for item in files.values()),
        "nonempty_count": sum(
            (
                item["noncomment_rows"] > 1
                if item["kind"] == "snapshot"
                else item["data_rows"] > 0
            )
            for item in files.values()
        ),
        "snapshot_marker_count": sum(
            item["kind"] == "snapshot" and item["snapshot_run_marker"]
            for item in files.values()
        ),
        "minimum_span_s": min(spans) if spans else None,
        "maximum_span_s": max(spans) if spans else None,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--expected-source", type=Path, required=True)
    parser.add_argument("--runner-script", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-s", type=int, default=1800)
    args = parser.parse_args()
    overlay = args.overlay.resolve()
    expected_source = args.expected_source.resolve()
    runner_script = args.runner_script.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "effective").mkdir()
    (output / "physical").mkdir()
    if not overlay.is_file():
        raise FileNotFoundError(overlay)
    if not expected_source.is_dir():
        raise FileNotFoundError(expected_source)
    if not runner_script.is_file():
        raise FileNotFoundError(runner_script)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", output.name):
        raise ValueError("output directory basename must be container-name safe")

    local_identity = {
        "commit": command(["git", "rev-parse", "HEAD"], cwd=expected_source),
        "tree": command(["git", "rev-parse", "HEAD^{tree}"], cwd=expected_source),
        "status": command(["git", "status", "--short"], cwd=expected_source),
    }
    if not (
        local_identity["commit"]["output"].strip() == EXPECTED_COMMIT
        and local_identity["tree"]["output"].strip() == EXPECTED_TREE
        and not local_identity["status"]["output"].strip()
    ):
        raise RuntimeError("expected NATIG source is not the frozen clean G1 checkout")

    container = f"grideval-{output.name}"
    inspect_existing = command(["docker", "container", "inspect", container])
    if inspect_existing["returncode"] == 0:
        raise RuntimeError(f"refusing to reuse existing container {container}")

    image_inspect = command(["docker", "image", "inspect", args.image])
    image_id_result = command(
        ["docker", "image", "inspect", "--format", "{{.Id}}", args.image]
    )
    if image_inspect["returncode"] != 0 or image_id_result["returncode"] != 0:
        raise RuntimeError(f"image unavailable: {args.image}")
    image_id = image_id_result["output"].strip()

    create = command(
        [
            "docker",
            "create",
            "--name",
            container,
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "4096",
            "--memory",
            "16g",
            "--cpus",
            "4",
            image_id,
            "sleep",
            "infinity",
        ]
    )
    start: dict[str, Any] | None = None
    container_image: dict[str, Any] | None = None
    embedded_identity: dict[str, Any] | None = None
    copy_overlay: dict[str, Any] | None = None
    copy_runner: dict[str, Any] | None = None
    clean: dict[str, Any] | None = None
    run: dict[str, Any] | None = None
    timeout_stop: dict[str, Any] | None = None
    process_check: dict[str, Any] | None = None
    attack_absence: dict[str, Any] | None = None
    copies: list[dict[str, Any]] = []
    cleanup: dict[str, Any] | None = None
    try:
        if create["returncode"] != 0:
            raise RuntimeError(create["output"])
        start = command(["docker", "start", container])
        container_image = command(
            ["docker", "container", "inspect", "--format", "{{.Image}}", container]
        )
        embedded_identity = command(
            [
                "docker",
                "exec",
                container,
                "bash",
                "-lc",
                (
                    f"git -C {NATIG} rev-parse HEAD "
                    f"&& git -C {NATIG} rev-parse HEAD^{{tree}} "
                    f"&& git -C {NATIG} status --short"
                ),
            ]
        )
        copy_overlay = command(
            ["docker", "cp", str(overlay), f"{container}:{SOURCE_PRESET}"]
        )
        copy_runner = command(
            [
                "docker",
                "cp",
                str(runner_script),
                f"{container}:/tmp/grideval_benign_federation.sh",
            ]
        )
        clean_script = (
            f"find {CONTROL}/output -mindepth 1 -delete "
            f"&& find {CONTROL}/config -mindepth 1 -delete "
            + " ".join(
                f"&& find {CONTROL}/{name} -mindepth 1 -delete "
                for name in PHYSICAL_DIRS
            )
            + (
                f"&& rm -f {CONTROL}/regulator_4.csv {CONTROL}/attack.csv "
                f"{CONTROL}/TP.txt {NS3}/perf.txt "
                f"&& test -z \"$(find {CONTROL}/output {CONTROL}/config "
                + " ".join(f"{CONTROL}/{name} " for name in PHYSICAL_DIRS)
                + "-mindepth 1 -print -quit)\" "
                f"&& test ! -e {CONTROL}/regulator_4.csv "
                f"&& test ! -e {CONTROL}/attack.csv "
                f"&& test ! -e {CONTROL}/TP.txt "
                f"&& test ! -e {NS3}/perf.txt"
            )
        )
        clean = command(
            ["docker", "exec", container, "bash", "-lc", clean_script]
        )
        prerequisites_ok = all(
            item is not None and item["returncode"] == 0
            for item in (
                start,
                container_image,
                embedded_identity,
                copy_overlay,
                copy_runner,
                clean,
            )
        )
        if prerequisites_ok:
            run = command(
                [
                    "docker",
                    "exec",
                    container,
                    "bash",
                    "/tmp/grideval_benign_federation.sh",
                ],
                timeout=args.timeout_s,
            )
            if run["timed_out"]:
                timeout_stop = command(
                    ["docker", "stop", "--time", "10", container]
                )
            else:
                process_check = command(
                    [
                        "docker",
                        "exec",
                        container,
                        "bash",
                        "-lc",
                        (
                            "pgrep -af "
                            "'helics_broker|gridlabd|ns3-helics-grid-dnp3' "
                            "|| true"
                        ),
                    ]
                )
                attack_absence = command(
                    [
                        "docker",
                        "exec",
                        container,
                        "test",
                        "!",
                        "-e",
                        f"{CONTROL}/attack.csv",
                    ]
                )

            copy_specs = [
                (f"{CONTROL}/output", output / "output"),
                (f"{CONTROL}/config", output / "effective" / "config"),
                (f"{CONTROL}/run.sh", output / "effective" / "run.sh"),
                (
                    f"{CONTROL}/ns3-helics-grid-dnp3.cc",
                    output / "effective" / "ns3-helics-grid-dnp3.cc",
                ),
                (f"{NS3}/perf.txt", output / "dnp3_perf.txt"),
                (f"{CONTROL}/TP.txt", output / "TP.txt"),
                (
                    f"{CONTROL}/regulator_4.csv",
                    output / "physical" / "regulator_4.csv",
                ),
                *(
                    (
                        f"{CONTROL}/{model}",
                        output / "effective" / model,
                    )
                    for model in MODEL_FILES
                ),
                *(
                    (
                        f"{CONTROL}/{name}",
                        output / "physical" / name,
                    )
                    for name in PHYSICAL_DIRS
                ),
            ]
            for remote, local in copy_specs:
                copied = command(
                    ["docker", "cp", f"{container}:{remote}", str(local)]
                )
                copied["remote"] = remote
                copied["local"] = str(local)
                copies.append(copied)
    finally:
        if create["returncode"] == 0:
            cleanup = command(["docker", "rm", "--force", container])

    launcher_log = output / "launcher.log"
    launcher_log.write_text(
        run["output"] if run is not None else "",
        encoding="utf-8",
    )
    process_log = output / "post_run_processes.log"
    process_log.write_text(
        process_check["output"] if process_check is not None else "",
        encoding="utf-8",
    )

    embedded_lines = (
        embedded_identity["output"].splitlines()
        if embedded_identity is not None
        else []
    )
    embedded_commit = embedded_lines[0].strip() if len(embedded_lines) >= 1 else None
    embedded_tree = embedded_lines[1].strip() if len(embedded_lines) >= 2 else None
    embedded_status = embedded_lines[2:] if len(embedded_lines) >= 3 else []
    effective_grid_path = output / "effective" / "config" / "grid.json"
    effective_grid = (
        json.loads(effective_grid_path.read_text(encoding="utf-8"))
        if effective_grid_path.is_file()
        else None
    )
    gridlabd_path = output / "output" / "gridlabd.log"
    ns3_path = output / "output" / "ns3-helics-grid-dnp3.log"
    broker_path = output / "output" / "helics_broker.log"
    gridlabd_log = read_if_present(gridlabd_path)
    ns3_log = read_if_present(ns3_path)
    broker_log = read_if_present(broker_path)
    process_lines = [
        line
        for line in process_log.read_text(encoding="utf-8").splitlines()
        if not re.search(r"pgrep -af|bash -lc", line)
    ]
    copied_paths = {
        str(Path(item["local"]).relative_to(output)): item["returncode"]
        for item in copies
    }

    expected_preset = expected_source / "RC" / "code" / "3G-conf-123"
    expected_points = expected_source / "RC" / "code" / "points-123"
    expected_config_hashes = {
        "grid.json": sha256(overlay),
        "gridlabd_config.json": sha256(expected_preset / "gridlabd_config.json"),
        "topology.json": sha256(expected_preset / "topology.json"),
        **{
            path.name: sha256(path)
            for path in sorted(expected_points.glob("*"))
            if path.is_file()
        },
    }
    effective_config_dir = output / "effective" / "config"
    effective_config_hashes = {
        path.name: sha256(path)
        for path in sorted(effective_config_dir.glob("*"))
        if path.is_file()
    }
    expected_model_hashes = {
        model: sha256(expected_preset / model) for model in MODEL_FILES
    }
    effective_model_hashes = {
        model: (
            sha256(output / "effective" / model)
            if (output / "effective" / model).is_file()
            else None
        )
        for model in MODEL_FILES
    }
    expected_recorders = active_recorder_paths(
        expected_preset / "IEEE_123_Recorders.glm"
    )
    recorders = recorder_evidence(output, expected_recorders)
    perf_lines = [
        line
        for line in read_if_present(output / "dnp3_perf.txt").splitlines()
        if line.strip() and not line.startswith("Timestamp")
    ]
    expected_model_source = (
        expected_source / "RC" / "code" / "ns3-helics-grid-dnp3-Docker.cc"
    )
    expected_launcher = expected_source / "RC" / "code" / "run.sh"
    model_source_text = expected_model_source.read_text(encoding="utf-8")

    assertions = {
        "image_present": image_inspect["returncode"] == 0,
        "container_used_resolved_image_id": (
            container_image is not None
            and container_image["output"].strip() == image_id
        ),
        "embedded_natig_commit_matches": embedded_commit == EXPECTED_COMMIT,
        "embedded_natig_tree_matches": embedded_tree == EXPECTED_TREE,
        "embedded_natig_clean_before_overlay": not embedded_status,
        "container_started": start is not None and start["returncode"] == 0,
        "overlay_copied": (
            copy_overlay is not None and copy_overlay["returncode"] == 0
        ),
        "v3_runner_copied": (
            copy_runner is not None and copy_runner["returncode"] == 0
        ),
        "clean_workspace_and_config": clean is not None and clean["returncode"] == 0,
        "launcher_completed": run is not None and run["returncode"] == 0,
        "launcher_not_timed_out": run is not None and not run["timed_out"],
        "no_federate_processes_left": (
            run is not None and not run["timed_out"] and not process_lines
        ),
        "effective_configuration_exact": (
            effective_config_hashes == expected_config_hashes
        ),
        "effective_models_exact": effective_model_hashes == expected_model_hashes,
        "effective_launcher_exact": (
            (output / "effective" / "run.sh").is_file()
            and sha256(output / "effective" / "run.sh") == sha256(expected_launcher)
        ),
        "effective_ns3_model_exact": (
            (output / "effective" / "ns3-helics-grid-dnp3.cc").is_file()
            and sha256(output / "effective" / "ns3-helics-grid-dnp3.cc")
            == sha256(expected_model_source)
        ),
        "effective_mitm_disabled": (
            effective_grid is not None
            and effective_grid["Simulation"][0]["includeMIM"] == 0
        ),
        "effective_ddos_disabled": (
            effective_grid is not None
            and effective_grid["DDoS"][0]["Active"] == 0
        ),
        "dynamic_route_controller_disabled": (
            effective_grid is not None
            and effective_grid["Controller"][0]["use"] == 0
        ),
        "benign_dnp3_analog_payload_declared": (
            "Simulator::Schedule(MilliSeconds(3005)" in model_source_text
            and "Dnp3ApplicationNew::DIRECT, 0, -16" in model_source_text
        ),
        "explicit_attack_log_absent": (
            attack_absence is not None and attack_absence["returncode"] == 0
        ),
        "required_copies_succeeded": all(
            returncode == 0 for returncode in copied_paths.values()
        ),
        "gridlabd_log_present": gridlabd_path.is_file() and bool(gridlabd_log),
        "ns3_log_present": ns3_path.is_file() and bool(ns3_log),
        "broker_log_file_present": broker_path.is_file(),
        "gridlabd_completed_timesteps": "Time steps completed" in gridlabd_log,
        "gridlabd_no_fatal": not bool(
            re.search(
                r"\b(FATAL|Segmentation fault|Aborted|core dumped)\b",
                gridlabd_log,
                re.IGNORECASE,
            )
        ),
        "ns3_no_fatal": not bool(
            re.search(
                r"\b(FATAL|Segmentation fault|Aborted|core dumped|assert failed)\b",
                ns3_log,
                re.IGNORECASE,
            )
        ),
        "ns3_no_attack_or_reset_markers": not bool(
            re.search(
                r"Applying attack|Reset .* point|Logged attack stats",
                ns3_log,
                re.IGNORECASE,
            )
        ),
        "broker_no_error": not bool(
            re.search(
                r"\b(ERROR|FATAL|Segmentation fault|Aborted|core dumped)\b",
                broker_log,
                re.IGNORECASE,
            )
        ),
        "all_active_recorders_present": (
            recorders["present_count"] == recorders["expected_count"]
        ),
        "all_active_recorders_nonempty": (
            recorders["nonempty_count"] == recorders["expected_count"]
        ),
        "snapshot_recorders_have_run_markers": (
            recorders["snapshot_marker_count"] == 2
        ),
        "recorders_reach_twenty_seconds": (
            recorders["minimum_span_s"] is not None
            and recorders["minimum_span_s"] >= 19.0
            and recorders["maximum_span_s"] is not None
            and recorders["maximum_span_s"] >= 20.0
        ),
        "dnp3_packets_recorded": len(perf_lines) > 0,
        "container_removed": cleanup is not None and cleanup["returncode"] == 0,
    }
    success = all(assertions.values())
    signature_files = {
        str(path.relative_to(output)): normalized_sha256(path)
        for root in (output / "effective", output / "physical")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    if (output / "dnp3_perf.txt").is_file():
        signature_files["dnp3_perf.txt"] = normalized_sha256(
            output / "dnp3_perf.txt"
        )
    science_signature = hashlib.sha256(
        json.dumps(
            signature_files,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    result = {
        "schema_version": "2.0",
        "scope": "NATIG IEEE-123 3G no-attack component proof",
        "declared_benign_command": {
            "kind": "DNP3 direct analog",
            "simulation_time_s": 3.005,
            "point_index": 0,
            "value": -16,
            "scheduled_once_per_outstation": True,
        },
        "image": {
            "reference": args.image,
            "resolved_id": image_id,
            "inspect_sha256": hashlib.sha256(
                image_inspect["output"].encode("utf-8")
            ).hexdigest(),
        },
        "embedded_source": {
            "commit": embedded_commit,
            "tree": embedded_tree,
            "status_lines": embedded_status,
        },
        "container": {
            "name": container,
            "network_mode": "none",
            "capabilities": "all dropped",
            "no_new_privileges": True,
            "pids_limit": 4096,
            "memory_limit": "16g",
            "cpu_limit": 4,
            "create_returncode": create["returncode"],
            "start_returncode": start["returncode"] if start else None,
            "cleanup_returncode": cleanup["returncode"] if cleanup else None,
        },
        "configuration": {
            "overlay_path": str(overlay),
            "overlay_sha256": sha256(overlay),
            "expected_hashes": expected_config_hashes,
            "effective_hashes": effective_config_hashes,
        },
        "run": {
            "orchestration": "v3 direct federate wrapper; no waf reconfigure",
            "runner_script": str(runner_script),
            "runner_script_sha256": sha256(runner_script),
            "returncode": run["returncode"] if run else None,
            "elapsed_s": run["elapsed_s"] if run else None,
            "timed_out": run["timed_out"] if run else None,
            "timeout_stop_returncode": (
                timeout_stop["returncode"] if timeout_stop else None
            ),
            "launcher_log": launcher_log.name,
        },
        "dnp3_packet_records": len(perf_lines),
        "recorders": recorders,
        "normalized_science_signature": {
            "sha256": science_signature,
            "files": signature_files,
            "excluded_wallclock_headers": [
                "# date......",
                "# user......",
                "# host......",
            ],
        },
        "copy_returncodes": copied_paths,
        "assertions": assertions,
        "artifacts": artifact_inventory(output),
        "success": success,
    }
    manifest = output / "natig_benign_result.json"
    manifest.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"success={success} assertions={sum(assertions.values())}/{len(assertions)} "
        f"run_returncode={result['run']['returncode']} "
        f"elapsed_s={result['run']['elapsed_s']}"
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
