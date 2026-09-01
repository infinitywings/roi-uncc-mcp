"""Fail-closed seed partitioning and component-seed derivation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .spec import SpecError, validate_spec


PARTITION_NAMES = ("detector_calibration", "development", "evaluation")


class SeedGuardError(SpecError):
    """Raised when a stochastic replicate is not authorized for its purpose."""


@dataclass(frozen=True)
class ComponentSeeds:
    """Every stochastic seed exposed by the current composed runtime."""

    replicate_seed: int
    attacker_policy_seed: int
    measurement_noise_seed: int
    gridlabd_random_seed: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def partition_for_seed(spec: dict[str, Any], seed: int) -> str:
    """Return the unique partition for ``seed``; unknown seeds fail closed."""
    validate_spec(spec)
    value = int(seed)
    matches = [
        name for name in PARTITION_NAMES
        if value in set(map(int, spec["partitions"][name]))
    ]
    if len(matches) != 1:
        if not matches:
            raise SeedGuardError(f"seed {value} is not declared in any partition")
        raise SeedGuardError(f"seed {value} is ambiguously assigned to {matches}")
    return matches[0]


def require_seed_partition(
    spec: dict[str, Any],
    seed: int,
    *,
    allowed: Iterable[str],
    purpose: str,
) -> str:
    """Authorize a seed for a bounded phase without ever opening evaluation."""
    allowed_set = set(allowed)
    unknown = allowed_set.difference(PARTITION_NAMES)
    if unknown:
        raise SeedGuardError(f"unknown allowed partitions: {sorted(unknown)}")
    partition = partition_for_seed(spec, seed)
    if partition not in allowed_set:
        if partition == "evaluation":
            raise SeedGuardError(
                f"evaluation seed {int(seed)} is sealed for {purpose}"
            )
        raise SeedGuardError(
            f"seed {int(seed)} belongs to {partition}, not {sorted(allowed_set)}, "
            f"for {purpose}"
        )
    return partition


def derive_component_seeds(
    spec: dict[str, Any],
    replicate_seed: int,
    *,
    gridlabd_random_seed: int,
) -> ComponentSeeds:
    controls = spec.get("seed_controls", {})
    offset = int(controls.get("measurement_noise_seed_offset", 90000))
    return ComponentSeeds(
        replicate_seed=int(replicate_seed),
        attacker_policy_seed=int(replicate_seed),
        measurement_noise_seed=int(replicate_seed) + offset,
        gridlabd_random_seed=int(gridlabd_random_seed),
    )


def require_component_seeds(
    spec: dict[str, Any],
    *,
    replicate_seed: int,
    gridlabd_random_seed: int,
    explicit_noise_seed: int | None,
    allowed: Iterable[str],
    purpose: str,
) -> tuple[str, ComponentSeeds]:
    partition = require_seed_partition(
        spec, replicate_seed, allowed=allowed, purpose=purpose
    )
    assignment = derive_component_seeds(
        spec, replicate_seed, gridlabd_random_seed=gridlabd_random_seed
    )
    if (explicit_noise_seed is not None
            and int(explicit_noise_seed) != assignment.measurement_noise_seed):
        raise SeedGuardError(
            "measurement-noise seed drift: "
            f"expected {assignment.measurement_noise_seed} from replicate seed "
            f"{replicate_seed}, received {int(explicit_noise_seed)}"
        )
    return partition, assignment


def gridlabd_random_seed(path: str | Path) -> int:
    """Read the explicit GridLAB-D seed from exact source bytes."""
    text = Path(path).read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^\s*#set\s+randomseed\s*=\s*(-?\d+)\s*;", text)
    if len(matches) != 1:
        raise SeedGuardError(
            f"expected exactly one explicit GridLAB-D randomseed in {path}, "
            f"found {len(matches)}"
        )
    return int(matches[0])
