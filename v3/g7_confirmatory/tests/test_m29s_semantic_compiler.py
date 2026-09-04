from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path

import pytest

from g7confirm import m29s_semantic_compiler as m29s


def _views(condition: m29s.LatentCondition) -> tuple[dict, dict, list[dict], list[dict]]:
    corpus = m29s.build_corpus()
    queries = m29s.build_query_manifest(corpus=corpus)
    flat = m29s.flat_corpus_view(condition, corpus, queries)
    retrieval = m29s.oracle_retrieval_view(condition, corpus)
    return corpus, queries, flat, retrieval


def test_factorial_plan_is_complete_and_equal_call() -> None:
    plan = m29s.validate_design_sources()["plan"]
    arms = {row["arm_id"]: row for row in plan["arms"]}
    assert set(arms) == set(m29s.FACTORIAL_ARMS + m29s.REFERENCE_ARMS + m29s.CONTROL_ARMS)
    assert all(arms[name]["model_calls_per_cell"] == 2 for name in m29s.FACTORIAL_ARMS)
    assert all(arms[name]["model_calls_per_cell"] == 1 for name in m29s.REFERENCE_ARMS)
    assert all(arms[name]["model_calls_per_cell"] == 0 for name in m29s.CONTROL_ARMS)
    assert 16 * sum(row["model_calls_per_cell"] for row in arms.values()) == 288
    assert plan["model_contract"]["maximum_additional_calls"] == 576
    assert plan["model_contract"]["maximum_cumulative_calls"] == 677
    assert plan["model_contract"]["pi_authorized_cumulative_ceiling"] == 1000


def test_factorial_has_every_interface_feedback_retrieval_combination() -> None:
    plan = m29s.validate_design_sources()["plan"]
    observed = {
        (row["interface"], row["feedback"], row["retrieval"])
        for row in plan["arms"]
        if row["causal_factorial"]
    }
    expected = {
        (interface, feedback, retrieval)
        for interface in ("flat", "staged")
        for feedback in ("neutral_self_revision", "validator_guided_revision")
        for retrieval in (False, True)
    }
    assert observed == expected


@pytest.mark.parametrize("split", m29s.SPLITS)
def test_split_registration_is_balanced(split: str) -> None:
    rows = m29s.default_conditions(split)
    assert len(rows) == 16
    assert len({row.pair_id for row in rows}) == 8
    assert len({row.seed for row in rows}) == 8
    assert sum(row.retrieval_required for row in rows) == 8
    for pair_id in {row.pair_id for row in rows}:
        assert {row.side for row in rows if row.pair_id == pair_id} == {"left", "right"}


def test_development_and_held_out_are_disjoint() -> None:
    development = m29s.default_conditions("development")
    held_out = m29s.default_conditions("held_out")
    assert {row.condition_id for row in development}.isdisjoint(row.condition_id for row in held_out)
    assert {row.seed for row in development}.isdisjoint(row.seed for row in held_out)
    assert {row.doctrine_code for row in development}.isdisjoint(row.doctrine_code for row in held_out)
    assert {
        m29s.sha256_value(m29s.semantic_core(row)) for row in development
    }.isdisjoint(m29s.sha256_value(m29s.semantic_core(row)) for row in held_out)


def test_m29s_fixture_is_disjoint_from_m29r() -> None:
    fixture = m29s.build_design_fixture()
    assert m29s.verify_m29r_disjointness(fixture) == []


def test_corpus_and_query_manifest_are_content_addressed() -> None:
    corpus = m29s.build_corpus()
    corpus_body = dict(corpus)
    identifier = corpus_body.pop("corpus_id")
    assert identifier == m29s.content_id("m29scorpus", corpus_body)
    assert len(corpus["passages"]) == 48
    queries = m29s.build_query_manifest(corpus=corpus)
    query_body = dict(queries)
    query_id = query_body.pop("query_manifest_id")
    assert query_id == m29s.content_id("m29squeries", query_body)
    assert len(queries["queries"]) == 32


def test_flat_view_withholds_half_of_retrieval_required_answers() -> None:
    corpus = m29s.build_corpus()
    queries = m29s.build_query_manifest(corpus=corpus)
    for split in m29s.SPLITS:
        rows = [row for row in m29s.default_conditions(split) if row.retrieval_required]
        included = 0
        for row in rows:
            ids = {value["passage_id"] for value in m29s.flat_corpus_view(row, corpus, queries)}
            included += row.doctrine_passage_id in ids
        assert included == 4


