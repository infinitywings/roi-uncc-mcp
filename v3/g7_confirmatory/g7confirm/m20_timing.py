"""Build create-once evidence for the M20 two-window timing qualification."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from .m19_qualification import _load_json, _normalise_commands, _sha256
from .manifest import build_manifest, create_once_json


SCHEMA_VERSION = "grideval-g7-m20-two-window-timing/v1"
CLASSIFICATION = "PRELIMINARY_ONLY"
PAIR_ID = "m20_pair_runtime_qualification_seed5102"
REPLICATE_SEED = 5102
FINAL_EVALUATION_SEEDS = tuple(range(9101, 9113))


def _finite_delta(a: Any, b: Any, label: str) -> float:
    delta = float(a) - float(b)
    if not math.isfinite(delta):
        raise ValueError(f"non-finite paired delta for {label}")
    return delta


def _load_coupling_recorders(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Read GridLAB-D's received DER power at each completed recorder step."""

    recorders: dict[str, list[dict[str, Any]]] = {}
    paths = sorted((run_dir / "output").glob("multi_der_*_coupling.csv"))
    if len(paths) != 4:
        raise ValueError(f"expected four DER coupling recorders, found {len(paths)}")
    for path in paths:
        lines = [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("#") or line.startswith("# timestamp")
        ]
        rows = list(csv.DictReader(lines))
        if len(rows) != 2:
            raise ValueError(f"coupling recorder length drift: {path}")
        power_key = next(
            (key for key in rows[0] if key.startswith("constant_power_")),
            None,
        )
        if power_key is None:
            raise ValueError(f"coupling recorder missing constant power: {path}")
        recorders[path.stem] = [
            {
                "timestamp": row["# timestamp"],
                "received_power_va": [
                    complex(row[power_key]).real,
                    complex(row[power_key]).imag,
                ],
            }
            for row in rows
        ]
    return recorders


