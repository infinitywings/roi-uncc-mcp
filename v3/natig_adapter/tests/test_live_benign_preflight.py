from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from v3.natig_adapter.run_live_benign import (
    DEFAULT_CONTRACT,
    PreflightError,
    load_json,
    prepare,
    sha256,
    validate_contract,
    validate_image_manifest,
    validate_runtime_result,
)


def image_manifest() -> dict:
    return {
        "schema_version": "1.0",
        "ready": True,
        "image_reference": "grideval/g4@sha256:" + "a" * 64,
        "image_id": "sha256:" + "b" * 64,
        "platform": "linux/amd64",
        "natig_repo_path": "/opt/natig",
        "natig_commit": "e163b350e243c6386477e35dead979a4cb2b7c60",
        "natig_tree": "9f10cb55d5eaa4c20a95f292b84a266e9992bc1a",
        "patch_set": "g4-der-ev4",
        "patches": [{"path": "/locks/g4.patch", "sha256": "c" * 64}],
        "binary": {"path": "/opt/natig/g4", "sha256": "d" * 64},
        "source": {"path": "/opt/natig/g4.cc", "sha256": "e" * 64},
        "python_runtime": {
            "executable": "/opt/g4-python/bin/python",
            "python_version": "3.9.2",
            "helics_version": "2.7.1",
            "helics_module": {
                "path": "/locks/helics.py",
                "sha256": "f" * 64,
            },
            "opender_version": "2.2.0",
            "opender_module": {
                "path": "/locks/opender.py",
                "sha256": "1" * 64,
            },
            "numpy_version": "2.0.2",
            "numpy_module": {
                "path": "/locks/numpy.py",
                "sha256": "2" * 64,
            },
            "pandas_version": "2.2.3",
            "pandas_module": {
                "path": "/locks/pandas.py",
                "sha256": "3" * 64,
            },
        },
        "runtime_command": [
            "/opt/natig/g4",
            "--RngRun=1",
            "--helicsConfig=/g4/effective/config/natig.json",
            "--microGridConfig=/g4/effective/config/microgrid.json",
            "--topologyConfig=/g4/effective/config/topology.json",
            "--pointFileDir=/g4/effective/config",
            "--pcapFileDir=/g4/effective/runtime_output/pcap/",
        ],
    }


def test_canonical_contract_passes_static_preflight():
    contract = load_json(DEFAULT_CONTRACT)
    assert validate_contract(contract, DEFAULT_CONTRACT) == []


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: value.__setitem__("seed", 1),
        lambda value: value["broker"].__setitem__("federate_count", 5),
        lambda value: value["security_condition"]["attacker_processes"].append(
            "attacker"
        ),
        lambda value: value["cyber_routes"].pop(),
        lambda value: value["source_locks"][0].__setitem__(
            "sha256", "0" * 64
        ),
    ),
)
def test_contract_mutations_fail_closed(mutation):
    contract = deepcopy(load_json(DEFAULT_CONTRACT))
    mutation(contract)
    assert validate_contract(contract, DEFAULT_CONTRACT)


def test_gridlabd_message_endpoint_is_rejected(tmp_path):
    source_dir = DEFAULT_CONTRACT.parent
    copied = tmp_path / "live"
    copied.mkdir()
    for name in (
        "federation_contract.json",
        "controller.json",
        "natig.json",
        "gateway.json",
        "gridlabd.json",
    ):
        (copied / name).write_bytes((source_dir / name).read_bytes())

    contract_path = copied / "federation_contract.json"
    contract = load_json(contract_path)
    overlay = contract["g3_physical_overlay"]
    overlay["model"] = str(
        (source_dir / overlay["model"]).resolve()
    )
    overlay["support_tree"] = str(
        (source_dir / overlay["support_tree"]).resolve()
    )
    for lock in contract["source_locks"]:
        lock["path"] = str((source_dir / lock["path"]).resolve())
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    grid_path = copied / "gridlabd.json"
    grid = load_json(grid_path)
    grid["endpoints"] = [
        {"name": "GLD/bypass", "type": "json", "global": True}
    ]
    grid_path.write_text(json.dumps(grid), encoding="utf-8")
    errors = validate_contract(contract, contract_path)
    assert any("zero message endpoints" in error for error in errors)
    assert any("exactly four cyber endpoints" in error for error in errors)


def test_image_manifest_requires_patched_python_runtime_and_exact_hashes():
    gate = load_json(DEFAULT_CONTRACT)["external_image_gate"]
    valid = image_manifest()
    assert validate_image_manifest(valid, gate) == []

    missing_helics = deepcopy(valid)
    missing_helics["python_runtime"]["helics_version"] = None
    errors = validate_image_manifest(missing_helics, gate)
    assert any("HELICS" in error for error in errors)

    old_python = deepcopy(valid)
    old_python["python_runtime"]["python_version"] = "3.6.15"
    errors = validate_image_manifest(old_python, gate)
    assert any("Python runtime" in error for error in errors)

    substituted_numpy = deepcopy(valid)
    substituted_numpy["python_runtime"]["numpy_version"] = "2.1.0"
    errors = validate_image_manifest(substituted_numpy, gate)
    assert any("NumPy" in error for error in errors)

    relative_binary = deepcopy(valid)
    relative_binary["binary"]["path"] = "g4"
    assert validate_image_manifest(relative_binary, gate)

    substituted_executable = deepcopy(valid)
    substituted_executable["runtime_command"][0] = "/opt/natig/unhashed"
    errors = validate_image_manifest(substituted_executable, gate)
    assert any(
        "exactly equal the hashed binary.path" in error for error in errors
    )


