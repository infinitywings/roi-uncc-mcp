"""Independent audit profile for the M29-S Attempt 4 oracle correction."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import m29s_independent_audit_v3 as v3


base = v3.base
EXPECTED_SCHEMA = "grideval-g7-m29s-execution-contract/v4"
EXPECTED_DECISION = "dec_01M1PSBNQ8VKKNK4H470SKEJYX"
EXPECTED_PLAN_GATE = "chk_01M1PSVJ4H3TR34G3ZN14Z1HAC"
AMENDMENT_PATH = base.ROOT / "m29s_attempt4_oracle_control_plan.json"
_BASE_VERIFY_CONTRACT = v3._BASE_VERIFY_CONTRACT


def _verify_contract(contract: Mapping[str, Any]) -> list[str]:
    """Recompute the v4 contract without importing primary campaign code."""

    issues = _BASE_VERIFY_CONTRACT(contract)
    issues = [
        value
        for value in issues
        if value
        not in {
            "contract_prior_calls",
            "contract_cumulative_calls",
            "contract_authorization_arithmetic",
        }
    ]
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        issues.append("oracle_contract_schema")
    if contract.get("decision_id") != EXPECTED_DECISION:
        issues.append("oracle_contract_decision")
    if contract.get("plan_gate_id") != EXPECTED_PLAN_GATE:
        issues.append("oracle_contract_plan_gate")
    budget = contract.get("authorization_budget", {})
    expected_budget = {
        "pre_m29s_model_calls": 101,
        "attempt1_conservative_calls": 85,
        "attempt2_conservative_calls": 36,
        "attempt3_conservative_calls": 18,
        "prior_model_calls": 240,
        "contracted_new_model_calls": 576,
        "maximum_cumulative_model_calls": 816,
        "pi_authorized_cumulative_ceiling": 1000,
        "remaining_after_attempt": 184,
    }
    for key, value in expected_budget.items():
        if budget.get(key) != value:
            issues.append(f"oracle_budget:{key}")
    model = contract.get("model_contract", {})
    if model.get("maximum_completion_tokens_per_call") != 1800:
        issues.append("oracle_completion_cap")
    if model.get("prior_cumulative_calls") != 240:
        issues.append("oracle_model_prior_calls")
    if model.get("maximum_cumulative_calls") != 816:
        issues.append("oracle_model_cumulative_calls")
    if contract.get("ledger_authority_contract") != {
        "source": "active visible records only",
        "ordering": list(v3.AUTHORITY_ORDER),
        "include_absent_authorities": False,
    }:
        issues.append("oracle_ledger_authority_contract")
    validator_slots = set(
        contract.get("tool_contract", {}).get("validator_result_slots", [])
    )
    if not v3.ADDITIONAL_DIAGNOSTIC_SLOTS.issubset(validator_slots):
        issues.append("oracle_validator_coverage")
    if contract.get("transport_profile") != {
        "workers": 4,
        "bounded_concurrency": True,
        "request_payloads_changed": False,
        "retry_count": 0,
        "schedule_bound_in_contract": True,
    }:
        issues.append("oracle_transport_profile")
    amendment = contract.get("oracle_control_amendment", {})
    try:
        if amendment.get("sha256") != base.sha256_file(AMENDMENT_PATH):
            issues.append("oracle_amendment_hash")
    except OSError:
        issues.append("oracle_amendment_absent")
    predecessor = contract.get("predecessor_attempt", {})
    try:
        path = base._resolve_stored_path(predecessor["path"])
        payload = base.strict_json(path, "M29-S Attempt 3 stop receipt")
        if predecessor.get("sha256") != base.sha256_file(path):
            issues.append("oracle_predecessor_hash")
        if predecessor.get("id") != payload.get("predecessor_receipt_id"):
            issues.append("oracle_predecessor_id")
        if payload.get("conservative_model_calls") != 18:
            issues.append("oracle_predecessor_calls")
        if payload.get("held_out_cell_count") != 0:
            issues.append("oracle_predecessor_heldout")
    except Exception as exc:
        issues.append(f"oracle_predecessor:{type(exc).__name__}")
    return list(dict.fromkeys(issues))


@contextmanager
def _audit_profile() -> Iterator[None]:
    previous = v3._verify_contract
    v3._verify_contract = _verify_contract
    try:
        yield
    finally:
        v3._verify_contract = previous


def verify(root: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    with _audit_profile():
        return v3.verify(root)


def build_audit_receipt(root: Path) -> dict[str, Any]:
    issues, cells, summary = verify(root)
    contract = base.strict_json(root / "contract.json", "M29-S Attempt 4 contract")
    body = {
        "schema_version": "grideval-g7-m29s-independent-audit/v4",
        "classification": base.CLASSIFICATION,
        "execution_contract_id": contract.get("execution_contract_id"),
        "auditor_source_sha256": base.sha256_file(Path(__file__).resolve()),
        "independent_imports_campaign": False,
        "independent_imports_semantic_compiler": False,
        "source_hashes_recomputed": True,
        "content_addresses_recomputed": True,
        "embedding_top_k_recomputed": True,
        "visible_input_lineage_recomputed": True,
        "factorial_request_parity_recomputed": True,
        "active_authority_ledger_recomputed": True,
        "staged_projection_recomputed": True,
        "semantic_endpoints_recomputed": True,
        "validator_nonleakage_recomputed": True,
        "predecessor_accounting_recomputed": True,
        "authorization_arithmetic_recomputed": True,
        "oracle_control_recomputed": True,
        "cell_count": len(cells),
        "model_calls": sum(
            row.get("accounting", {}).get("model_calls", 0) for row in cells
        ),
        "scientific_summary": summary,
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "m29b_authorized": False,
    }
    return {"audit_id": base.content_id("m29saudit", body), **body}


def verify_audit_receipt(root: Path) -> list[str]:
    path = root / "independent_audit_receipt.json"
    if not path.is_file():
        return ["missing_independent_audit_receipt"]
    stored = base.strict_json(path, "M29-S Attempt 4 independent audit")
    rebuilt = build_audit_receipt(root)
    return [] if base.canonical_json(stored) == base.canonical_json(rebuilt) else [
        "independent_audit_receipt_mismatch"
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        receipt = build_audit_receipt(args.root.resolve())
        base.create_once_json(
            args.root.resolve() / "independent_audit_receipt.json", receipt
        )
        print(
            base.canonical_json(
                {
                    "audit_id": receipt["audit_id"],
                    "status": receipt["status"],
                    "issues": receipt["issues"],
                }
            )
        )
        raise SystemExit(0 if receipt["status"] == "passed" else 1)
    issues = verify_audit_receipt(args.root.resolve())
    print(base.canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