def _validate_run(run_dir: Path, treatment: str) -> dict[str, Any]:
    required = {
        "integration": run_dir / "runtime_integration.json",
        "summary": run_dir / "g7_summary.json",
        "attack": run_dir / "attack_trace.json",
        "budget": run_dir / "dual_budget_trace.json",
        "devices": run_dir / "multi_der_traces.json",
        "source": run_dir / "multi_der_source.json",
        "gridlabd_log": run_dir / "gridlabd.log",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise ValueError(f"{treatment} run missing artifacts: {missing}")

    integration = _load_json(required["integration"])
    summary = _load_json(required["summary"])
    attack_trace = _load_json(required["attack"])
    budget = _load_json(required["budget"])
    device_traces = _load_json(required["devices"])
    source_trace = _load_json(required["source"])
    coupling_recorders = _load_coupling_recorders(run_dir)

    if integration.get("classification") != CLASSIFICATION:
        raise ValueError(f"{treatment} classification drift")
    if integration.get("campaign_authorized") is not False:
        raise ValueError(f"{treatment} campaign flag opened")
    if integration.get("evaluation_opened") is not False:
        raise ValueError(f"{treatment} evaluation flag opened")
    if integration.get("status") != "passed":
        raise ValueError(f"{treatment} runtime did not pass")
    if int(integration.get("runtime_window_limit", -1)) != 2:
        raise ValueError(f"{treatment} runtime window cap drift")
    lineage = integration.get("seed_lineage", {})
    if lineage.get("partition") != "runtime_qualification":
        raise ValueError(f"{treatment} preliminary partition drift")
    if int(lineage.get("replicate_seed", -1)) != REPLICATE_SEED:
        raise ValueError(f"{treatment} seed drift")
    pairing = integration.get("pairing", {})
    if pairing != {
        "pair_id": PAIR_ID,
        "treatment": treatment,
        "matched_seed": REPLICATE_SEED,
    }:
        raise ValueError(f"{treatment} pair lineage drift")
    if int(summary.get("windows", -1)) != 2:
        raise ValueError(f"{treatment} did not execute exactly two windows")
    if int(summary.get("gridlabd_returncode", -1)) != 0:
        raise ValueError(f"{treatment} GridLAB-D did not exit zero")
    if len(attack_trace) != 2 or len(source_trace) != 2:
        raise ValueError(f"{treatment} trace length drift")
    if not isinstance(device_traces, dict) or not device_traces:
        raise ValueError(f"{treatment} device traces are empty")
    if any(len(rows) != 2 for rows in device_traces.values()):
        raise ValueError(f"{treatment} device trace length drift")
    if budget.get("delivery_reconciled") is not True:
        raise ValueError(f"{treatment} delivery reconciliation failed")
    records = budget.get("records", [])
    if len(records) != 2 or any(
        record.get("runner_noted") is not True for record in records
    ):
        raise ValueError(f"{treatment} budget trace is incomplete")

    windows: list[dict[str, Any]] = []
    for index in range(2):
        requested = _normalise_commands(records[index].get("proposed", {}))
        accepted = _normalise_commands(records[index].get("admitted", {}))
        delivered = _normalise_commands(records[index].get("delivered", {}))
        if accepted != delivered:
            raise ValueError(
                f"{treatment} accepted/delivered drift in window {index}"
            )
        device_state = {
            device_id: {
                "voltage_pu": float(rows[index]["v_pu"]),
                "measured_voltage_pu": float(rows[index]["v_pu_meas"]),
                "command_kw_kvar": [
                    float(rows[index]["cmd_p_kw"]),
                    float(rows[index]["cmd_q_kvar"]),
                ],
                "realized_kw_kvar": [
                    float(rows[index]["p_kw"]),
                    float(rows[index]["q_kvar"]),
                ],
                "perturbed": bool(rows[index]["perturbed"]),
            }
            for device_id, rows in sorted(device_traces.items())
        }
        windows.append({
            "window": index,
            "time_s": attack_trace[index]["t"],
            "true_voltage_pu": attack_trace[index]["telemetry"],
            "measured_voltage_pu": attack_trace[index]["telemetry_meas"],
            "source_power_w_var": source_trace[index],
            "requested_commands_kw_kvar": requested,
            "accepted_commands_kw_kvar": accepted,
            "delivered_commands_kw_kvar": delivered,
            "devices": device_state,
        })

    if treatment == "benign":
        if summary.get("arm") != "benign":
            raise ValueError("benign arm drift")
        if any(
            window["requested_commands_kw_kvar"]
            or window["accepted_commands_kw_kvar"]
            or window["delivered_commands_kw_kvar"]
            for window in windows
        ):
            raise ValueError("benign trace contains a perturbation")
        if int(budget.get("windows_spent", -1)) != 0:
            raise ValueError("benign trace spent attack budget")
    else:
        if summary.get("arm") != "scripted_max":
            raise ValueError("attack arm drift")
        if not windows[0]["delivered_commands_kw_kvar"]:
            raise ValueError("attack window delivered no perturbation")
        if windows[1]["delivered_commands_kw_kvar"]:
            raise ValueError("attack exceeded its one-window intervention cap")
        if int(budget.get("windows_spent", -1)) != 1:
            raise ValueError("attack did not spend exactly one perturbed window")

    return {
        "treatment": treatment,
        "run_dir": run_dir.as_posix(),
        "seed_lineage": lineage,
        "operating_point": integration["operating_point"],
        "dependency_hashes": integration["dependency_hashes"],
        "detector_defense_state": integration["detector_defense_state"],
        "budget": {
            key: budget[key]
            for key in (
                "window_cap",
                "apparent_energy_cap_kvah",
                "windows_spent",
                "admitted_energy_kvah",
                "delivered_command_energy_kvah",
                "delivery_reconciled",
            )
        },
        "windows": windows,
        "gridlabd_received_DER_power": coupling_recorders,
        "artifact_sha256": {
            name: _sha256(path) for name, path in sorted(required.items())
        },
    }


def build_timing_qualification(
    *,
    root: Path,
    image_id: str,
    benign_container: str,
    attack_container: str,
) -> dict[str, Any]:
    """Validate the pair and calculate the first post-actuation deltas."""

    benign = _validate_run(root / "benign", "benign")
    attack = _validate_run(root / "attack", "attack")
    for field in ("seed_lineage", "operating_point", "dependency_hashes"):
        if benign[field] != attack[field]:
            raise ValueError(f"paired {field} drift")
    for field in (
        "true_voltage_pu",
        "measured_voltage_pu",
        "source_power_w_var",
    ):
        if benign["windows"][0][field] != attack["windows"][0][field]:
            raise ValueError(f"pre-intervention window-1 {field} drift")

    execution = _load_json(root / "runtime_execution.json")
    expected_containers = [benign_container, attack_container]
    if execution.get("classification") != CLASSIFICATION:
        raise ValueError("runtime execution classification drift")
    if execution.get("container_image_id") != image_id:
        raise ValueError("runtime image identity drift")
    if execution.get("container_names") != expected_containers:
        raise ValueError("runtime container identity drift")
    if execution.get("container_exit_codes") != {
        benign_container: 0,
        attack_container: 0,
    }:
        raise ValueError("runtime container exit status drift")
    if execution.get("teardown_verified") is not True:
        raise ValueError("runtime teardown was not verified")
    if execution.get("network_mode") != "none":
        raise ValueError("runtime container was not network-isolated")

    benign_post = benign["windows"][1]
    attack_post = attack["windows"][1]
    voltage_deltas = {
        device_id: _finite_delta(
            attack_post["true_voltage_pu"][device_id],
            benign_post["true_voltage_pu"][device_id],
            f"{device_id}.voltage_pu",
        )
        for device_id in sorted(benign_post["true_voltage_pu"])
    }
    source_deltas = {
        "source_p_w": _finite_delta(
            attack_post["source_power_w_var"]["source_p_w"],
            benign_post["source_power_w_var"]["source_p_w"],
            "source_p_w",
        ),
        "source_q_var": _finite_delta(
            attack_post["source_power_w_var"]["source_q_var"],
            benign_post["source_power_w_var"]["source_q_var"],
            "source_q_var",
        ),
    }
    nonzero_tolerance = 1e-12
    response_observed = any(
        abs(delta) > nonzero_tolerance for delta in voltage_deltas.values()
    ) or any(
        abs(delta) > nonzero_tolerance for delta in source_deltas.values()
    )
    attack_coupling_nonzero = any(
        abs(component) > nonzero_tolerance
        for rows in attack["gridlabd_received_DER_power"].values()
        for row in rows
        for component in row["received_power_va"]
    )
    status = (
        "TWO_WINDOW_POST_ACTUATION_TIMING_QUALIFIED"
        if response_observed
        else "TWO_WINDOW_OBSERVATION_LATENCY_GAP"
    )
    files = [
        path for path in root.rglob("*")
        if path.is_file() and path.name != "m20_two_window_timing.json"
    ]
    manifest = build_manifest(
        root=root,
        files=files,
        metadata={
            "milestone": "M20",
            "classification": CLASSIFICATION,
            "pair_id": PAIR_ID,
            "replicate_seed": REPLICATE_SEED,
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "milestone": "M20",
        "classification": CLASSIFICATION,
        "status": status,
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "final_evaluation_seeds_accessed": [],
        "final_evaluation_seeds_remain_sealed": list(FINAL_EVALUATION_SEEDS),
        "pair_id": PAIR_ID,
        "replicate_seed": REPLICATE_SEED,
        "runtime_environment": execution,
        "runs": [benign, attack],
        "paired_checks": {
            "controlled_lineage_equal": True,
            "window_1_true_voltage_equal": True,
            "window_1_measured_voltage_equal": True,
            "window_1_source_power_equal": True,
            "accepted_equals_delivered": True,
            "one_perturbed_window_only": True,
        },
        "post_actuation_window_2": {
            "time_s": attack_post["time_s"],
            "true_voltage_delta_attack_minus_benign_pu": voltage_deltas,
            "source_power_delta_attack_minus_benign_w_var": source_deltas,
            "nonzero_paired_response_observed": response_observed,
            "attack_power_visible_in_completed_GridLAB_D_recorders": (
                attack_coupling_nonzero
            ),
        },
        "operational_anomalies": execution["retained_warnings"],
        "scientific_scope": {
            "establishes": ([
                "post_actuation_observation_timing",
                "finite_nonzero_paired_window_2_response",
                "two_window_command_admission_delivery_and_reset_lineage",
            ] if response_observed else [
                "two_windows_are_insufficient_for_feeder_response_observation",
                "GridLAB_D_completed_recorders_do_not_yet_contain_the_attack_power",
                "two_window_command_admission_delivery_and_reset_lineage",
            ]),
            "does_not_establish": [
                "attack_harm_distribution",
                "detector_or_defense_effectiveness",
                "stealth_or_long_horizon_behavior",
                "LLM_attacker_advantage",
                "confirmatory_or_generalizable_effects",
            ],
            "next_gate": (
                "A separately authorized three-window timing test is required; "
                "M20 performs no automatic retry or duration expansion."
                if not response_observed else
                "The timing prerequisite is satisfied; design the same-surface "
                "LLM attacker gate without expanding authority."
            ),
        },
        "manifest": manifest,
    }


def verify_timing_qualification(root: Path) -> list[str]:
    """Verify checked-in M20 evidence without executing a simulator."""

    issues: list[str] = []
    try:
        payload = _load_json(root / "m20_two_window_timing.json")
    except (OSError, ValueError, TypeError) as exc:
        return [f"qualification_unreadable:{exc}"]
    expected = {
        "schema_version": SCHEMA_VERSION,
        "milestone": "M20",
        "classification": CLASSIFICATION,
        "status": "TWO_WINDOW_OBSERVATION_LATENCY_GAP",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "pair_id": PAIR_ID,
        "replicate_seed": REPLICATE_SEED,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            issues.append(f"field_drift:{field}")
    if payload.get("final_evaluation_seeds_accessed") != []:
        issues.append("final_evaluation_accessed")
    if payload.get("final_evaluation_seeds_remain_sealed") != list(
        FINAL_EVALUATION_SEEDS
    ):
        issues.append("final_evaluation_seal_drift")
    entries = payload.get("manifest", {}).get("files", [])
    if not isinstance(entries, list) or not entries:
        issues.append("manifest_empty")
        return sorted(set(issues))
    for entry in entries:
        relative = Path(str(entry.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            issues.append(f"manifest_path_unscoped:{relative}")
            continue
        path = root / relative
        if not path.is_file():
            issues.append(f"manifest_missing:{relative}")
            continue
        if path.stat().st_size != entry.get("bytes"):
            issues.append(f"manifest_size_drift:{relative}")
        if _sha256(path) != entry.get("sha256"):
            issues.append(f"manifest_sha256_drift:{relative}")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--image-id")
    parser.add_argument("--benign-container")
    parser.add_argument("--attack-container")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        issues = verify_timing_qualification(args.root.resolve())
        print(json.dumps({"issues": issues}, indent=2))
        return int(bool(issues))
    if not all((args.image_id, args.benign_container, args.attack_container)):
        parser.error("build mode requires image and container identities")
    payload = build_timing_qualification(
        root=args.root.resolve(),
        image_id=args.image_id,
        benign_container=args.benign_container,
        attack_container=args.attack_container,
    )
    create_once_json(args.root / "m20_two_window_timing.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "pair_id": payload["pair_id"],
        "classification": payload["classification"],
        "post_actuation_window_2": payload["post_actuation_window_2"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
