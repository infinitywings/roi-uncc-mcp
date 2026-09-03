"""Build create-once evidence for the M19 paired runtime qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .manifest import build_manifest, create_once_json


SCHEMA_VERSION = "grideval-g7-m19-runtime-qualification/v1"
CLASSIFICATION = "PRELIMINARY_ONLY"
PAIR_ID = "m19_pair_runtime_qualification_seed5101"
REPLICATE_SEED = 5101
FINAL_EVALUATION_SEEDS = tuple(range(9101, 9113))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: Any, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite {label}: {value!r}")
    return number


def _normalise_commands(raw: Mapping[str, Any]) -> dict[str, list[float]]:
    commands: dict[str, list[float]] = {}
    for device_id, command in raw.items():
        if not isinstance(command, (list, tuple)) or len(command) != 2:
            raise ValueError(f"invalid command for {device_id}")
        commands[device_id] = [
            _finite(command[0], f"{device_id}.p_kw"),
            _finite(command[1], f"{device_id}.q_kvar"),
        ]
    return commands


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

    if integration.get("classification") != CLASSIFICATION:
        raise ValueError(f"{treatment} classification drift")
    if integration.get("campaign_authorized") is not False:
        raise ValueError(f"{treatment} campaign flag opened")
    if integration.get("evaluation_opened") is not False:
        raise ValueError(f"{treatment} evaluation flag opened")
    if integration.get("status") != "passed":
        raise ValueError(f"{treatment} runtime did not pass")
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
    if int(summary.get("windows", -1)) != 1:
        raise ValueError(f"{treatment} runtime exceeded one window")
    if int(summary.get("gridlabd_returncode", -1)) != 0:
        raise ValueError(f"{treatment} GridLAB-D did not exit zero")
    if len(attack_trace) != 1 or len(source_trace) != 1:
        raise ValueError(f"{treatment} trace length drift")
    if not isinstance(device_traces, dict) or not device_traces:
        raise ValueError(f"{treatment} device traces are empty")
    if any(len(rows) != 1 for rows in device_traces.values()):
        raise ValueError(f"{treatment} device trace length drift")
    if budget.get("delivery_reconciled") is not True:
        raise ValueError(f"{treatment} delivery reconciliation failed")
    records = budget.get("records", [])
    if len(records) != 1 or records[0].get("runner_noted") is not True:
        raise ValueError(f"{treatment} budget trace is incomplete")

    requested = _normalise_commands(records[0].get("proposed", {}))
    accepted = _normalise_commands(records[0].get("admitted", {}))
    delivered = _normalise_commands(records[0].get("delivered", {}))
    commanded: dict[str, list[float]] = {}
    realized: dict[str, list[float]] = {}
    for device_id, rows in sorted(device_traces.items()):
        row = rows[0]
        commanded[device_id] = [
            _finite(row["cmd_p_kw"], f"{device_id}.cmd_p_kw"),
            _finite(row["cmd_q_kvar"], f"{device_id}.cmd_q_kvar"),
        ]
        realized[device_id] = [
            _finite(row["p_kw"], f"{device_id}.p_kw"),
            _finite(row["q_kvar"], f"{device_id}.q_kvar"),
        ]

    if treatment == "benign":
        if summary.get("arm") != "benign":
            raise ValueError("benign arm drift")
        if requested or accepted or delivered:
            raise ValueError("benign trace contains a perturbation")
        if int(budget.get("windows_spent", -1)) != 0:
            raise ValueError("benign trace spent attack budget")
    else:
        if summary.get("arm") != "scripted_max":
            raise ValueError("attack arm drift")
        if not requested or not accepted or not delivered:
            raise ValueError("attack trace contains no delivered perturbation")
        if accepted != delivered:
            raise ValueError("accepted and delivered attack commands differ")

    return {
        "treatment": treatment,
        "run_dir": run_dir.as_posix(),
        "seed_lineage": lineage,
        "operating_point": integration["operating_point"],
        "dependency_hashes": integration["dependency_hashes"],
        "detector_defense_state": integration["detector_defense_state"],
        "requested_commands_kw_kvar": requested,
        "accepted_commands_kw_kvar": accepted,
        "delivered_commands_kw_kvar": delivered,
        "commanded_all_devices_kw_kvar": commanded,
        "realized_all_devices_kw_kvar": realized,
        "true_voltage_pu": attack_trace[0]["telemetry"],
        "measured_voltage_pu": attack_trace[0]["telemetry_meas"],
        "source_power_w_var": source_trace[0],
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
        "artifact_sha256": {
            name: _sha256(path) for name, path in sorted(required.items())
        },
    }


def build_qualification(
    *,
    root: Path,
    service_preflight: Path,
    image_id: str,
    benign_container: str,
    attack_container: str,
    teardown_verified: bool,
) -> dict[str, Any]:
    """Validate the matched pair and return its preliminary evidence record."""

    benign = _validate_run(root / "benign", "benign")
    attack = _validate_run(root / "attack", "attack")
    for field in ("seed_lineage", "operating_point", "dependency_hashes"):
        if benign[field] != attack[field]:
            raise ValueError(f"paired {field} drift")
    if benign["true_voltage_pu"] != attack["true_voltage_pu"]:
        raise ValueError("paired pre-actuation physical state drift")
    if benign["measured_voltage_pu"] != attack["measured_voltage_pu"]:
        raise ValueError("paired measurement-noise realization drift")
    if benign["source_power_w_var"] != attack["source_power_w_var"]:
        raise ValueError("paired pre-actuation source state drift")
    if not teardown_verified:
        raise ValueError("ephemeral runtime teardown was not verified")

    services = _load_json(service_preflight)
    if services.get("classification") != CLASSIFICATION:
        raise ValueError("service preflight classification drift")
    if services.get("model_or_embedding_service_started_or_restarted") is not False:
        raise ValueError("service preflight requested a model lifecycle change")
    if services.get("llm", {}).get("probe_status") != "passed":
        raise ValueError("LLM service preflight did not pass")
    if services.get("embedding", {}).get("probe_status") != "passed":
        raise ValueError("embedding service preflight did not pass")

    execution_path = root / "runtime_execution.json"
    execution = _load_json(execution_path)
    if execution.get("classification") != CLASSIFICATION:
        raise ValueError("runtime execution classification drift")
    if execution.get("container_image_id") != image_id:
        raise ValueError("runtime image identity drift")
    expected_containers = [benign_container, attack_container]
    if execution.get("container_names") != expected_containers:
        raise ValueError("runtime container identity drift")
    if execution.get("container_exit_codes") != {
        benign_container: 0,
        attack_container: 0,
    }:
        raise ValueError("runtime container exit status drift")
    if execution.get("teardown_verified") is not True:
        raise ValueError("runtime execution did not retain teardown evidence")
    if execution.get("network_mode") != "none":
        raise ValueError("runtime container was not network-isolated")

    deltas = {
        device_id: [
            attack["realized_all_devices_kw_kvar"][device_id][axis]
            - benign["realized_all_devices_kw_kvar"][device_id][axis]
            for axis in (0, 1)
        ]
        for device_id in sorted(benign["realized_all_devices_kw_kvar"])
    }
    files = [
        path for path in root.rglob("*")
        if path.is_file() and path.name != "m19_runtime_qualification.json"
    ]
    manifest = build_manifest(
        root=root,
        files=files,
        metadata={
            "milestone": "M19",
            "classification": CLASSIFICATION,
            "pair_id": PAIR_ID,
            "replicate_seed": REPLICATE_SEED,
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "milestone": "M19",
        "classification": CLASSIFICATION,
        "status": "BOUNDED_PAIRED_RUNTIME_QUALIFIED",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "final_evaluation_seeds_accessed": [],
        "final_evaluation_seeds_remain_sealed": list(FINAL_EVALUATION_SEEDS),
        "pair_id": PAIR_ID,
        "replicate_seed": REPLICATE_SEED,
        "service_preflight": services,
        "runtime_environment": execution,
        "operational_anomalies": execution["retained_warnings"],
        "runs": [benign, attack],
        "paired_checks": {
            "controlled_lineage_equal": True,
            "pre_actuation_physical_state_equal": True,
            "measurement_noise_realization_equal": True,
            "source_state_equal": True,
            "accepted_equals_delivered": True,
        },
        "realized_attack_minus_benign_kw_kvar": deltas,
        "scientific_scope": {
            "establishes": [
                "single_window_paired_runtime_plumbing",
                "deterministic_attack_command_admission_and_delivery",
                "OpenDER_realization_under_a_simulated_feeder",
            ],
            "does_not_establish": [
                "post_actuation_grid_harm",
                "detector_or_defense_effectiveness",
                "multi_window_stability_or_stealth",
                "campaign_throughput",
                "confirmatory_or_generalizable_effects",
            ],
            "single_window_limit": (
                "The sampled voltage and source state precede command actuation; "
                "a later bounded multi-window pilot is required for grid-response effects."
            ),
        },
        "manifest": manifest,
    }


def verify_qualification(root: Path) -> list[str]:
    """Verify the checked-in M19 result without executing a runtime action."""

    issues: list[str] = []
    result_path = root / "m19_runtime_qualification.json"
    try:
        payload = _load_json(result_path)
    except (OSError, ValueError, TypeError) as exc:
        return [f"qualification_unreadable:{exc}"]
    expected_scalars = {
        "schema_version": SCHEMA_VERSION,
        "milestone": "M19",
        "classification": CLASSIFICATION,
        "status": "BOUNDED_PAIRED_RUNTIME_QUALIFIED",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "pair_id": PAIR_ID,
        "replicate_seed": REPLICATE_SEED,
    }
    for field, expected in expected_scalars.items():
        if payload.get(field) != expected:
            issues.append(f"field_drift:{field}")
    if payload.get("final_evaluation_seeds_accessed") != []:
        issues.append("final_evaluation_accessed")
    if payload.get("final_evaluation_seeds_remain_sealed") != list(
        FINAL_EVALUATION_SEEDS
    ):
        issues.append("final_evaluation_seal_drift")

    manifest = payload.get("manifest", {})
    entries = manifest.get("files", [])
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
    parser.add_argument("--service-preflight", type=Path)
    parser.add_argument("--image-id")
    parser.add_argument("--benign-container")
    parser.add_argument("--attack-container")
    parser.add_argument("--teardown-verified", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        issues = verify_qualification(args.root.resolve())
        print(json.dumps({"issues": issues}, indent=2))
        return int(bool(issues))
    if not all((
        args.service_preflight,
        args.image_id,
        args.benign_container,
        args.attack_container,
    )):
        parser.error(
            "build mode requires service preflight, image, and container identities"
        )
    payload = build_qualification(
        root=args.root.resolve(),
        service_preflight=args.service_preflight.resolve(),
        image_id=args.image_id,
        benign_container=args.benign_container,
        attack_container=args.attack_container,
        teardown_verified=args.teardown_verified,
    )
    create_once_json(args.root / "m19_runtime_qualification.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "pair_id": payload["pair_id"],
        "classification": payload["classification"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
