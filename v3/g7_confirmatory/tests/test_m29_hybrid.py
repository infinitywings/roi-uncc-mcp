"""Tests for the frozen M29-A hybrid agent-optimizer qualification."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from g7confirm.m29_counterfactual import (
    ARM_IDS,
    MODEL_ID,
    build_endpoint_table,
    build_execution_contract,
    build_model_request,
    execute_attempt,
    register_attempt,
    run_deterministic_cell,
    run_live_cell,
    verify_attempt,
    verify_primary_receipt,
)
from g7confirm.m29_hybrid_contract import (
    DESIGN_CONTRACT_ID,
    FROZEN_CANDIDATE_SURFACE_ID,
    STRATEGY_IDS,
    ContractViolation,
    assert_representation_parity,
    build_attack_state,
    build_candidate_library,
    build_optimization_request,
    candidate_for,
    condition_map,
    default_conditions,
    deterministic_strategy,
    optimizer_source_sha256,
    render_flat_text,
    render_structured_graph,
    run_optimizer,
    validate_candidate,
    validate_condition_registration,
    validate_design_contract,
    validate_optimization_request,
    validate_optimizer_result,
)
from g7confirm.m29_independent_audit import (
    build_audit_receipt,
    verify,
    verify_audit_receipt,
)


ROOT = Path(__file__).resolve().parents[1]


def _completion(payload: dict) -> dict:
    return {
        "id": "m29-mocked-completion",
        "object": "chat.completion",
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(payload, sort_keys=True),
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
    }


def _oracle_response(chat_payload: dict) -> dict:
    user = json.loads(chat_payload["messages"][1]["content"])
    arm_id = user["arm_id"]
    condition = condition_map()[user["condition_id"]]
    facts = user["scoped_state"]
    if facts["representation"] == "flat_text":
        fact_ids = [line.split(" | ", 1)[0] for line in facts["text"].splitlines()]
    else:
        fact_ids = [item["fact_id"] for item in facts["relations"]]
    strategy_id = deterministic_strategy(condition)
    if arm_id == "IA4-D":
        target_id = condition.expected_target_id
        assert target_id is not None
        candidate_id = candidate_for(strategy_id, target_id).candidate_id
        decision = {
            "decision": "plan",
            "strategy_id": strategy_id,
            "candidate_id": candidate_id,
            "evidence_refs": fact_ids[:4],
            "rationale": "Select the best valid fixture candidate.",
        }
    else:
        decision = {
            "decision": "optimize",
            "strategy_id": strategy_id,
            "evidence_refs": fact_ids[:4],
            "rationale": "Compile the evidence-conditioned strategy for the optimizer.",
        }
    return _completion(decision)


def test_frozen_design_contract_and_all_source_hashes_match() -> None:
    contract = validate_design_contract()
    assert contract["contract_id"] == DESIGN_CONTRACT_ID
    assert len(contract["arms"]) == 5
    assert len(contract["primary_contrasts"]) == 4
    assert len(contract["interventions"]) == 8
    assert len(contract["source_hash_manifest"]) == 7


def test_json_schema_designs_are_strict_at_the_root() -> None:
    names = (
        "m29_optimization_request.schema.json",
        "m29_optimizer_result.schema.json",
        "m29_attack_state.schema.json",
        "m29_counterfactual_contract.schema.json",
    )
    for name in names:
        schema = json.loads((ROOT / name).read_text(encoding="utf-8"))
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["required"]


def test_exactly_eight_pairs_and_sixteen_conditions_are_registered() -> None:
    validate_condition_registration()
    conditions = default_conditions()
    assert len(conditions) == 16
    assert len({item.condition_id for item in conditions}) == 16
    assert len({item.intervention_class for item in conditions}) == 8
    assert all(item.side in {"left", "right"} for item in conditions)


def test_candidate_surface_is_six_content_addressed_candidates() -> None:
    library = build_candidate_library()
    assert len(library.candidates) == 6
    assert len(set(library.ids())) == 6
    assert {
        (item.strategy_ids[0], item.target_ids[0]) for item in library.candidates
    } == {(strategy, target) for strategy in STRATEGY_IDS for target in ("DER_A", "DER_B")}


def test_flat_text_and_graph_views_share_raw_semantic_digest() -> None:
    for condition in default_conditions():
        state = build_attack_state(condition)
        flat = render_flat_text(state)
        graph = render_structured_graph(state)
        assert_representation_parity(flat, graph)
        assert flat["semantic_digest"] == graph["semantic_digest"]
        assert state["governance_separation"]["rka_exposed"] is False
        serialized = json.dumps(state).lower()
        assert all(prefix not in serialized for prefix in (
            "prj_", "jrn_", "dec_", "mis_", "chk_", "clm_"
        ))


def test_optimizer_request_result_round_trip_and_common_validator() -> None:
    condition = condition_map()["m29_sensitivity_reversal_right"]
    request = build_optimization_request(
        condition,
        "active_step",
        rationale="Use the active step under the registered high-load fixture.",
    )
    validate_optimization_request(request, condition)
    result = run_optimizer(request, condition)
    validate_optimizer_result(result, request)
    assert result["status"] == "feasible"
    assert result["optimizer_source_sha256"] == optimizer_source_sha256()
    assert request["candidate_surface_id"] == FROZEN_CANDIDATE_SURFACE_ID
    selected = result["selected_candidate_id"]
    validation = validate_candidate(
        arm_id="IA3-O",
        condition=condition,
        candidate_id=selected,
        rationale="Use the top feasible result.",
        optimizer_result_id=result["result_id"],
    )
    assert validation["accepted"] is True
    assert validation["effective_decision"] is True


def test_optimizer_is_byte_deterministic_for_identical_requests() -> None:
    condition = default_conditions()[0]
    request = build_optimization_request(
        condition, "active_step", rationale="Identical request."
    )
    assert run_optimizer(request, condition) == run_optimizer(request, condition)


def test_strict_request_rejects_extra_field_and_content_drift() -> None:
    condition = default_conditions()[0]
    request = build_optimization_request(
        condition, "active_step", rationale="Valid request."
    )
    request["hidden_capability"] = True
    with pytest.raises(ContractViolation, match="fields differ"):
        validate_optimization_request(request, condition)


def test_infeasible_and_tool_failure_results_fail_closed() -> None:
    for condition_id, status, failure in (
        ("m29_infeasible_optimizer_output_right", "infeasible", "NO_FEASIBLE_CANDIDATE"),
        ("m29_tool_failure_class_right", "tool_failure", "TOOL_UNAVAILABLE"),
    ):
        condition = condition_map()[condition_id]
        request = build_optimization_request(
            condition, "active_step", rationale="Exercise the failure contract."
        )
        result = run_optimizer(request, condition)
        assert result["status"] == status
        assert result["failure_class"] == failure
        assert result["selected_candidate_id"] is None
        assert result["environment_queries_used"] == 0


def test_validity_hole_uses_registered_partial_order_and_global_regret() -> None:
    condition = condition_map()["m29_validity_hole_right"]
    active_b = candidate_for("active_step", "DER_B").candidate_id
    reactive_a = candidate_for("reactive_shift", "DER_A").candidate_id
    assert active_b != reactive_a
    from g7confirm.m29_hybrid_contract import fixture_regret

    assert fixture_regret(condition, reactive_a) == 0.0
    assert fixture_regret(condition, active_b) == pytest.approx(0.16)


def test_all_deterministic_eligible_cells_match_the_oracle() -> None:
    cells = [
        run_deterministic_cell(arm_id, condition)
        for arm_id in ("IA2", "IA3-O")
        for condition in default_conditions()
    ]
    eligible = [item for item in cells if item["status"] == "completed"]
    assert len(eligible) == 28
    assert all(item["endpoints"]["oracle_selection_match"] for item in eligible)
    assert all(item["endpoints"]["validity_compliant"] for item in eligible)
    assert all(item["accounting"]["environment_queries"] == 0 for item in cells)


@patch("g7confirm.m29_counterfactual.request_json")
def test_one_live_hybrid_cell_compiles_and_uses_optimizer(mock_request) -> None:
    condition = default_conditions()[0]
    request = build_model_request("IA4-H", condition, 0)
    mock_request.return_value = _oracle_response(request["chat_payload"])
    cell = run_live_cell(
        arm_id="IA4-H",
        condition=condition,
        condition_index=0,
        base_url="http://ccil1s26m8hj6lws:8000/v1",
        execution_contract_id="m29exec_test",
    )
    assert cell["status"] == "completed"
    assert cell["optimization_request"] is not None
    assert cell["optimizer_result"]["status"] == "feasible"
    assert cell["validation"]["accepted"] is True
    assert cell["endpoints"]["oracle_selection_match"] is True
    assert cell["accounting"]["model_calls"] == 1
    assert cell["accounting"]["optimizer_calls"] == 1


@patch("g7confirm.m29_counterfactual.request_json")
def test_model_schema_failure_is_retained_without_retry(mock_request) -> None:
    condition = default_conditions()[0]
    mock_request.return_value = _completion({"unexpected": True})
    cell = run_live_cell(
        arm_id="IA4-D",
        condition=condition,
        condition_index=0,
        base_url="http://ccil1s26m8hj6lws:8000/v1",
        execution_contract_id="m29exec_test",
    )
    assert cell["status"] == "failed_closed"
    assert cell["accounting"]["model_calls"] == 1
    assert cell["accounting"]["invalid_proposals"] == 1
    assert cell["model"]["retry_count"] == 0
    assert mock_request.call_count == 1


@patch("g7confirm.m29_counterfactual.request_json")
@patch("g7confirm.m29_counterfactual.discover_model")
def test_full_mocked_attempt_and_non_importing_audit(
    mock_discover, mock_request, tmp_path: Path
) -> None:
    mock_discover.return_value = {
        "id": MODEL_ID,
        "owned_by": "vllm",
        "root": "mocked",
        "max_model_len": 262144,
    }
    mock_request.side_effect = lambda _url, *, timeout_s, payload: _oracle_response(payload)
    root = tmp_path / "attempt1"
    contract = register_attempt(root)
    assert contract["design_contract_id"] == DESIGN_CONTRACT_ID
    primary = execute_attempt(root)
    assert primary["status"] == "passed"
    assert primary["issues"] == []
    assert verify_attempt(root) == []
    assert verify_primary_receipt(root, primary) == []
    assert len(primary["endpoint_table"]) == 80
    assert primary["totals"]["model_calls"] == 44
    assert primary["totals"]["environment_queries"] == 0

    audit = build_audit_receipt(root)
    assert audit["status"] == "passed"
    assert audit["issues"] == []
    assert audit["endpoint_table"] == primary["endpoint_table"]
    assert verify(root)[0] == []
    assert verify_audit_receipt(root, audit) == []


def test_execution_contract_binds_final_source_and_80_cells() -> None:
    contract = build_execution_contract()
    assert contract["design_contract_id"] == DESIGN_CONTRACT_ID
    assert contract["arms"] == list(ARM_IDS)
    assert len(contract["conditions"]) == 16
    assert len(contract["expected_cell_paths"]) == 80
    assert len(contract["source_bindings"]) == 8
    assert contract["optimizer"]["source_sha256"] == optimizer_source_sha256()
    assert contract["access_boundary"]["simulator_allowed"] is False
    assert contract["m29b_authorized"] is False
