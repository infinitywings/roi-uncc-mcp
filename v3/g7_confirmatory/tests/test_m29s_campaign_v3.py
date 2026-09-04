from __future__ import annotations

import ast
import copy
import json
import threading
from pathlib import Path
from typing import Any, Mapping

import pytest

from g7confirm import m29s_campaign as base
from g7confirm import m29s_campaign_v2 as v2
from g7confirm import m29s_campaign_v3 as campaign
from g7confirm import m29s_independent_audit_v3 as independent
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
    validator_revision = len(request["messages"]) == 4 and "code-slot diagnostics" in request["messages"][-1]["content"]
    if not validator_revision:
        slots["slots"]["strategy_id"]["value"] = condition.doctrine_code
    ledger = campaign.build_oracle_ledger(bundle, passages)
    return {
        "evidence_ledger": ledger,
        "semantic_slots": slots,
        "strategy_program": program,
    }


def _mock_response(content: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": "mock-m29s-v3-response",
        "model": base.MODEL_ID,
        "choices": [{
            "finish_reason": "stop",
            "message": {"content": json.dumps(content, sort_keys=True, separators=(",", ":"))},
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
    }


def test_attempt2_is_preserved_and_conservatively_closed() -> None:
    contract = base.strict_json(
        campaign.PREDECESSOR_ROOT / "contract.json", "Attempt 2 contract"
    )
    assert v2.validate_execution_contract(contract) == []
    receipt = campaign.build_predecessor_receipt()
    assert receipt["development_cell_count"] == 20
    assert receipt["recorded_model_calls"] == 30
    assert receipt["conservative_model_calls"] == 36
    assert receipt["completed_staged_cells"] == 5
    assert receipt["staged_cells_with_length_failure"] == 0
    assert receipt["staged_cells_with_hidden_authority_failure"] == 5
    assert receipt["held_out_cell_count"] == 0


def test_active_authority_order_contains_only_visible_active_authorities() -> None:
    packet = json.loads((SPLITS / "development.json").read_text(encoding="utf-8"))
    for row in packet["conditions"]:
        bundle = row["visible_evidence"]
        expected = [
            value
            for value in design.AUTHORITY_ORDER
            if value in {
                record["authority"]
                for record in bundle["records"]
                if record["status"] == "active"
            }
        ]
        assert campaign.active_authority_order(bundle) == expected
        assert all(
            value in {record["authority"] for record in bundle["records"]}
            for value in expected
        )


def test_staged_validator_detects_slot_and_projection_without_values() -> None:
    packet = json.loads((SPLITS / "development.json").read_text(encoding="utf-8"))
    embedding = json.loads(
        (SERVICE / "development_embedding.json").read_text(encoding="utf-8")
    )
    row = packet["conditions"][0]
    condition = base._condition_object(row)
    passages = base.corpus_view("IA4-SV", row["condition_id"], packet, embedding)
    bundle = row["visible_evidence"]
    slots = design.build_oracle_slots(condition, bundle, passages)
    program = design.project_slots_to_program(slots, compiler_id="test")
    slots["slots"]["strategy_id"]["value"] = condition.doctrine_code
    draft = {
        "evidence_ledger": campaign.build_oracle_ledger(bundle, passages),
        "semantic_slots": slots,
        "strategy_program": program,
    }
    diagnostics = campaign.validate_strategy_draft(
        condition, draft, bundle, passages
    )
    pairs = {(value["code"], value["slot"]) for value in diagnostics["diagnostics"]}
    assert ("authority_conflict", "strategy_id") in pairs
    assert ("schema", "semantic_slots") in pairs
    encoded = base.canonical_json(diagnostics)
    assert condition.strategy_id not in encoded
    assert condition.doctrine_code not in encoded


def test_attempt3_contract_binds_visible_interface(tmp_path: Path) -> None:
    predecessor = campaign.build_predecessor_receipt()
    predecessor_path = tmp_path / "predecessor.json"
    base.create_once_json(predecessor_path, predecessor)
    contract = campaign.build_execution_contract(**_contract_kwargs(predecessor_path))
    assert campaign.validate_execution_contract(contract) == []
    assert contract["authorization_budget"]["maximum_cumulative_model_calls"] == 798
    assert contract["ledger_authority_contract"]["include_absent_authorities"] is False
    assert {"evidence_ledger", "semantic_slots"}.issubset(
        contract["tool_contract"]["validator_result_slots"]
    )


def test_full_mock_attempt3_exercises_staged_validator_and_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    predecessor = campaign.build_predecessor_receipt()
    predecessor_path = tmp_path / "predecessor.json"
    base.create_once_json(predecessor_path, predecessor)
    attempt = tmp_path / "attempt3"
    campaign.register_attempt(attempt, **_contract_kwargs(predecessor_path))
    rows = _rows()
    lock = threading.Lock()
    calls = 0

    def fake_post(_url: str, request: Mapping[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        with lock:
            calls += 1
        return _mock_response(_response_payload(request, rows))

    monkeypatch.setattr(base, "_post_json", fake_post)
    development = campaign.execute_split(attempt, "development")
    assert development["model_calls"] == 288
    assert development["scientific_summary"]["IA4-SV"]["repair_conversions"] > 0
    assert development["scientific_summary"]["IA4-SS"]["repair_conversions"] == 0
    freeze = campaign.build_development_freeze(attempt)
    base.create_once_json(attempt / "development_freeze.json", freeze)
    held_out = campaign.execute_split(attempt, "held_out")
    assert held_out["model_calls"] == 288
    assert calls == 576
    audit = independent.build_audit_receipt(attempt)
    assert audit["status"] == "passed", audit["issues"]
    base.create_once_json(attempt / "independent_audit_receipt.json", audit)
    primary = campaign.build_primary_receipt(attempt, independent_clean=True)
    base.create_once_json(attempt / "primary_receipt.json", primary)
    assert primary["status"] == "passed"
    assert campaign.verify_primary_receipt(attempt) == []
    assert independent.verify_audit_receipt(attempt) == []


def test_v3_independent_auditor_imports_no_primary_modules() -> None:
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
