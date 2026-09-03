"""Run the M22 current-service regression over the exact M7 tool surface."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ia4_counterfactual import (
    build_default_m7_overlay,
    perform_m7_counterfactual_model_smoke,
    run_matched_ia3_condition,
)
from .manifest import create_once_json
from .model_client import ModelClientError
from .preliminary_only_gate import (
    LLM_SERVICE_IDENTITY,
    validate_preliminary_action_request,
)


SCHEMA_VERSION = "grideval-g7-m22-current-service-regression/v1"
CONTRACT_SCHEMA_VERSION = "grideval-g7-m22-current-service-contract/v1"
CLASSIFICATION = "PRELIMINARY_ONLY"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MHT5H0AAN0H1Z0VFHMQV40"
DECISION_ID = "dec_01M1MHSM5MRQ127GMF4HNNB777"
MODEL_ID = "qwen3.6-35b-a3b"
BASE_URL = "http://ccil1s26m8hj6lws:8000/v1"
DEVELOPMENT_SEEDS = (8105, 8106)
BUDGET_ID = "m22_one_discovery_four_completions_two_by_512_tokens"

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PACKAGE_ROOT / "experiment_spec.yaml"
M18_GATE_PATH = PACKAGE_ROOT / "artifacts" / "preliminary_only_gate_m18.json"
M7_CODE_PATH = PACKAGE_ROOT / "g7confirm" / "ia4_counterfactual.py"
M7_CONTRACT_PATH = PACKAGE_ROOT / "artifacts" / "ia4_counterfactual_contract_m7.json"
M21_ARTIFACT_PATH = (
    PACKAGE_ROOT
    / "artifacts"
    / "m21_three_window_timing_seed5103_attempt1"
    / "m21_three_window_timing.json"
)
EXPECTED_SOURCE_HASHES = {
    "experiment_spec": (
        "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"
    ),
    "M18_gate": "e31a49d758700a3d30e4d7e3d5469b831b3f52370954fa92238eac6aa4dc3e9d",
    "M7_interface_code": (
        "325b5ae4c94e420b213cb3a9036da8a2b49ec9a989bf2821c5ef37f2e617af57"
    ),
    "M7_original_contract": (
        "4cef8444c56c40ff493ed3add9847d43d9d12c72f9f1714597e7566109d26de2"
    ),
    "M21_timing_artifact": (
        "2aa7bbc10bcd20f964f9a7cbcad9a70b6058b8e652acbc68bdbea953bc7e022d"
    ),
}


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
        raise ModelClientError("M22 value is not canonical JSON") from exc


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_bindings() -> dict[str, dict[str, Any]]:
    paths = {
        "experiment_spec": SPEC_PATH,
        "M18_gate": M18_GATE_PATH,
        "M7_interface_code": M7_CODE_PATH,
        "M7_original_contract": M7_CONTRACT_PATH,
        "M21_timing_artifact": M21_ARTIFACT_PATH,
    }
    bindings: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        digest = _sha256_file(path)
        if digest != EXPECTED_SOURCE_HASHES[name]:
            raise ModelClientError(f"M22 source hash drift: {name}")
        bindings[name] = {
            "path": path.relative_to(PACKAGE_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest,
        }
    return bindings


def _load_action_requests(paths: Sequence[Path]) -> list[dict[str, Any]]:
    if len(paths) != 2:
        raise ModelClientError("M22 requires exactly two action requests")
    requests = [_load_json(path) for path in paths]
    requests.sort(key=lambda item: int(item.get("seed", -1)))
    if [item.get("seed") for item in requests] != list(DEVELOPMENT_SEEDS):
        raise ModelClientError("M22 action-request seed drift")
    code_hash = _sha256_file(Path(__file__))
    for index, request in enumerate(requests):
        issues = validate_preliminary_action_request(request)
        if issues:
            raise ModelClientError(f"M22 action request rejected: {issues}")
        seed = DEVELOPMENT_SEEDS[index]
        expected = {
            "action_id": f"m22_llm_turn_seed{seed}",
            "action_type": "local_LLM_inference",
            "partition_role": "attack_development",
            "seed": seed,
            "output_classification": CLASSIFICATION,
            "create_once": True,
            "manifest_sha256": EXPECTED_SOURCE_HASHES["M18_gate"],
            "code_sha256": code_hash,
            "config_sha256": EXPECTED_SOURCE_HASHES["experiment_spec"],
            "budget_id": BUDGET_ID,
            "paired_benign_id": None,
            "final_evaluation_data_accessed": False,
            "physical_field_actuator": False,
            "starts_or_restarts_service": False,
            "retain_failures": True,
            "local_service_identity": LLM_SERVICE_IDENTITY,
        }
        if request != expected:
            raise ModelClientError(
                f"M22 action request does not match executable bytes for {seed}"
            )
    return requests


def build_contract(action_request_paths: Sequence[Path]) -> dict[str, Any]:
    """Build the exact M22 contract before model transport."""

    action_requests = _load_action_requests(action_request_paths)
    sources = _source_bindings()
    overlay = build_default_m7_overlay(
        model_id=MODEL_ID,
        development_seeds=DEVELOPMENT_SEEDS,
        timeout_s=120.0,
    )
    m7_contract = _load_json(M7_CONTRACT_PATH)
    if (
        overlay.protocol.protocol_id != m7_contract["protocol"]["protocol_id"]
        or overlay.protocol.adapter.search_surface.search_surface_id
        != m7_contract["protocol"]["base_search_surface_id"]
    ):
        raise ModelClientError("M22 does not preserve the exact M7 shared surface")
    matched_ia3 = [
        run_matched_ia3_condition(
            protocol=overlay.protocol,
            condition=condition,
        )
        for condition in overlay.conditions
    ]
    if [item["directional_correct"] for item in matched_ia3] != [True, True]:
        raise ModelClientError("M22 matched IA3 control failed")
    content = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M22",
        "classification": CLASSIFICATION,
        "status": "REGISTERED_NO_MODEL_CALL",
        "campaign_authorized": False,
        "evaluation_opened": False,
        "model_service": {
            "identity": LLM_SERVICE_IDENTITY,
            "model_id": MODEL_ID,
            "base_url": BASE_URL,
            "must_already_be_running": True,
            "start_or_restart_allowed": False,
        },
        "source_bindings": sources,
        "M21_role": (
            "downstream_runtime_timing_prerequisite_only_not_disclosed_to_model"
        ),
        "action_requests": action_requests,
        "overlay": overlay.to_dict(),
        "exact_M7_interface": {
            "protocol_id": overlay.protocol.protocol_id,
            "search_surface_id": (
                overlay.protocol.adapter.search_surface.search_surface_id
            ),
            "candidate_ids": list(
                overlay.protocol.adapter.candidate_library.ids()
            ),
            "tool_names": sorted(
                overlay.protocol.adapter.profile.allowed_tool_names
            ),
        },
        "matched_ia3_controls": matched_ia3,
        "primary_endpoint": {
            "name": "paired_directional_candidate_switch",
            "pass_rule": (
                "both_conditions_terminal_valid_and_each_candidate_matches_"
                "fixture_argmax_and_candidate_ids_switch"
            ),
            "IA3_and_IA4_share_surface": True,
        },
        "request_caps": {
            "model_discovery": 1,
            "completions": 4,
            "output_tokens_per_completion": 512,
            "retry_within_attempt": 0,
        },
        "access_boundary": {
            "fixture_injection": True,
            "real_tool_execution": False,
            "simulator": False,
            "detector": False,
            "defense": False,
            "embedding": False,
            "physical_actuator": False,
            "final_evaluation": False,
        },
        "failure_policy": "create_once_retain_and_stop_without_retry",
        "inference_boundary": (
            "A pass establishes current-service structured protocol and causal "
            "fixture-use regression only. It does not establish autonomous "
            "strategy discovery, real-tool safety, grid harm, IA4 superiority, "
            "simulator readiness, or final evidence."
        ),
    }
    contract = _canonical_copy(content)
    contract["contract_id"] = "m22contract_" + _sha256_value(content)
    return contract


def validate_contract(
    contract: Mapping[str, Any], action_request_paths: Sequence[Path],
) -> None:
    expected = build_contract(action_request_paths)
    if _canonical_copy(contract) != expected:
        raise ModelClientError("stored M22 contract drifts from executable bytes")


def build_receipt(
    *, contract: Mapping[str, Any], result: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one live result to the preregistered decision-only contract."""

    content = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M22",
        "classification": CLASSIFICATION,
        "contract_id": contract["contract_id"],
        "model_service_identity": LLM_SERVICE_IDENTITY,
        "M21_timing_artifact_sha256": EXPECTED_SOURCE_HASHES["M21_timing_artifact"],
        "M21_evidence_disclosed_to_model": False,
        "result": _canonical_copy(result),
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "final_evaluation_seeds_accessed": [],
        "model_service_started_or_restarted": False,
        "real_tool_executed": False,
        "simulator_accessed": False,
        "detector_accessed": False,
        "defense_accessed": False,
        "embedding_accessed": False,
        "physical_actuator_accessed": False,
    }
    receipt = _canonical_copy(content)
    receipt["receipt_id"] = "m22receipt_" + _sha256_value(content)
    return receipt