def test_visible_bundle_contains_no_oracle_or_latent_keys() -> None:
    for condition in m29s.default_conditions():
        bundle = m29s.build_visible_bundle(condition)
        text = m29s.canonical_json(bundle)
        assert "oracle" not in text.lower()
        assert "latent" not in text.lower()
        assert condition.seed == bundle["seed"]
        assert all(set(row) == {
            "record_id", "record_type", "authority", "issued_order",
            "valid_from", "valid_until", "status", "supersedes", "text",
        } for row in bundle["records"])


def test_oracle_ledger_slots_and_program_validate() -> None:
    for condition in m29s.default_conditions():
        _, _, flat, retrieval = _views(condition)
        passages = retrieval if condition.retrieval_required else flat
        bundle = m29s.build_visible_bundle(condition)
        ledger = m29s.build_oracle_ledger(bundle, passages)
        slots = m29s.build_oracle_slots(condition, bundle, passages)
        program = m29s.project_slots_to_program(slots, compiler_id="test_compiler")
        m29s.validate_evidence_ledger(ledger, bundle, passages)
        m29s.validate_semantic_slots(slots, bundle, passages)
        m29s.validate_strategy_program(program, bundle, passages)
        oracle = m29s.build_oracle_program(condition, bundle, passages)
        assert m29s.programs_equivalent(program, oracle)


def test_projection_canonicalizes_only_registered_sets() -> None:
    condition = m29s.default_conditions("development")[0]
    _, _, flat, _ = _views(condition)
    bundle = m29s.build_visible_bundle(condition)
    slots = m29s.build_oracle_slots(condition, bundle, flat)
    slots["slots"]["allowed_targets"]["value"].reverse()
    program = m29s.project_slots_to_program(slots, compiler_id="projection_test")
    assert program["allowed_targets"] == sorted(condition.allowed_targets)
    assert program["objective_weights"] == condition.weights()


def test_projection_does_not_repair_wrong_semantics() -> None:
    condition = m29s.default_conditions("development")[0]
    _, _, flat, _ = _views(condition)
    bundle = m29s.build_visible_bundle(condition)
    slots = m29s.build_oracle_slots(condition, bundle, flat)
    slots["slots"]["effect_direction"]["value"] = "decrease"
    program = m29s.project_slots_to_program(slots, compiler_id="projection_test")
    oracle = m29s.build_oracle_program(condition, bundle, flat)
    assert program["effect_direction"] == "decrease"
    assert not m29s.programs_equivalent(program, oracle)


def test_strong_parser_uses_only_visible_controlled_grammar() -> None:
    corpus = m29s.build_corpus()
    queries = m29s.build_query_manifest(corpus=corpus)
    for condition in m29s.default_conditions():
        bundle = m29s.build_visible_bundle(condition)
        passages = m29s.oracle_retrieval_view(condition, corpus)
        result = m29s.strong_deterministic_compile(condition, bundle, passages)
        assert result is not None
        oracle = m29s.build_oracle_program(condition, bundle, passages)
        assert m29s.programs_equivalent(result["strategy_program"], oracle)
    assert queries["top_k"] == 4


def test_strong_parser_fails_closed_when_required_doctrine_is_not_visible() -> None:
    corpus = m29s.build_corpus()
    queries = m29s.build_query_manifest(corpus=corpus)
    selected = [
        row for row in m29s.default_conditions("development")
        if row.retrieval_required and row.side == "right"
    ]
    assert len(selected) == 4
    for condition in selected:
        bundle = m29s.build_visible_bundle(condition)
        flat = m29s.flat_corpus_view(condition, corpus, queries)
        assert condition.doctrine_passage_id not in {row["passage_id"] for row in flat}
        assert m29s.strong_deterministic_compile(condition, bundle, flat) is None


def test_validator_reports_slots_without_expected_values() -> None:
    condition = m29s.default_conditions("development")[0]
    _, _, flat, _ = _views(condition)
    bundle = m29s.build_visible_bundle(condition)
    oracle = m29s.build_oracle_program(condition, bundle, flat)
    wrong = copy.deepcopy(oracle)
    wrong["effect_direction"] = "decrease"
    diagnostics = m29s.validate_strategy_draft(condition, wrong, bundle, flat)
    assert {tuple(sorted(row.items())) for row in diagnostics["diagnostics"]} >= {
        tuple(sorted({"code": "authority_conflict", "slot": "effect_direction"}.items()))
    }
    text = m29s.canonical_json(diagnostics)
    assert '"expected"' not in text
    assert '"correct"' not in text
    assert '"score"' not in text
    assert oracle["effect_direction"] not in text


def test_validator_rejects_unknown_codes_and_fields() -> None:
    payload = {
        "schema_version": "grideval-g7-m29s-validator-diagnostics/v1",
        "draft_id": "m29sdraft_" + "0" * 64,
        "visible_input_digest": "1" * 64,
        "diagnostics": [{"code": "answer", "slot": "strategy_id"}],
    }
    with pytest.raises(m29s.M29SContractError, match="unknown diagnostic code"):
        m29s.validate_diagnostics(payload)
    payload["diagnostics"] = [{"code": "schema", "slot": "strategy_id", "value": "x"}]
    with pytest.raises(m29s.M29SContractError, match="diagnostic row"):
        m29s.validate_diagnostics(payload)


