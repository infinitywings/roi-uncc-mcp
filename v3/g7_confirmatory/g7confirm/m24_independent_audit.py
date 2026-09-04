"""Independently audit the M24 contract, adapter, and qualification receipt."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .manifest import create_once_json


AUDIT_SCHEMA_VERSION = "grideval-g7-m24-independent-audit/v1"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m24-read-only-adapter-contract/v1"
INVOCATION_SCHEMA_VERSION = "grideval-g7-m24-read-only-adapter-invocation/v1"
QUALIFICATION_SCHEMA_VERSION = "grideval-g7-m24-read-only-adapter-qualification/v1"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MTKN0P1H5V3T76MJ6HYC7E"
DECISION_ID = "dec_01M1MTJT5WZGVBWFQ5E74FKK98"
CLASSIFICATION = "PRELIMINARY_ONLY"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
ADAPTER_PATH = PACKAGE_ROOT / "g7confirm" / "m24_read_only_adapter.py"
SCHEMA_PATH = PACKAGE_ROOT / "m24_read_only_adapter.schema.json"
M7_PATH = PACKAGE_ROOT / "artifacts" / "ia4_counterfactual_contract_m7.json"
M23_ROOT = PACKAGE_ROOT / "artifacts" / "m23_system_identification_seed6101_attempt1"
SOURCE_PATH = M23_ROOT / "m23_system_identification.json"
SOURCE_AUDIT_PATH = M23_ROOT / "independent_audit_receipt.json"
EXPECTED_M7_SHA256 = "4cef8444c56c40ff493ed3add9847d43d9d12c72f9f1714597e7566109d26de2"
EXPECTED_M7_ID = "m7contract_fc1b2a552f322effb0ff27a451154699528c7f26da875e204178820d19fc45b3"
EXPECTED_M7_PROTOCOL_ID = "m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff"
EXPECTED_M7_SURFACE_ID = "surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78"
EXPECTED_SOURCE_SHA256 = "30d003e06d016b88d49e024857c9b74a9f9f34012a6f022b6f3a26511fc619c1"
EXPECTED_SOURCE_ID = "m23source_300ed1e8d0d878cd5ce932e59fa8920d8a22edba3793a9cfc5d9044ca0dd9f50"
EXPECTED_SOURCE_CONTRACT_ID = "m23contract_1fe0006a3ed480a1ef6b7a084a7031aa8855c319f02c46bfbaea42a0c45ad859"
EXPECTED_SOURCE_AUDIT_SHA256 = "d0c3a539c20cc4dc3adb2910cd7bbba9c90a071a839ebc0fcde9d9e67f524030"
EXPECTED_SOURCE_AUDIT_ID = "m23audit_f424d5ca61a12125f837a4513f6b47424b62729096c9d61a0fa50e50379a532c"
METRIC = "voltage_stress_gain_pu_per_kw"
ALIASES = {"DER_A": "DER_EV1_BESS", "DER_B": "DER_EV4_BESS"}
REQUEST = {"metric": METRIC, "target_ids": ["DER_A", "DER_B"]}
PAYLOAD_FIELDS = {"schema_version", "window", "time_s", "metric", "values"}
QUALIFICATION_FIELDS = {
    "schema_version", "project_id", "mission_id", "decision_id", "milestone",
    "classification", "status", "development_only", "campaign_authorized",
    "confirmatory_claim_authorized", "evaluation_opened", "source_admitted",
    "contract_id", "contract_sha256", "invocations", "parity",
    "field_minimization", "access_seals", "limitations", "qualification_id",
}
INVOCATION_FIELDS = {
    "schema_version", "contract_id", "caller_rung", "tool_name",
    "request_schema_version", "output_schema_version", "request_canonical_json",
    "request_sha256", "payload_canonical_json", "payload_sha256",
    "payload_fields", "target_alias_map", "source_binding", "audit_binding",
    "files_read", "side_effects", "access_boundary", "invocation_id",
}
EXPECTED_FILE_READS = [
    "v3/g7_confirmatory/artifacts/m23_system_identification_seed6101_attempt1/m23_system_identification.json",
    "v3/g7_confirmatory/artifacts/m23_system_identification_seed6101_attempt1/independent_audit_receipt.json",
]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} duplicate field: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"{label} non-finite constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def _self_addressed(
    value: Mapping[str, Any], *, id_field: str, prefix: str,
) -> bool:
    content = json.loads(_canonical_json(value))
    actual = content.pop(id_field, None)
    return actual == prefix + _sha256_value(content)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _expected_tool() -> dict[str, Any]:
    return {
        "name": "observe_sensitivity",
        "input_schema_version": "sensitivity-query/v1",
        "output_schema_version": "sensitivity-result/v1",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["metric", "target_ids"],
            "properties": {
                "metric": {"const": METRIC},
                "target_ids": {"type": "array", "const": ["DER_A", "DER_B"]},
            },
        },
        "output_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "window", "time_s", "metric", "values"],
            "properties": {
                "schema_version": {"const": "sensitivity-result/v1"},
                "window": {"type": "integer", "minimum": 0},
                "time_s": {"type": "integer", "minimum": 0},
                "metric": {"const": METRIC},
                "values": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["DER_A", "DER_B"],
                    "properties": {
                        "DER_A": {"type": "number", "minimum": 0.0, "maximum": 0.1},
                        "DER_B": {"type": "number", "minimum": 0.0, "maximum": 0.1},
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


def _check_adapter_source(issues: list[str]) -> None:
    try:
        tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        issues.append(f"adapter_source_unreadable:{exc}")
        return
    forbidden_imports = {"requests", "httpx", "openai", "docker", "socket", "subprocess"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    unexpected = sorted(forbidden_imports & imported)
    if unexpected:
        issues.append(f"adapter_forbidden_imports:{unexpected}")
    text = ADAPTER_PATH.read_text(encoding="utf-8")
    for token in ("urlopen", "Popen", "os.system"):
        if token in text:
            issues.append(f"adapter_forbidden_call_token:{token}")


def audit_qualification(root: Path) -> list[str]:
    """Audit exact M24 evidence without importing the adapter implementation."""

    issues: list[str] = []
    paths = {
        "contract": root / "contract.json",
        "receipt": root / "qualification_receipt.json",
        "source": SOURCE_PATH,
        "source_audit": SOURCE_AUDIT_PATH,
        "adapter": ADAPTER_PATH,
        "schema": SCHEMA_PATH,
        "M7": M7_PATH,
    }
    for label, path in paths.items():
        if path.is_symlink():
            issues.append(f"{label}_is_symlink")
        if not path.is_file():
            issues.append(f"{label}_missing")
    if issues:
        return sorted(set(issues))
    try:
        contract = _load_json(paths["contract"], "M24 contract")
        receipt = _load_json(paths["receipt"], "M24 receipt")
        source = _load_json(paths["source"], "M23 source")
        source_audit = _load_json(paths["source_audit"], "M23 source audit")
        schema = _load_json(paths["schema"], "M24 schema")
        m7 = _load_json(paths["M7"], "M7 contract")
    except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
        return [f"evidence_unreadable:{exc}"]
    if not all(isinstance(item, Mapping) for item in (
        contract, receipt, source, source_audit, schema, m7,
    )):
        return ["evidence_object_shape_drift"]

    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        issues.append("contract_schema_drift")
    if not _self_addressed(contract, id_field="contract_id", prefix="m24contract_"):
        issues.append("contract_self_address_drift")
    identity = {
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M24",
        "classification": CLASSIFICATION,
        "status": "REGISTERED_OFFLINE_NO_ADAPTER_CALL",
    }
    for field, expected in identity.items():
        if contract.get(field) != expected:
            issues.append(f"contract_identity_drift:{field}")
    for field in (
        "campaign_authorized", "confirmatory_claim_authorized",
        "evaluation_opened", "source_admitted",
    ):
        if contract.get(field) is not False:
            issues.append(f"contract_boundary_opened:{field}")

    bindings = contract.get("bindings", {})
    expected_bindings = {
        "adapter_code": (ADAPTER_PATH, None, None),
        "receipt_schema": (SCHEMA_PATH, None, None),
        "M7_contract": (M7_PATH, EXPECTED_M7_SHA256, "contract_id"),
        "M23_source": (SOURCE_PATH, EXPECTED_SOURCE_SHA256, "source_id"),
        "M23_independent_audit": (
            SOURCE_AUDIT_PATH, EXPECTED_SOURCE_AUDIT_SHA256, "audit_id",
        ),
    }
    for label, (path, fixed_hash, _) in expected_bindings.items():
        binding = bindings.get(label, {})
        if binding.get("path") != _relative(path):
            issues.append(f"binding_path_drift:{label}")
        actual_hash = _sha256_file(path)
        if binding.get("sha256") != actual_hash:
            issues.append(f"binding_hash_drift:{label}")
        if fixed_hash is not None and actual_hash != fixed_hash:
            issues.append(f"fixed_input_hash_drift:{label}")
    if bindings.get("M7_contract", {}).get("contract_id") != EXPECTED_M7_ID:
        issues.append("M7_contract_id_drift")
    if bindings.get("M7_contract", {}).get("protocol_id") != EXPECTED_M7_PROTOCOL_ID:
        issues.append("M7_protocol_id_drift")
    if bindings.get("M7_contract", {}).get("search_surface_id") != EXPECTED_M7_SURFACE_ID:
        issues.append("M7_surface_id_drift")
    if bindings.get("M23_source", {}).get("source_id") != EXPECTED_SOURCE_ID:
        issues.append("M23_source_id_drift")
    if bindings.get("M23_source", {}).get("contract_id") != EXPECTED_SOURCE_CONTRACT_ID:
        issues.append("M23_contract_id_drift")
    if bindings.get("M23_independent_audit", {}).get("audit_id") != EXPECTED_SOURCE_AUDIT_ID:
        issues.append("M23_audit_id_drift")

    protocol = m7.get("protocol", {})
    tools = protocol.get("enabled_tools", [])
    if (
        m7.get("contract_id") != EXPECTED_M7_ID
        or protocol.get("protocol_id") != EXPECTED_M7_PROTOCOL_ID
        or protocol.get("base_search_surface_id") != EXPECTED_M7_SURFACE_ID
        or tools != [_expected_tool()]
    ):
        issues.append("exact_M7_surface_drift")
    consumer = contract.get("consumer_contract", {})
    if consumer.get("participant_rungs") != ["IA3", "IA4"]:
        issues.append("consumer_rungs_drift")
    if consumer.get("tool") != _expected_tool():
        issues.append("consumer_tool_drift")
    if consumer.get("exact_request") != REQUEST:
        issues.append("consumer_request_drift")
    if consumer.get("target_alias_map") != ALIASES:
        issues.append("target_alias_drift")

    if _sha256_file(SOURCE_PATH) != EXPECTED_SOURCE_SHA256:
        issues.append("source_hash_drift")
    if _sha256_file(SOURCE_AUDIT_PATH) != EXPECTED_SOURCE_AUDIT_SHA256:
        issues.append("source_audit_hash_drift")
    if source.get("source_id") != EXPECTED_SOURCE_ID or not _self_addressed(
        source, id_field="source_id", prefix="m23source_"
    ):
        issues.append("source_identity_or_self_address_drift")
    if source.get("contract_id") != EXPECTED_SOURCE_CONTRACT_ID:
        issues.append("source_contract_binding_drift")
    if source.get("classification") != CLASSIFICATION:
        issues.append("source_classification_drift")
    if source.get("final_evaluation_seeds_accessed") != []:
        issues.append("source_final_evaluation_accessed")
    candidate = source.get("read_only_tool_payload_candidate", {})
    if candidate.get("empirical_source_admitted") is not False:
        issues.append("source_admission_opened")
    if set(candidate.get("values", {})) != set(ALIASES.values()):
        issues.append("source_target_drift")
    if source_audit.get("audit_id") != EXPECTED_SOURCE_AUDIT_ID or not _self_addressed(
        source_audit, id_field="audit_id", prefix="m23audit_"
    ):
        issues.append("source_audit_identity_or_self_address_drift")
    if source_audit.get("status") != "passed" or source_audit.get("issues") != []:
        issues.append("source_audit_not_clean")
    if (
        source_audit.get("source_id") != EXPECTED_SOURCE_ID
        or source_audit.get("source_sha256") != EXPECTED_SOURCE_SHA256
    ):
        issues.append("source_audit_binding_drift")

    if set(receipt) != QUALIFICATION_FIELDS:
        issues.append("qualification_field_drift")
    if receipt.get("schema_version") != QUALIFICATION_SCHEMA_VERSION:
        issues.append("qualification_schema_drift")
    if not _self_addressed(receipt, id_field="qualification_id", prefix="m24qual_"):
        issues.append("qualification_self_address_drift")
    for field, expected in identity.items():
        expected_receipt = "passed" if field == "status" else expected
        if receipt.get(field) != expected_receipt:
            issues.append(f"qualification_identity_drift:{field}")
    if receipt.get("contract_id") != contract.get("contract_id"):
        issues.append("qualification_contract_id_drift")
    if receipt.get("contract_sha256") != _sha256_file(paths["contract"]):
        issues.append("qualification_contract_hash_drift")
    for field in (
        "campaign_authorized", "confirmatory_claim_authorized",
        "evaluation_opened", "source_admitted",
    ):
        if receipt.get(field) is not False:
            issues.append(f"qualification_boundary_opened:{field}")
    if receipt.get("development_only") is not True:
        issues.append("qualification_development_boundary_drift")

    source_values = candidate.get("values", {})
    expected_payload = {
        "schema_version": "sensitivity-result/v1",
        "window": 2,
        "time_s": 30,
        "metric": METRIC,
        "values": {
            alias: source_values.get(source_target)
            for alias, source_target in ALIASES.items()
        },
    }
    expected_request_json = _canonical_json(REQUEST)
    expected_payload_json = _canonical_json(expected_payload)
    invocation_payloads: dict[str, Any] = {}
    for rung in ("IA3", "IA4"):
        wrapper = receipt.get("invocations", {}).get(rung, {})
        if set(wrapper) != {"payload", "receipt"}:
            issues.append(f"invocation_wrapper_field_drift:{rung}")
            continue
        payload = wrapper.get("payload")
        invocation = wrapper.get("receipt")
        invocation_payloads[rung] = payload
        if payload != expected_payload or set(payload or {}) != PAYLOAD_FIELDS:
            issues.append(f"payload_drift:{rung}")
        values = payload.get("values", {}) if isinstance(payload, Mapping) else {}
        if set(values) != set(ALIASES):
            issues.append(f"payload_target_drift:{rung}")
        for value in values.values():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                issues.append(f"payload_nonfinite:{rung}")
        if not isinstance(invocation, Mapping) or set(invocation) != INVOCATION_FIELDS:
            issues.append(f"invocation_field_drift:{rung}")
            continue
        if invocation.get("schema_version") != INVOCATION_SCHEMA_VERSION:
            issues.append(f"invocation_schema_drift:{rung}")
        if not _self_addressed(
            invocation, id_field="invocation_id", prefix="m24invoke_"
        ):
            issues.append(f"invocation_self_address_drift:{rung}")
        if invocation.get("caller_rung") != rung:
            issues.append(f"invocation_rung_drift:{rung}")
        if invocation.get("request_canonical_json") != expected_request_json:
            issues.append(f"invocation_request_bytes_drift:{rung}")
        if invocation.get("payload_canonical_json") != expected_payload_json:
            issues.append(f"invocation_payload_bytes_drift:{rung}")
        if invocation.get("request_sha256") != hashlib.sha256(
            expected_request_json.encode("utf-8")
        ).hexdigest():
            issues.append(f"invocation_request_hash_drift:{rung}")
        if invocation.get("payload_sha256") != hashlib.sha256(
            expected_payload_json.encode("utf-8")
        ).hexdigest():
            issues.append(f"invocation_payload_hash_drift:{rung}")
        if invocation.get("files_read") != EXPECTED_FILE_READS:
            issues.append(f"invocation_file_read_drift:{rung}")
        source_binding = invocation.get("source_binding", {})
        if (
            source_binding.get("source_id") != EXPECTED_SOURCE_ID
            or source_binding.get("source_sha256") != EXPECTED_SOURCE_SHA256
            or source_binding.get("admitted") is not False
        ):
            issues.append(f"invocation_source_binding_drift:{rung}")
        audit_binding = invocation.get("audit_binding", {})
        if (
            audit_binding.get("audit_id") != EXPECTED_SOURCE_AUDIT_ID
            or audit_binding.get("audit_sha256") != EXPECTED_SOURCE_AUDIT_SHA256
            or audit_binding.get("status") != "passed"
            or audit_binding.get("issues") != []
        ):
            issues.append(f"invocation_audit_binding_drift:{rung}")
        side_effects = invocation.get("side_effects", {})
        if side_effects != {
            "class": "read_only_no_time_advance",
            "simulation_time_advance_s": 0.0,
            "outer_rollout_cost": 0,
            "file_writes": 0,
        }:
            issues.append(f"invocation_side_effect_drift:{rung}")
        boundary = invocation.get("access_boundary", {})
        expected_boundary = {
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
        }
        if boundary != expected_boundary:
            issues.append(f"invocation_access_boundary_drift:{rung}")

    if invocation_payloads.get("IA3") != invocation_payloads.get("IA4"):
        issues.append("IA3_IA4_payload_mismatch")
    parity = receipt.get("parity", {})
    if len(parity) != 7 or any(value is not True for value in parity.values()):
        issues.append("parity_assertion_drift")
    minimization = receipt.get("field_minimization", {})
    if len(minimization) != 4 or any(
        value is not True for value in minimization.values()
    ):
        issues.append("field_minimization_assertion_drift")
    seals = receipt.get("access_seals", {})
    expected_seals = {
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
    }
    if seals != expected_seals:
        issues.append("qualification_access_seal_drift")

    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        issues.append("receipt_schema_dialect_drift")
    if set(schema.get("required", [])) != QUALIFICATION_FIELDS:
        issues.append("receipt_schema_required_fields_drift")
    properties = schema.get("properties", {})
    if set(properties) != QUALIFICATION_FIELDS:
        issues.append("receipt_schema_properties_drift")
    if schema.get("additionalProperties") is not False:
        issues.append("receipt_schema_additional_properties_opened")
    _check_adapter_source(issues)
    return sorted(set(issues))


def build_audit_receipt(root: Path) -> dict[str, Any]:
    """Build a deterministic independent-audit receipt for exact M24 bytes."""

    issues = audit_qualification(root)
    content = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "contract_sha256": _sha256_file(root / "contract.json"),
        "qualification_sha256": _sha256_file(root / "qualification_receipt.json"),
        "adapter_sha256": _sha256_file(ADAPTER_PATH),
        "schema_sha256": _sha256_file(SCHEMA_PATH),
        "auditor_sha256": _sha256_file(Path(__file__)),
        "M7_contract_sha256": _sha256_file(M7_PATH),
        "M23_source_sha256": _sha256_file(SOURCE_PATH),
        "M23_audit_sha256": _sha256_file(SOURCE_AUDIT_PATH),
        "status": "passed" if not issues else "failed_closed",
        "issues": issues,
        "checks": [
            "contract_and_receipt_self_address",
            "exact_code_schema_M7_M23_and_audit_bindings",
            "strict_receipt_topology",
            "direct_M23_scalar_derivation",
            "exact_M7_schema_and_alias_mapping",
            "IA3_IA4_canonical_request_and_payload_byte_parity",
            "consumer_field_minimization",
            "source_and_audit_governance_seals",
            "two_file_read_and_zero_side_effect_boundary",
            "adapter_static_external_access_surface",
        ],
        "claim_boundary": (
            "A passing audit qualifies only the exact M24 offline adapter "
            "transformation and isolation boundary. It does not admit the M23 "
            "source or establish sensitivity stability, attacker advantage, "
            "runtime safety, or confirmatory evidence."
        ),
    }
    receipt = json.loads(_canonical_json(content))
    receipt["audit_id"] = "m24audit_" + _sha256_value(content)
    return receipt


def verify_audit_receipt(root: Path, receipt: Mapping[str, Any]) -> list[str]:
    """Verify the independent receipt against the current exact M24 bytes."""

    issues: list[str] = []
    if not _self_addressed(receipt, id_field="audit_id", prefix="m24audit_"):
        issues.append("audit_receipt_self_address_drift")
    try:
        expected = build_audit_receipt(root)
    except (OSError, ValueError, TypeError) as exc:
        return [f"audit_rebuild_failed:{exc}"]
    if receipt != expected:
        issues.append("audit_receipt_content_drift")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["build", "verify"], required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.mode == "build":
        receipt = build_audit_receipt(root)
        create_once_json(root / "independent_audit_receipt.json", receipt)
        print(json.dumps({
            "status": receipt["status"],
            "audit_id": receipt["audit_id"],
            "issues": receipt["issues"],
        }, indent=2))
        return int(bool(receipt["issues"]))
    receipt = _load_json(
        root / "independent_audit_receipt.json", "M24 independent audit"
    )
    issues = verify_audit_receipt(root, receipt)
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
