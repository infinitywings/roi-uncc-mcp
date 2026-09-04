"""Regression tests for the M29-R Attempt 2 provider-only delta."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from g7confirm import m29r_campaign as base
from g7confirm import m29r_campaign_v2 as campaign
from g7confirm import m29r_independent_audit as independent_v1
from g7confirm import m29r_independent_audit_v2 as independent_v2
from g7confirm.m29r_complementarity import (
    build_evidence_bundle,
    build_oracle_program,
    default_scenarios,
    program_semantics,
    run_independent_oracle,
    validate_strategy_program,
)


ARTIFACT_ROOT = campaign.ROOT / "artifacts"
COMPATIBILITY_AUDIT = (
    ARTIFACT_ROOT / "m29r_provider_compatibility_contract/plan_audit_receipt.json"
)


def _embedding_receipt() -> dict[str, Any]:
    return base.strict_json_file(
        ARTIFACT_ROOT / "m29r_service_preflight/embedding_receipt.json",
        "test embedding receipt",
    )


def _contains_key(value: Any, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(_contains_key(item, target) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, target) for item in value)
    return False


def _oracle_model_response(
    arm_id: str, model_request: dict[str, Any]
) -> dict[str, Any]:
    user = json.loads(model_request["messages"][1]["content"])
    condition_id = user["evidence_bundle"]["condition_id"]
    scenario = next(
        row for row in default_scenarios() if row.condition_id == condition_id
    )
    bundle = build_evidence_bundle(scenario)
    program = build_oracle_program(scenario, bundle)
    content: dict[str, Any] = {
        "strategy_program": {
            **program_semantics(program),
            "required_evidence_ids": program["required_evidence_ids"],
        }
    }
    if arm_id == "IA4-D":
        oracle = run_independent_oracle(scenario, bundle)
        content["action_ids"] = [
            row["action_id"] for row in oracle["plan"]["steps"]
        ]
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return {
        "id": "mock-v2-response",
        "model": base.MODEL_ID,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": encoded},
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 100,
            "total_tokens": 200,
        },
    }


def _contract_kwargs(authorized_total_calls: int) -> dict[str, Any]:
    return {
        "preflight_path": ARTIFACT_ROOT
        / "m29r_service_preflight/service_preflight.json",
        "embedding_receipt_path": ARTIFACT_ROOT
        / "m29r_service_preflight/embedding_receipt.json",
        "design_contract_path": ARTIFACT_ROOT / "m29r_design_contract/contract.json",
        "plan_audit_path": ARTIFACT_ROOT
        / "m29r_design_contract/plan_audit_receipt.json",
        "compatibility_audit_path": COMPATIBILITY_AUDIT,
        "authorization_note_id": "jrn_test_authorization",
        "authorized_total_calls": authorized_total_calls,
        "prior_read_only_chat_requests": 53,
    }


@pytest.mark.parametrize("arm_id", ["IA4-D", "IA4-H", "IA4-HR"])
def test_provider_projection_changes_only_registered_wire_fields(arm_id: str) -> None:
    scenario = default_scenarios()[0]
    bundle = build_evidence_bundle(scenario)
    embedding = _embedding_receipt()
    original = base.build_model_request(arm_id, bundle, embedding)
    revised = campaign.build_model_request(arm_id, bundle, embedding)
    assert _contains_key(
        original["response_format"]["json_schema"]["schema"], "uniqueItems"
    )
    assert not _contains_key(
        revised["response_format"]["json_schema"]["schema"], "uniqueItems"
    )
    expected = base.canonical_copy(original)
    original_schema = expected["response_format"]["json_schema"]["schema"]
    expected["response_format"]["json_schema"]["schema"] = (
        campaign._strip_provider_unsupported_keywords(original_schema)
    )
    expected["chat_template_kwargs"] = {"enable_thinking": False}
    expected["stream"] = False
    expected["n"] = 1
    assert revised == expected
    assert revised["max_tokens"] == original["max_tokens"] == 640
    assert revised["seed"] == original["seed"]
    assert revised["messages"] == original["messages"]


def test_local_validator_retains_uniqueness_enforcement() -> None:
    scenario = default_scenarios()[0]
    bundle = build_evidence_bundle(scenario)
    program = build_oracle_program(scenario, bundle)
    program["allowed_targets"] = [
        program["allowed_targets"][0],
        program["allowed_targets"][0],
    ]
    with pytest.raises(Exception, match="invalid allowed-target set"):
        validate_strategy_program(program, bundle, require_meaning_match=False)


def test_current_authorization_ceiling_fails_closed() -> None:
    with pytest.raises(campaign.M29RV2Error, match="fewer than 48"):
        campaign.build_execution_contract(**_contract_kwargs(100))


def test_one_call_extension_builds_valid_contract() -> None:
    contract = campaign.build_execution_contract(**_contract_kwargs(101))
    assert campaign.validate_execution_contract(contract) == []
    assert contract["authorization_budget"]["remaining_after_attempt_2"] == 0
    assert contract["provider_profile"]["semantic_contract_changed"] is False


def test_full_mock_attempt_passes_primary_and_independent_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign.register_attempt(tmp_path, **_contract_kwargs(101))
    model_calls = 0

    def fake_post(_url: str, request: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal model_calls
        model_calls += 1
        required = request["response_format"]["json_schema"]["schema"]["required"]
        arm_id = "IA4-D" if "action_ids" in required else "IA4-H"
        return _oracle_model_response(arm_id, request)

    monkeypatch.setattr(base, "_post_json", fake_post)
    primary = campaign.execute_attempt(tmp_path)
    assert model_calls == 48
    assert primary["status"] == "passed"
    assert primary["issues"] == []
    assert campaign.verify_primary_receipt(tmp_path) == []
    audit = independent_v2.build_audit_receipt(tmp_path)
    assert audit["status"] == "passed"
    assert audit["issues"] == []


def test_attempt_1_receipts_remain_reproducible() -> None:
    attempt_1 = ARTIFACT_ROOT / "m29r_complementarity_attempt1"
    assert base.verify_primary_receipt(attempt_1) == []
    assert independent_v1.verify_audit_receipt(attempt_1) == []


def test_v2_independent_auditor_does_not_import_campaign_or_complementarity() -> None:
    tree = ast.parse(Path(independent_v2.__file__).read_text(encoding="utf-8"))
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
    assert not any("m29r_campaign" in name for name in modules)
    assert not any("m29r_complementarity" in name for name in modules)
