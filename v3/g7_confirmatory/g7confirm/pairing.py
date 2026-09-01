"""Paired benign/attack lineage plans and fail-closed validation."""

from __future__ import annotations

import hashlib
import json
import copy
from typing import Any, Mapping

from .campaign import expand_profile
from .partitions import derive_component_seeds, require_seed_partition
from .spec import SpecError, spec_sha256, validate_spec


PAIR_SCHEMA_VERSION = "grideval-g7-paired-lineage/v1"


def _stable_id(prefix: str, payload: Any, length: int = 20) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return prefix + hashlib.sha256(encoded).hexdigest()[:length]


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def validate_pair(
    pair: dict[str, Any],
    spec: dict[str, Any],
    *,
    allowed_partitions: tuple[str, ...] = ("development",),
) -> None:
    """Require exact controlled-lineage equality and one treatment contrast."""
    validate_spec(spec)
    if pair.get("schema_version") != PAIR_SCHEMA_VERSION:
        raise SpecError("unsupported paired-lineage schema")
    if pair.get("evaluation_opened") is not False:
        raise SpecError("paired plan must keep evaluation_opened=false")
    runs = pair.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        raise SpecError("a pair must contain exactly two runs")
    by_treatment = {run.get("treatment"): run for run in runs}
    if set(by_treatment) != {"benign", "attack"}:
        raise SpecError("a pair requires exactly one benign and one attack run")
    benign, attack = by_treatment["benign"], by_treatment["attack"]
    if benign.get("controlled_lineage") != attack.get("controlled_lineage"):
        raise SpecError("paired controlled-lineage drift")

    controls = benign["controlled_lineage"]
    seed = int(controls["replicate_seed"])
    partition = require_seed_partition(
        spec, seed, allowed=allowed_partitions, purpose="paired-lineage planning"
    )
    if controls.get("partition") != partition:
        raise SpecError("paired partition label does not match the replicate seed")
    expected_seeds = derive_component_seeds(
        spec,
        seed,
        gridlabd_random_seed=int(controls["component_seeds"]["gridlabd_random_seed"]),
    ).as_dict()
    if controls.get("component_seeds") != expected_seeds:
        raise SpecError("paired component-seed derivation drift")
    dependencies = controls.get("dependency_hashes", {})
    if not dependencies or not all(_is_sha256(value) for value in dependencies.values()):
        raise SpecError("paired dependency hashes must be non-empty SHA-256 values")

    benign_intervention = benign.get("intervention", {})
    attack_intervention = attack.get("intervention", {})
    if benign_intervention != {
        "kind": "benign",
        "perturbation_policy": "none",
        "perturbed_window_cap": 0,
        "apparent_energy_cap_kvah": 0.0,
    }:
        raise SpecError("benign intervention is not the canonical zero-treatment control")
    if attack_intervention.get("kind") != "attack":
        raise SpecError("attack intervention is missing")
    if int(attack_intervention.get("perturbed_window_cap", -1)) < 0:
        raise SpecError("attack intervention has an invalid window cap")
    if float(attack_intervention.get("apparent_energy_cap_kvah", -1)) < 0:
        raise SpecError("attack intervention has an invalid energy cap")


def build_paired_development_plan(
    spec: dict[str, Any],
    profile_name: str,
    *,
    dependency_hashes: Mapping[str, str],
    detector_package_id: str,
    gridlabd_seed: int,
) -> dict[str, Any]:
    """Pair every non-executable development proposal with an exact control."""
    validate_spec(spec)
    campaign = expand_profile(spec, profile_name)
    pairs: list[dict[str, Any]] = []
    for proposed in campaign["runs"]:
        seed = int(proposed["seed"])
        partition = require_seed_partition(
            spec, seed, allowed=("development",), purpose="paired development plan"
        )
        controls = {
            "protocol_id": spec["protocol_id"],
            "spec_sha256": spec_sha256(spec),
            "partition": partition,
            "operating_point": proposed["operating_point"],
            "volt_var": bool(proposed["volt_var"]),
            "measurement_noise_pu": float(proposed["measurement_noise_pu"]),
            "window_seconds": float(spec["time"]["window_seconds"]),
            "total_windows": int(spec["time"]["total_windows"]),
            "duration_seconds": (
                float(spec["time"]["window_seconds"])
                * int(spec["time"]["total_windows"])
            ),
            "replicate_seed": seed,
            "component_seeds": derive_component_seeds(
                spec, seed, gridlabd_random_seed=gridlabd_seed
            ).as_dict(),
            "dependency_hashes": dict(sorted(dependency_hashes.items())),
            "detector_package_id": detector_package_id,
        }
        identity = {
            "controlled_lineage": controls,
            "attack_arm": proposed["arm"],
            "proposal_index": int(proposed["proposal_index"]),
        }
        pair_id = _stable_id("g7pair_", identity)
        pair = {
            "schema_version": PAIR_SCHEMA_VERSION,
            "pair_id": pair_id,
            "evaluation_opened": False,
            "executable": False,
            "status": proposed["status"],
            "campaign_run_id": proposed["run_id"],
            "runs": [
                {
                    "run_id": _stable_id("g7run_", [pair_id, "benign"]),
                    "treatment": "benign",
                    "controlled_lineage": copy.deepcopy(controls),
                    "intervention": {
                        "kind": "benign",
                        "perturbation_policy": "none",
                        "perturbed_window_cap": 0,
                        "apparent_energy_cap_kvah": 0.0,
                    },
                },
                {
                    "run_id": _stable_id("g7run_", [pair_id, "attack"]),
                    "treatment": "attack",
                    "controlled_lineage": copy.deepcopy(controls),
                    "intervention": {
                        "kind": "attack",
                        "perturbation_policy": proposed["arm"],
                        "perturbed_window_cap": int(proposed["window_cap"]),
                        "apparent_energy_cap_kvah": float(proposed["energy_cap_kvah"]),
                        "proposal": proposed["proposal"],
                    },
                },
            ],
        }
        validate_pair(pair, spec)
        pairs.append(pair)
    return {
        "schema_version": "grideval-g7-paired-plan/v1",
        "protocol_id": spec["protocol_id"],
        "spec_sha256": spec_sha256(spec),
        "profile": profile_name,
        "partition": "development",
        "evaluation_opened": False,
        "campaign_authorized": False,
        "executable": False,
        "pair_count": len(pairs),
        "pairs": pairs,
    }
