"""Independent standard-library audit of the frozen M29-S design package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "m29s_factorial_plan.json"
M29R_FIXTURE_PATH = ROOT / "artifacts/m29r_design_attempt1/design_fixture.json"
EXPECTED_SOURCE_PATHS = (
    "M29S_EXECUTOR_BACKBRIEF.md",
    "M29S_INDEPENDENT_AUDIT_PLAN.md",
    "m29s_factorial_plan.json",
    "m29s_evidence_ledger.schema.json",
    "m29s_semantic_slots.schema.json",
    "m29s_strategy_program.schema.json",
    "g7confirm/m29s_semantic_compiler.py",
    "g7confirm/m29s_design_contract.py",
    "g7confirm/m29s_plan_audit.py",
    "tests/test_m29s_semantic_compiler.py",
    "tests/test_m29s_plan_audit.py",
)
FACTORIAL_ARMS = {
    "IA4-FS", "IA4-FSR", "IA4-FV", "IA4-FVR",
    "IA4-SS", "IA4-SSR", "IA4-SV", "IA4-SVR",
}
REFERENCE_ARMS = {"IA4-C1", "IA4-C1R"}
CONTROL_ARMS = {"IA3-SX", "IA5-OC"}
SLOT_KEYS = {
    "strategy_id", "effect_direction", "allowed_targets", "forbidden_windows",
    "objective_weights", "max_total_energy", "max_total_visibility",
    "min_actions", "max_actions", "max_level_delta", "cooldown_same_target",
}
VALIDATOR_CODES = {
    "schema", "evidence_unknown", "evidence_missing", "authority_conflict",
    "expired_record", "topology_inconsistent", "budget_inconsistent",
    "weights_inconsistent", "cooldown_inconsistent",
}


class M29SPlanAuditError(ValueError):
    """Raised for malformed independent-audit inputs."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}_{sha256_value(payload)}"


def strict_json(path: Path, label: str) -> Any:
    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M29SPlanAuditError(f"duplicate key in {label}: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise M29SPlanAuditError(f"non-finite value in {label}: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_pairs,
        parse_constant=reject_constant,
    )


def _add(issues: list[str], issue: str) -> None:
    if issue not in issues:
        issues.append(issue)


def _verify_content_address(
    payload: Mapping[str, Any], key: str, prefix: str, issues: list[str], issue: str
) -> None:
    body = dict(payload)
    identifier = body.pop(key, None)
    if identifier != content_id(prefix, body):
        _add(issues, issue)


def _program_core(program: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: program.get(key) for key in SLOT_KEYS}
    if isinstance(result.get("allowed_targets"), list):
        result["allowed_targets"] = sorted(result["allowed_targets"])
    if isinstance(result.get("forbidden_windows"), list):
        result["forbidden_windows"] = sorted(result["forbidden_windows"])
    return result


def _verify_plan(plan: Mapping[str, Any], issues: list[str]) -> None:
    if plan.get("schema_version") != "grideval-g7-m29s-factorial-plan/v1":
        _add(issues, "plan_schema")
    if plan.get("classification") != "PRELIMINARY_ONLY":
        _add(issues, "plan_classification")
    arms = plan.get("arms", [])
    by_id = {row.get("arm_id"): row for row in arms if isinstance(row, Mapping)}
    if set(by_id) != FACTORIAL_ARMS | REFERENCE_ARMS | CONTROL_ARMS or len(arms) != 12:
        _add(issues, "arm_registration")
        return
    factor_rows = [by_id[name] for name in FACTORIAL_ARMS]
    combinations = {
        (row.get("interface"), row.get("feedback"), row.get("retrieval"))
        for row in factor_rows
    }
    expected = {
        (interface, feedback, retrieval)
        for interface in ("flat", "staged")
        for feedback in ("neutral_self_revision", "validator_guided_revision")
        for retrieval in (False, True)
    }
    if combinations != expected:
        _add(issues, "factorial_coverage")
    if any(row.get("model_calls_per_cell") != 2 for row in factor_rows):
        _add(issues, "factorial_call_parity")
    if any(by_id[name].get("model_calls_per_cell") != 1 for name in REFERENCE_ARMS):
        _add(issues, "reference_call_count")
    if any(by_id[name].get("model_calls_per_cell") != 0 for name in CONTROL_ARMS):
        _add(issues, "control_call_count")
    calls = 16 * sum(int(row.get("model_calls_per_cell", -999)) for row in arms)
    model = plan.get("model_contract", {})
    if calls != 288 or model.get("maximum_calls_per_split") != 288:
        _add(issues, "per_split_call_budget")
    if model.get("maximum_additional_calls") != 576:
        _add(issues, "additional_call_budget")
    if model.get("prior_cumulative_calls") != 101 or model.get("maximum_cumulative_calls") != 677:
        _add(issues, "cumulative_call_budget")
    if model.get("maximum_cumulative_calls", 1001) > model.get("pi_authorized_cumulative_ceiling", 0):
        _add(issues, "pi_authorization")
    if model.get("retry_count") != 0:
        _add(issues, "retry_budget")
    tool = plan.get("tool_contract", {})
    if set(tool.get("validator_codes", [])) != VALIDATOR_CODES:
        _add(issues, "validator_code_allowlist")
    if tool.get("expected_values_allowed") is not False:
        _add(issues, "validator_expected_values")
    if tool.get("corrected_program_allowed") is not False:
        _add(issues, "validator_corrected_program")
    if tool.get("scores_or_labels_allowed") is not False:
        _add(issues, "validator_scores_labels")


