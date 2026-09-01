"""Deterministic, non-executable campaign-plan expansion."""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from collections import Counter
from typing import Any

from .spec import SpecError, spec_sha256, validate_spec


def _stable_seed(parts: tuple[Any, ...]) -> int:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def _run_id(fields: dict[str, Any]) -> str:
    encoded = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "g7c_" + hashlib.sha256(encoded).hexdigest()[:20]


def _candidate_order(spec: dict[str, Any], arm: str, cell: tuple[Any, ...]) -> list[dict[str, Any]]:
    space = [
        {"amplitude_fraction": float(amplitude), "period_windows": int(period)}
        for amplitude, period in itertools.product(
            spec["candidate_space"]["amplitude_fractions"],
            spec["candidate_space"]["period_windows"],
        )
    ]
    if arm == "fixed_grid":
        # Space-filling deterministic order, not sorted around legacy optima.
        lo, hi = 0, len(space) - 1
        order: list[dict[str, Any]] = []
        while lo <= hi:
            order.append(space[lo])
            lo += 1
            if lo <= hi:
                order.append(space[hi])
                hi -= 1
        return order
    if arm == "random_search":
        shuffled = list(space)
        random.Random(_stable_seed((spec["protocol_id"], arm, *cell))).shuffle(shuffled)
        return shuffled
    return []


def expand_profile(spec: dict[str, Any], profile_name: str) -> dict[str, Any]:
    validate_spec(spec)
    if profile_name not in spec["profiles"]:
        raise SpecError(f"unknown profile: {profile_name}")
    profile = spec["profiles"][profile_name]
    proposal_count = int(profile["proposal_count"])
    arms = list(spec["search"]["arms"])
    seeds = list(map(int, profile["development_seeds"][:proposal_count]))
    budget_energy = float(spec["budgets"]["primary"]["apparent_energy_kvah"])

    runs: list[dict[str, Any]] = []
    cells = itertools.product(
        profile["operating_points"],
        profile["volt_var"],
        profile["measurement_noise_pu"],
        profile["budget_windows"],
    )
    for operating_point, volt_var, noise, window_cap in cells:
        cell = (operating_point, bool(volt_var), float(noise), int(window_cap))
        for arm in arms:
            order = _candidate_order(spec, arm, cell)
            for index in range(proposal_count):
                proposal = order[index] if order else None
                fields = {
                    "protocol_id": spec["protocol_id"],
                    "profile": profile_name,
                    "partition": "development",
                    "operating_point": operating_point,
                    "volt_var": bool(volt_var),
                    "measurement_noise_pu": float(noise),
                    "window_cap": int(window_cap),
                    "energy_cap_kvah": budget_energy,
                    "arm": arm,
                    "proposal_index": index,
                    "seed": seeds[index],
                    "proposal": proposal,
                }
                fields["run_id"] = _run_id(fields)
                fields["status"] = "requires_model_proposal" if proposal is None else "planned"
                fields["executable"] = False
                runs.append(fields)

    validate_equal_outer_budget(runs, arms, proposal_count)
    return {
        "schema_version": "grideval-g7-campaign-plan/v1",
        "protocol_id": spec["protocol_id"],
        "spec_sha256": spec_sha256(spec),
        "profile": profile_name,
        "campaign_authorized": False,
        "executable": False,
        "outer_budget_per_arm_per_cell": proposal_count,
        "runs": runs,
    }


def validate_equal_outer_budget(runs: list[dict[str, Any]], arms: list[str], k: int) -> None:
    counts: Counter[tuple[Any, ...]] = Counter()
    for run in runs:
        cell_arm = (
            run["operating_point"], run["volt_var"], run["measurement_noise_pu"],
            run["window_cap"], run["arm"],
        )
        counts[cell_arm] += 1
    cells = {key[:-1] for key in counts}
    for cell in cells:
        for arm in arms:
            if counts[cell + (arm,)] != k:
                raise SpecError(f"unequal outer budget for cell={cell}, arm={arm}")

