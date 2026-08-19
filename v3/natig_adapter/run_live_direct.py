#!/usr/bin/env python3
"""Stage, attest, and optionally execute the G4 live direct-reference arm."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v3.natig_adapter.run_live_benign import (
    PreflightError,
    _container_hash,
    _run,
    inventory,
    load_json,
    sha256,
    tree_sha256,
    validate_image_manifest,
    validate_runtime_result,
)


LIVE_DIR = Path(__file__).with_name("live_direct")
DEFAULT_CONTRACT = LIVE_DIR / "federation_contract.json"
DEFAULT_IMAGE_MANIFEST = (
    Path(__file__).with_name("locked_runtime_result_base_r24_r1")
    / "live_image_manifest.json"
)
SAFE_OUTPUT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}")
EXPECTED_FEDERATES = {
    "controller": (
        "g4_live_direct_controller_der_ev4",
        "controller.json",
    ),
    "gateway": (
        "g4_live_direct_gateway_der_ev4",
        "gateway.json",
    ),
    "gridlabd": (
        "g4_gridlabd_der_ev4",
        "../live_benign/gridlabd.json",
    ),
}
EXPECTED_ROUTES = {
    (
        "command",
        "controller/der_ev4",
        "gateway/der_ev4",
        "helics_message",
    ),
    (
        "telemetry",
        "gateway/der_ev4",
        "controller/der_ev4",
        "helics_message",
    ),
}
EXPECTED_PHYSICAL = {
    (
        "gridlabd/ev4_voltage_c",
        "gridlabd",
        "gateway",
        "complex",
        "V",
    ),
    (
        "gateway/feeder_load_va",
        "gateway",
        "gridlabd",
        "complex",
        "VA",
    ),
}
IDENTITY_KEYS = {
    "image_id",
    "image_manifest_sha256",
    "execution_user",
    "natig_commit",
    "natig_tree",
    "binary_sha256",
    "source_sha256",
    "helics_module_sha256",
    "opender_module_sha256",
    "numpy_module_sha256",
    "pandas_module_sha256",
    "python_version",
    "helics_version",
    "helics_native_version",
    "opender_version",
    "numpy_version",
    "pandas_version",
}


def _exact_keys(
    value: dict[str, Any],
    expected: set[str],
    label: str,
    errors: list[str],
) -> None:
    actual = set(value)
    if actual != expected:
        errors.append(
            f"{label} keys must be exact; "
            f"missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _resolve(contract_path: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise PreflightError("contract path must be a non-empty string")
    return (contract_path.parent / relative).resolve()


def validate_contract(
    contract: dict[str, Any], contract_path: Path
) -> list[str]:
    """Validate the complete direct-arm contract without changing state."""
    errors: list[str] = []
    required_root = {
        "schema_version",
        "scope",
        "seed",
        "simulation",
        "broker",
        "federates",
        "cyber_routes",
        "physical_values",
        "security_condition",
        "g3_physical_overlay",
        "source_locks",
        "external_image_gate",
        "r24_image_manifest",
        "required_processes",
        "required_runtime_outputs",
    }
    _exact_keys(contract, required_root, "contract", errors)
    if contract.get("schema_version") != "1.0":
        errors.append("contract schema_version must equal 1.0")
    if contract.get("seed") != 777:
        errors.append("direct reference seed must equal 777")
    if contract.get("simulation") != {
        "duration_s": 840,
        "controller_period_s": 10,
        "physical_coupling_period_s": 10,
        "opender_internal_step_s": 1,
    }:
        errors.append("simulation timing must exactly reuse the G3/G4 freeze")
    if contract.get("broker") != {
        "core_type": "zmq",
        "port": 9000,
        "federate_count": 3,
    }:
        errors.append("broker contract must require exactly three federates")

    federates = contract.get("federates")
    observed_federates: dict[str, tuple[Any, Any]] = {}
    if not isinstance(federates, list):
        errors.append("federates must be a list")
        federates = []
    for index, item in enumerate(federates):
        if not isinstance(item, dict):
            errors.append(f"federates[{index}] must be an object")
            continue
        _exact_keys(
            item,
            {"owner", "name", "config"},
            f"federates[{index}]",
            errors,
        )
        owner = item.get("owner")
        if not isinstance(owner, str) or owner in observed_federates:
            errors.append(f"federates[{index}].owner must be unique")
            continue
        observed_federates[owner] = (item.get("name"), item.get("config"))
    if observed_federates != EXPECTED_FEDERATES or len(federates) != 3:
        errors.append("direct federates must be controller/gateway/gridlabd")

    routes = contract.get("cyber_routes")
    observed_routes = set()
    if not isinstance(routes, list):
        errors.append("cyber_routes must be a list")
        routes = []
    for item in routes:
        if isinstance(item, dict):
            _exact_keys(
                item,
                {"stream", "source", "destination", "transport"},
                "cyber route",
                errors,
            )
            observed_routes.add(
                (
                    item.get("stream"),
                    item.get("source"),
                    item.get("destination"),
                    item.get("transport"),
                )
            )
    if observed_routes != EXPECTED_ROUTES or len(routes) != 2:
        errors.append("direct cyber routes must be the exact bidirectional pair")

    physical = contract.get("physical_values")
    observed_physical = set()
    if not isinstance(physical, list):
        errors.append("physical_values must be a list")
        physical = []
    for item in physical:
        if isinstance(item, dict):
            _exact_keys(
                item,
                {"key", "publisher", "subscriber", "type", "unit"},
                "physical value",
                errors,
            )
            observed_physical.add(
                (
                    item.get("key"),
                    item.get("publisher"),
                    item.get("subscriber"),
                    item.get("type"),
                    item.get("unit"),
                )
            )
    if observed_physical != EXPECTED_PHYSICAL or len(physical) != 2:
        errors.append("physical HELICS links must match the canonical G3 pair")
    if contract.get("security_condition") != {
        "name": "benign",
        "attacker_processes": [],
        "network_impairments": [],
        "natig_processes": [],
    }:
        errors.append("direct arm must contain no NATIG, attacker, or impairment")

    overlay = contract.get("g3_physical_overlay")
    expected_overlay_keys = {
        "model",
        "model_sha256",
        "support_tree",
        "support_tree_sha256",
        "gridlabd_config",
        "gridlabd_config_sha256",
        "coupling_object",
        "parent_bus",
        "minimum_timestep_s",
    }
    if not isinstance(overlay, dict):
        errors.append("g3_physical_overlay must be an object")
        overlay = {}
    _exact_keys(
        overlay, expected_overlay_keys, "g3_physical_overlay", errors
    )
    if (
        overlay.get("coupling_object") != "DER_EV4_BESS_COUPLING"
        or overlay.get("parent_bus") != "l92"
        or overlay.get("minimum_timestep_s") != 10
    ):
        errors.append("physical overlay identity must remain l92/10-second")
    try:
        model = _resolve(contract_path, overlay.get("model"))
        if not model.is_file():
            errors.append(f"canonical G3 model is missing: {model}")
        elif sha256(model) != overlay.get("model_sha256"):
            errors.append("canonical G3 model hash mismatch")
        else:
            model_text = model.read_text(encoding="utf-8")
            for token in (
                "#set minimum_timestep=10.000000;",
                "#set randomseed=10;",
                "name DER_EV4_BESS_COUPLING;",
                "parent l92;",
                "configure mainglm.json;",
            ):
                if token not in model_text:
                    errors.append(
                        f"canonical G3 model is missing freeze token {token!r}"
                    )
    except PreflightError as exc:
        errors.append(str(exc))
    try:
        support = _resolve(contract_path, overlay.get("support_tree"))
        if not support.is_dir():
            errors.append(f"G3 support tree is missing: {support}")
        elif tree_sha256(support) != overlay.get("support_tree_sha256"):
            errors.append("G3 support tree hash mismatch")
    except PreflightError as exc:
        errors.append(str(exc))
    try:
        grid_config = _resolve(
            contract_path, overlay.get("gridlabd_config")
        )
        if not grid_config.is_file():
            errors.append("canonical GridLAB-D HELICS config is missing")
        elif sha256(grid_config) != overlay.get(
            "gridlabd_config_sha256"
        ):
            errors.append("canonical GridLAB-D config hash mismatch")
    except PreflightError as exc:
        errors.append(str(exc))

    configs: dict[str, dict[str, Any]] = {}
    for owner, (name, relative) in EXPECTED_FEDERATES.items():
        path = _resolve(contract_path, relative)
        if not path.is_file():
            errors.append(f"missing federate config: {path}")
            continue
        config = load_json(path)
        configs[owner] = config
        if config.get("name") != name:
            errors.append(f"{owner} federate name mismatch")
    controller = configs.get("controller", {})
    gateway = configs.get("gateway", {})
    gridlabd = configs.get("gridlabd", {})
    if controller.get("period") != 10 or gateway.get("period") != 10:
        errors.append("controller and gateway periods must both equal 10")
    endpoint_owners = {}
    for owner, config in configs.items():
        endpoints = config.get("endpoints")
        if not isinstance(endpoints, list):
            errors.append(f"{owner} endpoints must be a list")
            continue
        if owner == "gridlabd" and endpoints:
            errors.append("GridLAB-D must declare zero message endpoints")
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                errors.append(f"{owner} endpoint must be an object")
                continue
            name = endpoint.get("name")
            if (
                not isinstance(name, str)
                or name in endpoint_owners
                or endpoint.get("global") is not True
            ):
                errors.append(f"{owner} endpoint declaration is invalid")
            else:
                endpoint_owners[name] = owner
    if endpoint_owners != {
        "controller/der_ev4": "controller",
        "gateway/der_ev4": "gateway",
    }:
        errors.append("direct configs must declare exactly two cyber endpoints")
    if gridlabd.get("period") != 10:
        errors.append("GridLAB-D period must equal 10")
    grid_pubs = {
        (item.get("key"), item.get("type"), item.get("unit"))
        for item in gridlabd.get("publications", [])
        if isinstance(item, dict)
    }
    grid_subs = {
        (item.get("key"), item.get("type"), item.get("unit"))
        for item in gridlabd.get("subscriptions", [])
        if isinstance(item, dict)
    }
    gateway_pubs = {
        (item.get("key"), item.get("type"), item.get("unit"))
        for item in gateway.get("publications", [])
        if isinstance(item, dict)
    }
    gateway_subs = {
        (item.get("key"), item.get("type"), item.get("unit"))
        for item in gateway.get("subscriptions", [])
        if isinstance(item, dict)
    }
    if grid_pubs != {("gridlabd/ev4_voltage_c", "complex", "V")}:
        errors.append("GridLAB-D voltage publication must remain canonical")
    if grid_subs != {("gateway/feeder_load_va", "complex", "VA")}:
        errors.append("GridLAB-D feeder-load subscription must remain canonical")
    if gateway_pubs != {("gateway/feeder_load_va", "complex", "VA")}:
        errors.append("gateway feeder-load publication must remain canonical")
    if gateway_subs != {("gridlabd/ev4_voltage_c", "complex", "V")}:
        errors.append("gateway voltage subscription must remain canonical")

    locks = contract.get("source_locks")
    if not isinstance(locks, list) or not locks:
        errors.append("source_locks must be a non-empty list")
        locks = []
    seen = set()
    for index, item in enumerate(locks):
        if not isinstance(item, dict):
            errors.append(f"source_locks[{index}] must be an object")
            continue
        _exact_keys(
            item, {"path", "sha256"}, f"source_locks[{index}]", errors
        )
        try:
            path = _resolve(contract_path, item.get("path"))
        except PreflightError as exc:
            errors.append(str(exc))
            continue
        if path in seen:
            errors.append(f"duplicate source lock: {path}")
        seen.add(path)
        if not path.is_file():
            errors.append(f"locked source is missing: {path}")
        elif sha256(path) != item.get("sha256"):
            errors.append(f"locked source hash mismatch: {path}")

    image_lock = contract.get("r24_image_manifest")
    if not isinstance(image_lock, dict):
        errors.append("r24_image_manifest must be an object")
        image_lock = {}
    _exact_keys(image_lock, {"path", "sha256"}, "r24 image lock", errors)
    try:
        image_path = _resolve(contract_path, image_lock.get("path"))
        if image_path != DEFAULT_IMAGE_MANIFEST.resolve():
            errors.append("r24 image manifest path must be canonical")
        if not image_path.is_file():
            errors.append("r24 image manifest is missing")
        elif sha256(image_path) != image_lock.get("sha256"):
            errors.append("r24 image manifest hash mismatch")
    except PreflightError as exc:
        errors.append(str(exc))
    if contract.get("required_processes") != [
        "broker",
        "controller",
        "gateway",
        "gridlabd",
    ]:
        errors.append("direct required process list must be exact")
    outputs = contract.get("required_runtime_outputs")
    if outputs != [
        "controller_trace.json",
        "gateway_trace.json",
        "broker.log",
        "controller.log",
        "gateway.log",
        "gridlabd.log",
    ]:
        errors.append("direct runtime output list must be exact")
    return errors


def _copy_python_runtime(stage: Path) -> None:
    v3_root = Path(__file__).resolve().parents[1]
    python_root = stage / "python/v3"
    for package, names in {
        "cyber_gateway": (
            "__init__.py",
            "gateway.py",
            "dnp3_point_map.yaml",
        ),
        "natig_adapter": (
            "__init__.py",
            "dnp3_codec.py",
            "gateway_bridge.py",
            "run_offline_conformance.py",
        ),
        "opender": ("device.py",),
    }.items():
        target = python_root / package
        target.mkdir(parents=True)
        if package == "opender":
            (target / "__init__.py").write_text("", encoding="utf-8")
        for name in names:
            shutil.copy2(v3_root / package / name, target / name)
    (python_root / "__init__.py").write_text("", encoding="utf-8")


def stage_overlay(
    contract: dict[str, Any],
    contract_path: Path,
    output_dir: Path,
) -> Path:
    """Create a self-contained effective overlay in a new output directory."""
    output_dir.mkdir(parents=True, exist_ok=False)
    stage = output_dir / "effective"
    config_dir = stage / "config"
    model_dir = stage / "model"
    runtime_dir = stage / "runtime"
    runtime_output = stage / "runtime_output"
    for path in (config_dir, model_dir, runtime_dir, runtime_output):
        path.mkdir(parents=True)
    for name in ("controller.json", "gateway.json"):
        shutil.copy2(contract_path.parent / name, config_dir / name)
    overlay = contract["g3_physical_overlay"]
    shutil.copy2(
        _resolve(contract_path, overlay["gridlabd_config"]),
        model_dir / "mainglm.json",
    )
    shutil.copy2(
        _resolve(contract_path, overlay["model"]),
        model_dir / "1c_IEEE_123_feeder.glm",
    )
    shutil.copytree(
        _resolve(contract_path, overlay["support_tree"]),
        model_dir / "include",
    )
    (model_dir / "output").mkdir()
    for name in (
        "live_controller_federate.py",
        "live_gateway_federate.py",
    ):
        shutil.copy2(contract_path.parent / name, runtime_dir / name)
    _copy_python_runtime(stage)
    shutil.copy2(contract_path, stage / "federation_contract.json")
    return stage


def _attest_image(
    *,
    container: str,
    manifest: dict[str, Any],
    manifest_sha256: str,
) -> dict[str, Any]:
    commit = _run(
        [
            "docker",
            "exec",
            container,
            "git",
            "-C",
            manifest["natig_repo_path"],
            "rev-parse",
            "HEAD",
        ],
        check=True,
    ).stdout.strip()
    tree = _run(
        [
            "docker",
            "exec",
            container,
            "git",
            "-C",
            manifest["natig_repo_path"],
            "rev-parse",
            "HEAD^{tree}",
        ],
        check=True,
    ).stdout.strip()
    if commit != manifest["natig_commit"] or tree != manifest["natig_tree"]:
        raise PreflightError("embedded NATIG commit/tree mismatch")
    identity: dict[str, Any] = {
        "image_id": manifest["image_id"],
        "image_manifest_sha256": manifest_sha256,
        "execution_user": f"{os.getuid()}:{os.getgid()}",
        "natig_commit": commit,
        "natig_tree": tree,
    }
    for label, item in (
        ("binary", manifest["binary"]),
        ("source", manifest["source"]),
    ):
        actual = _container_hash(container, item["path"])
        if actual != item["sha256"]:
            raise PreflightError(f"embedded {label} hash mismatch")
        identity[f"{label}_sha256"] = actual
    for patch in manifest["patches"]:
        if _container_hash(container, patch["path"]) != patch["sha256"]:
            raise PreflightError(
                f"embedded patch hash mismatch: {patch['path']}"
            )
    python_runtime = manifest["python_runtime"]
    for field in (
        "helics_module",
        "opender_module",
        "numpy_module",
        "pandas_module",
    ):
        item = python_runtime[field]
        actual = _container_hash(container, item["path"])
        if actual != item["sha256"]:
            raise PreflightError(f"embedded Python {field} hash mismatch")
        identity[f"{field}_sha256"] = actual
    probe = (
        "import importlib.metadata,json,platform,helics;"
        "print(json.dumps({"
        "'python_version':platform.python_version(),"
        "'helics_version':importlib.metadata.version('helics'),"
        "'helics_native_version':str(helics.helicsGetVersion()),"
        "'opender_version':importlib.metadata.version('opender'),"
        "'numpy_version':importlib.metadata.version('numpy'),"
        "'pandas_version':importlib.metadata.version('pandas')"
        "},sort_keys=True))"
    )
    observed = json.loads(
        _run(
            [
                "docker",
                "exec",
                container,
                python_runtime["executable"],
                "-c",
                probe,
            ],
            check=True,
        ).stdout
    )
    expected = {
        "python_version": python_runtime["python_version"],
        "helics_version": python_runtime["helics_version"],
        "opender_version": python_runtime["opender_version"],
        "numpy_version": python_runtime["numpy_version"],
        "pandas_version": python_runtime["pandas_version"],
    }
    if {key: observed.get(key) for key in expected} != expected:
        raise PreflightError("embedded Python package version mismatch")
    if not str(observed.get("helics_native_version", "")).startswith(
        "2.7.1"
    ):
        raise PreflightError("embedded HELICS native version mismatch")
    identity.update(observed)
    if set(identity) != IDENTITY_KEYS:
        raise PreflightError("execution identity fields are incomplete")
    return identity


def execute_container(
    manifest: dict[str, Any],
    manifest_sha256: str,
    contract: dict[str, Any],
    output_dir: Path,
    timeout_s: int,
) -> dict[str, Any]:
    """Execute broker plus exactly three direct-reference federates."""
    observed_image = _run(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            "{{.Id}}",
            manifest["image_reference"],
        ],
        check=True,
    ).stdout.strip()
    if observed_image != manifest["image_id"]:
        raise PreflightError("Docker image ID differs from r24 manifest")
    if not SAFE_OUTPUT_NAME.fullmatch(output_dir.name):
        raise PreflightError("output basename is not container-name safe")
    container = f"grideval-g4-direct-{output_dir.name}"
    if _run(["docker", "container", "inspect", container]).returncode == 0:
        raise PreflightError(f"refusing existing container {container}")
    create = _run(
        [
            "docker",
            "create",
            "--name",
            container,
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "4096",
            "--memory",
            "16g",
            "--cpus",
            "4",
            manifest["image_id"],
            "sleep",
            "infinity",
        ],
        check=True,
    )
    runtime_dir = output_dir / "runtime_output"
    runtime_dir.mkdir()
    returncodes: dict[str, int] = {}
    handles: dict[str, tuple[subprocess.Popen[Any], Any]] = {}
    execution_user = f"{os.getuid()}:{os.getgid()}"
    try:
        _run(["docker", "start", container], check=True)
        _run(["docker", "exec", container, "mkdir", "-p", "/g4"], check=True)
        _run(
            [
                "docker",
                "cp",
                str(output_dir / "effective"),
                f"{container}:/g4/",
            ],
            timeout=300,
            check=True,
        )
        identity = _attest_image(
            container=container,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
        )
        python_runtime = manifest["python_runtime"]
        commands = {
            "broker": [
                "helics_broker",
                "--slowresponding",
                "--federates=3",
                "--port=9000",
                "--loglevel=warning",
            ],
            "controller": [
                python_runtime["executable"],
                "/g4/effective/runtime/live_controller_federate.py",
                "--config",
                "/g4/effective/config/controller.json",
                "--trace",
                "/g4/effective/runtime_output/controller_trace.json",
            ],
            "gateway": [
                python_runtime["executable"],
                "/g4/effective/runtime/live_gateway_federate.py",
                "--config",
                "/g4/effective/config/gateway.json",
                "--trace",
                "/g4/effective/runtime_output/gateway_trace.json",
            ],
            "gridlabd": [
                "gridlabd",
                "/g4/effective/model/1c_IEEE_123_feeder.glm",
            ],
        }
        process_cwds = {
            "broker": "/g4/effective",
            "controller": "/g4/effective",
            "gateway": "/g4/effective",
            "gridlabd": "/g4/effective/model",
        }
        for process in contract["required_processes"]:
            log = (runtime_dir / f"{process}.log").open(
                "w", encoding="utf-8"
            )
            argv = [
                "docker",
                "exec",
                "--user",
                execution_user,
                "-e",
                "HELICS_BROKER=tcp://127.0.0.1:9000",
                "-e",
                "PYTHONPATH=/g4/effective/python",
                "-w",
                process_cwds[process],
                container,
                *commands[process],
            ]
            handles[process] = (
                subprocess.Popen(
                    argv,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                ),
                log,
            )
            if process == "broker":
                time.sleep(0.5)
        deadline = time.monotonic() + timeout_s
        while any(handle.poll() is None for handle, _ in handles.values()):
            if time.monotonic() >= deadline:
                raise PreflightError("live direct federation process timeout")
            time.sleep(0.25)
        for process, (handle, log) in handles.items():
            returncodes[process] = int(handle.returncode)
            log.close()
        _run(
            [
                "docker",
                "cp",
                f"{container}:/g4/effective/runtime_output/.",
                str(runtime_dir),
            ],
            timeout=300,
            check=True,
        )
        errors = validate_runtime_result(
            returncodes,
            runtime_dir,
            contract["required_processes"],
            contract["required_runtime_outputs"],
        )
        if errors:
            raise PreflightError("; ".join(errors))
        result = {
            "status": "PASS",
            "create_returncode": create.returncode,
            "identity": identity,
            "returncodes": returncodes,
            "runtime_inventory": inventory(runtime_dir),
        }
        if set(result) != {
            "status",
            "create_returncode",
            "identity",
            "returncodes",
            "runtime_inventory",
        }:
            raise PreflightError("execution result fields are incomplete")
        return result
    finally:
        for handle, log in handles.values():
            if handle.poll() is None:
                handle.terminate()
            if not log.closed:
                log.close()
        _run(["docker", "rm", "-f", container], timeout=60)


def prepare(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    output_dir: Path,
    image_manifest_path: Path = DEFAULT_IMAGE_MANIFEST,
    execute: bool = False,
    timeout_s: int = 1800,
) -> dict[str, Any]:
    """Validate and stage the direct arm, then execute only when requested."""
    contract_path = contract_path.resolve()
    output_dir = output_dir.resolve()
    image_manifest_path = image_manifest_path.resolve()
    contract = load_json(contract_path)
    errors = validate_contract(contract, contract_path)
    if errors:
        raise PreflightError(
            "static preflight failed:\n- " + "\n- ".join(errors)
        )
    if output_dir.exists():
        raise FileExistsError(
            f"create-once output already exists: {output_dir}"
        )
    canonical_manifest = _resolve(
        contract_path, contract["r24_image_manifest"]["path"]
    )
    if image_manifest_path != canonical_manifest:
        raise PreflightError("only the immutable r24-derived manifest is allowed")
    manifest_sha256 = sha256(image_manifest_path)
    if manifest_sha256 != contract["r24_image_manifest"]["sha256"]:
        raise PreflightError("r24 image manifest hash mismatch")
    manifest = load_json(image_manifest_path)
    image_errors = validate_image_manifest(
        manifest, contract["external_image_gate"]
    )
    if image_errors:
        raise PreflightError(
            "execution image is invalid: " + "; ".join(image_errors)
        )

    stage = stage_overlay(contract, contract_path, output_dir)
    retained_manifest = output_dir / "live_image_manifest.json"
    shutil.copy2(image_manifest_path, retained_manifest)
    if sha256(retained_manifest) != manifest_sha256:
        raise PreflightError("retained image manifest hash mismatch")
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "scope": contract["scope"],
        "mode": "execute" if execute else "dry_run",
        "static_preflight": "PASS",
        "image_preflight": "READY",
        "image_errors": [],
        "image_evidence": {
            "path": retained_manifest.name,
            "sha256": manifest_sha256,
            "image_id": manifest["image_id"],
        },
        "execution_attempted": execute,
        "execution_result": None,
        "claims_permitted": (
            ["configuration_preflight"]
            if not execute
            else ["configuration_preflight", "live_direct_execution"]
        ),
        "equivalence_claim_permitted": False,
        "seed": contract["seed"],
        "federate_count": 3,
        "cyber_endpoint_count": 2,
        "cyber_route_count": 2,
        "physical_value_link_count": 2,
        "gridlabd_message_endpoint_count": 0,
        "attacker_process_count": 0,
        "network_impairment_count": 0,
        "effective_inventory": inventory(stage),
    }
    if execute:
        result["execution_result"] = execute_container(
            manifest,
            manifest_sha256,
            contract,
            output_dir,
            timeout_s,
        )
    (output_dir / "live_direct_preflight.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--image-manifest", type=Path, default=DEFAULT_IMAGE_MANIFEST
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-s", type=int, default=1800)
    args = parser.parse_args()
    if args.timeout_s <= 0:
        raise ValueError("timeout-s must be positive")
    result = prepare(
        contract_path=args.contract,
        output_dir=args.output_dir,
        image_manifest_path=args.image_manifest,
        execute=args.execute,
        timeout_s=args.timeout_s,
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "mode",
                    "static_preflight",
                    "image_preflight",
                    "execution_attempted",
                    "federate_count",
                    "cyber_endpoint_count",
                    "cyber_route_count",
                    "physical_value_link_count",
                    "gridlabd_message_endpoint_count",
                    "attacker_process_count",
                    "network_impairment_count",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
