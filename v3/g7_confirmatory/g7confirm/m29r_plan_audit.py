"""Independent, non-importing plan audit for the M29-R design contract."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = "PRELIMINARY_ONLY"
WINDOWS = ("w0", "w1", "w2", "w3")
TARGETS = ("DER_A", "DER_B", "DER_C")
FINAL_SEEDS = set(range(9101, 9113))

EXPECTED_SOURCE_PATHS = (
    "M29R_EXECUTOR_BACKBRIEF.md",
    "M29R_INDEPENDENT_AUDIT_PLAN.md",
    "m29r_complementarity_plan.json",
    "m29r_strategy_corpus.json",
    "m29r_retrieval_queries.json",
    "m29r_evidence_bundle.schema.json",
    "m29r_strategy_program.schema.json",
    "m29r_multistage_request.schema.json",
    "m29r_optimizer_result.schema.json",
    "m29r_attack_plan.schema.json",
    "g7confirm/m29r_complementarity.py",
    "g7confirm/m29r_design_contract.py",
    "g7confirm/m29r_plan_audit.py",
    "tests/test_m29r_complementarity.py",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}_{sha256_value(payload)}"


def strict_json(path: Path, label: str) -> Any:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate_key:{label}:{key}")
            out[key] = value
        return out

    def reject(value: str) -> None:
        raise ValueError(f"nonfinite:{label}:{value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs_hook, parse_constant=reject)


def _add(issues: list[str], issue: str) -> None:
    if issue not in issues:
        issues.append(issue)


def _semantics(program: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "strategy_id", "effect_direction", "allowed_targets", "forbidden_windows",
        "objective_weights", "max_total_energy", "max_total_visibility",
        "min_actions", "max_actions", "max_level_delta", "cooldown_same_target",
    )
    return {key: program.get(key) for key in keys}


def _metrics(
    sequence: Sequence[Mapping[str, Any]], program: Mapping[str, Any]
) -> tuple[dict[str, Any], float]:
    direction = 1.0 if program.get("effect_direction") == "increase" else -1.0
    signed_effect = round(direction * sum(float(row["effect"]) for row in sequence), 6)
    persistence = sum(direction * float(row["effect"]) > 0 for row in sequence)
    energy = sum(int(row["energy_cost"]) for row in sequence)
    visibility = sum(int(row["visibility_cost"]) for row in sequence)
    action_count = sum(row["target_id"] is not None for row in sequence)
    aggregate = {
        "signed_effect": signed_effect,
        "persistence_windows": persistence,
        "total_energy": energy,
        "total_visibility": visibility,
        "action_count": action_count,
    }
    weights = program["objective_weights"]
    objective = round(
        float(weights["effect"]) * signed_effect
        + float(weights["persistence"]) * persistence
        - float(weights["energy"]) * energy
        - float(weights["visibility"]) * visibility,
        6,
    )
    return aggregate, objective


def _valid(sequence: Sequence[Mapping[str, Any]], program: Mapping[str, Any]) -> bool:
    if len(sequence) != 4 or [row.get("window") for row in sequence] != list(WINDOWS):
        return False
    allowed = set(program.get("allowed_targets", []))
    forbidden = set(program.get("forbidden_windows", []))
    if not allowed or allowed - set(TARGETS) or forbidden - set(WINDOWS):
        return False
    for row in sequence:
        if row.get("target_id") is not None and row.get("target_id") not in allowed:
            return False
        if row.get("window") in forbidden and row.get("target_id") is not None:
            return False
    aggregate, _ = _metrics(sequence, program)
    if not int(program["min_actions"]) <= aggregate["action_count"] <= int(program["max_actions"]):
        return False
    if aggregate["total_energy"] > int(program["max_total_energy"]):
        return False
    if aggregate["total_visibility"] > int(program["max_total_visibility"]):
        return False
    levels = [int(row["level"]) for row in sequence]
    if any(abs(right - left) > int(program["max_level_delta"]) for left, right in zip(levels, levels[1:])):
        return False
    if program.get("cooldown_same_target") is True:
        targets = [row.get("target_id") for row in sequence]
        if any(left is not None and left == right for left, right in zip(targets, targets[1:])):
            return False
    return True


def _enumerate(
    surface: Sequence[Mapping[str, Any]], program: Mapping[str, Any]
) -> tuple[list[str], dict[str, Any], float, int, int]:
    grouped = {window: [] for window in WINDOWS}
    for row in surface:
        if row.get("window") not in grouped:
            raise ValueError("unknown_window")
        grouped[row["window"]].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: item["action_id"])
    best_ids: tuple[str, ...] | None = None
    best_aggregate: dict[str, Any] | None = None
    best_objective = -math.inf
    evaluated = 0
    feasible = 0
    for sequence in itertools.product(*(grouped[window] for window in WINDOWS)):
        evaluated += 1
        if not _valid(sequence, program):
            continue
        feasible += 1
        aggregate, objective = _metrics(sequence, program)
        ids = tuple(row["action_id"] for row in sequence)
        if best_ids is None or objective > best_objective or (objective == best_objective and ids < best_ids):
            best_ids = ids
            best_aggregate = aggregate
            best_objective = objective
    if best_ids is None or best_aggregate is None:
        raise ValueError("infeasible_latent_scenario")
    return list(best_ids), best_aggregate, best_objective, evaluated, feasible


def _verify_plan_content_address(
    plan: Mapping[str, Any], prefix: str, issues: list[str], label: str
) -> None:
    body = dict(plan)
    identifier = body.pop("plan_id", None)
    if identifier != content_id(prefix, body):
        _add(issues, f"content_address:{label}")


def verify(contract_path: Path) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    try:
        contract = strict_json(contract_path, "design_contract")
    except Exception as exc:
        return [f"contract_parse:{type(exc).__name__}:{exc}"], {}

    contract_body = dict(contract)
    contract_id = contract_body.pop("design_contract_id", None)
    if contract_id != content_id("m29rcontract", contract_body):
        _add(issues, "design_contract_content_address")
    if contract.get("classification") != CLASSIFICATION:
        _add(issues, "contract_classification")
    if contract.get("m29b_authorized") is not False:
        _add(issues, "m29b_opened")

    source_rows = contract.get("source_hashes", [])
    if [row.get("path") for row in source_rows] != list(EXPECTED_SOURCE_PATHS):
        _add(issues, "source_path_registration")
    for row in source_rows:
        relative = row.get("path")
        if not isinstance(relative, str) or relative not in EXPECTED_SOURCE_PATHS:
            _add(issues, "unregistered_source")
            continue
        path = ROOT / relative
        if not path.is_file():
            _add(issues, f"missing_source:{relative}")
        elif row.get("sha256") != sha256_file(path):
            _add(issues, f"source_hash:{relative}")

    authorization = contract.get("access_authorization", {})
    expected_false = {
        "embedding_service_start_restart_or_reconfigure", "docker", "simulator",
        "detector", "defense", "network_impairment", "physical_actuator",
        "final_evaluation", "evaluation_seeds_9101_9112",
        "rka_governance_attacker_view",
    }
    for key in expected_false:
        if authorization.get(key) is not False:
            _add(issues, f"access_authorization:{key}")
    if authorization.get("offline_llm_after_plan_gate") is not True:
        _add(issues, "llm_gate_authorization")
    if authorization.get("existing_embedding_after_plan_gate") is not True:
        _add(issues, "embedding_gate_authorization")

    plan = strict_json(ROOT / "m29r_complementarity_plan.json", "plan")
    if [row.get("arm_id") for row in plan.get("arms", [])] != ["IA3-O", "IA3-SO", "IA4-D", "IA4-H", "IA4-HR", "IA5-OC"]:
        _add(issues, "arm_matrix")
    if contract.get("scientific_unlock_rule") != plan.get("scientific_unlock_rule"):
        _add(issues, "unlock_rule_binding")
    unlock = plan.get("scientific_unlock_rule", {})
    expected_unlock = {
        "oracle_ceiling_minimum_successes": 16,
        "ia4_h_minimum_successes": 12,
        "ia4_h_maximum_validity_violations": 0,
        "ia4_h_minimum_correct_pairs": 6,
        "ia4_h_minus_ia3_o_minimum_paired_successes": 6,
        "ia4_h_minus_ia4_d_minimum_paired_successes": 4,
        "minimum_witness_cells": 4,
    }
    for key, value in expected_unlock.items():
        if unlock.get(key) != value:
            _add(issues, f"unlock_threshold:{key}")
    if unlock.get("aggregate_success_alone_sufficient") is not False:
        _add(issues, "aggregate_unlock")

    corpus = strict_json(ROOT / "m29r_strategy_corpus.json", "corpus")
    corpus_body = dict(corpus)
    corpus_id = corpus_body.pop("corpus_id", None)
    if corpus_id != content_id("m29rcorpus", corpus_body):
        _add(issues, "corpus_content_address")
    passages = corpus.get("passages", [])
    passage_ids = [row.get("passage_id") for row in passages]
    if len(passages) != 24 or len(set(passage_ids)) != 24:
        _add(issues, "corpus_cardinality")

    query_manifest = strict_json(ROOT / "m29r_retrieval_queries.json", "queries")
    query_body = dict(query_manifest)
    query_id = query_body.pop("query_manifest_id", None)
    if query_id != content_id("m29rqueries", query_body):
        _add(issues, "query_content_address")
    query_rows = query_manifest.get("queries", [])
    query_map = {row.get("condition_id"): row for row in query_rows}
    if len(query_rows) != 16 or len(query_map) != 16:
        _add(issues, "query_cardinality")

    fixture_ref = contract.get("design_fixture", {})
    fixture_path = ROOT / str(fixture_ref.get("path", ""))
    if not fixture_path.is_file():
        _add(issues, "missing_design_fixture")
        return issues, contract
    if fixture_ref.get("sha256") != sha256_file(fixture_path):
        _add(issues, "design_fixture_file_hash")
    fixture = strict_json(fixture_path, "design_fixture")
    fixture_body = dict(fixture)
    fixture_id = fixture_body.pop("design_fixture_id", None)
    if fixture_id != content_id("m29rfixture", fixture_body):
        _add(issues, "design_fixture_content_address")
    if fixture_ref.get("design_fixture_id") != fixture_id:
        _add(issues, "design_fixture_id_binding")
    if fixture.get("classification") != CLASSIFICATION or fixture.get("m29b_authorized") is not False:
        _add(issues, "design_fixture_boundary")
    access = fixture.get("access_boundary", {})
    for key, value in access.items():
        expected = [] if key == "final_evaluation_seeds_accessed" else False
        if value != expected:
            _add(issues, f"design_access:{key}")

    conditions = fixture.get("conditions", [])
    if len(conditions) != 16:
        _add(issues, "condition_count")
    seen: set[str] = set()
    pair_surfaces: dict[str, list[str]] = {}
    retrieval_count = 0
    gradual_count = 0
    for row in conditions:
        condition_id = row.get("condition_id")
        label = str(condition_id)
        if not isinstance(condition_id, str) or condition_id in seen:
            _add(issues, f"condition_identity:{label}")
            continue
        seen.add(condition_id)
        latent = row.get("latent_scenario", {})
        evidence = row.get("evidence_bundle", {})
        oracle = row.get("independent_oracle", {})
        program = latent.get("semantic_program", {})
        surface = latent.get("numeric_surface", [])
        if latent.get("condition_id") != condition_id or evidence.get("condition_id") != condition_id or oracle.get("condition_id") != condition_id:
            _add(issues, f"condition_binding:{label}")
        if int(latent.get("development_seed", -1)) in FINAL_SEEDS:
            _add(issues, f"final_seed:{label}")
        if latent.get("oracle_created_before_rendering") is not True or latent.get("simulator_data_used") is not False or latent.get("final_evaluation_data_used") is not False:
            _add(issues, f"oracle_independence:{label}")
        if evidence.get("latent_scenario_sha256") != sha256_value(latent):
            _add(issues, f"latent_hash:{label}")
        evidence_body = dict(evidence)
        evidence_id = evidence_body.pop("evidence_bundle_id", None)
        if evidence_id != content_id("m29revidence", evidence_body):
            _add(issues, f"evidence_content_address:{label}")
        meaning = sha256_value(_semantics(program))
        if evidence.get("semantic_meaning_digest") != meaning:
            _add(issues, f"semantic_digest:{label}")
        alternate = row.get("alternate_rendering", {})
        if alternate.get("semantic_meaning_digest") != meaning or not alternate.get("text"):
            _add(issues, f"alternate_rendering:{label}")
        if alternate.get("rendering_id") == evidence.get("active_rendering"):
            _add(issues, f"rendering_identity:{label}")
        if canonical_json(surface) != canonical_json(evidence.get("numeric_surface")):
            _add(issues, f"surface_evidence_parity:{label}")
        if len(surface) != 52 or len({x.get("action_id") for x in surface}) != 52:
            _add(issues, f"surface_cardinality:{label}")
        pair_surfaces.setdefault(str(row.get("pair_id")), []).append(canonical_json(surface))
        if latent.get("retrieval_required") is True:
            retrieval_count += 1
        if program.get("strategy_id") == "gradual_bias" and int(program.get("min_actions", -1)) >= 3:
            gradual_count += 1
        query = query_map.get(condition_id)
        if query is None or query.get("query_id") != evidence.get("retrieval_query_id") or query.get("retrieval_required") is not latent.get("retrieval_required"):
            _add(issues, f"query_binding:{label}")
        oracle_program = oracle.get("strategy_program", {})
        if canonical_json(_semantics(oracle_program)) != canonical_json(program):
            _add(issues, f"oracle_program:{label}")
        if oracle.get("tested_optimizer_called") is not False or oracle.get("oracle_independent_of_language_rendering") is not True:
            _add(issues, f"oracle_call_boundary:{label}")
        try:
            action_ids, aggregate, objective, evaluated, feasible = _enumerate(surface, program)
        except Exception as exc:
            _add(issues, f"oracle_enumeration:{label}:{type(exc).__name__}")
            continue
        oracle_plan = oracle.get("plan", {})
        _verify_plan_content_address(oracle_plan, "m29rplan", issues, f"oracle_plan:{label}")
        stored_ids = [step.get("action_id") for step in oracle_plan.get("steps", [])]
        if stored_ids != action_ids:
            _add(issues, f"oracle_actions:{label}")
        if canonical_json(oracle_plan.get("aggregate")) != canonical_json(aggregate):
            _add(issues, f"oracle_aggregate:{label}")
        if oracle_plan.get("objective_value") != objective:
            _add(issues, f"oracle_objective:{label}")
        if oracle.get("evaluated_sequences") != evaluated or oracle.get("feasible_sequences") != feasible:
            _add(issues, f"oracle_accounting:{label}")
        parity = row.get("shared_optimizer_parity", {})
        if parity.get("action_ids") != action_ids or parity.get("objective_value") != objective:
            _add(issues, f"shared_optimizer_parity:{label}")

    if len(seen) != 16:
        _add(issues, "condition_uniqueness")
    if len(pair_surfaces) != 8 or any(len(values) != 2 or values[0] != values[1] for values in pair_surfaces.values()):
        _add(issues, "mirrored_surface_parity")
    if retrieval_count != 8:
        _add(issues, "retrieval_condition_count")
    if gradual_count < 4:
        _add(issues, "gradual_bias_coverage")

    return issues, contract


def build_audit_receipt(contract_path: Path) -> dict[str, Any]:
    issues, contract = verify(contract_path)
    body = {
        "schema_version": "grideval-g7-m29r-plan-audit/v1",
        "classification": CLASSIFICATION,
        "design_contract_id": contract.get("design_contract_id"),
        "auditor_source_sha256": sha256_file(Path(__file__).resolve()),
        "independent_imports_primary": False,
        "source_hashes_recomputed": True,
        "content_addresses_recomputed": True,
        "oracle_reenumerated": True,
        "pair_parity_recomputed": True,
        "access_seals_recomputed": True,
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "m29b_authorized": False,
    }
    return {"audit_id": content_id("m29rplanaudit", body), **body}


def create_once_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = build_audit_receipt(args.contract)
    if args.output:
        create_once_json(args.output, receipt)
    print(canonical_json(receipt))
    raise SystemExit(0 if receipt["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
