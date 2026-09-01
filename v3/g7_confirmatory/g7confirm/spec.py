"""Experiment-spec loading and invariants."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class SpecError(ValueError):
    """Raised when a confirmatory specification violates a hard invariant."""


def load_spec(path: str | Path) -> dict[str, Any]:
    spec_path = Path(path)
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SpecError("experiment spec must be a mapping")
    validate_spec(data)
    return data


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SpecError(message)


def validate_spec(spec: dict[str, Any]) -> None:
    _require(spec.get("schema_version") == "grideval-g7-confirmatory/v1",
             "unsupported schema_version")
    _require(spec.get("campaign_authorized") is False,
             "Phase 0–1 spec must keep campaign_authorized=false")

    model = spec.get("model", {})
    _require(isinstance(model.get("base_url"), str) and model["base_url"].endswith("/v1"),
             "model.base_url must be an OpenAI-compatible /v1 URL")
    _require(isinstance(model.get("id"), str) and bool(model["id"]),
             "model.id is required")
    _require(0 <= float(model.get("temperature", -1)) <= 2,
             "model.temperature must be in [0,2]")
    _require(int(model.get("max_tokens", 0)) > 0, "model.max_tokens must be positive")
    _require(float(model.get("timeout_s", 0)) > 0, "model.timeout_s must be positive")

    timing = spec.get("time", {})
    _require(float(timing.get("window_seconds", 0)) > 0,
             "time.window_seconds must be positive")
    _require(int(timing.get("total_windows", 0)) > 0,
             "time.total_windows must be positive")

    primary = spec.get("budgets", {}).get("primary", {})
    _require(int(primary.get("perturbed_windows", -1)) >= 0,
             "primary perturbed-window budget must be non-negative")
    _require(float(primary.get("apparent_energy_kvah", 0)) > 0,
             "primary apparent-energy budget must be positive")

    space = spec.get("candidate_space", {})
    amplitudes = space.get("amplitude_fractions", [])
    periods = space.get("period_windows", [])
    _require(isinstance(amplitudes, list) and amplitudes,
             "candidate amplitude set must be non-empty")
    _require(isinstance(periods, list) and periods,
             "candidate period set must be non-empty")
    _require(len(set(map(float, amplitudes))) == len(amplitudes),
             "candidate amplitudes must be unique")
    _require(len(set(map(int, periods))) == len(periods),
             "candidate periods must be unique")
    _require(all(0.0 <= float(v) <= 1.0 for v in amplitudes),
             "candidate amplitudes must be in [0,1]")
    _require(all(1 <= int(v) <= 12 and float(v) == int(v) for v in periods),
             "candidate periods must be integers in [1,12]")

    search = spec.get("search", {})
    k = int(search.get("outer_budget_k", 0))
    arms = search.get("arms", [])
    _require(k > 0, "search.outer_budget_k must be positive")
    _require(isinstance(arms, list) and len(arms) >= 2 and len(set(arms)) == len(arms),
             "at least two unique search arms are required")
    _require(k <= len(amplitudes) * len(periods),
             "outer budget cannot exceed the finite candidate space")

    partitions = spec.get("partitions", {})
    names = ("detector_calibration", "development", "evaluation")
    sets: dict[str, set[int]] = {}
    for name in names:
        values = partitions.get(name, [])
        _require(isinstance(values, list) and values, f"partition {name} must be non-empty")
        _require(len(set(values)) == len(values), f"partition {name} contains duplicate seeds")
        sets[name] = set(map(int, values))
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            _require(sets[left].isdisjoint(sets[right]),
                     f"partitions {left} and {right} overlap")
    minimum = int(partitions.get("minimum_valid_evaluation_replicates", 0))
    _require(10 <= minimum <= len(sets["evaluation"]),
             "minimum valid evaluation replicates must be >=10 and available")

    seed_controls = spec.get("seed_controls", {})
    _require(seed_controls.get("evaluation_sealed") is True,
             "seed_controls.evaluation_sealed must remain true")
    _require(seed_controls.get("allowed_runtime_partitions") == ["development"],
             "runtime is restricted to the development partition")
    _require(int(seed_controls.get("measurement_noise_seed_offset", 0)) > 0,
             "measurement-noise seed offset must be positive")
    _require(seed_controls.get("gridlabd_random_seed_source") == "source_glm",
             "GridLAB-D seed must come from exact source GLM bytes")

    detector_controls = spec.get("detector_controls", {})
    _require(detector_controls.get("calibration_partition") == "detector_calibration",
             "detector calibration must use its dedicated partition")
    _require(detector_controls.get("calibration_mode") == "per_operating_condition",
             "detector calibration must be per operating condition")
    _require(detector_controls.get("calibration_input") == "benign_only",
             "detector calibration inputs must be benign-only")
    _require(int(detector_controls.get("minimum_benign_replicates_per_cell", 0))
             == len(sets["detector_calibration"]),
             "detector calibration replicate count must match the frozen partition")
    _require(int(detector_controls.get("fit_seed", -1)) in sets["detector_calibration"],
             "detector fit seed must belong to detector_calibration")
    _require(detector_controls.get("source_schema_freeze_does_not_imply_calibrated") is True,
             "source/schema freeze must not imply detector calibration")

    conditions = spec.get("conditions", {})
    operating_points = conditions.get("operating_points", [])
    _require(len(operating_points) >= 5, "four responsive and one falsification OP are required")
    ids = [item.get("id") for item in operating_points if isinstance(item, dict)]
    _require(len(ids) == len(operating_points) and len(set(ids)) == len(ids),
             "operating-point IDs must be present and unique")
    _require(sum(item.get("class") == "responsive" for item in operating_points) >= 4,
             "at least four responsive operating points are required")
    _require(any(item.get("class") == "falsification" for item in operating_points),
             "at least one falsification operating point is required")
    integrated = [item for item in operating_points
                  if item.get("integration_status") == "derived_clock_hook"]
    if integrated:
        _require(len(integrated) == len(operating_points),
                 "operating-point integration must be all-or-none")
        start_times = [item.get("start_time") for item in integrated]
        _require(all(isinstance(value, str) and value for value in start_times),
                 "integrated operating points require start_time")
        _require(len(set(start_times)) == len(start_times),
                 "integrated operating points require distinct start_time values")

    runtime = spec.get("runtime_integration", {})
    if runtime:
        _require(runtime.get("campaign_hold_preserved") is True,
                 "runtime integration must preserve the campaign HOLD")
        _require(int(runtime.get("live_smoke_max_windows", 0)) == 1,
                 "runtime integration must remain capped at one live window")

    profiles = spec.get("profiles", {})
    _require(isinstance(profiles, dict) and profiles, "at least one profile is required")
    for name, profile in profiles.items():
        _require(set(profile.get("operating_points", [])).issubset(ids),
                 f"profile {name} references an unknown operating point")
        count = int(profile.get("proposal_count", 0))
        seeds = profile.get("development_seeds", [])
        _require(0 < count <= k, f"profile {name} proposal_count must be in [1,K]")
        _require(len(seeds) >= count, f"profile {name} needs one seed per proposal")
        _require(set(seeds).issubset(sets["development"]),
                 f"profile {name} includes a non-development seed")

    required_stops = {
        "prompt_audit_failure",
        "partition_overlap",
        "unequal_outer_budget",
        "budget_violation",
        "output_exists",
        "runtime_hash_drift",
        "model_id_mismatch",
        "evaluation_opened_before_freeze",
        "operating_point_not_integrated",
        "unpartitioned_seed",
        "evaluation_seed_in_non_evaluation_phase",
        "unpaired_control_drift",
        "detector_calibration_lineage_missing",
    }
    _require(required_stops.issubset(set(spec.get("hard_stops", []))),
             "hard_stops is missing a required fail-closed condition")


def canonical_spec_bytes(spec: dict[str, Any]) -> bytes:
    return json.dumps(spec, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def spec_sha256(spec: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_spec_bytes(spec)).hexdigest()
