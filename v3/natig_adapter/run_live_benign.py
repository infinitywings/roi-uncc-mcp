#!/usr/bin/env python3
"""Stage, preflight, and optionally execute the G4 benign federation.

Dry-run is the default. It performs every repository/configuration check,
creates an immutable staged overlay, and records BLOCKED_IMAGE_NOT_READY when
no external patched-image manifest is supplied. ``--execute`` additionally
requires a complete image manifest and verifies its identities in-container
before launching any federate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v3.natig_adapter.validate_endpoint_graph import (
    EXPECTED_EDGES,
    EXPECTED_ENDPOINTS,
    EXPECTED_PHYSICAL_LINKS,
    validate_endpoint_graph,
)


LIVE_DIR = Path(__file__).with_name("live_benign")
DEFAULT_CONTRACT = LIVE_DIR / "federation_contract.json"
EXPECTED_FEDERATES = {
    "controller": ("g4_controller_der_ev4", "controller.json"),
    "natig": ("g4_natig_der_ev4", "natig.json"),
    "gateway": ("g4_gateway_der_ev4", "gateway.json"),
    "gridlabd": ("g4_gridlabd_der_ev4", "gridlabd.json"),
}
EXPECTED_ENDPOINT_OWNERS = {
    endpoint: owner
    for endpoint, (owner, _function) in EXPECTED_ENDPOINTS.items()
}
IMAGE_MANIFEST_KEYS = {
    "schema_version",
    "ready",
    "image_reference",
    "image_id",
    "platform",
    "natig_repo_path",
    "natig_commit",
    "natig_tree",
    "patch_set",
    "patches",
    "binary",
    "source",
    "python_runtime",
    "runtime_command",
}
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
SAFE_OUTPUT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}")


class PreflightError(RuntimeError):
    """A fail-closed preflight invariant did not hold."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        result = json.load(handle)
    if not isinstance(result, dict):
        raise PreflightError(f"{path}: JSON root must be an object")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


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