def test_program_rejects_unknown_evidence_and_content_drift() -> None:
    condition = m29s.default_conditions("development")[0]
    _, _, flat, _ = _views(condition)
    bundle = m29s.build_visible_bundle(condition)
    program = m29s.build_oracle_program(condition, bundle, flat)
    program["required_evidence_ids"].append("m29s_ev_unknown")
    with pytest.raises(m29s.M29SContractError, match="unknown evidence"):
        m29s.validate_strategy_program(program, bundle, flat)


def test_provider_schemas_remove_only_unsupported_uniqueness_hints() -> None:
    condition = m29s.default_conditions("development")[0]
    _, _, flat, _ = _views(condition)
    bundle = m29s.build_visible_bundle(condition)
    for interface in ("flat", "staged"):
        schema = m29s.response_schema(
            interface=interface,
            condition_id=condition.condition_id,
            input_digest=m29s.visible_input_digest(bundle, flat),
            compiler_id="test_compiler",
        )
        text = m29s.canonical_json(schema)
        assert "uniqueItems" not in text
        assert '"additionalProperties":false' in text
        assert condition.condition_id in text


def test_matched_requests_have_byte_identical_user_evidence() -> None:
    condition = m29s.default_conditions("development")[0]
    _, _, flat, _ = _views(condition)
    bundle = m29s.build_visible_bundle(condition)
    flat_request = m29s.build_initial_model_request(
        arm_id="IA4-FS", condition=condition, bundle=bundle, passages=flat
    )
    staged_request = m29s.build_initial_model_request(
        arm_id="IA4-SS", condition=condition, bundle=bundle, passages=flat
    )
    assert flat_request["messages"][1] == staged_request["messages"][1]
    assert flat_request["model"] == staged_request["model"]
    assert flat_request["temperature"] == staged_request["temperature"] == 0
    assert flat_request["chat_template_kwargs"] == {"enable_thinking": False}


def test_neutral_self_revision_contains_no_diagnostic_signal() -> None:
    message = m29s.neutral_self_revision_message().lower()
    assert "correct" not in message
    assert "incorrect" not in message
    assert "diagnostic" not in message
    assert "external facts" in message


def test_design_fixture_is_stable_and_sealed() -> None:
    first = m29s.build_design_fixture()
    second = m29s.build_design_fixture()
    assert first["design_fixture_id"] == second["design_fixture_id"]
    assert first["condition_count"] == 32
    assert first["conditions_per_split"] == 16
    assert first["call_budget"]["maximum_additional_calls"] == 576
    assert first["call_budget"]["maximum_cumulative_calls"] == 677
    assert all(value is False or value == [] for value in first["access_boundary"].values())
    assert first["m29b_authorized"] is False


def test_design_fixture_content_address_changes_after_mutation() -> None:
    fixture = m29s.build_design_fixture()
    body = dict(fixture)
    identifier = body.pop("design_fixture_id")
    assert identifier == m29s.content_id("m29sfixture", body)
    mutated = copy.deepcopy(body)
    mutated["call_budget"]["maximum_additional_calls"] = 575
    assert identifier != m29s.content_id("m29sfixture", mutated)


def test_static_json_files_are_strict_and_parseable() -> None:
    for path in (
        m29s.PLAN_PATH,
        m29s.LEDGER_SCHEMA_PATH,
        m29s.SLOTS_SCHEMA_PATH,
        m29s.PROGRAM_SCHEMA_PATH,
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)


def test_new_sources_and_documents_are_english_only() -> None:
    paths = (
        Path(m29s.__file__),
        m29s.ROOT / "M29S_EXECUTOR_BACKBRIEF.md",
        m29s.ROOT / "M29S_INDEPENDENT_AUDIT_PLAN.md",
        m29s.PLAN_PATH,
        m29s.LEDGER_SCHEMA_PATH,
        m29s.SLOTS_SCHEMA_PATH,
        m29s.PROGRAM_SCHEMA_PATH,
    )
    cjk = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
    assert not {
        path.name: cjk.findall(path.read_text(encoding="utf-8"))
        for path in paths
        if cjk.search(path.read_text(encoding="utf-8"))
    }


def test_module_imports_only_standard_library() -> None:
    tree = ast.parse(Path(m29s.__file__).read_text(encoding="utf-8"))
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
        "__future__", "argparse", "copy", "dataclasses", "hashlib", "json",
        "pathlib", "re", "typing",
    }
