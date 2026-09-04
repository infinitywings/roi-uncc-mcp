from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from g7confirm import m29s_campaign as campaign
from g7confirm import m29s_independent_audit as independent
from g7confirm import m29s_semantic_compiler as design


DESIGN_ROOT = design.ROOT / "artifacts/m29s_design_contract_attempt2"
FIXTURE_PATH = design.ROOT / "artifacts/m29s_design_attempt1/design_fixture.json"


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _preflight() -> dict[str, Any]:
    body = {
        "schema_version": "grideval-g7-m29s-service-preflight/v1",
        "classification": design.CLASSIFICATION,
        "llm": {
            "endpoint": campaign.LLM_BASE_URL,
            "probe": "GET /models",
            "id": campaign.MODEL_ID,
            "owned_by": "vllm",
            "root": campaign.MODEL_ROOT,
            "max_model_len": 262144,
            "service_started_or_restarted": False,
            "configuration_changed": False,
        },
        "embedding": {
            "endpoint": campaign.EMBEDDING_BASE_URL,
            "probe": "GET /models plus one /embeddings identity item",
            "id": campaign.EMBEDDING_MODEL,
            "response_model": campaign.EMBEDDING_MODEL,
            "dimensions": 1024,
            "probe_items": 1,
            "service_started_or_restarted": False,
            "configuration_changed": False,
        },
        "access_boundary": campaign._access_boundary(
            llm_accessed=False, embedding_accessed=True
        ),
    }
    return {"service_preflight_id": campaign.content_id("m29spreflight", body), **body}


def _embedding(
    preflight: Mapping[str, Any], packet: Mapping[str, Any]
) -> dict[str, Any]:
    passage_ids = [row["passage_id"] for row in packet["corpus"]["passages"]]
    passage_vectors = []
    for index in range(len(passage_ids)):
        vector = [0.0] * 1024
        vector[index] = 1.0
        passage_vectors.append(vector)
    passage_index = {value: index for index, value in enumerate(passage_ids)}
    retrievals = []
    query_vectors = []
    for index, query in enumerate(packet["query_manifest"]["queries"]):
        query_vector = copy.deepcopy(
            passage_vectors[passage_index[query["expected_passage_id"]]]
        )
        query_vectors.append(query_vector)
        ids = [
            query["expected_passage_id"],
            *sorted(value for value in passage_ids if value != query["expected_passage_id"])[:3],
        ]
        retrievals.append(
            {
                "query_id": query["query_id"],
                "condition_id": query["condition_id"],
                "retrieval_required": query["retrieval_required"],
                "expected_passage_id": query["expected_passage_id"],
                "expected_passage_rank": 1,
                "top_k": [
                    {
                        "passage_id": value,
                        "cosine_similarity": 1.0 if offset == 0 else 0.0,
                    }
                    for offset, value in enumerate(ids)
                ],
            }
        )
    body = {
        "schema_version": "grideval-g7-m29s-embedding-receipt/v1",
        "classification": design.CLASSIFICATION,
        "service_preflight_id": preflight["service_preflight_id"],
        "split_packet_id": packet["split_packet_id"],
        "split": packet["split"],
        "model": campaign.EMBEDDING_MODEL,
        "dimensions": 1024,
        "corpus_id": packet["corpus"]["corpus_id"],
        "query_manifest_id": packet["query_manifest"]["query_manifest_id"],
        "passage_ids": passage_ids,
        "query_ids": [row["query_id"] for row in packet["query_manifest"]["queries"]],
        "passage_vectors": passage_vectors,
        "query_vectors": query_vectors,
        "retrievals": retrievals,
        "accounting": {
            "embedding_http_calls": 2,
            "embedding_corpus_items": len(packet["corpus"]["passages"]),
            "embedding_query_items": len(packet["query_manifest"]["queries"]),
            "embedding_prompt_tokens": 0,
            "wall_time_ms": 0.0,
        },
        "access_boundary": campaign._access_boundary(
            llm_accessed=False, embedding_accessed=True
        ),
    }
    return {"embedding_receipt_id": campaign.content_id("m29sembed", body), **body}


def _prepare_contract_inputs(tmp_path: Path) -> tuple[dict[str, Path], dict[str, dict[str, Any]]]:
    split_root = tmp_path / "splits"
    campaign.prepare_split_packets(fixture_path=FIXTURE_PATH, output_root=split_root)
    preflight = _preflight()
    preflight_path = tmp_path / "preflight.json"
    _write(preflight_path, preflight)
    packets = {
        split: json.loads((split_root / f"{split}.json").read_text(encoding="utf-8"))
        for split in design.SPLITS
    }
    embedding_paths: dict[str, Path] = {}
    for split, packet in packets.items():
        path = tmp_path / f"{split}_embedding.json"
        _write(path, _embedding(preflight, packet))
        embedding_paths[split] = path
    return {
        "design_contract_path": DESIGN_ROOT / "contract.json",
        "plan_audit_path": DESIGN_ROOT / "plan_audit_receipt.json",
        "split_commitment_path": split_root / "commitment.json",
        "preflight_path": preflight_path,
        "development_embedding_path": embedding_paths["development"],
        "held_out_embedding_path": embedding_paths["held_out"],
        "authorization_note_id": "jrn_test_1000_call_authorization",
    }, packets