def _verify_schema(path: Path, issues: list[str]) -> None:
    schema = strict_json(path, path.name)
    if schema.get("additionalProperties") is not False:
        _add(issues, f"schema_not_strict:{path.name}")
    if not str(schema.get("$schema", "")).endswith("2020-12/schema"):
        _add(issues, f"schema_version:{path.name}")


def _verify_fixture(fixture: Mapping[str, Any], issues: list[str]) -> None:
    _verify_content_address(
        fixture, "design_fixture_id", "m29sfixture", issues,
        "design_fixture_content_address",
    )
    if fixture.get("schema_version") != "grideval-g7-m29s-design-fixture/v1":
        _add(issues, "design_fixture_schema")
    if fixture.get("classification") != "PRELIMINARY_ONLY":
        _add(issues, "design_fixture_classification")
    rows = fixture.get("conditions", [])
    if fixture.get("condition_count") != 32 or len(rows) != 32:
        _add(issues, "condition_count")
        return
    ids = [row.get("condition_id") for row in rows]
    if len(set(ids)) != 32:
        _add(issues, "condition_id_uniqueness")
    for split, expected_seeds in (
        ("development", set(range(39101, 39109))),
        ("held_out", set(range(39201, 39209))),
    ):
        selected = [row for row in rows if row.get("split") == split]
        if len(selected) != 16:
            _add(issues, f"split_count:{split}")
            continue
        seeds = {row.get("latent_condition", {}).get("seed") for row in selected}
        if seeds != expected_seeds:
            _add(issues, f"split_seeds:{split}")
        if seeds & set(range(9101, 9113)):
            _add(issues, "final_seed_access")
        pairs: dict[str, set[str]] = {}
        for row in selected:
            pairs.setdefault(str(row.get("pair_id")), set()).add(str(row.get("side")))
        if len(pairs) != 8 or any(sides != {"left", "right"} for sides in pairs.values()):
            _add(issues, f"pair_registration:{split}")
        retrieval_count = sum(
            row.get("latent_condition", {}).get("retrieval_required") is True
            for row in selected
        )
        if retrieval_count != 8:
            _add(issues, f"retrieval_balance:{split}")
    corpus = fixture.get("corpus", {})
    queries = fixture.get("query_manifest", {})
    _verify_content_address(corpus, "corpus_id", "m29scorpus", issues, "corpus_content_address")
    _verify_content_address(queries, "query_manifest_id", "m29squeries", issues, "query_content_address")
    passages = {row.get("passage_id"): row for row in corpus.get("passages", [])}
    if len(passages) != 48:
        _add(issues, "corpus_cardinality")
    query_rows = {row.get("condition_id"): row for row in queries.get("queries", [])}
    if len(query_rows) != 32:
        _add(issues, "query_cardinality")
    for row in rows:
        condition_id = row.get("condition_id")
        latent = row.get("latent_condition", {})
        visible = row.get("visible_evidence", {})
        visible_text = canonical_json(visible).lower()
        if "oracle" in visible_text or "latent" in visible_text:
            _add(issues, f"hidden_field_in_visible:{condition_id}")
        if visible.get("condition_id") != condition_id:
            _add(issues, f"visible_condition:{condition_id}")
        records = visible.get("records", [])
        record_ids = {record.get("record_id") for record in records}
        if len(records) != 5 or len(record_ids) != 5:
            _add(issues, f"visible_record_count:{condition_id}")
        flat_ids = row.get("flat_passage_ids", [])
        retrieval_ids = row.get("oracle_retrieval_passage_ids", [])
        if len(flat_ids) != 4 or len(retrieval_ids) != 4:
            _add(issues, f"passage_view_cardinality:{condition_id}")
        if set(flat_ids) - set(passages) or set(retrieval_ids) - set(passages):
            _add(issues, f"unknown_passage:{condition_id}")
        expected_passage = "m29s_doc_" + re.sub(
            r"[^A-Za-z0-9]+", "_", str(latent.get("doctrine_code", ""))
        ).strip("_")
        if expected_passage not in retrieval_ids:
            _add(issues, f"retrieval_expected_missing:{condition_id}")
        oracle = row.get("independent_oracle", {})
        program = oracle.get("strategy_program", {})
        latent_program = latent.get("semantic_program", {})
        if canonical_json(_program_core(program)) != canonical_json(_program_core(latent_program)):
            _add(issues, f"oracle_semantics:{condition_id}")
        oracle_passage_ids = set(retrieval_ids if latent.get("retrieval_required") else flat_ids)
        visible_ids = record_ids | oracle_passage_ids
        if set(program.get("required_evidence_ids", [])) - visible_ids:
            _add(issues, f"oracle_hidden_evidence:{condition_id}")
        slots = oracle.get("semantic_slots", {}).get("slots", {})
        if set(slots) != SLOT_KEYS:
            _add(issues, f"slot_coverage:{condition_id}")
        else:
            for slot in SLOT_KEYS:
                if canonical_json(slots[slot].get("value")) != canonical_json(latent_program.get(slot)):
                    _add(issues, f"slot_oracle:{condition_id}:{slot}")
                if set(slots[slot].get("supporting_evidence_ids", [])) - visible_ids:
                    _add(issues, f"slot_hidden_evidence:{condition_id}:{slot}")
        ledger = oracle.get("evidence_ledger", {})
        expected_status = {
            "active_evidence_ids": sorted(record["record_id"] for record in records if record["status"] == "active"),
            "superseded_evidence_ids": sorted(record["record_id"] for record in records if record["status"] == "superseded"),
            "expired_evidence_ids": sorted(record["record_id"] for record in records if record["status"] == "expired"),
        }
        for key, expected_values in expected_status.items():
            if ledger.get(key) != expected_values:
                _add(issues, f"ledger_status:{condition_id}:{key}")
        query = query_rows.get(condition_id, {})
        if query.get("expected_passage_id") != expected_passage:
            _add(issues, f"query_expected:{condition_id}")
    access = fixture.get("access_boundary", {})
    if any(value not in (False, []) for value in access.values()):
        _add(issues, "access_boundary")
    budget = fixture.get("call_budget", {})
    if budget != {
        "calls_per_split": 288,
        "maximum_additional_calls": 576,
        "prior_cumulative_calls": 101,
        "maximum_cumulative_calls": 677,
        "pi_authorized_ceiling": 1000,
        "retry_count": 0,
    }:
        _add(issues, "fixture_call_budget")
    if fixture.get("m29b_authorized") is not False:
        _add(issues, "m29b_authorization")


