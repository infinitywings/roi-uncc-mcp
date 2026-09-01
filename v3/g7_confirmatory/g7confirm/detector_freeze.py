"""Detector provenance audit and benign-only calibration planning."""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .manifest import sha256_file
from .partitions import (
    derive_component_seeds,
    gridlabd_random_seed,
    require_seed_partition,
)
from .spec import SpecError, spec_sha256, validate_spec


def _stable_id(prefix: str, payload: Any, length: int = 20) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return prefix + hashlib.sha256(encoded).hexdigest()[:length]


def _entry(repo_root: Path, path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    relative = resolved.relative_to(repo_root.resolve())
    return {
        "path": relative.as_posix(),
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def _clock_start(path: Path) -> str | None:
    match = re.search(r"(?m)^\s*starttime\s+'([^']+)'\s*;", path.read_text())
    return match.group(1) if match else None


def _check(name: str, passed: bool, evidence: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "evidence": evidence}


def build_detector_provenance_audit(
    spec: dict[str, Any],
    *,
    repo_root: str | Path,
    mission_id: str,
    decision_id: str,
) -> dict[str, Any]:
    """Hash current inputs and reject unverifiable legacy calibration lineage."""
    validate_spec(spec)
    root = Path(repo_root).resolve()
    freeze = root / "v3/g7_condition_freeze/20260830_r1"
    detector = freeze / "shared/detector_g7.py"
    sensitivity = freeze / "shared/sensitivity_g7.json"
    base_runner = freeze / "shared/run_multi_der_loop.py"
    benign = freeze / "shared/g7_pilot_b0"
    summary_path = benign / "g7_summary.json"
    traces_path = benign / "multi_der_traces.json"
    legacy_glm = benign / "1c_IEEE_123_feeder.glm"
    source_glm = root / "examples/2bus-13bus/1c_IEEE_123_feeder.glm"
    device_config = root / "v3/configs/der_devices.yaml"
    for path in (
        detector, sensitivity, base_runner, summary_path, traces_path,
        legacy_glm, source_glm, device_config,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    summary = json.loads(summary_path.read_text())
    sensitivity_data = json.loads(sensitivity.read_text())
    checks: list[dict[str, Any]] = []
    checks.append(_check(
        "benign_zero_treatment",
        summary.get("budget_windows") == 0 and summary.get("budget_spent") == 0,
        {"budget_windows": summary.get("budget_windows"),
         "budget_spent": summary.get("budget_spent")},
    ))
    checks.append(_check(
        "benign_completed_expected_windows",
        summary.get("gridlabd_returncode") == 0
        and int(summary.get("windows", -1)) == int(spec["time"]["total_windows"]),
        {"gridlabd_returncode": summary.get("gridlabd_returncode"),
         "windows": summary.get("windows")},
    ))

    legacy_seed = summary.get("attacker_seed")
    seed_error: str | None = None
    seed_partition: str | None = None
    try:
        seed_partition = require_seed_partition(
            spec,
            int(legacy_seed),
            allowed=("detector_calibration",),
            purpose="legacy benign detector calibration",
        )
    except (SpecError, TypeError, ValueError) as exc:
        seed_error = str(exc)
    checks.append(_check(
        "replicate_seed_in_detector_calibration_partition",
        seed_partition == "detector_calibration",
        {"seed": legacy_seed, "partition": seed_partition, "error": seed_error},
    ))

    required_lineage = {
        "operating_point": summary.get("operating_point"),
        "volt_var_defender": summary.get("volt_var_defender"),
        "meas_noise_pu": summary.get("meas_noise_pu"),
        "noise_seed": summary.get("noise_seed"),
    }
    checks.append(_check(
        "explicit_condition_and_noise_lineage",
        all(value is not None for value in required_lineage.values()),
        required_lineage,
    ))
    checks.append(_check(
        "sensitivity_sources_content_addressed",
        isinstance(sensitivity_data.get("source_run_manifests"), list)
        and bool(sensitivity_data.get("source_run_manifests"))
        and all(
            isinstance(item, dict) and item.get("sha256") and item.get("seed") is not None
            for item in sensitivity_data.get("source_run_manifests", [])
        ),
        {
            "source_runs": sensitivity_data.get("source_runs"),
            "source_run_manifests": sensitivity_data.get("source_run_manifests"),
        },
    ))

    fit_seed = int(spec.get("detector_controls", {}).get("fit_seed", -1))
    fit_partition: str | None = None
    fit_error: str | None = None
    try:
        fit_partition = require_seed_partition(
            spec,
            fit_seed,
            allowed=("detector_calibration",),
            purpose="detector fitting",
        )
    except SpecError as exc:
        fit_error = str(exc)
    checks.append(_check(
        "declared_fit_seed_is_calibration_only",
        fit_partition == "detector_calibration",
        {"seed": fit_seed, "partition": fit_partition, "error": fit_error,
         "legacy_source_default": 7},
    ))
    checks.append(_check(
        "legacy_fit_default_is_not_accepted",
        False,
        "detector_g7.WindowDetector.fit defaults to seed=7, which is outside all current partitions",
    ))

    inventory_paths = [
        detector, sensitivity, base_runner, summary_path, traces_path,
        legacy_glm, source_glm, device_config,
    ]
    inventory = [_entry(root, path) for path in inventory_paths]
    package_material = {
        "protocol_id": spec["protocol_id"],
        "spec_sha256": spec_sha256(spec),
        "inventory": inventory,
    }
    calibration_lineage_valid = all(item["passed"] for item in checks)
    return {
        "schema_version": "grideval-g7-detector-provenance-audit/v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": spec["protocol_id"],
        "spec_sha256": spec_sha256(spec),
        "mission_id": mission_id,
        "decision_id": decision_id,
        "detector_package_id": _stable_id("g7det_", package_material),
        "evaluation_opened": False,
        "inventory": inventory,
        "legacy_candidate": {
            "path": benign.relative_to(root).as_posix(),
            "inferred_clock_start_not_accepted_as_lineage": _clock_start(legacy_glm),
            "gridlabd_random_seed": gridlabd_random_seed(legacy_glm),
            "checks": checks,
            "admissible_for_confirmatory_calibration": calibration_lineage_valid,
        },
        "freeze_state": {
            "source_bytes_hashed": True,
            "interface_schema_frozen": True,
            "calibration_lineage_valid": calibration_lineage_valid,
            "calibrated": False,
            "detector_parameter_artifact_present": False,
            "evaluation_admissible": False,
            "campaign_admissible": False,
        },
        "readiness": {
            "source_schema_freeze": "pass",
            "calibration": "hold",
            "paired_runtime_pilot": "not_run",
            "evaluation": "sealed",
            "campaign": "hold",
        },
        "required_next_evidence": [
            "benign-only runs generated from detector_calibration seeds with complete condition lineage",
            "content-addressed sensitivity provenance that does not depend on held-out evaluation",
            "detector fit invoked with the declared calibration-only fit seed",
            "serialized detector parameters and thresholds in a create-once artifact",
            "false-alarm validation on calibration holdout folds before any evaluation seed is opened",
        ],
    }


def build_benign_calibration_plan(
    spec: dict[str, Any],
    *,
    dependency_hashes: Mapping[str, str],
    gridlabd_seed: int,
) -> dict[str, Any]:
    """Plan benign-only, per-condition calibration inputs without executing them."""
    validate_spec(spec)
    seeds = list(map(int, spec["partitions"]["detector_calibration"]))
    noise = float(spec["conditions"]["measurement_noise_pu"]["primary"])
    points = [item["id"] for item in spec["conditions"]["operating_points"]]
    runs: list[dict[str, Any]] = []
    for point, volt_var, seed in itertools.product(
        points, spec["conditions"]["volt_var"], seeds
    ):
        partition = require_seed_partition(
            spec, seed, allowed=("detector_calibration",),
            purpose="benign detector calibration plan",
        )
        controlled = {
            "partition": partition,
            "operating_point": point,
            "volt_var": bool(volt_var),
            "measurement_noise_pu": noise,
            "window_seconds": float(spec["time"]["window_seconds"]),
            "total_windows": int(spec["time"]["total_windows"]),
            "replicate_seed": seed,
            "component_seeds": derive_component_seeds(
                spec, seed, gridlabd_random_seed=gridlabd_seed
            ).as_dict(),
            "dependency_hashes": dict(sorted(dependency_hashes.items())),
        }
        runs.append({
            "run_id": _stable_id("g7cal_", controlled),
            "treatment": "benign",
            "controlled_lineage": controlled,
            "executable": False,
            "status": "planned_not_authorized",
        })
    fit_seed = int(spec["detector_controls"]["fit_seed"])
    require_seed_partition(
        spec, fit_seed, allowed=("detector_calibration",), purpose="detector fit plan"
    )
    return {
        "schema_version": "grideval-g7-benign-calibration-plan/v1",
        "protocol_id": spec["protocol_id"],
        "spec_sha256": spec_sha256(spec),
        "partition": "detector_calibration",
        "evaluation_opened": False,
        "campaign_authorized": False,
        "executable": False,
        "calibration_mode": spec["detector_controls"]["calibration_mode"],
        "fit_seed": fit_seed,
        "run_count": len(runs),
        "runs": runs,
        "fit_stage": {
            "status": "blocked_until_all_input_manifests_validate",
            "benign_only": True,
            "creates_parameter_artifact_once": True,
        },
    }
