#!/usr/bin/env python3
"""Normalize one completed NATIG live run into the G4 equivalence contract.

The normalizer is an evidence transformation only.  It never launches HELICS,
NATIG, GridLAB-D, or OpenDER.  It fails closed unless the create-once live-run
directory proves that every process exited successfully and its controller,
gateway, and runtime-inventory evidence is complete and internally consistent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v3.natig_adapter.analyze_live_equivalence import (
    EXPECTED_COMMANDS,
    EXPECTED_SAMPLE_TIMES,
    TRACE_SCHEMA,
)


DURATION_S = 840.0
NOMINAL_VOLTAGE_V = 2401.7771
NATIG_HELICS_VERSION = "2.7.1"
EXPECTED_PROCESSES = {"broker", "controller", "natig", "gateway", "gridlabd"}
EXPECTED_RUNTIME_OUTPUTS = {
    "broker.log",
    "controller.log",
    "controller_trace.json",
    "gateway.log",
    "gateway_trace.json",
    "gridlabd.log",
    "natig.log",
}
EXPECTED_WINDOWS = {
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
IDENTITY_KEYS = {
    "image_id",
    "image_manifest_sha256",
    "natig_commit",
    "natig_tree",
    "binary_sha256",
    "source_sha256",
    "helics_module_sha256",
    "opender_module_sha256",
    "numpy_module_sha256",
    "pandas_module_sha256",
    "execution_user",
    "python_version",
    "helics_version",
    "helics_native_version",
    "opender_version",
    "numpy_version",
    "pandas_version",
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
SEMANTIC_KEYS = {
    "schema_version",
    "kind",
    "message_id",
    "event_time_s",
    "source",
    "target",
    "sequence",
    "type",
    "payload",
}
SEMANTIC_PAYLOAD_KEYS = {
    "value",
    "unit",
    "valid_until_s",
    "quality",
}
CONTROLLER_TELEMETRY_KEYS = {
    "granted_time_s",
    "source",
    "original_source",
    "payload",
}
DECODED_TELEMETRY_KEYS = {
    "wire_schema",
    "master_address",
    "outstation_address",
    "received_time_s",
    "analog_g30v5",
    "binary_g1v2",
}
GATEWAY_TRACE_KEYS = {
    "scope",
    "commands",
    "steps",
    "command_message_count",
    "step_count",
}
GATEWAY_COMMAND_KEYS = {"receive_time_s", "wire", "result"}
GATEWAY_WIRE_KEYS = {
    "schema_version",
    "group",
    "variation",
    "operation",
    "master_address",
    "outstation_address",
    "point_index",
    "raw_count",
    "status",
}
GATEWAY_STEP_KEYS = {
    "granted_time_s",
    "device_time_s",
    "terminal_voltage_v",
    "p_out_kw",
    "q_out_kvar",
    "soc_pu",
    "status",
    "feeder_load_va",
    "applied",
    "telemetry",
}
GATEWAY_TELEMETRY_KEYS = {
    "schema_version",
    "target",
    "analog",
    "binary",
}
APPLIED_KEYS = {
    "action_id",
    "sequence",
    "due_time_s",
    "applied_time_s",
    "settings",
    "inputs",
}


class NormalizationError(RuntimeError):
    """The live execution bundle cannot be normalized safely."""


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
        parsed = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(f"cannot load {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise NormalizationError(f"{path}: JSON root must be an object")
    return parsed


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


def _integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise NormalizationError(f"{label} must be an integer")
    return value


def _float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _relative_or_absolute(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _metadata(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": _relative_or_absolute(path, repo_root),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def _validate_inventory(
    root: Path,
    inventory: Any,
    *,
    label: str,
) -> list[Path]:
    if not isinstance(inventory, list):
        raise NormalizationError(f"{label} must be an array")
    expected: dict[str, tuple[int, str]] = {}
    for index, item in enumerate(inventory):
        row = _exact(item, {"path", "size", "sha256"}, f"{label}[{index}]")
        relative = row["path"]
        size = row["size"]
        digest = row["sha256"]
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative in expected
        ):
            raise NormalizationError(f"{label}[{index}].path is invalid")
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise NormalizationError(f"{label}[{index}] metadata is invalid")
        expected[relative] = (size, digest)

    actual_paths = sorted(item for item in root.rglob("*") if item.is_file())
    actual_names = {item.relative_to(root).as_posix() for item in actual_paths}
    if actual_names != set(expected):
        raise NormalizationError(f"{label} file set differs from disk")
    for path in actual_paths:
        relative = path.relative_to(root).as_posix()
        if (path.stat().st_size, sha256(path)) != expected[relative]:
            raise NormalizationError(f"{label} artifact drift: {relative}")
    return actual_paths


def _validate_contract(contract: dict[str, Any]) -> str:
    if contract.get("schema_version") != "1.0":
        raise NormalizationError("effective contract schema is unsupported")
    if contract.get("seed") != 777 or contract.get("simulation") != {
        "duration_s": 840,
        "controller_period_s": 10,
        "dnp3_poll_period_s": 10,
        "physical_coupling_period_s": 10,
        "opender_internal_step_s": 1,
    }:
        raise NormalizationError("effective contract timing or seed changed")
    security = contract.get("security_condition")
    if security != {
        "name": "benign",
        "attacker_processes": [],
        "network_impairments": [],
    }:
        raise NormalizationError("effective contract is not benign")
    if set(contract.get("required_processes", [])) != EXPECTED_PROCESSES:
        raise NormalizationError("effective required-process set changed")
    if set(contract.get("required_runtime_outputs", [])) != EXPECTED_RUNTIME_OUTPUTS:
        raise NormalizationError("effective required-output set changed")
    source_locks = contract.get("source_locks")
    if not isinstance(source_locks, list):
        raise NormalizationError("effective source locks are missing")
    runner_digests = [
        item.get("sha256")
        for item in source_locks
        if isinstance(item, dict)
        and item.get("path") == "../run_live_benign.py"
    ]
    if (
        len(runner_digests) != 1
        or not isinstance(runner_digests[0], str)
        or len(runner_digests[0]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in runner_digests[0]
        )
    ):
        raise NormalizationError("effective runner source lock is missing")
    return runner_digests[0]


def _validate_preflight(
    run_dir: Path,
    preflight: dict[str, Any],
) -> tuple[dict[str, Any], list[Path]]:
    _exact(preflight, PREFLIGHT_KEYS, "preflight")
    required_scalars = {
        "schema_version": "1.0",
        "mode": "execute",
        "static_preflight": "PASS",
        "image_preflight": "READY",
        "image_errors": [],
        "execution_attempted": True,
        "equivalence_claim_permitted": False,
        "seed": 777,
        "federate_count": 4,
        "cyber_endpoint_count": 4,
        "cyber_route_count": 6,
        "physical_value_link_count": 2,
        "gridlabd_message_endpoint_count": 0,
        "attacker_process_count": 0,
        "network_impairment_count": 0,
    }
    for field, expected in required_scalars.items():
        if preflight[field] != expected:
            raise NormalizationError(f"preflight {field} does not prove a live run")
    if (
        not isinstance(preflight["claims_permitted"], list)
        or not all(
            isinstance(item, str) for item in preflight["claims_permitted"]
        )
        or "live_benign_execution" not in preflight["claims_permitted"]
    ):
        raise NormalizationError("preflight does not permit a live-execution claim")

    execution = _exact(
        preflight["execution_result"],
        EXECUTION_RESULT_KEYS,
        "preflight.execution_result",
    )
    if execution["status"] != "PASS" or execution["create_returncode"] != 0:
        raise NormalizationError("live execution did not pass")
    if (
        not isinstance(execution["returncodes"], dict)
        or set(execution["returncodes"]) != EXPECTED_PROCESSES
        or any(value != 0 for value in execution["returncodes"].values())
    ):
        raise NormalizationError("live process return codes are incomplete or nonzero")
    identity = _exact(
        execution["identity"], IDENTITY_KEYS, "preflight.execution_result.identity"
    )
    image_evidence = _exact(
        preflight["image_evidence"],
        {"path", "sha256", "image_id"},
        "preflight.image_evidence",
    )
    if image_evidence["path"] != "live_image_manifest.json":
        raise NormalizationError("retained image manifest path changed")
    retained_manifest = run_dir / image_evidence["path"]
    if (
        not retained_manifest.is_file()
        or sha256(retained_manifest) != image_evidence["sha256"]
        or identity["image_manifest_sha256"] != image_evidence["sha256"]
    ):
        raise NormalizationError("retained image manifest digest mismatch")
    if (
        not isinstance(image_evidence["image_id"], str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_evidence["image_id"])
        or identity["image_id"] != image_evidence["image_id"]
    ):
        raise NormalizationError("retained image identity mismatch")
    retained = load_json(retained_manifest)
    if (
        retained.get("schema_version") != "1.0"
        or retained.get("ready") is not True
        or retained.get("image_id") != image_evidence["image_id"]
    ):
        raise NormalizationError("retained image manifest identity changed")
    if (
        identity["python_version"] != "3.9.2"
        or identity["helics_version"] != NATIG_HELICS_VERSION
        or not str(identity["helics_native_version"]).startswith(
            NATIG_HELICS_VERSION
        )
        or identity["opender_version"] != "2.2.0"
        or identity["numpy_version"] != "2.0.2"
        or identity["pandas_version"] != "2.2.3"
    ):
        raise NormalizationError("live producer runtime versions changed")
    for field in (
        "binary_sha256",
        "source_sha256",
        "helics_module_sha256",
        "opender_module_sha256",
        "numpy_module_sha256",
        "pandas_module_sha256",
    ):
        digest = identity[field]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise NormalizationError(f"invalid producer identity {field}")
    for field in ("natig_commit", "natig_tree"):
        digest = identity[field]
        if (
            not isinstance(digest, str)
            or len(digest) != 40
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise NormalizationError(f"invalid producer identity {field}")
    if not (
        isinstance(identity["execution_user"], str)
        and re.fullmatch(r"[0-9]+:[0-9]+", identity["execution_user"])
    ):
        raise NormalizationError("invalid producer identity execution_user")

    effective_paths = _validate_inventory(
        run_dir / "effective",
        preflight["effective_inventory"],
        label="effective_inventory",
    )
    runtime_paths = _validate_inventory(
        run_dir / "runtime_output",
        execution["runtime_inventory"],
        label="runtime_inventory",
    )
    names = {path.name for path in runtime_paths}
    if not EXPECTED_RUNTIME_OUTPUTS <= names:
        raise NormalizationError("runtime inventory lacks required outputs")
    if any(
        path.stat().st_size == 0
        for path in runtime_paths
        if path.name in EXPECTED_RUNTIME_OUTPUTS
        and path.name != "broker.log"
    ):
        raise NormalizationError("required runtime output is empty")
    return identity, [retained_manifest, *effective_paths, *runtime_paths]


def _expected_semantic(expected: dict[str, Any], sequence: int) -> dict[str, Any]:
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


def _validate_controller_commands(document: dict[str, Any]) -> None:
    commands = document["commands"]
    if not isinstance(commands, list) or len(commands) != len(EXPECTED_COMMANDS):
        raise NormalizationError("controller trace must contain exactly 18 commands")
    for index, (row, expected) in enumerate(zip(commands, EXPECTED_COMMANDS)):
        row = _exact(row, CONTROLLER_COMMAND_KEYS, f"controller.commands[{index}]")
        event_time = int(expected["event_time_s"])
        sequence = list(EXPECTED_WINDOWS).index(event_time) + 1
        if (
            row["sent_time_s"] != expected["event_time_s"]
            or row["window"] != EXPECTED_WINDOWS[event_time]
            or row["operation"] != "select_operate"
            or row["point_index"] != expected["point_index"]
            or row["semantic_message"] != _expected_semantic(expected, sequence)
        ):
            raise NormalizationError(
                f"controller.commands[{index}] violates the frozen schedule"
            )
    if document["command_message_count"] != len(commands):
        raise NormalizationError("controller command count is inconsistent")


def _validate_gateway_telemetry(
    steps: Any,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(steps, list) or len(steps) != len(EXPECTED_SAMPLE_TIMES):
        raise NormalizationError("gateway trace must contain exactly 84 steps")
    validated: list[dict[str, Any]] = []
    applications: dict[str, dict[str, Any]] = {}
    for index, (row, expected_time) in enumerate(
        zip(steps, EXPECTED_SAMPLE_TIMES)
    ):
        label = f"gateway.steps[{index}]"
        row = _exact(row, GATEWAY_STEP_KEYS, label)
        if (
            row["granted_time_s"] != float(expected_time)
            or row["device_time_s"] != float(expected_time)
            or row["status"] != "Continuous Operation"
        ):
            raise NormalizationError(f"{label} time or device status changed")
        terminal_v = _finite(row["terminal_voltage_v"], f"{label}.terminal_voltage_v")
        p_kw = _finite(row["p_out_kw"], f"{label}.p_out_kw")
        q_kvar = _finite(row["q_out_kvar"], f"{label}.q_out_kvar")
        soc = _finite(row["soc_pu"], f"{label}.soc_pu")
        if not (0.0 < terminal_v <= 2.0 * NOMINAL_VOLTAGE_V):
            raise NormalizationError(f"{label} terminal voltage is out of bounds")
        if not (0.0 <= soc <= 1.0):
            raise NormalizationError(f"{label} SOC is out of bounds")
        feeder = _exact(row["feeder_load_va"], {"real", "imag"}, f"{label}.feeder")
        if (
            _finite(feeder["real"], f"{label}.feeder.real") != -1000.0 * p_kw
            or _finite(feeder["imag"], f"{label}.feeder.imag") != -1000.0 * q_kvar
        ):
            raise NormalizationError(f"{label} feeder sign mapping changed")
        telemetry = _exact(
            row["telemetry"], GATEWAY_TELEMETRY_KEYS, f"{label}.telemetry"
        )
        expected_analog = [p_kw, q_kvar, terminal_v / NOMINAL_VOLTAGE_V, soc]
        if (
            telemetry["schema_version"] != "grideval-g4-telemetry-0.1"
            or telemetry["target"] != "DER_EV4_BESS"
            or telemetry["analog"] != expected_analog
            or not isinstance(telemetry["binary"], list)
            or len(telemetry["binary"]) != 2
            or not all(isinstance(value, bool) for value in telemetry["binary"])
            or telemetry["binary"][0] is not True
        ):
            raise NormalizationError(f"{label} gateway telemetry is malformed")
        if not isinstance(row["applied"], list):
            raise NormalizationError(f"{label}.applied must be an array")
        for applied_index, application in enumerate(row["applied"]):
            application = _exact(
                application,
                APPLIED_KEYS,
                f"{label}.applied[{applied_index}]",
            )
            action_id = application["action_id"]
            if (
                not isinstance(action_id, str)
                or not action_id
                or action_id in applications
            ):
                raise NormalizationError(f"{label} has invalid OpenDER application")
            due_time = _finite(
                application["due_time_s"],
                f"{label}.applied[{applied_index}].due_time_s",
            )
            applied_time = _finite(
                application["applied_time_s"],
                f"{label}.applied[{applied_index}].applied_time_s",
            )
            if due_time > applied_time or applied_time > float(expected_time):
                raise NormalizationError(f"{label} has invalid OpenDER application")
            applications[action_id] = application
        validated.append(row)
    if len(applications) != len(EXPECTED_COMMANDS):
        raise NormalizationError("gateway trace must prove exactly 18 applications")
    return validated, applications


def _expected_application_payload(expected: dict[str, Any]) -> tuple[dict, dict]:
    if expected["point_index"] == 0:
        return {}, {"demand_kw": expected["value"]}
    q_value = expected["value"]
    return (
        {
            "QV_MODE_ENABLE": "DISABLED",
            "QP_MODE_ENABLE": "DISABLED",
            "CONST_PF_MODE_ENABLE": "DISABLED",
            "CONST_Q": q_value * 0.005,
            "CONST_Q_MODE_ENABLE": "DISABLED" if q_value == 0.0 else "ENABLED",
        },
        {},
    )


def _validate_gateway_commands(
    rows: Any,
    applications: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(rows, list) or len(rows) != 2 * len(EXPECTED_COMMANDS):
        raise NormalizationError("gateway trace must contain exactly 36 callbacks")
    commands: list[dict[str, Any]] = []
    normalized_applications: list[dict[str, Any]] = []
    seen_message_ids: set[str] = set()
    for index, expected in enumerate(EXPECTED_COMMANDS):
        pair = rows[2 * index : 2 * index + 2]
        semantic_pair = []
        accepted_time = None
        for offset, operation in enumerate(("select", "operate")):
            label = f"gateway.commands[{2 * index + offset}]"
            record = _exact(pair[offset], GATEWAY_COMMAND_KEYS, label)
            wire = _exact(record["wire"], GATEWAY_WIRE_KEYS, f"{label}.wire")
            raw_count = round(expected["value"] / 0.001)
            receive_time = _finite(record["receive_time_s"], f"{label}.receive_time_s")
            if (
                wire["schema_version"] != "grideval-g4-dnp3-object-0.1"
                or wire["group"] != 41
                or wire["variation"] != 1
                or wire["operation"] != operation
                or wire["master_address"] != 1
                or wire["outstation_address"] != 4
                or wire["point_index"] != expected["point_index"]
                or wire["raw_count"] != raw_count
                or wire["status"] != 0
                or receive_time < expected["event_time_s"]
                or receive_time > expected["event_time_s"] + 10.0
            ):
                raise NormalizationError(f"{label} is not the expected DNP3 callback")
            result = record["result"]
            expected_decision = "selected" if operation == "select" else "accepted"
            if (
                not isinstance(result, dict)
                or result.get("adapter_decision") != expected_decision
                or result.get("semantic_message") is None
                or not isinstance(result.get("gateway_result"), dict)
            ):
                raise NormalizationError(f"{label} was not accepted end to end")
            semantic = _exact(
                result["semantic_message"], SEMANTIC_KEYS, f"{label}.semantic"
            )
            payload = _exact(
                semantic["payload"], SEMANTIC_PAYLOAD_KEYS, f"{label}.payload"
            )
            if (
                semantic["schema_version"] != "0.1"
                or semantic["kind"] != "command"
                or semantic["source"] != "ev_controller_v3"
                or semantic["target"] != "DER_EV4_BESS"
                or semantic["type"] != expected["command_type"]
                or payload["value"] != expected["value"]
                or payload["unit"] != expected["unit"]
                or payload["quality"] != ["online"]
                or semantic["event_time_s"] != receive_time
            ):
                raise NormalizationError(f"{label} semantic reconstruction changed")
            semantic_pair.append(semantic)
            gateway_result = result["gateway_result"]
            if gateway_result.get("message_id") != semantic["message_id"]:
                raise NormalizationError(f"{label} gateway message lineage broke")
            if operation == "operate":
                if (
                    gateway_result.get("gateway_decision") != "accepted"
                    or gateway_result.get("lifecycle_stage") != "gateway_accepted"
                    or gateway_result.get("receive_time_s") != receive_time
                ):
                    raise NormalizationError(f"{label} gateway acceptance is invalid")
                accepted_time = receive_time
        if semantic_pair[0] != semantic_pair[1]:
            raise NormalizationError(f"gateway command pair {index} violates SBO")
        semantic = semantic_pair[1]
        action_id = semantic["message_id"]
        if action_id in seen_message_ids:
            raise NormalizationError("gateway semantic message IDs are not unique")
        seen_message_ids.add(action_id)
        application = applications.get(action_id)
        if application is None:
            raise NormalizationError(f"missing OpenDER application for {action_id}")
        expected_settings, expected_inputs = _expected_application_payload(expected)
        if (
            application["settings"] != expected_settings
            or application["inputs"] != expected_inputs
        ):
            raise NormalizationError(f"OpenDER application differs for {action_id}")
        application_id = f"natig-{action_id}-application"
        command_id = f"natig-{action_id}-accepted-command"
        assert accepted_time is not None
        commands.append(
            {
                **expected,
                "accepted": True,
                "accepted_time_s": accepted_time,
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
    if set(applications) != seen_message_ids:
        raise NormalizationError("unmatched OpenDER applications are present")
    return commands, normalized_applications


def _validate_controller_telemetry(
    rows: Any,
    gateway_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_SAMPLE_TIMES):
        raise NormalizationError(
            "controller trace must contain exactly 84 decoded telemetry frames"
        )
    samples = []
    last_received = -math.inf
    last_granted = -math.inf
    for index, (row, step, expected_time) in enumerate(
        zip(rows, gateway_steps, EXPECTED_SAMPLE_TIMES)
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
        for endpoint_field in ("source", "original_source"):
            if row[endpoint_field] is not None and not isinstance(
                row[endpoint_field], str
            ):
                raise NormalizationError(f"{label}.{endpoint_field} is invalid")
        endpoint_evidence = [
            row[field]
            for field in ("source", "original_source")
            if isinstance(row[field], str) and row[field]
        ]
        if not any("cc_der_ev4" in value for value in endpoint_evidence):
            raise NormalizationError(f"{label} lacks NATIG endpoint provenance")
        payload = _exact(
            row["payload"], DECODED_TELEMETRY_KEYS, f"{label}.payload"
        )
        received = _finite(payload["received_time_s"], f"{label}.received_time_s")
        if (
            payload["wire_schema"]
            != "grideval-g4-dnp3-telemetry-decoded/1.0"
            or payload["master_address"] != 1
            or payload["outstation_address"] != 4
            or received < last_received
            or received < expected_time
            or received > expected_time + 10.0
            or received > granted
        ):
            raise NormalizationError(f"{label} decoded DNP3 envelope is invalid")
        last_received = received
        analog = payload["analog_g30v5"]
        binary = payload["binary_g1v2"]
        if (
            not isinstance(analog, list)
            or len(analog) != 4
            or not isinstance(binary, list)
            or len(binary) != 2
            or not all(isinstance(value, bool) for value in binary)
        ):
            raise NormalizationError(f"{label} telemetry is partial or malformed")
        decoded = [
            _finite(value, f"{label}.analog_g30v5[{offset}]")
            for offset, value in enumerate(analog)
        ]
        expected_analog = [
            _float32(float(value))
            for value in step["telemetry"]["analog"]
        ]
        if decoded != expected_analog or binary != step["telemetry"]["binary"]:
            raise NormalizationError(
                f"{label} differs from gateway telemetry after float32 encoding"
            )
        samples.append(
            {
                "time_s": expected_time,
                "p_kw": decoded[0],
                "q_kvar": decoded[1],
                "voltage_pu": decoded[2],
                "soc_pu": decoded[3],
            }
        )
    return samples


def normalize(*, run_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Normalize one completed create-once live-run directory."""

    run_dir = run_dir.resolve()
    repo_root = repo_root.resolve()
    preflight_path = run_dir / "live_benign_preflight.json"
    controller_path = run_dir / "runtime_output" / "controller_trace.json"
    gateway_path = run_dir / "runtime_output" / "gateway_trace.json"
    contract_path = run_dir / "effective" / "federation_contract.json"
    for path in (preflight_path, controller_path, gateway_path, contract_path):
        if not path.is_file():
            raise NormalizationError(f"missing live-run artifact: {path}")

    preflight = load_json(preflight_path)
    identity, inventoried = _validate_preflight(run_dir, preflight)
    contract = load_json(contract_path)
    runner_sha = _validate_contract(contract)
    controller = load_json(controller_path)
    gateway = load_json(gateway_path)
    _exact(controller, CONTROLLER_TRACE_KEYS, "controller trace")
    _exact(gateway, GATEWAY_TRACE_KEYS, "gateway trace")
    if (
        controller["scope"] != "G4 benign controller trace; no attacker"
        or gateway["scope"] != "G4 benign gateway/OpenDER trace; no attacker"
    ):
        raise NormalizationError("raw trace scope is not the frozen benign run")
    _validate_controller_commands(controller)
    gateway_steps, raw_applications = _validate_gateway_telemetry(gateway["steps"])
    commands, applications = _validate_gateway_commands(
        gateway["commands"], raw_applications
    )
    if gateway["command_message_count"] != len(gateway["commands"]):
        raise NormalizationError("gateway command count is inconsistent")
    if gateway["step_count"] != len(gateway_steps):
        raise NormalizationError("gateway step count is inconsistent")
    samples = _validate_controller_telemetry(
        controller["telemetry"], gateway_steps
    )
    if controller["telemetry_message_count"] != len(samples):
        raise NormalizationError("controller telemetry count is inconsistent")
    settle = _finite(controller["settle_grant_s"], "controller.settle_grant_s")
    if settle < DURATION_S or settle > DURATION_S + 10.0:
        raise NormalizationError("controller final settle grant is invalid")

    unique_artifacts = {
        path.resolve()
        for path in [
            preflight_path,
            contract_path,
            *inventoried,
        ]
    }
    metadata = [
        _metadata(path, repo_root)
        for path in sorted(unique_artifacts, key=lambda item: str(item))
    ]
    return {
        "schema_version": TRACE_SCHEMA,
        "path": "natig",
        "execution": {
            "status": "complete",
            "start_time_s": 0.0,
            "end_time_s": DURATION_S,
            "duration_s": DURATION_S,
        },
        "provenance": {
            "source_artifacts": metadata,
            "producer": {
                "runner_sha256": runner_sha,
                "helics_version": identity["helics_version"],
                "opender_version": identity["opender_version"],
            },
            "normalization": {
                "normalizer_sha256": sha256(Path(__file__).resolve()),
                "method": (
                    "create-once projection of one completed NATIG live-run "
                    "bundle; no process was launched"
                ),
                "is_new_execution": False,
            },
            "field_provenance": {
                "observed": [
                    "process completion, in-container identities, 36 strict "
                    "DNP3 callbacks, 18 gateway acceptances, and 18 OpenDER "
                    "application reports are checked from the live bundle",
                    "84 P/Q/voltage/SOC samples are the controller-side "
                    "decoded G30V5 values reconciled to gateway telemetry "
                    "after exact float32 encoding",
                ],
                "derived": [
                    "schedule keys are assigned by exact ordinal matching of "
                    "the frozen controller trace to accepted DNP3 pairs",
                    "canonical path-local command and application IDs are "
                    "derived from the DNP3 bridge semantic action_id",
                    "sample time_s is assigned from the exact 10..840 gateway "
                    "step paired to each ordered controller telemetry frame",
                ],
            },
            "comparison_qualifications": [
                (
                    "the live runner retains the immutable image ID and exact "
                    "live-image-manifest bytes together with in-container "
                    "commit, tree, binary, source, module, and package identities"
                ),
                (
                    "NATIG reconstructs semantic command identity and event "
                    "time at the DNP3 outstation; controller schedule lineage "
                    "is therefore established by strict point/value/order "
                    "matching, not an end-to-end transported message ID"
                ),
            ],
        },
        "commands": commands,
        "applications": applications,
        "samples": samples,
    }


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
                "status": "normalized_existing_live_execution",
                "output": str(args.output.resolve()),
                "equivalence_claim_permitted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