def _verify_m29r_disjointness(
    fixture: Mapping[str, Any], prior: Mapping[str, Any], issues: list[str]
) -> None:
    current = fixture.get("conditions", [])
    old = prior.get("conditions", [])
    if {row.get("condition_id") for row in current} & {row.get("condition_id") for row in old}:
        _add(issues, "m29r_condition_overlap")
    current_seeds = {row.get("latent_condition", {}).get("seed") for row in current}
    old_seeds = {row.get("latent_scenario", {}).get("development_seed") for row in old}
    if current_seeds & old_seeds:
        _add(issues, "m29r_seed_overlap")
    current_digests = {
        sha256_value(row.get("latent_condition", {}).get("semantic_program", {}))
        for row in current
    }
    old_digests = {
        row.get("evidence_bundle", {}).get("semantic_meaning_digest") for row in old
    }
    if current_digests & old_digests:
        _add(issues, "m29r_semantic_overlap")
    current_bytes = {
        canonical_json(row.get("visible_evidence", {}).get("records", []))
        for row in current
    }
    old_bytes = {
        canonical_json(row.get("evidence_bundle", {}).get("semantic_records", []))
        for row in old
    }
    if current_bytes & old_bytes:
        _add(issues, "m29r_rendered_overlap")
    current_doctrines = {
        row.get("latent_condition", {}).get("doctrine_code") for row in current
    }
    old_doctrines = {
        row.get("latent_scenario", {}).get("doctrine_code") for row in old
    }
    if current_doctrines & old_doctrines:
        _add(issues, "m29r_doctrine_overlap")


