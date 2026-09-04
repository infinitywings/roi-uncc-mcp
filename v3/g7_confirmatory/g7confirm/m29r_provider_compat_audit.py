"""Independent non-importing plan audit for the M29-R Attempt 2 delta."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = "PRELIMINARY_ONLY"
ATTEMPT_1_ROOT = ROOT / "artifacts/m29r_complementarity_attempt1"
PLAN_PATH = ROOT / "m29r_attempt2_compatibility_plan.json"
DIAGNOSTIC_PATH = ROOT / "artifacts/m29r_provider_diagnostic_attempt1/receipt.json"
AUDIT_SOURCE_PATHS = (
    "m29r_attempt2_compatibility_plan.json",
    "artifacts/m29r_provider_diagnostic_attempt1/receipt.json",
    "g7confirm/m29r_campaign.py",
    "g7confirm/m29r_campaign_v2.py",
    "g7confirm/m29r_independent_audit.py",
    "g7confirm/m29r_independent_audit_v2.py",
    "g7confirm/m29r_provider_compat_audit.py",
    "tests/test_m29r_campaign_v2.py",
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(prefix: str, body: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def strict_json(path: Path, label: str) -> Any:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key in {label}: {key}")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs_hook,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"nonfinite value in {label}: {value}")
        ),
    )


def _verify_id(
    payload: Mapping[str, Any], field: str, prefix: str, issues: list[str]
) -> None:
    body = dict(payload)
    identifier = body.pop(field, None)
    if identifier != content_id(prefix, body):
        issues.append(f"content_address:{field}")


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise ValueError(f"missing literal assignment: {name}")


def _audit_attempt_1(issues: list[str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = strict_json(ATTEMPT_1_ROOT / "contract.json", "Attempt 1 contract")
    primary = strict_json(ATTEMPT_1_ROOT / "primary_receipt.json", "Attempt 1 primary")
    audit = strict_json(
        ATTEMPT_1_ROOT / "independent_audit_receipt.json", "Attempt 1 audit"
    )
    _verify_id(contract, "execution_contract_id", "m29rexec", issues)
    _verify_id(primary, "primary_receipt_id", "m29rprimary", issues)
    _verify_id(audit, "audit_id", "m29raudit", issues)
    if primary.get("status") != "failed_qualification":
        issues.append("attempt_1_primary_status")
    if audit.get("status") != "failed":
        issues.append("attempt_1_audit_status")
    if primary.get("bounded_m29b_proposal_eligible") is not False:
        issues.append("attempt_1_m29b_boundary")
    llm_cells = 0
    http_500_cells = 0
    for arm in ("IA4-D", "IA4-H", "IA4-HR"):
        for path in sorted((ATTEMPT_1_ROOT / "cells" / arm).glob("*.json")):
            llm_cells += 1
            cell = strict_json(path, path.as_posix())
            if (
                cell.get("status") == "failed_closed"
                and cell.get("failure_class")
                == "HTTPError:HTTP Error 500: Internal Server Error"
                and cell.get("model_response") is None
                and cell.get("accounting", {}).get("model_calls") == 1
                and cell.get("accounting", {}).get("model_prompt_tokens") == 0
                and cell.get("accounting", {}).get("model_completion_tokens") == 0
            ):
                http_500_cells += 1
    if llm_cells != 48 or http_500_cells != 48:
        issues.append("attempt_1_provider_failure_cardinality")
    return contract, primary, audit


def audit() -> dict[str, Any]:
    issues: list[str] = []
    plan = strict_json(PLAN_PATH, "compatibility plan")
    diagnostic = strict_json(DIAGNOSTIC_PATH, "diagnostic receipt")
    _verify_id(plan, "compatibility_plan_id", "m29rcompat", issues)
    _verify_id(diagnostic, "diagnostic_receipt_id", "m29rdiag", issues)
    contract, primary, attempt_audit = _audit_attempt_1(issues)

    expected_statuses = [500, 200, 200, 500, 200]
    probes = diagnostic.get("diagnostic_probes", [])
    if [probe.get("http_status") for probe in probes] != expected_statuses:
        issues.append("diagnostic_status_pattern")
    if diagnostic.get("diagnosis") != {
        "provider_failure_class": "unsupported_uniqueItems_in_structured_output_compiler",
        "single_factor_reproduction": True,
        "attempt_1_is_scientifically_inconclusive": True,
        "local_uniqueness_validation_present": True,
        "secondary_risk": "thinking_tokens_can_exhaust_the_640_token_completion_budget",
    }:
        issues.append("diagnostic_conclusion")
    accounting = diagnostic.get("authorization_accounting", {})
    if accounting != {
        "authorized_read_only_chat_request_ceiling": 100,
        "attempt_1_requests": 48,
        "diagnostic_requests": 5,
        "requests_used": 53,
        "requests_remaining": 47,
        "attempt_2_required_requests": 48,
        "shortfall": 1,
    }:
        issues.append("diagnostic_authorization_accounting")

    if plan.get("provider_delta") != {
        "remove_keywords_from_wire_schema": ["uniqueItems"],
        "post_response_validator_retains_uniqueness": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": False,
        "n": 1,
    }:
        issues.append("plan_provider_delta")
    if plan.get("execution_gate", {}).get("execution_authorized_under_current_ceiling") is not False:
        issues.append("plan_execution_gate")
    if plan.get("m29b_authorized") is not False:
        issues.append("plan_m29b_boundary")

    campaign_path = ROOT / "g7confirm/m29r_campaign_v2.py"
    campaign_source = campaign_path.read_text(encoding="utf-8")
    required_fragments = (
        'if key != "uniqueItems"',
        '_BASE_BUILD_MODEL_REQUEST(arm_id, bundle, embedding_receipt)',
        'request["chat_template_kwargs"] = {"enable_thinking": False}',
        'request["stream"] = False',
        'request["n"] = 1',
        'base.build_model_request = build_model_request',
    )
    if any(fragment not in campaign_source for fragment in required_fragments):
        issues.append("campaign_provider_projection_source")

    campaign_sources = _literal_assignment(campaign_path, "BOUND_SOURCE_PATHS")
    independent_path = ROOT / "g7confirm/m29r_independent_audit_v2.py"
    independent_sources = _literal_assignment(independent_path, "BOUND_SOURCE_PATHS")
    if campaign_sources != independent_sources:
        issues.append("bound_source_path_parity")
    independent_tree = ast.parse(independent_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(independent_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_modules |= {
        alias.name
        for node in ast.walk(independent_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    if any(
        "m29r_campaign" in module or "m29r_complementarity" in module
        for module in imported_modules
    ):
        issues.append("independent_auditor_import_boundary")

    expected_attempt_ids = {
        "execution_contract_id": contract.get("execution_contract_id"),
        "primary_receipt_id": primary.get("primary_receipt_id"),
        "independent_audit_id": attempt_audit.get("audit_id"),
    }
    if diagnostic.get("attempt_1", {}).get("execution_contract_id") != expected_attempt_ids["execution_contract_id"]:
        issues.append("diagnostic_attempt_contract_lineage")
    if diagnostic.get("attempt_1", {}).get("primary_receipt_id") != expected_attempt_ids["primary_receipt_id"]:
        issues.append("diagnostic_attempt_primary_lineage")
    if diagnostic.get("attempt_1", {}).get("independent_audit_id") != expected_attempt_ids["independent_audit_id"]:
        issues.append("diagnostic_attempt_audit_lineage")

    source_hashes = [
        {"path": relative, "sha256": sha256_file(ROOT / relative)}
        for relative in AUDIT_SOURCE_PATHS
    ]
    body = {
        "schema_version": "grideval-g7-m29r-provider-compatibility-audit/v1",
        "classification": CLASSIFICATION,
        "compatibility_plan_id": plan.get("compatibility_plan_id"),
        "diagnostic_receipt_id": diagnostic.get("diagnostic_receipt_id"),
        "attempt_1_ids": expected_attempt_ids,
        "source_hashes": source_hashes,
        "attempt_1_failure_recomputed": True,
        "single_factor_diagnosis_recomputed": True,
        "provider_delta_source_inspected": True,
        "bound_source_parity_recomputed": True,
        "independent_import_boundary_recomputed": True,
        "authorization_arithmetic_recomputed": True,
        "status": "passed" if not issues else "failed",
        "issues": list(dict.fromkeys(issues)),
        "attempt_2_execution_authorized": False,
        "m29b_authorized": False,
    }
    return {"audit_id": content_id("m29rcompataudit", body), **body}


def create_once_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = audit()
    if args.output:
        create_once_json(args.output, receipt)
    print(canonical_json(receipt))
    raise SystemExit(0 if receipt["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
