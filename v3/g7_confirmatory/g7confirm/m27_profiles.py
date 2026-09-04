"""Frozen crossed-anchor runtime profiles for the M27 coverage gate."""

from __future__ import annotations

from typing import Any


M27_CELLS: tuple[dict[str, Any], ...] = (
    {"seed": 6102, "operating_point": "responsive_night"},
    {"seed": 6103, "operating_point": "responsive_night"},
    {"seed": 6102, "operating_point": "responsive_morning"},
    {"seed": 6102, "operating_point": "responsive_midday"},
    {"seed": 6102, "operating_point": "responsive_evening"},
    {"seed": 6102, "operating_point": "voltage_ceiling"},
)

TARGET_IDS = ("DER_EV1_BESS", "DER_EV4_BESS")
PROBE_MAGNITUDE_KW = 30.0
WINDOWS = 3
WINDOW_SECONDS = 10


def cell_id(seed: int, operating_point: str) -> str:
    """Return the canonical cell identifier."""

    return f"seed{int(seed)}_{operating_point}"


def pair_id(seed: int, operating_point: str) -> str:
    """Return the runtime pairing identifier for one M27 cell."""

    return f"m27_system_identification_{cell_id(seed, operating_point)}"


def treatment_definitions(seed: int, operating_point: str) -> tuple[dict[str, Any], ...]:
    """Return the five preregistered treatments for one M27 cell."""

    suffix = cell_id(seed, operating_point)
    return (
        {
            "id": "benign",
            "target_id": None,
            "command_kw": 0.0,
            "action_id": f"m27_benign_{suffix}",
            "action_request": "benign_action_request.json",
        },
        {
            "id": "probe_ev1_plus30",
            "target_id": "DER_EV1_BESS",
            "command_kw": 30.0,
            "action_id": f"m27_probe_ev1_plus30_{suffix}",
            "action_request": "probe_ev1_plus30_action_request.json",
        },
        {
            "id": "probe_ev1_minus30",
            "target_id": "DER_EV1_BESS",
            "command_kw": -30.0,
            "action_id": f"m27_probe_ev1_minus30_{suffix}",
            "action_request": "probe_ev1_minus30_action_request.json",
        },
        {
            "id": "probe_ev4_plus30",
            "target_id": "DER_EV4_BESS",
            "command_kw": 30.0,
            "action_id": f"m27_probe_ev4_plus30_{suffix}",
            "action_request": "probe_ev4_plus30_action_request.json",
        },
        {
            "id": "probe_ev4_minus30",
            "target_id": "DER_EV4_BESS",
            "command_kw": -30.0,
            "action_id": f"m27_probe_ev4_minus30_{suffix}",
            "action_request": "probe_ev4_minus30_action_request.json",
        },
    )


def build_runtime_profiles() -> dict[str, dict[str, Any]]:
    """Build the six exact profiles injected by the M27 runtime wrapper."""

    profiles: dict[str, dict[str, Any]] = {}
    for cell in M27_CELLS:
        seed = int(cell["seed"])
        operating_point = str(cell["operating_point"])
        treatments = treatment_definitions(seed, operating_point)
        by_id = {item["id"]: item for item in treatments}
        profiles[pair_id(seed, operating_point)] = {
            "seed": seed,
            "operating_point": operating_point,
            "windows": WINDOWS,
            "window_seconds": WINDOW_SECONDS,
            "attack_window_cap": 1,
            "attack_energy_cap_kvah": 2.0,
            "partition_role": "system_identification",
            "action_type": "simulator_execution",
            "benign_action_id": by_id["benign"]["action_id"],
            "probe_action_ids": {
                "DER_EV1_BESS:+30": by_id["probe_ev1_plus30"]["action_id"],
                "DER_EV1_BESS:-30": by_id["probe_ev1_minus30"]["action_id"],
                "DER_EV4_BESS:+30": by_id["probe_ev4_plus30"]["action_id"],
                "DER_EV4_BESS:-30": by_id["probe_ev4_minus30"]["action_id"],
            },
            "probe_treatment_ids": {
                "DER_EV1_BESS:+30": "probe_ev1_plus30",
                "DER_EV1_BESS:-30": "probe_ev1_minus30",
                "DER_EV4_BESS:+30": "probe_ev4_plus30",
                "DER_EV4_BESS:-30": "probe_ev4_minus30",
            },
            "budget_id": f"m27_{cell_id(seed, operating_point)}_three_windows_symmetric_30kw",
        }
    return profiles


M27_RUNTIME_PROFILES = build_runtime_profiles()

