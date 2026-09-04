"""Run the exact M28 actor-blind command through the bounded runtime core."""

from __future__ import annotations

import argparse
from typing import Any

from . import runtime as bounded_runtime
from .partitions import derive_component_seeds
from .preliminary_only_gate import PARTITION_REGISTRY


SEED = 8109
OPERATING_POINT = "responsive_night"
WINDOWS = 3
WINDOW_SECONDS = 10
TARGET_ID = "DER_EV4_BESS"
COMMAND_KW = 30.0
ACTORS = ("IA3", "IA4")


def pair_id(actor: str) -> str:
    """Return the registered runtime pair for one M28 actor."""

    if actor not in ACTORS:
        raise ValueError(f"unregistered M28 actor: {actor}")
    return f"m28_{actor.lower()}_decision_to_action_seed{SEED}"


def build_profiles() -> dict[str, dict[str, Any]]:
    """Build actor-labelled profiles whose executable command is identical."""

    profiles: dict[str, dict[str, Any]] = {}
    for actor in ACTORS:
        actor_key = actor.lower()
        benign_action_id = f"m28_{actor_key}_benign_seed{SEED}"
        profiles[pair_id(actor)] = {
            "seed": SEED,
            "operating_point": OPERATING_POINT,
            "windows": WINDOWS,
            "window_seconds": WINDOW_SECONDS,
            "attack_window_cap": 1,
            "attack_energy_cap_kvah": 2.0,
            "partition_role": "attack_development",
            "action_type": "simulator_execution",
            "benign_action_id": benign_action_id,
            "probe_action_ids": {
                f"{TARGET_ID}:+30": f"m28_{actor_key}_attack_seed{SEED}",
            },
            "probe_treatment_ids": {
                f"{TARGET_ID}:+30": "attack",
            },
            "budget_id": f"m28_{actor_key}_three_windows_one_30kw_action",
        }
    return profiles


M28_RUNTIME_PROFILES = build_profiles()


def _attack_development_component_seeds(
    *,
    spec: dict[str, Any],
    role: str,
    replicate_seed: int,
    gridlabd_seed: int,
    explicit_noise_seed: int | None,
):
    """Authorize only the preregistered M28 attack-development seed."""

    partition = next(
        (item for item in PARTITION_REGISTRY if item["role"] == role), None
    )
    if partition is None or role != "attack_development":
        raise ValueError(f"unsupported M28 runtime role: {role}")
    if int(replicate_seed) != SEED or SEED not in partition["seeds"]:
        raise ValueError("M28 requires the registered attack-development seed")
    if (
        partition["classification"] != "PRELIMINARY_ONLY"
        or not partition["may_read"]
    ):
        raise ValueError("M28 attack-development partition is not readable")
    assignment = derive_component_seeds(
        spec,
        int(replicate_seed),
        gridlabd_random_seed=int(gridlabd_seed),
    )
    if (
        explicit_noise_seed is not None
        and int(explicit_noise_seed) != assignment.measurement_noise_seed
    ):
        raise ValueError(
            "M28 measurement-noise seed drift: "
            f"expected {assignment.measurement_noise_seed}, "
            f"received {int(explicit_noise_seed)}"
        )
    return role, assignment


def validate_args(args: argparse.Namespace) -> None:
    """Reject any invocation outside the registered point-specific smoke."""

    profile = M28_RUNTIME_PROFILES.get(str(args.pair_id))
    if profile is None:
        raise ValueError(f"unregistered M28 pair: {args.pair_id}")
    expected = {
        "preliminary_role": "attack_development",
        "attacker_seed": SEED,
        "noise_seed": SEED + 90000,
        "operating_point": OPERATING_POINT,
        "windows": WINDOWS,
        "coupling_step": WINDOW_SECONDS,
    }
    for field, value in expected.items():
        if getattr(args, field) != value:
            raise ValueError(f"M28 runtime drift for {field}")
    if args.arm not in {"benign", "probe"}:
        raise ValueError("M28 runtime accepts only benign or fixed probe arms")
    if args.arm == "benign":
        if args.budget_windows != 0 or args.energy_cap_kvah != 0.0:
            raise ValueError("M28 benign budget drift")
    elif (
        args.probe_id != TARGET_ID
        or float(args.probe_kw) != COMMAND_KW
        or args.budget_windows != 1
        or float(args.energy_cap_kvah) != 2.0
    ):
        raise ValueError("M28 executable command or budget drift")
    if (
        args.gen_only
        or args.detector
        or args.volt_var
        or float(args.meas_noise_pu) != 0.002
        or args.config is not None
    ):
        raise ValueError("M28 runtime option opens an unregistered boundary")


def main(argv: list[str] | None = None) -> int:
    parser = bounded_runtime.build_parser()
    for action in parser._actions:
        if action.dest == "preliminary_role":
            action.choices = [
                "runtime_qualification",
                "system_identification",
                "attack_development",
            ]
            break
    args = parser.parse_args(argv)
    validate_args(args)
    overlap = set(bounded_runtime.PRELIMINARY_RUNTIME_PROFILES).intersection(
        M28_RUNTIME_PROFILES
    )
    if overlap:
        raise ValueError(f"M28 profile collision: {sorted(overlap)}")
    bounded_runtime.PRELIMINARY_RUNTIME_PROFILES.update(M28_RUNTIME_PROFILES)
    bounded_runtime._preliminary_component_seeds = (
        _attack_development_component_seeds
    )
    return bounded_runtime.run_bounded(args)


if __name__ == "__main__":
    raise SystemExit(main())
