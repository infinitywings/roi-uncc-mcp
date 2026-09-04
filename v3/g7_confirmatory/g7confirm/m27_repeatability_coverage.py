"""Build and verify the M27 crossed-anchor sensitivity evidence package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping

from .m19_qualification import _load_json, _normalise_commands, _sha256
from .m27_profiles import (
    M27_CELLS,
    M27_RUNTIME_PROFILES,
    PROBE_MAGNITUDE_KW,
    TARGET_IDS,
    WINDOWS,
    WINDOW_SECONDS,
    cell_id,
    pair_id,
    treatment_definitions,
)
from .manifest import create_once_json
from .preliminary_only_gate import validate_preliminary_action_request
from .runtime import DEFAULT_CONFIG, M18_GATE_ARTIFACT


SCHEMA_VERSION = "grideval-g7-m27-repeatability-coverage/v1"
CELL_SCHEMA_VERSION = "grideval-g7-m27-system-identification-cell/v1"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m27-repeatability-coverage-contract/v1"
CLASSIFICATION = "PRELIMINARY_ONLY"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MZXYE3CTWNMRQ8YXA4H30F"
DECISION_ID = "dec_01M1MZWXXY65C3XXMERCAMT794"
IMAGE_TAG = "docker-cosim:latest"
IMAGE_ID = "sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7"
GRIDLABD_SEED = 10
MEASUREMENT_NOISE_OFFSET = 90000
PROBE_ENERGY_KVAH = PROBE_MAGNITUDE_KW * WINDOW_SECONDS / 3600.0
FINAL_EVALUATION_SEEDS = tuple(range(9101, 9113))
OPERATING_POINTS = (
    "responsive_morning",
    "responsive_midday",
    "responsive_evening",
    "responsive_night",
    "voltage_ceiling",
)
DEVICE_IDS = (
    "DER_EV1_BESS",
    "DER_EV3_PV",
    "DER_EV4_BESS",
    "DER_EV5_PV",
)
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_PATH = PACKAGE_ROOT / "g7confirm" / "runtime.py"
PROFILE_PATH = PACKAGE_ROOT / "g7confirm" / "m27_profiles.py"
WRAPPER_PATH = PACKAGE_ROOT / "g7confirm" / "m27_runtime.py"
EXECUTOR_PATH = PACKAGE_ROOT / "g7confirm" / "m27_execute.py"
AUDITOR_PATH = PACKAGE_ROOT / "g7confirm" / "m27_independent_audit.py"
M21_PATH = (
    PACKAGE_ROOT
    / "artifacts"
    / "m21_three_window_timing_seed5103_attempt1"
    / "m21_three_window_timing.json"
)
M23_ROOT = (
    PACKAGE_ROOT
    / "artifacts"
    / "m23_system_identification_seed6101_attempt1"
)
M23_SOURCE_PATH = M23_ROOT / "m23_system_identification.json"
M23_AUDIT_PATH = M23_ROOT / "independent_audit_receipt.json"
SPEC_PATH = PACKAGE_ROOT / "experiment_spec.yaml"
EXPECTED_M18_SHA256 = "e31a49d758700a3d30e4d7e3d5469b831b3f52370954fa92238eac6aa4dc3e9d"
EXPECTED_M21_SHA256 = "2aa7bbc10bcd20f964f9a7cbcad9a70b6058b8e652acbc68bdbea953bc7e022d"
EXPECTED_M23_SOURCE_SHA256 = "30d003e06d016b88d49e024857c9b74a9f9f34012a6f022b6f3a26511fc619c1"
EXPECTED_M23_AUDIT_SHA256 = "d0c3a539c20cc4dc3adb2910cd7bbba9c90a071a839ebc0fcde9d9e67f524030"
T95_DF2 = 4.302652729696142


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _finite(value: Any, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite M27 value: {label}")
    return number


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _binding(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _source_bindings() -> dict[str, dict[str, Any]]:
    fixed = {
        M18_GATE_ARTIFACT: EXPECTED_M18_SHA256,
        M21_PATH: EXPECTED_M21_SHA256,
        M23_SOURCE_PATH: EXPECTED_M23_SOURCE_SHA256,
        M23_AUDIT_PATH: EXPECTED_M23_AUDIT_SHA256,
    }
    for path, expected in fixed.items():
        if _sha256(path) != expected:
            raise ValueError(f"fixed M27 dependency drift: {_relative(path)}")
    return {
        "M18_gate": _binding(M18_GATE_ARTIFACT),
        "M21_timing": _binding(M21_PATH),
        "M23_anchor_source": _binding(M23_SOURCE_PATH),
        "M23_anchor_audit": _binding(M23_AUDIT_PATH),
        "runtime_core": _binding(RUNTIME_PATH),
        "M27_profiles": _binding(PROFILE_PATH),
        "M27_runtime_wrapper": _binding(WRAPPER_PATH),
        "M27_source_builder": _binding(Path(__file__)),
        "M27_executor": _binding(EXECUTOR_PATH),
        "M27_independent_auditor": _binding(AUDITOR_PATH),
        "DER_configuration": _binding(DEFAULT_CONFIG),
        "experiment_specification": _binding(SPEC_PATH),
    }


def _request_root(root: Path, seed: int, operating_point: str) -> Path:
    return root / "requests" / cell_id(seed, operating_point)


def build_action_requests() -> dict[str, dict[str, dict[str, Any]]]:
    """Build all 30 runtime and six source-generation M18 requests."""

    runtime_hash = _sha256(RUNTIME_PATH)
    builder_hash = _sha256(Path(__file__))
    config_hash = _sha256(DEFAULT_CONFIG)
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for cell in M27_CELLS:
        seed = int(cell["seed"])
        operating_point = str(cell["operating_point"])
        identifier = cell_id(seed, operating_point)
        profile = M27_RUNTIME_PROFILES[pair_id(seed, operating_point)]
        common = {
            "partition_role": "system_identification",
            "seed": seed,
            "output_classification": CLASSIFICATION,
            "create_once": True,
            "manifest_sha256": EXPECTED_M18_SHA256,
            "config_sha256": config_hash,
            "paired_benign_id": profile["benign_action_id"],
            "final_evaluation_data_accessed": False,
            "physical_field_actuator": False,
            "starts_or_restarts_service": False,
            "retain_failures": True,
            "local_service_identity": None,
        }
        requests: dict[str, dict[str, Any]] = {}
        for treatment in treatment_definitions(seed, operating_point):
            requests[treatment["action_request"]] = {
                "action_id": treatment["action_id"],
                "action_type": "simulator_execution",
                "code_sha256": runtime_hash,
                "budget_id": profile["budget_id"],
                **common,
            }
        requests["source_generation_action_request.json"] = {
            "action_id": f"m27_empirical_source_{identifier}",
            "action_type": "source_generation",
            "code_sha256": builder_hash,
            "budget_id": f"m27_{identifier}_one_source_from_five_runs",
            **{**common, "paired_benign_id": None},
        }
        for name, request in requests.items():
            issues = validate_preliminary_action_request(request)
            if issues:
                raise ValueError(f"M27 action request rejected ({identifier}/{name}): {issues}")
        result[identifier] = requests
    return _canonical_copy(result)


def _load_action_requests(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    expected = build_action_requests()
    actual: dict[str, dict[str, dict[str, Any]]] = {}
    for identifier, requests in expected.items():
        actual[identifier] = {}
        for name in requests:
            path = root / "requests" / identifier / name
            if not path.is_file():
                raise ValueError(f"missing M27 action request: {identifier}/{name}")
            actual[identifier][name] = _load_json(path)
    if _canonical_copy(actual) != expected:
        raise ValueError("stored M27 action requests drift from executable bytes")
    return actual


def build_contract(root: Path) -> dict[str, Any]:
    """Build the final-code contract before any M27 simulator run."""

    requests = _load_action_requests(root)
    matrix = []
    for cell in M27_CELLS:
        seed = int(cell["seed"])
        operating_point = str(cell["operating_point"])
        identifier = cell_id(seed, operating_point)
        matrix.append({
            "cell_id": identifier,
            "seed": seed,
            "measurement_noise_seed": seed + MEASUREMENT_NOISE_OFFSET,
            "gridlabd_seed": GRIDLABD_SEED,
            "operating_point": operating_point,
            "pair_id": pair_id(seed, operating_point),
            "treatments": list(treatment_definitions(seed, operating_point)),
            "action_requests": requests[identifier],
        })
    content = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M27",
        "classification": CLASSIFICATION,
        "status": "REGISTERED_NO_SIMULATOR_RUN",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "source_bindings": _source_bindings(),
        "design": {
            "geometry": "seven_cell_crossed_anchor",
            "immutable_anchor": {
                "seed": 6101,
                "operating_point": "responsive_night",
                "source_sha256": EXPECTED_M23_SOURCE_SHA256,
                "audit_sha256": EXPECTED_M23_AUDIT_SHA256,
                "runtime_rerun": False,
            },
            "new_cells": matrix,
            "new_cell_count": 6,
            "new_runtime_run_cap": 30,
            "retry_cap": 0,
            "fixed_night_seed_axis": [6101, 6102, 6103],
            "fixed_seed_operating_point_axis": {
                "seed": 6102,
                "operating_points": list(OPERATING_POINTS),
            },
            "seed_by_operating_point_interaction_estimable": False,
        },
        "probe_design": {
            "authority": "one_BESS_active_power_setpoint_per_treatment",
            "targets": list(TARGET_IDS),
            "signed_commands_kw": [-PROBE_MAGNITUDE_KW, PROBE_MAGNITUDE_KW],
            "windows": WINDOWS,
            "window_seconds": WINDOW_SECONDS,
            "post_actuation_time_s": 30,
            "perturbed_window_cap": 1,
            "apparent_energy_cap_kvah": 2.0,
            "expected_energy_per_probe_kvah": PROBE_ENERGY_KVAH,
        },
        "analysis": {
            "true_and_measured_voltage_columns": True,
            "primary_scalar": "max_abs_true_voltage_gain_pu_per_kw",
            "seed_axis_statistics": ["n", "mean", "sample_sd", "min", "max", "t95_mean_interval_df2"],
            "operating_point_axis_statistics": "descriptive_only",
            "rank_outputs": ["winner", "absolute_margin", "ratio_margin", "agreement"],
            "scientific_threshold_selected": False,
            "small_n_warning_required": True,
            "unestimated_interaction_warning_required": True,
        },
        "runtime": {
            "image_tag": IMAGE_TAG,
            "image_id": IMAGE_ID,
            "network_mode": "none",
            "containers_ephemeral": True,
        },
        "access_boundary": {
            "simulator": True,
            "simulated_probe": True,
            "real_network": False,
            "LLM": False,
            "embedding": False,
            "detector": False,
            "defense": False,
            "physical_field_actuator": False,
            "final_evaluation": False,
            "resource_admission": False,
        },
        "claim_boundary": (
            "M27 is a descriptive preliminary repeatability and coverage gate. "
            "It cannot estimate the seed-by-operating-point interaction, admit a "
            "resource without Brain Gate 2, or support confirmatory claims."
        ),
    }
    contract = _canonical_copy(content)
    contract["contract_id"] = "m27contract_" + _sha256_value(content)
    return contract


def _manifest(root: Path, files: Iterable[Path]) -> dict[str, Any]:
    entries = []
    for path in sorted(set(files)):
        if path.is_symlink() or not path.is_file():
            continue
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return {
        "algorithm": "sha256",
        "file_count": len(entries),
        "total_bytes": sum(item["bytes"] for item in entries),
        "files": entries,
    }


def _verify_manifest(root: Path, manifest: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    entries = manifest.get("files", [])
    if manifest.get("algorithm") != "sha256" or not isinstance(entries, list):
        return ["manifest_shape_invalid"]
    seen: set[str] = set()
    total = 0
    for entry in entries:
        relative = str(entry.get("path", ""))
        if relative in seen or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
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
    return sorted(set(issues))


def _load_recorders(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    recorders: dict[str, list[dict[str, Any]]] = {}
    paths = sorted((run_dir / "output").glob("multi_der_*_coupling.csv"))
    if len(paths) != len(DEVICE_IDS):
        raise ValueError(f"expected four coupling recorders, found {len(paths)}")
    for path in paths:
        lines = [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("#") or line.startswith("# timestamp")
        ]
        rows = list(csv.DictReader(lines))
        if len(rows) != WINDOWS:
            raise ValueError(f"coupling recorder length drift: {path}")
        power_key = next((key for key in rows[0] if key.startswith("constant_power_")), None)
        if power_key is None:
            raise ValueError(f"coupling recorder missing power column: {path}")
        recorders[path.stem] = [{
            "timestamp": row["# timestamp"],
            "received_power_va": [
                _finite(complex(row[power_key]).real, f"{path}.P"),
                _finite(complex(row[power_key]).imag, f"{path}.Q"),
            ],
        } for row in rows]
    return recorders


def _warning_lines(run_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    paths = sorted(
        path for path in run_dir.rglob("*")
        if path.is_file() and not path.is_symlink()
        and (path.suffix == ".log" or path.name.startswith("console."))
    )
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            lowered = line.lower()
            if any(token in lowered for token in ("warning", "deprecated", "unknown route", "no broker")):
                results.append({
                    "path": path.relative_to(run_dir).as_posix(),
                    "line": number,
                    "text": line,
                })
    return results


def _validate_run(
    *, root: Path, identifier: str, seed: int, operating_point: str,
    treatment: Mapping[str, Any], action_request: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = root / "cells" / identifier / str(treatment["id"])
    required = {
        "integration": run_dir / "runtime_integration.json",
        "summary": run_dir / "g7_summary.json",
        "attack": run_dir / "attack_trace.json",
        "budget": run_dir / "dual_budget_trace.json",
        "devices": run_dir / "multi_der_traces.json",
        "source": run_dir / "multi_der_source.json",
        "gridlabd_log": run_dir / "gridlabd.log",
        "stdout": run_dir / "console.stdout.txt",
        "stderr": run_dir / "console.stderr.txt",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise ValueError(f"{identifier}/{treatment['id']} missing artifacts: {missing}")
    integration = _load_json(required["integration"])
    summary = _load_json(required["summary"])
    attack_trace = _load_json(required["attack"])
    budget = _load_json(required["budget"])
    device_traces = _load_json(required["devices"])
    source_trace = _load_json(required["source"])
    recorders = _load_recorders(run_dir)
    expected_lineage = {
        "partition": "system_identification",
        "replicate_seed": seed,
        "attacker_policy_seed": seed,
        "measurement_noise_seed": seed + MEASUREMENT_NOISE_OFFSET,
        "gridlabd_random_seed": GRIDLABD_SEED,
    }
    expected_pairing = {
        "pair_id": pair_id(seed, operating_point),
        "treatment": treatment["id"],
        "matched_seed": seed,
    }
    if integration.get("classification") != CLASSIFICATION or integration.get("status") != "passed":
        raise ValueError(f"{identifier}/{treatment['id']} runtime status drift")
    if integration.get("campaign_authorized") is not False or integration.get("evaluation_opened") is not False:
        raise ValueError(f"{identifier}/{treatment['id']} authority boundary opened")
    if integration.get("runtime_window_limit") != WINDOWS:
        raise ValueError(f"{identifier}/{treatment['id']} window cap drift")
    if integration.get("seed_lineage") != expected_lineage:
        raise ValueError(f"{identifier}/{treatment['id']} seed lineage drift")
    if integration.get("pairing") != expected_pairing:
        raise ValueError(f"{identifier}/{treatment['id']} pairing drift")
    if integration.get("M18_action_request") != action_request:
        raise ValueError(f"{identifier}/{treatment['id']} action request drift")
    op = integration.get("operating_point", {})
    if op.get("id") != operating_point or op.get("duration_s") != WINDOWS * WINDOW_SECONDS:
        raise ValueError(f"{identifier}/{treatment['id']} operating point drift")
    expected_arm = "benign" if treatment["id"] == "benign" else "probe"
    if summary.get("arm") != expected_arm or summary.get("windows") != WINDOWS:
        raise ValueError(f"{identifier}/{treatment['id']} runner profile drift")
    if summary.get("attacker_seed") != seed or summary.get("noise_seed") != seed + MEASUREMENT_NOISE_OFFSET:
        raise ValueError(f"{identifier}/{treatment['id']} summary seed drift")
    if int(summary.get("gridlabd_returncode", -1)) != 0:
        raise ValueError(f"{identifier}/{treatment['id']} GridLAB-D failed")
    if len(attack_trace) != WINDOWS or len(source_trace) != WINDOWS:
        raise ValueError(f"{identifier}/{treatment['id']} trace length drift")
    if set(device_traces) != set(DEVICE_IDS) or any(len(rows) != WINDOWS for rows in device_traces.values()):
        raise ValueError(f"{identifier}/{treatment['id']} device trace drift")
    records = budget.get("records", [])
    if len(records) != WINDOWS or any(record.get("runner_noted") is not True for record in records):
        raise ValueError(f"{identifier}/{treatment['id']} budget trace incomplete")
    if budget.get("delivery_reconciled") is not True:
        raise ValueError(f"{identifier}/{treatment['id']} delivery not reconciled")
    windows = []
    for index in range(WINDOWS):
        windows.append({
            "window": index,
            "time_s": int(attack_trace[index]["t"]),
            "true_voltage_pu": {
                key: _finite(value, f"{identifier}.{treatment['id']}.{key}.v{index}")
                for key, value in sorted(attack_trace[index]["telemetry"].items())
            },
            "measured_voltage_pu": {
                key: _finite(value, f"{identifier}.{treatment['id']}.{key}.vm{index}")
                for key, value in sorted(attack_trace[index]["telemetry_meas"].items())
            },
            "source_power_w_var": {
                "source_p_w": _finite(source_trace[index]["source_p_w"], "source_p"),
                "source_q_var": _finite(source_trace[index]["source_q_var"], "source_q"),
            },
            "proposed_commands_kw_kvar": _normalise_commands(records[index].get("proposed", {})),
            "accepted_commands_kw_kvar": _normalise_commands(records[index].get("admitted", {})),
            "delivered_commands_kw_kvar": _normalise_commands(records[index].get("delivered", {})),
        })
    if treatment["id"] == "benign":
        if any(window["proposed_commands_kw_kvar"] or window["accepted_commands_kw_kvar"] or window["delivered_commands_kw_kvar"] for window in windows):
            raise ValueError(f"{identifier} benign run contains a command")
        if budget.get("windows_spent") != 0 or float(budget.get("delivered_command_energy_kvah", -1)) != 0.0:
            raise ValueError(f"{identifier} benign run spent budget")
    else:
        expected_command = {str(treatment["target_id"]): [float(treatment["command_kw"]), 0.0]}
        if any(windows[0][field] != expected_command for field in (
            "proposed_commands_kw_kvar", "accepted_commands_kw_kvar", "delivered_commands_kw_kvar"
        )):
            raise ValueError(f"{identifier}/{treatment['id']} command drift")
        if any(window["accepted_commands_kw_kvar"] or window["delivered_commands_kw_kvar"] for window in windows[1:]):
            raise ValueError(f"{identifier}/{treatment['id']} exceeded one intervention")
        if budget.get("windows_spent") != 1 or not math.isclose(
            float(budget.get("delivered_command_energy_kvah", -1)),
            PROBE_ENERGY_KVAH,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"{identifier}/{treatment['id']} budget drift")
    return {
        "treatment": treatment["id"],
        "target_id": treatment["target_id"],
        "command_kw": treatment["command_kw"],
        "run_dir": run_dir.relative_to(root).as_posix(),
        "seed_lineage": integration["seed_lineage"],
        "operating_point": op,
        "dependency_hashes": integration["dependency_hashes"],
        "detector_defense_state": integration["detector_defense_state"],
        "budget": {key: budget[key] for key in (
            "window_cap", "apparent_energy_cap_kvah", "windows_spent",
            "admitted_energy_kvah", "delivered_command_energy_kvah", "delivery_reconciled",
        )},
        "windows": windows,
        "gridlabd_received_DER_power": recorders,
        "warning_lines": _warning_lines(run_dir),
        "artifact_sha256": {name: _sha256(path) for name, path in sorted(required.items())},
    }


def _recorder_deltas(benign: Mapping[str, Any], probe: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index in range(WINDOWS):
        values = {}
        timestamp = None
        for recorder_id in sorted(benign["gridlabd_received_DER_power"]):
            left = benign["gridlabd_received_DER_power"][recorder_id][index]
            right = probe["gridlabd_received_DER_power"][recorder_id][index]
            if left["timestamp"] != right["timestamp"]:
                raise ValueError("M27 recorder timestamp drift")
            timestamp = timestamp or left["timestamp"]
            values[recorder_id] = [
                _finite(right["received_power_va"][component], "probe recorder")
                - _finite(left["received_power_va"][component], "benign recorder")
                for component in range(2)
            ]
        rows.append({
            "recorder_row": index,
            "timestamp": timestamp,
            "received_power_delta_probe_minus_benign_va": values,
        })
    target_recorder = f"multi_der_{probe['target_id']}_coupling"
    expected_p = -1000.0 * float(probe["command_kw"])
    for index, row in enumerate(rows):
        for recorder_id, (p_w, q_var) in row["received_power_delta_probe_minus_benign_va"].items():
            expected = expected_p if index == 2 and recorder_id == target_recorder else 0.0
            if not math.isclose(p_w, expected, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"{probe['treatment']} recorder sign or target drift")
            if not math.isclose(q_var, 0.0, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"{probe['treatment']} unexpected reactive probe")
    return rows


def _response_delta(benign: Mapping[str, Any], probe: Mapping[str, Any], index: int) -> dict[str, Any]:
    left = benign["windows"][index]
    right = probe["windows"][index]
    return {
        "window": index,
        "time_s": right["time_s"],
        "true_voltage_delta_probe_minus_benign_pu": {
            key: _finite(right["true_voltage_pu"][key] - left["true_voltage_pu"][key], f"{key}.delta")
            for key in DEVICE_IDS
        },
        "measured_voltage_delta_probe_minus_benign_pu": {
            key: _finite(right["measured_voltage_pu"][key] - left["measured_voltage_pu"][key], f"{key}.measured_delta")
            for key in DEVICE_IDS
        },
        "source_power_delta_probe_minus_benign_w_var": {
            field: _finite(right["source_power_w_var"][field] - left["source_power_w_var"][field], f"{field}.delta")
            for field in ("source_p_w", "source_q_var")
        },
    }


def _estimate_column(
    *, target_id: str, benign: Mapping[str, Any], plus: Mapping[str, Any], minus: Mapping[str, Any],
) -> dict[str, Any]:
    index = 2
    b = benign["windows"][index]
    p = plus["windows"][index]
    m = minus["windows"][index]
    span = 2.0 * PROBE_MAGNITUDE_KW
    result: dict[str, Any] = {"target_id": target_id, "post_actuation_time_s": 30}
    for prefix, field in (("true", "true_voltage_pu"), ("measured", "measured_voltage_pu")):
        central = {key: _finite((p[field][key] - m[field][key]) / span, f"{target_id}.{key}.{prefix}.central") for key in DEVICE_IDS}
        plus_side = {key: _finite((p[field][key] - b[field][key]) / PROBE_MAGNITUDE_KW, f"{target_id}.{key}.{prefix}.plus") for key in DEVICE_IDS}
        minus_side = {key: _finite((b[field][key] - m[field][key]) / PROBE_MAGNITUDE_KW, f"{target_id}.{key}.{prefix}.minus") for key in DEVICE_IDS}
        residual = {key: _finite((p[field][key] + m[field][key]) / 2.0 - b[field][key], f"{target_id}.{key}.{prefix}.residual") for key in DEVICE_IDS}
        result[f"central_{prefix}_voltage_gain_pu_per_kw"] = central
        result[f"plus_one_sided_{prefix}_voltage_gain_pu_per_kw"] = plus_side
        result[f"minus_one_sided_{prefix}_voltage_gain_pu_per_kw"] = minus_side
        result[f"centered_{prefix}_voltage_residual_pu"] = residual
        result[f"max_abs_{prefix}_voltage_gain_pu_per_kw"] = max(abs(value) for value in central.values())
        result[f"max_abs_centered_{prefix}_voltage_residual_pu"] = max(abs(value) for value in residual.values())
    result["central_source_power_gain_w_var_per_kw"] = {
        field: _finite((p["source_power_w_var"][field] - m["source_power_w_var"][field]) / span, f"{target_id}.{field}.central")
        for field in ("source_p_w", "source_q_var")
    }
    result["centered_source_power_residual_w_var"] = {
        field: _finite((p["source_power_w_var"][field] + m["source_power_w_var"][field]) / 2.0 - b["source_power_w_var"][field], f"{target_id}.{field}.residual")
        for field in ("source_p_w", "source_q_var")
    }
    return result


def _rank(columns: Iterable[Mapping[str, Any]], metric: str) -> dict[str, Any]:
    values = {str(column["target_id"]): _finite(column[metric], metric) for column in columns}
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


def build_cell_source(root: Path, seed: int, operating_point: str) -> dict[str, Any]:
    identifier = cell_id(seed, operating_point)
    requests = _load_action_requests(root)[identifier]
    contract = _load_json(root / "contract.json")
    if contract != build_contract(root):
        raise ValueError("stored M27 contract drifts from final executable bytes")
    runs = [
        _validate_run(
            root=root,
            identifier=identifier,
            seed=seed,
            operating_point=operating_point,
            treatment=treatment,
            action_request=requests[treatment["action_request"]],
        )
        for treatment in treatment_definitions(seed, operating_point)
    ]
    by_id = {run["treatment"]: run for run in runs}
    benign = by_id["benign"]
    pair_evidence = []
    for probe in runs[1:]:
        for field in ("seed_lineage", "operating_point", "dependency_hashes"):
            if probe[field] != benign[field]:
                raise ValueError(f"{identifier}/{probe['treatment']} controlled-lineage drift")
        for index in (0, 1):
            for field in ("true_voltage_pu", "measured_voltage_pu", "source_power_w_var"):
                if probe["windows"][index][field] != benign["windows"][index][field]:
                    raise ValueError(f"{identifier}/{probe['treatment']} pre-response drift at window {index}")
        recorder = _recorder_deltas(benign, probe)
        response = [_response_delta(benign, probe, index) for index in (1, 2)]
        for family in ("true_voltage_delta_probe_minus_benign_pu", "measured_voltage_delta_probe_minus_benign_pu", "source_power_delta_probe_minus_benign_w_var"):
            if any(abs(value) > 1e-12 for value in response[0][family].values()):
                raise ValueError(f"{identifier}/{probe['treatment']} response appeared before t=30")
        if not any(abs(value) > 1e-12 for value in response[1]["true_voltage_delta_probe_minus_benign_pu"].values()):
            raise ValueError(f"{identifier}/{probe['treatment']} has no t=30 response")
        pair_evidence.append({
            "treatment": probe["treatment"],
            "target_id": probe["target_id"],
            "command_kw": probe["command_kw"],
            "recorder_deltas": recorder,
            "runner_observation_deltas": response,
        })
    columns = [
        _estimate_column(target_id="DER_EV1_BESS", benign=benign, plus=by_id["probe_ev1_plus30"], minus=by_id["probe_ev1_minus30"]),
        _estimate_column(target_id="DER_EV4_BESS", benign=benign, plus=by_id["probe_ev4_plus30"], minus=by_id["probe_ev4_minus30"]),
    ]
    cell_root = root / "cells" / identifier
    raw_files = [path for path in cell_root.rglob("*") if path.is_file() and path.name != "cell_source.json"]
    content = {
        "schema_version": CELL_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M27",
        "classification": CLASSIFICATION,
        "status": "EMPIRICAL_SYSTEM_IDENTIFICATION_CELL_COMPLETE",
        "cell_id": identifier,
        "seed": seed,
        "measurement_noise_seed": seed + MEASUREMENT_NOISE_OFFSET,
        "gridlabd_seed": GRIDLABD_SEED,
        "operating_point": operating_point,
        "contract_id": contract["contract_id"],
        "source_generation_action_request": requests["source_generation_action_request.json"],
        "runs": runs,
        "pair_evidence": pair_evidence,
        "estimator": {"columns": columns},
        "rank": {
            "true": _rank(columns, "max_abs_true_voltage_gain_pu_per_kw"),
            "measured": _rank(columns, "max_abs_measured_voltage_gain_pu_per_kw"),
        },
        "warning_line_count": sum(len(run["warning_lines"]) for run in runs),
        "raw_manifest": _manifest(cell_root, raw_files),
        "checks": {
            "five_run_cap_respected": True,
            "controlled_lineage_equal": True,
            "shared_benign_control": True,
            "single_target_per_probe": True,
            "symmetric_signed_probe_pair_per_target": True,
            "accepted_equals_delivered": True,
            "one_perturbed_window_per_probe": True,
            "first_recorder_visible_row": 2,
            "first_runner_response_time_s": 30,
            "true_and_measured_vectors_retained": True,
            "scientific_threshold_selected": False,
            "resource_admitted": False,
        },
    }
    source = _canonical_copy(content)
    source["cell_source_id"] = "m27cell_" + _sha256_value(content)
    return source


def _anchor_cell() -> dict[str, Any]:
    if _sha256(M23_SOURCE_PATH) != EXPECTED_M23_SOURCE_SHA256 or _sha256(M23_AUDIT_PATH) != EXPECTED_M23_AUDIT_SHA256:
        raise ValueError("M23 anchor bytes drift")
    source = _load_json(M23_SOURCE_PATH)
    audit = _load_json(M23_AUDIT_PATH)
    if audit.get("status") != "passed" or audit.get("issues") != []:
        raise ValueError("M23 anchor audit is not passing")
    runs = source.get("runs", [])
    by_id = {run["treatment"]: run for run in runs}
    columns = [
        _estimate_column(target_id="DER_EV1_BESS", benign=by_id["benign"], plus=by_id["probe_ev1_plus30"], minus=by_id["probe_ev1_minus30"]),
        _estimate_column(target_id="DER_EV4_BESS", benign=by_id["benign"], plus=by_id["probe_ev4_plus30"], minus=by_id["probe_ev4_minus30"]),
    ]
    stored = {column["target_id"]: column["max_abs_true_voltage_gain_pu_per_kw"] for column in source["estimator"]["columns"]}
    rebuilt = {column["target_id"]: column["max_abs_true_voltage_gain_pu_per_kw"] for column in columns}
    if stored != rebuilt:
        raise ValueError("M23 anchor estimator arithmetic drift")
    return {
        "cell_id": "seed6101_responsive_night",
        "seed": 6101,
        "measurement_noise_seed": 96101,
        "gridlabd_seed": GRIDLABD_SEED,
        "operating_point": "responsive_night",
        "provenance": {
            "source_path": _relative(M23_SOURCE_PATH),
            "source_sha256": EXPECTED_M23_SOURCE_SHA256,
            "source_id": source["source_id"],
            "audit_path": _relative(M23_AUDIT_PATH),
            "audit_sha256": EXPECTED_M23_AUDIT_SHA256,
            "audit_id": audit["audit_id"],
            "runtime_rerun": False,
        },
        "columns": columns,
        "rank": {
            "true": _rank(columns, "max_abs_true_voltage_gain_pu_per_kw"),
            "measured": _rank(columns, "max_abs_measured_voltage_gain_pu_per_kw"),
        },
        "warning_lines": [
            {"run": run["treatment"], **item}
            for run in runs
            for item in _warning_lines(M23_ROOT / run["run_dir"])
        ],
    }


def _cell_summary(source: Mapping[str, Any], source_sha256: str) -> dict[str, Any]:
    return {
        "cell_id": source["cell_id"],
        "seed": source["seed"],
        "measurement_noise_seed": source["measurement_noise_seed"],
        "gridlabd_seed": source["gridlabd_seed"],
        "operating_point": source["operating_point"],
        "columns": source["estimator"]["columns"],
        "rank": source["rank"],
        "warning_line_count": source["warning_line_count"],
        "provenance": {
            "path": f"cells/{source['cell_id']}/cell_source.json",
            "sha256": source_sha256,
            "cell_source_id": source["cell_source_id"],
        },
    }


def _stats(values: list[float]) -> dict[str, Any]:
    if len(values) != 3:
        raise ValueError("M27 seed-axis statistics require exactly three values")
    mean = statistics.fmean(values)
    sample_sd = statistics.stdev(values)
    half_width = T95_DF2 * sample_sd / math.sqrt(len(values))
    return {
        "n": len(values),
        "values": values,
        "mean": mean,
        "sample_sd": sample_sd,
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
        "coefficient_of_variation": sample_sd / mean if mean != 0.0 else None,
        "t95_mean_interval_df2": [mean - half_width, mean + half_width],
        "interval_interpretation": "descriptive_small_n_not_population_certification",
    }


def _axis_analysis(cells: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    seed_axis = sorted(
        (cell for cell in cells if cell["operating_point"] == "responsive_night"),
        key=lambda item: item["seed"],
    )
    op_axis = [
        next(cell for cell in cells if cell["seed"] == 6102 and cell["operating_point"] == point)
        for point in OPERATING_POINTS
    ]
    per_target = {}
    for target in TARGET_IDS:
        seed_values = [
            next(column[metric] for column in cell["columns"] if column["target_id"] == target)
            for cell in seed_axis
        ]
        op_values = {
            cell["operating_point"]: next(column[metric] for column in cell["columns"] if column["target_id"] == target)
            for cell in op_axis
        }
        per_target[target] = {
            "fixed_night_seed_statistics": _stats(seed_values),
            "fixed_seed_6102_operating_point_values": op_values,
            "operating_point_min": min(op_values.values()),
            "operating_point_max": max(op_values.values()),
            "operating_point_range": max(op_values.values()) - min(op_values.values()),
            "operating_point_max_to_min_ratio": max(op_values.values()) / min(op_values.values()) if min(op_values.values()) > 0.0 else None,
        }
    winners = [cell["rank"]["true" if "true" in metric else "measured"]["winner"] for cell in cells]
    return {
        "metric": metric,
        "fixed_night_seed_axis": [cell["cell_id"] for cell in seed_axis],
        "fixed_seed_6102_operating_point_axis": [cell["cell_id"] for cell in op_axis],
        "per_target": per_target,
        "rank_stability": {
            "cells": len(cells),
            "winners": winners,
            "winner_counts": {target: winners.count(target) for target in TARGET_IDS},
            "all_cells_same_winner": len(set(winners)) == 1,
            "unanimous_winner": winners[0] if len(set(winners)) == 1 else None,
            "cell_margins": {
                cell["cell_id"]: cell["rank"]["true" if "true" in metric else "measured"]
                for cell in cells
            },
        },
    }


def build_evidence(root: Path) -> dict[str, Any]:
    """Build six cell sources and the seven-cell crossed-anchor aggregate."""

    contract = _load_json(root / "contract.json")
    if contract != build_contract(root):
        raise ValueError("stored M27 contract drifts from final executable bytes")
    runtime_execution = _load_json(root / "runtime_execution.json")
    if runtime_execution.get("status") != "complete" or runtime_execution.get("issues") != []:
        raise ValueError("M27 runtime execution is not complete")
    new_cells = []
    for cell in M27_CELLS:
        seed = int(cell["seed"])
        operating_point = str(cell["operating_point"])
        cell_root = root / "cells" / cell_id(seed, operating_point)
        source_path = cell_root / "cell_source.json"
        source = build_cell_source(root, seed, operating_point)
        create_once_json(source_path, source)
        summary = _cell_summary(source, _sha256(source_path))
        new_cells.append(summary)
    anchor = _anchor_cell()
    anchor_summary = {
        "cell_id": anchor["cell_id"],
        "seed": anchor["seed"],
        "measurement_noise_seed": anchor["measurement_noise_seed"],
        "gridlabd_seed": anchor["gridlabd_seed"],
        "operating_point": anchor["operating_point"],
        "columns": anchor["columns"],
        "rank": anchor["rank"],
        "warning_line_count": len(anchor["warning_lines"]),
        "provenance": anchor["provenance"],
    }
    cells = [anchor_summary, *new_cells]
    manifest_files = [
        path for path in root.rglob("*")
        if path.is_file() and path.name not in {
            "m27_repeatability_coverage.json", "independent_audit_receipt.json"
        }
    ]
    content = {
        "schema_version": SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M27",
        "classification": CLASSIFICATION,
        "status": "EMPIRICAL_REPEATABILITY_COVERAGE_CANDIDATE",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "final_evaluation_seeds_accessed": [],
        "final_evaluation_seeds_remain_sealed": list(FINAL_EVALUATION_SEEDS),
        "contract_id": contract["contract_id"],
        "runtime_execution": runtime_execution,
        "cells": cells,
        "analysis": {
            "true": _axis_analysis(cells, "max_abs_true_voltage_gain_pu_per_kw"),
            "measured": _axis_analysis(cells, "max_abs_measured_voltage_gain_pu_per_kw"),
            "seed_by_operating_point_interaction": "not_estimable_in_crossed_anchor_design",
            "scientific_threshold_selected": False,
        },
        "warning_summary": {
            "anchor_warning_line_count": len(anchor["warning_lines"]),
            "new_warning_line_count": sum(cell["warning_line_count"] for cell in new_cells),
            "warning_lines_retained_in_cell_sources": True,
            "raw_logs_retained": True,
        },
        "checks": {
            "seven_cells_present": len(cells) == 7,
            "six_new_cells_present": len(new_cells) == 6,
            "thirty_new_runs_completed": len(runtime_execution["runs"]) == 30,
            "immutable_M23_anchor_not_rerun": anchor["provenance"]["runtime_rerun"] is False,
            "fixed_night_three_seed_axis_complete": True,
            "fixed_seed_five_operating_point_axis_complete": True,
            "true_and_measured_vectors_retained": True,
            "small_n_warning_retained": True,
            "unestimated_interaction_warning_retained": True,
            "scientific_threshold_selected": False,
            "resource_admitted": False,
            "final_evaluation_accessed": False,
        },
        "manifest": _manifest(root, manifest_files),
        "scientific_scope": {
            "establishes_if_audit_passes": [
                "bounded_three_seed_fixed_night_repeatability_description",
                "bounded_five_operating_point_fixed_seed_coverage_description",
                "seven_cell_target_rank_stability_description",
                "crossed_anchor_source_generation_mechanics",
            ],
            "does_not_establish": [
                "seed_by_operating_point_interaction",
                "population_level_uncertainty",
                "full_factorial_generalization",
                "scientific_linearity_threshold",
                "automatic_resource_admission",
                "attacker_or_LLM_advantage",
                "detector_or_defense_effectiveness",
                "confirmatory_or_publication_grade_evidence",
            ],
            "next_gate": "separate_Brain_resource_admission_decision",
        },
    }
    evidence = _canonical_copy(content)
    evidence["evidence_id"] = "m27evidence_" + _sha256_value(content)
    return evidence


def verify_evidence(root: Path) -> list[str]:
    """Rebuild and verify all M27 sources from retained exact bytes."""

    issues: list[str] = []
    try:
        actual = _load_json(root / "m27_repeatability_coverage.json")
        for cell in M27_CELLS:
            seed = int(cell["seed"])
            operating_point = str(cell["operating_point"])
            path = root / "cells" / cell_id(seed, operating_point) / "cell_source.json"
            stored = _load_json(path)
            rebuilt = build_cell_source(root, seed, operating_point)
            if stored != rebuilt:
                issues.append(f"cell_source_content_drift:{cell_id(seed, operating_point)}")
            content = _canonical_copy(stored)
            source_id = content.pop("cell_source_id", None)
            if source_id != "m27cell_" + _sha256_value(content):
                issues.append(f"cell_source_id_drift:{cell_id(seed, operating_point)}")
            issues.extend(
                f"{cell_id(seed, operating_point)}:{item}"
                for item in _verify_manifest(path.parent, stored.get("raw_manifest", {}))
            )
        expected = build_evidence_without_writes(root)
        if actual != expected:
            issues.append("M27_evidence_content_drift")
        content = _canonical_copy(actual)
        evidence_id = content.pop("evidence_id", None)
        if evidence_id != "m27evidence_" + _sha256_value(content):
            issues.append("M27_evidence_id_drift")
        issues.extend(_verify_manifest(root, actual.get("manifest", {})))
        if actual.get("final_evaluation_seeds_accessed") != []:
            issues.append("final_evaluation_accessed")
        if actual.get("checks", {}).get("resource_admitted") is not False:
            issues.append("resource_admission_boundary_opened")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        issues.append(f"M27_evidence_unreadable_or_invalid:{exc}")
    return sorted(set(issues))


def build_evidence_without_writes(root: Path) -> dict[str, Any]:
    """Rebuild the aggregate while requiring existing cell sources."""

    contract = _load_json(root / "contract.json")
    if contract != build_contract(root):
        raise ValueError("stored M27 contract drifts from final executable bytes")
    runtime_execution = _load_json(root / "runtime_execution.json")
    new_cells = []
    for cell in M27_CELLS:
        identifier = cell_id(int(cell["seed"]), str(cell["operating_point"]))
        path = root / "cells" / identifier / "cell_source.json"
        source = _load_json(path)
        summary = _cell_summary(source, _sha256(path))
        new_cells.append(summary)
    anchor = _anchor_cell()
    anchor_summary = {
        "cell_id": anchor["cell_id"], "seed": anchor["seed"],
        "measurement_noise_seed": anchor["measurement_noise_seed"],
        "gridlabd_seed": anchor["gridlabd_seed"],
        "operating_point": anchor["operating_point"], "columns": anchor["columns"],
        "rank": anchor["rank"], "warning_line_count": len(anchor["warning_lines"]),
        "provenance": anchor["provenance"],
    }
    cells = [anchor_summary, *new_cells]
    manifest_files = [
        path for path in root.rglob("*")
        if path.is_file() and path.name not in {"m27_repeatability_coverage.json", "independent_audit_receipt.json"}
    ]
    content = {
        "schema_version": SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M27",
        "classification": CLASSIFICATION,
        "status": "EMPIRICAL_REPEATABILITY_COVERAGE_CANDIDATE",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "final_evaluation_seeds_accessed": [],
        "final_evaluation_seeds_remain_sealed": list(FINAL_EVALUATION_SEEDS),
        "contract_id": contract["contract_id"],
        "runtime_execution": runtime_execution,
        "cells": cells,
        "analysis": {
            "true": _axis_analysis(cells, "max_abs_true_voltage_gain_pu_per_kw"),
            "measured": _axis_analysis(cells, "max_abs_measured_voltage_gain_pu_per_kw"),
            "seed_by_operating_point_interaction": "not_estimable_in_crossed_anchor_design",
            "scientific_threshold_selected": False,
        },
        "warning_summary": {
            "anchor_warning_line_count": len(anchor["warning_lines"]),
            "new_warning_line_count": sum(cell["warning_line_count"] for cell in new_cells),
            "warning_lines_retained_in_cell_sources": True,
            "raw_logs_retained": True,
        },
        "checks": {
            "seven_cells_present": len(cells) == 7,
            "six_new_cells_present": len(new_cells) == 6,
            "thirty_new_runs_completed": len(runtime_execution["runs"]) == 30,
            "immutable_M23_anchor_not_rerun": anchor["provenance"]["runtime_rerun"] is False,
            "fixed_night_three_seed_axis_complete": True,
            "fixed_seed_five_operating_point_axis_complete": True,
            "true_and_measured_vectors_retained": True,
            "small_n_warning_retained": True,
            "unestimated_interaction_warning_retained": True,
            "scientific_threshold_selected": False,
            "resource_admitted": False,
            "final_evaluation_accessed": False,
        },
        "manifest": _manifest(root, manifest_files),
        "scientific_scope": {
            "establishes_if_audit_passes": [
                "bounded_three_seed_fixed_night_repeatability_description",
                "bounded_five_operating_point_fixed_seed_coverage_description",
                "seven_cell_target_rank_stability_description",
                "crossed_anchor_source_generation_mechanics",
            ],
            "does_not_establish": [
                "seed_by_operating_point_interaction", "population_level_uncertainty",
                "full_factorial_generalization", "scientific_linearity_threshold",
                "automatic_resource_admission", "attacker_or_LLM_advantage",
                "detector_or_defense_effectiveness", "confirmatory_or_publication_grade_evidence",
            ],
            "next_gate": "separate_Brain_resource_admission_decision",
        },
    }
    evidence = _canonical_copy(content)
    evidence["evidence_id"] = "m27evidence_" + _sha256_value(content)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["build-requests", "build-contract", "build-evidence", "verify"], required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.mode == "build-requests":
        root.mkdir(parents=True, exist_ok=False)
        requests = build_action_requests()
        for identifier, items in requests.items():
            request_root = root / "requests" / identifier
            request_root.mkdir(parents=True, exist_ok=False)
            for name, request in items.items():
                create_once_json(request_root / name, request)
        print(json.dumps({"status": "registered", "cells": 6, "requests": 36}, indent=2))
        return 0
    if args.mode == "build-contract":
        contract = build_contract(root)
        create_once_json(root / "contract.json", contract)
        print(json.dumps({"status": "registered", "contract_id": contract["contract_id"]}, indent=2))
        return 0
    if args.mode == "build-evidence":
        evidence = build_evidence(root)
        create_once_json(root / "m27_repeatability_coverage.json", evidence)
        print(json.dumps({
            "status": evidence["status"],
            "evidence_id": evidence["evidence_id"],
            "true_rank": evidence["analysis"]["true"]["rank_stability"],
        }, indent=2))
        return 0
    issues = verify_evidence(root)
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