def verify(contract_path: Path) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    issues: list[str] = []
    contract = strict_json(contract_path, "M29-S design contract")
    _verify_content_address(
        contract, "design_contract_id", "m29scontract", issues,
        "design_contract_content_address",
    )
    if contract.get("schema_version") != "grideval-g7-m29s-design-contract/v1":
        _add(issues, "design_contract_schema")
    if contract.get("classification") != "PRELIMINARY_ONLY":
        _add(issues, "design_contract_classification")
    source_rows = contract.get("source_hashes", [])
    source_map = {row.get("path"): row.get("sha256") for row in source_rows}
    if set(source_map) != set(EXPECTED_SOURCE_PATHS):
        _add(issues, "source_manifest")
    for relative in EXPECTED_SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file() or source_map.get(relative) != sha256_file(path):
            _add(issues, f"source_hash:{relative}")
    plan = strict_json(PLAN_PATH, "M29-S factorial plan")
    _verify_plan(plan, issues)
    if contract.get("decision_id") != plan.get("decision_id"):
        _add(issues, "decision_binding")
    if contract.get("registered_arms") != [row["arm_id"] for row in plan.get("arms", [])]:
        _add(issues, "arm_binding")
    if contract.get("tool_contract") != plan.get("tool_contract"):
        _add(issues, "tool_contract_binding")
    if contract.get("model_contract") != plan.get("model_contract"):
        _add(issues, "model_contract_binding")
    for name in (
        "m29s_evidence_ledger.schema.json",
        "m29s_semantic_slots.schema.json",
        "m29s_strategy_program.schema.json",
    ):
        _verify_schema(ROOT / name, issues)
    fixture_ref = contract.get("design_fixture", {})
    fixture_path = ROOT / str(fixture_ref.get("path", "missing"))
    if not fixture_path.is_file():
        _add(issues, "design_fixture_missing")
        return sorted(issues), contract, {}
    if fixture_ref.get("sha256") != sha256_file(fixture_path):
        _add(issues, "design_fixture_hash")
    fixture = strict_json(fixture_path, "M29-S design fixture")
    if fixture_ref.get("design_fixture_id") != fixture.get("design_fixture_id"):
        _add(issues, "design_fixture_binding")
    _verify_fixture(fixture, issues)
    prior = strict_json(M29R_FIXTURE_PATH, "M29-R design fixture")
    _verify_m29r_disjointness(fixture, prior, issues)
    cjk = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
    for relative in EXPECTED_SOURCE_PATHS:
        if cjk.search((ROOT / relative).read_text(encoding="utf-8")):
            _add(issues, f"non_english_source:{relative}")
    authorization = contract.get("access_authorization", {})
    allowed_true = {"offline_llm_after_plan_gate", "existing_embedding_after_plan_gate"}
    if {key for key, value in authorization.items() if value is True} != allowed_true:
        _add(issues, "access_authorization")
    if contract.get("m29b_authorized") is not False:
        _add(issues, "contract_m29b_authorization")
    return sorted(issues), contract, fixture


def build_audit_receipt(contract_path: Path) -> dict[str, Any]:
    issues, contract, fixture = verify(contract_path)
    body = {
        "schema_version": "grideval-g7-m29s-plan-audit/v1",
        "classification": "PRELIMINARY_ONLY",
        "design_contract_id": contract.get("design_contract_id"),
        "design_fixture_id": fixture.get("design_fixture_id"),
        "auditor_source_sha256": sha256_file(Path(__file__)),
        "independent_imports_primary": False,
        "checks": {
            "factorial_coverage": "passed" if "factorial_coverage" not in issues else "failed",
            "equal_call_parity": "passed" if "factorial_call_parity" not in issues else "failed",
            "interface_separation": "passed" if "arm_registration" not in issues else "failed",
            "validator_nonleakage": "passed" if not any("validator_" in item for item in issues) else "failed",
            "m29r_disjointness": "passed" if not any(item.startswith("m29r_") for item in issues) else "failed",
            "call_authorization": "passed" if not any("budget" in item or item == "pi_authorization" for item in issues) else "failed",
            "access_seals": "passed" if not any("access" in item or "m29b" in item for item in issues) else "failed",
        },
        "model_calls": 0,
        "embedding_calls": 0,
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "m29b_authorized": False,
    }
    return {"audit_id": content_id("m29splanaudit", body), **body}


def verify_audit_receipt(contract_path: Path, receipt_path: Path) -> list[str]:
    issues: list[str] = []
    recorded = strict_json(receipt_path, "M29-S plan audit receipt")
    _verify_content_address(
        recorded, "audit_id", "m29splanaudit", issues,
        "audit_receipt_content_address",
    )
    expected = build_audit_receipt(contract_path)
    if canonical_json(recorded) != canonical_json(expected):
        _add(issues, "audit_receipt_reproduction")
    return sorted(issues)


def create_once_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite create-once artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        issues = verify_audit_receipt(args.contract.resolve(), args.verify.resolve())
        print(canonical_json({"status": "passed" if not issues else "failed", "issues": issues}))
        raise SystemExit(0 if not issues else 2)
    receipt = build_audit_receipt(args.contract.resolve())
    if args.output:
        create_once_json(args.output, receipt)
    print(canonical_json(receipt))
    raise SystemExit(0 if receipt["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