def test_dry_run_is_create_once_and_records_image_block(tmp_path):
    output = tmp_path / "preflight"
    result = prepare(
        contract_path=DEFAULT_CONTRACT,
        output_dir=output,
    )
    assert result["static_preflight"] == "PASS"
    assert result["image_preflight"] == "BLOCKED_IMAGE_NOT_READY"
    assert result["execution_attempted"] is False
    assert result["claims_permitted"] == ["configuration_preflight"]
    assert result["equivalence_claim_permitted"] is False
    assert result["federate_count"] == 4
    assert result["cyber_endpoint_count"] == 4
    assert result["cyber_route_count"] == 6
    assert result["physical_value_link_count"] == 2
    assert result["gridlabd_message_endpoint_count"] == 0
    assert result["attacker_process_count"] == 0
    assert (output / "effective/model/mainglm.json").is_file()
    assert (
        load_json(output / "effective/model/mainglm.json")["endpoints"]
        == []
    )
    assert (output / "effective/runtime_output/pcap").is_dir()
    for name in ("microgrid.json", "topology.json", "points_der_ev4.csv"):
        assert (output / "effective/config" / name).is_file()
    with pytest.raises(FileExistsError):
        prepare(contract_path=DEFAULT_CONTRACT, output_dir=output)


def test_ready_dry_run_retains_exact_image_manifest_and_identity(tmp_path):
    manifest_path = tmp_path / "input-live-image.json"
    manifest_path.write_text(
        json.dumps(image_manifest(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "ready-preflight"
    result = prepare(
        contract_path=DEFAULT_CONTRACT,
        output_dir=output,
        image_manifest_path=manifest_path,
    )
    retained = output / "live_image_manifest.json"
    assert result["image_preflight"] == "READY"
    assert result["execution_attempted"] is False
    assert retained.read_bytes() == manifest_path.read_bytes()
    assert result["image_evidence"] == {
        "path": retained.name,
        "sha256": sha256(manifest_path),
        "image_id": image_manifest()["image_id"],
    }


def test_direct_cli_bootstraps_repository_imports(tmp_path):
    output = tmp_path / "cli-preflight"
    script = DEFAULT_CONTRACT.parents[1] / "run_live_benign.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(output)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert load_json(output / "live_benign_preflight.json")[
        "static_preflight"
    ] == "PASS"


def test_execute_refuses_missing_image_without_creating_output(tmp_path):
    output = tmp_path / "execute"
    with pytest.raises(PreflightError, match="BLOCKED_IMAGE_NOT_READY"):
        prepare(
            contract_path=DEFAULT_CONTRACT,
            output_dir=output,
            execute=True,
        )
    assert not output.exists()


def test_runtime_requires_every_zero_return_code_and_new_nonempty_output(
    tmp_path,
):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    processes = ["broker", "controller", "natig", "gateway", "gridlabd"]
    outputs = [f"{name}.log" for name in processes]
    for name in outputs:
        (runtime / name).write_text("new evidence\n", encoding="utf-8")
    assert (
        validate_runtime_result(
            {name: 0 for name in processes},
            runtime,
            processes,
            outputs,
        )
        == []
    )
    errors = validate_runtime_result(
        {
            "broker": 0,
            "controller": 0,
            "natig": 9,
            "gateway": 0,
            "gridlabd": 0,
        },
        runtime,
        processes,
        outputs + ["gateway_trace.json"],
    )
    assert any("natig return code" in error for error in errors)
    assert any("gateway_trace.json" in error for error in errors)


def test_runtime_allows_quiet_successful_broker_but_not_other_empty_outputs(
    tmp_path,
):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    processes = ["broker", "controller", "natig", "gateway", "gridlabd"]
    outputs = [f"{name}.log" for name in processes]
    for name in outputs:
        (runtime / name).write_text("evidence\n", encoding="utf-8")
    (runtime / "broker.log").write_text("", encoding="utf-8")

    assert (
        validate_runtime_result(
            {name: 0 for name in processes},
            runtime,
            processes,
            outputs,
        )
        == []
    )

    (runtime / "gateway.log").write_text("", encoding="utf-8")
    errors = validate_runtime_result(
        {name: 0 for name in processes},
        runtime,
        processes,
        outputs,
    )
    assert errors == [
        "required runtime output missing/empty: gateway.log"
    ]

    (runtime / "broker.log").unlink()
    errors = validate_runtime_result(
        {name: 0 for name in processes},
        runtime,
        processes,
        outputs,
    )
    assert "required runtime output missing: broker.log" in errors
