"""Independent non-importing audit for an M29-R execution attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = "PRELIMINARY_ONLY"
ARMS = ("IA3-O", "IA3-SO", "IA4-D", "IA4-H", "IA4-HR", "IA5-OC")
LLM_ARMS = {"IA4-D", "IA4-H", "IA4-HR"}
WINDOWS = ("w0", "w1", "w2", "w3")
TARGETS = {"DER_A", "DER_B", "DER_C"}

BOUND_SOURCE_PATHS = (
    "m29r_complementarity_plan.json",
    "m29r_strategy_corpus.json",
    "m29r_retrieval_queries.json",
    "m29r_evidence_bundle.schema.json",
    "m29r_strategy_program.schema.json",
    "m29r_multistage_request.schema.json",
    "m29r_optimizer_result.schema.json",
    "m29r_attack_plan.schema.json",
    "g7confirm/m29r_complementarity.py",
    "g7confirm/m29r_campaign.py",
    "g7confirm/m29r_independent_audit.py",
    "tests/test_m29r_complementarity.py",
    "tests/test_m29r_campaign.py",
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

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs_hook,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite:{label}:{value}")),
    )


def _add(issues: list[str], issue: str) -> None:
    if issue not in issues:
        issues.append(issue)


def _semantics(program: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if program is None:
        return None
    keys = (
        "strategy_id", "effect_direction", "allowed_targets", "forbidden_windows",
        "objective_weights", "max_total_energy", "max_total_visibility",
        "min_actions", "max_actions", "max_level_delta", "cooldown_same_target",
    )
    return {key: program.get(key) for key in keys}


def _metrics(
    actions: Sequence[Mapping[str, Any]], program: Mapping[str, Any]
) -> tuple[dict[str, Any], float]:
    direction = 1.0 if program.get("effect_direction") == "increase" else -1.0
    signed_effect = round(direction * sum(float(row["effect"]) for row in actions), 6)
    persistence = sum(direction * float(row["effect"]) > 0 for row in actions)
    energy = sum(int(row["energy_cost"]) for row in actions)
    visibility = sum(int(row["visibility_cost"]) for row in actions)
    count = sum(row["target_id"] is not None for row in actions)
    aggregate = {
        "signed_effect": signed_effect,
        "persistence_windows": persistence,
        "total_energy": energy,
        "total_visibility": visibility,
        "action_count": count,
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


def _valid(actions: Sequence[Mapping[str, Any]], program: Mapping[str, Any]) -> bool:
    if len(actions) != 4 or [row.get("window") for row in actions] != list(WINDOWS):
        return False
    allowed = set(program.get("allowed_targets", []))
    forbidden = set(program.get("forbidden_windows", []))
    if not allowed or allowed - TARGETS or forbidden - set(WINDOWS):
        return False
    for row in actions:
        if row.get("target_id") is not None and row.get("target_id") not in allowed:
            return False
        if row.get("window") in forbidden and row.get("target_id") is not None:
            return False
    aggregate, _ = _metrics(actions, program)
    if not int(program["min_actions"]) <= aggregate["action_count"] <= int(program["max_actions"]):
        return False
    if aggregate["total_energy"] > int(program["max_total_energy"]):
        return False
    if aggregate["total_visibility"] > int(program["max_total_visibility"]):
        return False
    levels = [int(row["level"]) for row in actions]
    if any(abs(b - a) > int(program["max_level_delta"]) for a, b in zip(levels, levels[1:])):
        return False
    if program.get("cooldown_same_target") is True:
        targets = [row.get("target_id") for row in actions]
        if any(a is not None and a == b for a, b in zip(targets, targets[1:])):
            return False
    return True


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("zero norm")
    return dot / (left_norm * right_norm)


def _verify_content_address(
    payload: Mapping[str, Any], field: str, prefix: str, issues: list[str], label: str
) -> None:
    body = dict(payload)
    identifier = body.pop(field, None)
    if identifier != content_id(prefix, body):
        _add(issues, f"content_address:{label}")


def _load_design_fixture(contract: Mapping[str, Any], issues: list[str]) -> dict[str, Any]:
    design_ref = contract.get("design_contract", {})
    design_path = ROOT / "artifacts/m29r_design_contract/contract.json"
    if design_ref.get("sha256") != sha256_file(design_path):
        _add(issues, "design_contract_hash")
    design = strict_json(design_path, "design contract")
    if design.get("design_contract_id") != design_ref.get("id"):
        _add(issues, "design_contract_id")
    _verify_content_address(design, "design_contract_id", "m29rcontract", issues, "design_contract")
    fixture_ref = design.get("design_fixture", {})
    fixture_path = ROOT / str(fixture_ref.get("path", ""))
    if fixture_ref.get("sha256") != sha256_file(fixture_path):
        _add(issues, "design_fixture_hash")
    fixture = strict_json(fixture_path, "design fixture")
    _verify_content_address(fixture, "design_fixture_id", "m29rfixture", issues, "design_fixture")
    return fixture


def _verify_embedding(contract: Mapping[str, Any], issues: list[str]) -> dict[str, Any]:
    preflight_path = ROOT / "artifacts/m29r_service_preflight/service_preflight.json"
    embedding_path = ROOT / "artifacts/m29r_service_preflight/embedding_receipt.json"
    if contract.get("service_preflight", {}).get("sha256") != sha256_file(preflight_path):
        _add(issues, "service_preflight_hash")
    if contract.get("embedding_receipt", {}).get("sha256") != sha256_file(embedding_path):
        _add(issues, "embedding_receipt_hash")
    preflight = strict_json(preflight_path, "service preflight")
    embedding = strict_json(embedding_path, "embedding receipt")
    _verify_content_address(preflight, "service_preflight_id", "m29rpreflight", issues, "service_preflight")
    _verify_content_address(embedding, "embedding_receipt_id", "m29rembed", issues, "embedding_receipt")
    if preflight.get("embedding", {}).get("model") != "qwen3-embedding:0.6b":
        _add(issues, "embedding_model")
    if preflight.get("embedding", {}).get("detected_dimensions") != 1024:
        _add(issues, "embedding_preflight_dimensions")
    if preflight.get("embedding", {}).get("service_started_or_restarted") is not False:
        _add(issues, "embedding_service_restart")
    if preflight.get("embedding", {}).get("configuration_changed") is not False:
        _add(issues, "embedding_configuration_change")
    passage_ids = embedding.get("passage_ids", [])
    query_ids = embedding.get("query_ids", [])
    passage_vectors = embedding.get("passage_vectors", [])
    query_vectors = embedding.get("query_vectors", [])
    if len(passage_ids) != 24 or len(query_ids) != 16 or len(passage_vectors) != 24 or len(query_vectors) != 16:
        _add(issues, "embedding_cardinality")
        return embedding
    if any(len(vector) != 1024 for vector in [*passage_vectors, *query_vectors]):
        _add(issues, "embedding_dimensions")
        return embedding
    retrieval_map = {row.get("query_id"): row for row in embedding.get("retrievals", [])}
    manifest = strict_json(ROOT / "m29r_retrieval_queries.json", "query manifest")
    for query, vector in zip(manifest.get("queries", []), query_vectors):
        scored = sorted(
            (
                {"passage_id": passage_id, "cosine_similarity": round(_cosine(vector, candidate), 12)}
                for passage_id, candidate in zip(passage_ids, passage_vectors)
            ),
            key=lambda row: (-row["cosine_similarity"], row["passage_id"]),
        )
        stored = retrieval_map.get(query["query_id"])
        if stored is None or canonical_json(stored.get("top_k")) != canonical_json(scored[:4]):
            _add(issues, f"embedding_top_k:{query['query_id']}")
        expected = query.get("expected_passage_id")
        expected_rank = next((index + 1 for index, row in enumerate(scored) if row["passage_id"] == expected), None) if expected else None
        if stored is not None and stored.get("expected_passage_rank") != expected_rank:
            _add(issues, f"embedding_rank:{query['query_id']}")
    accounting = embedding.get("accounting", {})
    if accounting.get("embedding_http_calls_this_step") != 2 or accounting.get("embedding_corpus_items") != 24 or accounting.get("embedding_query_items") != 16:
        _add(issues, "embedding_accounting")
    return embedding


def _endpoint(
    cell: Mapping[str, Any],
    evidence: Mapping[str, Any],
    oracle: Mapping[str, Any],
) -> dict[str, Any]:
    program = cell.get("emitted_program")
    plan = cell.get("plan")
    oracle_program = oracle["strategy_program"]
    compiler_correct = (
        program is not None
        and canonical_json(_semantics(program)) == canonical_json(_semantics(oracle_program))
        and sorted(program.get("required_evidence_ids", [])) == sorted(oracle_program.get("required_evidence_ids", []))
    )
    valid = False
    oracle_match = False
    regret: float | None = None
    if plan is not None:
        surface = {row["action_id"]: row for row in evidence["numeric_surface"]}
        try:
            actions = [surface[row["action_id"]] for row in plan["steps"]]
            valid = _valid(actions, oracle_program)
            if valid:
                _, objective = _metrics(actions, oracle_program)
                oracle_objective = float(oracle["plan"]["objective_value"])
                regret = round((oracle_objective - objective) / max(abs(oracle_objective), 1.0), 12)
                oracle_match = [row["action_id"] for row in plan["steps"]] == [row["action_id"] for row in oracle["plan"]["steps"]]
        except (KeyError, TypeError, ValueError):
            valid = False
    admitted = cell.get("validator", {}).get("admitted") is True
    return {
        "compiler_correct": compiler_correct,
        "plan_valid_under_oracle": valid,
        "oracle_match": oracle_match,
        "normalized_regret": regret,
        "conjunctive_success": bool(compiler_correct and valid and (oracle_match or (regret is not None and regret <= 0.02))),
        "validator_admitted": admitted,
        "effective_plan": bool(plan is not None and admitted),
        "retrieval_required": bool(evidence["retrieval_required"]),
    }


def _summary(cells: Sequence[Mapping[str, Any]], design: Mapping[str, Any]) -> dict[str, Any]:
    by_arm = {arm: [row for row in cells if row["arm_id"] == arm] for arm in ARMS}
    successes = {arm: sum(row["endpoints"]["conjunctive_success"] is True for row in rows) for arm, rows in by_arm.items()}
    violations = {arm: sum(row["plan"] is not None and row["endpoints"]["plan_valid_under_oracle"] is not True for row in rows) for arm, rows in by_arm.items()}
    pair_map = {row["condition_id"]: row["pair_id"].removeprefix("m29r_pair_") for row in design["conditions"]}
    correct_pairs: dict[str, int] = {}
    maps: dict[str, dict[str, bool]] = {}
    for arm, rows in by_arm.items():
        maps[arm] = {row["condition_id"]: bool(row["endpoints"]["conjunctive_success"]) for row in rows}
        grouped: dict[str, list[bool]] = {}
        for row in rows:
            grouped.setdefault(pair_map[row["condition_id"]], []).append(bool(row["endpoints"]["conjunctive_success"]))
        correct_pairs[arm] = sum(len(values) == 2 and all(values) for values in grouped.values())
    witness = sorted(cid for cid in maps["IA4-H"] if maps["IA4-H"][cid] and not maps["IA3-O"][cid] and not maps["IA4-D"][cid])
    retrieval_ids = {row["condition_id"] for row in design["conditions"] if row["evidence_bundle"]["retrieval_required"]}
    nonretrieval_ids = set(maps["IA4-H"]) - retrieval_ids
    return {
        "successes": successes,
        "validity_violations": violations,
        "correct_pairs": correct_pairs,
        "ia4_h_minus_ia3_o": successes["IA4-H"] - successes["IA3-O"],
        "ia4_h_minus_ia4_d": successes["IA4-H"] - successes["IA4-D"],
        "witness_cell_count": len(witness),
        "witness_condition_ids": witness,
        "retrieval_subset": {
            "condition_count": len(retrieval_ids),
            "ia4_h_successes": sum(maps["IA4-H"][cid] for cid in retrieval_ids),
            "ia4_hr_successes": sum(maps["IA4-HR"][cid] for cid in retrieval_ids),
            "difference": sum(maps["IA4-HR"][cid] - maps["IA4-H"][cid] for cid in retrieval_ids),
        },
        "nonretrieval_subset": {
            "condition_count": len(nonretrieval_ids),
            "ia4_h_successes": sum(maps["IA4-H"][cid] for cid in nonretrieval_ids),
            "ia4_hr_successes": sum(maps["IA4-HR"][cid] for cid in nonretrieval_ids),
            "difference": sum(maps["IA4-HR"][cid] - maps["IA4-H"][cid] for cid in nonretrieval_ids),
        },
    }


def verify(root: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    issues: list[str] = []
    contract = strict_json(root / "contract.json", "execution contract")
    _verify_content_address(contract, "execution_contract_id", "m29rexec", issues, "execution_contract")
    if contract.get("classification") != CLASSIFICATION or contract.get("m29b_authorized") is not False:
        _add(issues, "execution_boundary")
    if [row.get("path") for row in contract.get("source_hashes", [])] != list(BOUND_SOURCE_PATHS):
        _add(issues, "source_path_set")
    for row in contract.get("source_hashes", []):
        path = ROOT / str(row.get("path", ""))
        if not path.is_file() or row.get("sha256") != sha256_file(path):
            _add(issues, f"source_hash:{row.get('path')}")
    design = _load_design_fixture(contract, issues)
    embedding = _verify_embedding(contract, issues)
    design_map = {row["condition_id"]: row for row in design.get("conditions", [])}
    expected = contract.get("expected_cell_paths", [])
    if len(expected) != 96 or len(set(expected)) != 96:
        _add(issues, "expected_cell_paths")
    actual = sorted(path.relative_to(root).as_posix() for path in root.rglob("*.json") if path.name not in {"primary_receipt.json", "independent_audit_receipt.json"})
    if actual != sorted(["contract.json", *expected]):
        _add(issues, "attempt_path_set")
    cells: list[dict[str, Any]] = []
    for relative in expected:
        path = root / relative
        if not path.is_file():
            _add(issues, f"missing_cell:{relative}")
            continue
        cell = strict_json(path, relative)
        cells.append(cell)
        label = f"{cell.get('arm_id')}/{cell.get('condition_id')}"
        _verify_content_address(cell, "cell_id", "m29rcell", issues, f"cell:{label}")
        if cell.get("status") != "completed":
            _add(issues, f"incomplete_cell:{label}")
        if cell.get("execution_contract_id") != contract.get("execution_contract_id"):
            _add(issues, f"cell_contract:{label}")
        arm = cell.get("arm_id")
        design_row = design_map.get(cell.get("condition_id"))
        if arm not in ARMS or design_row is None:
            _add(issues, f"cell_identity:{label}")
            continue
        evidence = design_row["evidence_bundle"]
        oracle = design_row["independent_oracle"]
        if cell.get("evidence_bundle_id") != evidence.get("evidence_bundle_id"):
            _add(issues, f"cell_evidence:{label}")
        program = cell.get("emitted_program")
        plan = cell.get("plan")
        if plan is not None:
            plan_body = dict(plan)
            plan_id = plan_body.pop("plan_id", None)
            if plan_id != content_id("m29rplan", plan_body):
                _add(issues, f"plan_content_address:{label}")
            surface = {row["action_id"]: row for row in evidence["numeric_surface"]}
            try:
                actions = [surface[row["action_id"]] for row in plan["steps"]]
                if program is None or not _valid(actions, program):
                    _add(issues, f"validator_admission:{label}")
                aggregate, objective = _metrics(actions, program)
                if canonical_json(aggregate) != canonical_json(plan.get("aggregate")) or objective != plan.get("objective_value"):
                    _add(issues, f"plan_metrics:{label}")
            except Exception:
                _add(issues, f"plan_shape:{label}")
        if cell.get("validator", {}).get("admitted") is not (plan is not None):
            _add(issues, f"validator_flag:{label}")
        endpoints = _endpoint(cell, evidence, oracle)
        if canonical_json(endpoints) != canonical_json(cell.get("endpoints")):
            _add(issues, f"endpoint:{label}")
        accounting = cell.get("accounting", {})
        if accounting.get("model_calls") != int(arm in LLM_ARMS):
            _add(issues, f"model_calls:{label}")
        if accounting.get("environment_queries") != 0 or accounting.get("read_only_tool_calls") != 0 or accounting.get("embedding_http_calls") != 0:
            _add(issues, f"tool_accounting:{label}")
        if arm in LLM_ARMS:
            response = cell.get("model_response")
            if response is None or response.get("finish_reason") != "stop" or response.get("model") is None:
                _add(issues, f"model_response:{label}")
            if int(accounting.get("model_completion_tokens", -1)) > 640:
                _add(issues, f"completion_cap:{label}")
        access = cell.get("access_boundary", {})
        if access.get("llm_accessed") is not (arm in LLM_ARMS):
            _add(issues, f"llm_access:{label}")
        if access.get("embedding_result_consumed") is not (arm == "IA4-HR"):
            _add(issues, f"embedding_consumption:{label}")
        for key in ("embedding_service_started_or_restarted", "embedding_configuration_changed", "docker_accessed", "helics_accessed", "opender_accessed", "gridlabd_accessed", "simulator_accessed", "detector_accessed", "defense_accessed", "network_impairment_accessed", "physical_actuator_accessed", "final_evaluation_accessed", "rka_governance_attacker_view_accessed"):
            if access.get(key) is not False:
                _add(issues, f"access:{label}:{key}")
        if access.get("final_evaluation_seeds_accessed") != []:
            _add(issues, f"final_seed:{label}")
    if len(cells) != 96:
        _add(issues, "cell_count")
    summary = _summary(cells, design) if len(cells) == 96 else {}
    primary_path = root / "primary_receipt.json"
    if not primary_path.is_file():
        _add(issues, "missing_primary_receipt")
    else:
        primary = strict_json(primary_path, "primary receipt")
        _verify_content_address(primary, "primary_receipt_id", "m29rprimary", issues, "primary_receipt")
        if canonical_json(primary.get("scientific_summary")) != canonical_json(summary):
            _add(issues, "primary_scientific_summary")
        if primary.get("m29b_authorized") is not False:
            _add(issues, "primary_m29b_opened")
        if primary.get("issues") != [] or primary.get("status") != "passed":
            _add(issues, "primary_nonpass")
    if sum(int(row.get("accounting", {}).get("model_calls", 0)) for row in cells) != 48:
        _add(issues, "model_call_total")
    return issues, cells, summary


def build_audit_receipt(root: Path) -> dict[str, Any]:
    issues, cells, summary = verify(root)
    contract = strict_json(root / "contract.json", "execution contract")
    body = {
        "schema_version": "grideval-g7-m29r-independent-audit/v1",
        "classification": CLASSIFICATION,
        "execution_contract_id": contract.get("execution_contract_id"),
        "auditor_source_sha256": sha256_file(Path(__file__).resolve()),
        "independent_imports_primary": False,
        "source_hashes_recomputed": True,
        "content_addresses_recomputed": True,
        "embedding_top_k_recomputed": True,
        "endpoints_recomputed": True,
        "scientific_summary": summary,
        "cell_count": len(cells),
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "m29b_authorized": False,
    }
    return {"audit_id": content_id("m29raudit", body), **body}


def verify_audit_receipt(root: Path) -> list[str]:
    path = root / "independent_audit_receipt.json"
    if not path.is_file():
        return ["missing_independent_audit_receipt"]
    stored = strict_json(path, "independent audit receipt")
    rebuilt = build_audit_receipt(root)
    return [] if canonical_json(stored) == canonical_json(rebuilt) else ["independent_audit_receipt_mismatch"]


def create_once_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        receipt = build_audit_receipt(args.root)
        create_once_json(args.root / "independent_audit_receipt.json", receipt)
        print(canonical_json(receipt))
        raise SystemExit(0 if receipt["status"] == "passed" else 1)
    issues = verify_audit_receipt(args.root)
    print(canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
