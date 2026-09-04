"""Provider-compatible create-once runner for M29-R Attempt 2.

This module deliberately reuses the frozen Attempt 1 scientific implementation
and changes only the provider-facing request representation. Attempt 1 remains
verifiable against its original source bytes.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import m29r_campaign as base


ROOT = base.ROOT
COMPATIBILITY_PLAN_PATH = ROOT / "m29r_attempt2_compatibility_plan.json"
DIAGNOSTIC_RECEIPT_PATH = (
    ROOT / "artifacts/m29r_provider_diagnostic_attempt1/receipt.json"
)
ATTEMPT_1_ROOT = ROOT / "artifacts/m29r_complementarity_attempt1"
REQUIRED_ATTEMPT_2_MODEL_CALLS = 48

BOUND_SOURCE_PATHS = (
    "m29r_complementarity_plan.json",
    "m29r_attempt2_compatibility_plan.json",
    "m29r_strategy_corpus.json",
    "m29r_retrieval_queries.json",
    "m29r_evidence_bundle.schema.json",
    "m29r_strategy_program.schema.json",
    "m29r_multistage_request.schema.json",
    "m29r_optimizer_result.schema.json",
    "m29r_attack_plan.schema.json",
    "artifacts/m29r_provider_diagnostic_attempt1/receipt.json",
    "g7confirm/m29r_complementarity.py",
    "g7confirm/m29r_campaign.py",
    "g7confirm/m29r_campaign_v2.py",
    "g7confirm/m29r_independent_audit.py",
    "g7confirm/m29r_independent_audit_v2.py",
    "g7confirm/m29r_provider_compat_audit.py",
    "tests/test_m29r_complementarity.py",
    "tests/test_m29r_campaign.py",
    "tests/test_m29r_campaign_v2.py",
)

_BASE_BUILD_MODEL_REQUEST = base.build_model_request


class M29RV2Error(RuntimeError):
    """Raised when the Attempt 2 compatibility boundary is violated."""


def _strip_provider_unsupported_keywords(value: Any) -> Any:
    """Return a JSON copy with only the unsupported uniqueItems hints removed."""

    if isinstance(value, Mapping):
        return {
            key: _strip_provider_unsupported_keywords(item)
            for key, item in value.items()
            if key != "uniqueItems"
        }
    if isinstance(value, list):
        return [_strip_provider_unsupported_keywords(item) for item in value]
    return value


def build_model_request(
    arm_id: str,
    bundle: Mapping[str, Any],
    embedding_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the frozen request with a provider-only compatibility projection."""

    request = base.canonical_copy(
        _BASE_BUILD_MODEL_REQUEST(arm_id, bundle, embedding_receipt)
    )
    schema = request["response_format"]["json_schema"]["schema"]
    request["response_format"]["json_schema"]["schema"] = (
        _strip_provider_unsupported_keywords(schema)
    )
    request["chat_template_kwargs"] = {"enable_thinking": False}
    request["stream"] = False
    request["n"] = 1
    return request


@contextmanager
def _attempt_2_profile() -> Iterator[None]:
    """Temporarily select the versioned request and source-binding profile."""

    previous_builder = base.build_model_request
    previous_sources = base.BOUND_SOURCE_PATHS
    base.build_model_request = build_model_request
    base.BOUND_SOURCE_PATHS = BOUND_SOURCE_PATHS
    try:
        yield
    finally:
        base.build_model_request = previous_builder
        base.BOUND_SOURCE_PATHS = previous_sources


def _validate_content_id(
    payload: Mapping[str, Any], field: str, prefix: str, label: str
) -> None:
    body = dict(payload)
    identifier = body.pop(field, None)
    if identifier != base.content_id(prefix, body):
        raise M29RV2Error(f"{label} content address drift")


