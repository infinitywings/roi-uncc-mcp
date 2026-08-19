#!/usr/bin/env python3
"""Freeze a no-attack NATIG IEEE-123 configuration without editing upstream."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_SOURCE_SHA256 = (
    "5a4ae5354a514a6b65d33220a2b1e37bbd1e076b8dce6d2b3cf15c217d513a14"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-config-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_config_dir.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)

    source_grid = source / "grid.json"
    if sha256(source_grid) != EXPECTED_SOURCE_SHA256:
        raise ValueError("source grid.json does not match the pinned G1 preset")
    grid = json.loads(source_grid.read_text(encoding="utf-8"))
    if not (
        len(grid.get("Simulation", [])) == 1
        and len(grid.get("Controller", [])) == 1
        and len(grid.get("DDoS", [])) == 1
    ):
        raise ValueError("unexpected NATIG control-array cardinality")
    original_grid = json.loads(json.dumps(grid))
    before = {
        "includeMIM": grid["Simulation"][0]["includeMIM"],
        "controller_use": grid["Controller"][0]["use"],
        "ddos_active": grid["DDoS"][0]["Active"],
    }
    grid["Simulation"][0]["includeMIM"] = 0
    grid["Controller"][0]["use"] = 0
    grid["DDoS"][0]["Active"] = 0

    overlay = output / "grid.json"
    overlay.write_text(
        json.dumps(grid, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    after = {
        "includeMIM": grid["Simulation"][0]["includeMIM"],
        "controller_use": grid["Controller"][0]["use"],
        "ddos_active": grid["DDoS"][0]["Active"],
    }
    assert after == {
        "includeMIM": 0,
        "controller_use": 0,
        "ddos_active": 0,
    }

    preserved = {
        "sim_time_s": grid["Simulation"][0]["SimTime"],
        "poll_request_frequency_s": grid["Simulation"][0]["PollReqFreq"],
        "static_seed_enabled": grid["Simulation"][0]["StaticSeed"],
        "random_seed": grid["Simulation"][0]["RandomSeed"],
        "dynamic_topology": grid["Simulation"][0]["UseDynTop"],
    }
    manifest = {
        "schema_version": "1.0",
        "purpose": "NATIG IEEE-123 no-attack component proof",
        "source": {
            "path": str(source_grid),
            "sha256": sha256(source_grid),
            "attack_state": before,
        },
        "overlay": {
            "path": overlay.name,
            "sha256": sha256(overlay),
            "attack_state": after,
        },
        "preserved_settings": preserved,
        "assertions": {
            "mitm_disabled": after["includeMIM"] == 0,
            "ddos_disabled": after["ddos_active"] == 0,
            "dynamic_route_controller_disabled": after["controller_use"] == 0,
            "twenty_second_duration": preserved["sim_time_s"] == 20,
            "fixed_network_seed": preserved["random_seed"] == 777,
            "exact_semantic_diff": (
                original_grid["Simulation"][0]["includeMIM"] == 1
                and grid["Simulation"][0]["includeMIM"] == 0
                and {
                    **grid,
                    "Simulation": [
                        {
                            **grid["Simulation"][0],
                            "includeMIM": 1,
                        }
                    ],
                }
                == original_grid
            ),
        },
    }
    if not all(manifest["assertions"].values()):
        raise AssertionError(f"overlay invariant failed: {manifest['assertions']}")
    (output / "overlay_manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"source_attack_state={before} overlay_attack_state={after} "
        f"overlay_sha256={manifest['overlay']['sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
