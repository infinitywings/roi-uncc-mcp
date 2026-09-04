"""Append-only resolution of the M29-S v4 auditor array-order mismatch."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import m29s_independent_audit_v4 as parent


base = parent.base
SCORING_ISSUE_PREFIXES = ("initial_scores:", "final_scores:", "endpoints:")


def _score_order_sensitive(
    draft: Mapping[str, Any] | None,
    interface: str,
    oracle: Mapping[str, Any],
    visible: Mapping[str, Any],
) -> dict[str, Any]:
    """Reproduce the frozen campaign's exact, order-sensitive slot metric."""

    program = base._program(draft)
    oracle_program = oracle["strategy_program"]
    slots = {
        key: bool(
            program is not None
            and base.canonical_json(program.get(key))
            == base.canonical_json(oracle_program[key])
        )
        for key in base.SLOT_KEYS
    }
    lineage = bool(
        program is not None
        and sorted(program.get("required_evidence_ids", []))
        == sorted(oracle_program["required_evidence_ids"])
    )
    ledger_exact: bool | None = None
    slot_lineage: bool | None = None
    if interface == "staged":
        records = visible["visible_evidence"]["records"]
        active_authorities = {
            row["authority"] for row in records if row["status"] == "active"
        }
        expected_ledger = {
            "schema_version": "grideval-g7-m29s-evidence-ledger/v1",
            "condition_id": visible["visible_evidence"]["condition_id"],
            "active_evidence_ids": sorted(
                row["record_id"] for row in records if row["status"] == "active"
            ),
            "superseded_evidence_ids": sorted(
                row["record_id"]
                for row in records
                if row["status"] == "superseded"
            ),
            "expired_evidence_ids": sorted(
                row["record_id"] for row in records if row["status"] == "expired"
            ),
            "unresolved_conflict_ids": [],
            "authority_order": [
                value
                for value in parent.v3.AUTHORITY_ORDER
                if value in active_authorities
            ],
            "visible_input_digest": base.sha256_value(visible),
        }
        ledger_exact = bool(
            draft
            and base.canonical_json(draft.get("evidence_ledger"))
            == base.canonical_json(expected_ledger)
        )
        submitted_slots = (
            draft.get("semantic_slots", {}).get("slots", {}) if draft else {}
        )
        oracle_slots = oracle["semantic_slots"]["slots"]
        slot_lineage = bool(
            set(submitted_slots) == set(base.SLOT_KEYS)
            and all(
                sorted(submitted_slots[key].get("supporting_evidence_ids", []))
                == sorted(oracle_slots[key]["supporting_evidence_ids"])
                for key in base.SLOT_KEYS
            )
        )
        lineage = bool(lineage and slot_lineage)
    semantics_exact = all(slots.values())
    success = bool(
        semantics_exact
        and lineage
        and (interface != "staged" or ledger_exact is True)
    )
    return {
        "per_slot_exact": slots,
        "correct_slot_count": sum(slots.values()),
        "program_semantics_exact": semantics_exact,
        "evidence_lineage_exact": lineage,
        "evidence_ledger_exact": ledger_exact,
        "semantic_slot_lineage_exact": slot_lineage,
        "all_slot_program_exact": success,
    }


@contextmanager
def _scoring_profile() -> Iterator[None]:
    previous = parent.v3._score
    parent.v3._score = _score_order_sensitive
    try:
        yield
    finally:
        parent.v3._score = previous


def verify(root: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    with _scoring_profile():
        return parent.verify(root)


def build_addendum_receipt(root: Path) -> dict[str, Any]:
    prior_path = root / "independent_audit_receipt.json"
    prior = base.strict_json(prior_path, "M29-S v4 failed independent audit")
    prior_issues = prior.get("issues", [])
    prior_scoring_only = bool(prior_issues) and all(
        isinstance(value, str) and value.startswith(SCORING_ISSUE_PREFIXES)
        for value in prior_issues
    )
    issues, cells, summary = verify(root)
    contract = base.strict_json(root / "contract.json", "M29-S Attempt 4 contract")
    resolution_issues = list(issues)
    if prior.get("status") != "failed":
        resolution_issues.append("prior_audit_was_not_failed")
    if not prior_scoring_only:
        resolution_issues.append("prior_audit_contains_non_scoring_issues")
    body = {
        "schema_version": "grideval-g7-m29s-independent-audit-addendum/v1",
        "classification": base.CLASSIFICATION,
        "execution_contract_id": contract.get("execution_contract_id"),
        "addendum_source_sha256": base.sha256_file(Path(__file__).resolve()),
        "independent_imports_campaign": False,
        "independent_imports_semantic_compiler": False,
        "prior_audit": {
            "path": prior_path.relative_to(root).as_posix(),
            "sha256": base.sha256_file(prior_path),
            "audit_id": prior.get("audit_id"),
            "status": prior.get("status"),
            "issue_count": len(prior_issues),
            "all_issues_are_score_recomputation_mismatches": prior_scoring_only,
        },
        "resolution": {
            "root_cause": "The original independent scorer normalized unordered arrays while the frozen campaign exact metric preserved array order.",
            "frozen_campaign_or_evidence_modified": False,
            "model_calls_repeated": False,
            "corrected_rule": "Compare every semantic slot with canonical JSON and preserve array order, matching the frozen campaign metric.",
        },
        "source_hashes_recomputed": True,
        "content_addresses_recomputed": True,
        "embedding_top_k_recomputed": True,
        "request_parity_recomputed": True,
        "active_authority_ledger_recomputed": True,
        "order_sensitive_endpoints_recomputed": True,
        "cell_count": len(cells),
        "model_calls": sum(
            row.get("accounting", {}).get("model_calls", 0) for row in cells
        ),
        "scientific_summary": summary,
        "status": "passed" if not resolution_issues else "failed",
        "issues": list(dict.fromkeys(resolution_issues)),
        "m29b_authorized": False,
    }
    return {"audit_addendum_id": base.content_id("m29sauditadd", body), **body}


def verify_addendum_receipt(root: Path) -> list[str]:
    path = root / "independent_audit_addendum.json"
    if not path.is_file():
        return ["missing_independent_audit_addendum"]
    stored = base.strict_json(path, "M29-S independent audit addendum")
    rebuilt = build_addendum_receipt(root)
    return [] if base.canonical_json(stored) == base.canonical_json(rebuilt) else [
        "independent_audit_addendum_mismatch"
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.write:
        receipt = build_addendum_receipt(root)
        base.create_once_json(root / "independent_audit_addendum.json", receipt)
        print(
            base.canonical_json(
                {
                    "audit_addendum_id": receipt["audit_addendum_id"],
                    "status": receipt["status"],
                    "issues": receipt["issues"],
                }
            )
        )
        raise SystemExit(0 if receipt["status"] == "passed" else 1)
    issues = verify_addendum_receipt(root)
    print(base.canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