def _response_payload(
    request: Mapping[str, Any], rows: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    visible = json.loads(request["messages"][1]["content"])
    condition_id = visible["visible_evidence"]["condition_id"]
    row = rows[condition_id]
    bundle = visible["visible_evidence"]
    passages = visible["corpus_passages"]
    condition = campaign._condition_object(row)
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
    if staged:
        return {
            "evidence_ledger": design.build_oracle_ledger(bundle, passages),
            "semantic_slots": slots,
            "strategy_program": program,
        }
    return program


def _mock_response(content: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": "mock-m29s-response",
        "model": campaign.MODEL_ID,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(content, sort_keys=True, separators=(",", ":"))
                },
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
    }


def test_split_packets_are_physically_disjoint(tmp_path: Path) -> None:
    commitment = campaign.prepare_split_packets(
        fixture_path=FIXTURE_PATH, output_root=tmp_path
    )
    development = (tmp_path / "development.json").read_text(encoding="utf-8")
    held_out = (tmp_path / "held_out.json").read_text(encoding="utf-8")
    assert "m29s_held_out" not in development
    assert "m29s_development" not in held_out
    assert commitment["access_protocol"]["held_out_requires_development_freeze"] is True


def test_feedback_matched_initial_requests_are_identical(tmp_path: Path) -> None:
    _, packets = _prepare_contract_inputs(tmp_path)
    packet = packets["development"]
    row = packet["conditions"][0]
    condition = campaign._condition_object(row)
    fake_embedding = _embedding(_preflight(), packet)
    passages = campaign.corpus_view(
        "IA4-FS", row["condition_id"], packet, fake_embedding
    )
    requests = [
        campaign.build_initial_request(
            arm_id=arm,
            condition=condition,
            bundle=row["visible_evidence"],
            passages=passages,
        )
        for arm in ("IA4-C1", "IA4-FS", "IA4-FV")
    ]
    assert len({campaign.canonical_json(value) for value in requests}) == 1
    schema_text = campaign.canonical_json(
        requests[0]["response_format"]["json_schema"]["schema"]
    )
    assert '"$ref"' not in schema_text
    assert "uniqueItems" not in schema_text


def test_validator_revision_contains_only_allowlisted_diagnostics(tmp_path: Path) -> None:
    _, packets = _prepare_contract_inputs(tmp_path)
    row = packets["development"]["conditions"][0]
    condition = campaign._condition_object(row)
    fake_embedding = _embedding(_preflight(), packets["development"])
    passages = campaign.corpus_view(
        "IA4-FV", row["condition_id"], packets["development"], fake_embedding
    )
    initial = campaign.build_initial_request(
        arm_id="IA4-FV",
        condition=condition,
        bundle=row["visible_evidence"],
        passages=passages,
    )
    diagnostics = design.validate_strategy_draft(
        condition, {}, row["visible_evidence"], passages
    )
    revised = campaign.build_revision_request(
        initial_request=initial,
        initial_content="{}",
        feedback="validator_guided_revision",
        diagnostics=diagnostics,
        condition_id=row["condition_id"],
        interface="flat",
        retrieval=False,
    )
    assert revised["messages"][-1]["content"].endswith(
        campaign.canonical_json(diagnostics)
    )
    assert set(diagnostics) == {
        "schema_version", "draft_id", "visible_input_digest", "diagnostics"
    }


def test_held_out_fails_closed_without_development_freeze(tmp_path: Path) -> None:
    kwargs, _ = _prepare_contract_inputs(tmp_path)
    attempt = tmp_path / "attempt"
    campaign.register_attempt(attempt, **kwargs)
    with pytest.raises(campaign.M29SCampaignError, match="development freeze"):
        campaign.execute_split(attempt, "held_out")


def test_full_mock_campaign_passes_integrity_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kwargs, packets = _prepare_contract_inputs(tmp_path)
    attempt = tmp_path / "attempt"
    contract = campaign.register_attempt(attempt, **kwargs)
    assert campaign.validate_execution_contract(contract) == []
    rows = {
        row["condition_id"]: row
        for packet in packets.values()
        for row in packet["conditions"]
    }
    calls = 0

    def fake_post(_url: str, request: Mapping[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return _mock_response(_response_payload(request, rows))

    monkeypatch.setattr(campaign, "_post_json", fake_post)
    development = campaign.execute_split(attempt, "development")
    assert development["model_calls"] == 288
    freeze = campaign.build_development_freeze(attempt)
    campaign.create_once_json(attempt / "development_freeze.json", freeze)
    held_out = campaign.execute_split(attempt, "held_out")
    assert held_out["model_calls"] == 288
    assert calls == 576
    audit = independent.build_audit_receipt(attempt)
    assert audit["status"] == "passed", audit["issues"]
    assert audit["issues"] == []
    campaign.create_once_json(attempt / "independent_audit_receipt.json", audit)
    primary = campaign.build_primary_receipt(attempt, independent_clean=True)
    campaign.create_once_json(attempt / "primary_receipt.json", primary)
    assert primary["status"] == "passed"
    assert campaign.verify_primary_receipt(attempt) == []
    assert independent.verify_audit_receipt(attempt) == []


def test_independent_auditor_does_not_import_primary_modules() -> None:
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
