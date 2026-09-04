"""Independently audit M26 without importing its harness or the M24 adapter."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .manifest import create_once_json


AUDIT_SCHEMA_VERSION = "grideval-g7-m26-independent-audit/v1"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m26-live-empirical-contract/v1"
RECEIPT_SCHEMA_VERSION = "grideval-g7-m26-live-empirical-receipt/v1"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MYHTSJACSDYVE60Y80K6AJ"
DECISION_ID = "dec_01M1MYH0XYEVZA6SARSND8DJG4"
MODEL_ID = "qwen3.6-35b-a3b"
SEEDS = [8107, 8108]
EXPECTED_PROTOCOL_ID = (
    "m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff"
)
EXPECTED_SURFACE_ID = (
    "surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78"
)
EXPECTED_PAYLOAD_SHA256 = (
    "c397c90c3240643c75323a166432ea67e1cae94648ec1dff2edbc9564c52d5e8"
)
EXPECTED_ACCESS = {
    "model_transport_authorized": True,
    "network_access_authorized_for_registered_model_only": True,
    "real_local_read_only_adapter_authorized": True,
    "synthetic_fixture_injection_authorized": False,
    "external_tool_execution_authorized": False,
    "docker_access_authorized": False,
    "simulator_access_authorized": False,
    "embedding_access_authorized": False,
    "detector_access_authorized": False,
    "defense_access_authorized": False,
    "physical_actuator_authorized": False,
    "evaluation_access_authorized": False,
}
FORBIDDEN_CONSUMER_KEYS = {
    "access_boundary",
    "adapter_invocation_receipt",
    "audit_binding",
    "contract_id",
    "files_read",
    "fingerprint",
    "invocation_id",
    "result_kind",
    "source_binding",
    "target_alias_map",
}

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
M26_CODE_PATH = Path(__file__).with_name("m26_live_empirical_decision.py")
AUDITOR_PATH = Path(__file__).resolve()


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


def _strict_json_file(path: Path, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate field: {key}")
            result[key] = item
        return result

    def reject_constant(item: str) -> None:
        raise ValueError(f"{label} contains non-finite constant: {item}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def _self_addressed(value: Mapping[str, Any], field: str, prefix: str) -> bool:
    content = _canonical_copy(value)
    actual = content.pop(field, None)
    return actual == prefix + _sha256_value(content)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _check_harness_boundary() -> list[str]:
    issues: list[str] = []
    tree = ast.parse(M26_CODE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for forbidden in ("docker", "requests", "subprocess", "socket"):
        if forbidden in imported:
            issues.append(f"M26_harness_forbidden_import:{forbidden}")
    source = M26_CODE_PATH.read_text(encoding="utf-8")
    if "start_service" in source or "restart_service" in source:
        issues.append("M26_harness_service_lifecycle_token")
    auditor_tree = ast.parse(AUDITOR_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(auditor_tree):
        if isinstance(node, ast.ImportFrom) and node.module and (
            node.module.endswith("m26_live_empirical_decision")
            or node.module.endswith("m24_read_only_adapter")
        ):
            issues.append("independent_auditor_imports_execution_harness")
    return issues


def audit_qualification(root: Path) -> list[str]:
    """Return independent issue codes for one create-once M26 attempt."""

    issues = _check_harness_boundary()
    try:
        contract = _strict_json_file(root / "contract.json", "M26 contract")
        receipt = _strict_json_file(root / "receipt.json", "M26 receipt")
        actions = [
            _strict_json_file(
                root / f"action_request_seed{seed}.json", "M26 action request"
            )
            for seed in SEEDS
        ]
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return sorted(set([*issues, f"M26_artifact_unreadable_or_invalid:{exc}"]))

    if not _self_addressed(contract, "contract_id", "m26contract_"):
        issues.append("contract_content_address_drift")
    if not _self_addressed(receipt, "receipt_id", "m26receipt_"):
        issues.append("receipt_content_address_drift")
    for value, schema, label in (
        (contract, CONTRACT_SCHEMA_VERSION, "contract"),
        (receipt, RECEIPT_SCHEMA_VERSION, "receipt"),
    ):
        if value.get("schema_version") != schema:
            issues.append(f"{label}_schema_version_drift")
        if value.get("project_id") != PROJECT_ID:
            issues.append(f"{label}_project_id_drift")
        if value.get("mission_id") != MISSION_ID:
            issues.append(f"{label}_mission_id_drift")
        if value.get("decision_id") != DECISION_ID:
            issues.append(f"{label}_decision_id_drift")
        if value.get("classification") != "PRELIMINARY_ONLY":
            issues.append(f"{label}_classification_drift")
    if receipt.get("contract_id") != contract.get("contract_id"):
        issues.append("receipt_contract_id_drift")

    interface = contract.get("exact_interface", {})
    if interface.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        issues.append("protocol_identity_drift")
    if interface.get("search_surface_id") != EXPECTED_SURFACE_ID:
        issues.append("search_surface_identity_drift")
    if interface.get("tool_name") != "observe_sensitivity":
        issues.append("tool_name_drift")
    if interface.get("tool_arguments") != {
        "metric": "voltage_stress_gain_pu_per_kw",
        "target_ids": ["DER_A", "DER_B"],
    }:
        issues.append("tool_arguments_drift")
    if interface.get("call_id") != "call_m26_real_adapter_0001":
        issues.append("call_id_drift")
    control = contract.get("matched_IA3_control", {})
    if _sha256_value(control.get("consumer_payload")) != EXPECTED_PAYLOAD_SHA256:
        issues.append("preregistered_payload_drift")
    if control.get("consumer_payload_sha256") != EXPECTED_PAYLOAD_SHA256:
        issues.append("preregistered_payload_hash_drift")
    if control.get("expected_target") != "DER_B":
        issues.append("preregistered_target_drift")

    if contract.get("access_boundary") != EXPECTED_ACCESS:
        issues.append("contract_access_boundary_drift")
    if contract.get("hard_caps") != {
        "model_discovery_requests": 1,
        "completion_requests": 2,
        "real_local_adapter_invocations": 1,
        "tool_calls": 1,
        "outer_rollouts": 0,
        "simulation_time_advance_s": 0.0,
        "retry_within_attempt": 0,
    }:
        issues.append("hard_cap_drift")

    bindings = contract.get("source_bindings", {})
    if not isinstance(bindings, Mapping):
        issues.append("source_bindings_missing")
    else:
        for name, binding in bindings.items():
            if not isinstance(binding, Mapping):
                issues.append(f"source_binding_invalid:{name}")
                continue
            path_value = binding.get("path")
            if not isinstance(path_value, str):
                issues.append(f"source_binding_path_invalid:{name}")
                continue
            path = REPO_ROOT / path_value
            try:
                if _sha256_file(path) != binding.get("sha256"):
                    issues.append(f"source_binding_hash_drift:{name}")
                if path.stat().st_size != binding.get("bytes"):
                    issues.append(f"source_binding_size_drift:{name}")
            except OSError:
                issues.append(f"source_binding_unreadable:{name}")
    if bindings.get("M26_code", {}).get("path") != _relative(M26_CODE_PATH):
        issues.append("M26_code_binding_path_drift")

    if [item.get("seed") for item in actions] != SEEDS:
        issues.append("action_seed_drift")
    for seed, action in zip(SEEDS, actions):
        expected = {
            "action_id": f"m26_llm_turn_seed{seed}",
            "action_type": "local_LLM_inference",
            "partition_role": "attack_development",
            "seed": seed,
            "output_classification": "PRELIMINARY_ONLY",
            "create_once": True,
            "manifest_sha256": bindings.get("M18_gate", {}).get("sha256"),
            "code_sha256": bindings.get("M26_code", {}).get("sha256"),
            "config_sha256": bindings.get("experiment_spec", {}).get("sha256"),
            "budget_id": "m26_one_discovery_two_completions_one_real_adapter",
            "paired_benign_id": None,
            "final_evaluation_data_accessed": False,
            "physical_field_actuator": False,
            "starts_or_restarts_service": False,
            "retain_failures": True,
            "local_service_identity": (
                "qwen3.6-35b-a3b@http://ccil1s26m8hj6lws:8000/v1"
            ),
        }
        if action != expected:
            issues.append(f"action_request_drift:{seed}")
    if contract.get("action_requests") != actions:
        issues.append("contract_action_request_drift")

    result = receipt.get("result", {})
    if not isinstance(result, Mapping):
        return sorted(set([*issues, "result_missing"]))
    if result.get("status") != "passed":
        issues.append("M26_status_not_passed")
    for field, expected in {
        "network_requests": 3,
        "model_discovery_requests": 1,
        "completion_requests": 2,
        "adapter_invocations": 1,
    }.items():
        if result.get(field) != expected:
            issues.append(f"request_count_drift:{field}")
    if (result.get("model_record") or {}).get("id") != MODEL_ID:
        issues.append("model_identity_drift")
    requests = result.get("requests", [])
    if not isinstance(requests, list) or len(requests) != 2:
        issues.append("request_records_drift")
    else:
        seeds = [item.get("chat_payload", {}).get("seed") for item in requests]
        if seeds != SEEDS:
            issues.append("request_turn_seed_drift")
        for item in requests:
            if item.get("chat_request_sha256") != _sha256_value(
                item.get("chat_payload")
            ):
                issues.append("chat_request_hash_drift")
            if item.get("session_request_sha256") != item.get(
                "session_request", {}
            ).get("request_sha256"):
                issues.append("session_request_hash_drift")
    if len(result.get("completions", [])) != 2:
        issues.append("completion_records_drift")

    consumer = result.get("consumer_tool_result_event")
    if not isinstance(consumer, Mapping):
        issues.append("consumer_event_missing")
    else:
        if consumer.get("output") != control.get("consumer_payload"):
            issues.append("consumer_payload_not_byte_equal_to_IA3")
        if _sha256_value(consumer.get("output")) != EXPECTED_PAYLOAD_SHA256:
            issues.append("consumer_payload_hash_drift")
        consumer_json = _canonical_json(consumer)
        for key in FORBIDDEN_CONSUMER_KEYS:
            if key in consumer_json:
                issues.append(f"consumer_provenance_leak:{key}")
    if result.get("selected_candidate_id") != control.get(
        "expected_candidate_id"
    ):
        issues.append("candidate_agreement_failed")
    if result.get("matched_IA3_candidate_agreement") is not True:
        issues.append("matched_IA3_agreement_failed")
    if (result.get("validation") or {}).get("accepted") is not True:
        issues.append("terminal_validation_failed")

    session = result.get("session_receipt", {})
    if session.get("state") != "terminal":
        issues.append("session_not_terminal")
    if session.get("protocol_id") != EXPECTED_PROTOCOL_ID:
        issues.append("session_protocol_drift")
    tool_results = session.get("tool_results", [])
    if not isinstance(tool_results, list) or len(tool_results) != 1:
        issues.append("real_tool_result_count_drift")
    else:
        tool_result = tool_results[0]
        invocation = tool_result.get("adapter_invocation_receipt", {})
        if tool_result.get("result_kind") != "real_local_read_only_adapter":
            issues.append("real_tool_result_kind_drift")
        if tool_result.get("output") != control.get("consumer_payload"):
            issues.append("real_tool_output_drift")
        if not _self_addressed(invocation, "invocation_id", "m24invoke_"):
            issues.append("M24_invocation_content_address_drift")
        if invocation.get("payload_sha256") != EXPECTED_PAYLOAD_SHA256:
            issues.append("M24_invocation_payload_hash_drift")
        if invocation.get("caller_rung") != "IA4":
            issues.append("M24_invocation_rung_drift")
        try:
            if json.loads(invocation.get("payload_canonical_json", "")) != (
                control.get("consumer_payload")
            ):
                issues.append("M24_invocation_payload_bytes_drift")
        except json.JSONDecodeError:
            issues.append("M24_invocation_payload_bytes_invalid")
        if result.get("actual_files_read") != invocation.get("files_read"):
            issues.append("M24_file_read_provenance_drift")
    accounting = session.get("accounting", {})
    if accounting.get("model_turns") != 2 or accounting.get("tool_calls") != 1:
        issues.append("session_accounting_drift")
    if accounting.get("outer_rollouts") != 0:
        issues.append("outer_rollout_used")
    if session.get("model_transport_used") is not True:
        issues.append("session_model_transport_drift")
    if session.get("real_local_read_only_adapter_executed") is not True:
        issues.append("session_real_adapter_drift")
    if session.get("synthetic_fixture_injected") is not False:
        issues.append("session_fixture_state_drift")
    if session.get("external_tool_execution_used") is not False:
        issues.append("session_external_tool_state_drift")

    true_fields = (
        "model_transport_used",
        "real_local_read_only_adapter_executed",
    )
    false_fields = (
        "synthetic_fixture_injected",
        "external_tool_execution_used",
        "docker_accessed",
        "simulator_accessed",
        "embedding_accessed",
        "detector_accessed",
        "defense_accessed",
        "physical_actuator_accessed",
        "evaluation_accessed",
    )
    for field in true_fields:
        if result.get(field) is not True:
            issues.append(f"result_access_drift:{field}")
    for field in false_fields:
        if result.get(field) is not False:
            issues.append(f"result_access_drift:{field}")
    if result.get("final_evaluation_seeds_accessed") != []:
        issues.append("result_final_evaluation_accessed")
    for field in (
        "campaign_authorized",
        "confirmatory_claim_authorized",
        "evaluation_opened",
        "source_admitted",
        "model_service_started_or_restarted",
        "docker_accessed",
        "simulator_accessed",
        "embedding_accessed",
        "detector_accessed",
        "defense_accessed",
        "physical_actuator_accessed",
        "evaluation_accessed",
    ):
        if receipt.get(field) is not False:
            issues.append(f"receipt_access_drift:{field}")
    if receipt.get("final_evaluation_seeds_accessed") != []:
        issues.append("receipt_final_evaluation_accessed")
    return sorted(set(issues))


def build_audit_receipt(root: Path) -> dict[str, Any]:
    contract = _strict_json_file(root / "contract.json", "M26 contract")
    receipt = _strict_json_file(root / "receipt.json", "M26 receipt")
    issues = audit_qualification(root)
    content = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M26",
        "classification": "PRELIMINARY_ONLY",
        "auditor_independence": {
            "imports_M26_harness": False,
            "imports_M24_adapter": False,
            "derives_checks_from_stored_bytes": True,
        },
        "contract_id": contract.get("contract_id"),
        "receipt_id": receipt.get("receipt_id"),
        "contract_file_sha256": _sha256_file(root / "contract.json"),
        "receipt_file_sha256": _sha256_file(root / "receipt.json"),
        "auditor_code_sha256": _sha256_file(AUDITOR_PATH),
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "check_classes": [
            "content_addresses_and_lineage",
            "source_file_hashes",
            "M18_action_requests_and_development_seeds",
            "model_identity_and_transport_caps",
            "M5_M7_identity_and_terminal_validation",
            "real_M24_invocation_and_exact_payload",
            "actor_facing_provenance_separation",
            "matched_IA3_candidate_agreement",
            "resource_and_final_evaluation_seals",
            "execution_harness_static_boundary",
        ],
    }
    audit = _canonical_copy(content)
    audit["audit_id"] = "m26audit_" + _sha256_value(content)
    return audit


def verify_audit_receipt(root: Path, audit: Mapping[str, Any]) -> list[str]:
    expected = build_audit_receipt(root)
    issues = []
    if _canonical_copy(audit) != expected:
        issues.append("M26_independent_audit_receipt_content_drift")
    if not _self_addressed(audit, "audit_id", "m26audit_"):
        issues.append("M26_independent_audit_receipt_self_address_drift")
    if audit.get("status") != "passed" or audit.get("issues") != []:
        issues.append("M26_independent_audit_not_passed")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["create", "verify"], required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args(argv)
    audit_path = args.artifact_root / "independent_audit_receipt.json"
    if args.mode == "create":
        audit = build_audit_receipt(args.artifact_root)
        create_once_json(audit_path, audit)
        print(json.dumps({"audit_id": audit["audit_id"], "issues": audit["issues"]}, indent=2))
        return int(bool(audit["issues"]))
    audit = _strict_json_file(audit_path, "M26 independent audit")
    issues = verify_audit_receipt(args.artifact_root, audit)
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
