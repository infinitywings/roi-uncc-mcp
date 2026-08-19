from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from v3.natig_adapter.analyze_live_equivalence import (
    EXPECTED_COMMANDS,
    EXPECTED_SAMPLE_TIMES,
    validate_execution,
)
from v3.natig_adapter.normalize_direct_live_reference import (
    EXPECTED_RUNTIME_OUTPUTS,
    NOMINAL_VOLTAGE_V,
    NormalizationError,
    R24_IDENTITY,
    normalize,
    sha256,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
NORMALIZER = (
    REPO_ROOT / "v3" / "natig_adapter" / "normalize_direct_live_reference.py"
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


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


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


def semantic(expected: dict, sequence: int) -> dict:
    event = expected["event_time_s"]
    return {
        "schema_version": "0.1",
        "kind": "command",
        "message_id": f"live-t{int(event):04d}-ao{expected['point_index']}",
        "event_time_s": event,
        "source": "ev_controller_v3",
        "target": "DER_EV4_BESS",
        "sequence": sequence,
        "type": expected["command_type"],
        "payload": {
            "value": expected["value"],
            "unit": expected["unit"],
            "valid_until_s": event + 30.0,
            "quality": ["online"],
        },
    }


def payload(expected: dict) -> tuple[dict, dict]:
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


def make_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "direct_live"
    effective = run_dir / "effective"
    runtime = run_dir / "runtime_output"
    effective.mkdir(parents=True)
    runtime.mkdir()
    shutil.copy2(
        REPO_ROOT / "v3/natig_adapter/live_direct/federation_contract.json",
        effective / "federation_contract.json",
    )

    controller_commands = []
    gateway_commands = []
    applications_by_step = {
        time_s: [] for time_s in EXPECTED_SAMPLE_TIMES
    }
    for index, expected in enumerate(EXPECTED_COMMANDS):
        event = int(expected["event_time_s"])
        message = semantic(expected, list(WINDOWS).index(event) + 1)
        settings, inputs = payload(expected)
        controller_commands.append(
            {
                "sent_time_s": expected["event_time_s"],
                "window": WINDOWS[event],
                "operation": "select_operate",
                "point_index": expected["point_index"],
                "semantic_message": message,
            }
        )
        receive = expected["event_time_s"]
        gateway_commands.append(
            {
                "receive_time_s": receive,
                "semantic_message": message,
                "select_result": {
                    "gateway_decision": "selected",
                    "reason": "select_accepted",
                    "message_id": message["message_id"],
                    "receive_time_s": receive,
                    "select_expires_at_s": receive + 5.0,
                },
                "operate_result": {
                    "gateway_decision": "accepted",
                    "reason": "operate_accepted",
                    "lifecycle_stage": "gateway_accepted",
                    "acceptance_scope": (
                        "gateway_validation_and_queue_acceptance_not_device_application"
                    ),
                    "message_id": message["message_id"],
                    "receive_time_s": receive,
                    "due_time_s": receive,
                    "actuation_sequence": index + 1,
                    "opender_settings": settings,
                    "opender_inputs": inputs,
                },
            }
        )
        applied_time = receive + 1.0
        step_time = max(10, 10 * math.ceil(applied_time / 10))
        applications_by_step[step_time].append(
            {
                "action_id": message["message_id"],
                "sequence": index + 1,
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
        terminal = NOMINAL_VOLTAGE_V * (
            1.0 + (time_s % 30) / 100_000.0
        )
        soc = 0.5 - time_s / 100_000.0
        telemetry = {
            "schema_version": "grideval-g4-telemetry-0.1",
            "target": "DER_EV4_BESS",
            "analog": [
                p_kw,
                q_kvar,
                terminal / NOMINAL_VOLTAGE_V,
                soc,
            ],
            "binary": [True, True],
        }
        gateway_steps.append(
            {
                "granted_time_s": float(time_s),
                "device_time_s": float(time_s),
                "terminal_voltage_v": terminal,
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
                "source": "gateway/der_ev4",
                "original_source": "gateway/der_ev4",
                "payload": telemetry,
            }
        )
    write_json(
        runtime / "controller_trace.json",
        {
            "scope": (
                "G4 benign live direct controller trace; "
                "no NATIG, attacker, or impairment"
            ),
            "commands": controller_commands,
            "telemetry": controller_telemetry,
            "settle_grant_s": 850.0,
            "command_message_count": 18,
            "telemetry_message_count": 84,
        },
    )
    write_json(
        runtime / "gateway_trace.json",
        {
            "scope": (
                "G4 benign live direct gateway/OpenDER trace; "
                "no NATIG, attacker, or impairment"
            ),
            "commands": gateway_commands,
            "steps": gateway_steps,
            "command_message_count": 18,
            "step_count": 84,
        },
    )
    for name in EXPECTED_RUNTIME_OUTPUTS - {
        "controller_trace.json",
        "gateway_trace.json",
    }:
        (runtime / name).write_text("successful direct process\n", encoding="utf-8")

    manifest = run_dir / "live_image_manifest.json"
    shutil.copy2(
        REPO_ROOT
        / "v3/natig_adapter/locked_runtime_result_base_r24_r1/"
        "live_image_manifest.json",
        manifest,
    )
    image_id = R24_IDENTITY["image_id"]
    manifest_sha = sha256(manifest)
    identity = {
        **R24_IDENTITY,
        "execution_user": "1000:1000",
        "helics_native_version": "2.7.1 (test)",
    }
    preflight = {
        "schema_version": "1.0",
        "scope": "test-only direct live",
        "mode": "execute",
        "static_preflight": "PASS",
        "image_preflight": "READY",
        "image_errors": [],
        "image_evidence": {
            "path": manifest.name,
            "sha256": manifest_sha,
            "image_id": image_id,
        },
        "execution_attempted": True,
        "execution_result": {
            "status": "PASS",
            "create_returncode": 0,
            "identity": identity,
            "returncodes": {
                "broker": 0,
                "controller": 0,
                "gateway": 0,
                "gridlabd": 0,
            },
            "runtime_inventory": inventory(runtime),
        },
        "claims_permitted": [
            "configuration_preflight",
            "live_direct_execution",
        ],
        "equivalence_claim_permitted": False,
        "seed": 777,
        "federate_count": 3,
        "cyber_endpoint_count": 2,
        "cyber_route_count": 2,
        "physical_value_link_count": 2,
        "gridlabd_message_endpoint_count": 0,
        "attacker_process_count": 0,
        "network_impairment_count": 0,
        "effective_inventory": inventory(effective),
    }
    write_json(run_dir / "live_direct_preflight.json", preflight)
    return run_dir


def refresh_runtime_inventory(run_dir: Path) -> None:
    path = run_dir / "live_direct_preflight.json"
    value = json.loads(path.read_text())
    value["execution_result"]["runtime_inventory"] = inventory(
        run_dir / "runtime_output"
    )
    write_json(path, value)


def test_complete_direct_bundle_normalizes_to_analyzer_contract(tmp_path):
    run_dir = make_run(tmp_path)
    result = normalize(run_dir=run_dir, repo_root=REPO_ROOT)
    errors, _ = validate_execution(result, expected_path="direct_reference")
    assert errors == []
    assert len(result["commands"]) == 18
    assert len(result["applications"]) == 18
    assert len(result["samples"]) == 84
    assert result["path"] == "direct_reference"
    assert result["provenance"]["normalization"]["is_new_execution"] is False
    assert all(command["accepted"] is True for command in result["commands"])


def test_quiet_successful_broker_is_allowed(tmp_path):
    run_dir = make_run(tmp_path)
    (run_dir / "runtime_output/broker.log").write_text("", encoding="utf-8")
    refresh_runtime_inventory(run_dir)
    assert normalize(run_dir=run_dir, repo_root=REPO_ROOT)["execution"][
        "status"
    ] == "complete"


def test_rejected_direct_operate_fails_closed(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway_trace.json"
    value = json.loads(path.read_text())
    value["commands"][6]["operate_result"]["gateway_decision"] = "rejected"
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="accepted end to end"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_direct_message_lineage_fails_closed(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway_trace.json"
    value = json.loads(path.read_text())
    value["commands"][4]["semantic_message"]["message_id"] = "forged"
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="schedule lineage"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_missing_direct_application_fails_closed(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway_trace.json"
    value = json.loads(path.read_text())
    value["steps"][0]["applied"].pop()
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="exactly 18 applications"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_controller_telemetry_must_match_gateway(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/controller_trace.json"
    value = json.loads(path.read_text())
    value["telemetry"][9]["payload"]["analog"][0] += 0.5
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="differs from direct gateway"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_every_direct_process_must_exit_zero(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "live_direct_preflight.json"
    value = json.loads(path.read_text())
    value["execution_result"]["returncodes"]["gateway"] = 1
    write_json(path, value)
    with pytest.raises(NormalizationError, match="return codes"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_r24_derived_versions_are_required(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "live_direct_preflight.json"
    value = json.loads(path.read_text())
    value["execution_result"]["identity"]["helics_version"] = "3.6.1"
    write_json(path, value)
    with pytest.raises(NormalizationError, match="r24-derived"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_runtime_artifact_drift_is_rejected(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway.log"
    path.write_text(path.read_text() + "drift\n", encoding="utf-8")
    with pytest.raises(NormalizationError, match="artifact drift"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_extra_raw_field_is_rejected(tmp_path):
    run_dir = make_run(tmp_path)
    path = run_dir / "runtime_output/gateway_trace.json"
    value = json.loads(path.read_text())
    value["commands"][0]["unexpected"] = True
    write_json(path, value)
    refresh_runtime_inventory(run_dir)
    with pytest.raises(NormalizationError, match="fields must be exact"):
        normalize(run_dir=run_dir, repo_root=REPO_ROOT)


def test_cli_is_create_once_and_does_not_claim_equivalence(tmp_path):
    run_dir = make_run(tmp_path)
    output = tmp_path / "g4_direct_live_trace.json"
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
    assert json.loads(output.read_text())["path"] == "direct_reference"
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
