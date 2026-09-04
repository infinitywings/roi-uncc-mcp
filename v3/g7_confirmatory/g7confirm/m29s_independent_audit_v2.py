"""Independent audit profile for the M29-S Attempt 2 provider-budget delta."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import m29s_independent_audit as base


MAX_COMPLETION_TOKENS = 1800
EXPECTED_SCHEMA = "grideval-g7-m29s-execution-contract/v2"
EXPECTED_PRIOR_CALLS = 186
EXPECTED_CUMULATIVE_CALLS = 762
EXPECTED_REMAINING_CALLS = 238
_BASE_VERIFY_CONTRACT = base._verify_contract
_BASE_VERIFY_CELL = base._verify_cell


def _verify_contract(contract: Mapping[str, Any]) -> list[str]:
    issues = _BASE_VERIFY_CONTRACT(contract)
    v1_budget_issues = {
        "contract_prior_calls",
        "contract_cumulative_calls",
        "contract_authorization_arithmetic",
    }
    issues = [value for value in issues if value not in v1_budget_issues]
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        issues.append("provider_contract_schema")
    budget = contract.get("authorization_budget", {})
    if budget.get("pre_m29s_model_calls") != 101:
        issues.append("provider_budget_pre_m29s")
    if budget.get("predecessor_attempt_calls") != 85:
        issues.append("provider_budget_predecessor")
    if budget.get("prior_model_calls") != EXPECTED_PRIOR_CALLS:
        issues.append("provider_budget_prior")
    if budget.get("contracted_new_model_calls") != 576:
        issues.append("provider_budget_contracted")
    if budget.get("maximum_cumulative_model_calls") != EXPECTED_CUMULATIVE_CALLS:
        issues.append("provider_budget_cumulative")
    if budget.get("pi_authorized_cumulative_ceiling") != 1000:
        issues.append("provider_budget_authorization")
    if budget.get("remaining_after_attempt") != EXPECTED_REMAINING_CALLS:
        issues.append("provider_budget_remaining")
    if contract.get("model_contract", {}).get(
        "maximum_completion_tokens_per_call"
    ) != MAX_COMPLETION_TOKENS:
        issues.append("provider_completion_cap")
    if contract.get("transport_profile") != {
        "workers": 4,
        "bounded_concurrency": True,
        "request_payloads_changed": False,
        "retry_count": 0,
        "schedule_bound_in_contract": True,
    }:
        issues.append("provider_transport_profile")
    predecessor = contract.get("predecessor_attempt", {})
    try:
        path = base._resolve_stored_path(predecessor["path"])
        payload = base.strict_json(path, "M29-S predecessor receipt")
        if predecessor.get("sha256") != base.sha256_file(path):
            issues.append("provider_predecessor_hash")
        if predecessor.get("id") != payload.get("predecessor_receipt_id"):
            issues.append("provider_predecessor_id")
        if payload.get("conservative_model_calls") != 85:
            issues.append("provider_predecessor_calls")
        if payload.get("held_out_cell_count") != 0:
            issues.append("provider_predecessor_heldout")
    except Exception as exc:
        issues.append(f"provider_predecessor:{type(exc).__name__}")
    return list(dict.fromkeys(issues))


def _verify_cell(
    cell: Mapping[str, Any],
    row: Mapping[str, Any],
    contract: Mapping[str, Any],
    packet: Mapping[str, Any],
    embedding: Mapping[str, Any],
) -> tuple[list[str], Mapping[str, Any] | None]:
    issues, visible = _BASE_VERIFY_CELL(
        cell, row, contract, packet, embedding
    )
    label = f"{cell.get('split')}/{cell.get('arm_id')}/{cell.get('condition_id')}"
    sampling_issue = f"model_sampling:{label}"
    request = cell.get("initial_request")
    if isinstance(request, Mapping):
        if request.get("temperature") == 0 and request.get("max_tokens") == MAX_COMPLETION_TOKENS:
            issues = [value for value in issues if value != sampling_issue]
        else:
            issues.append(f"provider_completion_budget:{label}")
        revision = cell.get("revision_request")
        if revision is not None and revision.get("max_tokens") != MAX_COMPLETION_TOKENS:
            issues.append(f"provider_revision_completion_budget:{label}")
    return list(dict.fromkeys(issues)), visible


@contextmanager
def _audit_profile() -> Iterator[None]:
    previous_contract = base._verify_contract
    previous_cell = base._verify_cell
    base._verify_contract = _verify_contract
    base._verify_cell = _verify_cell
    try:
        yield
    finally:
        base._verify_contract = previous_contract
        base._verify_cell = previous_cell


def verify(root: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    with _audit_profile():
        return base.verify(root)


def build_audit_receipt(root: Path) -> dict[str, Any]:
    issues, cells, summary = verify(root)
    contract = base.strict_json(root / "contract.json", "M29-S Attempt 2 contract")
    body = {
        "schema_version": "grideval-g7-m29s-independent-audit/v2",
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
        "staged_projection_recomputed": True,
        "semantic_endpoints_recomputed": True,
        "provider_budget_delta_recomputed": True,
        "predecessor_accounting_recomputed": True,
        "authorization_arithmetic_recomputed": True,
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
    stored = base.strict_json(path, "M29-S Attempt 2 independent audit")
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
        print(base.canonical_json({
            "audit_id": receipt["audit_id"],
            "status": receipt["status"],
            "issues": receipt["issues"],
        }))
        raise SystemExit(0 if receipt["status"] == "passed" else 1)
    issues = verify_audit_receipt(args.root.resolve())
    print(base.canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
