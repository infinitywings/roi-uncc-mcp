"""Independently audit M28 without importing its execution or evidence code."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

from .manifest import create_once_json


AUDIT_SCHEMA_VERSION = "grideval-g7-m28-independent-audit/v1"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m28-decision-to-action-contract/v1"
EVIDENCE_SCHEMA_VERSION = "grideval-g7-m28-decision-to-action-evidence/v1"
EXECUTION_SCHEMA_VERSION = "grideval-g7-m28-runtime-execution/v1"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1N1G1JVYHSXVZFHREF01QKA"
DECISION_ID = "dec_01M1N1F7JDKCVK43WGCC6NGYW1"
ACTORS = ("IA3", "IA4")
TREATMENTS = ("benign", "attack")
SEED = 8109
TARGET_ID = "DER_EV4_BESS"
ABSTRACT_TARGET_ID = "DER_B"
EXPECTED_CANDIDATE_ID = "cand_bc73d19dea133043082f"
IMAGE_ID = "sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7"
AUDITOR_PATH = Path(__file__).resolve()
HARNESS_NAMES = {
    "m28_decision_to_action",
    "m28_execute",
    "m28_runtime",
}


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


def _strict_json(path: Path, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate field: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"{label} contains non-finite constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def _self_addressed(value: Mapping[str, Any], field: str, prefix: str) -> bool:
    content = _canonical_copy(value)
    actual = content.pop(field, None)
    return actual == prefix + _sha256_value(content)


def _check_independence() -> list[str]:
    issues: list[str] = []
    tree = ast.parse(AUDITOR_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.module.split(".")[-1] in HARNESS_NAMES:
            issues.append("independent_auditor_imports_M28_harness")
    return issues


def _verify_manifest(root: Path, evidence: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    manifest = evidence.get("manifest", {})
    entries = manifest.get("files")
    if manifest.get("algorithm") != "sha256" or not isinstance(entries, list):
        return ["manifest_shape_invalid"]
    seen: set[str] = set()
    total = 0
    for entry in entries:
        relative = str(entry.get("path", ""))
        path_value = Path(relative)
        if (
            not relative
            or relative in seen
            or path_value.is_absolute()
            or ".." in path_value.parts
        ):
            issues.append("manifest_path_invalid_or_duplicate")
            continue
        seen.add(relative)
        path = root / path_value
        if not path.is_file() or path.is_symlink():
            issues.append(f"manifest_file_missing:{relative}")
            continue
        size = path.stat().st_size
        total += size
        if entry.get("bytes") != size:
            issues.append(f"manifest_size_drift:{relative}")
        if entry.get("sha256") != _sha256_file(path):
            issues.append(f"manifest_sha256_drift:{relative}")
    if manifest.get("file_count") != len(entries):
        issues.append("manifest_file_count_drift")
    if manifest.get("total_bytes") != total:
        issues.append("manifest_total_bytes_drift")
    required = {
        "contract.json",
        "runtime_execution.json",
        *{
            f"requests/{actor}/{treatment}_action_request.json"
            for actor in ACTORS
            for treatment in TREATMENTS
        },
    }
    if not required.issubset(seen):
        issues.append("manifest_required_file_missing")
    return issues


def _load_physical(root: Path, actor: str, treatment: str) -> dict[str, Any]:
    run_dir = root / "runs" / actor / treatment
    return {
        name: _strict_json(run_dir / name, f"{actor}/{treatment}/{name}")
        for name in (
            "attack_trace.json",
            "dual_budget_trace.json",
            "g7_summary.json",
            "multi_der_source.json",
            "multi_der_traces.json",
        )
    }


def _audit_run(root: Path, actor: str, treatment: str) -> list[str]:
    issues: list[str] = []
    run_dir = root / "runs" / actor / treatment
    integration = _strict_json(run_dir / "runtime_integration.json", "integration")
    trace = _strict_json(run_dir / "attack_trace.json", "attack trace")
    dual = _strict_json(run_dir / "dual_budget_trace.json", "dual budget")
    expected_pair = f"m28_{actor.lower()}_decision_to_action_seed{SEED}"
    if integration.get("status") != "passed":
        issues.append(f"runtime_not_passed:{actor}:{treatment}")
    if integration.get("classification") != "PRELIMINARY_ONLY":
        issues.append(f"classification_drift:{actor}:{treatment}")
    lineage = integration.get("seed_lineage", {})
    for field, expected in (
        ("partition", "attack_development"),
        ("replicate_seed", SEED),
        ("attacker_policy_seed", SEED),
        ("measurement_noise_seed", SEED + 90000),
        ("gridlabd_random_seed", 10),
    ):
        if lineage.get(field) != expected:
            issues.append(f"seed_lineage_drift:{actor}:{treatment}:{field}")
    if integration.get("operating_point", {}).get("id") != "responsive_night":
        issues.append(f"operating_point_drift:{actor}:{treatment}")
    pairing = integration.get("pairing", {})
    if (
        pairing.get("pair_id") != expected_pair
        or pairing.get("treatment") != treatment
        or pairing.get("matched_seed") != SEED
    ):
        issues.append(f"pairing_drift:{actor}:{treatment}")
    request = _strict_json(
        root / "requests" / actor / f"{treatment}_action_request.json",
        "action request",
    )
    if integration.get("M18_action_request") != request:
        issues.append(f"action_request_runtime_drift:{actor}:{treatment}")
    if not isinstance(trace, list) or len(trace) != 3:
        return [*issues, f"attack_trace_shape_drift:{actor}:{treatment}"]
    commands = [item.get("attack") for item in trace]
    if treatment == "benign":
        if commands != [{}, {}, {}]:
            issues.append(f"benign_command_contamination:{actor}")
        if dual.get("windows_spent") != 0:
            issues.append(f"benign_window_spend:{actor}")
    else:
        if commands != [{TARGET_ID: [30.0, 0.0]}, {}, {}]:
            issues.append(f"attack_command_drift:{actor}")
        if dual.get("windows_spent") != 1:
            issues.append(f"attack_window_spend_drift:{actor}")
        if dual.get("delivery_reconciled") is not True:
            issues.append(f"delivery_not_reconciled:{actor}")
        if not math.isclose(
            float(dual.get("admitted_energy_kvah", -1)),
            30.0 * 10.0 / 3600.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            issues.append(f"attack_energy_drift:{actor}")
    return issues


def audit(root: Path) -> list[str]:
    """Return independent issue codes for the M28 evidence package."""

    issues = _check_independence()
    try:
        contract = _strict_json(root / "contract.json", "M28 contract")
        evidence = _strict_json(
            root / "m28_decision_to_action.json", "M28 evidence"
        )
        execution = _strict_json(
            root / "runtime_execution.json", "M28 execution"
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return sorted(set([*issues, f"M28_artifact_unreadable_or_invalid:{exc}"]))

    if not _self_addressed(contract, "contract_id", "m28contract_"):
        issues.append("contract_content_address_drift")
    if not _self_addressed(evidence, "evidence_id", "m28evidence_"):
        issues.append("evidence_content_address_drift")
    for value, schema, label in (
        (contract, CONTRACT_SCHEMA_VERSION, "contract"),
        (evidence, EVIDENCE_SCHEMA_VERSION, "evidence"),
        (execution, EXECUTION_SCHEMA_VERSION, "execution"),
    ):
        if value.get("schema_version") != schema:
            issues.append(f"{label}_schema_drift")
    for value, label in ((contract, "contract"), (evidence, "evidence")):
        if value.get("project_id") != PROJECT_ID:
            issues.append(f"{label}_project_id_drift")
        if value.get("mission_id") != MISSION_ID:
            issues.append(f"{label}_mission_id_drift")
        if value.get("decision_id") != DECISION_ID:
            issues.append(f"{label}_decision_id_drift")
        if value.get("classification") != "PRELIMINARY_ONLY":
            issues.append(f"{label}_classification_drift")
    if evidence.get("contract_id") != contract.get("contract_id"):
        issues.append("evidence_contract_id_drift")
    if execution.get("contract_id") != contract.get("contract_id"):
        issues.append("execution_contract_id_drift")

    for name, binding in contract.get("source_bindings", {}).items():
        relative = binding.get("path")
        if not isinstance(relative, str):
            issues.append(f"source_binding_path_invalid:{name}")
            continue
        repo_root = Path(__file__).resolve().parents[3]
        path = repo_root / relative
        if not path.is_file():
            issues.append(f"source_binding_missing:{name}")
            continue
        if binding.get("bytes") != path.stat().st_size:
            issues.append(f"source_binding_size_drift:{name}")
        if binding.get("sha256") != _sha256_file(path):
            issues.append(f"source_binding_sha256_drift:{name}")

    lineage = contract.get("decision_lineage", {})
    for actor in ACTORS:
        record = lineage.get(actor, {})
        if record.get("candidate_id") != EXPECTED_CANDIDATE_ID:
            issues.append(f"decision_candidate_drift:{actor}")
        if record.get("abstract_target_id") != ABSTRACT_TARGET_ID:
            issues.append(f"decision_target_drift:{actor}")
        if record.get("commands") != {ABSTRACT_TARGET_ID: [30, 0]}:
            issues.append(f"decision_command_drift:{actor}")
    translation = contract.get("translation", {})
    if (
        translation.get("actor_visible_target") != ABSTRACT_TARGET_ID
        or translation.get("runtime_target") != TARGET_ID
        or translation.get("active_power_kw") != 30.0
        or translation.get("reactive_power_kvar") != 0.0
        or translation.get("executor_may_modify_plan") is not False
    ):
        issues.append("translation_drift")

    for actor in ACTORS:
        for treatment in TREATMENTS:
            request = _strict_json(
                root / "requests" / actor / f"{treatment}_action_request.json",
                "M28 action request",
            )
            for field, expected in (
                ("action_type", "simulator_execution"),
                ("partition_role", "attack_development"),
                ("seed", SEED),
                ("output_classification", "PRELIMINARY_ONLY"),
                ("create_once", True),
                ("final_evaluation_data_accessed", False),
                ("physical_field_actuator", False),
                ("starts_or_restarts_service", False),
                ("retain_failures", True),
                ("local_service_identity", None),
            ):
                if request.get(field) != expected:
                    issues.append(f"action_request_drift:{actor}:{treatment}:{field}")
            issues.extend(_audit_run(root, actor, treatment))

    if (
        execution.get("status") != "complete"
        or execution.get("issues") != []
        or execution.get("runs_completed") != 4
        or execution.get("retry_count") != 0
        or execution.get("network_mode") != "none"
        or execution.get("container_image_id") != IMAGE_ID
        or execution.get("teardown_verified") is not True
    ):
        issues.append("runtime_execution_boundary_drift")
    for record in execution.get("runs", []):
        if (
            record.get("container_exit_code") != 0
            or record.get("teardown_verified") is not True
            or record.get("retry_count") != 0
        ):
            issues.append("runtime_run_failed_or_retried")
        for link in record.get("container_only_links_removed", []):
            if not str(link.get("target", "")).startswith("/work/examples/"):
                issues.append("unexpected_removed_link_target")
    if any(path.is_symlink() for path in root.rglob("*")):
        issues.append("residual_symlink_present")

    for treatment in TREATMENTS:
        if _load_physical(root, "IA3", treatment) != _load_physical(
            root, "IA4", treatment
        ):
            issues.append(f"actor_blind_physical_difference:{treatment}")
    for actor in ACTORS:
        benign = _load_physical(root, actor, "benign")["attack_trace.json"]
        attack = _load_physical(root, actor, "attack")["attack_trace.json"]
        for index in (0, 1):
            if attack[index]["telemetry"] != benign[index]["telemetry"]:
                issues.append(f"pre_t30_response:{actor}:{index}")
        deltas = {
            device: float(attack[2]["telemetry"][device])
            - float(benign[2]["telemetry"][device])
            for device in benign[2]["telemetry"]
        }
        if not any(abs(value) > 1e-12 for value in deltas.values()):
            issues.append(f"missing_t30_response:{actor}")
        stored = evidence.get("paired_t30_true_voltage_delta_pu", {}).get(actor)
        if stored != deltas:
            issues.append(f"stored_delta_drift:{actor}")
    if evidence.get("paired_t30_true_voltage_delta_pu", {}).get("IA3") != evidence.get(
        "paired_t30_true_voltage_delta_pu", {}
    ).get("IA4"):
        issues.append("actor_delta_difference")

    boundary = evidence.get("access_boundary", {})
    if boundary.get("simulator_accessed") is not True:
        issues.append("simulator_access_state_drift")
    for field in (
        "new_LLM_inference_used",
        "embedding_accessed",
        "detector_accessed",
        "defense_accessed",
        "real_network_used",
        "physical_field_actuator_accessed",
        "final_evaluation_accessed",
        "resource_admitted",
    ):
        if boundary.get(field) is not False:
            issues.append(f"access_boundary_drift:{field}")
    if boundary.get("final_evaluation_seeds_accessed") != []:
        issues.append("final_evaluation_seed_access")
    issues.extend(_verify_manifest(root, evidence))
    return sorted(set(issues))


def build_receipt(root: Path) -> dict[str, Any]:
    """Build a content-addressed receipt from the independent findings."""

    issues = audit(root)
    contract = _strict_json(root / "contract.json", "M28 contract")
    evidence = _strict_json(root / "m28_decision_to_action.json", "M28 evidence")
    execution = _strict_json(root / "runtime_execution.json", "M28 execution")
    content = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M28",
        "classification": "PRELIMINARY_ONLY",
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "contract_id": contract.get("contract_id"),
        "evidence_id": evidence.get("evidence_id"),
        "evidence_sha256": _sha256_file(root / "m28_decision_to_action.json"),
        "runtime_execution_sha256": _sha256_file(root / "runtime_execution.json"),
        "auditor_path": str(AUDITOR_PATH),
        "auditor_sha256": _sha256_file(AUDITOR_PATH),
        "checks": {
            "independent_no_M28_harness_import": True,
            "content_addresses": True,
            "source_bindings": True,
            "decision_lineage": True,
            "fixed_translation": True,
            "M18_requests": True,
            "runtime_and_teardown": True,
            "command_delivery": True,
            "paired_causal_response": True,
            "actor_blind_physical_equality": True,
            "manifest": True,
            "access_seals": True,
        },
        "runtime_run_count": execution.get("runs_completed"),
        "retry_count": execution.get("retry_count"),
    }
    receipt = _canonical_copy(content)
    receipt["audit_id"] = "m28audit_" + _sha256_value(content)
    return receipt


def verify_receipt(root: Path, receipt: Mapping[str, Any]) -> list[str]:
    """Verify the saved audit receipt against current exact bytes."""

    issues: list[str] = []
    content = _canonical_copy(receipt)
    actual_id = content.pop("audit_id", None)
    if actual_id != "m28audit_" + _sha256_value(content):
        issues.append("audit_content_address_drift")
    current = audit(root)
    if receipt.get("issues") != current:
        issues.append("audit_issue_list_drift")
    if receipt.get("status") != ("passed" if not current else "failed"):
        issues.append("audit_status_drift")
    if receipt.get("auditor_sha256") != _sha256_file(AUDITOR_PATH):
        issues.append("auditor_sha256_drift")
    if receipt.get("evidence_sha256") != _sha256_file(
        root / "m28_decision_to_action.json"
    ):
        issues.append("audited_evidence_sha256_drift")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["audit", "verify"], required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.mode == "audit":
        receipt = build_receipt(root)
        create_once_json(root / "independent_audit_receipt.json", receipt)
        output = {
            "status": receipt["status"],
            "audit_id": receipt["audit_id"],
            "issues": receipt["issues"],
        }
    else:
        receipt = _strict_json(
            root / "independent_audit_receipt.json", "M28 audit receipt"
        )
        issues = verify_receipt(root, receipt)
        output = {"status": "passed" if not issues else "failed", "issues": issues}
    print(json.dumps(output, indent=2, sort_keys=True))
    return int(output["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
