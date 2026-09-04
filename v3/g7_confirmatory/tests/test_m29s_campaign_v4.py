from __future__ import annotations

import ast
import json
import threading
from pathlib import Path
from typing import Any, Mapping

import pytest

from g7confirm import m29s_campaign as base
from g7confirm import m29s_campaign_v3 as v3
from g7confirm import m29s_campaign_v4 as campaign
from g7confirm import m29s_independent_audit_v4 as independent
from g7confirm import m29s_semantic_compiler as design


ARTIFACTS = design.ROOT / "artifacts"
SPLITS = ARTIFACTS / "m29s_split_packets_attempt1"
SERVICE = ARTIFACTS / "m29s_service_preflight_attempt1"
DESIGN = ARTIFACTS / "m29s_design_contract_attempt2"


def _contract_kwargs(predecessor: Path) -> dict[str, Any]:
    return {
        "predecessor_receipt_path": predecessor,
        "design_contract_path": DESIGN / "contract.json",
        "plan_audit_path": DESIGN / "plan_audit_receipt.json",
        "split_commitment_path": SPLITS / "commitment.json",
        "preflight_path": SERVICE / "service_preflight.json",
        "development_embedding_path": SERVICE / "development_embedding.json",
        "held_out_embedding_path": SERVICE / "held_out_embedding.json",
        "authorization_note_id": "jrn_01M1PHYJFXBRK6BH421BHJTC60",
    }


def _rows() -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for split in design.SPLITS:
        packet = json.loads((SPLITS / f"{split}.json").read_text(encoding="utf-8"))
        result.update({row["condition_id"]: row for row in packet["conditions"]})
    return result


def _response_payload(
    request: Mapping[str, Any], rows: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    visible = json.loads(request["messages"][1]["content"])
    row = rows[visible["visible_evidence"]["condition_id"]]
    bundle = visible["visible_evidence"]
    passages = visible["corpus_passages"]
    condition = base._condition_object(row)
    schema = request["response_format"]["json_schema"]["schema"]
    staged = "evidence_ledger" in schema.get("properties", {})
    program_schema = schema["properties"]["strategy_program"] if staged else schema
    compiler_id = program_schema["properties"]["compiler_id"]["const"]
    slots = design.build_oracle_slots(condition, bundle, passages)
    visible_ids = {
        value["record_id"] for value in bundle["records"]
    } | {value["passage_id"] for value in passages}
    fallback = next(
        value["record_id"]
        for value in bundle["records"]
        if value["record_type"] == "doctrine" and value["status"] == "active"
    )
    for slot in design.SLOT_KEYS:
        supports = slots["slots"][slot]["supporting_evidence_ids"]
        slots["slots"][slot]["supporting_evidence_ids"] = [
            value if value in visible_ids else fallback for value in supports
        ]
    program = design.project_slots_to_program(slots, compiler_id=compiler_id)
    if not staged:
        return program
    validator_revision = (
        len(request["messages"]) == 4
        and "code-slot diagnostics" in request["messages"][-1]["content"]
    )
    if not validator_revision:
        slots["slots"]["strategy_id"]["value"] = condition.doctrine_code
    ledger = v3.build_oracle_ledger(bundle, passages)
    return {
        "evidence_ledger": ledger,
        "semantic_slots": slots,
        "strategy_program": program,
    }


def _mock_response(content: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": "mock-m29s-v4-response",
        "model": base.MODEL_ID,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        content, sort_keys=True, separators=(",", ":")
                    )
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 100,
            "total_tokens": 200,
        },
    }


def test_attempt3_is_preserved_and_conservatively_closed() -> None:
    contract = base.strict_json(
        campaign.PREDECESSOR_ROOT / "contract.json", "Attempt 3 contract"
    )
    assert v3.validate_execution_contract(contract) == []
    receipt = campaign.build_predecessor_receipt()
    assert receipt["development_cell_count"] == 8
    assert receipt["recorded_model_calls"] == 10
    assert receipt["conservative_model_calls"] == 18
    assert receipt["oracle_control_failures"] == 1
    assert receipt["held_out_cell_count"] == 0


