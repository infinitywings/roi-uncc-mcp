"""Focused tests for the M29-R offline complementarity design."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from g7confirm import m29r_complementarity as m29r
from g7confirm import m29r_design_contract as design_contract
from g7confirm import m29r_plan_audit as plan_audit


def test_static_design_sources_are_valid_and_content_addressed() -> None:
    sources = m29r.validate_design_sources()
    assert sources["plan"]["classification"] == "PRELIMINARY_ONLY"
    assert sources["corpus"]["corpus_id"].startswith("m29rcorpus_")
    assert sources["queries"]["query_manifest_id"].startswith("m29rqueries_")
    assert len(sources["source_hashes"]) == 3


def test_registered_ladder_and_contrasts_are_exact() -> None:
    plan = m29r.validate_design_sources()["plan"]
    assert [arm["arm_id"] for arm in plan["arms"]] == [
        "IA3-O", "IA3-SO", "IA4-D", "IA4-H", "IA4-HR", "IA5-OC"
    ]
    assert [row["contrast_id"] for row in plan["registered_contrasts"]] == [
        "semantic_compilation_value",
        "optimizer_tool_value",
        "llm_vs_symbolic_compiler",
        "retrieval_value",
        "oracle_headroom",
    ]


def test_scenario_registration_is_mirrored_and_uses_only_development_seeds() -> None:
    scenarios = m29r.default_scenarios()
    assert len(scenarios) == 16
    assert {row.development_seed for row in scenarios} == set(range(29001, 29009))
    assert not ({row.development_seed for row in scenarios} & set(range(9101, 9113)))
    pairs: dict[str, set[str]] = {}
    for row in scenarios:
        pairs.setdefault(row.pair_id, set()).add(row.side)
    assert len(pairs) == 8
    assert all(sides == {"left", "right"} for sides in pairs.values())


def test_pair_numeric_surfaces_are_byte_identical() -> None:
    scenarios = m29r.default_scenarios()
    by_pair: dict[str, list[m29r.LatentScenario]] = {}
    for scenario in scenarios:
        by_pair.setdefault(scenario.pair_id, []).append(scenario)
    for rows in by_pair.values():
        assert len(rows) == 2
        assert m29r.canonical_json(m29r.build_numeric_surface(rows[0])) == m29r.canonical_json(
            m29r.build_numeric_surface(rows[1])
        )


def test_every_numeric_surface_has_four_windows_and_52_unique_actions() -> None:
    for scenario in m29r.default_scenarios():
        surface = m29r.build_numeric_surface(scenario)
        assert len(surface) == 52
        assert len({row["action_id"] for row in surface}) == 52
        assert {row["window"] for row in surface} == set(m29r.WINDOWS)


def test_alternate_renderings_bind_the_same_latent_meaning() -> None:
    for scenario in m29r.default_scenarios():
        controlled = m29r.render_semantic_text(scenario, "controlled_operational_english")
        paraphrase = m29r.render_semantic_text(scenario, "held_out_compositional_paraphrase")
        assert controlled != paraphrase
        bundle = m29r.build_evidence_bundle(scenario)
        assert bundle["semantic_meaning_digest"] == m29r.semantic_meaning_digest(scenario)


def test_evidence_bundle_mutation_breaks_content_address() -> None:
    scenario = m29r.default_scenarios()[0]
    bundle = m29r.build_evidence_bundle(scenario)
    mutated = copy.deepcopy(bundle)
    mutated["machine_limits"]["max_actions"] = 3
    with pytest.raises(m29r.M29RContractError, match="content address drift"):
        m29r.validate_evidence_bundle(mutated)


def test_oracle_program_round_trip_and_neutral_program_are_distinct() -> None:
    for scenario in m29r.default_scenarios():
        bundle = m29r.build_evidence_bundle(scenario)
        oracle = m29r.build_oracle_program(scenario, bundle)
        neutral = m29r.build_neutral_program(bundle)
        m29r.validate_strategy_program(oracle, bundle)
        m29r.validate_strategy_program(neutral, bundle, require_meaning_match=False)
        assert not m29r.programs_equivalent(oracle, neutral)


def test_frozen_symbolic_compiler_has_predeclared_narrow_coverage() -> None:
    successful: list[str] = []
    for scenario in m29r.default_scenarios():
        bundle = m29r.build_evidence_bundle(scenario)
        program = m29r.symbolic_compile(scenario, bundle)
        if program is not None:
            assert m29r.programs_equivalent(program, m29r.build_oracle_program(scenario, bundle))
            successful.append(scenario.condition_id)
    assert successful == [
        "m29r_doctrine_priority_left",
        "m29r_doctrine_priority_right",
        "m29r_authority_supersession_left",
        "m29r_authority_supersession_right",
    ]


def test_shared_optimizer_matches_independent_recursive_oracle() -> None:
    for scenario in m29r.default_scenarios():
        bundle = m29r.build_evidence_bundle(scenario)
        oracle = m29r.run_independent_oracle(scenario, bundle)
        request = m29r.build_optimization_request(bundle, oracle["strategy_program"])
        result = m29r.run_shared_optimizer(request, bundle)
        assert result["status"] == "optimal"
        assert result["plan"]["objective_value"] == oracle["plan"]["objective_value"]
        assert [row["action_id"] for row in result["plan"]["steps"]] == [
            row["action_id"] for row in oracle["plan"]["steps"]
        ]
        assert result["evaluated_sequences"] == 13 ** 4


def test_optimizer_request_rejects_source_and_surface_drift() -> None:
    scenario = m29r.default_scenarios()[0]
    bundle = m29r.build_evidence_bundle(scenario)
    program = m29r.build_oracle_program(scenario, bundle)
    request = m29r.build_optimization_request(bundle, program)
    altered = copy.deepcopy(request)
    altered["candidate_surface_sha256"] = "0" * 64
    with pytest.raises(m29r.M29RContractError, match="content address drift"):
        m29r.validate_optimization_request(altered, bundle)


def test_oracle_plans_respect_multi_window_and_gradual_bias_requirements() -> None:
    gradual_count = 0
    for scenario in m29r.default_scenarios():
        bundle = m29r.build_evidence_bundle(scenario)
        oracle = m29r.run_independent_oracle(scenario, bundle)
        plan = oracle["plan"]
        m29r.validate_attack_plan(plan, bundle, oracle["strategy_program"])
        assert len(plan["steps"]) == 4
        if scenario.strategy_id == "gradual_bias" and scenario.min_actions >= 3:
            gradual_count += 1
            assert plan["aggregate"]["action_count"] >= 3
    assert gradual_count >= 4


def test_retrieval_manifest_balances_included_and_withheld_relevant_passages() -> None:
    manifest = m29r.validate_design_sources()["queries"]
    retrieval_rows = [row for row in manifest["queries"] if row["retrieval_required"]]
    assert len(retrieval_rows) == 8
    included = sum(row["expected_passage_id"] in row["flat_excerpt_passage_ids"] for row in retrieval_rows)
    assert included == 4


def test_design_fixture_is_stable_complete_and_sealed() -> None:
    first = m29r.build_design_fixture()
    second = m29r.build_design_fixture()
    assert first["design_fixture_id"] == second["design_fixture_id"]
    assert first["condition_count"] == 16
    assert first["access_boundary"] == {
        "llm_accessed": False,
        "embedding_accessed": False,
        "embedding_service_started_or_restarted": False,
        "docker_accessed": False,
        "simulator_accessed": False,
        "detector_accessed": False,
        "defense_accessed": False,
        "network_impairment_accessed": False,
        "physical_actuator_accessed": False,
        "final_evaluation_accessed": False,
        "final_evaluation_seeds_accessed": [],
        "rka_governance_attacker_view_accessed": False,
    }
    assert first["m29b_authorized"] is False


def test_json_schemas_are_strict_and_parseable() -> None:
    names = [
        "m29r_strategy_program.schema.json",
        "m29r_evidence_bundle.schema.json",
        "m29r_multistage_request.schema.json",
        "m29r_attack_plan.schema.json",
        "m29r_optimizer_result.schema.json",
    ]
    for name in names:
        schema = json.loads((m29r.ROOT / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
        assert schema["$schema"].endswith("2020-12/schema")


def test_module_imports_only_standard_library() -> None:
    source_path = Path(m29r.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported <= {
        "__future__", "argparse", "dataclasses", "hashlib", "itertools", "json",
        "math", "pathlib", "re", "typing",
    }


def test_design_contract_and_independent_plan_audit_pass(tmp_path: Path) -> None:
    fixture_path = m29r.ROOT / "artifacts/m29r_design_attempt1/design_fixture.json"
    contract = design_contract.build_contract(fixture_path)
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    issues, loaded = plan_audit.verify(contract_path)
    assert issues == []
    assert loaded["design_contract_id"] == contract["design_contract_id"]
    receipt = plan_audit.build_audit_receipt(contract_path)
    assert receipt["status"] == "passed"
    assert receipt["issues"] == []
    assert receipt["independent_imports_primary"] is False


def test_independent_plan_audit_detects_contract_mutation(tmp_path: Path) -> None:
    fixture_path = m29r.ROOT / "artifacts/m29r_design_attempt1/design_fixture.json"
    contract = design_contract.build_contract(fixture_path)
    contract["scientific_unlock_rule"]["minimum_witness_cells"] = 0
    contract_path = tmp_path / "mutated_contract.json"
    contract_path.write_text(json.dumps(contract, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    issues, _ = plan_audit.verify(contract_path)
    assert "design_contract_content_address" in issues
    assert "unlock_rule_binding" in issues


def test_plan_auditor_does_not_import_primary_module() -> None:
    tree = ast.parse(Path(plan_audit.__file__).read_text(encoding="utf-8"))
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    modules |= {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any("m29r_complementarity" in name for name in modules)
    assert not any("m29r_design_contract" in name for name in modules)
