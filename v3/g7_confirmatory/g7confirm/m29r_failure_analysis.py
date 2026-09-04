"""Build and verify the post-hoc M29-R Attempt 2 failure analysis.

The analysis reads only immutable PRELIMINARY_ONLY attempt artifacts. It does
not call a model, embedding service, optimizer, simulator, detector, defense,
or final-evaluation resource.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ATTEMPT_ROOT = ROOT / "artifacts/m29r_complementarity_attempt2"
DEFAULT_DESIGN_PATH = ROOT / "artifacts/m29r_design_attempt1/design_fixture.json"
ARMS = ("IA3-O", "IA3-SO", "IA4-D", "IA4-H", "IA4-HR", "IA5-OC")
SEMANTIC_FIELDS = (
    "strategy_id",
    "effect_direction",
    "allowed_targets",
    "forbidden_windows",
    "objective_weights",
    "max_total_energy",
    "max_total_visibility",
    "min_actions",
    "max_actions",
    "max_level_delta",
    "cooldown_same_target",
)


class M29RAnalysisError(RuntimeError):
    """Raised when immutable analysis inputs or outputs fail validation."""


def _reject_duplicate(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise M29RAnalysisError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate,
            parse_constant=lambda value: (_ for _ in ()).throw(
                M29RAnalysisError(f"non-finite JSON constant: {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M29RAnalysisError(f"cannot read strict JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise M29RAnalysisError(f"expected JSON object: {path}")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(prefix: str, body: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def _increment(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _arm_analysis(
    rows: Sequence[Mapping[str, Any]],
    oracle_programs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    mismatches = {field: 0 for field in SEMANTIC_FIELDS}
    failure_classes: dict[str, int] = {}
    finish_reasons: dict[str, int] = {}
    program_absent = 0
    evidence_lineage_mismatch = 0
    zero_regret_wrong_semantics = 0

    for row in rows:
        condition_id = str(row["condition_id"])
        oracle = oracle_programs[condition_id]
        program = row.get("emitted_program")
        if not isinstance(program, Mapping):
            program_absent += 1
        else:
            for field in SEMANTIC_FIELDS:
                if program.get(field) != oracle.get(field):
                    mismatches[field] += 1
            if sorted(program.get("required_evidence_ids", [])) != sorted(
                oracle.get("required_evidence_ids", [])
            ):
                evidence_lineage_mismatch += 1

        failure_class = row.get("failure_class")
        if isinstance(failure_class, str):
            _increment(failure_classes, failure_class)
        response = row.get("model_response")
        if isinstance(response, Mapping) and isinstance(response.get("finish_reason"), str):
            _increment(finish_reasons, str(response["finish_reason"]))

        endpoints = row["endpoints"]
        if (
            endpoints.get("compiler_correct") is False
            and endpoints.get("normalized_regret") == 0
        ):
            zero_regret_wrong_semantics += 1

    return {
        "cell_count": len(rows),
        "program_absent": program_absent,
        "compiler_correct": sum(
            row["endpoints"].get("compiler_correct") is True for row in rows
        ),
        "conjunctive_success": sum(
            row["endpoints"].get("conjunctive_success") is True for row in rows
        ),
        "plan_valid_under_oracle": sum(
            row["endpoints"].get("plan_valid_under_oracle") is True for row in rows
        ),
        "oracle_match": sum(
            row["endpoints"].get("oracle_match") is True for row in rows
        ),
        "validator_admitted": sum(
            row["endpoints"].get("validator_admitted") is True for row in rows
        ),
        "zero_regret_wrong_semantics": zero_regret_wrong_semantics,
        "evidence_lineage_mismatch": evidence_lineage_mismatch,
        "semantic_field_mismatches": mismatches,
        "finish_reasons": dict(sorted(finish_reasons.items())),
        "failure_classes": dict(sorted(failure_classes.items())),
    }


def build_analysis(attempt_root: Path, design_path: Path) -> dict[str, Any]:
    contract_path = attempt_root / "contract.json"
    primary_path = attempt_root / "primary_receipt.json"
    audit_path = attempt_root / "independent_audit_receipt.json"
    contract = strict_json(contract_path)
    primary = strict_json(primary_path)
    audit = strict_json(audit_path)
    design = strict_json(design_path)

    contract_id = contract.get("execution_contract_id")
    if primary.get("execution_contract_id") != contract_id:
        raise M29RAnalysisError("primary receipt contract lineage mismatch")
    if audit.get("execution_contract_id") != contract_id:
        raise M29RAnalysisError("independent audit contract lineage mismatch")
    if primary.get("status") != "passed" or primary.get("issues") != []:
        raise M29RAnalysisError("primary receipt did not pass")
    if audit.get("status") != "passed" or audit.get("issues") != []:
        raise M29RAnalysisError("independent audit did not pass")

    conditions = design.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 16:
        raise M29RAnalysisError("design condition count drift")
    oracle_programs = {
        str(row["condition_id"]): row["independent_oracle"]["strategy_program"]
        for row in conditions
    }

    cell_paths = sorted((attempt_root / "cells").glob("*/*.json"))
    cells = [strict_json(path) for path in cell_paths]
    if len(cells) != 96:
        raise M29RAnalysisError("attempt cell count drift")
    by_arm = {
        arm: [row for row in cells if row.get("arm_id") == arm] for arm in ARMS
    }
    if any(len(rows) != 16 for rows in by_arm.values()):
        raise M29RAnalysisError("arm cell count drift")

    summary = primary["scientific_summary"]
    retrieval = summary["retrieval_subset"]
    nonretrieval = summary["nonretrieval_subset"]
    retrieval_rule = contract["secondary_retrieval_rule"]
    retrieval_checks = {
        "retrieval_margin": retrieval["difference"]
        >= retrieval_rule["ia4_hr_minus_ia4_h_minimum_successes_on_retrieval_subset"],
        "nonretrieval_degradation": (
            nonretrieval["ia4_h_successes"] - nonretrieval["ia4_hr_successes"]
        )
        <= retrieval_rule["maximum_nonretrieval_subset_degradation"],
        "registered_subset_size": retrieval["condition_count"]
        == retrieval_rule["retrieval_required_condition_count"],
    }

    body = {
        "schema_version": "grideval-g7-m29r-failure-analysis/v1",
        "classification": "PRELIMINARY_ONLY",
        "execution_contract_id": contract_id,
        "primary_receipt_id": primary.get("primary_receipt_id"),
        "independent_audit_id": audit.get("audit_id"),
        "source_hashes": {
            "contract": sha256_file(contract_path),
            "primary_receipt": sha256_file(primary_path),
            "independent_audit_receipt": sha256_file(audit_path),
            "design_fixture": sha256_file(design_path),
            "analysis_source": sha256_file(Path(__file__).resolve()),
        },
        "arm_analysis": {
            arm: _arm_analysis(rows, oracle_programs)
            for arm, rows in by_arm.items()
        },
        "core_unlock_checks": primary["scientific_unlock_checks"],
        "core_unlock_passed": bool(
            primary.get("bounded_m29b_proposal_eligible") is True
        ),
        "secondary_retrieval_checks": retrieval_checks,
        "secondary_retrieval_rule_passed": all(retrieval_checks.values()),
        "call_accounting": {
            "prior_read_only_chat_requests": contract["authorization_budget"][
                "prior_read_only_chat_requests"
            ],
            "attempt_2_model_calls": primary["totals"]["model_calls"],
            "cumulative_read_only_chat_requests": contract["authorization_budget"][
                "prior_read_only_chat_requests"
            ]
            + primary["totals"]["model_calls"],
            "authorized_ceiling": contract["authorization_budget"][
                "authorized_total_read_only_chat_requests"
            ],
        },
        "interpretation_boundary": {
            "supported": [
                "Attempt 2 repaired provider compatibility without changing the scientific contract.",
                "The current model did not establish semantic-compiler and optimizer complementarity on the registered battery.",
                "Scoped retrieval met the registered secondary retrieval rule within this battery.",
            ],
            "prohibited": [
                "M29-B simulator authorization",
                "general LLM or retrieval superiority",
                "physical, stealth, detector-evasion, defense-bypass, or confirmatory inference",
            ],
        },
        "m29b_authorized": False,
    }
    return {"analysis_id": content_id("m29ranalysis", body), **body}


def write_create_once(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-root", type=Path, default=DEFAULT_ATTEMPT_ROOT)
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN_PATH)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()

    rebuilt = build_analysis(args.attempt_root, args.design)
    if args.output is not None:
        write_create_once(args.output, rebuilt)
        print(canonical_json(rebuilt))
        return
    stored = strict_json(args.verify)
    issues = [] if canonical_json(stored) == canonical_json(rebuilt) else [
        "failure_analysis_receipt_mismatch"
    ]
    print(canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