def test_oracle_control_uses_the_active_visible_ledger() -> None:
    packet = json.loads((SPLITS / "development.json").read_text(encoding="utf-8"))
    embedding = json.loads(
        (SERVICE / "development_embedding.json").read_text(encoding="utf-8")
    )
    row = packet["conditions"][0]
    with v3._execution_profile():
        cell = campaign._run_cell(
            arm_id="IA5-OC",
            row=row,
            packet=packet,
            embedding=embedding,
            execution_contract_id="test-contract",
        )
    active = {
        value["authority"]
        for value in row["visible_evidence"]["records"]
        if value["status"] == "active"
    }
    assert cell["final_draft"]["evidence_ledger"]["authority_order"] == [
        value for value in design.AUTHORITY_ORDER if value in active
    ]
    assert cell["endpoints"]["all_slot_program_exact"] is True
    assert cell["accounting"]["model_calls"] == 0
    assert cell["access_boundary"]["llm_accessed"] is False


def test_attempt4_contract_binds_only_the_oracle_correction(tmp_path: Path) -> None:
    predecessor = campaign.build_predecessor_receipt()
    predecessor_path = tmp_path / "predecessor.json"
    base.create_once_json(predecessor_path, predecessor)
    contract = campaign.build_execution_contract(**_contract_kwargs(predecessor_path))
    assert campaign.validate_execution_contract(contract) == []
    assert contract["authorization_budget"]["maximum_cumulative_model_calls"] == 816
    assert contract["authorization_budget"]["remaining_after_attempt"] == 184
    assert contract["transport_profile"]["request_payloads_changed"] is False
    assert contract["predecessor_attempt"]["id"] == predecessor["predecessor_receipt_id"]


def test_full_mock_attempt4_restores_the_oracle_ceiling_and_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    predecessor = campaign.build_predecessor_receipt()
    predecessor_path = tmp_path / "predecessor.json"
    base.create_once_json(predecessor_path, predecessor)
    attempt = tmp_path / "attempt4"
    campaign.register_attempt(attempt, **_contract_kwargs(predecessor_path))
    rows = _rows()
    lock = threading.Lock()
    calls = 0

    def fake_post(
        _url: str, request: Mapping[str, Any], **_kwargs: Any
    ) -> dict[str, Any]:
        nonlocal calls
        with lock:
            calls += 1
        return _mock_response(_response_payload(request, rows))

    monkeypatch.setattr(base, "_post_json", fake_post)
    development = campaign.execute_split(attempt, "development")
    assert development["model_calls"] == 288
    assert (
        development["scientific_summary"]["IA5-OC"]["all_slot_successes"]
        == 16
    )
    freeze = campaign.build_development_freeze(attempt)
    base.create_once_json(attempt / "development_freeze.json", freeze)
    held_out = campaign.execute_split(attempt, "held_out")
    assert held_out["model_calls"] == 288
    assert held_out["scientific_summary"]["IA5-OC"]["all_slot_successes"] == 16
    assert calls == 576
    audit = independent.build_audit_receipt(attempt)
    assert audit["status"] == "passed", audit["issues"]
    base.create_once_json(attempt / "independent_audit_receipt.json", audit)
    primary = campaign.build_primary_receipt(attempt, independent_clean=True)
    base.create_once_json(attempt / "primary_receipt.json", primary)
    assert primary["status"] == "passed"
    assert campaign.verify_primary_receipt(attempt) == []
    assert independent.verify_audit_receipt(attempt) == []


def test_v4_independent_auditor_imports_no_primary_modules() -> None:
    tree = ast.parse(Path(independent.__file__).read_text(encoding="utf-8"))
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
    assert not any("m29s_campaign" in name for name in modules)
    assert not any("m29s_semantic_compiler" in name for name in modules)
