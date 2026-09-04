"""Independent audit profile for the M29-S Attempt 3 interface correction."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import m29s_independent_audit as base


MAX_COMPLETION_TOKENS = 1800
EXPECTED_SCHEMA = "grideval-g7-m29s-execution-contract/v3"
EXPECTED_PRIOR_CALLS = 222
EXPECTED_CUMULATIVE_CALLS = 798
EXPECTED_REMAINING_CALLS = 202
AUTHORITY_ORDER = ("emergency", "operator", "planning", "advisory")
ADDITIONAL_DIAGNOSTIC_SLOTS = {"evidence_ledger", "semantic_slots"}
_BASE_VERIFY_CONTRACT = base._verify_contract
_BASE_VERIFY_CELL = base._verify_cell
_BASE_SCORE = base._score


def _verify_contract(contract: Mapping[str, Any]) -> list[str]:
    issues = _BASE_VERIFY_CONTRACT(contract)
    v1_budget_issues = {
        "contract_prior_calls",
        "contract_cumulative_calls",
        "contract_authorization_arithmetic",
    }
    issues = [value for value in issues if value not in v1_budget_issues]
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        issues.append("interface_contract_schema")
    budget = contract.get("authorization_budget", {})
    expected_budget = {
        "pre_m29s_model_calls": 101,
        "attempt1_conservative_calls": 85,
        "attempt2_conservative_calls": 36,
        "prior_model_calls": EXPECTED_PRIOR_CALLS,
        "contracted_new_model_calls": 576,
        "maximum_cumulative_model_calls": EXPECTED_CUMULATIVE_CALLS,
        "pi_authorized_cumulative_ceiling": 1000,
        "remaining_after_attempt": EXPECTED_REMAINING_CALLS,
    }
    for key, value in expected_budget.items():
        if budget.get(key) != value:
            issues.append(f"interface_budget:{key}")
    if contract.get("model_contract", {}).get(
        "maximum_completion_tokens_per_call"
    ) != MAX_COMPLETION_TOKENS:
        issues.append("interface_completion_cap")
    if contract.get("ledger_authority_contract") != {
        "source": "active visible records only",
        "ordering": list(AUTHORITY_ORDER),
        "include_absent_authorities": False,
    }:
        issues.append("interface_ledger_authority_contract")
    validator_slots = set(
        contract.get("tool_contract", {}).get("validator_result_slots", [])
    )
    if not ADDITIONAL_DIAGNOSTIC_SLOTS.issubset(validator_slots):
        issues.append("interface_validator_coverage")
    if contract.get("transport_profile") != {
        "workers": 4,
        "bounded_concurrency": True,
        "request_payloads_changed": False,
        "retry_count": 0,
        "schedule_bound_in_contract": True,
    }:
        issues.append("interface_transport_profile")
    predecessor = contract.get("predecessor_attempt", {})
    try:
        path = base._resolve_stored_path(predecessor["path"])
        payload = base.strict_json(path, "M29-S Attempt 2 stop receipt")
        if predecessor.get("sha256") != base.sha256_file(path):
            issues.append("interface_predecessor_hash")
        if predecessor.get("id") != payload.get("predecessor_receipt_id"):
            issues.append("interface_predecessor_id")
        if payload.get("conservative_model_calls") != 36:
            issues.append("interface_predecessor_calls")
        if payload.get("held_out_cell_count") != 0:
            issues.append("interface_predecessor_heldout")
    except Exception as exc:
        issues.append(f"interface_predecessor:{type(exc).__name__}")
    return list(dict.fromkeys(issues))


def _score(
    draft: Mapping[str, Any] | None,
    interface: str,
    oracle: Mapping[str, Any],
    visible: Mapping[str, Any],
) -> dict[str, Any]:
    result = _BASE_SCORE(draft, interface, oracle, visible)
    if interface != "staged":
        return result
    records = visible["visible_evidence"]["records"]
    active_authorities = {row["authority"] for row in records if row["status"] == "active"}
    expected_authorities = [
        value for value in AUTHORITY_ORDER if value in active_authorities
    ]
    ledger = draft.get("evidence_ledger") if isinstance(draft, Mapping) else None
    ledger_exact = bool(
        isinstance(ledger, Mapping)
        and ledger.get("authority_order") == expected_authorities
        and sorted(ledger.get("active_evidence_ids", []))
        == sorted(row["record_id"] for row in records if row["status"] == "active")
        and sorted(ledger.get("superseded_evidence_ids", []))
        == sorted(row["record_id"] for row in records if row["status"] == "superseded")
        and sorted(ledger.get("expired_evidence_ids", []))
        == sorted(row["record_id"] for row in records if row["status"] == "expired")
        and ledger.get("unresolved_conflict_ids") == []
        and ledger.get("condition_id") == visible["visible_evidence"]["condition_id"]
        and ledger.get("visible_input_digest") == base.sha256_value(visible)
    )
    result["evidence_ledger_exact"] = ledger_exact
    result["all_slot_program_exact"] = bool(
        result["program_semantics_exact"]
        and result["evidence_lineage_exact"]
        and ledger_exact
    )
    return result


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
        if request.get("temperature") == 0 and request.get("max_tokens") == 1800:
            issues = [value for value in issues if value != sampling_issue]
        else:
            issues.append(f"interface_completion_budget:{label}")
        revision = cell.get("revision_request")
        if revision is not None and revision.get("max_tokens") != 1800:
            issues.append(f"interface_revision_completion_budget:{label}")
    return list(dict.fromkeys(issues)), visible


@contextmanager
def _audit_profile() -> Iterator[None]:
    previous = {
        "contract": base._verify_contract,
        "cell": base._verify_cell,
        "score": base._score,
        "slots": base.VALIDATOR_SLOTS,
    }
    base._verify_contract = _verify_contract
    base._verify_cell = _verify_cell
    base._score = _score
    base.VALIDATOR_SLOTS = set(base.VALIDATOR_SLOTS) | ADDITIONAL_DIAGNOSTIC_SLOTS
    try:
        yield
    finally:
        base._verify_contract = previous["contract"]
        base._verify_cell = previous["cell"]
        base._score = previous["score"]
        base.VALIDATOR_SLOTS = previous["slots"]


def verify(root: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    with _audit_profile():
        return base.verify(root)


def build_audit_receipt(root: Path) -> dict[str, Any]:
    issues, cells, summary = verify(root)
    contract = base.strict_json(root / "contract.json", "M29-S Attempt 3 contract")
    body = {
        "schema_version": "grideval-g7-m29s-independent-audit/v3",
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
    stored = base.strict_json(path, "M29-S Attempt 3 independent audit")
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
