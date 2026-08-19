from __future__ import annotations

import json
import math
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from v3.natig_adapter.analyze_live_equivalence import (
    EXPECTED_COMMANDS,
    EXPECTED_SAMPLE_TIMES,
    validate_execution,
)
from v3.natig_adapter.normalize_natig_live_reference import (
    NOMINAL_VOLTAGE_V,
    NormalizationError,
    _float32,
    normalize,
    sha256,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
NORMALIZER = (
    REPO_ROOT / "v3" / "natig_adapter" / "normalize_natig_live_reference.py"
)
RUNTIME_OUTPUTS = (
    "broker.log",
    "controller.log",
    "controller_trace.json",
    "gateway.log",
    "gateway_trace.json",
    "gridlabd.log",
    "natig.log",
)
WINDOWS = {
    0: "baseline",
    60: "p_inject",
    180: "p_recovery",
    240: "p_absorb",
    360: "pre_q_recovery",
    420: "q_inject",
    540: "q_recovery",
    600: "q_absorb",
    720: "final_recovery",
}


def inventory(root: Path) -> list[dict]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def controller_semantic(expected: dict, sequence: int) -> dict:
    event_time = expected["event_time_s"]
    return {
        "schema_version": "0.1",
        "kind": "command",
        "message_id": (
            f"live-t{int(event_time):04d}-ao{expected['point_index']}"
        ),
        "event_time_s": event_time,
        "source": "ev_controller_v3",
        "target": "DER_EV4_BESS",
        "sequence": sequence,
        "type": expected["command_type"],
        "payload": {
            "value": expected["value"],
            "unit": expected["unit"],
            "valid_until_s": event_time + 30.0,
            "quality": ["online"],
        },
    }


def bridge_semantic(expected: dict, transaction: int) -> dict:
    event_time = expected["event_time_s"]
    return {
        "schema_version": "0.1",
        "kind": "command",
        "message_id": (
            f"dnp3-o4-t{transaction:08d}-ao{expected['point_index']}-"
            f"{transaction:016x}"
        ),
        "event_time_s": event_time,
        "source": "ev_controller_v3",
        "target": "DER_EV4_BESS",
        "sequence": transaction,
        "type": expected["command_type"],
        "payload": {
            "value": expected["value"],
            "unit": expected["unit"],
            "valid_until_s": event_time + 5.0,
            "quality": ["online"],
        },
    }


def application_payload(expected: dict) -> tuple[dict, dict]:
    if expected["point_index"] == 0:
        return {}, {"demand_kw": expected["value"]}
    value = expected["value"]
    return (
        {
            "QV_MODE_ENABLE": "DISABLED",
            "QP_MODE_ENABLE": "DISABLED",
            "CONST_PF_MODE_ENABLE": "DISABLED",
            "CONST_Q": value * 0.005,
            "CONST_Q_MODE_ENABLE": "DISABLED" if value == 0.0 else "ENABLED",
        },
        {},
    )


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def make_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "live_run"
    effective = run_dir / "effective"
    runtime = run_dir / "runtime_output"
    effective.mkdir(parents=True)
    runtime.mkdir()

    contract = {
        "schema_version": "1.0",
        "seed": 777,
        "simulation": {
            "duration_s": 840,
            "controller_period_s": 10,
            "dnp3_poll_period_s": 10,
            "physical_coupling_period_s": 10,
            "opender_internal_step_s": 1,
        },
        "security_condition": {
            "name": "benign",
            "attacker_processes": [],
            "network_impairments": [],
        },
        "required_processes": [
            "broker",
            "controller",
            "natig",
            "gateway",
            "gridlabd",
        ],
        "required_runtime_outputs": list(RUNTIME_OUTPUTS),
        "source_locks": [
            {
                "path": "../run_live_benign.py",
                "sha256": "a" * 64,
            }
        ],
    }
    write_json(effective / "federation_contract.json", contract)

    controller_commands = []
    for expected in EXPECTED_COMMANDS:
        event_time = int(expected["event_time_s"])
        sequence = list(WINDOWS).index(event_time) + 1
        controller_commands.append(
            {
                "sent_time_s": expected["event_time_s"],
                "window": WINDOWS[event_time],
                "operation": "select_operate",
                "point_index": expected["point_index"],
                "semantic_message": controller_semantic(expected, sequence),
            }
        )

    gateway_commands = []
    applications_by_step: dict[int, list[dict]] = {
        time_s: [] for time_s in EXPECTED_SAMPLE_TIMES
    }
    for transaction, expected in enumerate(EXPECTED_COMMANDS, start=1):
        semantic = bridge_semantic(expected, transaction)
        receive = expected["event_time_s"]
        raw_count = round(expected["value"] / 0.001)
        for operation in ("select", "operate"):
            gateway_result = (
                {
                    "gateway_decision": "selected",
                    "message_id": semantic["message_id"],
                    "receive_time_s": receive,
                }
                if operation == "select"
                else {
                    "gateway_decision": "accepted",
                    "lifecycle_stage": "gateway_accepted",
                    "message_id": semantic["message_id"],
                    "receive_time_s": receive,
                }
            )
            gateway_commands.append(
                {
                    "receive_time_s": receive,
                    "wire": {
                        "schema_version": "grideval-g4-dnp3-object-0.1",
                        "group": 41,
                        "variation": 1,
                        "operation": operation,
                        "master_address": 1,
                        "outstation_address": 4,
                        "point_index": expected["point_index"],
                        "raw_count": raw_count,
                        "status": 0,
                    },
                    "result": {
                        "adapter_decision": (
                            "selected" if operation == "select" else "accepted"
                        ),
                        "semantic_message": semantic,
                        "gateway_result": gateway_result,
                    },
                }
            )
        settings, inputs = application_payload(expected)
        applied_time = receive + 1.0
        step_time = max(10, 10 * math.ceil(applied_time / 10.0))
        applications_by_step[step_time].append(
            {
                "action_id": semantic["message_id"],
                "sequence": transaction,
                "due_time_s": receive,
                "applied_time_s": applied_time,
                "settings": settings,
                "inputs": inputs,
            }
        )

    gateway_steps = []
    controller_telemetry = []
    for time_s in EXPECTED_SAMPLE_TIMES:
        p_kw = float((time_s // 60) % 3 - 1)
        q_kvar = float((time_s // 120) % 3 - 1)
        terminal_voltage_v = NOMINAL_VOLTAGE_V * (
            1.0 + (time_s % 30) / 100_000.0
        )
        soc = 0.5 - time_s / 100_000.0
        analog = [
            p_kw,
            q_kvar,
            terminal_voltage_v / NOMINAL_VOLTAGE_V,
            soc,
        ]
        telemetry = {
            "schema_version": "grideval-g4-telemetry-0.1",
            "target": "DER_EV4_BESS",
            "analog": analog,
            "binary": [True, True],
        }
        gateway_steps.append(
            {
                "granted_time_s": float(time_s),
                "device_time_s": float(time_s),
                "terminal_voltage_v": terminal_voltage_v,
                "p_out_kw": p_kw,
                "q_out_kvar": q_kvar,
                "soc_pu": soc,
                "status": "Continuous Operation",
                "feeder_load_va": {
                    "real": -1000.0 * p_kw,
                    "imag": -1000.0 * q_kvar,
                },
                "applied": applications_by_step[time_s],
                "telemetry": telemetry,
            }
        )
        controller_telemetry.append(
            {
                "granted_time_s": float(time_s),
                "source": "natig/cc_der_ev4",
                "original_source": "natig/cc_der_ev4",
                "payload": {
                    "wire_schema": (
                        "grideval-g4-dnp3-telemetry-decoded/1.0"
                    ),
                    "master_address": 1,
                    "outstation_address": 4,
                    "received_time_s": float(time_s),
                    "analog_g30v5": [_float32(value) for value in analog],
                    "binary_g1v2": [True, True],
                },
            }
        )

    controller_trace = {
        "scope": "G4 benign controller trace; no attacker",
        "commands": controller_commands,
        "telemetry": controller_telemetry,
        "settle_grant_s": 850.0,
        "command_message_count": 18,
        "telemetry_message_count": 84,
    }
    gateway_trace = {
        "scope": "G4 benign gateway/OpenDER trace; no attacker",
        "commands": gateway_commands,
        "steps": gateway_steps,
        "command_message_count": 36,
        "step_count": 84,
    }
    write_json(runtime / "controller_trace.json", controller_trace)
    write_json(runtime / "gateway_trace.json", gateway_trace)
    for filename in set(RUNTIME_OUTPUTS) - {
        "controller_trace.json",
        "gateway_trace.json",
    }:
        (runtime / filename).write_text("successful synthetic process\n")

    image_id = "sha256:" + "a" * 64
    retained_manifest = run_dir / "live_image_manifest.json"
    write_json(
        retained_manifest,
        {
            "schema_version": "1.0",
            "ready": True,
            "image_id": image_id,
        },
    )
    retained_manifest_sha = sha256(retained_manifest)
    preflight = {
        "schema_version": "1.0",
        "scope": "test-only",
        "mode": "execute",
        "static_preflight": "PASS",
        "image_preflight": "READY",
        "image_errors": [],
        "image_evidence": {
            "path": retained_manifest.name,
            "sha256": retained_manifest_sha,
            "image_id": image_id,
        },
        "execution_attempted": True,
        "execution_result": {
            "status": "PASS",
            "create_returncode": 0,
            "identity": {
                "image_id": image_id,
                "image_manifest_sha256": retained_manifest_sha,
                "natig_commit": "b" * 40,
                "natig_tree": "c" * 40,
                "binary_sha256": "d" * 64,
                "source_sha256": "e" * 64,
                "helics_module_sha256": "1" * 64,
                "opender_module_sha256": "2" * 64,
                "numpy_module_sha256": "3" * 64,
                "pandas_module_sha256": "4" * 64,
                "execution_user": "1000:1000",
                "python_version": "3.9.2",
                "helics_version": "2.7.1",
                "helics_native_version": "2.7.1 (test)",
                "opender_version": "2.2.0",
                "numpy_version": "2.0.2",
                "pandas_version": "2.2.3",
            },
            "returncodes": {
                "broker": 0,
                "controller": 0,
                "natig": 0,
                "gateway": 0,
                "gridlabd": 0,
            },
            "runtime_inventory": inventory(runtime),
        },
        "claims_permitted": [
            "configuration_preflight",
            "live_benign_execution",
        ],
        "equivalence_claim_permitted": False,
        "seed": 777,
        "federate_count": 4,
        "cyber_endpoint_count": 4,
        "cyber_route_count": 6,
        "physical_value_link_count": 2,
        "gridlabd_message_endpoint_count": 0,
        "attacker_process_count": 0,
        "network_impairment_count": 0,
        "effective_inventory": inventory(effective),
    }
    write_json(run_dir / "live_benign_preflight.json", preflight)
    return run_dir


def refresh_runtime_inventory(run_dir: Path) -> None:
    path = run_dir / "live_benign_preflight.json"
    preflight = json.loads(path.read_text())
    preflight["execution_result"]["runtime_inventory"] = inventory(
        run_dir / "runtime_output"
    )
    write_json(path, preflight)


def test_complete_live_bundle_normalizes_to_analyzer_contract(tmp_path):
    run_dir = make_run(tmp_path)
    result = normalize(run_dir=run_dir, repo_root=REPO_ROOT)
    errors, _ = validate_execution(result, expected_path="natig")
    assert errors == []
    assert len(result["commands"]) == 18
    assert len(result["applications"]) == 18
    assert len(result["samples"]) == 84
    assert result["samples"][0]["voltage_pu"] == _float32(1.0001)
    assert result["provenance"]["normalization"]["is_new_execution"] is False
    assert not any(
        item.startswith("cross-version HELICS comparison:")
        for item in result["provenance"]["comparison_qualifications"]
    )


def test_quiet_successful_broker_log_normalizes(tmp_path):
    run_dir = make_run(tmp_path)
    (run_dir / "runtime_output/broker.log").write_text("", encoding="utf-8")
    refresh_runtime_inventory(run_dir)
    result = normalize(run_dir=run_dir, repo_root=REPO_ROOT)
    errors, _ = validate_execution(result, expected_path="natig")
    assert errors == []


@pytest.mark.parametrize(
    ("collection", "message"),
    [
        ("commands", "exactly 18 commands"),
        ("telemetry", "exactly 84 decoded telemetry"),
    ],
)
def test_missing_controller_evidence_fails_closed(tmp_path, collection, message):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/controller_trace.json"
    value = json.loads(path.read_text())
    value[collection].pop()
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match=message):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_partial_controller_telemetry_fails_closed(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/controller_trace.json"
    value = json.loads(path.read_text())
    value["telemetry"][9]["payload"]["analog_g30v5"].pop()
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="partial or malformed"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_controller_telemetry_must_match_gateway_float32_encoding(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/controller_trace.json"
    value = json.loads(path.read_text())
    value["telemetry"][12]["payload"]["analog_g30v5"][0] += 0.25
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="after float32 encoding"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_gateway_telemetry_must_report_observed_terminal_voltage(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway_trace.json"
    value = json.loads(path.read_text())
    value["steps"][0]["telemetry"]["analog"][2] = 1.0
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="gateway telemetry is malformed"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_missing_opender_application_fails_closed(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway_trace.json"
    value = json.loads(path.read_text())
    value["steps"][0]["applied"].pop()
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="exactly 18 applications"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_rejected_gateway_operate_fails_closed(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway_trace.json"
    value = json.loads(path.read_text())
    value["commands"][1]["result"]["adapter_decision"] = "rejected"
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="not accepted end to end"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_wrong_dnp3_raw_count_fails_closed(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway_trace.json"
    value = json.loads(path.read_text())
    value["commands"][10]["wire"]["raw_count"] += 1
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="expected DNP3 callback"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_preflight_must_prove_every_process_succeeded(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "live_benign_preflight.json"
    value = json.loads(path.read_text())
    value["execution_result"]["returncodes"]["natig"] = 1
    write_json(path, value)
    with pytest.raises(NormalizationError, match="return codes"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_retained_image_manifest_byte_drift_is_rejected(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "live_image_manifest.json"
    path.write_text(path.read_text() + " ", encoding="utf-8")
    with pytest.raises(
        NormalizationError, match="retained image manifest digest mismatch"
    ):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_retained_image_id_mismatch_is_rejected(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "live_benign_preflight.json"
    value = json.loads(path.read_text())
    value["execution_result"]["identity"]["image_id"] = "sha256:" + "f" * 64
    write_json(path, value)
    with pytest.raises(
        NormalizationError, match="retained image identity mismatch"
    ):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_inventory_hash_drift_is_rejected_before_trace_use(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/natig.log"
    path.write_text(path.read_text() + "drift\n")
    with pytest.raises(NormalizationError, match="artifact drift"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_cli_is_create_once_and_does_not_claim_equivalence(tmp_path):
    run_dir = make_run(tmp_path)
    output = tmp_path / "natig_trace.json"
    command = [
        sys.executable,
        str(NORMALIZER),
        "--run-dir",
        str(run_dir),
        "--repo-root",
        str(REPO_ROOT),
        "--output",
        str(output),
    ]
    first = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["equivalence_claim_permitted"] is False
    assert json.loads(output.read_text())["path"] == "natig"
    original = output.read_bytes()
    second = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode != 0
    assert output.read_bytes() == original


def test_mutated_copy_does_not_change_original_fixture(tmp_path):
    run_dir = make_run(tmp_path)
    before = normalize(run_dir=run_dir, repo_root=REPO_ROOT)
    mutated = deepcopy(before)
    mutated["samples"][0]["p_kw"] += 1.0
    assert normalize(run_dir=run_dir, repo_root=REPO_ROOT) == before
