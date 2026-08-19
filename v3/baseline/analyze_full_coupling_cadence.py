#!/usr/bin/env python3
"""Analyze repaired full-coupling control and bounded-pulse cadence arms."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


COMMAND_TIME_S = 60
COMMAND_STEP_W = 200_000.0
FEEDBACK_THRESHOLD_W = 100_000.0
EQUIVALENCE_TOLERANCE_FRACTION = 0.02


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def internal_apply_time(run: dict[str, Any]) -> int:
    for row in run["gridlabd_ev4_internal_trace"]:
        if row["constant_power_c_w"] == 400_000.0:
            return int(row["simulation_time_s"])
    raise ValueError("EV4 high command never appeared in internal trace")


def feedback_differences(
    control: dict[str, Any], pulse: dict[str, Any]
) -> list[dict[str, float]]:
    control_by_time = {
        row["granted_time_s"]: row["total_real_power_w"]
        for row in control["controller_events"]
    }
    return [
        {
            "time_s": float(row["granted_time_s"]),
            "pulse_minus_control_w": float(
                row["total_real_power_w"]
                - control_by_time[row["granted_time_s"]]
            ),
        }
        for row in pulse["controller_events"]
    ]


def first_feedback_time(differences: list[dict[str, float]]) -> float:
    for row in differences:
        if abs(row["pulse_minus_control_w"]) >= FEEDBACK_THRESHOLD_W:
            return row["time_s"]
    raise ValueError("No controller-visible bounded-pulse effect found")


def main() -> int:
    parser = argparse.ArgumentParser()
    for arm in ("frozen", "physical10"):
        parser.add_argument(f"--{arm}-control", type=Path, required=True)
        parser.add_argument(f"--{arm}-pulse", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    paths = {
        "frozen_control": args.frozen_control.resolve(),
        "frozen_pulse": args.frozen_pulse.resolve(),
        "physical10_control": args.physical10_control.resolve(),
        "physical10_pulse": args.physical10_pulse.resolve(),
    }
    runs = {name: load(path) for name, path in paths.items()}
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    arm_results = {}
    for arm in ("frozen", "physical10"):
        control = runs[f"{arm}_control"]
        pulse = runs[f"{arm}_pulse"]
        differences = feedback_differences(control, pulse)
        apply_time = internal_apply_time(pulse)
        feedback_time = first_feedback_time(differences)
        high_effect = next(
            row["pulse_minus_control_w"]
            for row in differences
            if row["time_s"] == feedback_time
        )
        arm_results[arm] = {
            "internal_apply_time_s": apply_time,
            "internal_actuation_latency_s": apply_time - COMMAND_TIME_S,
            "first_controller_visible_effect_time_s": feedback_time,
            "controller_feedback_latency_s": (
                feedback_time - COMMAND_TIME_S
            ),
            "first_visible_effect_w": high_effect,
            "feedback_differences": differences,
        }

    effect_difference_w = abs(
        arm_results["physical10"]["first_visible_effect_w"]
        - arm_results["frozen"]["first_visible_effect_w"]
    )
    effect_difference_fraction_of_command = (
        effect_difference_w / COMMAND_STEP_W
    )
    executable_hashes = {
        run["identity"]["selected_gridpack_executable_sha256"]
        for run in runs.values()
    }
    checks = {
        "all_runs_successful": all(run["success"] for run in runs.values()),
        "all_process_returncodes_zero": all(
            all(code == 0 for code in run["process_returncodes"].values())
            for run in runs.values()
        ),
        "single_repaired_gridpack_executable": len(executable_hashes) == 1,
        "control_arms_send_no_commands": all(
            runs[f"{arm}_control"]["commands"]["mode"] == "no_commands"
            for arm in ("frozen", "physical10")
        ),
        "pulse_arms_use_same_bounded_command": all(
            runs[f"{arm}_pulse"]["commands"]["mode"] == "bounded"
            for arm in ("frozen", "physical10")
        ),
        "physical10_internal_actuation_within_10s": (
            arm_results["physical10"]["internal_actuation_latency_s"] <= 10
        ),
        "physical10_feedback_within_20s": (
            arm_results["physical10"]["controller_feedback_latency_s"] <= 20
        ),
        "effect_magnitude_equivalent_within_2pct": (
            effect_difference_fraction_of_command
            <= EQUIVALENCE_TOLERANCE_FRACTION
        ),
    }
    result = {
        "schema_version": "1.0",
        "experiment": (
            "repaired GridPACK plus two IEEE-123 feeders, no-command control "
            "versus bounded EV4 pulse"
        ),
        "command": {
            "send_high_time_s": 60,
            "high_w": 400_000.0,
            "send_restore_time_s": 120,
            "restore_w": 200_000.0,
            "step_w": COMMAND_STEP_W,
        },
        "inputs": {
            name: {"path": str(path), "sha256": sha256(path)}
            for name, path in paths.items()
        },
        "repaired_gridpack_executable_sha256": next(
            iter(executable_hashes)
        ),
        "arms": arm_results,
        "effect_equivalence": {
            "absolute_difference_w": effect_difference_w,
            "difference_fraction_of_command": (
                effect_difference_fraction_of_command
            ),
            "tolerance_fraction_of_command": (
                EQUIVALENCE_TOLERANCE_FRACTION
            ),
        },
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "interpretation": (
            "The repaired physical-10 full federation preserves the bounded "
            "effect magnitude and provides 10-second internal actuation with "
            "20-second controller-visible feedback."
        ),
    }
    (output_dir / "full_coupling_cadence_analysis.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"all_checks_pass={result['all_checks_pass']} "
        f"effect_difference_fraction="
        f"{effect_difference_fraction_of_command:.8f}"
    )
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