def verify_receipt(
    receipt: Mapping[str, Any], contract: Mapping[str, Any],
) -> list[str]:
    """Verify self-addressing and all M22 access and qualification gates."""

    issues: list[str] = []
    content = _canonical_copy(receipt)
    receipt_id = content.pop("receipt_id", None)
    if receipt_id != "m22receipt_" + _sha256_value(content):
        issues.append("receipt_content_address_drift")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        issues.append("schema_version_drift")
    if receipt.get("contract_id") != contract.get("contract_id"):
        issues.append("contract_id_drift")
    if receipt.get("classification") != CLASSIFICATION:
        issues.append("classification_drift")
    if receipt.get("final_evaluation_seeds_accessed") != []:
        issues.append("final_evaluation_accessed")
    false_fields = (
        "campaign_authorized",
        "confirmatory_claim_authorized",
        "evaluation_opened",
        "M21_evidence_disclosed_to_model",
        "model_service_started_or_restarted",
        "real_tool_executed",
        "simulator_accessed",
        "detector_accessed",
        "defense_accessed",
        "embedding_accessed",
        "physical_actuator_accessed",
    )
    for field in false_fields:
        if receipt.get(field) is not False:
            issues.append(f"access_boundary_drift:{field}")
    result = receipt.get("result", {})
    if result.get("status") != "passed":
        issues.append("model_regression_not_passed")
    if result.get("network_requests", 0) > 5:
        issues.append("network_request_cap_exceeded")
    if result.get("completion_requests", 0) > 4:
        issues.append("completion_request_cap_exceeded")
    qualification = result.get("qualification", {})
    if qualification.get("directional_accuracy") != 1.0:
        issues.append("directional_accuracy_failed")
    if qualification.get("candidate_switched") is not True:
        issues.append("candidate_switch_failed")
    for field in (
        "tool_execution_used",
        "simulator_accessed",
        "detector_accessed",
        "embedding_accessed",
        "evaluation_accessed",
    ):
        if result.get(field) is not False:
            issues.append(f"nested_access_boundary_drift:{field}")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["build-contract", "run", "verify"],
        required=True,
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--action-request", type=Path, nargs=2, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args(argv)
    if args.base_url.rstrip("/") != BASE_URL:
        raise ModelClientError("M22 endpoint differs from the registered service")

    if args.mode == "build-contract":
        create_once_json(args.contract, build_contract(args.action_request))
        print(json.dumps({
            "status": "registered",
            "contract": str(args.contract),
        }, indent=2))
        return 0

    contract = _load_json(args.contract)
    validate_contract(contract, args.action_request)
    if args.output is None:
        parser.error("--output is required for run and verify")
    if args.mode == "run":
        overlay = build_default_m7_overlay(
            model_id=MODEL_ID,
            development_seeds=DEVELOPMENT_SEEDS,
            timeout_s=120.0,
        )
        result = perform_m7_counterfactual_model_smoke(
            base_url=BASE_URL,
            overlay=overlay,
        )
        receipt = build_receipt(contract=contract, result=result)
        create_once_json(args.output, receipt)
        issues = verify_receipt(receipt, contract)
        print(json.dumps({
            "status": result["status"],
            "receipt_id": receipt["receipt_id"],
            "issues": issues,
            "qualification": result["qualification"],
        }, indent=2))
        return int(bool(issues))

    receipt = _load_json(args.output)
    issues = verify_receipt(receipt, contract)
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