def _load_compatibility_evidence(
    compatibility_audit_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = base.strict_json_file(COMPATIBILITY_PLAN_PATH, "M29-R compatibility plan")
    diagnostic = base.strict_json_file(
        DIAGNOSTIC_RECEIPT_PATH, "M29-R provider diagnostic"
    )
    audit = base.strict_json_file(
        compatibility_audit_path, "M29-R compatibility plan audit"
    )
    _validate_content_id(plan, "compatibility_plan_id", "m29rcompat", "plan")
    _validate_content_id(
        diagnostic, "diagnostic_receipt_id", "m29rdiag", "diagnostic"
    )
    _validate_content_id(audit, "audit_id", "m29rcompataudit", "audit")
    if audit.get("status") != "passed" or audit.get("issues") != []:
        raise M29RV2Error("compatibility plan audit did not pass")
    if audit.get("compatibility_plan_id") != plan["compatibility_plan_id"]:
        raise M29RV2Error("compatibility plan/audit lineage mismatch")
    if audit.get("diagnostic_receipt_id") != diagnostic["diagnostic_receipt_id"]:
        raise M29RV2Error("diagnostic/audit lineage mismatch")
    return plan, diagnostic, audit


def _predecessor_references() -> dict[str, Any]:
    contract_path = ATTEMPT_1_ROOT / "contract.json"
    primary_path = ATTEMPT_1_ROOT / "primary_receipt.json"
    audit_path = ATTEMPT_1_ROOT / "independent_audit_receipt.json"
    contract = base.strict_json_file(contract_path, "M29-R Attempt 1 contract")
    primary = base.strict_json_file(primary_path, "M29-R Attempt 1 primary")
    audit = base.strict_json_file(audit_path, "M29-R Attempt 1 audit")
    if primary.get("status") != "failed_qualification":
        raise M29RV2Error("Attempt 1 primary status drift")
    if audit.get("status") != "failed":
        raise M29RV2Error("Attempt 1 audit status drift")
    return {
        "execution_contract": {
            "id": contract["execution_contract_id"],
            "sha256": base.sha256_file(contract_path),
        },
        "primary_receipt": {
            "id": primary["primary_receipt_id"],
            "sha256": base.sha256_file(primary_path),
        },
        "independent_audit": {
            "id": audit["audit_id"],
            "sha256": base.sha256_file(audit_path),
        },
        "preserved": True,
        "scientific_verdict_available": False,
    }


def build_execution_contract(
    *,
    preflight_path: Path,
    embedding_receipt_path: Path,
    design_contract_path: Path,
    plan_audit_path: Path,
    compatibility_audit_path: Path,
    authorization_note_id: str,
    authorized_total_calls: int,
    prior_read_only_chat_requests: int,
) -> dict[str, Any]:
    plan, diagnostic, compatibility_audit = _load_compatibility_evidence(
        compatibility_audit_path
    )
    if prior_read_only_chat_requests != int(
        diagnostic["authorization_accounting"]["requests_used"]
    ):
        raise M29RV2Error("prior request accounting drift")
    remaining = authorized_total_calls - prior_read_only_chat_requests
    if remaining < REQUIRED_ATTEMPT_2_MODEL_CALLS:
        raise M29RV2Error(
            "authorization ceiling leaves fewer than 48 Attempt 2 model calls"
        )
    with _attempt_2_profile():
        contract = base.build_execution_contract(
            preflight_path=preflight_path,
            embedding_receipt_path=embedding_receipt_path,
            design_contract_path=design_contract_path,
            plan_audit_path=plan_audit_path,
        )
    body = dict(contract)
    body.pop("execution_contract_id")
    body["schema_version"] = "grideval-g7-m29r-execution-contract/v2"
    body["decision_id"] = "dec_01M1PFD38VVHHSMQS3M7YEECAC"
    body["compatibility_plan"] = {
        "id": plan["compatibility_plan_id"],
        "sha256": base.sha256_file(COMPATIBILITY_PLAN_PATH),
    }
    body["compatibility_plan_audit"] = {
        "id": compatibility_audit["audit_id"],
        "sha256": base.sha256_file(compatibility_audit_path),
    }
    body["predecessor_attempt"] = _predecessor_references()
    body["provider_profile"] = {
        "wire_schema_removed_keywords": ["uniqueItems"],
        "local_uniqueness_validation_retained": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": False,
        "n": 1,
        "maximum_completion_tokens": 640,
        "semantic_contract_changed": False,
    }
    body["authorization_budget"] = {
        "pi_authorization_note_id": authorization_note_id,
        "authorized_total_read_only_chat_requests": authorized_total_calls,
        "prior_read_only_chat_requests": prior_read_only_chat_requests,
        "contracted_attempt_2_requests": REQUIRED_ATTEMPT_2_MODEL_CALLS,
        "remaining_after_attempt_2": remaining - REQUIRED_ATTEMPT_2_MODEL_CALLS,
    }
    body["m29b_authorized"] = False
    return {"execution_contract_id": base.content_id("m29rexec", body), **body}


def validate_execution_contract(contract: Mapping[str, Any]) -> list[str]:
    with _attempt_2_profile():
        issues = list(base.validate_execution_contract(contract))
    if contract.get("schema_version") != "grideval-g7-m29r-execution-contract/v2":
        issues.append("execution_contract_schema_version")
    expected_profile = {
        "wire_schema_removed_keywords": ["uniqueItems"],
        "local_uniqueness_validation_retained": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": False,
        "n": 1,
        "maximum_completion_tokens": 640,
        "semantic_contract_changed": False,
    }
    if contract.get("provider_profile") != expected_profile:
        issues.append("execution_contract_provider_profile")
    budget = contract.get("authorization_budget", {})
    if int(budget.get("contracted_attempt_2_requests", -1)) != 48:
        issues.append("execution_contract_call_count")
    authorized = int(budget.get("authorized_total_read_only_chat_requests", -1))
    prior = int(budget.get("prior_read_only_chat_requests", -1))
    if authorized - prior < 48:
        issues.append("execution_contract_authorization")
    if int(budget.get("remaining_after_attempt_2", -1)) != authorized - prior - 48:
        issues.append("execution_contract_authorization_arithmetic")
    try:
        plan, diagnostic, audit = _load_compatibility_evidence(
            ROOT / "artifacts/m29r_provider_compatibility_contract/plan_audit_receipt.json"
        )
        if contract.get("compatibility_plan") != {
            "id": plan["compatibility_plan_id"],
            "sha256": base.sha256_file(COMPATIBILITY_PLAN_PATH),
        }:
            issues.append("execution_contract_compatibility_plan")
        audit_path = ROOT / "artifacts/m29r_provider_compatibility_contract/plan_audit_receipt.json"
        if contract.get("compatibility_plan_audit") != {
            "id": audit["audit_id"],
            "sha256": base.sha256_file(audit_path),
        }:
            issues.append("execution_contract_compatibility_audit")
        if diagnostic["authorization_accounting"]["requests_used"] != prior:
            issues.append("execution_contract_prior_request_count")
    except Exception as exc:
        issues.append(f"execution_contract_compatibility_evidence:{type(exc).__name__}")
    try:
        if contract.get("predecessor_attempt") != _predecessor_references():
            issues.append("execution_contract_predecessor")
    except Exception as exc:
        issues.append(f"execution_contract_predecessor:{type(exc).__name__}")
    return list(dict.fromkeys(issues))


def register_attempt(root: Path, **kwargs: Any) -> dict[str, Any]:
    contract = build_execution_contract(**kwargs)
    issues = validate_execution_contract(contract)
    if issues:
        raise M29RV2Error(f"Attempt 2 contract invalid: {issues}")
    base.create_once_json(root / "contract.json", contract)
    return contract


def execute_attempt(root: Path) -> dict[str, Any]:
    contract = base.strict_json_file(root / "contract.json", "M29-R Attempt 2 contract")
    issues = validate_execution_contract(contract)
    if issues:
        raise M29RV2Error(f"Attempt 2 contract failed pre-execution verification: {issues}")
    with _attempt_2_profile():
        return base.execute_attempt(root)


def verify_primary_receipt(root: Path) -> list[str]:
    with _attempt_2_profile():
        return base.verify_primary_receipt(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    register = subparsers.add_parser("register")
    register.add_argument("--root", type=Path, required=True)
    register.add_argument("--preflight", type=Path, required=True)
    register.add_argument("--embedding-receipt", type=Path, required=True)
    register.add_argument("--design-contract", type=Path, required=True)
    register.add_argument("--plan-audit", type=Path, required=True)
    register.add_argument("--compatibility-audit", type=Path, required=True)
    register.add_argument("--authorization-note-id", required=True)
    register.add_argument("--authorized-total-calls", type=int, required=True)
    register.add_argument("--prior-read-only-chat-requests", type=int, required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--root", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        contract = register_attempt(
            args.root,
            preflight_path=args.preflight,
            embedding_receipt_path=args.embedding_receipt,
            design_contract_path=args.design_contract,
            plan_audit_path=args.plan_audit,
            compatibility_audit_path=args.compatibility_audit,
            authorization_note_id=args.authorization_note_id,
            authorized_total_calls=args.authorized_total_calls,
            prior_read_only_chat_requests=args.prior_read_only_chat_requests,
        )
        print(base.canonical_json({"execution_contract_id": contract["execution_contract_id"]}))
    elif args.command == "execute":
        primary = execute_attempt(args.root)
        print(base.canonical_json({
            "primary_receipt_id": primary["primary_receipt_id"],
            "status": primary["status"],
            "eligible": primary["bounded_m29b_proposal_eligible"],
        }))
    else:
        issues = verify_primary_receipt(args.root)
        print(base.canonical_json({"issues": issues}))
        raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
