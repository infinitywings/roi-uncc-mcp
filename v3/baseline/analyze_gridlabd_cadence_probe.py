#!/usr/bin/env python3
"""Validate and compare immutable GridLAB-D cadence-arm traces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


STEP_THRESHOLD_W = 100_000.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def step_response(
    events: list[dict[str, Any]], send_time_s: float, direction: int
) -> dict[str, Any]:
    for previous, current in zip(events, events[1:]):
        if current["granted_time_s"] <= send_time_s:
            continue
        phase_delta = [
            current["phase_real_power_w"][index]
            - previous["phase_real_power_w"][index]
            for index in range(3)
        ]
        phase_c_delta = phase_delta[2]
        if direction * phase_c_delta <= STEP_THRESHOLD_W:
            continue
        non_target_mean_delta = (phase_delta[0] + phase_delta[1]) / 2
        return {
            "send_time_s": send_time_s,
            "first_visible_time_s": current["granted_time_s"],
            "latency_s": current["granted_time_s"] - send_time_s,
            "previous_sample_time_s": previous["granted_time_s"],
            "phase_delta_w": phase_delta,
            "total_delta_w": (
                current["total_real_power_w"]
                - previous["total_real_power_w"]
            ),
            "phase_c_effect_adjusted_for_mean_ab_drift_w": (
                phase_c_delta - non_target_mean_delta
            ),
        }
    raise ValueError(
        f"No {'positive' if direction > 0 else 'negative'} EV4 step found "
        f"after t={send_time_s}"
    )


def summarize_arm(result: dict[str, Any]) -> dict[str, Any]:
    events = result["controller_events"]
    updated_event_count = sum(any(event["input_updated"]) for event in events)
    return {
        "arm": result["arm"],
        "success": result["success"],
        "gridlabd_returncode": result["gridlabd_returncode"],
        "event_count": len(events),
        "updated_value_event_count": updated_event_count,
        "grant_times_s": [event["granted_time_s"] for event in events],
        "high_step": step_response(events, 60.0, 1),
        "nominal_restore_step": step_response(events, 120.0, -1),
        "internal_actuation": internal_actuation(
            result["gridlabd_ev4_internal_trace"]
        ),
        "warning_count": sum(
            "WARNING" in line for line in result["gridlabd_diagnostics"]
        ),
        "error_or_fatal_diagnostic_count": sum(
            "ERROR" in line or "FATAL" in line
            for line in result["gridlabd_diagnostics"]
        ),
    }


def internal_actuation(
    trace: list[dict[str, Any]],
) -> dict[str, Any]:
    high = next(
        row
        for row in trace
        if row["simulation_time_s"] > 60
        and row["constant_power_c_w"] == 400_000
    )
    restored = next(
        row
        for row in trace
        if row["simulation_time_s"] > 120
        and row["constant_power_c_w"] == 200_000
    )
    return {
        "high_apply_time_s": high["simulation_time_s"],
        "high_apply_latency_s": high["simulation_time_s"] - 60,
        "restore_apply_time_s": restored["simulation_time_s"],
        "restore_apply_latency_s": restored["simulation_time_s"] - 120,
        "trace_sample_count": len(trace),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    paths = {
        "frozen_primary": (
            repo
            / "v3/baseline/gridlabd_cadence_frozen60_r5/"
            "gridlabd_cadence_arm.json"
        ),
        "frozen_repeat": (
            repo
            / "v3/baseline/gridlabd_cadence_frozen60_r6/"
            "gridlabd_cadence_arm.json"
        ),
        "physical10_primary": (
            repo
            / "v3/baseline/gridlabd_cadence_physical10_r3/"
            "gridlabd_cadence_arm.json"
        ),
        "physical10_repeat": (
            repo
            / "v3/baseline/gridlabd_cadence_physical10_r4/"
            "gridlabd_cadence_arm.json"
        ),
        "failed_readonly_overlay": (
            repo
            / "v3/baseline/gridlabd_cadence_frozen60_r1/"
            "gridlabd_cadence_arm.json"
        ),
        "failed_1500kw_pulse": (
            repo
            / "v3/baseline/gridlabd_cadence_frozen60_r2/"
            "gridlabd_cadence_arm.json"
        ),
    }
    results = {key: load(path) for key, path in paths.items()}
    for key in (
        "frozen_primary",
        "frozen_repeat",
        "physical10_primary",
        "physical10_repeat",
    ):
        if not results[key]["success"]:
            raise ValueError(f"Expected successful trace: {key}")

    frozen_byte_identical = (
        paths["frozen_primary"].read_bytes()
        == paths["frozen_repeat"].read_bytes()
    )
    physical10_byte_identical = (
        paths["physical10_primary"].read_bytes()
        == paths["physical10_repeat"].read_bytes()
    )
    if not frozen_byte_identical or not physical10_byte_identical:
        raise ValueError("Cadence-arm repeat is not byte-identical")

    frozen = summarize_arm(results["frozen_primary"])
    physical10 = summarize_arm(results["physical10_primary"])
    frozen_t60 = next(
        event
        for event in results["frozen_primary"]["controller_events"]
        if event["granted_time_s"] == 60
    )
    physical10_t60 = next(
        event
        for event in results["physical10_primary"]["controller_events"]
        if event["granted_time_s"] == 60
    )
    baseline_phase_differences = [
        right - left
        for left, right in zip(
            frozen_t60["phase_real_power_w"],
            physical10_t60["phase_real_power_w"],
        )
    ]
    baseline_total_difference = (
        physical10_t60["total_real_power_w"]
        - frozen_t60["total_real_power_w"]
    )

    high_effect_difference = (
        physical10["high_step"][
            "phase_c_effect_adjusted_for_mean_ab_drift_w"
        ]
        - frozen["high_step"][
            "phase_c_effect_adjusted_for_mean_ab_drift_w"
        ]
    )
    restore_effect_difference = (
        physical10["nominal_restore_step"][
            "phase_c_effect_adjusted_for_mean_ab_drift_w"
        ]
        - frozen["nominal_restore_step"][
            "phase_c_effect_adjusted_for_mean_ab_drift_w"
        ]
    )

    failed_readonly = results["failed_readonly_overlay"]
    failed_high = results["failed_1500kw_pulse"]
    analysis = {
        "schema_version": "1.0",
        "analysis": "IEEE-123 GridLAB-D physical cadence comparison",
        "identity": {
            "analyzer_sha256": sha256(Path(__file__).resolve()),
            "input_artifacts": {
                key: {
                    "path": str(path.relative_to(repo)),
                    "sha256": sha256(path),
                }
                for key, path in paths.items()
            },
        },
        "reproducibility": {
            "frozen_repeat_byte_identical": frozen_byte_identical,
            "physical10_repeat_byte_identical": physical10_byte_identical,
        },
        "pre_pulse_equivalence_at_t60": {
            "phase_real_power_difference_physical10_minus_frozen_w": (
                baseline_phase_differences
            ),
            "total_real_power_difference_physical10_minus_frozen_w": (
                baseline_total_difference
            ),
            "exact_match": (
                baseline_total_difference == 0
                and all(value == 0 for value in baseline_phase_differences)
            ),
            "absolute_tolerance_w": 1.0,
            "within_1w_tolerance": (
                abs(baseline_total_difference) <= 1.0
                and all(
                    abs(value) <= 1.0
                    for value in baseline_phase_differences
                )
            ),
        },
        "arms": {
            "frozen60": frozen,
            "physical10": physical10,
        },
        "between_arm_effect_equivalence": {
            "high_adjusted_effect_difference_physical10_minus_frozen_w": (
                high_effect_difference
            ),
            "restore_adjusted_effect_difference_physical10_minus_frozen_w": (
                restore_effect_difference
            ),
            "high_absolute_difference_fraction_of_200kw_step": (
                abs(high_effect_difference) / 200_000
            ),
            "restore_absolute_difference_fraction_of_200kw_step": (
                abs(restore_effect_difference) / 200_000
            ),
        },
        "failure_evidence": {
            "readonly_overlay_attempt": {
                "success": failed_readonly["success"],
                "gridlabd_returncode": failed_readonly[
                    "gridlabd_returncode"
                ],
                "controller_event_count": len(
                    failed_readonly["controller_events"]
                ),
                "classification": (
                    "probe_infrastructure_failure_before simulation: recorder "
                    "outputs were symlinked into a read-only source mount"
                ),
            },
            "1500kw_pulse_attempt": {
                "success": failed_high["success"],
                "gridlabd_returncode": failed_high["gridlabd_returncode"],
                "controller_event_count": len(
                    failed_high["controller_events"]
                ),
                "classification": (
                    "physical-model failure: FBS convergence iteration limit "
                    "at t=120 when the 1.5 MW EV4 command was applied"
                ),
            },
        },
        "gate_assessment": {
            "bounded_400kw_pulse_valid": True,
            "physical_magnitude_equivalent_across_cadence": (
                abs(high_effect_difference) <= 0.02 * 200_000
                and abs(restore_effect_difference) <= 0.02 * 200_000
            ),
            "ten_second_internal_actuation_achieved": (
                physical10["internal_actuation"][
                    "high_apply_latency_s"
                ]
                <= 10
                and physical10["internal_actuation"][
                    "restore_apply_latency_s"
                ]
                <= 10
            ),
            "ten_second_controller_visible_effect_achieved": (
                physical10["high_step"]["latency_s"] <= 10
                and physical10["nominal_restore_step"]["latency_s"] <= 10
            ),
            "verdict": (
                "The v3 10-second overlay preserves the bounded EV4 physical "
                "effect magnitude and applies each command internally after "
                "10 seconds. The controller first observes the resulting "
                "feeder publication after 20 seconds. The frozen arm applies "
                "after 60 seconds and exposes the effect after 120 seconds. "
                "G0 therefore falsifies the manuscript's claimed 10-second "
                "physical response for the frozen baseline. The v3 overlay "
                "supports a 10-second actuation cadence but not a fresh "
                "10-second closed-loop observation cadence without iterative "
                "or otherwise redesigned coupling."
            ),
        },
        "scope_limits": [
            "Feeder A is isolated from GridPACK and uses its source fixed swing voltage.",
            "This is a deterministic component experiment, not a campaign or inferential sample.",
            "The pulse is 400 kW; the preserved 1.5 MW attempt failed FBS convergence.",
            "HELICS value publications are change-driven, so unchanged values between grants do not alone prove that GridLAB-D failed to advance.",
        ],
    }
    output_path = output_dir / "gridlabd_cadence_analysis.json"
    output_path.write_text(
        json.dumps(analysis, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")
    print(
        "latency_s: frozen high/restore="
        f"{frozen['high_step']['latency_s']}/"
        f"{frozen['nominal_restore_step']['latency_s']}; "
        "physical10 high/restore="
        f"{physical10['high_step']['latency_s']}/"
        f"{physical10['nominal_restore_step']['latency_s']}"
    )
    print(
        "pre_pulse_within_1w="
        f"{analysis['pre_pulse_equivalence_at_t60']['within_1w_tolerance']} "
        "magnitude_equivalent="
        f"{analysis['gate_assessment']['physical_magnitude_equivalent_across_cadence']} "
        "ten_second_internal="
        f"{analysis['gate_assessment']['ten_second_internal_actuation_achieved']} "
        "ten_second_feedback="
        f"{analysis['gate_assessment']['ten_second_controller_visible_effect_achieved']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
