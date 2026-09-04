"""Independently audit the checked-in M25 offline transaction evidence.

The auditor intentionally does not import the M25 transaction harness or the
M24 adapter. It reconstructs payload and provenance expectations directly
from immutable JSON evidence and source text.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .manifest import create_once_json


AUDIT_SCHEMA_VERSION = "grideval-g7-m25-independent-audit/v1"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MVY5SHFG6Z1JJBWRPE66DM"
DECISION_ID = "dec_01M1MVXEYYVZ9CVQ19XFH7S92P"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m25-adapter-transaction-contract/v1"
QUALIFICATION_SCHEMA_VERSION = (
    "grideval-g7-m25-adapter-transaction-qualification/v1"
)
REAL_RESULT_SCHEMA_VERSION = "grideval-g7-m5-real-adapter-tool-result/v1"
CONSUMER_RESULT_SCHEMA_VERSION = "grideval-g7-ia4-tool-result/v1"
M24_INVOCATION_SCHEMA_VERSION = (
    "grideval-g7-m24-read-only-adapter-invocation/v1"
)
EXPECTED_M7_PROTOCOL_ID = (
    "m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff"
)
EXPECTED_M7_SEARCH_SURFACE_ID = (
    "surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78"
)
EXPECTED_M24_CONTRACT_ID = (
    "m24contract_c92535c44ed39b2d8f42555fee19977aebcc764fd17841c7e8a0736d7b560575"
)
EXPECTED_M23_SOURCE_SHA256 = (
    "30d003e06d016b88d49e024857c9b74a9f9f34012a6f022b6f3a26511fc619c1"
)
EXPECTED_M23_AUDIT_SHA256 = (
    "d0c3a539c20cc4dc3adb2910cd7bbba9c90a071a839ebc0fcde9d9e67f524030"
)
EXPECTED_LEGACY_RESULT_SHA256 = (
    "0a0d364173120eb25f3b7892a989e76ba897270a728e68e72ceacca0ca6629e2"
)
EXPECTED_LEGACY_RECEIPT_SHA256 = (
    "5a7af50c3b56e45238b8f96f93cbefd72813a8dc9b81faa7e1a28465ae314ff9"
)
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
AUDITOR_PATH = Path(__file__).resolve()
M25_CODE_PATH = Path(__file__).with_name("m25_adapter_transaction.py")
M5_CORE_PATH = Path(__file__).with_name("ia4_tool_loop.py")
SCHEMA_PATH = PACKAGE_ROOT / "m25_adapter_transaction.schema.json"
M23_ROOT = PACKAGE_ROOT / "artifacts" / "m23_system_identification_seed6101_attempt1"
M23_SOURCE_PATH = M23_ROOT / "m23_system_identification.json"
M23_AUDIT_PATH = M23_ROOT / "independent_audit_receipt.json"


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


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_json(path: Path) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate field: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def _artifact_sha256(value: Any) -> str:
    encoded = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _self_addressed(value: Mapping[str, Any], *, field: str, prefix: str) -> bool:
    content = _canonical_copy(value)
    actual = content.pop(field, None)
    return actual == prefix + _sha256_value(content)


def _expected_payload() -> dict[str, Any]:
    source = _strict_json(M23_SOURCE_PATH)
    source_payload = source["read_only_tool_payload_candidate"]
    return {
        "schema_version": "sensitivity-result/v1",
        "window": source_payload["window"],
        "time_s": source_payload["time_s"],
        "metric": source_payload["metric"],
        "values": {
            "DER_A": source_payload["values"]["DER_EV1_BESS"],
            "DER_B": source_payload["values"]["DER_EV4_BESS"],
        },
    }


def _audit_code_boundaries() -> list[str]:
    issues: list[str] = []
    tree = ast.parse(M25_CODE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    if not {"requests", "httpx", "openai", "docker", "socket"}.isdisjoint(
            imported):
        issues.append("M25_harness_external_service_import")
    source = M25_CODE_PATH.read_text(encoding="utf-8")
    for token in ("subprocess", "urlopen", "Popen", "os.system"):
        if token in source:
            issues.append(f"M25_harness_forbidden_call_token:{token}")
    auditor_tree = ast.parse(AUDITOR_PATH.read_text(encoding="utf-8"))
    if any(
            isinstance(node, ast.ImportFrom) and
            node.module == "m25_adapter_transaction"
            for node in ast.walk(auditor_tree)):
        issues.append("independent_auditor_imports_M25_harness")
    core = M5_CORE_PATH.read_text(encoding="utf-8")
    required_core_tokens = (
        "class RealAdapterToolResult",
        "def consumer_dict",
        "real_local_read_only_adapter_executed",
        "synthetic_fixture_injected",
        "external_tool_execution_used",
    )
    for token in required_core_tokens:
        if token not in core:
            issues.append(f"M5_real_result_path_missing:{token}")
    return issues


def _audit_binding_files(contract: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    bindings = contract.get("bindings")
    if not isinstance(bindings, Mapping):
        return ["contract_bindings_missing"]
    for name, binding in bindings.items():
        if not isinstance(binding, Mapping):
            issues.append(f"binding_not_object:{name}")
            continue
        path = binding.get("path")
        expected = binding.get("sha256")
        if not isinstance(path, str) or not isinstance(expected, str):
            issues.append(f"binding_path_or_hash_invalid:{name}")
            continue
        resolved = REPO_ROOT / path
        try:
            actual = _sha256_file(resolved)
        except OSError:
            issues.append(f"binding_file_unreadable:{name}")
            continue
        if actual != expected:
            issues.append(f"binding_file_hash_drift:{name}")
    return issues


def _audit_invocation(
        invocation: Any, *, rung: str, expected_payload: Mapping[str, Any],
        expected_request: Mapping[str, Any]) -> list[str]:
    label = f"invocation:{rung}"
    if not isinstance(invocation, Mapping):
        return [f"{label}:not_object"]
    issues: list[str] = []
    if invocation.get("schema_version") != M24_INVOCATION_SCHEMA_VERSION:
        issues.append(f"{label}:schema_drift")
    if invocation.get("contract_id") != EXPECTED_M24_CONTRACT_ID:
        issues.append(f"{label}:contract_drift")
    if invocation.get("caller_rung") != rung:
        issues.append(f"{label}:rung_drift")
    if invocation.get("tool_name") != "observe_sensitivity":
        issues.append(f"{label}:tool_drift")
    request_json = _canonical_json(expected_request)
    payload_json = _canonical_json(expected_payload)
    if invocation.get("request_canonical_json") != request_json:
        issues.append(f"{label}:request_bytes_drift")
    if invocation.get("request_sha256") != hashlib.sha256(
            request_json.encode("utf-8")).hexdigest():
        issues.append(f"{label}:request_hash_drift")
    if invocation.get("payload_canonical_json") != payload_json:
        issues.append(f"{label}:payload_bytes_drift")
    if invocation.get("payload_sha256") != hashlib.sha256(
            payload_json.encode("utf-8")).hexdigest():
        issues.append(f"{label}:payload_hash_drift")
    if invocation.get("payload_fields") != [
            "schema_version", "window", "time_s", "metric", "values"]:
        issues.append(f"{label}:payload_fields_drift")
    if invocation.get("target_alias_map") != {
            "DER_A": "DER_EV1_BESS", "DER_B": "DER_EV4_BESS"}:
        issues.append(f"{label}:alias_map_drift")
    source = invocation.get("source_binding")
    if (not isinstance(source, Mapping) or
            source.get("source_sha256") != EXPECTED_M23_SOURCE_SHA256 or
            source.get("classification") != "PRELIMINARY_ONLY" or
            source.get("admitted") is not False):
        issues.append(f"{label}:source_binding_drift")
    audit = invocation.get("audit_binding")
    if (not isinstance(audit, Mapping) or
            audit.get("audit_sha256") != EXPECTED_M23_AUDIT_SHA256 or
            audit.get("status") != "passed" or audit.get("issues") != []):
        issues.append(f"{label}:audit_binding_drift")
    if invocation.get("files_read") != [
            "v3/g7_confirmatory/artifacts/"
            "m23_system_identification_seed6101_attempt1/"
            "m23_system_identification.json",
            "v3/g7_confirmatory/artifacts/"
            "m23_system_identification_seed6101_attempt1/"
            "independent_audit_receipt.json",
    ]:
        issues.append(f"{label}:file_read_drift")
    if invocation.get("side_effects") != {
            "class": "read_only_no_time_advance",
            "simulation_time_advance_s": 0.0,
            "outer_rollout_cost": 0,
            "file_writes": 0,
    }:
        issues.append(f"{label}:side_effect_drift")
    if invocation.get("access_boundary") != {
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
    }:
        issues.append(f"{label}:access_boundary_drift")
    if not _self_addressed(
            invocation, field="invocation_id", prefix="m24invoke_"):
        issues.append(f"{label}:self_address_drift")
    return issues


def _audit_transaction(
        transaction: Any, *, rung: str, expected_payload: Mapping[str, Any],
        expected_request: Mapping[str, Any]) -> list[str]:
    label = f"transaction:{rung}"
    if not isinstance(transaction, Mapping):
        return [f"{label}:not_object"]
    issues: list[str] = []
    if transaction.get("rung") != rung:
        issues.append(f"{label}:rung_drift")
    if transaction.get("decision_core_id") != "m25_offline_argmax_replay":
        issues.append(f"{label}:decision_core_drift")
    request = transaction.get("tool_request")
    if request != {
            "schema_version": "grideval-g7-ia4-tool-request/v1",
            "protocol_id": EXPECTED_M7_PROTOCOL_ID,
            "base_search_surface_id": EXPECTED_M7_SEARCH_SURFACE_ID,
            "turn_index": 0,
            "decision": "tool_request",
            "call_id": "call_m25_real_adapter_0001",
            "tool_name": "observe_sensitivity",
            "arguments": expected_request,
            "rationale": "Acquire the shared empirical sensitivity payload.",
    }:
        issues.append(f"{label}:tool_request_drift")
    if transaction.get("tool_request_sha256") != _sha256_value(request):
        issues.append(f"{label}:tool_request_hash_drift")

    consumer = transaction.get("consumer_tool_result_event")
    expected_consumer_keys = {
        "event", "schema_version", "protocol_id", "call_id", "tool_name",
        "output_schema_version", "output", "returned_information_level",
        "simulation_time_advance_s", "outer_rollout_cost", "wall_clock_ms",
    }
    if not isinstance(consumer, Mapping):
        issues.append(f"{label}:consumer_event_missing")
    else:
        if set(consumer) != expected_consumer_keys:
            issues.append(f"{label}:consumer_event_field_drift")
        if (consumer.get("event") != "tool_result" or
                consumer.get("schema_version") != CONSUMER_RESULT_SCHEMA_VERSION or
                consumer.get("protocol_id") != EXPECTED_M7_PROTOCOL_ID or
                consumer.get("output") != expected_payload or
                consumer.get("simulation_time_advance_s") != 0.0 or
                consumer.get("outer_rollout_cost") != 0):
            issues.append(f"{label}:consumer_event_value_drift")
        encoded = _canonical_json(consumer)
        for forbidden in (
                "adapter_invocation_receipt", "access_boundary",
                "audit_binding", "source_binding", "invocation_id",
                "result_kind", "files_read", "target_alias_map"):
            if forbidden in encoded:
                issues.append(f"{label}:consumer_provenance_leak:{forbidden}")
    if transaction.get("consumer_tool_result_event_sha256") != _sha256_value(
            consumer):
        issues.append(f"{label}:consumer_event_hash_drift")

    receipt = transaction.get("session_receipt")
    if not isinstance(receipt, Mapping):
        return issues + [f"{label}:session_receipt_missing"]
    if (receipt.get("actor_rung") != rung or
            receipt.get("protocol_id") != EXPECTED_M7_PROTOCOL_ID or
            receipt.get("model_transport_used") is not False or
            receipt.get("tool_execution_used") is not True or
            receipt.get("real_local_read_only_adapter_executed") is not True or
            receipt.get("synthetic_fixture_injected") is not False or
            receipt.get("external_tool_execution_used") is not False or
            receipt.get("simulator_accessed") is not False or
            receipt.get("detector_accessed") is not False or
            receipt.get("embedding_accessed") is not False):
        issues.append(f"{label}:session_access_state_drift")
    if receipt.get("accounting") != {
            "model_turns": 2,
            "tool_calls": 1,
            "outer_rollouts": 0,
            "total_model_tokens": 0,
    }:
        issues.append(f"{label}:accounting_drift")
    calls = receipt.get("tool_calls")
    if (not isinstance(calls, list) or len(calls) != 1 or
            calls[0].get("caller_rung") != rung or
            calls[0].get("outer_rollout_cost") != 0 or
            calls[0].get("simulation_time_advance_s") != 0.0):
        issues.append(f"{label}:tool_call_drift")
    results = receipt.get("tool_results")
    if not isinstance(results, list) or len(results) != 1:
        return issues + [f"{label}:real_result_count_drift"]
    result = results[0]
    if (result.get("schema_version") != REAL_RESULT_SCHEMA_VERSION or
            result.get("result_kind") != "real_local_read_only_adapter" or
            result.get("output") != expected_payload or
            not _self_addressed(result, field="fingerprint", prefix="")):
        issues.append(f"{label}:real_result_drift")
    invocation = result.get("adapter_invocation_receipt")
    issues.extend(_audit_invocation(
        invocation,
        rung=rung,
        expected_payload=expected_payload,
        expected_request=expected_request,
    ))
    if transaction.get("adapter_invocation_receipt_sha256") != _sha256_value(
            invocation):
        issues.append(f"{label}:invocation_receipt_hash_drift")
    if transaction.get("actual_files_read") != invocation.get("files_read"):
        issues.append(f"{label}:actual_read_log_drift")
    if (transaction.get("selected_target") != "DER_B" or
            transaction.get("validation", {}).get("accepted") is not True):
        issues.append(f"{label}:selection_or_validation_drift")
    transcript = receipt.get("transcript")
    if not isinstance(transcript, list) or consumer not in transcript:
        issues.append(f"{label}:consumer_event_not_in_transcript")
    return issues


def audit_qualification(root: Path) -> list[str]:
    """Return independent issue codes for one M25 artifact directory."""

    try:
        contract = _strict_json(root / "contract.json")
        qualification = _strict_json(root / "qualification_receipt.json")
        expected_payload = _expected_payload()
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        return [f"M25_artifact_unreadable_or_invalid:{exc}"]
    issues: list[str] = []
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        issues.append("contract_schema_drift")
    if not _self_addressed(contract, field="contract_id", prefix="m25contract_"):
        issues.append("contract_self_address_drift")
    if (contract.get("project_id") != PROJECT_ID or
            contract.get("mission_id") != MISSION_ID or
            contract.get("decision_id") != DECISION_ID):
        issues.append("contract_governance_identity_drift")
    if (contract.get("source_admitted") is not False or
            contract.get("evaluation_opened") is not False or
            contract.get("campaign_authorized") is not False):
        issues.append("contract_scientific_boundary_opened")
    anchors = contract.get("legacy_compatibility_anchors")
    if anchors != {
            "fixture_result_sha256": EXPECTED_LEGACY_RESULT_SHA256,
            "fixture_episode_receipt_sha256": EXPECTED_LEGACY_RECEIPT_SHA256,
    }:
        issues.append("legacy_fixture_anchor_drift")
    issues.extend(_audit_binding_files(contract))

    if qualification.get("schema_version") != QUALIFICATION_SCHEMA_VERSION:
        issues.append("qualification_schema_drift")
    if not _self_addressed(
            qualification, field="qualification_id", prefix="m25qual_"):
        issues.append("qualification_self_address_drift")
    if qualification.get("contract_id") != contract.get("contract_id"):
        issues.append("qualification_contract_identity_drift")
    if qualification.get("contract_sha256") != _artifact_sha256(contract):
        issues.append("qualification_contract_hash_drift")
    if (qualification.get("status") != "passed" or
            qualification.get("source_admitted") is not False or
            qualification.get("evaluation_opened") is not False or
            qualification.get("campaign_authorized") is not False):
        issues.append("qualification_boundary_drift")

    expected_request = {
        "metric": "voltage_stress_gain_pu_per_kw",
        "target_ids": ["DER_A", "DER_B"],
    }
    transactions = qualification.get("transactions")
    if not isinstance(transactions, Mapping) or set(transactions) != {"IA3", "IA4"}:
        issues.append("transaction_topology_drift")
    else:
        for rung in ("IA3", "IA4"):
            issues.extend(_audit_transaction(
                transactions[rung],
                rung=rung,
                expected_payload=expected_payload,
                expected_request=expected_request,
            ))
        ia3 = transactions["IA3"]
        ia4 = transactions["IA4"]
        if (ia3.get("tool_request") != ia4.get("tool_request") or
                ia3.get("consumer_tool_result_event") !=
                ia4.get("consumer_tool_result_event") or
                ia3.get("selected_target") != ia4.get("selected_target") or
                ia3.get("selected_candidate_id") !=
                ia4.get("selected_candidate_id")):
            issues.append("IA3_IA4_consumer_parity_drift")
    parity = qualification.get("parity")
    if not isinstance(parity, Mapping) or not parity or not all(
            value is True for value in parity.values()):
        issues.append("declared_parity_not_all_true")
    separation = qualification.get("provenance_separation")
    if not isinstance(separation, Mapping) or not separation or not all(
            value is True for value in separation.values()):
        issues.append("declared_provenance_separation_not_all_true")
    seals = qualification.get("access_seals")
    if (not isinstance(seals, Mapping) or
            seals.get("real_local_read_only_adapter_executed") is not True or
            seals.get("synthetic_fixture_injected") is not False or
            seals.get("external_tool_execution_used") is not False or
            seals.get("model_transport_used") is not False or
            seals.get("simulator_accessed") is not False or
            seals.get("evaluation_accessed") is not False or
            seals.get("outer_rollout_cost") != 0 or
            seals.get("simulation_time_advance_s") != 0.0):
        issues.append("qualification_access_seal_drift")
    issues.extend(_audit_code_boundaries())
    return sorted(set(issues))


def build_audit_receipt(root: Path) -> dict[str, Any]:
    issues = audit_qualification(root)
    contract = _strict_json(root / "contract.json")
    qualification = _strict_json(root / "qualification_receipt.json")
    content = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "status": "passed" if not issues else "failed_closed",
        "issues": issues,
        "contract_sha256": _sha256_file(root / "contract.json"),
        "qualification_sha256": _sha256_file(
            root / "qualification_receipt.json"
        ),
        "contract_id": contract.get("contract_id"),
        "qualification_id": qualification.get("qualification_id"),
        "M25_code_sha256": _sha256_file(M25_CODE_PATH),
        "M5_core_sha256": _sha256_file(M5_CORE_PATH),
        "auditor_sha256": _sha256_file(AUDITOR_PATH),
        "schema_sha256": _sha256_file(SCHEMA_PATH),
        "checks": [
            "independent_content_address_and_governance",
            "exact_file_binding_hashes",
            "legacy_fixture_byte_anchors",
            "direct_M23_to_consumer_payload_derivation",
            "M24_invocation_self_address_and_bindings",
            "real_result_self_address_and_transaction_lineage",
            "model_facing_provenance_separation",
            "IA3_IA4_consumer_byte_parity",
            "real_fixture_external_execution_distinction",
            "offline_code_and_access_boundary",
        ],
        "claim_boundary": (
            "An empty issue list establishes offline M24-to-M5 transaction "
            "integration, provenance separation, and matched consumer parity "
            "only. It does not admit the M23 source or establish live-LLM, "
            "physical-impact, defense, runtime, or confirmatory performance."
        ),
    }
    receipt = _canonical_copy(content)
    receipt["audit_id"] = "m25audit_" + _sha256_value(content)
    return receipt


def verify_audit_receipt(root: Path, receipt: Mapping[str, Any]) -> list[str]:
    expected = build_audit_receipt(root)
    issues: list[str] = []
    if _canonical_copy(receipt) != expected:
        issues.append("M25_independent_audit_receipt_content_drift")
    if not _self_addressed(receipt, field="audit_id", prefix="m25audit_"):
        issues.append("M25_independent_audit_receipt_self_address_drift")
    if receipt.get("status") != "passed" or receipt.get("issues") != []:
        issues.append("M25_independent_audit_not_passed")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["audit", "verify"], required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.mode == "audit":
        receipt = build_audit_receipt(root)
        create_once_json(root / "independent_audit_receipt.json", receipt)
        print(json.dumps({
            "status": receipt["status"],
            "issues": receipt["issues"],
            "audit_id": receipt["audit_id"],
        }, indent=2))
        return int(bool(receipt["issues"]))
    try:
        receipt = _strict_json(root / "independent_audit_receipt.json")
        issues = verify_audit_receipt(root, receipt)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        issues = [f"M25_independent_audit_unreadable_or_invalid:{exc}"]
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