def validate_image_manifest(
    manifest: dict[str, Any],
    image_gate: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    _exact_keys(
        manifest, IMAGE_MANIFEST_KEYS, "image manifest", errors
    )
    if manifest.get("schema_version") != image_gate.get("schema_version"):
        errors.append("image manifest schema_version mismatch")
    if manifest.get("ready") is not True:
        errors.append("patched image manifest must explicitly set ready=true")
    if (
        not isinstance(manifest.get("image_reference"), str)
        or not manifest["image_reference"]
    ):
        errors.append("image_reference must be a non-empty string")
    if not isinstance(manifest.get("image_id"), str) or not IMAGE_ID.fullmatch(
        manifest["image_id"]
    ):
        errors.append("image_id must be an immutable sha256 image ID")
    if manifest.get("platform") != "linux/amd64":
        errors.append("patched image platform must be linux/amd64")
    if (
        not isinstance(manifest.get("natig_repo_path"), str)
        or not manifest["natig_repo_path"].startswith("/")
    ):
        errors.append("natig_repo_path must be an absolute container path")
    if manifest.get("natig_commit") != image_gate.get(
        "required_natig_commit"
    ):
        errors.append("NATIG commit does not match the G4 lock")
    if manifest.get("natig_tree") != image_gate.get("required_natig_tree"):
        errors.append("NATIG tree does not match the G4 lock")
    if manifest.get("patch_set") != image_gate.get("required_patch_set"):
        errors.append("image patch_set does not match the G4 contract")

    patches = manifest.get("patches")
    if not isinstance(patches, list) or not patches:
        errors.append("patches must be a non-empty list")
    else:
        seen_paths = set()
        for index, patch in enumerate(patches):
            label = f"patches[{index}]"
            if not isinstance(patch, dict):
                errors.append(f"{label} must be an object")
                continue
            _exact_keys(patch, {"path", "sha256"}, label, errors)
            path = patch.get("path")
            if not isinstance(path, str) or not path.startswith("/"):
                errors.append(f"{label}.path must be absolute")
            elif path in seen_paths:
                errors.append(f"{label}.path must be unique")
            else:
                seen_paths.add(path)
            if not isinstance(patch.get("sha256"), str) or not HEX64.fullmatch(
                patch["sha256"]
            ):
                errors.append(f"{label}.sha256 must be 64 lowercase hex")

    for field in ("binary", "source"):
        item = manifest.get(field)
        if not isinstance(item, dict):
            errors.append(f"{field} must be an object")
            continue
        _exact_keys(item, {"path", "sha256"}, field, errors)
        if (
            not isinstance(item.get("path"), str)
            or not item["path"].startswith("/")
        ):
            errors.append(f"{field}.path must be absolute")
        if not isinstance(item.get("sha256"), str) or not HEX64.fullmatch(
            item["sha256"]
        ):
            errors.append(f"{field}.sha256 must be 64 lowercase hex")

    python_runtime = manifest.get("python_runtime")
    expected_python_keys = {
        "executable",
        "python_version",
        "helics_version",
        "helics_module",
        "opender_version",
        "opender_module",
        "numpy_version",
        "numpy_module",
        "pandas_version",
        "pandas_module",
    }
    if not isinstance(python_runtime, dict):
        errors.append("python_runtime must be an object")
    else:
        _exact_keys(
            python_runtime,
            expected_python_keys,
            "python_runtime",
            errors,
        )
        if (
            not isinstance(python_runtime.get("executable"), str)
            or not python_runtime["executable"].startswith("/")
        ):
            errors.append("python_runtime.executable must be absolute")
        if python_runtime.get("python_version") != "3.9.2":
            errors.append("image Python runtime must exactly equal 3.9.2")
        if python_runtime.get("helics_version") != "2.7.1":
            errors.append("image Python HELICS bindings must equal 2.7.1")
        if python_runtime.get("opender_version") != "2.2.0":
            errors.append("image OpenDER package must equal 2.2.0")
        if python_runtime.get("numpy_version") != "2.0.2":
            errors.append("image NumPy package must equal 2.0.2")
        if python_runtime.get("pandas_version") != "2.2.3":
            errors.append("image pandas package must equal 2.2.3")
        for field in (
            "helics_module",
            "opender_module",
            "numpy_module",
            "pandas_module",
        ):
            module = python_runtime.get(field)
            if not isinstance(module, dict):
                errors.append(f"python_runtime.{field} must be an object")
                continue
            _exact_keys(
                module, {"path", "sha256"}, f"python_runtime.{field}", errors
            )
            if (
                not isinstance(module.get("path"), str)
                or not module["path"].startswith("/")
            ):
                errors.append(
                    f"python_runtime.{field}.path must be absolute"
                )
            if not isinstance(module.get("sha256"), str) or not HEX64.fullmatch(
                module["sha256"]
            ):
                errors.append(
                    f"python_runtime.{field}.sha256 must be 64 lowercase hex"
                )

    runtime = manifest.get("runtime_command")
    if (
        not isinstance(runtime, list)
        or not runtime
        or not all(isinstance(item, str) and item for item in runtime)
    ):
        errors.append("runtime_command must be a non-empty argv list")
    elif not runtime[0].startswith("/"):
        errors.append("runtime_command executable must be an absolute path")
    elif runtime[0] != manifest.get("binary", {}).get("path"):
        errors.append(
            "runtime_command executable must exactly equal the hashed "
            "binary.path"
        )
    else:
        expected_runtime = [
            runtime[0],
            "--RngRun=1",
            "--helicsConfig=/g4/effective/config/natig.json",
            "--microGridConfig=/g4/effective/config/microgrid.json",
            "--topologyConfig=/g4/effective/config/topology.json",
            "--pointFileDir=/g4/effective/config",
            "--pcapFileDir=/g4/effective/runtime_output/pcap/",
        ]
        if runtime != expected_runtime:
            errors.append(
                "runtime_command must pass the exact locked NATIG fixtures"
            )
    return errors


def validate_contract(
    contract: dict[str, Any], contract_path: Path
) -> list[str]:
    """Return all deterministic static preflight errors."""

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
        "runtime_paths",
        "required_processes",
        "required_runtime_outputs",
    }
    _exact_keys(contract, required_root, "contract", errors)
    if contract.get("schema_version") != "1.0":
        errors.append("contract schema_version must equal 1.0")
    if contract.get("seed") != 777:
        errors.append("NATIG network seed must equal 777")

    simulation = contract.get("simulation")
    expected_simulation = {
        "duration_s": 840,
        "controller_period_s": 10,
        "dnp3_poll_period_s": 10,
        "physical_coupling_period_s": 10,
        "opender_internal_step_s": 1,
    }
    if simulation != expected_simulation:
        errors.append("simulation timing must exactly reuse the G3/G4 freeze")
    broker = contract.get("broker")
    if broker != {
        "core_type": "zmq",
        "port": 9000,
        "federate_count": 4,
    }:
        errors.append("broker contract must require exactly four federates")

    federates = contract.get("federates")
    actual_federates: dict[str, tuple[Any, Any]] = {}
    if not isinstance(federates, list):
        errors.append("federates must be a list")
        federates = []
    for index, item in enumerate(federates):
        if not isinstance(item, dict):
            errors.append(f"federates[{index}] must be an object")
            continue
        _exact_keys(
            item, {"owner", "name", "config"}, f"federates[{index}]", errors
        )
        owner = item.get("owner")
        if not isinstance(owner, str) or owner in actual_federates:
            errors.append(f"federates[{index}].owner must be unique")
            continue
        actual_federates[owner] = (item.get("name"), item.get("config"))
    if actual_federates != EXPECTED_FEDERATES:
        errors.append("federate owners, names, and config files must be exact")
    if len(federates) != 4:
        errors.append("exactly four federate declarations are required")

    routes = contract.get("cyber_routes")
    actual_routes = set()
    if not isinstance(routes, list):
        errors.append("cyber_routes must be a list")
        routes = []
    for item in routes:
        if isinstance(item, dict):
            actual_routes.add(
                (
                    item.get("stream"),
                    item.get("stage"),
                    item.get("source"),
                    item.get("destination"),
                    item.get("transport"),
                )
            )
    if actual_routes != EXPECTED_EDGES or len(routes) != len(EXPECTED_EDGES):
        errors.append("cyber route set must exactly match endpoint_graph.json")

    physical = contract.get("physical_values")
    actual_physical = set()
    if not isinstance(physical, list):
        errors.append("physical_values must be a list")
        physical = []
    for item in physical:
        if isinstance(item, dict):
            actual_physical.add(
                (
                    item.get("key"),
                    item.get("publisher"),
                    item.get("subscriber"),
                    item.get("type"),
                    item.get("unit"),
                )
            )
    if (
        actual_physical != EXPECTED_PHYSICAL_LINKS
        or len(physical) != len(EXPECTED_PHYSICAL_LINKS)
    ):
        errors.append("physical HELICS-value set must contain exactly two links")
    if contract.get("security_condition") != {
        "name": "benign",
        "attacker_processes": [],
        "network_impairments": [],
    }:
        errors.append("security condition must be benign with no attacker/impairment")

    overlay = contract.get("g3_physical_overlay")
    if not isinstance(overlay, dict):
        errors.append("g3_physical_overlay must be an object")
        overlay = {}
    expected_overlay_fields = {
        "model",
        "model_sha256",
        "support_tree",
        "support_tree_sha256",
        "coupling_object",
        "parent_bus",
        "minimum_timestep_s",
    }
    _exact_keys(overlay, expected_overlay_fields, "g3_physical_overlay", errors)
    if (
        overlay.get("coupling_object") != "DER_EV4_BESS_COUPLING"
        or overlay.get("parent_bus") != "l92"
        or overlay.get("minimum_timestep_s") != 10
    ):
        errors.append("G3 physical overlay identity must remain l92/10-second")
    try:
        model = _resolve(contract_path, overlay.get("model"))
        if not model.is_file():
            errors.append(f"canonical G3 model is missing: {model}")
        elif sha256(model) != overlay.get("model_sha256"):
            errors.append("canonical G3 model hash mismatch")
        else:
            model_text = model.read_text(encoding="utf-8")
            for required in (
                "#set minimum_timestep=10.000000;",
                "#set randomseed=10;",
                "name DER_EV4_BESS_COUPLING;",
                "parent l92;",
                "configure mainglm.json;",
            ):
                if required not in model_text:
                    errors.append(
                        f"canonical G3 model is missing freeze token {required!r}"
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

    locks = contract.get("source_locks")
    if not isinstance(locks, list) or not locks:
        errors.append("source_locks must be a non-empty list")
        locks = []
    seen_locks = set()
    for index, lock in enumerate(locks):
        if not isinstance(lock, dict):
            errors.append(f"source_locks[{index}] must be an object")
            continue
        _exact_keys(lock, {"path", "sha256"}, f"source_locks[{index}]", errors)
        try:
            path = _resolve(contract_path, lock.get("path"))
        except PreflightError as exc:
            errors.append(str(exc))
            continue
        if path in seen_locks:
            errors.append(f"duplicate source lock: {path}")
        seen_locks.add(path)
        if not path.is_file():
            errors.append(f"locked source is missing: {path}")
        elif sha256(path) != lock.get("sha256"):
            errors.append(f"locked source hash mismatch: {path}")

    endpoint_path = (contract_path.parent / "../endpoint_graph.json").resolve()
    if endpoint_path.is_file():
        endpoint_errors = validate_endpoint_graph(load_json(endpoint_path))
        errors.extend(f"endpoint graph: {item}" for item in endpoint_errors)

    declared_endpoints: dict[str, str] = {}
    config_by_owner: dict[str, dict[str, Any]] = {}
    for owner, (_name, filename) in EXPECTED_FEDERATES.items():
        path = contract_path.parent / filename
        if not path.is_file():
            errors.append(f"missing federate config: {path}")
            continue
        config = load_json(path)
        config_by_owner[owner] = config
        if config.get("name") != EXPECTED_FEDERATES[owner][0]:
            errors.append(f"{filename}: federate name mismatch")
        endpoints = config.get("endpoints")
        if not isinstance(endpoints, list):
            errors.append(f"{filename}: endpoints must be a list")
            continue
        if owner == "gridlabd" and endpoints:
            errors.append("GridLAB-D must declare zero message endpoints")
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                errors.append(f"{filename}: endpoint must be an object")
                continue
            name = endpoint.get("name")
            if name in declared_endpoints:
                errors.append(f"duplicate endpoint declaration: {name}")
            elif isinstance(name, str):
                declared_endpoints[name] = owner
            if endpoint.get("global") is not True:
                errors.append(f"{filename}: every cyber endpoint must be global")
    if declared_endpoints != EXPECTED_ENDPOINT_OWNERS:
        errors.append("federate configs must declare exactly four cyber endpoints")

    gridlabd = config_by_owner.get("gridlabd", {})
    gateway = config_by_owner.get("gateway", {})
    natig = config_by_owner.get("natig", {})
    if gridlabd.get("period") != 10 or gateway.get("period") != 10:
        errors.append("GridLAB-D and gateway periods must both equal 10 seconds")
    if natig.get("seed") != 777:
        errors.append("NATIG config seed must equal 777")
    if natig.get("attacker") is not None or natig.get(
        "network_impairment"
    ) is not None:
        errors.append("NATIG config must contain no attacker or impairment")
    if natig.get("dnp3", {}).get("poll_period_s") != 10:
        errors.append("NATIG DNP3 poll period must equal 10 seconds")
    if natig.get("brokerPort") != 9000:
        errors.append("NATIG C++ brokerPort must equal 9000")

    microgrid_path = contract_path.parent / "microgrid.json"
    topology_path = contract_path.parent / "topology.json"
    points_path = contract_path.parent / "points_der_ev4.csv"
    try:
        microgrid = load_json(microgrid_path)
        topology = load_json(topology_path)
    except (FileNotFoundError, json.JSONDecodeError, PreflightError) as exc:
        errors.append(f"NATIG runtime fixture is unreadable: {exc}")
        microgrid = {}
        topology = {}
    expected_microgrid = {
        "Simulation": [
            {
                "SimTime": 840,
                "StartTime": 0.0,
                "PollReqFreq": 10,
                "includeMIM": 0,
                "UseDynTop": 0,
                "MonitorPerf": 0,
                "StaticSeed": 1,
                "RandomSeed": 777,
            }
        ],
        "microgrid": [{"name": "der_ev4"}],
        "controlCenter": {"name": "cc_"},
        "Controller": [{"use": 0, "actionFile": ""}],
        "DDoS": [
            {
                "Rate": "1kb/s",
                "PacketSize": 64,
                "NumberOfBots": 0,
                "threadsPerAttacker": 1,
                "Active": 0,
                "usePing": 0,
                "Start": 0,
                "End": 0,
                "TimeOn": 0.0,
                "TimeOff": 1.0,
                "NodeType": [],
                "NodeID": [],
                "endPoint": "",
            }
        ],
        "MIM": [{"listMIM": ""}],
    }
    expected_topology = {
        "Channel": [
            {
                "P2PRate": "60Mb/s",
                "CSMAdelay": 0,
                "jitterMin": 0,
                "jitterMax": 0,
                "delay": 0,
            }
        ],
        "Gridlayout": [
            {
                "MinX": 0,
                "MinY": 0,
                "DeltaX": 10,
                "DeltaY": 10,
                "GridWidth": 2,
                "GridLayout": 2,
                "LayoutType": "RowFirst",
            }
        ],
    }
    if microgrid != expected_microgrid:
        errors.append("NATIG one-DER microgrid fixture must be exact")
    if topology != expected_topology:
        errors.append("NATIG one-DER topology fixture must be exact")
    expected_points = (
        "ANALOG,DER_EV4_BESS.P_APPLIED_KW,0\n"
        "ANALOG,DER_EV4_BESS.Q_APPLIED_KVAR,0\n"
        "ANALOG,DER_EV4_BESS.V_PU,0\n"
        "ANALOG,DER_EV4_BESS.SOC_PU,0\n"
        "BINARY,DER_EV4_BESS.CONNECTED,1\n"
        "BINARY,DER_EV4_BESS.COMMAND_ACCEPTED,0\n"
    )
    if (
        not points_path.is_file()
        or points_path.read_text(encoding="utf-8") != expected_points
    ):
        errors.append("NATIG DER_EV4 point CSV must be exact")

    grid_publications = {
        (
            item.get("key"),
            item.get("type"),
            item.get("unit"),
        )
        for item in gridlabd.get("publications", [])
        if isinstance(item, dict)
    }
    grid_subscriptions = {
        (
            item.get("key"),
            item.get("type"),
            item.get("unit"),
        )
        for item in gridlabd.get("subscriptions", [])
        if isinstance(item, dict)
    }
    gateway_publications = {
        (item.get("key"), item.get("type"), item.get("unit"))
        for item in gateway.get("publications", [])
        if isinstance(item, dict)
    }
    gateway_subscriptions = {
        (item.get("key"), item.get("type"), item.get("unit"))
        for item in gateway.get("subscriptions", [])
        if isinstance(item, dict)
    }
    if grid_publications != {("gridlabd/ev4_voltage_c", "complex", "V")}:
        errors.append("GridLAB-D must publish only EV4 terminal voltage")
    if grid_subscriptions != {("gateway/feeder_load_va", "complex", "VA")}:
        errors.append("GridLAB-D must subscribe only to gateway feeder load")
    if gateway_publications != {("gateway/feeder_load_va", "complex", "VA")}:
        errors.append("gateway must publish only feeder load")
    if gateway_subscriptions != {("gridlabd/ev4_voltage_c", "complex", "V")}:
        errors.append("gateway must subscribe only to EV4 terminal voltage")

    if contract.get("required_processes") != [
        "broker",
        "controller",
        "natig",
        "gateway",
        "gridlabd",
    ]:
        errors.append("required process list must be exact")
    outputs = contract.get("required_runtime_outputs")
    if (
        not isinstance(outputs, list)
        or len(outputs) != len(set(outputs))
        or not all(isinstance(item, str) and item for item in outputs)
    ):
        errors.append("required runtime outputs must be unique filenames")
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
    """Create a new, self-contained effective overlay directory."""

    output_dir.mkdir(parents=True, exist_ok=False)
    stage = output_dir / "effective"
    config_dir = stage / "config"
    model_dir = stage / "model"
    runtime_dir = stage / "runtime"
    runtime_output = stage / "runtime_output"
    for path in (config_dir, model_dir, runtime_dir, runtime_output):
        path.mkdir(parents=True)
    (runtime_output / "pcap").mkdir()

    for owner, (_name, filename) in EXPECTED_FEDERATES.items():
        source = contract_path.parent / filename
        target = (
            model_dir / "mainglm.json"
            if owner == "gridlabd"
            else config_dir / filename
        )
        shutil.copy2(source, target)
    for filename in ("microgrid.json", "topology.json", "points_der_ev4.csv"):
        shutil.copy2(contract_path.parent / filename, config_dir / filename)
    overlay = contract["g3_physical_overlay"]
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


def inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(root)),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def validate_runtime_result(
    returncodes: dict[str, int],
    runtime_output: Path,
    required_processes: list[str],
    required_outputs: list[str],
) -> list[str]:
    errors = []
    if set(returncodes) != set(required_processes):
        errors.append("process return-code set is incomplete or has extras")
    for process in required_processes:
        if returncodes.get(process) != 0:
            errors.append(
                f"process {process} return code is "
                f"{returncodes.get(process)!r}, expected 0"
            )
    for filename in required_outputs:
        path = runtime_output / filename
        if not path.is_file():
            errors.append(f"required runtime output missing: {filename}")
        elif filename != "broker.log" and path.stat().st_size == 0:
            errors.append(f"required runtime output missing/empty: {filename}")
    return errors


