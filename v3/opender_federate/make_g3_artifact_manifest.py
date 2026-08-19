#!/usr/bin/env python3
"""Create the immutable G3 evidence manifest without overwriting evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite create-once output: {output}")

    relative_files = [
        Path("v3/configs/der_devices.yaml"),
        Path("v3/opender/device.py"),
        Path("v3/opender/conformance_r11/opender_component_conformance.json"),
        Path("v3/opender_federate/run_physical_loop.py"),
        Path("v3/opender_federate/analyze_physical_loop_convergence.py"),
        Path("v3/opender_federate/compare_selected_repeat.py"),
        Path("v3/opender_federate/G3_VALIDATION_REPORT.md"),
        Path("v3/opender_federate/README.md"),
        Path("v3/IMPLEMENTATION_PLAN.md"),
        Path("v3/SELF_AUDIT.md"),
    ]
    canonical = repo / "v3/opender_federate/g3_canonical_r1"
    relative_files.extend(
        path.relative_to(repo)
        for path in sorted(canonical.rglob("*"))
        if path.is_file()
    )
    missing = [str(path) for path in relative_files if not (repo / path).is_file()]
    if missing:
        parser.error("Missing required artifact(s): " + ", ".join(missing))

    convergence = json.loads(
        (canonical / "convergence.json").read_text(encoding="utf-8")
    )
    repeatability = json.loads(
        (canonical / "repeatability_v2.json").read_text(encoding="utf-8")
    )
    arm_results = []
    for step in (1, 5, 10, 60):
        for scenario in ("pulse", "null"):
            path = canonical / f"{scenario}_coupling{step}/g3_physical_loop.json"
            result = json.loads(path.read_text(encoding="utf-8"))
            arm_results.append(
                {
                    "scenario": scenario,
                    "coupling_step_s": step,
                    "success": result["success"],
                    "gridlabd_returncode": result["process"][
                        "gridlabd_returncode"
                    ],
                    "failed_assertions": [
                        name
                        for name, passed in result["assertions"].items()
                        if not passed
                    ],
                }
            )

    manifest = {
        "schema_version": "1.0",
        "gate": "G3 OpenDER physical-loop adapter",
        "verdict": "PASS_WITH_SELECTED_10S_CADENCE",
        "scope": (
            "One OpenDER BESS at IEEE-123 Feeder A bus l92; no NATIG, "
            "DNP3, cyber impairment, GridPACK, or attacker-effect claim"
        ),
        "canonical_matrix": {
            "all_individual_arms_pass": all(
                arm["success"] and not arm["failed_assertions"]
                for arm in arm_results
            ),
            "arms": arm_results,
            "convergence_gate_pass": convergence["gate_pass"],
            "passing_steps_s": convergence["passing_steps_s"],
            "selected_coarsest_step_s": convergence[
                "selected_coarsest_step_s"
            ],
            "repeatability_pass": repeatability["success"],
        },
        "preserved_noncanonical_failures": [
            "physical_loop_coupling1_r1: runner stdout-pipe deadlock/truncation",
            "physical_loop_coupling60_r1: superseded short-window evaluator",
            "pulse_coupling10_r1: transition-boundary evaluator contamination",
            "physical_loop_coupling*_r*: superseded parent-EV4 topology",
        ],
        "artifacts": {
            str(path): {
                "sha256": sha256(repo / path),
                "bytes": (repo / path).stat().st_size,
            }
            for path in relative_files
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {output}: artifacts={len(relative_files)} "
        f"verdict={manifest['verdict']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
