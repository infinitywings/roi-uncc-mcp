"""Regression tests for the frozen M28 decision-to-action evidence."""

from __future__ import annotations

import json
from pathlib import Path

from g7confirm.m28_decision_to_action import (
    EXPECTED_CANDIDATE_ID,
    M26_ROOT,
    PACKAGE_ROOT,
    build_action_requests,
    build_contract,
    verify_evidence,
)
from g7confirm.m28_independent_audit import verify_receipt
from g7confirm.m28_runtime import ACTORS, M28_RUNTIME_PROFILES, pair_id
from g7confirm.preliminary_only_gate import validate_preliminary_action_request


ROOT = PACKAGE_ROOT / "artifacts" / "m28_decision_to_action_attempt1"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_m28_profiles_are_two_actor_labelled_matched_pairs() -> None:
    assert ACTORS == ("IA3", "IA4")
    assert set(M28_RUNTIME_PROFILES) == {pair_id(actor) for actor in ACTORS}
    commands = {
        actor: M28_RUNTIME_PROFILES[pair_id(actor)]["probe_action_ids"]
        for actor in ACTORS
    }
    assert all(set(value) == {"DER_EV4_BESS:+30"} for value in commands.values())


def test_m28_four_action_requests_pass_the_m18_gate() -> None:
    requests = build_action_requests()
    assert sum(len(value) for value in requests.values()) == 4
    for actor in ACTORS:
        for request in requests[actor].values():
            assert request["partition_role"] == "attack_development"
            assert request["seed"] == 8109
            assert validate_preliminary_action_request(request) == []


def test_m28_contract_matches_final_bound_bytes() -> None:
    contract = _load(ROOT / "contract.json")
    assert contract == build_contract(ROOT)
    assert contract["runtime_design"]["runs"] == 4
    assert contract["runtime_design"]["retry_cap"] == 0
    assert contract["runtime_design"]["operating_point"] == "responsive_night"
    assert contract["translation"] == {
        "active_power_kw": 30.0,
        "actor_visible_target": "DER_B",
        "executor_may_modify_plan": False,
        "reactive_power_kvar": 0.0,
        "runtime_target": "DER_EV4_BESS",
        "strategy_id": "matched_step",
        "translation_is_fixed": True,
    }


def test_m28_reuses_verified_ia3_and_live_ia4_decisions() -> None:
    contract = _load(ROOT / "contract.json")
    assert {
        contract["decision_lineage"][actor]["candidate_id"] for actor in ACTORS
    } == {EXPECTED_CANDIDATE_ID}
    m26 = _load(M26_ROOT / "receipt.json")
    assert m26["result"]["model_transport_used"] is True
    assert m26["result"]["selected_candidate_id"] == EXPECTED_CANDIDATE_ID
    assert contract["decision_lineage"]["IA4"]["receipt_id"] == m26["receipt_id"]


def test_m28_runtime_completed_once_with_isolated_teardown() -> None:
    execution = _load(ROOT / "runtime_execution.json")
    assert execution["status"] == "complete"
    assert execution["issues"] == []
    assert execution["runs_completed"] == 4
    assert execution["retry_count"] == 0
    assert execution["network_mode"] == "none"
    assert execution["teardown_verified"] is True
    assert all(item["container_exit_code"] == 0 for item in execution["runs"])
    assert all(item["container_only_link_count"] == 39 for item in execution["runs"])


def test_m28_actor_blind_physical_json_is_exactly_equal() -> None:
    names = (
        "attack_trace.json",
        "dual_budget_trace.json",
        "g7_summary.json",
        "multi_der_source.json",
        "multi_der_traces.json",
    )
    for treatment in ("benign", "attack"):
        for name in names:
            ia3 = (ROOT / "runs" / "IA3" / treatment / name).read_bytes()
            ia4 = (ROOT / "runs" / "IA4" / treatment / name).read_bytes()
            assert ia3 == ia4


def test_m28_evidence_passes_primary_verification() -> None:
    evidence = _load(ROOT / "m28_decision_to_action.json")
    assert verify_evidence(ROOT) == []
    assert evidence["actor_blind_physical_equality"] == {
        "attack": True,
        "benign": True,
    }
    assert evidence["actor_paired_delta_equality"] is True
    assert evidence["max_abs_t30_true_voltage_delta_pu"] > 0.0


def test_m28_independent_receipt_verifies_current_bytes() -> None:
    receipt = _load(ROOT / "independent_audit_receipt.json")
    assert receipt["status"] == "passed"
    assert receipt["issues"] == []
    assert verify_receipt(ROOT, receipt) == []


def test_m28_access_seals_and_filesystem_are_closed() -> None:
    evidence = _load(ROOT / "m28_decision_to_action.json")
    boundary = evidence["access_boundary"]
    assert boundary["simulator_accessed"] is True
    assert boundary["simulated_actuator_used"] is True
    assert boundary["new_LLM_inference_used"] is False
    assert boundary["embedding_accessed"] is False
    assert boundary["detector_accessed"] is False
    assert boundary["defense_accessed"] is False
    assert boundary["real_network_used"] is False
    assert boundary["physical_field_actuator_accessed"] is False
    assert boundary["final_evaluation_accessed"] is False
    assert boundary["final_evaluation_seeds_accessed"] == []
    assert not any(path.is_symlink() for path in ROOT.rglob("*"))