def _run(
    argv: list[str],
    *,
    timeout: int = 60,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise PreflightError(
            f"command failed ({result.returncode}): {argv!r}\n{result.stdout}"
        )
    return result


def _container_hash(container: str, path: str) -> str:
    result = _run(
        ["docker", "exec", container, "sha256sum", path],
        check=True,
    )
    value = result.stdout.split()[0] if result.stdout.split() else ""
    if not HEX64.fullmatch(value):
        raise PreflightError(f"invalid in-container sha256 output for {path}")
    return value


def execute_container(
    manifest: dict[str, Any],
    manifest_sha256: str,
    contract: dict[str, Any],
    output_dir: Path,
    timeout_s: int,
) -> dict[str, Any]:
    """Execute all five processes in one isolated patched container."""

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
        raise PreflightError("Docker image ID differs from image manifest")
    container = f"grideval-g4-{output_dir.name}"
    if not SAFE_OUTPUT_NAME.fullmatch(output_dir.name):
        raise PreflightError("output basename is not container-name safe")
    existing = _run(["docker", "container", "inspect", container])
    if existing.returncode == 0:
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
    identity: dict[str, Any] = {
        "image_id": observed_image,
        "image_manifest_sha256": manifest_sha256,
    }
    execution_user = f"{os.getuid()}:{os.getgid()}"
    identity["execution_user"] = execution_user
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
        identity["natig_commit"] = commit
        identity["natig_tree"] = tree
        for label, item in (
            ("binary", manifest["binary"]),
            ("source", manifest["source"]),
        ):
            actual = _container_hash(container, item["path"])
            if actual != item["sha256"]:
                raise PreflightError(f"embedded {label} hash mismatch")
            identity[f"{label}_sha256"] = actual
        for patch in manifest["patches"]:
            actual = _container_hash(container, patch["path"])
            if actual != patch["sha256"]:
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
                raise PreflightError(
                    f"embedded Python {field} hash mismatch"
                )
            identity[f"{field}_sha256"] = actual
        package_probe = (
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
        probed = json.loads(
            _run(
                [
                    "docker",
                    "exec",
                    container,
                    python_runtime["executable"],
                    "-c",
                    package_probe,
                ],
                check=True,
            ).stdout
        )
        expected_probe = {
            "python_version": python_runtime["python_version"],
            "helics_version": python_runtime["helics_version"],
            "opender_version": python_runtime["opender_version"],
            "numpy_version": python_runtime["numpy_version"],
            "pandas_version": python_runtime["pandas_version"],
        }
        if {
            key: probed.get(key) for key in expected_probe
        } != expected_probe:
            raise PreflightError("embedded Python package version mismatch")
        if not str(probed.get("helics_native_version", "")).startswith(
            "2.7.1"
        ):
            raise PreflightError("embedded HELICS native version mismatch")
        identity.update(probed)

        commands = {
            "broker": [
                "helics_broker",
                "--slowresponding",
                "--federates=4",
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
            "natig": manifest["runtime_command"],
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
            "natig": "/g4/effective",
            "gateway": "/g4/effective",
            "gridlabd": "/g4/effective/model",
        }
        handles: dict[str, tuple[subprocess.Popen[Any], Any]] = {}
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
        while any(handle.poll() is None for handle, _log in handles.values()):
            if time.monotonic() >= deadline:
                raise PreflightError("live federation process timeout")
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
        runtime_errors = validate_runtime_result(
            returncodes,
            runtime_dir,
            contract["required_processes"],
            contract["required_runtime_outputs"],
        )
        if runtime_errors:
            raise PreflightError("; ".join(runtime_errors))
        return {
            "status": "PASS",
            "create_returncode": create.returncode,
            "identity": identity,
            "returncodes": returncodes,
            "runtime_inventory": inventory(runtime_dir),
        }
    finally:
        for name, value in list(locals().get("handles", {}).items()):
            handle, log = value
            if handle.poll() is None:
                handle.terminate()
            if not log.closed:
                log.close()
        _run(["docker", "rm", "-f", container], timeout=60)


def prepare(
    *,
    contract_path: Path,
    output_dir: Path,
    image_manifest_path: Path | None = None,
    execute: bool = False,
    timeout_s: int = 1800,
) -> dict[str, Any]:
    contract_path = contract_path.resolve()
    output_dir = output_dir.resolve()
    contract = load_json(contract_path)
    static_errors = validate_contract(contract, contract_path)
    if static_errors:
        raise PreflightError(
            "static preflight failed:\n- " + "\n- ".join(static_errors)
        )
    if output_dir.exists():
        raise FileExistsError(
            f"create-once output already exists: {output_dir}"
        )

    manifest = None
    image_manifest_path_resolved: Path | None = None
    image_manifest_sha256: str | None = None
    image_errors: list[str] = []
    if image_manifest_path is None:
        image_status = "BLOCKED_IMAGE_NOT_READY"
    else:
        image_manifest_path_resolved = image_manifest_path.resolve()
        manifest = load_json(image_manifest_path_resolved)
        image_manifest_sha256 = sha256(image_manifest_path_resolved)
        image_errors = validate_image_manifest(
            manifest, contract["external_image_gate"]
        )
        image_status = (
            "READY" if not image_errors else "BLOCKED_IMAGE_INVALID"
        )
    if execute and image_status != "READY":
        raise PreflightError(
            f"execution forbidden: {image_status}; "
            + "; ".join(image_errors)
        )

    stage = stage_overlay(contract, contract_path, output_dir)
    image_evidence = None
    if manifest is not None:
        assert image_manifest_path_resolved is not None
        assert image_manifest_sha256 is not None
        retained_manifest = output_dir / "live_image_manifest.json"
        shutil.copy2(image_manifest_path_resolved, retained_manifest)
        if sha256(retained_manifest) != image_manifest_sha256:
            raise PreflightError("retained image manifest hash mismatch")
        image_evidence = {
            "path": retained_manifest.name,
            "sha256": image_manifest_sha256,
            "image_id": manifest["image_id"],
        }
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "scope": contract["scope"],
        "mode": "execute" if execute else "dry_run",
        "static_preflight": "PASS",
        "image_preflight": image_status,
        "image_errors": image_errors,
        "image_evidence": image_evidence,
        "execution_attempted": execute,
        "execution_result": None,
        "claims_permitted": (
            ["configuration_preflight"]
            if not execute
            else ["configuration_preflight", "live_benign_execution"]
        ),
        "equivalence_claim_permitted": False,
        "seed": contract["seed"],
        "federate_count": contract["broker"]["federate_count"],
        "cyber_endpoint_count": len(EXPECTED_ENDPOINTS),
        "cyber_route_count": len(EXPECTED_EDGES),
        "physical_value_link_count": len(EXPECTED_PHYSICAL_LINKS),
        "gridlabd_message_endpoint_count": 0,
        "attacker_process_count": 0,
        "network_impairment_count": 0,
        "effective_inventory": inventory(stage),
    }
    if execute:
        assert manifest is not None
        assert image_manifest_sha256 is not None
        result["execution_result"] = execute_container(
            manifest,
            image_manifest_sha256,
            contract,
            output_dir,
            timeout_s,
        )
    (output_dir / "live_benign_preflight.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract", type=Path, default=DEFAULT_CONTRACT
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--image-manifest", type=Path)
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
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
