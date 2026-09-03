"""Build and verify the bounded M23 empirical system-identification source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .manifest import build_manifest, create_once_json
from .m19_qualification import _load_json, _normalise_commands, _sha256
from .preliminary_only_gate import validate_preliminary_action_request
from .runtime import DEFAULT_CONFIG, M18_GATE_ARTIFACT


SCHEMA_VERSION = "grideval-g7-m23-system-identification/v1"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m23-system-identification-contract/v1"
CLASSIFICATION = "PRELIMINARY_ONLY"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MJREESWBMY89S08A94T0MZ"
DECISION_ID = "dec_01M1MJQWE9A762RK7N3SE3YNFF"
PAIR_ID = "m23_system_identification_seed6101"
REPLICATE_SEED = 6101
MEASUREMENT_NOISE_SEED = 96101
GRIDLABD_SEED = 10
WINDOWS = 3
WINDOW_SECONDS = 10
PROBE_MAGNITUDE_KW = 30.0
PROBE_ENERGY_KVAH = PROBE_MAGNITUDE_KW * WINDOW_SECONDS / 3600.0
OPERATING_POINT = "responsive_night"
IMAGE_TAG = "docker-cosim:latest"
IMAGE_ID = "sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7"
FINAL_EVALUATION_SEEDS = tuple(range(9101, 9113))
RUNTIME_BUDGET_ID = "m23_seed6101_three_windows_symmetric_30kw"
SOURCE_BUDGET_ID = "m23_one_source_from_five_three_window_runs"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_PATH = PACKAGE_ROOT / "g7confirm" / "runtime.py"
M21_ARTIFACT = (
    PACKAGE_ROOT
    / "artifacts"
    / "m21_three_window_timing_seed5103_attempt1"
    / "m21_three_window_timing.json"
)
EXPECTED_M18_SHA256 = (
    "e31a49d758700a3d30e4d7e3d5469b831b3f52370954fa92238eac6aa4dc3e9d"
)
EXPECTED_M21_SHA256 = (
    "2aa7bbc10bcd20f964f9a7cbcad9a70b6058b8e652acbc68bdbea953bc7e022d"
)
DEVICE_IDS = (
    "DER_EV1_BESS",
    "DER_EV3_PV",
    "DER_EV4_BESS",
    "DER_EV5_PV",
)
TARGET_IDS = ("DER_EV1_BESS", "DER_EV4_BESS")

TREATMENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "benign",
        "target_id": None,
        "command_kw": 0.0,
        "action_id": "m23_benign_seed6101",
        "action_request": "benign_action_request.json",
        "container": "g7-m23-benign-seed6101-a1",
    },
    {
        "id": "probe_ev1_plus30",
        "target_id": "DER_EV1_BESS",
        "command_kw": 30.0,
        "action_id": "m23_probe_ev1_plus30_seed6101",
        "action_request": "probe_ev1_plus30_action_request.json",
        "container": "g7-m23-ev1-plus30-seed6101-a1",
    },
    {
        "id": "probe_ev1_minus30",
        "target_id": "DER_EV1_BESS",
        "command_kw": -30.0,
        "action_id": "m23_probe_ev1_minus30_seed6101",
        "action_request": "probe_ev1_minus30_action_request.json",
        "container": "g7-m23-ev1-minus30-seed6101-a1",
    },
    {
        "id": "probe_ev4_plus30",
        "target_id": "DER_EV4_BESS",
        "command_kw": 30.0,
        "action_id": "m23_probe_ev4_plus30_seed6101",
        "action_request": "probe_ev4_plus30_action_request.json",
        "container": "g7-m23-ev4-plus30-seed6101-a1",
    },
    {
        "id": "probe_ev4_minus30",
        "target_id": "DER_EV4_BESS",
        "command_kw": -30.0,
        "action_id": "m23_probe_ev4_minus30_seed6101",
        "action_request": "probe_ev4_minus30_action_request.json",
        "container": "g7-m23-ev4-minus30-seed6101-a1",
    },
)


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
        raise ValueError(f"non-finite M23 value: {label}")
    return number


def _source_bindings() -> dict[str, dict[str, Any]]:
    paths = {
        "M18_gate": M18_GATE_ARTIFACT,
        "M21_timing_artifact": M21_ARTIFACT,
        "runtime_code": RUNTIME_PATH,
        "source_builder_code": Path(__file__),
        "DER_configuration": DEFAULT_CONFIG,
    }
    if _sha256(M18_GATE_ARTIFACT) != EXPECTED_M18_SHA256:
        raise ValueError("M18 gate hash drift")
    if _sha256(M21_ARTIFACT) != EXPECTED_M21_SHA256:
        raise ValueError("M21 timing artifact hash drift")
    return {
        name: {
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for name, path in paths.items()
    }


def build_action_requests() -> dict[str, dict[str, Any]]:
    """Build the exact five runtime requests and one source-build request."""

    runtime_hash = _sha256(RUNTIME_PATH)
    config_hash = _sha256(DEFAULT_CONFIG)
    common = {
        "partition_role": "system_identification",
        "seed": REPLICATE_SEED,
        "output_classification": CLASSIFICATION,
        "create_once": True,
        "manifest_sha256": EXPECTED_M18_SHA256,
        "config_sha256": config_hash,
        "paired_benign_id": "m23_benign_seed6101",
        "final_evaluation_data_accessed": False,
        "physical_field_actuator": False,
        "starts_or_restarts_service": False,
        "retain_failures": True,
        "local_service_identity": None,
    }
    requests: dict[str, dict[str, Any]] = {}
    for treatment in TREATMENTS:
        requests[treatment["action_request"]] = {
            "action_id": treatment["action_id"],
            "action_type": "simulator_execution",
            "code_sha256": runtime_hash,
            "budget_id": RUNTIME_BUDGET_ID,
            **common,
        }
    requests["source_generation_action_request.json"] = {
        "action_id": "m23_empirical_source_seed6101",
        "action_type": "source_generation",
        "code_sha256": _sha256(Path(__file__)),
        "budget_id": SOURCE_BUDGET_ID,
        **{**common, "paired_benign_id": None},
    }
    for name, request in requests.items():
        issues = validate_preliminary_action_request(request)
        if issues:
            raise ValueError(f"M23 action request rejected ({name}): {issues}")
    return _canonical_copy(requests)


def _load_action_requests(root: Path) -> dict[str, dict[str, Any]]:
    expected = build_action_requests()
    actual: dict[str, dict[str, Any]] = {}
    for name in expected:
        path = root / name
        if not path.is_file():
            raise ValueError(f"missing M23 action request: {name}")
        actual[name] = _load_json(path)
    if _canonical_copy(actual) != expected:
        raise ValueError("stored M23 action requests drift from executable bytes")
    return actual


def build_contract(root: Path) -> dict[str, Any]:
    """Build the content-addressed M23 contract before simulator execution."""

    action_requests = _load_action_requests(root)
    content = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M23",
        "classification": CLASSIFICATION,
        "status": "REGISTERED_NO_SIMULATOR_RUN",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "source_bindings": _source_bindings(),
        "action_requests": action_requests,
        "runtime": {
            "profile_id": PAIR_ID,
            "partition_role": "system_identification",
            "replicate_seed": REPLICATE_SEED,
            "measurement_noise_seed": MEASUREMENT_NOISE_SEED,
            "gridlabd_seed": GRIDLABD_SEED,
            "operating_point": OPERATING_POINT,
            "windows": WINDOWS,
            "window_seconds": WINDOW_SECONDS,
            "valid_post_actuation_time_s": 30,
            "image_tag": IMAGE_TAG,
            "image_id": IMAGE_ID,
            "network_mode": "none",
            "containers": [item["container"] for item in TREATMENTS],
        },
        "probe_design": {
            "authority": "one_BESS_active_power_setpoint_per_treatment",
            "command_sign_convention": "OpenDER_positive_generation",
            "targets": list(TARGET_IDS),
            "signed_commands_kw": [-PROBE_MAGNITUDE_KW, PROBE_MAGNITUDE_KW],
            "perturbed_window_cap": 1,
            "apparent_energy_cap_kvah": 2.0,
            "expected_energy_per_probe_kvah": PROBE_ENERGY_KVAH,
            "treatments": list(TREATMENTS),
        },
        "estimator": {
            "primary": "central_difference_at_runner_t30",
            "voltage_column_definition": "(v_plus30-v_minus30)/60_kw",
            "source_power_column_definition": "(source_plus30-source_minus30)/60_kw",
            "one_sided_estimates_retained": True,
            "centered_nonlinearity_residual_retained": True,
            "scalar_tool_metric": "max_abs_true_voltage_gain_pu_per_kw",
            "scientific_thresholds_selected": False,
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
            "A pass creates one empirical source candidate and qualifies the "
            "five-run source-generation mechanism only. It does not establish "
            "a final sensitivity, operating-point coverage, repeatability, "
            "linearity, real-adapter safety, attacker advantage, or final evidence."
        ),
    }
    contract = _canonical_copy(content)
    contract["contract_id"] = "m23contract_" + _sha256_value(content)
    return contract


def _load_coupling_recorders(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
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
        power_key = next(
            (key for key in rows[0] if key.startswith("constant_power_")),
            None,
        )
        if power_key is None:
            raise ValueError(f"coupling recorder missing power column: {path}")
        recorders[path.stem] = [
            {
                "timestamp": row["# timestamp"],
                "received_power_va": [
                    _finite(complex(row[power_key]).real, f"{path}.P"),
                    _finite(complex(row[power_key]).imag, f"{path}.Q"),
                ],
            }
            for row in rows
        ]
    return recorders


def _validate_run(
    *, root: Path, treatment: Mapping[str, Any], action_request: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = root / str(treatment["id"])
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
        raise ValueError(f"{treatment['id']} missing artifacts: {missing}")
    integration = _load_json(required["integration"])
    summary = _load_json(required["summary"])
    attack_trace = _load_json(required["attack"])
    budget = _load_json(required["budget"])
    device_traces = _load_json(required["devices"])
    source_trace = _load_json(required["source"])
    recorders = _load_coupling_recorders(run_dir)

    if integration.get("classification") != CLASSIFICATION:
        raise ValueError(f"{treatment['id']} classification drift")
    if integration.get("status") != "passed":
        raise ValueError(f"{treatment['id']} runtime failed")
    if integration.get("campaign_authorized") is not False:
        raise ValueError(f"{treatment['id']} campaign flag opened")
    if integration.get("evaluation_opened") is not False:
        raise ValueError(f"{treatment['id']} evaluation flag opened")
    if integration.get("runtime_window_limit") != WINDOWS:
        raise ValueError(f"{treatment['id']} window cap drift")
    lineage = integration.get("seed_lineage", {})
    expected_lineage = {
        "partition": "system_identification",
        "replicate_seed": REPLICATE_SEED,
        "attacker_policy_seed": REPLICATE_SEED,
        "measurement_noise_seed": MEASUREMENT_NOISE_SEED,
        "gridlabd_random_seed": GRIDLABD_SEED,
    }
    if lineage != expected_lineage:
        raise ValueError(f"{treatment['id']} seed lineage drift")
    if integration.get("pairing") != {
        "pair_id": PAIR_ID,
        "treatment": treatment["id"],
        "matched_seed": REPLICATE_SEED,
    }:
        raise ValueError(f"{treatment['id']} pairing drift")
    if integration.get("M18_action_request") != action_request:
        raise ValueError(f"{treatment['id']} action-request drift")
    operating_point = integration.get("operating_point", {})
    if (
        operating_point.get("id") != OPERATING_POINT
        or operating_point.get("duration_s") != WINDOWS * WINDOW_SECONDS
    ):
        raise ValueError(f"{treatment['id']} operating-point drift")
    expected_arm = "benign" if treatment["id"] == "benign" else "probe"
    if summary.get("arm") != expected_arm or summary.get("windows") != WINDOWS:
        raise ValueError(f"{treatment['id']} runner profile drift")
    if int(summary.get("gridlabd_returncode", -1)) != 0:
        raise ValueError(f"{treatment['id']} GridLAB-D failed")
    if len(attack_trace) != WINDOWS or len(source_trace) != WINDOWS:
        raise ValueError(f"{treatment['id']} trace length drift")
    if set(device_traces) != set(DEVICE_IDS) or any(
        len(rows) != WINDOWS for rows in device_traces.values()
    ):
        raise ValueError(f"{treatment['id']} device trace drift")
    records = budget.get("records", [])
    if len(records) != WINDOWS or any(
        record.get("runner_noted") is not True for record in records
    ):
        raise ValueError(f"{treatment['id']} budget trace incomplete")
    if budget.get("delivery_reconciled") is not True:
        raise ValueError(f"{treatment['id']} delivery was not reconciled")

    windows: list[dict[str, Any]] = []
    for index in range(WINDOWS):
        windows.append({
            "window": index,
            "time_s": int(attack_trace[index]["t"]),
            "true_voltage_pu": {
                key: _finite(value, f"{treatment['id']}.{key}.v{index}")
                for key, value in sorted(attack_trace[index]["telemetry"].items())
            },
            "measured_voltage_pu": {
                key: _finite(value, f"{treatment['id']}.{key}.vm{index}")
                for key, value in sorted(
                    attack_trace[index]["telemetry_meas"].items()
                )
            },
            "source_power_w_var": {
                "source_p_w": _finite(
                    source_trace[index]["source_p_w"],
                    f"{treatment['id']}.source_p{index}",
                ),
                "source_q_var": _finite(
                    source_trace[index]["source_q_var"],
                    f"{treatment['id']}.source_q{index}",
                ),
            },
            "proposed_commands_kw_kvar": _normalise_commands(
                records[index].get("proposed", {})
            ),
            "accepted_commands_kw_kvar": _normalise_commands(
                records[index].get("admitted", {})
            ),
            "delivered_commands_kw_kvar": _normalise_commands(
                records[index].get("delivered", {})
            ),
        })

    if treatment["id"] == "benign":
        if any(
            window["proposed_commands_kw_kvar"]
            or window["accepted_commands_kw_kvar"]
            or window["delivered_commands_kw_kvar"]
            for window in windows
        ):
            raise ValueError("M23 benign run contains a command")
        if (
            budget.get("windows_spent") != 0
            or float(budget.get("delivered_command_energy_kvah", -1)) != 0.0
        ):
            raise ValueError("M23 benign run spent budget")
    else:
        expected_command = {
            str(treatment["target_id"]): [float(treatment["command_kw"]), 0.0]
        }
        if windows[0]["proposed_commands_kw_kvar"] != expected_command:
            raise ValueError(f"{treatment['id']} proposed command drift")
        if windows[0]["accepted_commands_kw_kvar"] != expected_command:
            raise ValueError(f"{treatment['id']} admitted command drift")
        if windows[0]["delivered_commands_kw_kvar"] != expected_command:
            raise ValueError(f"{treatment['id']} delivered command drift")
        if any(
            window["accepted_commands_kw_kvar"]
            or window["delivered_commands_kw_kvar"]
            for window in windows[1:]
        ):
            raise ValueError(f"{treatment['id']} exceeded one intervention")
        if budget.get("windows_spent") != 1 or not math.isclose(
            float(budget.get("delivered_command_energy_kvah", -1)),
            PROBE_ENERGY_KVAH,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"{treatment['id']} budget drift")

    return {
        "treatment": treatment["id"],
        "target_id": treatment["target_id"],
        "command_kw": treatment["command_kw"],
        "run_dir": run_dir.relative_to(root).as_posix(),
        "seed_lineage": lineage,
        "operating_point": operating_point,
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
        "gridlabd_received_DER_power": recorders,
        "artifact_sha256": {
            name: _sha256(path) for name, path in sorted(required.items())
        },
    }


def _validate_execution(root: Path) -> dict[str, Any]:
    execution = _load_json(root / "runtime_execution.json")
    expected_names = [item["container"] for item in TREATMENTS]
    expected_codes = {name: 0 for name in expected_names}
    expected = {
        "classification": CLASSIFICATION,
        "container_image_id": IMAGE_ID,
        "container_image_tag": IMAGE_TAG,
        "network_mode": "none",
        "physical_field_connection": False,
        "container_names": expected_names,
        "container_exit_codes": expected_codes,
        "containers_ephemeral": True,
        "teardown_verified": True,
        "final_evaluation_data_accessed": False,
        "model_or_embedding_inference_used": False,
        "model_or_embedding_service_started_or_restarted": False,
    }
    for field, value in expected.items():
        if execution.get(field) != value:
            raise ValueError(f"M23 runtime execution drift: {field}")
    return execution


def _recorder_deltas(
    benign: Mapping[str, Any], probe: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(WINDOWS):
        values: dict[str, list[float]] = {}
        timestamp: str | None = None
        for recorder_id in sorted(benign["gridlabd_received_DER_power"]):
            left = benign["gridlabd_received_DER_power"][recorder_id][index]
            right = probe["gridlabd_received_DER_power"][recorder_id][index]
            if left["timestamp"] != right["timestamp"]:
                raise ValueError("M23 recorder timestamp drift")
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
        for recorder_id, (p_w, q_var) in row[
            "received_power_delta_probe_minus_benign_va"
        ].items():
            expected = expected_p if index == 2 and recorder_id == target_recorder else 0.0
            if not math.isclose(p_w, expected, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(
                    f"{probe['treatment']} recorder sign or target drift"
                )
            if not math.isclose(q_var, 0.0, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"{probe['treatment']} unexpected reactive probe")
    return rows


def _response_delta(
    benign: Mapping[str, Any], probe: Mapping[str, Any], index: int,
) -> dict[str, Any]:
    left = benign["windows"][index]
    right = probe["windows"][index]
    return {
        "window": index,
        "time_s": right["time_s"],
        "true_voltage_delta_probe_minus_benign_pu": {
            device_id: _finite(
                right["true_voltage_pu"][device_id]
                - left["true_voltage_pu"][device_id],
                f"{probe['treatment']}.{device_id}.delta",
            )
            for device_id in DEVICE_IDS
        },
        "source_power_delta_probe_minus_benign_w_var": {
            field: _finite(
                right["source_power_w_var"][field]
                - left["source_power_w_var"][field],
                f"{probe['treatment']}.{field}.delta",
            )
            for field in ("source_p_w", "source_q_var")
        },
    }


def _estimate_column(
    *, target_id: str, benign: Mapping[str, Any], plus: Mapping[str, Any],
    minus: Mapping[str, Any],
) -> dict[str, Any]:
    index = 2
    b = benign["windows"][index]
    p = plus["windows"][index]
    m = minus["windows"][index]
    span = 2.0 * PROBE_MAGNITUDE_KW
    voltage_central = {
        device_id: _finite(
            (p["true_voltage_pu"][device_id] - m["true_voltage_pu"][device_id])
            / span,
            f"{target_id}.{device_id}.central",
        )
        for device_id in DEVICE_IDS
    }
    voltage_plus = {
        device_id: _finite(
            (p["true_voltage_pu"][device_id] - b["true_voltage_pu"][device_id])
            / PROBE_MAGNITUDE_KW,
            f"{target_id}.{device_id}.plus",
        )
        for device_id in DEVICE_IDS
    }
    voltage_minus = {
        device_id: _finite(
            (b["true_voltage_pu"][device_id] - m["true_voltage_pu"][device_id])
            / PROBE_MAGNITUDE_KW,
            f"{target_id}.{device_id}.minus",
        )
        for device_id in DEVICE_IDS
    }
    voltage_center_residual = {
        device_id: _finite(
            (p["true_voltage_pu"][device_id] + m["true_voltage_pu"][device_id])
            / 2.0 - b["true_voltage_pu"][device_id],
            f"{target_id}.{device_id}.center_residual",
        )
        for device_id in DEVICE_IDS
    }
    source_central = {
        field: _finite(
            (p["source_power_w_var"][field] - m["source_power_w_var"][field])
            / span,
            f"{target_id}.{field}.central",
        )
        for field in ("source_p_w", "source_q_var")
    }
    source_center_residual = {
        field: _finite(
            (p["source_power_w_var"][field] + m["source_power_w_var"][field])
            / 2.0 - b["source_power_w_var"][field],
            f"{target_id}.{field}.center_residual",
        )
        for field in ("source_p_w", "source_q_var")
    }
    max_gain = max(abs(value) for value in voltage_central.values())
    if max_gain <= 0.0:
        raise ValueError(f"{target_id} empirical voltage sensitivity is zero")
    return {
        "target_id": target_id,
        "command_coordinate": "OpenDER_active_power_setpoint_kw",
        "post_actuation_window": index,
        "post_actuation_time_s": 30,
        "central_true_voltage_gain_pu_per_kw": voltage_central,
        "plus_one_sided_true_voltage_gain_pu_per_kw": voltage_plus,
        "minus_one_sided_true_voltage_gain_pu_per_kw": voltage_minus,
        "centered_true_voltage_residual_pu": voltage_center_residual,
        "central_source_power_gain_w_var_per_kw": source_central,
        "centered_source_power_residual_w_var": source_center_residual,
        "max_abs_true_voltage_gain_pu_per_kw": max_gain,
        "max_abs_centered_true_voltage_residual_pu": max(
            abs(value) for value in voltage_center_residual.values()
        ),
    }


def build_source(root: Path) -> dict[str, Any]:
    """Validate the five runs and build the empirical source candidate."""

    requests = _load_action_requests(root)
    contract = _load_json(root / "contract.json")
    if contract != build_contract(root):
        raise ValueError("stored M23 contract drifts from executable bytes")
    execution = _validate_execution(root)
    runs = [
        _validate_run(
            root=root,
            treatment=treatment,
            action_request=requests[treatment["action_request"]],
        )
        for treatment in TREATMENTS
    ]
    by_id = {run["treatment"]: run for run in runs}
    benign = by_id["benign"]
    for probe in runs[1:]:
        for field in ("seed_lineage", "operating_point", "dependency_hashes"):
            if probe[field] != benign[field]:
                raise ValueError(f"{probe['treatment']} controlled-lineage drift")
        for index in (0, 1):
            for field in (
                "true_voltage_pu", "measured_voltage_pu", "source_power_w_var",
            ):
                if probe["windows"][index][field] != benign["windows"][index][field]:
                    raise ValueError(
                        f"{probe['treatment']} pre-response drift at window {index}"
                    )

    pair_evidence: list[dict[str, Any]] = []
    for probe in runs[1:]:
        recorder = _recorder_deltas(benign, probe)
        runner = [_response_delta(benign, probe, index) for index in (1, 2)]
        if any(
            abs(value) > 1e-12
            for value in runner[0][
                "true_voltage_delta_probe_minus_benign_pu"
            ].values()
        ) or any(
            abs(value) > 1e-12
            for value in runner[0][
                "source_power_delta_probe_minus_benign_w_var"
            ].values()
        ):
            raise ValueError(f"{probe['treatment']} response appeared before t=30")
        if not any(
            abs(value) > 1e-12
            for value in runner[1][
                "true_voltage_delta_probe_minus_benign_pu"
            ].values()
        ):
            raise ValueError(f"{probe['treatment']} has no t=30 voltage response")
        pair_evidence.append({
            "treatment": probe["treatment"],
            "target_id": probe["target_id"],
            "command_kw": probe["command_kw"],
            "recorder_deltas": recorder,
            "runner_observation_deltas": runner,
        })

    columns = [
        _estimate_column(
            target_id="DER_EV1_BESS",
            benign=benign,
            plus=by_id["probe_ev1_plus30"],
            minus=by_id["probe_ev1_minus30"],
        ),
        _estimate_column(
            target_id="DER_EV4_BESS",
            benign=benign,
            plus=by_id["probe_ev4_plus30"],
            minus=by_id["probe_ev4_minus30"],
        ),
    ]
    tool_values = {
        column["target_id"]: column["max_abs_true_voltage_gain_pu_per_kw"]
        for column in columns
    }
    files = [
        path for path in root.rglob("*")
        if path.is_file() and path.name != "m23_system_identification.json"
    ]
    manifest = build_manifest(
        root=root,
        files=files,
        metadata={
            "milestone": "M23",
            "classification": CLASSIFICATION,
            "pair_id": PAIR_ID,
            "replicate_seed": REPLICATE_SEED,
        },
    )
    content = {
        "schema_version": SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M23",
        "classification": CLASSIFICATION,
        "status": "EMPIRICAL_SYSTEM_IDENTIFICATION_SOURCE_CANDIDATE",
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "final_evaluation_seeds_accessed": [],
        "final_evaluation_seeds_remain_sealed": list(FINAL_EVALUATION_SEEDS),
        "contract_id": contract["contract_id"],
        "source_generation_action_request": requests[
            "source_generation_action_request.json"
        ],
        "runtime_environment": execution,
        "runs": runs,
        "pair_evidence": pair_evidence,
        "estimator": {
            "coordinate": "OpenDER_active_power_setpoint_kw",
            "post_actuation_time_s": 30,
            "symmetric_span_kw": 60.0,
            "columns": columns,
        },
        "read_only_tool_payload_candidate": {
            "schema_version": "sensitivity-result/v1",
            "metric": "voltage_stress_gain_pu_per_kw",
            "time_s": 30,
            "window": 2,
            "values": tool_values,
            "source_classification": CLASSIFICATION,
            "empirical_source_admitted": False,
        },
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
            "full_voltage_response_vectors_retained": True,
            "scientific_threshold_selected": False,
            "resource_admitted": False,
        },
        "manifest": manifest,
        "scientific_scope": {
            "establishes": [
                "one_seed_one_operating_point_empirical_source_candidate",
                "target_isolated_symmetric_probe_mechanics",
                "t30_central_difference_voltage_response_columns",
                "source_to_future_read_only_payload_transformation",
            ],
            "does_not_establish": [
                "final_or_general_sensitivity",
                "repeatability_or_uncertainty",
                "multi_operating_point_coverage",
                "linearity_threshold_pass",
                "real_read_only_adapter_safety",
                "resource_admission",
                "attacker_or_LLM_advantage",
                "detector_or_defense_effectiveness",
                "confirmatory_or_publication_grade_evidence",
            ],
            "next_gate": (
                "Qualify a field-minimized real read-only adapter against this "
                "source candidate without simulator execution or actuation."
            ),
        },
    }
    source = _canonical_copy(content)
    source["source_id"] = "m23source_" + _sha256_value(content)
    return source


def verify_source(root: Path) -> list[str]:
    """Verify the checked-in M23 source without running Docker."""

    try:
        actual = _load_json(root / "m23_system_identification.json")
        expected = build_source(root)
    except (OSError, TypeError, ValueError) as exc:
        return [f"M23_source_unreadable_or_invalid:{exc}"]
    issues: list[str] = []
    if actual != expected:
        issues.append("M23_source_content_drift")
    if actual.get("source_id") != expected.get("source_id"):
        issues.append("M23_source_id_drift")
    if actual.get("final_evaluation_seeds_accessed") != []:
        issues.append("final_evaluation_accessed")
    if actual.get("read_only_tool_payload_candidate", {}).get(
        "empirical_source_admitted"
    ) is not False:
        issues.append("source_admission_boundary_opened")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["build-requests", "build-contract", "build-source", "verify"],
        required=True,
    )
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.mode == "build-requests":
        root.mkdir(parents=True, exist_ok=False)
        for name, request in build_action_requests().items():
            create_once_json(root / name, request)
        print(json.dumps({"status": "registered", "requests": 6}, indent=2))
        return 0
    if args.mode == "build-contract":
        create_once_json(root / "contract.json", build_contract(root))
        print(json.dumps({"status": "registered", "contract": "contract.json"}, indent=2))
        return 0
    if args.mode == "build-source":
        source = build_source(root)
        create_once_json(root / "m23_system_identification.json", source)
        print(json.dumps({
            "status": source["status"],
            "source_id": source["source_id"],
            "values": source["read_only_tool_payload_candidate"]["values"],
        }, indent=2))
        return 0
    issues = verify_source(root)
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
