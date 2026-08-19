#!/usr/bin/env python3
"""Summarize repeated benign full-coupling failures without erasing them."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_RETURNCODES = {
    "gridpack": -6,
    "feeder_a": 2,
    "feeder_b": 2,
    "pacer": 0,
}
CONVERGENCE_MARKER = (
    "convergence iteration limit reached for object meter:190"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def has_marker(run: dict[str, Any], process: str, marker: str) -> bool:
    return any(
        marker in line
        for line in run["process_diagnostics"].get(process, [])
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if len(args.run) != 2:
        parser.error("exactly two --run inputs are required")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    input_paths = [path.resolve() for path in args.run]
    runs = [load(path) for path in input_paths]

    checks = {
        "two_independent_runs": len(runs) == 2,
        "both_benign_no_pulse": all(
            run["commands"]["mode"] == "none" for run in runs
        ),
        "both_failed": all(not run["success"] for run in runs),
        "same_source_identity": (
            runs[0]["identity"]["source_hashes"]
            == runs[1]["identity"]["source_hashes"]
        ),
        "same_generated_overlay_identity": (
            runs[0]["identity"]["generated_hashes"]
            == runs[1]["identity"]["generated_hashes"]
        ),
        "same_runner_identity": (
            runs[0]["identity"]["runner_sha256"]
            == runs[1]["identity"]["runner_sha256"]
        ),
        "same_controller_observation": (
            runs[0]["controller_events"] == runs[1]["controller_events"]
        ),
        "expected_process_returncodes": all(
            run["process_returncodes"] == EXPECTED_RETURNCODES
            for run in runs
        ),
        "pacer_completed_normally": all(
            run["process_returncodes"]["pacer"] == 0 for run in runs
        ),
        "both_feeders_failed_convergence_at_meter_190": all(
            has_marker(run, feeder, CONVERGENCE_MARKER)
            for run in runs
            for feeder in ("feeder_a", "feeder_b")
        ),
        "failure_at_first_60_second_grant": all(
            len(run["controller_events"]) == 1
            and run["controller_events"][0]["granted_time_s"] == 60
            for run in runs
        ),
    }
    result = {
        "schema_version": "1.0",
        "experiment": "benign full GridPACK plus two IEEE-123 feeders",
        "runtime_image": {
            "tag": "roi-img:latest",
            "image_id": (
                "sha256:86c0e62ec71478dfd5ef2e41a95a08b64a53603322fbd"
                "4661d0c4479b7549637"
            ),
            "repo_digest": (
                "missingrain/roi-img@sha256:"
                "e16084eb7313c81fdb3731ef9ee8939165db53a377ec588b468"
                "66ab7a0e405c6"
            ),
        },
        "inputs": [
            {"path": str(path), "sha256": sha256(path)}
            for path in input_paths
        ],
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "failure_class": "gridlabd_fbs_nonconvergence",
        "failure_time_s": 60,
        "failed_objects": {
            "feeder_a": "meter:190",
            "feeder_b": "meter:190",
        },
        "gate_effect": (
            "G0 remains blocked; no NATIG or OpenDER attack comparison is "
            "scientifically admissible on this full-coupling baseline."
        ),
    }
    output = output_dir / "full_coupling_blocker_analysis.json"
    output.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"all_checks_pass={result['all_checks_pass']} "
        f"failure_class={result['failure_class']}"
    )
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
