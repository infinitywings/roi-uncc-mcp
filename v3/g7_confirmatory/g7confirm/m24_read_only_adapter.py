"""Qualify the exact-byte-bound M24 empirical sensitivity adapter.

The adapter reads two local evidence files, returns a field-minimized M7
``observe_sensitivity`` payload, and records provenance separately. It cannot
contact a model, embedding service, detector, network, simulator, or actuator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .ia4_tool_loop import validate_strict_json_schema
from .manifest import create_once_json
from .orchestration_contract import ContractViolation


CONTRACT_SCHEMA_VERSION = "grideval-g7-m24-read-only-adapter-contract/v1"
INVOCATION_SCHEMA_VERSION = "grideval-g7-m24-read-only-adapter-invocation/v1"
QUALIFICATION_SCHEMA_VERSION = "grideval-g7-m24-read-only-adapter-qualification/v1"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MTKN0P1H5V3T76MJ6HYC7E"
DECISION_ID = "dec_01M1MTJT5WZGVBWFQ5E74FKK98"
CLASSIFICATION = "PRELIMINARY_ONLY"

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
ADAPTER_CODE_PATH = Path(__file__).resolve()
SCHEMA_PATH = PACKAGE_ROOT / "m24_read_only_adapter.schema.json"
M7_CONTRACT_PATH = PACKAGE_ROOT / "artifacts" / "ia4_counterfactual_contract_m7.json"
M23_ROOT = PACKAGE_ROOT / "artifacts" / "m23_system_identification_seed6101_attempt1"
M23_SOURCE_PATH = M23_ROOT / "m23_system_identification.json"
M23_AUDIT_PATH = M23_ROOT / "independent_audit_receipt.json"

EXPECTED_M7_CONTRACT_SHA256 = (
    "4cef8444c56c40ff493ed3add9847d43d9d12c72f9f1714597e7566109d26de2"
)
EXPECTED_M7_CONTRACT_ID = (
    "m7contract_fc1b2a552f322effb0ff27a451154699528c7f26da875e204178820d19fc45b3"
)
EXPECTED_M7_PROTOCOL_ID = (
    "m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff"
)
EXPECTED_M7_SEARCH_SURFACE_ID = (
    "surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78"
)
EXPECTED_M23_SOURCE_SHA256 = (
    "30d003e06d016b88d49e024857c9b74a9f9f34012a6f022b6f3a26511fc619c1"
)
EXPECTED_M23_SOURCE_ID = (
    "m23source_300ed1e8d0d878cd5ce932e59fa8920d8a22edba3793a9cfc5d9044ca0dd9f50"
)
EXPECTED_M23_CONTRACT_ID = (
    "m23contract_1fe0006a3ed480a1ef6b7a084a7031aa8855c319f02c46bfbaea42a0c45ad859"
)
EXPECTED_M23_AUDIT_SHA256 = (
    "d0c3a539c20cc4dc3adb2910cd7bbba9c90a071a839ebc0fcde9d9e67f524030"
)
EXPECTED_M23_AUDIT_ID = (
    "m23audit_f424d5ca61a12125f837a4513f6b47424b62729096c9d61a0fa50e50379a532c"
)
FINAL_EVALUATION_SEEDS = list(range(9101, 9113))
TOOL_NAME = "observe_sensitivity"
TOOL_INPUT_SCHEMA_VERSION = "sensitivity-query/v1"
TOOL_OUTPUT_SCHEMA_VERSION = "sensitivity-result/v1"
METRIC = "voltage_stress_gain_pu_per_kw"
CONSUMER_TARGETS = ("DER_A", "DER_B")
SOURCE_TARGETS = ("DER_EV1_BESS", "DER_EV4_BESS")
TARGET_ALIAS_MAP = {
    "DER_A": "DER_EV1_BESS",
    "DER_B": "DER_EV4_BESS",
}
PAYLOAD_FIELDS = ("schema_version", "window", "time_s", "metric", "values")
FORBIDDEN_PAYLOAD_FIELDS = (
    "source_id",
    "source_sha256",
    "source_classification",
    "empirical_source_admitted",
    "estimator",
    "runs",
    "pair_evidence",
    "manifest",
    "central_true_voltage_gain_pu_per_kw",
    "central_source_power_gain_w_var_per_kw",
    "centered_true_voltage_residual_pu",
    "detector",
    "defense",
)


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractViolation("M24 value is not canonical JSON") from exc


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _artifact_sha256(value: Any) -> str:
    encoded = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _strict_json_bytes(value: bytes, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ContractViolation(f"{label} contains duplicate field: {key}")
            result[key] = item
        return result

    def reject_constant(item: str) -> None:
        raise ContractViolation(f"{label} contains non-finite constant: {item}")

    try:
        decoded = value.decode("utf-8")
        return json.loads(
            decoded,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractViolation(f"{label} is not one UTF-8 JSON value") from exc


def _strict_json_file(path: Path, label: str) -> Any:
    return _strict_json_bytes(path.read_bytes(), label)


def _self_addressed(
    value: Mapping[str, Any], *, id_field: str, prefix: str,
) -> bool:
    content = _canonical_copy(value)
    actual = content.pop(id_field, None)
    return actual == prefix + _sha256_value(content)


def _expected_tool_definition() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "input_schema_version": TOOL_INPUT_SCHEMA_VERSION,
        "output_schema_version": TOOL_OUTPUT_SCHEMA_VERSION,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["metric", "target_ids"],
            "properties": {
                "metric": {"const": METRIC},
                "target_ids": {
                    "type": "array",
                    "const": list(CONSUMER_TARGETS),
                },
            },
        },
        "output_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": list(PAYLOAD_FIELDS),
            "properties": {
                "schema_version": {"const": TOOL_OUTPUT_SCHEMA_VERSION},
                "window": {"type": "integer", "minimum": 0},
                "time_s": {"type": "integer", "minimum": 0},
                "metric": {"const": METRIC},
                "values": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(CONSUMER_TARGETS),
                    "properties": {
                        target: {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 0.1,
                        }
                        for target in CONSUMER_TARGETS
                    },
                },
            },
        },
        "side_effect_class": "read_only_no_time_advance",
        "information_axis": "grid",
        "returned_information_level": "partial",
        "simulation_time_advance_s": 0.0,
        "outer_rollout_cost": 0,
    }


def _load_m7_tool_binding() -> tuple[dict[str, Any], str, str]:
    if _sha256_file(M7_CONTRACT_PATH) != EXPECTED_M7_CONTRACT_SHA256:
        raise ContractViolation("M7 contract file hash drift")
    artifact = _strict_json_file(M7_CONTRACT_PATH, "M7 contract")
    if not isinstance(artifact, Mapping):
        raise ContractViolation("M7 contract must be an object")
    if artifact.get("contract_id") != EXPECTED_M7_CONTRACT_ID:
        raise ContractViolation("M7 contract identity drift")
    protocol = artifact.get("protocol")
    if not isinstance(protocol, Mapping):
        raise ContractViolation("M7 protocol is missing")
    if protocol.get("protocol_id") != EXPECTED_M7_PROTOCOL_ID:
        raise ContractViolation("M7 protocol identity drift")
    if protocol.get("base_search_surface_id") != EXPECTED_M7_SEARCH_SURFACE_ID:
        raise ContractViolation("M7 search-surface identity drift")
    tools = protocol.get("enabled_tools")
    if not isinstance(tools, list) or len(tools) != 1:
        raise ContractViolation("M7 tool count drift")
    tool = _canonical_copy(tools[0])
    if tool != _expected_tool_definition():
        raise ContractViolation("M7 observe_sensitivity definition drift")
    return tool, protocol["protocol_id"], protocol["base_search_surface_id"]


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def build_contract() -> dict[str, Any]:
    """Build the deterministic M24 contract before invoking the adapter."""

    tool, protocol_id, surface_id = _load_m7_tool_binding()
    content = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M24",
        "classification": CLASSIFICATION,
        "status": "REGISTERED_OFFLINE_NO_ADAPTER_CALL",
        "development_only": True,
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "source_admitted": False,
        "bindings": {
            "adapter_code": {
                "path": _relative(ADAPTER_CODE_PATH),
                "sha256": _sha256_file(ADAPTER_CODE_PATH),
            },
            "receipt_schema": {
                "path": _relative(SCHEMA_PATH),
                "sha256": _sha256_file(SCHEMA_PATH),
            },
            "M7_contract": {
                "path": _relative(M7_CONTRACT_PATH),
                "sha256": EXPECTED_M7_CONTRACT_SHA256,
                "contract_id": EXPECTED_M7_CONTRACT_ID,
                "protocol_id": protocol_id,
                "search_surface_id": surface_id,
            },
            "M23_source": {
                "path": _relative(M23_SOURCE_PATH),
                "sha256": EXPECTED_M23_SOURCE_SHA256,
                "source_id": EXPECTED_M23_SOURCE_ID,
                "contract_id": EXPECTED_M23_CONTRACT_ID,
            },
            "M23_independent_audit": {
                "path": _relative(M23_AUDIT_PATH),
                "sha256": EXPECTED_M23_AUDIT_SHA256,
                "audit_id": EXPECTED_M23_AUDIT_ID,
            },
        },
        "consumer_contract": {
            "participant_rungs": ["IA3", "IA4"],
            "tool": tool,
            "exact_request": {
                "metric": METRIC,
                "target_ids": list(CONSUMER_TARGETS),
            },
            "target_alias_map": dict(TARGET_ALIAS_MAP),
            "consumer_payload_fields": list(PAYLOAD_FIELDS),
            "forbidden_consumer_payload_fields": list(FORBIDDEN_PAYLOAD_FIELDS),
            "provenance_channel": "separate_non_model_facing_invocation_receipt",
        },
        "access_boundary": {
            "real_local_read_only_adapter_authorized": True,
            "allowed_file_reads_per_invocation": [
                _relative(M23_SOURCE_PATH),
                _relative(M23_AUDIT_PATH),
            ],
            "file_write_authorized": False,
            "model_access_authorized": False,
            "embedding_access_authorized": False,
            "detector_access_authorized": False,
            "defense_access_authorized": False,
            "network_access_authorized": False,
            "docker_access_authorized": False,
            "simulator_access_authorized": False,
            "physical_actuator_authorized": False,
            "evaluation_access_authorized": False,
            "simulation_time_advance_s": 0.0,
            "outer_rollout_cost": 0,
        },
        "scientific_boundary": {
            "establishes": [
                "exact_M23_source_to_M7_payload_transformation",
                "field_minimized_consumer_payload",
                "IA3_IA4_request_and_payload_byte_parity",
                "local_read_only_adapter_access_boundary",
            ],
            "does_not_establish": [
                "source_admission",
                "stable_or_general_sensitivity",
                "attacker_or_LLM_advantage",
                "runtime_or_actuation_safety",
                "detector_or_defense_effectiveness",
                "confirmatory_or_publication_grade_evidence",
            ],
        },
    }
    contract = _canonical_copy(content)
    contract["contract_id"] = "m24contract_" + _sha256_value(content)
    return contract


def _source_issues(source: Any) -> list[str]:
    if not isinstance(source, Mapping):
        return ["source_not_object"]
    issues: list[str] = []
    if source.get("schema_version") != "grideval-g7-m23-system-identification/v1":
        issues.append("source_schema_drift")
    if source.get("source_id") != EXPECTED_M23_SOURCE_ID:
        issues.append("source_id_drift")
    if not _self_addressed(source, id_field="source_id", prefix="m23source_"):
        issues.append("source_self_address_drift")
    if source.get("contract_id") != EXPECTED_M23_CONTRACT_ID:
        issues.append("source_contract_binding_drift")
    if source.get("classification") != CLASSIFICATION:
        issues.append("source_classification_drift")
    if source.get("status") != "EMPIRICAL_SYSTEM_IDENTIFICATION_SOURCE_CANDIDATE":
        issues.append("source_status_drift")
    for field in ("campaign_authorized", "confirmatory_claim_authorized", "evaluation_opened"):
        if source.get(field) is not False:
            issues.append(f"source_boundary_opened:{field}")
    if source.get("final_evaluation_seeds_accessed") != []:
        issues.append("final_evaluation_accessed")
    if source.get("final_evaluation_seeds_remain_sealed") != FINAL_EVALUATION_SEEDS:
        issues.append("final_evaluation_seal_drift")

    payload = source.get("read_only_tool_payload_candidate")
    expected_payload_fields = {
        "schema_version",
        "metric",
        "time_s",
        "window",
        "values",
        "source_classification",
        "empirical_source_admitted",
    }
    if not isinstance(payload, Mapping):
        issues.append("source_payload_missing")
        return sorted(set(issues))
    if set(payload) != expected_payload_fields:
        issues.append("source_payload_field_drift")
    if payload.get("schema_version") != TOOL_OUTPUT_SCHEMA_VERSION:
        issues.append("source_payload_schema_drift")
    if payload.get("metric") != METRIC:
        issues.append("source_payload_metric_drift")
    if payload.get("time_s") != 30 or payload.get("window") != 2:
        issues.append("source_payload_time_drift")
    if payload.get("source_classification") != CLASSIFICATION:
        issues.append("source_payload_classification_drift")
    if payload.get("empirical_source_admitted") is not False:
        issues.append("source_admission_boundary_opened")
    values = payload.get("values")
    if not isinstance(values, Mapping) or set(values) != set(SOURCE_TARGETS):
        issues.append("source_payload_target_drift")
    else:
        for target in SOURCE_TARGETS:
            value = values[target]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 <= float(value) <= 0.1
            ):
                issues.append(f"source_payload_value_invalid:{target}")

    columns = source.get("estimator", {}).get("columns", [])
    column_map = {
        item.get("target_id"): item
        for item in columns
        if isinstance(item, Mapping)
    }
    for target in SOURCE_TARGETS:
        column = column_map.get(target)
        if not isinstance(column, Mapping):
            issues.append(f"source_full_vector_missing:{target}")
            continue
        vector = column.get("central_true_voltage_gain_pu_per_kw")
        if not isinstance(vector, Mapping) or set(vector) != {
            "DER_EV1_BESS", "DER_EV3_PV", "DER_EV4_BESS", "DER_EV5_PV",
        }:
            issues.append(f"source_full_vector_drift:{target}")
        if isinstance(values, Mapping) and target in values:
            expected = column.get("max_abs_true_voltage_gain_pu_per_kw")
            try:
                if not math.isclose(
                    float(values[target]), float(expected), rel_tol=1e-12, abs_tol=1e-15,
                ):
                    issues.append(f"source_scalar_derivation_drift:{target}")
            except (TypeError, ValueError):
                issues.append(f"source_scalar_derivation_drift:{target}")
    return sorted(set(issues))


def _audit_issues(audit: Any) -> list[str]:
    if not isinstance(audit, Mapping):
        return ["audit_not_object"]
    issues: list[str] = []
    if audit.get("schema_version") != "grideval-g7-m23-independent-audit/v1":
        issues.append("audit_schema_drift")
    if audit.get("audit_id") != EXPECTED_M23_AUDIT_ID:
        issues.append("audit_id_drift")
    if not _self_addressed(audit, id_field="audit_id", prefix="m23audit_"):
        issues.append("audit_self_address_drift")
    if audit.get("status") != "passed":
        issues.append("audit_status_not_passed")
    if audit.get("issues") != []:
        issues.append("audit_issues_not_empty")
    if audit.get("source_sha256") != EXPECTED_M23_SOURCE_SHA256:
        issues.append("audit_source_hash_binding_drift")
    if audit.get("source_id") != EXPECTED_M23_SOURCE_ID:
        issues.append("audit_source_id_binding_drift")
    if audit.get("contract_id") != EXPECTED_M23_CONTRACT_ID:
        issues.append("audit_contract_id_binding_drift")
    retained = audit.get("known_generator_verifier_failure_retained")
    if not isinstance(retained, Mapping):
        issues.append("audit_known_failure_record_missing")
    else:
        if retained.get("source_overwritten") is not False:
            issues.append("audit_source_overwrite_boundary_drift")
        if retained.get("runtime_rerun") is not False:
            issues.append("audit_runtime_rerun_boundary_drift")
    return sorted(set(issues))


def _contract_issues(contract: Any) -> list[str]:
    if not isinstance(contract, Mapping):
        return ["contract_not_object"]
    issues: list[str] = []
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        issues.append("contract_schema_drift")
    if not _self_addressed(contract, id_field="contract_id", prefix="m24contract_"):
        issues.append("contract_self_address_drift")
    expected_identity = {
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "classification": CLASSIFICATION,
        "status": "REGISTERED_OFFLINE_NO_ADAPTER_CALL",
    }
    for field, expected in expected_identity.items():
        if contract.get(field) != expected:
            issues.append(f"contract_identity_drift:{field}")
    for field in (
        "campaign_authorized", "confirmatory_claim_authorized",
        "evaluation_opened", "source_admitted",
    ):
        if contract.get(field) is not False:
            issues.append(f"contract_boundary_opened:{field}")
    consumer = contract.get("consumer_contract")
    if not isinstance(consumer, Mapping):
        issues.append("consumer_contract_missing")
    else:
        if consumer.get("participant_rungs") != ["IA3", "IA4"]:
            issues.append("consumer_rung_drift")
        if consumer.get("tool") != _expected_tool_definition():
            issues.append("consumer_tool_schema_drift")
        if consumer.get("exact_request") != {
            "metric": METRIC, "target_ids": list(CONSUMER_TARGETS),
        }:
            issues.append("consumer_request_drift")
        if consumer.get("target_alias_map") != TARGET_ALIAS_MAP:
            issues.append("consumer_alias_drift")
        if consumer.get("consumer_payload_fields") != list(PAYLOAD_FIELDS):
            issues.append("consumer_payload_allowlist_drift")
    boundary = contract.get("access_boundary")
    if not isinstance(boundary, Mapping):
        issues.append("contract_access_boundary_missing")
    else:
        if boundary.get("real_local_read_only_adapter_authorized") is not True:
            issues.append("adapter_authorization_missing")
        for field in (
            "file_write_authorized", "model_access_authorized",
            "embedding_access_authorized", "detector_access_authorized",
            "defense_access_authorized", "network_access_authorized",
            "docker_access_authorized", "simulator_access_authorized",
            "physical_actuator_authorized", "evaluation_access_authorized",
        ):
            if boundary.get(field) is not False:
                issues.append(f"contract_access_boundary_opened:{field}")
        if boundary.get("simulation_time_advance_s") != 0.0:
            issues.append("contract_simulation_time_advance")
        if boundary.get("outer_rollout_cost") != 0:
            issues.append("contract_outer_rollout_cost")
    return sorted(set(issues))


@dataclass(frozen=True)
class AdapterInvocation:
    """One field-minimized payload plus its non-model-facing provenance."""

    payload: Mapping[str, Any]
    receipt: Mapping[str, Any]

    @property
    def payload_canonical_json(self) -> str:
        return _canonical_json(self.payload)


class EmpiricalSensitivityAdapter:
    """Read the exact M23 bytes and serve only the registered M7 scalar fields."""

    def __init__(
        self,
        *,
        contract: Mapping[str, Any],
        source_path: Path = M23_SOURCE_PATH,
        audit_path: Path = M23_AUDIT_PATH,
        read_bytes: Callable[[Path], bytes] | None = None,
    ):
        contract_issues = _contract_issues(contract)
        if contract_issues:
            raise ContractViolation(
                "M24 contract rejected: " + ",".join(contract_issues)
            )
        self.contract = _canonical_copy(contract)
        self.source_path = Path(source_path)
        self.audit_path = Path(audit_path)
        self._read_bytes = read_bytes or (lambda path: path.read_bytes())
        self._read_log: list[str] = []
        source_bytes = self._read_regular(self.source_path, "M23 source")
        audit_bytes = self._read_regular(self.audit_path, "M23 audit")
        issues: list[str] = []
        if _sha256_bytes(source_bytes) != EXPECTED_M23_SOURCE_SHA256:
            issues.append("source_file_sha256_drift")
        if _sha256_bytes(audit_bytes) != EXPECTED_M23_AUDIT_SHA256:
            issues.append("audit_file_sha256_drift")
        source = _strict_json_bytes(source_bytes, "M23 source")
        audit = _strict_json_bytes(audit_bytes, "M23 audit")
        issues.extend(_source_issues(source))
        issues.extend(_audit_issues(audit))
        if issues:
            raise ContractViolation(
                "M24 evidence rejected: " + ",".join(sorted(set(issues)))
            )
        self._source = _canonical_copy(source)
        self._audit = _canonical_copy(audit)

    def _read_regular(self, path: Path, label: str) -> bytes:
        if path.is_symlink():
            raise ContractViolation(f"{label} must not be a symlink")
        try:
            mode = path.stat().st_mode
        except OSError as exc:
            raise ContractViolation(f"{label} is unavailable") from exc
        if not stat.S_ISREG(mode):
            raise ContractViolation(f"{label} must be a regular file")
        try:
            data = self._read_bytes(path)
        except OSError as exc:
            raise ContractViolation(f"{label} is unreadable") from exc
        if not isinstance(data, bytes):
            raise ContractViolation(f"{label} reader must return bytes")
        try:
            label_path = _relative(path)
        except ValueError:
            label_path = path.resolve().as_posix()
        self._read_log.append(label_path)
        return data

    def invoke(
        self, *, arguments: Mapping[str, Any], caller_rung: str,
    ) -> AdapterInvocation:
        """Return the strict M7 payload without exposing source internals."""

        if caller_rung not in {"IA3", "IA4"}:
            raise ContractViolation("M24 caller_rung must be IA3 or IA4")
        if not isinstance(arguments, Mapping):
            raise ContractViolation("M24 tool arguments must be an object")
        tool = self.contract["consumer_contract"]["tool"]
        canonical_arguments = _canonical_copy(arguments)
        validate_strict_json_schema(canonical_arguments, tool["input_schema"])
        if canonical_arguments != self.contract["consumer_contract"]["exact_request"]:
            raise ContractViolation("M24 request bytes drift from the registered request")

        source_payload = self._source["read_only_tool_payload_candidate"]
        source_values = source_payload["values"]
        payload = {
            "schema_version": TOOL_OUTPUT_SCHEMA_VERSION,
            "window": source_payload["window"],
            "time_s": source_payload["time_s"],
            "metric": source_payload["metric"],
            "values": {
                alias: float(source_values[source_target])
                for alias, source_target in TARGET_ALIAS_MAP.items()
            },
        }
        validate_strict_json_schema(payload, tool["output_schema"])
        if set(payload) != set(PAYLOAD_FIELDS):
            raise ContractViolation("M24 consumer payload field drift")
        payload_json = _canonical_json(payload)
        if any(field in payload_json for field in FORBIDDEN_PAYLOAD_FIELDS):
            raise ContractViolation("M24 consumer payload leaked a forbidden field")
        request_json = _canonical_json(canonical_arguments)
        receipt_content = {
            "schema_version": INVOCATION_SCHEMA_VERSION,
            "contract_id": self.contract["contract_id"],
            "caller_rung": caller_rung,
            "tool_name": TOOL_NAME,
            "request_schema_version": TOOL_INPUT_SCHEMA_VERSION,
            "output_schema_version": TOOL_OUTPUT_SCHEMA_VERSION,
            "request_canonical_json": request_json,
            "request_sha256": hashlib.sha256(request_json.encode("utf-8")).hexdigest(),
            "payload_canonical_json": payload_json,
            "payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            "payload_fields": list(PAYLOAD_FIELDS),
            "target_alias_map": dict(TARGET_ALIAS_MAP),
            "source_binding": {
                "source_id": EXPECTED_M23_SOURCE_ID,
                "source_sha256": EXPECTED_M23_SOURCE_SHA256,
                "contract_id": EXPECTED_M23_CONTRACT_ID,
                "classification": CLASSIFICATION,
                "admitted": False,
                "full_internal_response_vectors_preserved_by_exact_byte_reference": True,
            },
            "audit_binding": {
                "audit_id": EXPECTED_M23_AUDIT_ID,
                "audit_sha256": EXPECTED_M23_AUDIT_SHA256,
                "status": "passed",
                "issues": [],
            },
            "files_read": list(self._read_log),
            "side_effects": {
                "class": "read_only_no_time_advance",
                "simulation_time_advance_s": 0.0,
                "outer_rollout_cost": 0,
                "file_writes": 0,
            },
            "access_boundary": {
                "real_local_read_only_adapter_executed": True,
                "external_tool_execution_used": False,
                "model_accessed": False,
                "embedding_accessed": False,
                "detector_accessed": False,
                "defense_accessed": False,
                "network_accessed": False,
                "docker_accessed": False,
                "simulator_accessed": False,
                "physical_actuator_accessed": False,
                "evaluation_accessed": False,
            },
        }
        receipt = _canonical_copy(receipt_content)
        receipt["invocation_id"] = "m24invoke_" + _sha256_value(receipt_content)
        return AdapterInvocation(
            payload=_canonical_copy(payload),
            receipt=receipt,
        )


def build_qualification_receipt(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Invoke the real local adapter once for each matched consumer rung."""

    expected_contract = build_contract()
    if _canonical_copy(contract) != expected_contract:
        raise ContractViolation("stored M24 contract drifts from current exact bytes")
    request = expected_contract["consumer_contract"]["exact_request"]
    invocations: dict[str, dict[str, Any]] = {}
    payloads: dict[str, Mapping[str, Any]] = {}
    for rung in ("IA3", "IA4"):
        adapter = EmpiricalSensitivityAdapter(contract=expected_contract)
        invocation = adapter.invoke(arguments=request, caller_rung=rung)
        invocations[rung] = {
            "payload": _canonical_copy(invocation.payload),
            "receipt": _canonical_copy(invocation.receipt),
        }
        payloads[rung] = invocation.payload

    ia3_receipt = invocations["IA3"]["receipt"]
    ia4_receipt = invocations["IA4"]["receipt"]
    parity = {
        "same_request_canonical_bytes": (
            ia3_receipt["request_canonical_json"]
            == ia4_receipt["request_canonical_json"]
        ),
        "same_request_sha256": (
            ia3_receipt["request_sha256"] == ia4_receipt["request_sha256"]
        ),
        "same_payload_canonical_bytes": (
            ia3_receipt["payload_canonical_json"]
            == ia4_receipt["payload_canonical_json"]
        ),
        "same_payload_sha256": (
            ia3_receipt["payload_sha256"] == ia4_receipt["payload_sha256"]
        ),
        "same_payload_object": payloads["IA3"] == payloads["IA4"],
        "same_side_effect_contract": (
            ia3_receipt["side_effects"] == ia4_receipt["side_effects"]
        ),
        "same_exact_two_file_reads": (
            ia3_receipt["files_read"] == ia4_receipt["files_read"]
            == expected_contract["access_boundary"]["allowed_file_reads_per_invocation"]
        ),
    }
    field_minimization = {
        "exact_top_level_fields": (
            set(payloads["IA3"]) == set(PAYLOAD_FIELDS)
        ),
        "exact_value_fields": (
            set(payloads["IA3"]["values"]) == set(CONSUMER_TARGETS)
        ),
        "forbidden_fields_absent": not any(
            field in ia3_receipt["payload_canonical_json"]
            for field in FORBIDDEN_PAYLOAD_FIELDS
        ),
        "provenance_separate_from_consumer_payload": all(
            key not in payloads["IA3"]
            for key in ("source_binding", "audit_binding", "access_boundary")
        ),
    }
    if not all(parity.values()):
        raise ContractViolation("M24 IA3/IA4 parity failed")
    if not all(field_minimization.values()):
        raise ContractViolation("M24 field minimization failed")
    content = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M24",
        "classification": CLASSIFICATION,
        "status": "passed",
        "development_only": True,
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "source_admitted": False,
        "contract_id": expected_contract["contract_id"],
        "contract_sha256": _artifact_sha256(expected_contract),
        "invocations": invocations,
        "parity": parity,
        "field_minimization": field_minimization,
        "access_seals": {
            "real_local_read_only_adapter_executed": True,
            "model_accessed": False,
            "embedding_accessed": False,
            "detector_accessed": False,
            "defense_accessed": False,
            "network_accessed": False,
            "docker_accessed": False,
            "simulator_accessed": False,
            "physical_actuator_accessed": False,
            "evaluation_accessed": False,
            "simulation_time_advance_s": 0.0,
            "outer_rollout_cost": 0,
        },
        "limitations": [
            "The M23 source remains PRELIMINARY_ONLY and unadmitted.",
            "The values cover one seed and one responsive_night operating point.",
            "The adapter qualification does not establish sensitivity stability.",
            "No LLM, attacker, detector, defense, runtime, or final claim is supported.",
        ],
    }
    receipt = _canonical_copy(content)
    receipt["qualification_id"] = "m24qual_" + _sha256_value(content)
    return receipt


