"""Independent non-campaign audit for M29-R provider-compatible Attempt 2."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import m29r_independent_audit as base


ROOT = base.ROOT
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


@contextmanager
def _source_profile() -> Iterator[None]:
    previous = base.BOUND_SOURCE_PATHS
    base.BOUND_SOURCE_PATHS = BOUND_SOURCE_PATHS
    try:
        yield
    finally:
        base.BOUND_SOURCE_PATHS = previous


def _contains_key(value: Any, target: str) -> bool:
    if isinstance(value, Mapping):
        return target in value or any(_contains_key(item, target) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, target) for item in value)
    return False


def _provider_issues(
    contract: Mapping[str, Any], cells: Sequence[Mapping[str, Any]]
) -> list[str]:
    issues: list[str] = []
    if contract.get("schema_version") != "grideval-g7-m29r-execution-contract/v2":
        issues.append("provider_contract_schema")
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
        issues.append("provider_contract_profile")
    budget = contract.get("authorization_budget", {})
    authorized = int(budget.get("authorized_total_read_only_chat_requests", -1))
    prior = int(budget.get("prior_read_only_chat_requests", -1))
    contracted = int(budget.get("contracted_attempt_2_requests", -1))
    if contracted != 48 or authorized - prior < contracted:
        issues.append("provider_authorization_budget")
    if int(budget.get("remaining_after_attempt_2", -1)) != authorized - prior - contracted:
        issues.append("provider_authorization_arithmetic")
    for cell in cells:
        arm = cell.get("arm_id")
        if arm not in base.LLM_ARMS:
            continue
        label = f"{arm}/{cell.get('condition_id')}"
        request = cell.get("model_request")
        if not isinstance(request, Mapping):
            issues.append(f"provider_request_absent:{label}")
            continue
        if request.get("chat_template_kwargs") != {"enable_thinking": False}:
            issues.append(f"provider_thinking:{label}")
        if request.get("stream") is not False or request.get("n") != 1:
            issues.append(f"provider_cardinality:{label}")
        schema = request.get("response_format", {}).get("json_schema", {}).get("schema")
        if not isinstance(schema, Mapping) or _contains_key(schema, "uniqueItems"):
            issues.append(f"provider_wire_schema:{label}")
        if request.get("max_tokens") != 640:
            issues.append(f"provider_completion_budget:{label}")
    return list(dict.fromkeys(issues))


def verify(root: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    with _source_profile():
        issues, cells, summary = base.verify(root)
    contract = base.strict_json(root / "contract.json", "Attempt 2 contract")
    issues.extend(_provider_issues(contract, cells))
    return list(dict.fromkeys(issues)), cells, summary


def build_audit_receipt(root: Path) -> dict[str, Any]:
    issues, cells, summary = verify(root)
    contract = base.strict_json(root / "contract.json", "Attempt 2 contract")
    body = {
        "schema_version": "grideval-g7-m29r-independent-audit/v2",
        "classification": base.CLASSIFICATION,
        "execution_contract_id": contract.get("execution_contract_id"),
        "auditor_source_sha256": base.sha256_file(Path(__file__).resolve()),
        "independent_imports_campaign": False,
        "independent_imports_complementarity": False,
        "source_hashes_recomputed": True,
        "content_addresses_recomputed": True,
        "embedding_top_k_recomputed": True,
        "endpoints_recomputed": True,
        "provider_profile_recomputed": True,
        "authorization_arithmetic_recomputed": True,
        "scientific_summary": summary,
        "cell_count": len(cells),
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "m29b_authorized": False,
    }
    return {"audit_id": base.content_id("m29raudit", body), **body}


def verify_audit_receipt(root: Path) -> list[str]:
    path = root / "independent_audit_receipt.json"
    if not path.is_file():
        return ["missing_independent_audit_receipt"]
    stored = base.strict_json(path, "Attempt 2 independent audit")
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
        receipt = build_audit_receipt(args.root)
        base.create_once_json(args.root / "independent_audit_receipt.json", receipt)
        print(base.canonical_json(receipt))
        raise SystemExit(0 if receipt["status"] == "passed" else 1)
    issues = verify_audit_receipt(args.root)
    print(base.canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
