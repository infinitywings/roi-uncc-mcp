"""Focused tests for the bounded M29-R campaign runner."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from g7confirm import m29r_campaign as campaign
from g7confirm import m29r_independent_audit as independent
from g7confirm.m29r_complementarity import (
    build_evidence_bundle,
    build_oracle_program,
    default_scenarios,
    program_semantics,
    run_independent_oracle,
)


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _embedding_receipt() -> dict[str, Any]:
    manifest = json.loads(campaign.QUERY_PATH.read_text(encoding="utf-8"))
    return {
        "embedding_receipt_id": "m29rembed_" + "0" * 64,
        "retrievals": [
            {
                "query_id": row["query_id"],
                "condition_id": row["condition_id"],
                "retrieval_required": row["retrieval_required"],
                "expected_passage_id": row["expected_passage_id"],
                "expected_passage_rank": 1 if row["expected_passage_id"] else None,
                "top_k": [
                    {"passage_id": passage_id, "cosine_similarity": 1.0 - index / 10.0}
                    for index, passage_id in enumerate(row["flat_excerpt_passage_ids"])
                ],
            }
            for row in manifest["queries"]
        ],
    }


def _oracle_model_response(arm_id: str, model_request: dict[str, Any]) -> dict[str, Any]:
    user = json.loads(model_request["messages"][1]["content"])
    condition_id = user["evidence_bundle"]["condition_id"]
    scenario = next(row for row in default_scenarios() if row.condition_id == condition_id)
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
        content["action_ids"] = [row["action_id"] for row in oracle["plan"]["steps"]]
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return {
        "id": "mock-response",
        "model": campaign.MODEL_ID,
        "choices": [{"finish_reason": "stop", "message": {"content": encoded}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
    }


def test_service_preflight_binds_existing_services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = {
        "backend": "openai_compat",
        "config": {"base_url": "http://172.20.0.1:11434", "model": "qwen3-embedding:0.6b", "dim": 1024},
        "updated_at": "2026-08-30T17:43:59Z",
        "updated_by": "pi",
    }
    test = {"ok": True, "detected_dim": 1024, "latency_ms": 100.0}
    probe = {
        "model": "qwen3-embedding:0.6b",
        "data": [{"index": 0, "embedding": [0.0] * 1024}],
        "usage": {"prompt_tokens": 8, "total_tokens": 8},
    }
    paths = [tmp_path / name for name in ("config.json", "test.json", "probe.json")]
    for path, payload in zip(paths, (config, test, probe)):
        _write(path, payload)
    monkeypatch.setattr(campaign, "_get_json", lambda *_args, **_kwargs: {"data": [{"id": campaign.MODEL_ID, "owned_by": "vllm", "root": "QuantTrio/Qwen3.6-35B-A3B-AWQ", "max_model_len": 262144}]})
    record = campaign.build_service_preflight(
        embedding_config_path=paths[0], embedding_test_path=paths[1], embedding_probe_path=paths[2]
    )
    assert record["service_preflight_id"].startswith("m29rpreflight_")
    assert record["embedding"]["model"] == "qwen3-embedding:0.6b"
    assert record["embedding"]["service_started_or_restarted"] is False


def test_model_request_is_strict_and_bounded() -> None:
    scenario = default_scenarios()[0]
    bundle = build_evidence_bundle(scenario)
    request = campaign.build_model_request("IA4-D", bundle, _embedding_receipt())
    assert request["model"] == campaign.MODEL_ID
    assert request["max_tokens"] == 640
    assert request["temperature"] == 0
    schema = request["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["strategy_program", "action_ids"]


@pytest.mark.parametrize("arm_id", ["IA4-D", "IA4-H", "IA4-HR"])
def test_live_cell_accepts_oracle_shaped_response(
    arm_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = default_scenarios()[0]

    def fake_post(_url: str, request: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        return _oracle_model_response(arm_id, request)

    monkeypatch.setattr(campaign, "_post_json", fake_post)
    cell = campaign.run_live_cell(arm_id, scenario, "m29rexec_" + "1" * 64, _embedding_receipt())
    assert cell["status"] == "completed"
    assert cell["endpoints"]["compiler_correct"] is True
    assert cell["endpoints"]["conjunctive_success"] is True
    assert cell["accounting"]["model_calls"] == 1
    assert cell["accounting"]["optimizer_calls"] == int(arm_id != "IA4-D")


def test_live_length_failure_is_retained_and_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_post(_url: str, _request: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "id": "mock-length",
            "model": campaign.MODEL_ID,
            "choices": [{"finish_reason": "length", "message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 640, "total_tokens": 740},
        }

    monkeypatch.setattr(campaign, "_post_json", fake_post)
    cell = campaign.run_live_cell("IA4-H", default_scenarios()[0], "m29rexec_" + "1" * 64, _embedding_receipt())
    assert calls == 1
    assert cell["status"] == "failed_closed"
    assert cell["plan"] is None
    assert "finish reason: length" in cell["failure_class"]


def test_deterministic_ladder_has_expected_capabilities() -> None:
    receipt = _embedding_receipt()
    direct_scenario = default_scenarios()[0]
    held_out_scenario = default_scenarios()[2]
    optimizer = campaign.run_deterministic_cell("IA3-O", direct_scenario, "m29rexec_" + "1" * 64, receipt)
    symbolic = campaign.run_deterministic_cell("IA3-SO", direct_scenario, "m29rexec_" + "1" * 64, receipt)
    held_out = campaign.run_deterministic_cell("IA3-SO", held_out_scenario, "m29rexec_" + "1" * 64, receipt)
    oracle = campaign.run_deterministic_cell("IA5-OC", direct_scenario, "m29rexec_" + "1" * 64, receipt)
    assert optimizer["accounting"]["optimizer_calls"] == 1
    assert optimizer["endpoints"]["compiler_correct"] is False
    assert symbolic["endpoints"]["conjunctive_success"] is True
    assert held_out["failure_class"] == "semantic_compiler_unavailable"
    assert oracle["endpoints"]["conjunctive_success"] is True


def test_scientific_summary_counts_witness_cells() -> None:
    condition_ids = [row.condition_id for row in default_scenarios()]
    cells = []
    for arm in campaign.ARM_IDS:
        for index, condition_id in enumerate(condition_ids):
            success = arm in {"IA4-H", "IA5-OC"}
            if arm == "IA4-D":
                success = index >= 8
            cells.append(
                {
                    "arm_id": arm,
                    "condition_id": condition_id,
                    "plan": {} if success else None,
                    "endpoints": {"conjunctive_success": success, "plan_valid_under_oracle": success},
                }
            )
    summary = campaign._scientific_summary(cells)
    assert summary["successes"]["IA4-H"] == 16
    assert summary["ia4_h_minus_ia4_d"] == 8
    assert summary["witness_cell_count"] == 8


def test_campaign_and_independent_auditor_source_separation() -> None:
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
    assert not any("m29r_campaign" in name for name in modules)
    assert not any("m29r_complementarity" in name for name in modules)


def test_expected_cell_paths_are_complete_and_unique() -> None:
    paths = campaign.expected_cell_paths()
    assert len(paths) == 96
    assert len(set(paths)) == 96
    assert all(path.startswith("cells/") and path.endswith(".json") for path in paths)


def test_full_mock_campaign_passes_primary_and_independent_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = campaign.ROOT / "artifacts"
    contract = campaign.register_attempt(
        tmp_path,
        preflight_path=artifact_root / "m29r_service_preflight/service_preflight.json",
        embedding_receipt_path=artifact_root / "m29r_service_preflight/embedding_receipt.json",
        design_contract_path=artifact_root / "m29r_design_contract/contract.json",
        plan_audit_path=artifact_root / "m29r_design_contract/plan_audit_receipt.json",
    )
    assert campaign.validate_execution_contract(contract) == []

    model_calls = 0

    def fake_post(_url: str, request: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal model_calls
        model_calls += 1
        required = request["response_format"]["json_schema"]["schema"]["required"]
        arm_id = "IA4-D" if "action_ids" in required else "IA4-H"
        return _oracle_model_response(arm_id, request)

    monkeypatch.setattr(campaign, "_post_json", fake_post)
    primary = campaign.execute_attempt(tmp_path)
    assert model_calls == 48
    assert primary["status"] == "passed"
    assert primary["issues"] == []
    assert primary["cell_count"] == 96
    assert campaign.verify_primary_receipt(tmp_path) == []

    audit = independent.build_audit_receipt(tmp_path)
    assert audit["status"] == "passed"
    assert audit["issues"] == []
