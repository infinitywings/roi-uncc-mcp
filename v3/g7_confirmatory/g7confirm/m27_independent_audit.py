"""Independently audit the exact M27 package without importing its builder."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Mapping


AUDIT_SCHEMA_VERSION = "grideval-g7-m27-independent-audit/v1"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m27-repeatability-coverage-contract/v1"
EVIDENCE_SCHEMA_VERSION = "grideval-g7-m27-repeatability-coverage/v1"
CELL_SCHEMA_VERSION = "grideval-g7-m27-system-identification-cell/v1"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MZXYE3CTWNMRQ8YXA4H30F"
DECISION_ID = "dec_01M1MZWXXY65C3XXMERCAMT794"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
M23_ROOT = PACKAGE_ROOT / "artifacts" / "m23_system_identification_seed6101_attempt1"
M23_SOURCE = M23_ROOT / "m23_system_identification.json"
M23_AUDIT = M23_ROOT / "independent_audit_receipt.json"
M23_SOURCE_SHA256 = "30d003e06d016b88d49e024857c9b74a9f9f34012a6f022b6f3a26511fc619c1"
M23_AUDIT_SHA256 = "d0c3a539c20cc4dc3adb2910cd7bbba9c90a071a839ebc0fcde9d9e67f524030"
IMAGE_ID = "sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7"
TARGETS = ("DER_EV1_BESS", "DER_EV4_BESS")
DEVICES = ("DER_EV1_BESS", "DER_EV3_PV", "DER_EV4_BESS", "DER_EV5_PV")
OPERATING_POINTS = (
    "responsive_morning", "responsive_midday", "responsive_evening",
    "responsive_night", "voltage_ceiling",
)
NEW_CELLS = (
    (6102, "responsive_night"),
    (6103, "responsive_night"),
    (6102, "responsive_morning"),
    (6102, "responsive_midday"),
    (6102, "responsive_evening"),
    (6102, "voltage_ceiling"),
)
TREATMENTS = (
    ("benign", None, 0.0),
    ("probe_ev1_plus30", "DER_EV1_BESS", 30.0),
    ("probe_ev1_minus30", "DER_EV1_BESS", -30.0),
    ("probe_ev4_plus30", "DER_EV4_BESS", 30.0),
    ("probe_ev4_minus30", "DER_EV4_BESS", -30.0),
)
T95_DF2 = 4.302652729696142


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _copy(value: Any) -> Any:
    return json.loads(_canonical(value))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _cell_id(seed: int, operating_point: str) -> str:
    return f"seed{seed}_{operating_point}"


def _pair_id(seed: int, operating_point: str) -> str:
    return f"m27_system_identification_{_cell_id(seed, operating_point)}"


def _self_address(value: Mapping[str, Any], field: str, prefix: str) -> bool:
    content = _copy(value)
    identity = content.pop(field, None)
    return identity == prefix + _sha256_value(content)


def _audit_manifest(root: Path, manifest: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    entries = manifest.get("files")
    if manifest.get("algorithm") != "sha256" or not isinstance(entries, list):
        return ["manifest_shape_invalid"]
    seen: set[str] = set()
    total = 0
    for entry in entries:
        relative = str(entry.get("path", ""))
        relative_path = Path(relative)
        if not relative or relative in seen or relative_path.is_absolute() or ".." in relative_path.parts:
            issues.append("manifest_path_invalid_or_duplicate")
            continue
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.is_symlink():
            issues.append(f"manifest_file_missing:{relative}")
            continue
        size = path.stat().st_size
        total += size
        if entry.get("bytes") != size:
            issues.append(f"manifest_size_drift:{relative}")
        if entry.get("sha256") != _sha256(path):
            issues.append(f"manifest_sha256_drift:{relative}")
    if manifest.get("file_count") != len(entries):
        issues.append("manifest_file_count_drift")
    if manifest.get("total_bytes") != total:
        issues.append("manifest_total_bytes_drift")
    return issues


def _estimate_columns(runs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id = {run["treatment"]: run for run in runs}
    benign = by_id["benign"]["windows"][2]
    columns = []
    for target, plus_id, minus_id in (
        ("DER_EV1_BESS", "probe_ev1_plus30", "probe_ev1_minus30"),
        ("DER_EV4_BESS", "probe_ev4_plus30", "probe_ev4_minus30"),
    ):
        plus = by_id[plus_id]["windows"][2]
        minus = by_id[minus_id]["windows"][2]
        column: dict[str, Any] = {"target_id": target, "post_actuation_time_s": 30}
        for prefix, field in (("true", "true_voltage_pu"), ("measured", "measured_voltage_pu")):
            central = {device: (plus[field][device] - minus[field][device]) / 60.0 for device in DEVICES}
            plus_side = {device: (plus[field][device] - benign[field][device]) / 30.0 for device in DEVICES}
            minus_side = {device: (benign[field][device] - minus[field][device]) / 30.0 for device in DEVICES}
            residual = {device: (plus[field][device] + minus[field][device]) / 2.0 - benign[field][device] for device in DEVICES}
            column[f"central_{prefix}_voltage_gain_pu_per_kw"] = central
            column[f"plus_one_sided_{prefix}_voltage_gain_pu_per_kw"] = plus_side
            column[f"minus_one_sided_{prefix}_voltage_gain_pu_per_kw"] = minus_side
            column[f"centered_{prefix}_voltage_residual_pu"] = residual
            column[f"max_abs_{prefix}_voltage_gain_pu_per_kw"] = max(abs(value) for value in central.values())
            column[f"max_abs_centered_{prefix}_voltage_residual_pu"] = max(abs(value) for value in residual.values())
        column["central_source_power_gain_w_var_per_kw"] = {
            field: (plus["source_power_w_var"][field] - minus["source_power_w_var"][field]) / 60.0
            for field in ("source_p_w", "source_q_var")
        }
        column["centered_source_power_residual_w_var"] = {
            field: (plus["source_power_w_var"][field] + minus["source_power_w_var"][field]) / 2.0 - benign["source_power_w_var"][field]
            for field in ("source_p_w", "source_q_var")
        }
        columns.append(column)
    return _copy(columns)


def _rank(columns: list[Mapping[str, Any]], metric: str) -> dict[str, Any]:
    values = {column["target_id"]: column[metric] for column in columns}
    ordered = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    winner, winner_value = ordered[0]
    runner_up, runner_value = ordered[1]
    return {
        "metric": metric,
        "values": values,
        "winner": winner,
        "runner_up": runner_up,
        "absolute_margin": winner_value - runner_value,
        "ratio_margin": winner_value / runner_value if runner_value > 0.0 else None,
        "tie": math.isclose(winner_value, runner_value, rel_tol=0.0, abs_tol=1e-15),
    }


def _audit_contract(root: Path, contract: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        issues.append("contract_schema_drift")
    if not _self_address(contract, "contract_id", "m27contract_"):
        issues.append("contract_self_address_drift")
    for field, expected in (("project_id", PROJECT_ID), ("mission_id", MISSION_ID), ("decision_id", DECISION_ID)):
        if contract.get(field) != expected:
            issues.append(f"contract_{field}_drift")
    boundary = contract.get("access_boundary", {})
    for field in ("real_network", "LLM", "embedding", "detector", "defense", "physical_field_actuator", "final_evaluation", "resource_admission"):
        if boundary.get(field) is not False:
            issues.append(f"contract_boundary_open:{field}")
    design = contract.get("design", {})
    if design.get("new_cell_count") != 6 or design.get("new_runtime_run_cap") != 30 or design.get("retry_cap") != 0:
        issues.append("contract_cap_drift")
    if design.get("seed_by_operating_point_interaction_estimable") is not False:
        issues.append("contract_interaction_boundary_drift")
    cells = design.get("new_cells", [])
    observed = [(cell.get("seed"), cell.get("operating_point")) for cell in cells]
    if observed != list(NEW_CELLS):
        issues.append("contract_matrix_drift")
    action_ids: set[str] = set()
    request_count = 0
    for cell in cells:
        seed = cell["seed"]
        operating_point = cell["operating_point"]
        if cell.get("pair_id") != _pair_id(seed, operating_point):
            issues.append("contract_pair_id_drift")
        requests = cell.get("action_requests", {})
        if len(requests) != 6:
            issues.append(f"request_count_drift:{_cell_id(seed, operating_point)}")
        request_count += len(requests)
        for name, request in requests.items():
            action_id = request.get("action_id")
            if action_id in action_ids:
                issues.append("duplicate_action_id")
            action_ids.add(action_id)
            if request.get("partition_role") != "system_identification" or request.get("seed") != seed:
                issues.append(f"request_partition_or_seed_drift:{action_id}")
            expected_type = "source_generation" if name == "source_generation_action_request.json" else "simulator_execution"
            if request.get("action_type") != expected_type:
                issues.append(f"request_type_drift:{action_id}")
            for field in ("final_evaluation_data_accessed", "physical_field_actuator", "starts_or_restarts_service"):
                if request.get(field) is not False:
                    issues.append(f"request_boundary_open:{action_id}:{field}")
    if request_count != 36 or len(action_ids) != 36:
        issues.append("total_request_count_drift")
    for binding in contract.get("source_bindings", {}).values():
        path = REPO_ROOT / str(binding.get("path", ""))
        if not path.is_file():
            issues.append(f"binding_missing:{binding.get('path')}")
        elif path.stat().st_size != binding.get("bytes") or _sha256(path) != binding.get("sha256"):
            issues.append(f"binding_drift:{binding.get('path')}")
    return issues


def _audit_runtime(execution: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if execution.get("status") != "complete" or execution.get("issues") != []:
        issues.append("runtime_not_complete")
    if execution.get("container_image_id") != IMAGE_ID or execution.get("network_mode") != "none":
        issues.append("runtime_image_or_network_drift")
    if execution.get("runs_completed") != 30 or len(execution.get("runs", [])) != 30:
        issues.append("runtime_run_count_drift")
    if execution.get("retry_count") != 0 or execution.get("teardown_verified") is not True:
        issues.append("runtime_retry_or_teardown_drift")
    for field in (
        "physical_field_connection", "final_evaluation_data_accessed",
        "model_or_embedding_inference_used", "model_or_embedding_service_started_or_restarted",
        "detector_or_defense_used", "real_network_used",
    ):
        if execution.get(field) is not False:
            issues.append(f"runtime_boundary_open:{field}")
    expected = [
        (_cell_id(seed, point), seed, point, treatment[0])
        for seed, point in NEW_CELLS for treatment in TREATMENTS
    ]
    observed = [
        (run.get("cell_id"), run.get("seed"), run.get("operating_point"), run.get("treatment"))
        for run in execution.get("runs", [])
    ]
    if observed != expected:
        issues.append("runtime_order_or_matrix_drift")
    for run in execution.get("runs", []):
        if run.get("container_exit_code") != 0 or run.get("teardown_verified") is not True or run.get("teardown_remaining_names") != [] or run.get("retry_count") != 0:
            issues.append(f"runtime_run_failed:{run.get('container_name')}")
    return issues


def _audit_cell(root: Path, seed: int, point: str, source: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    identifier = _cell_id(seed, point)
    if source.get("schema_version") != CELL_SCHEMA_VERSION or source.get("cell_id") != identifier:
        issues.append(f"cell_identity_drift:{identifier}")
    if source.get("seed") != seed or source.get("operating_point") != point or source.get("measurement_noise_seed") != seed + 90000:
        issues.append(f"cell_lineage_drift:{identifier}")
    if not _self_address(source, "cell_source_id", "m27cell_"):
        issues.append(f"cell_self_address_drift:{identifier}")
    runs = source.get("runs", [])
    expected_treatments = [item[0] for item in TREATMENTS]
    if [run.get("treatment") for run in runs] != expected_treatments:
        issues.append(f"cell_treatment_structure_drift:{identifier}")
        return issues
    benign = runs[0]
    for run, (treatment, target, command) in zip(runs, TREATMENTS):
        lineage = run.get("seed_lineage", {})
        if lineage != {
            "partition": "system_identification", "replicate_seed": seed,
            "attacker_policy_seed": seed, "measurement_noise_seed": seed + 90000,
            "gridlabd_random_seed": 10,
        }:
            issues.append(f"cell_run_lineage_drift:{identifier}:{treatment}")
        windows = run.get("windows", [])
        if len(windows) != 3 or [window.get("time_s") for window in windows] != [10, 20, 30]:
            issues.append(f"cell_window_drift:{identifier}:{treatment}")
            continue
        expected_command = {} if treatment == "benign" else {target: [command, 0.0]}
        for field in ("proposed_commands_kw_kvar", "accepted_commands_kw_kvar", "delivered_commands_kw_kvar"):
            if windows[0].get(field) != expected_command:
                issues.append(f"cell_command_drift:{identifier}:{treatment}:{field}")
        if any(window.get("accepted_commands_kw_kvar") or window.get("delivered_commands_kw_kvar") for window in windows[1:]):
            issues.append(f"cell_command_spillover:{identifier}:{treatment}")
        if treatment != "benign":
            for index in (0, 1):
                for field in ("true_voltage_pu", "measured_voltage_pu", "source_power_w_var"):
                    if windows[index].get(field) != benign["windows"][index].get(field):
                        issues.append(f"cell_pre_response_drift:{identifier}:{treatment}:{index}:{field}")
    rebuilt = _estimate_columns(runs)
    if source.get("estimator", {}).get("columns") != rebuilt:
        issues.append(f"cell_estimator_arithmetic_drift:{identifier}")
    rank = source.get("rank", {})
    if rank.get("true") != _rank(rebuilt, "max_abs_true_voltage_gain_pu_per_kw"):
        issues.append(f"cell_true_rank_drift:{identifier}")
    if rank.get("measured") != _rank(rebuilt, "max_abs_measured_voltage_gain_pu_per_kw"):
        issues.append(f"cell_measured_rank_drift:{identifier}")
    warning_count = sum(len(run.get("warning_lines", [])) for run in runs)
    if source.get("warning_line_count") != warning_count:
        issues.append(f"cell_warning_count_drift:{identifier}")
    issues.extend(f"{identifier}:{item}" for item in _audit_manifest(root / "cells" / identifier, source.get("raw_manifest", {})))
    if source.get("checks", {}).get("resource_admitted") is not False:
        issues.append(f"cell_resource_boundary_open:{identifier}")
    return issues


def _stats(values: list[float]) -> dict[str, Any]:
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    half = T95_DF2 * sd / math.sqrt(3)
    return {
        "n": 3, "values": values, "mean": mean, "sample_sd": sd,
        "min": min(values), "max": max(values), "range": max(values) - min(values),
        "coefficient_of_variation": sd / mean if mean != 0.0 else None,
        "t95_mean_interval_df2": [mean - half, mean + half],
        "interval_interpretation": "descriptive_small_n_not_population_certification",
    }


def _audit_aggregate(root: Path, evidence: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        issues.append("evidence_schema_drift")
    if not _self_address(evidence, "evidence_id", "m27evidence_"):
        issues.append("evidence_self_address_drift")
    if evidence.get("final_evaluation_seeds_accessed") != [] or evidence.get("evaluation_opened") is not False:
        issues.append("evidence_evaluation_boundary_open")
    if evidence.get("checks", {}).get("resource_admitted") is not False:
        issues.append("evidence_resource_boundary_open")
    cells = evidence.get("cells", [])
    expected_cells = [(6101, "responsive_night"), *NEW_CELLS]
    if [(cell.get("seed"), cell.get("operating_point")) for cell in cells] != expected_cells:
        issues.append("aggregate_cell_matrix_drift")
        return issues
    if _sha256(M23_SOURCE) != M23_SOURCE_SHA256 or _sha256(M23_AUDIT) != M23_AUDIT_SHA256:
        issues.append("anchor_hash_drift")
    else:
        anchor_source = _load(M23_SOURCE)
        anchor_audit = _load(M23_AUDIT)
        if anchor_audit.get("status") != "passed" or anchor_audit.get("issues") != []:
            issues.append("anchor_audit_not_passing")
        rebuilt_anchor = _estimate_columns(anchor_source["runs"])
        if cells[0].get("columns") != rebuilt_anchor:
            issues.append("anchor_aggregate_arithmetic_drift")
        if cells[0].get("rank", {}).get("true") != _rank(rebuilt_anchor, "max_abs_true_voltage_gain_pu_per_kw"):
            issues.append("anchor_true_rank_drift")
    for cell, (seed, point) in zip(cells[1:], NEW_CELLS):
        path = root / cell.get("provenance", {}).get("path", "")
        if not path.is_file() or _sha256(path) != cell.get("provenance", {}).get("sha256"):
            issues.append(f"aggregate_cell_provenance_drift:{_cell_id(seed, point)}")
        else:
            stored = _load(path)
            if cell.get("columns") != stored.get("estimator", {}).get("columns") or cell.get("rank") != stored.get("rank"):
                issues.append(f"aggregate_cell_summary_drift:{_cell_id(seed, point)}")
    for family, metric in (("true", "max_abs_true_voltage_gain_pu_per_kw"), ("measured", "max_abs_measured_voltage_gain_pu_per_kw")):
        analysis = evidence.get("analysis", {}).get(family, {})
        seed_axis = [cell for cell in cells if cell["operating_point"] == "responsive_night"]
        for target in TARGETS:
            values = [next(column[metric] for column in cell["columns"] if column["target_id"] == target) for cell in seed_axis]
            stored = analysis.get("per_target", {}).get(target, {}).get("fixed_night_seed_statistics")
            if stored != _stats(values):
                issues.append(f"aggregate_seed_statistics_drift:{family}:{target}")
        winners = [cell["rank"][family]["winner"] for cell in cells]
        stability = analysis.get("rank_stability", {})
        if stability.get("winners") != winners or stability.get("all_cells_same_winner") != (len(set(winners)) == 1):
            issues.append(f"aggregate_rank_stability_drift:{family}")
    if evidence.get("analysis", {}).get("seed_by_operating_point_interaction") != "not_estimable_in_crossed_anchor_design":
        issues.append("aggregate_interaction_boundary_drift")
    issues.extend(_audit_manifest(root, evidence.get("manifest", {})))
    return issues


def audit(root: Path) -> list[str]:
    """Return all independent M27 audit findings."""

    issues: list[str] = []
    try:
        contract = _load(root / "contract.json")
        execution = _load(root / "runtime_execution.json")
        evidence = _load(root / "m27_repeatability_coverage.json")
        issues.extend(_audit_contract(root, contract))
        issues.extend(_audit_runtime(execution))
        if evidence.get("contract_id") != contract.get("contract_id") or execution.get("contract_id") != contract.get("contract_id"):
            issues.append("contract_lineage_drift")
        for seed, point in NEW_CELLS:
            path = root / "cells" / _cell_id(seed, point) / "cell_source.json"
            issues.extend(_audit_cell(root, seed, point, _load(path)))
        issues.extend(_audit_aggregate(root, evidence))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        issues.append(f"audit_input_unreadable_or_invalid:{exc}")
    return sorted(set(issues))


def build_receipt(root: Path) -> dict[str, Any]:
    issues = audit(root)
    contract = _load(root / "contract.json")
    evidence = _load(root / "m27_repeatability_coverage.json")
    content = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M27",
        "classification": "PRELIMINARY_ONLY",
        "status": "passed" if not issues else "failed_closed",
        "issues": issues,
        "contract_id": contract.get("contract_id"),
        "contract_sha256": _sha256(root / "contract.json"),
        "evidence_id": evidence.get("evidence_id"),
        "evidence_sha256": _sha256(root / "m27_repeatability_coverage.json"),
        "auditor_sha256": _sha256(Path(__file__)),
        "checks": [
            "contract_self_address_and_final_code_bindings",
            "thirty_six_M18_requests_and_access_seals",
            "six_cell_thirty_run_create_once_matrix",
            "network_isolation_exit_codes_and_teardown",
            "five_run_symmetric_probe_structure_per_cell",
            "true_and_measured_estimator_arithmetic",
            "immutable_M23_anchor_binding",
            "seed_axis_uncertainty_arithmetic",
            "operating_point_axis_and_rank_stability",
            "all_raw_manifest_sizes_and_sha256",
            "small_n_and_unestimated_interaction_boundaries",
            "resource_admission_and_final_evaluation_seals",
        ],
        "claim_boundary": (
            "A passing audit validates the exact M27 preliminary crossed-anchor "
            "package. It does not estimate the missing interaction, admit a "
            "resource, or establish confirmatory evidence."
        ),
    }
    receipt = _copy(content)
    receipt["audit_id"] = "m27audit_" + _sha256_value(content)
    return receipt


def verify_receipt(root: Path, receipt: Mapping[str, Any]) -> list[str]:
    issues = audit(root)
    if not _self_address(receipt, "audit_id", "m27audit_"):
        issues.append("audit_receipt_self_address_drift")
    if receipt.get("auditor_sha256") != _sha256(Path(__file__)):
        issues.append("auditor_bytes_drift")
    if receipt.get("status") != "passed" or receipt.get("issues") != []:
        issues.append("stored_audit_not_passing")
    return sorted(set(issues))


def _create_once(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output.resolve()
    if args.verify:
        issues = verify_receipt(root, _load(output))
        print(json.dumps({"issues": issues}, indent=2))
        return int(bool(issues))
    receipt = build_receipt(root)
    _create_once(output, receipt)
    print(json.dumps({"status": receipt["status"], "audit_id": receipt["audit_id"], "issues": receipt["issues"]}, indent=2))
    return int(bool(receipt["issues"]))


if __name__ == "__main__":
    raise SystemExit(main())
