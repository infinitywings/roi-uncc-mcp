#!/usr/bin/env python3
"""Normalize one completed independent direct-control run for the G4 gate.

This is an evidence transformation only.  It launches no process and makes no
equivalence claim.  It fails closed unless the retained live bundle proves an
exact benign schedule, successful direct semantic-command delivery, eighteen
OpenDER applications, and all 84 physical samples.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v3.natig_adapter.analyze_live_equivalence import (
    EXPECTED_COMMANDS,
    EXPECTED_SAMPLE_TIMES,
    TRACE_SCHEMA,
    validate_execution,
)
from v3.natig_adapter.normalize_natig_live_reference import (
    APPLIED_KEYS,
    DURATION_S,
    EXPECTED_WINDOWS,
    GATEWAY_STEP_KEYS,
    GATEWAY_TELEMETRY_KEYS,
    IDENTITY_KEYS,
    NOMINAL_VOLTAGE_V,
    SEMANTIC_KEYS,
    SEMANTIC_PAYLOAD_KEYS,
)


EXPECTED_PROCESSES = {"broker", "controller", "gateway", "gridlabd"}
EXPECTED_RUNTIME_OUTPUTS = {
    "broker.log",
    "controller.log",
    "controller_trace.json",
    "gateway.log",
    "gateway_trace.json",
    "gridlabd.log",
}
R24_IDENTITY = {
    "image_id": (
        "sha256:85b09515ed5cabbbf5360ab73d91a7ce5c34e38db062f9071a4005a95042b40d"
    ),
    "image_manifest_sha256": (
        "1d26c9f1ccf853c9a3ff0f6db7ef7f8077a6becb0caff4023284cd483f8b3e24"
    ),
    "natig_commit": "e163b350e243c6386477e35dead979a4cb2b7c60",
    "natig_tree": "9f10cb55d5eaa4c20a95f292b84a266e9992bc1a",
    "binary_sha256": (
        "8e56ea1dc177213f9a6d1b076ecb4446b9be4c4fae8e477535823185805bb32b"
    ),
    "source_sha256": (
        "18e5869c46e6c711b7e4f5c830455ad7d6a8456cca535a5be1f126ad575398a2"
    ),
    "helics_module_sha256": (
        "14082a5e16c4977873d7bcd6a8978bcb010f19241d172a4f902797fd76b71192"
    ),
    "opender_module_sha256": (
        "3d88c9379f9ac2e67c0f92b21103b51a41d9121672bb81357d0b2471891cb7ff"
    ),
    "numpy_module_sha256": (
        "c09e25b58f6b2f8e2cb3c158168f902d447f8171e5ea6513c0aca41ecbda7c2b"
    ),
    "pandas_module_sha256": (
        "108be8ca3ae1a2a5c765ee6f87e8867d87c2fb5a89107e6c2d3a6acc96612b7b"
    ),
    "python_version": "3.9.2",
    "helics_version": "2.7.1",
    "opender_version": "2.2.0",
    "numpy_version": "2.0.2",
    "pandas_version": "2.2.3",
}
CONTROLLER_TRACE_KEYS = {
    "scope",
    "commands",
    "telemetry",
    "settle_grant_s",
    "command_message_count",
    "telemetry_message_count",
}
CONTROLLER_COMMAND_KEYS = {
    "sent_time_s",
    "window",
    "operation",
    "point_index",
    "semantic_message",
}
GATEWAY_TRACE_KEYS = {
    "scope",
    "commands",
    "steps",
    "command_message_count",
    "step_count",
}
DIRECT_COMMAND_KEYS = {
    "receive_time_s",
    "semantic_message",
    "select_result",
    "operate_result",
}
CONTROLLER_TELEMETRY_KEYS = {
    "granted_time_s",
    "source",
    "original_source",
    "payload",
}
PREFLIGHT_KEYS = {
    "schema_version",
    "scope",
    "mode",
    "static_preflight",
    "image_preflight",
    "image_errors",
    "image_evidence",
    "execution_attempted",
    "execution_result",
    "claims_permitted",
    "equivalence_claim_permitted",
    "seed",
    "federate_count",
    "cyber_endpoint_count",
    "cyber_route_count",
    "physical_value_link_count",
    "gridlabd_message_endpoint_count",
    "attacker_process_count",
    "network_impairment_count",
    "effective_inventory",
}
EXECUTION_RESULT_KEYS = {
    "status",
    "create_returncode",
    "identity",
    "returncodes",
    "runtime_inventory",
}


class NormalizationError(RuntimeError):
    """The direct live bundle cannot be normalized safely."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise NormalizationError(f"{path}: duplicate JSON field {key}")
            result[key] = value
        return result

    try:
        result = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(f"cannot load {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise NormalizationError(f"{path}: JSON root must be an object")
    return result


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise NormalizationError(f"{label} fields must be exact")
    return value


def _finite(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise NormalizationError(f"{label} must be finite")
    return float(value)


def _metadata(path: Path, repo_root: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        relative = str(path.resolve())
    return {
        "path": relative,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def _validate_inventory(
    root: Path, inventory: Any, *, label: str
) -> list[Path]:
    if not isinstance(inventory, list):
        raise NormalizationError(f"{label} must be an array")
    expected: dict[str, tuple[int, str]] = {}
    for index, item in enumerate(inventory):
        row = _exact(item, {"path", "size", "sha256"}, f"{label}[{index}]")
        relative, size, digest = row["path"], row["size"], row["sha256"]
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative in expected
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise NormalizationError(f"{label}[{index}] metadata is invalid")
        expected[relative] = (size, digest)
    actual = sorted(path for path in root.rglob("*") if path.is_file())
    if {path.relative_to(root).as_posix() for path in actual} != set(expected):
        raise NormalizationError(f"{label} file set differs from disk")
    for path in actual:
        relative = path.relative_to(root).as_posix()
        if (path.stat().st_size, sha256(path)) != expected[relative]:
            raise NormalizationError(f"{label} artifact drift: {relative}")
    return actual


def _validate_contract(contract: dict[str, Any]) -> str:
    _exact(
        contract,
        {
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
        },
        "effective direct contract",
    )
    if contract.get("schema_version") != "1.0" or contract.get("seed") != 777:
        raise NormalizationError("effective direct contract identity changed")
    if contract.get("scope") != (
        "G4 benign live direct-reference arm using the canonical IEEE "
        "123-bus/OpenDER physical loop; no NATIG, attacker, or impairment"
    ):
        raise NormalizationError("effective direct scope changed")
    simulation = contract.get("simulation")
    if not isinstance(simulation, dict) or simulation.get("duration_s") != 840:
        raise NormalizationError("effective direct duration changed")
    expected_periods = {
        "controller_period_s": 10,
        "physical_coupling_period_s": 10,
        "opender_internal_step_s": 1,
    }
    if any(simulation.get(key) != value for key, value in expected_periods.items()):
        raise NormalizationError("effective direct timing changed")
    if contract.get("broker") != {
        "core_type": "zmq",
        "port": 9000,
        "federate_count": 3,
    }:
        raise NormalizationError("effective direct broker contract changed")
    if contract.get("federates") != [
        {
            "owner": "controller",
            "name": "g4_live_direct_controller_der_ev4",
            "config": "controller.json",
        },
        {
            "owner": "gateway",
            "name": "g4_live_direct_gateway_der_ev4",
            "config": "gateway.json",
        },
        {
            "owner": "gridlabd",
            "name": "g4_gridlabd_der_ev4",
            "config": "../live_benign/gridlabd.json",
        },
    ]:
        raise NormalizationError("effective direct federates changed")
    if contract.get("cyber_routes") != [
        {
            "stream": "command",
            "source": "controller/der_ev4",
            "destination": "gateway/der_ev4",
            "transport": "helics_message",
        },
        {
            "stream": "telemetry",
            "source": "gateway/der_ev4",
            "destination": "controller/der_ev4",
            "transport": "helics_message",
        },
    ]:
        raise NormalizationError("effective direct cyber routes changed")
    if contract.get("physical_values") != [
        {
            "key": "gridlabd/ev4_voltage_c",
            "publisher": "gridlabd",
            "subscriber": "gateway",
            "type": "complex",
            "unit": "V",
        },
        {
            "key": "gateway/feeder_load_va",
            "publisher": "gateway",
            "subscriber": "gridlabd",
            "type": "complex",
            "unit": "VA",
        },
    ]:
        raise NormalizationError("effective direct physical links changed")
    if contract.get("security_condition") != {
        "name": "benign",
        "attacker_processes": [],
        "network_impairments": [],
        "natig_processes": [],
    }:
        raise NormalizationError("effective direct contract is not benign")
    if set(contract.get("required_processes", [])) != EXPECTED_PROCESSES:
        raise NormalizationError("effective direct process set changed")
    if set(contract.get("required_runtime_outputs", [])) != EXPECTED_RUNTIME_OUTPUTS:
        raise NormalizationError("effective direct output set changed")
    source_locks = contract.get("source_locks")
    if not isinstance(source_locks, list):
        raise NormalizationError("effective direct source locks are missing")
    expected_lock_paths = {
        "../run_live_direct.py",
        "live_controller_federate.py",
        "live_gateway_federate.py",
        "controller.json",
        "gateway.json",
        "../live_benign/gridlabd.json",
        "../../cyber_gateway/dnp3_point_map.yaml",
        "../../cyber_gateway/gateway.py",
        "../dnp3_codec.py",
        "../gateway_bridge.py",
        "../run_offline_conformance.py",
        "../../opender/device.py",
        "../run_live_benign.py",
    }
    observed_lock_paths: set[str] = set()
    for index, row in enumerate(source_locks):
        row = _exact(row, {"path", "sha256"}, f"source_locks[{index}]")
        if (
            not isinstance(row["path"], str)
            or row["path"] in observed_lock_paths
            or not isinstance(row["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        ):
            raise NormalizationError(f"source_locks[{index}] is invalid")
        observed_lock_paths.add(row["path"])
    if observed_lock_paths != expected_lock_paths:
        raise NormalizationError("effective direct source-lock set changed")
    candidates = [
        row.get("sha256")
        for row in source_locks
        if isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and "run_live_direct" in row["path"]
    ]
    if len(candidates) != 1 or not isinstance(candidates[0], str):
        raise NormalizationError("effective direct runner source lock is missing")
    if not re.fullmatch(r"[0-9a-f]{64}", candidates[0]):
        raise NormalizationError("effective direct runner digest is invalid")
    if contract.get("r24_image_manifest") != {
        "path": "../locked_runtime_result_base_r24_r1/live_image_manifest.json",
        "sha256": R24_IDENTITY["image_manifest_sha256"],
    }:
        raise NormalizationError("effective direct r24 manifest lock changed")
    overlay = contract.get("g3_physical_overlay")
    if (
        not isinstance(overlay, dict)
        or overlay.get("model_sha256")
        != "d6008f376371ff18b548f5f93971f162121ac7c91555c8b07358c27697983202"
        or overlay.get("support_tree_sha256")
        != "23aa30bcd0b8685f2bcc19c2290d1d63fba35a8b04475c643eb2ba4a1a35ff94"
        or overlay.get("gridlabd_config_sha256")
        != "d27b6015db96da7101aa5c5795ee24470120bc769605efe32b487617b2485a31"
        or overlay.get("coupling_object") != "DER_EV4_BESS_COUPLING"
        or overlay.get("parent_bus") != "l92"
        or overlay.get("minimum_timestep_s") != 10
    ):
        raise NormalizationError("effective direct G3 physical overlay changed")
    return candidates[0]


def _validate_preflight(
    run_dir: Path, preflight: dict[str, Any]
) -> tuple[dict[str, Any], list[Path]]:
    _exact(preflight, PREFLIGHT_KEYS, "preflight")
    required = {
        "schema_version": "1.0",
        "mode": "execute",
        "static_preflight": "PASS",
        "image_preflight": "READY",
        "image_errors": [],
        "execution_attempted": True,
        "equivalence_claim_permitted": False,
        "seed": 777,
        "federate_count": 3,
        "attacker_process_count": 0,
        "network_impairment_count": 0,
    }
    for field, expected in required.items():
        if preflight[field] != expected:
            raise NormalizationError(f"preflight {field} does not prove direct run")
    for field in (
        "cyber_endpoint_count",
        "cyber_route_count",
        "physical_value_link_count",
        "gridlabd_message_endpoint_count",
    ):
        if (
            not isinstance(preflight[field], int)
            or isinstance(preflight[field], bool)
            or preflight[field] < 0
        ):
            raise NormalizationError(f"preflight {field} is invalid")
    if (
        preflight["cyber_endpoint_count"] != 2
        or preflight["cyber_route_count"] != 2
        or preflight["physical_value_link_count"] != 2
        or preflight["gridlabd_message_endpoint_count"] != 0
    ):
        raise NormalizationError("preflight direct topology counts changed")
    claims = preflight["claims_permitted"]
    if (
        not isinstance(claims, list)
        or "live_direct_execution" not in claims
        or not all(isinstance(item, str) for item in claims)
    ):
        raise NormalizationError("preflight does not permit direct execution claim")
    execution = _exact(
        preflight["execution_result"],
        EXECUTION_RESULT_KEYS,
        "preflight.execution_result",
    )
    if execution["status"] != "PASS" or execution["create_returncode"] != 0:
        raise NormalizationError("direct live execution did not pass")
    if (
        not isinstance(execution["returncodes"], dict)
        or set(execution["returncodes"]) != EXPECTED_PROCESSES
        or any(value != 0 for value in execution["returncodes"].values())
    ):
        raise NormalizationError("direct process return codes are incomplete or nonzero")
    identity = _exact(
        execution["identity"], IDENTITY_KEYS, "preflight.execution_result.identity"
    )
    if any(identity[field] != value for field, value in R24_IDENTITY.items()):
        raise NormalizationError("direct producer is not the r24-derived runtime")
    if not str(identity["helics_native_version"]).startswith("2.7.1"):
        raise NormalizationError("direct producer is not the r24-derived runtime")
    for field in (
        "binary_sha256",
        "source_sha256",
        "helics_module_sha256",
        "opender_module_sha256",
        "numpy_module_sha256",
        "pandas_module_sha256",
    ):
        if not isinstance(identity[field], str) or not re.fullmatch(
            r"[0-9a-f]{64}", identity[field]
        ):
            raise NormalizationError(f"invalid direct producer identity {field}")
    for field in ("natig_commit", "natig_tree"):
        if not isinstance(identity[field], str) or not re.fullmatch(
            r"[0-9a-f]{40}", identity[field]
        ):
            raise NormalizationError(f"invalid direct producer identity {field}")
    if not isinstance(identity["execution_user"], str) or not re.fullmatch(
        r"[0-9]+:[0-9]+", identity["execution_user"]
    ):
        raise NormalizationError("invalid direct producer execution_user")
    image_evidence = _exact(
        preflight["image_evidence"],
        {"path", "sha256", "image_id"},
        "preflight.image_evidence",
    )
    retained_manifest = run_dir / str(image_evidence["path"])
    if (
        image_evidence["path"] != "live_image_manifest.json"
        or not retained_manifest.is_file()
        or sha256(retained_manifest) != image_evidence["sha256"]
        or identity["image_manifest_sha256"] != image_evidence["sha256"]
        or identity["image_id"] != image_evidence["image_id"]
        or not isinstance(image_evidence["image_id"], str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_evidence["image_id"])
    ):
        raise NormalizationError("retained direct image identity mismatch")
    retained = load_json(retained_manifest)
    if (
        retained.get("schema_version") != "1.0"
        or retained.get("ready") is not True
        or retained.get("image_id") != image_evidence["image_id"]
    ):
        raise NormalizationError("retained direct image manifest changed")
    effective = _validate_inventory(
        run_dir / "effective",
        preflight["effective_inventory"],
        label="effective_inventory",
    )
    runtime = _validate_inventory(
        run_dir / "runtime_output",
        execution["runtime_inventory"],
        label="runtime_inventory",
    )
    names = {path.name for path in runtime}
    if not EXPECTED_RUNTIME_OUTPUTS <= names:
        raise NormalizationError("direct runtime inventory lacks required outputs")
    if any(
        path.stat().st_size == 0
        for path in runtime
        if path.name in EXPECTED_RUNTIME_OUTPUTS and path.name != "broker.log"
    ):
        raise NormalizationError("required direct runtime output is empty")
    return identity, [retained_manifest, *effective, *runtime]


def _expected_semantic(expected: dict[str, Any], sequence: int) -> dict[str, Any]:
    event_time = expected["event_time_s"]
    return {
        "schema_version": "0.1",
        "kind": "command",
        "message_id": f"live-t{int(event_time):04d}-ao{expected['point_index']}",
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


def _validate_controller(controller: dict[str, Any]) -> None:
    _exact(controller, CONTROLLER_TRACE_KEYS, "controller trace")
    if controller["scope"] != (
        "G4 benign live direct controller trace; "
        "no NATIG, attacker, or impairment"
    ):
        raise NormalizationError("controller trace is not the direct benign arm")
    rows = controller["commands"]
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_COMMANDS):
        raise NormalizationError("direct controller must contain exactly 18 commands")
    for index, (row, expected) in enumerate(zip(rows, EXPECTED_COMMANDS)):
        row = _exact(row, CONTROLLER_COMMAND_KEYS, f"controller.commands[{index}]")
        event = int(expected["event_time_s"])
        sequence = list(EXPECTED_WINDOWS).index(event) + 1
        if (
            row["sent_time_s"] != expected["event_time_s"]
            or row["window"] != EXPECTED_WINDOWS[event]
            or row["operation"] != "select_operate"
            or row["point_index"] != expected["point_index"]
            or row["semantic_message"] != _expected_semantic(expected, sequence)
        ):
            raise NormalizationError(
                f"controller.commands[{index}] violates frozen schedule"
            )
    if controller["command_message_count"] != len(rows):
        raise NormalizationError("direct controller command count is inconsistent")
    settle = _finite(controller["settle_grant_s"], "controller.settle_grant_s")
    if settle < DURATION_S or settle > DURATION_S + 10.0:
        raise NormalizationError("direct controller settle grant is invalid")


def _validate_controller_telemetry(
    rows: Any, steps: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_SAMPLE_TIMES):
        raise NormalizationError(
            "direct controller must contain exactly 84 telemetry messages"
        )
    samples: list[dict[str, Any]] = []
    last_granted = -math.inf
    for index, (row, step, expected_time) in enumerate(
        zip(rows, steps, EXPECTED_SAMPLE_TIMES)
    ):
        label = f"controller.telemetry[{index}]"
        row = _exact(row, CONTROLLER_TELEMETRY_KEYS, label)
        granted = _finite(row["granted_time_s"], f"{label}.granted_time_s")
        if (
            granted < last_granted
            or granted < expected_time
            or granted > expected_time + 10.0
        ):
            raise NormalizationError(f"{label} HELICS grant is invalid")
        last_granted = granted
        endpoints = []
        for field in ("source", "original_source"):
            value = row[field]
            if value is not None and not isinstance(value, str):
                raise NormalizationError(f"{label}.{field} is invalid")
            if isinstance(value, str) and value:
                endpoints.append(value)
        if not any("gateway/der_ev4" in value for value in endpoints):
            raise NormalizationError(f"{label} lacks direct gateway provenance")
        payload = _exact(
            row["payload"], GATEWAY_TELEMETRY_KEYS, f"{label}.payload"
        )
        if payload != step["telemetry"]:
            raise NormalizationError(
                f"{label} differs from direct gateway telemetry"
            )
        analog = payload["analog"]
        samples.append(
            {
                "time_s": expected_time,
                "p_kw": float(analog[0]),
                "q_kvar": float(analog[1]),
                "voltage_pu": float(analog[2]),
                "soc_pu": float(analog[3]),
            }
        )
    return samples


def _expected_application_payload(expected: dict[str, Any]) -> tuple[dict, dict]:
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


def _validate_steps(
    rows: Any,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_SAMPLE_TIMES):
        raise NormalizationError("direct gateway must contain exactly 84 steps")
    applications: dict[str, dict[str, Any]] = {}
    validated: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    for index, (row, expected_time) in enumerate(zip(rows, EXPECTED_SAMPLE_TIMES)):
        label = f"gateway.steps[{index}]"
        row = _exact(row, GATEWAY_STEP_KEYS, label)
        if (
            row["granted_time_s"] != float(expected_time)
            or row["device_time_s"] != float(expected_time)
            or row["status"] != "Continuous Operation"
        ):
            raise NormalizationError(f"{label} time or device status changed")
        terminal = _finite(row["terminal_voltage_v"], f"{label}.terminal_voltage_v")
        p_kw = _finite(row["p_out_kw"], f"{label}.p_out_kw")
        q_kvar = _finite(row["q_out_kvar"], f"{label}.q_out_kvar")
        soc = _finite(row["soc_pu"], f"{label}.soc_pu")
        if not 0.0 < terminal <= 2.0 * NOMINAL_VOLTAGE_V or not 0.0 <= soc <= 1.0:
            raise NormalizationError(f"{label} physical values are out of bounds")
        feeder = _exact(row["feeder_load_va"], {"real", "imag"}, f"{label}.feeder")
        if (
            _finite(feeder["real"], f"{label}.feeder.real") != -1000.0 * p_kw
            or _finite(feeder["imag"], f"{label}.feeder.imag") != -1000.0 * q_kvar
        ):
            raise NormalizationError(f"{label} feeder sign mapping changed")
        telemetry = _exact(
            row["telemetry"], GATEWAY_TELEMETRY_KEYS, f"{label}.telemetry"
        )
        if (
            telemetry["schema_version"] != "grideval-g4-telemetry-0.1"
            or telemetry["target"] != "DER_EV4_BESS"
            or telemetry["analog"]
            != [p_kw, q_kvar, terminal / NOMINAL_VOLTAGE_V, soc]
            or not isinstance(telemetry["binary"], list)
            or len(telemetry["binary"]) != 2
            or not all(isinstance(item, bool) for item in telemetry["binary"])
            or telemetry["binary"][0] is not True
        ):
            raise NormalizationError(f"{label} direct telemetry is malformed")
        if not isinstance(row["applied"], list):
            raise NormalizationError(f"{label}.applied must be an array")
        for offset, application in enumerate(row["applied"]):
            application = _exact(
                application, APPLIED_KEYS, f"{label}.applied[{offset}]"
            )
            action_id = application["action_id"]
            due = _finite(application["due_time_s"], f"{label}.due_time_s")
            applied = _finite(
                application["applied_time_s"], f"{label}.applied_time_s"
            )
            if (
                not isinstance(action_id, str)
                or not action_id
                or action_id in applications
                or due > applied
                or applied > float(expected_time)
            ):
                raise NormalizationError(f"{label} has invalid OpenDER application")
            applications[action_id] = application
        validated.append(row)
        samples.append(
            {
                "time_s": expected_time,
                "p_kw": p_kw,
                "q_kvar": q_kvar,
                "voltage_pu": terminal / NOMINAL_VOLTAGE_V,
                "soc_pu": soc,
            }
        )
    if len(applications) != len(EXPECTED_COMMANDS):
        raise NormalizationError("direct gateway must prove exactly 18 applications")
    return validated, applications, samples


def _validate_commands(
    rows: Any, applications: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_COMMANDS):
        raise NormalizationError("direct gateway must contain exactly 18 commands")
    commands: list[dict[str, Any]] = []
    normalized_applications: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, (row, expected) in enumerate(zip(rows, EXPECTED_COMMANDS)):
        label = f"gateway.commands[{index}]"
        row = _exact(row, DIRECT_COMMAND_KEYS, label)
        receive = _finite(row["receive_time_s"], f"{label}.receive_time_s")
        event = int(expected["event_time_s"])
        sequence = list(EXPECTED_WINDOWS).index(event) + 1
        semantic = _exact(row["semantic_message"], SEMANTIC_KEYS, f"{label}.semantic")
        _exact(semantic["payload"], SEMANTIC_PAYLOAD_KEYS, f"{label}.payload")
        if (
            semantic != _expected_semantic(expected, sequence)
            or receive < expected["event_time_s"]
            or receive > expected["event_time_s"] + 10.0
        ):
            raise NormalizationError(f"{label} violates direct schedule lineage")
        message_id = semantic["message_id"]
        if message_id in seen:
            raise NormalizationError("direct semantic message IDs are not unique")
        seen.add(message_id)
        settings, inputs = _expected_application_payload(expected)
        select = row["select_result"]
        operate = row["operate_result"]
        expected_select = {
            "gateway_decision": "selected",
            "reason": "select_accepted",
            "message_id": message_id,
            "receive_time_s": receive,
            "select_expires_at_s": receive + 5.0,
        }
        expected_operate = {
            "gateway_decision": "accepted",
            "reason": "operate_accepted",
            "lifecycle_stage": "gateway_accepted",
            "acceptance_scope": (
                "gateway_validation_and_queue_acceptance_not_device_application"
            ),
            "message_id": message_id,
            "receive_time_s": receive,
            "due_time_s": receive,
            "actuation_sequence": index + 1,
            "opender_settings": settings,
            "opender_inputs": inputs,
        }
        if select != expected_select or operate != expected_operate:
            raise NormalizationError(f"{label} was not accepted end to end")
        application = applications.get(message_id)
        if application is None:
            raise NormalizationError(f"missing direct application for {message_id}")
        if (
            application["sequence"] != index + 1
            or application["settings"] != settings
            or application["inputs"] != inputs
        ):
            raise NormalizationError(f"OpenDER application differs for {message_id}")
        command_id = f"direct-{message_id}-accepted-command"
        application_id = f"direct-{message_id}-application"
        commands.append(
            {
                **expected,
                "accepted": True,
                "accepted_time_s": receive,
                "command_id": command_id,
                "application_id": application_id,
            }
        )
        normalized_applications.append(
            {
                "application_id": application_id,
                "command_id": command_id,
                "schedule_key": expected["schedule_key"],
                "point_index": expected["point_index"],
                "value": expected["value"],
                "unit": expected["unit"],
                "applied_time_s": float(application["applied_time_s"]),
            }
        )
    if set(applications) != seen:
        raise NormalizationError("unmatched direct OpenDER applications are present")
    return commands, normalized_applications


def normalize(*, run_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Normalize one completed create-once direct live-run directory."""

    run_dir = run_dir.resolve()
    repo_root = repo_root.resolve()
    preflight_path = run_dir / "live_direct_preflight.json"
    controller_path = run_dir / "runtime_output" / "controller_trace.json"
    gateway_path = run_dir / "runtime_output" / "gateway_trace.json"
    contract_path = run_dir / "effective" / "federation_contract.json"
    for path in (preflight_path, controller_path, gateway_path, contract_path):
        if not path.is_file():
            raise NormalizationError(f"missing direct live artifact: {path}")
    preflight = load_json(preflight_path)
    identity, inventoried = _validate_preflight(run_dir, preflight)
    runner_sha = _validate_contract(load_json(contract_path))
    controller = load_json(controller_path)
    gateway = load_json(gateway_path)
    _validate_controller(controller)
    _exact(gateway, GATEWAY_TRACE_KEYS, "gateway trace")
    if gateway["scope"] != (
        "G4 benign live direct gateway/OpenDER trace; "
        "no NATIG, attacker, or impairment"
    ):
        raise NormalizationError("gateway trace is not the direct benign arm")
    steps, raw_applications, _gateway_samples = _validate_steps(gateway["steps"])
    commands, applications = _validate_commands(
        gateway["commands"], raw_applications
    )
    if gateway["command_message_count"] != len(commands):
        raise NormalizationError("direct gateway command count is inconsistent")
    if gateway["step_count"] != len(steps):
        raise NormalizationError("direct gateway step count is inconsistent")
    samples = _validate_controller_telemetry(controller["telemetry"], steps)
    if controller["telemetry_message_count"] != len(samples):
        raise NormalizationError(
            "direct controller telemetry count is inconsistent"
        )
    unique = {
        path.resolve()
        for path in [preflight_path, contract_path, *inventoried]
    }
    result = {
        "schema_version": TRACE_SCHEMA,
        "path": "direct_reference",
        "execution": {
            "status": "complete",
            "start_time_s": 0.0,
            "end_time_s": DURATION_S,
            "duration_s": DURATION_S,
        },
        "provenance": {
            "source_artifacts": [
                _metadata(path, repo_root)
                for path in sorted(unique, key=lambda item: str(item))
            ],
            "producer": {
                "runner_sha256": runner_sha,
                "helics_version": identity["helics_version"],
                "opender_version": identity["opender_version"],
            },
            "normalization": {
                "normalizer_sha256": sha256(Path(__file__).resolve()),
                "method": (
                    "create-once projection of one completed independent direct "
                    "live-run bundle; no process was launched"
                ),
                "is_new_execution": False,
            },
            "field_provenance": {
                "observed": [
                    "four zero process return codes, exact runtime identities, "
                    "18 semantic gateway acceptances, 18 OpenDER applications, "
                    "and 84 controller-received physical samples are checked "
                    "from the direct bundle",
                    "command message identity is preserved from controller "
                    "publication through direct gateway acceptance and application",
                ],
                "derived": [
                    "canonical schedule keys and path-local IDs are assigned only "
                    "after exact ordinal and semantic-message lineage validation",
                    "sample time_s is assigned from each exact ordered gateway "
                    "grant at 10 through 840 seconds",
                ],
            },
            "comparison_qualifications": [
                (
                    "direct control and NATIG arms use independently executed "
                    "federations in the same r24-derived HELICS/OpenDER runtime"
                ),
                (
                    "normalization is evidence transformation only and does not "
                    "assert equivalence"
                ),
            ],
        },
        "commands": commands,
        "applications": applications,
        "samples": samples,
    }
    errors, _ = validate_execution(result, expected_path="direct_reference")
    if errors:
        raise NormalizationError(
            "normalized direct trace violates analyzer contract: "
            + "; ".join(errors)
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing existing output: {args.output}")
    try:
        result = normalize(run_dir=args.run_dir, repo_root=args.repo_root)
    except NormalizationError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except FileExistsError:
        parser.error(f"refusing existing output: {args.output}")
    print(
        json.dumps(
            {
                "status": "normalized_existing_direct_live_execution",
                "output": str(args.output.resolve()),
                "equivalence_claim_permitted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