def verify_qualification(root: Path) -> list[str]:
    """Verify checked-in M24 contract and receipt against current exact bytes."""

    try:
        contract = _strict_json_file(root / "contract.json", "M24 contract")
        receipt = _strict_json_file(
            root / "qualification_receipt.json", "M24 qualification receipt"
        )
        expected_contract = build_contract()
        expected_receipt = build_qualification_receipt(expected_contract)
    except (ContractViolation, OSError, TypeError, ValueError) as exc:
        return [f"M24_qualification_unreadable_or_invalid:{exc}"]
    issues: list[str] = []
    if contract != expected_contract:
        issues.append("M24_contract_content_drift")
    if receipt != expected_receipt:
        issues.append("M24_receipt_content_drift")
    if not _self_addressed(
        receipt, id_field="qualification_id", prefix="m24qual_"
    ):
        issues.append("M24_receipt_self_address_drift")
    if receipt.get("status") != "passed":
        issues.append("M24_status_not_passed")
    if receipt.get("source_admitted") is not False:
        issues.append("M24_source_admission_boundary_opened")
    if receipt.get("access_seals", {}).get("evaluation_accessed") is not False:
        issues.append("M24_evaluation_boundary_opened")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["build-contract", "run", "verify"], required=True
    )
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.mode == "build-contract":
        root.mkdir(parents=True, exist_ok=False)
        contract = build_contract()
        create_once_json(root / "contract.json", contract)
        print(json.dumps({
            "status": contract["status"],
            "contract_id": contract["contract_id"],
        }, indent=2))
        return 0
    if args.mode == "run":
        contract = _strict_json_file(root / "contract.json", "M24 contract")
        receipt = build_qualification_receipt(contract)
        create_once_json(root / "qualification_receipt.json", receipt)
        print(json.dumps({
            "status": receipt["status"],
            "qualification_id": receipt["qualification_id"],
            "payload_sha256": receipt["invocations"]["IA3"]["receipt"][
                "payload_sha256"
            ],
        }, indent=2))
        return 0
    issues = verify_qualification(root)
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
