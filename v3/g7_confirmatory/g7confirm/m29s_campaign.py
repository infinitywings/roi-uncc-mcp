"""Create-once runner for the M29-S task-interface factorial study.

The runner is deliberately offline with respect to the grid.  Its only
network clients are the registered read-only language-model and embedding
endpoints.  Development and held-out payloads are stored in separate,
content-addressed packets, and held-out execution requires an immutable
development-freeze receipt.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import time
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import m29s_semantic_compiler as design


ROOT = Path(__file__).resolve().parents[1]
LLM_BASE_URL = "http://ccil1s26m8hj6lws:8000/v1"
EMBEDDING_BASE_URL = "http://172.20.0.1:11434/v1"
MODEL_ID = "qwen3.6-35b-a3b"
MODEL_ROOT = "QuantTrio/Qwen3.6-35B-A3B-AWQ"
EMBEDDING_MODEL = "qwen3-embedding:0.6b"
EMBEDDING_DIMENSIONS = 1024
PLAN_GATE_ID = "chk_01M1PNY0YBT8K26DEW6CK0E838"
DESIGN_CONTRACT_ID = (
    "m29scontract_2718c430056e1314ec36f107feb2ca1ec160e2d430b0bc94bb4d527ecc922fe0"
)
PLAN_AUDIT_ID = (
    "m29splanaudit_df21393fa47ffe702a9b03443939cdb6f2b6c8d88c868e9abd7bfafa9fb04de7"
)

ARM_IDS = design.CONTROL_ARMS + design.REFERENCE_ARMS + design.FACTORIAL_ARMS
LIVE_ARMS = design.REFERENCE_ARMS + design.FACTORIAL_ARMS
CALLS_PER_SPLIT = 288
MAXIMUM_ADDITIONAL_CALLS = 576
PRIOR_MODEL_CALLS = 101
AUTHORIZED_CUMULATIVE_CALLS = 1000

BOUND_SOURCE_PATHS = (
    "M29S_EXECUTOR_BACKBRIEF.md",
    "M29S_INDEPENDENT_AUDIT_PLAN.md",
    "M29S_EXECUTION_PROTOCOL.md",
    "m29s_factorial_plan.json",
    "m29s_evidence_ledger.schema.json",
    "m29s_semantic_slots.schema.json",
    "m29s_strategy_program.schema.json",
    "g7confirm/m29s_semantic_compiler.py",
    "g7confirm/m29s_design_contract.py",
    "g7confirm/m29s_plan_audit.py",
    "g7confirm/m29s_campaign.py",
    "g7confirm/m29s_independent_audit.py",
    "tests/test_m29s_semantic_compiler.py",
    "tests/test_m29s_plan_audit.py",
    "tests/test_m29s_campaign.py",
)


class M29SCampaignError(RuntimeError):
    """Raised when a frozen M29-S campaign invariant is violated."""


def canonical_json(value: Any) -> str:
    return design.canonical_json(value)


def content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return design.content_id(prefix, payload)


def sha256_file(path: Path) -> str:
    return design.sha256_file(path)


def strict_json(path: Path, label: str) -> Any:
    return design.strict_json_file(path, label)


def create_once_json(path: Path, payload: Any) -> None:
    design.create_once_json(path, payload)


def _stored_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _resolve_stored_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _get_json(url: str, timeout: float = 30.0) -> Any:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(
    url: str, payload: Mapping[str, Any], timeout: float = 240.0
) -> Any:
    request = urllib.request.Request(
        url,
        data=canonical_json(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _validate_content_address(
    payload: Mapping[str, Any], field: str, prefix: str, label: str
) -> None:
    body = dict(payload)
    identifier = body.pop(field, None)
    if identifier != content_id(prefix, body):
        raise M29SCampaignError(f"{label} content address drift")


def build_split_packet(
    fixture: Mapping[str, Any], split: str
) -> dict[str, Any]:
    """Create one self-contained split packet without the other split's bytes."""

    if split not in design.SPLITS:
        raise M29SCampaignError(f"unknown split: {split}")
    rows = [copy.deepcopy(row) for row in fixture["conditions"] if row["split"] == split]
    if len(rows) != 16:
        raise M29SCampaignError(f"split condition count drift: {split}")
    doctrine_codes = {
        row["latent_condition"]["doctrine_code"] for row in rows
    }
    passages = [
        copy.deepcopy(row)
        for row in fixture["corpus"]["passages"]
        if row["doctrine_code"] in doctrine_codes or "DISTRACTOR" in row["passage_id"]
    ]
    queries = [
        copy.deepcopy(row)
        for row in fixture["query_manifest"]["queries"]
        if row["split"] == split
    ]
    body = {
        "schema_version": "grideval-g7-m29s-split-packet/v1",
        "classification": design.CLASSIFICATION,
        "design_fixture_id": fixture["design_fixture_id"],
        "split": split,
        "condition_count": len(rows),
        "conditions": rows,
        "corpus": {
            "schema_version": fixture["corpus"]["schema_version"],
            "classification": fixture["corpus"]["classification"],
            "passages": passages,
        },
        "query_manifest": {
            "schema_version": fixture["query_manifest"]["schema_version"],
            "classification": fixture["query_manifest"]["classification"],
            "top_k": fixture["query_manifest"]["top_k"],
            "similarity": fixture["query_manifest"]["similarity"],
            "tie_break": fixture["query_manifest"]["tie_break"],
            "queries": queries,
        },
        "access_boundary": {
            "contains_other_split": False,
            "contains_final_evaluation": False,
            "contains_rka_governance": False,
            "contains_simulator_or_detector_data": False,
        },
    }
    body["corpus"]["corpus_id"] = content_id(
        "m29ssplitcorpus", body["corpus"]
    )
    body["query_manifest"]["query_manifest_id"] = content_id(
        "m29ssplitqueries", body["query_manifest"]
    )
    return {"split_packet_id": content_id("m29spacket", body), **body}


def prepare_split_packets(
    *, fixture_path: Path, output_root: Path
) -> dict[str, Any]:
    fixture = strict_json(fixture_path, "M29-S design fixture")
    _validate_content_address(fixture, "design_fixture_id", "m29sfixture", "fixture")
    packet_records: dict[str, dict[str, Any]] = {}
    for split in design.SPLITS:
        packet = build_split_packet(fixture, split)
        path = output_root / f"{split}.json"
        create_once_json(path, packet)
        packet_records[split] = {
            "path": _stored_path(path),
            "sha256": sha256_file(path),
            "split_packet_id": packet["split_packet_id"],
            "condition_count": packet["condition_count"],
        }
    body = {
        "schema_version": "grideval-g7-m29s-split-commitment/v1",
        "classification": design.CLASSIFICATION,
        "design_fixture_id": fixture["design_fixture_id"],
        "packets": packet_records,
        "access_protocol": {
            "development_runner_loads_held_out_packet": False,
            "held_out_requires_development_freeze": True,
            "source_or_prompt_adaptation_after_development": False,
            "create_once": True,
        },
        "m29b_authorized": False,
    }
    commitment = {"split_commitment_id": content_id("m29ssplits", body), **body}
    create_once_json(output_root / "commitment.json", commitment)
    return commitment


def _find_model(listing: Mapping[str, Any], model_id: str) -> Mapping[str, Any]:
    rows = listing.get("data", [])
    model = next((row for row in rows if row.get("id") == model_id), None)
    if not isinstance(model, Mapping):
        raise M29SCampaignError(f"registered model unavailable: {model_id}")
    return model


def _embedding_rows(
    response: Mapping[str, Any], expected_count: int
) -> list[list[float]]:
    if response.get("model") != EMBEDDING_MODEL:
        raise M29SCampaignError("embedding response model drift")
    rows = sorted(response.get("data", []), key=lambda row: int(row.get("index", -1)))
    if len(rows) != expected_count:
        raise M29SCampaignError("embedding response cardinality drift")
    vectors: list[list[float]] = []
    for index, row in enumerate(rows):
        if row.get("index") != index:
            raise M29SCampaignError("embedding response index drift")
        vector = row.get("embedding", [])
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise M29SCampaignError("embedding response dimension drift")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in vector
        ):
            raise M29SCampaignError("embedding response contains non-finite values")
        vectors.append([float(value) for value in vector])
    return vectors


def build_service_preflight() -> dict[str, Any]:
    """Probe identities only; never start, stop, or reconfigure either service."""

    llm = _find_model(_get_json(f"{LLM_BASE_URL}/models"), MODEL_ID)
    if llm.get("owned_by") != "vllm" or llm.get("root") != MODEL_ROOT:
        raise M29SCampaignError("LLM identity drift")
    if int(llm.get("max_model_len", -1)) != 262144:
        raise M29SCampaignError("LLM context-length drift")
    embedding_listing = _get_json(f"{EMBEDDING_BASE_URL}/models")
    embedding_identity = _find_model(embedding_listing, EMBEDDING_MODEL)
    probe = _post_json(
        f"{EMBEDDING_BASE_URL}/embeddings",
        {"model": EMBEDDING_MODEL, "input": ["M29-S identity probe"]},
    )
    _embedding_rows(probe, 1)
    body = {
        "schema_version": "grideval-g7-m29s-service-preflight/v1",
        "classification": design.CLASSIFICATION,
        "llm": {
            "endpoint": LLM_BASE_URL,
            "probe": "GET /models",
            "id": llm["id"],
            "owned_by": llm["owned_by"],
            "root": llm["root"],
            "max_model_len": llm["max_model_len"],
            "service_started_or_restarted": False,
            "configuration_changed": False,
        },
        "embedding": {
            "endpoint": EMBEDDING_BASE_URL,
            "probe": "GET /models plus one /embeddings identity item",
            "id": embedding_identity["id"],
            "response_model": probe["model"],
            "dimensions": EMBEDDING_DIMENSIONS,
            "probe_items": 1,
            "service_started_or_restarted": False,
            "configuration_changed": False,
        },
        "access_boundary": _access_boundary(llm_accessed=False, embedding_accessed=True),
    }
    return {"service_preflight_id": content_id("m29spreflight", body), **body}


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise M29SCampaignError("zero-norm embedding")
    return dot / (left_norm * right_norm)


def build_embedding_receipt(
    preflight: Mapping[str, Any], packet: Mapping[str, Any]
) -> dict[str, Any]:
    if preflight.get("embedding", {}).get("id") != EMBEDDING_MODEL:
        raise M29SCampaignError("preflight embedding identity mismatch")
    passages = packet["corpus"]["passages"]
    queries = packet["query_manifest"]["queries"]
    passage_inputs = [f"{row['doctrine_code']} | {row['text']}" for row in passages]
    query_inputs = [row["query"] for row in queries]
    start = time.monotonic()
    passage_response = _post_json(
        f"{EMBEDDING_BASE_URL}/embeddings",
        {"model": EMBEDDING_MODEL, "input": passage_inputs},
    )
    query_response = _post_json(
        f"{EMBEDDING_BASE_URL}/embeddings",
        {"model": EMBEDDING_MODEL, "input": query_inputs},
    )
    passage_vectors = _embedding_rows(passage_response, len(passages))
    query_vectors = _embedding_rows(query_response, len(queries))
    passage_ids = [row["passage_id"] for row in passages]
    retrievals: list[dict[str, Any]] = []
    top_k = int(packet["query_manifest"]["top_k"])
    for query, vector in zip(queries, query_vectors):
        scored = sorted(
            (
                {
                    "passage_id": passage_id,
                    "cosine_similarity": round(_cosine(vector, candidate), 12),
                }
                for passage_id, candidate in zip(passage_ids, passage_vectors)
            ),
            key=lambda row: (-row["cosine_similarity"], row["passage_id"]),
        )
        expected = query["expected_passage_id"]
        expected_rank = next(
            (
                index + 1
                for index, row in enumerate(scored)
                if row["passage_id"] == expected
            ),
            None,
        )
        retrievals.append(
            {
                "query_id": query["query_id"],
                "condition_id": query["condition_id"],
                "retrieval_required": query["retrieval_required"],
                "expected_passage_id": expected,
                "expected_passage_rank": expected_rank,
                "top_k": scored[:top_k],
            }
        )
    body = {
        "schema_version": "grideval-g7-m29s-embedding-receipt/v1",
        "classification": design.CLASSIFICATION,
        "service_preflight_id": preflight["service_preflight_id"],
        "split_packet_id": packet["split_packet_id"],
        "split": packet["split"],
        "model": EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "corpus_id": packet["corpus"]["corpus_id"],
        "query_manifest_id": packet["query_manifest"]["query_manifest_id"],
        "passage_ids": passage_ids,
        "query_ids": [row["query_id"] for row in queries],
        "passage_vectors": passage_vectors,
        "query_vectors": query_vectors,
        "retrievals": retrievals,
        "accounting": {
            "embedding_http_calls": 2,
            "embedding_corpus_items": len(passages),
            "embedding_query_items": len(queries),
            "embedding_prompt_tokens": int(passage_response.get("usage", {}).get("prompt_tokens", 0))
            + int(query_response.get("usage", {}).get("prompt_tokens", 0)),
            "wall_time_ms": round((time.monotonic() - start) * 1000.0, 3),
        },
        "access_boundary": _access_boundary(llm_accessed=False, embedding_accessed=True),
    }
    return {"embedding_receipt_id": content_id("m29sembed", body), **body}


def _packet_condition(packet: Mapping[str, Any], condition_id: str) -> Mapping[str, Any]:
    row = next(
        (row for row in packet["conditions"] if row["condition_id"] == condition_id),
        None,
    )
    if row is None:
        raise M29SCampaignError(f"condition absent from split packet: {condition_id}")
    return row


def _condition_object(row: Mapping[str, Any]) -> design.LatentCondition:
    latent = row["latent_condition"]
    values = latent["semantic_program"]
    return design.LatentCondition(
        split=row["split"],
        pair_id=row["pair_id"].removeprefix(f"m29s_{row['split']}_pair_"),
        construct=row["construct"],
        side=row["side"],
        seed=int(latent["seed"]),
        rendering=latent["rendering"],
        retrieval_required=bool(latent["retrieval_required"]),
        doctrine_code=latent["doctrine_code"],
        strategy_id=values["strategy_id"],
        effect_direction=values["effect_direction"],
        allowed_targets=tuple(values["allowed_targets"]),
        forbidden_windows=tuple(values["forbidden_windows"]),
        objective_weights=tuple(sorted(values["objective_weights"].items())),
        max_total_energy=int(values["max_total_energy"]),
        max_total_visibility=int(values["max_total_visibility"]),
        min_actions=int(values["min_actions"]),
        max_actions=int(values["max_actions"]),
        max_level_delta=int(values["max_level_delta"]),
        cooldown_same_target=bool(values["cooldown_same_target"]),
    )


def corpus_view(
    arm_id: str,
    condition_id: str,
    packet: Mapping[str, Any],
    embedding: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_id = {row["passage_id"]: row for row in packet["corpus"]["passages"]}
    spec = design.arm_spec(arm_id)
    if spec["retrieval"]:
        row = next(
            row for row in embedding["retrievals"] if row["condition_id"] == condition_id
        )
        ids = [hit["passage_id"] for hit in row["top_k"]]
    else:
        query = next(
            row
            for row in packet["query_manifest"]["queries"]
            if row["condition_id"] == condition_id
        )
        ids = list(query["flat_passage_ids"])
    return [copy.deepcopy(by_id[value]) for value in ids]


def _inline_local_refs(value: Any, inherited_defs: Mapping[str, Any] | None = None) -> Any:
    """Inline nested local definitions before sending schemas to the provider."""

    if isinstance(value, list):
        return [_inline_local_refs(row, inherited_defs) for row in value]
    if not isinstance(value, Mapping):
        return copy.deepcopy(value)
    local_defs = value.get("$defs", inherited_defs or {})
    reference = value.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/$defs/"):
        name = reference.rsplit("/", 1)[-1]
        if name not in local_defs:
            raise M29SCampaignError(f"unresolved provider schema reference: {reference}")
        merged = copy.deepcopy(local_defs[name])
        merged.update({key: row for key, row in value.items() if key != "$ref"})
        return _inline_local_refs(merged, local_defs)
    return {
        key: _inline_local_refs(row, local_defs)
        for key, row in value.items()
        if key != "$defs"
    }


def _request_seed(
    *, interface: str, retrieval: bool, condition_id: str, stage: str
) -> int:
    material = f"m29s:{interface}:{int(retrieval)}:{condition_id}:{stage}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _compiler_id(interface: str, retrieval: bool) -> str:
    return f"qwen_m29s_{interface}_{'retrieval' if retrieval else 'fixed'}_v1"


def build_initial_request(
    *,
    arm_id: str,
    condition: design.LatentCondition,
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a feedback-matched first request for one factorial cell."""

    spec = design.arm_spec(arm_id)
    if arm_id not in LIVE_ARMS:
        raise M29SCampaignError("model request built for a deterministic arm")
    interface = str(spec["interface"])
    retrieval = bool(spec["retrieval"])
    digest = design.visible_input_digest(bundle, passages)
    compiler_id = _compiler_id(interface, retrieval)
    schema = design.response_schema(
        interface=interface,
        condition_id=condition.condition_id,
        input_digest=digest,
        compiler_id=compiler_id,
    )
    schema = _inline_local_refs(schema)
    interface_instruction = (
        "Return only the final StrategyProgram JSON."
        if interface == "flat"
        else "Return EvidenceLedger, SemanticSlots with per-slot supporting evidence IDs, and a StrategyProgram that exactly projects those submitted slot values."
    )
    return {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You compile visible grid red-team evidence into a typed offline strategy program. "
                    "Use only supplied records and corpus passages. Resolve status, authority, validity, scope, budgets, and evidence lineage exactly. "
                    + interface_instruction
                ),
            },
            {
                "role": "user",
                "content": canonical_json(design.visible_input(bundle, passages)),
            },
        ],
        "temperature": 0,
        "seed": _request_seed(
            interface=interface,
            retrieval=retrieval,
            condition_id=condition.condition_id,
            stage="initial",
        ),
        "max_tokens": 900,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": False,
        "n": 1,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": f"m29s_{interface}_response",
                "strict": True,
                "schema": schema,
            },
        },
    }


def build_revision_request(
    *,
    initial_request: Mapping[str, Any],
    initial_content: str,
    feedback: str,
    diagnostics: Mapping[str, Any] | None,
    condition_id: str,
    interface: str,
    retrieval: bool,
) -> dict[str, Any]:
    if feedback not in {"neutral_self_revision", "validator_guided_revision"}:
        raise M29SCampaignError(f"invalid revision policy: {feedback}")
    if feedback == "neutral_self_revision":
        if diagnostics is not None:
            raise M29SCampaignError("neutral revision received diagnostics")
        message = design.neutral_self_revision_message()
    else:
        if diagnostics is None:
            raise M29SCampaignError("validator revision missing diagnostics")
        design.validate_diagnostics(diagnostics)
        message = (
            "A visible-only validator returned the following code-slot diagnostics. "
            "Revise once using only the original visible input and return the same registered schema: "
            + canonical_json(diagnostics)
        )
    request = copy.deepcopy(dict(initial_request))
    request["messages"] = [
        *copy.deepcopy(initial_request["messages"]),
        {"role": "assistant", "content": initial_content},
        {"role": "user", "content": message},
    ]
    request["seed"] = _request_seed(
        interface=interface,
        retrieval=retrieval,
        condition_id=condition_id,
        stage="final",
    )
    return request


def _strict_model_content(content: str) -> dict[str, Any]:
    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M29SCampaignError(f"duplicate model JSON key: {key}")
            result[key] = value
        return result

    payload = json.loads(
        content,
        object_pairs_hook=reject_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(M29SCampaignError(value)),
    )
    if not isinstance(payload, dict):
        raise M29SCampaignError("model response is not an object")
    return payload


def _response_record(response: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    choices = response.get("choices", [])
    if len(choices) != 1:
        raise M29SCampaignError("model response choice cardinality drift")
    choice = choices[0]
    message = choice.get("message", {})
    content = message.get("content")
    usage = response.get("usage", {})
    record = {
        "id": response.get("id"),
        "model": response.get("model"),
        "finish_reason": choice.get("finish_reason"),
        "content": content,
        "refusal": message.get("refusal"),
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "total_tokens": int(
                usage.get(
                    "total_tokens",
                    int(usage.get("prompt_tokens", 0))
                    + int(usage.get("completion_tokens", 0)),
                )
            ),
        },
    }
    if choice.get("finish_reason") != "stop":
        raise M29SCampaignError(f"model finish reason: {choice.get('finish_reason')}")
    if not isinstance(content, str):
        raise M29SCampaignError("model response content is absent")
    return record, content


def _interpret_draft(
    *,
    payload: Mapping[str, Any],
    interface: str,
    compiler_id: str,
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if interface == "flat":
        design.validate_strategy_program(payload, bundle, passages)
        return {
            "evidence_ledger": None,
            "semantic_slots": None,
            "strategy_program": copy.deepcopy(dict(payload)),
        }
    if set(payload) != {"evidence_ledger", "semantic_slots", "strategy_program"}:
        raise M29SCampaignError("staged response keys drift")
    ledger = payload["evidence_ledger"]
    slots = payload["semantic_slots"]
    program = payload["strategy_program"]
    design.validate_evidence_ledger(ledger, bundle, passages)
    design.validate_semantic_slots(slots, bundle, passages)
    design.validate_strategy_program(program, bundle, passages)
    projected = design.project_slots_to_program(slots, compiler_id=compiler_id)
    if canonical_json(program) != canonical_json(projected):
        raise M29SCampaignError("staged program is not the deterministic slot projection")
    return copy.deepcopy(dict(payload))


def _score_draft(
    *,
    draft: Mapping[str, Any] | None,
    interface: str,
    condition: design.LatentCondition,
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
    oracle: Mapping[str, Any],
) -> dict[str, Any]:
    program = draft.get("strategy_program") if draft else None
    oracle_program = oracle["strategy_program"]
    slot_results = design.slot_accuracy(program, oracle_program)
    program_exact = bool(program is not None and all(slot_results.values()))
    expected_slots = design.build_oracle_slots(condition, bundle, passages)
    expected_program = design.project_slots_to_program(
        expected_slots, compiler_id=program.get("compiler_id", "score") if program else "score"
    )
    lineage_exact = bool(
        program is not None
        and sorted(program.get("required_evidence_ids", []))
        == sorted(expected_program["required_evidence_ids"])
    )
    ledger_exact: bool | None = None
    slot_lineage_exact: bool | None = None
    if interface == "staged":
        ledger_exact = bool(
            draft
            and canonical_json(draft.get("evidence_ledger"))
            == canonical_json(design.build_oracle_ledger(bundle, passages))
        )
        slot_lineage_exact = bool(
            draft
            and all(
                sorted(
                    draft.get("semantic_slots", {})
                    .get("slots", {})
                    .get(key, {})
                    .get("supporting_evidence_ids", [])
                )
                == sorted(expected_slots["slots"][key]["supporting_evidence_ids"])
                for key in design.SLOT_KEYS
            )
        )
        lineage_exact = bool(lineage_exact and slot_lineage_exact)
    success = bool(
        program_exact
        and lineage_exact
        and (interface != "staged" or ledger_exact is True)
    )
    return {
        "per_slot_exact": slot_results,
        "correct_slot_count": sum(slot_results.values()),
        "program_semantics_exact": program_exact,
        "evidence_lineage_exact": lineage_exact,
        "evidence_ledger_exact": ledger_exact,
        "semantic_slot_lineage_exact": slot_lineage_exact,
        "all_slot_program_exact": success,
    }


def _access_boundary(*, llm_accessed: bool, embedding_accessed: bool) -> dict[str, Any]:
    return {
        "llm_accessed": llm_accessed,
        "existing_embedding_accessed": embedding_accessed,
        "model_or_embedding_service_started_or_restarted": False,
        "embedding_configuration_changed": False,
        "docker_accessed": False,
        "helics_accessed": False,
        "opender_accessed": False,
        "gridlabd_accessed": False,
        "simulator_accessed": False,
        "detector_accessed": False,
        "defense_accessed": False,
        "network_impairment_accessed": False,
        "physical_actuator_accessed": False,
        "final_evaluation_accessed": False,
        "final_evaluation_seeds_accessed": [],
        "rka_governance_attacker_view_accessed": False,
    }


def _finish_cell(body: Mapping[str, Any]) -> dict[str, Any]:
    return {"cell_id": content_id("m29scell", body), **copy.deepcopy(dict(body))}


def run_control_cell(
    *,
    arm_id: str,
    row: Mapping[str, Any],
    packet: Mapping[str, Any],
    embedding: Mapping[str, Any],
    execution_contract_id: str,
) -> dict[str, Any]:
    if arm_id not in design.CONTROL_ARMS:
        raise M29SCampaignError("invalid control arm")
    condition = _condition_object(row)
    bundle = row["visible_evidence"]
    if arm_id == "IA5-OC" and condition.retrieval_required:
        by_id = {
            value["passage_id"]: value for value in packet["corpus"]["passages"]
        }
        passages = [
            copy.deepcopy(by_id[value])
            for value in row["oracle_retrieval_passage_ids"]
        ]
    else:
        passages = corpus_view(arm_id, row["condition_id"], packet, embedding)
    if arm_id == "IA3-SX":
        draft = design.strong_deterministic_compile(condition, bundle, passages)
        failure_class = None if draft else "visible_compiler_abstained"
    else:
        draft = copy.deepcopy(row["independent_oracle"])
        draft.pop("tested_model_called", None)
        draft.pop("validator_called", None)
        failure_class = None
    scores = _score_draft(
        draft=draft,
        interface="staged",
        condition=condition,
        bundle=bundle,
        passages=passages,
        oracle=row["independent_oracle"],
    )
    body = {
        "schema_version": "grideval-g7-m29s-cell/v1",
        "classification": design.CLASSIFICATION,
        "execution_contract_id": execution_contract_id,
        "split": row["split"],
        "arm_id": arm_id,
        "condition_id": row["condition_id"],
        "pair_id": row["pair_id"],
        "construct": row["construct"],
        "status": "completed",
        "failure_class": failure_class,
        "visible_evidence_id": bundle["visible_evidence_id"],
        "corpus_view_passage_ids": [value["passage_id"] for value in passages],
        "initial_request": None,
        "initial_response": None,
        "initial_draft": draft,
        "validator_diagnostics": None,
        "revision_request": None,
        "revision_response": None,
        "final_draft": draft,
        "initial_scores": scores,
        "final_scores": scores,
        "endpoints": {
            **scores,
            "initial_all_slot_program_exact": scores["all_slot_program_exact"],
            "repair_conversion": False,
            "repair_regression": False,
            "final_contract_violation": False,
            "retrieval_required": bool(condition.retrieval_required),
        },
        "accounting": {
            "model_calls": 0,
            "model_prompt_tokens": 0,
            "model_completion_tokens": 0,
            "invalid_outputs": 0,
            "refusals": int(draft is None),
            "wall_time_ms": 0.0,
        },
        "access_boundary": _access_boundary(
            llm_accessed=False, embedding_accessed=False
        ),
    }
    return _finish_cell(body)


def run_live_cell(
    *,
    arm_id: str,
    row: Mapping[str, Any],
    packet: Mapping[str, Any],
    embedding: Mapping[str, Any],
    execution_contract_id: str,
) -> dict[str, Any]:
    if arm_id not in LIVE_ARMS:
        raise M29SCampaignError("invalid live arm")
    spec = design.arm_spec(arm_id)
    expected_calls = int(spec["model_calls_per_cell"])
    condition = _condition_object(row)
    bundle = row["visible_evidence"]
    passages = corpus_view(arm_id, row["condition_id"], packet, embedding)
    interface = str(spec["interface"])
    feedback = str(spec["feedback"])
    compiler_id = _compiler_id(interface, bool(spec["retrieval"]))
    initial_request = build_initial_request(
        arm_id=arm_id,
        condition=condition,
        bundle=bundle,
        passages=passages,
    )
    requests: list[dict[str, Any]] = [initial_request]
    responses: list[dict[str, Any] | None] = []
    initial_draft: dict[str, Any] | None = None
    final_draft: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    revision_request: dict[str, Any] | None = None
    failure_messages: list[str] = []
    invalid_outputs = 0
    refusals = 0
    prompt_tokens = 0
    completion_tokens = 0
    start = time.monotonic()

    initial_content = "{}"
    try:
        raw_response = _post_json(
            f"{LLM_BASE_URL}/chat/completions", initial_request
        )
        record, initial_content = _response_record(raw_response)
        responses.append(record)
        prompt_tokens += record["usage"]["prompt_tokens"]
        completion_tokens += record["usage"]["completion_tokens"]
        parsed = _strict_model_content(initial_content)
        initial_draft = _interpret_draft(
            payload=parsed,
            interface=interface,
            compiler_id=compiler_id,
            bundle=bundle,
            passages=passages,
        )
    except Exception as exc:
        if len(responses) == 0:
            responses.append(None)
        invalid_outputs += 1
        failure_messages.append(f"initial:{type(exc).__name__}:{exc}")
        if "refusal" in str(exc).lower():
            refusals += 1

    if expected_calls == 2:
        if feedback == "validator_guided_revision":
            raw_draft: Mapping[str, Any]
            try:
                raw_draft = _strict_model_content(initial_content)
            except Exception:
                raw_draft = {}
            diagnostics = design.validate_strategy_draft(
                condition, raw_draft, bundle, passages
            )
        revision_request = build_revision_request(
            initial_request=initial_request,
            initial_content=initial_content,
            feedback=feedback,
            diagnostics=diagnostics,
            condition_id=condition.condition_id,
            interface=interface,
            retrieval=bool(spec["retrieval"]),
        )
        requests.append(revision_request)
        try:
            raw_response = _post_json(
                f"{LLM_BASE_URL}/chat/completions", revision_request
            )
            record, final_content = _response_record(raw_response)
            responses.append(record)
            prompt_tokens += record["usage"]["prompt_tokens"]
            completion_tokens += record["usage"]["completion_tokens"]
            parsed = _strict_model_content(final_content)
            final_draft = _interpret_draft(
                payload=parsed,
                interface=interface,
                compiler_id=compiler_id,
                bundle=bundle,
                passages=passages,
            )
        except Exception as exc:
            if len(responses) < 2:
                responses.append(None)
            invalid_outputs += 1
            failure_messages.append(f"final:{type(exc).__name__}:{exc}")
            if "refusal" in str(exc).lower():
                refusals += 1
    else:
        final_draft = initial_draft

    initial_scores = _score_draft(
        draft=initial_draft,
        interface=interface,
        condition=condition,
        bundle=bundle,
        passages=passages,
        oracle=row["independent_oracle"],
    )
    final_scores = _score_draft(
        draft=final_draft,
        interface=interface,
        condition=condition,
        bundle=bundle,
        passages=passages,
        oracle=row["independent_oracle"],
    )
    final_violation = final_draft is None
    body = {
        "schema_version": "grideval-g7-m29s-cell/v1",
        "classification": design.CLASSIFICATION,
        "execution_contract_id": execution_contract_id,
        "split": row["split"],
        "arm_id": arm_id,
        "condition_id": row["condition_id"],
        "pair_id": row["pair_id"],
        "construct": row["construct"],
        "status": "completed" if len(responses) == expected_calls else "failed_closed",
        "failure_class": ";".join(failure_messages) if failure_messages else None,
        "visible_evidence_id": bundle["visible_evidence_id"],
        "corpus_view_passage_ids": [value["passage_id"] for value in passages],
        "initial_request": requests[0],
        "initial_response": responses[0],
        "initial_draft": initial_draft,
        "validator_diagnostics": diagnostics,
        "revision_request": revision_request,
        "revision_response": responses[1] if expected_calls == 2 else None,
        "final_draft": final_draft,
        "initial_scores": initial_scores,
        "final_scores": final_scores,
        "endpoints": {
            **final_scores,
            "initial_all_slot_program_exact": initial_scores["all_slot_program_exact"],
            "repair_conversion": bool(
                not initial_scores["all_slot_program_exact"]
                and final_scores["all_slot_program_exact"]
            ),
            "repair_regression": bool(
                initial_scores["all_slot_program_exact"]
                and not final_scores["all_slot_program_exact"]
            ),
            "final_contract_violation": final_violation,
            "retrieval_required": bool(condition.retrieval_required),
        },
        "accounting": {
            "model_calls": len(responses),
            "model_prompt_tokens": prompt_tokens,
            "model_completion_tokens": completion_tokens,
            "invalid_outputs": invalid_outputs,
            "refusals": refusals,
            "wall_time_ms": round((time.monotonic() - start) * 1000.0, 3),
        },
        "access_boundary": _access_boundary(
            llm_accessed=True, embedding_accessed=bool(spec["retrieval"])
        ),
    }
    return _finish_cell(body)


def expected_cell_paths(split: str | None = None) -> tuple[str, ...]:
    splits = (split,) if split else design.SPLITS
    return tuple(
        f"cells/{selected}/{arm_id}/m29s_{selected}_{pair}_{side}.json"
        for selected in splits
        for arm_id in ARM_IDS
        for pair in (
            "doctrine_direction",
            "authority_supersession",
            "validity_expiry",
            "topology_scope",
            "resource_budget",
            "objective_cooldown",
            "delayed_lineage",
            "retrieval_doctrine",
        )
        for side in design.SIDES
    )


def _artifact_ref(path: Path, id_field: str) -> dict[str, Any]:
    payload = strict_json(path, path.name)
    return {
        "path": _stored_path(path),
        "sha256": sha256_file(path),
        "id": payload[id_field],
    }


def build_execution_contract(
    *,
    design_contract_path: Path,
    plan_audit_path: Path,
    split_commitment_path: Path,
    preflight_path: Path,
    development_embedding_path: Path,
    held_out_embedding_path: Path,
    authorization_note_id: str,
) -> dict[str, Any]:
    design_contract = strict_json(design_contract_path, "M29-S design contract")
    plan_audit = strict_json(plan_audit_path, "M29-S plan audit")
    commitment = strict_json(split_commitment_path, "M29-S split commitment")
    preflight = strict_json(preflight_path, "M29-S preflight")
    embeddings = {
        "development": strict_json(development_embedding_path, "development embedding"),
        "held_out": strict_json(held_out_embedding_path, "held-out embedding"),
    }
    if design_contract.get("design_contract_id") != DESIGN_CONTRACT_ID:
        raise M29SCampaignError("unapproved design contract")
    if plan_audit.get("audit_id") != PLAN_AUDIT_ID:
        raise M29SCampaignError("unapproved plan audit")
    if plan_audit.get("status") != "passed" or plan_audit.get("issues") != []:
        raise M29SCampaignError("plan audit did not pass")
    _validate_content_address(commitment, "split_commitment_id", "m29ssplits", "split commitment")
    _validate_content_address(preflight, "service_preflight_id", "m29spreflight", "preflight")
    for split, embedding in embeddings.items():
        _validate_content_address(embedding, "embedding_receipt_id", "m29sembed", f"{split} embedding")
        if embedding.get("split_packet_id") != commitment["packets"][split]["split_packet_id"]:
            raise M29SCampaignError(f"{split} embedding/packet lineage mismatch")
        if embedding.get("service_preflight_id") != preflight["service_preflight_id"]:
            raise M29SCampaignError(f"{split} embedding/preflight lineage mismatch")
    source_hashes = []
    for relative in BOUND_SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        source_hashes.append({"path": relative, "sha256": sha256_file(path)})
    plan = strict_json(design.PLAN_PATH, "M29-S factorial plan")
    schedule = {
        split: [
            {
                "condition_id": row["condition_id"],
                "arm_order": list(ARM_IDS[index % len(ARM_IDS):] + ARM_IDS[:index % len(ARM_IDS)]),
            }
            for index, row in enumerate(
                strict_json(_resolve_stored_path(commitment["packets"][split]["path"]), f"{split} packet")["conditions"]
            )
        ]
        for split in design.SPLITS
    }
    body = {
        "schema_version": "grideval-g7-m29s-execution-contract/v1",
        "classification": design.CLASSIFICATION,
        "project_id": design.PROJECT_ID,
        "mission_id": design.MISSION_ID,
        "decision_id": design.DECISION_ID,
        "plan_gate_id": PLAN_GATE_ID,
        "design_contract": _artifact_ref(design_contract_path, "design_contract_id"),
        "plan_audit": _artifact_ref(plan_audit_path, "audit_id"),
        "split_commitment": _artifact_ref(split_commitment_path, "split_commitment_id"),
        "service_preflight": _artifact_ref(preflight_path, "service_preflight_id"),
        "embedding_receipts": {
            "development": _artifact_ref(development_embedding_path, "embedding_receipt_id"),
            "held_out": _artifact_ref(held_out_embedding_path, "embedding_receipt_id"),
        },
        "source_hashes": source_hashes,
        "arm_ids": list(ARM_IDS),
        "live_arm_ids": list(LIVE_ARMS),
        "expected_cell_paths": list(expected_cell_paths()),
        "execution_schedule": schedule,
        "model_contract": plan["model_contract"],
        "retrieval_contract": plan["retrieval_contract"],
        "held_out_mechanism_gate": plan["held_out_mechanism_gate"],
        "authorization_budget": {
            "pi_authorization_note_id": authorization_note_id,
            "prior_model_calls": PRIOR_MODEL_CALLS,
            "contracted_new_model_calls": MAXIMUM_ADDITIONAL_CALLS,
            "maximum_cumulative_model_calls": PRIOR_MODEL_CALLS + MAXIMUM_ADDITIONAL_CALLS,
            "pi_authorized_cumulative_ceiling": AUTHORIZED_CUMULATIVE_CALLS,
            "remaining_after_attempt": AUTHORIZED_CUMULATIVE_CALLS
            - PRIOR_MODEL_CALLS
            - MAXIMUM_ADDITIONAL_CALLS,
        },
        "attempt_policy": {
            "create_once": True,
            "retry_count": 0,
            "overwrite": False,
            "development_before_held_out": True,
            "held_out_requires_development_freeze": True,
            "adaptation_after_development": False,
        },
        "access_boundary": {
            "offline_llm": True,
            "existing_embedding": True,
            "service_start_restart_or_reconfigure": False,
            "docker": False,
            "simulator": False,
            "detector": False,
            "defense": False,
            "network_impairment": False,
            "physical_actuator": False,
            "final_evaluation": False,
            "evaluation_seeds_9101_9112": False,
            "rka_governance_attacker_view": False,
        },
        "claim_boundary": plan["claim_boundary"],
        "m29b_authorized": False,
    }
    return {"execution_contract_id": content_id("m29sexec", body), **body}


def validate_execution_contract(contract: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    body = dict(contract)
    identifier = body.pop("execution_contract_id", None)
    if identifier != content_id("m29sexec", body):
        issues.append("execution_contract_content_address")
    if contract.get("classification") != design.CLASSIFICATION:
        issues.append("execution_contract_classification")
    if contract.get("plan_gate_id") != PLAN_GATE_ID:
        issues.append("execution_contract_plan_gate")
    if contract.get("arm_ids") != list(ARM_IDS):
        issues.append("execution_contract_arms")
    if contract.get("expected_cell_paths") != list(expected_cell_paths()):
        issues.append("execution_contract_cell_paths")
    if contract.get("attempt_policy") != {
        "create_once": True,
        "retry_count": 0,
        "overwrite": False,
        "development_before_held_out": True,
        "held_out_requires_development_freeze": True,
        "adaptation_after_development": False,
    }:
        issues.append("execution_contract_attempt_policy")
    budget = contract.get("authorization_budget", {})
    if int(budget.get("contracted_new_model_calls", -1)) != MAXIMUM_ADDITIONAL_CALLS:
        issues.append("execution_contract_call_count")
    if int(budget.get("maximum_cumulative_model_calls", -1)) != 677:
        issues.append("execution_contract_cumulative_calls")
    if int(budget.get("pi_authorized_cumulative_ceiling", -1)) != 1000:
        issues.append("execution_contract_authorization")
    if int(budget.get("remaining_after_attempt", -1)) != 323:
        issues.append("execution_contract_authorization_arithmetic")
    source_rows = contract.get("source_hashes", [])
    if [row.get("path") for row in source_rows] != list(BOUND_SOURCE_PATHS):
        issues.append("execution_contract_source_paths")
    for row in source_rows:
        relative = row.get("path")
        if not isinstance(relative, str):
            issues.append("execution_contract_source_path_type")
            continue
        path = ROOT / relative
        if not path.is_file():
            issues.append(f"execution_contract_missing_source:{relative}")
        elif row.get("sha256") != sha256_file(path):
            issues.append(f"execution_contract_source_hash:{relative}")
    for key in (
        "service_start_restart_or_reconfigure",
        "docker",
        "simulator",
        "detector",
        "defense",
        "network_impairment",
        "physical_actuator",
        "final_evaluation",
        "evaluation_seeds_9101_9112",
        "rka_governance_attacker_view",
    ):
        if contract.get("access_boundary", {}).get(key) is not False:
            issues.append(f"execution_contract_access:{key}")
    if contract.get("m29b_authorized") is not False:
        issues.append("execution_contract_m29b_opened")
    return list(dict.fromkeys(issues))


def register_attempt(root: Path, **kwargs: Any) -> dict[str, Any]:
    contract = build_execution_contract(**kwargs)
    issues = validate_execution_contract(contract)
    if issues:
        raise M29SCampaignError(f"execution contract invalid: {issues}")
    create_once_json(root / "contract.json", contract)
    return contract


def _load_contract_artifact(
    contract: Mapping[str, Any], section: str, split: str | None = None
) -> dict[str, Any]:
    ref = contract[section] if split is None else contract[section][split]
    path = _resolve_stored_path(ref["path"])
    if sha256_file(path) != ref["sha256"]:
        raise M29SCampaignError(f"contract artifact drift: {section}/{split or ''}")
    return strict_json(path, f"{section}/{split or ''}")


def execute_split(root: Path, split: str) -> dict[str, Any]:
    if split not in design.SPLITS:
        raise M29SCampaignError(f"unknown split: {split}")
    contract = strict_json(root / "contract.json", "M29-S execution contract")
    issues = validate_execution_contract(contract)
    if issues:
        raise M29SCampaignError(f"execution contract failed verification: {issues}")
    if split == "held_out":
        freeze_path = root / "development_freeze.json"
        if not freeze_path.is_file():
            raise M29SCampaignError("held-out execution requires development freeze")
        freeze = strict_json(freeze_path, "M29-S development freeze")
        freeze_issues = verify_development_freeze(root, freeze)
        if freeze_issues:
            raise M29SCampaignError(f"development freeze failed verification: {freeze_issues}")
    commitment = _load_contract_artifact(contract, "split_commitment")
    packet_ref = commitment["packets"][split]
    packet_path = _resolve_stored_path(packet_ref["path"])
    if sha256_file(packet_path) != packet_ref["sha256"]:
        raise M29SCampaignError(f"{split} packet drift")
    packet = strict_json(packet_path, f"M29-S {split} packet")
    embedding = _load_contract_artifact(contract, "embedding_receipts", split)
    schedule = contract["execution_schedule"][split]
    for schedule_row in schedule:
        row = _packet_condition(packet, schedule_row["condition_id"])
        for arm_id in schedule_row["arm_order"]:
            output = root / "cells" / split / arm_id / f"{row['condition_id']}.json"
            if output.exists():
                raise FileExistsError(f"create-once cell already exists: {output}")
            if arm_id in design.CONTROL_ARMS:
                cell = run_control_cell(
                    arm_id=arm_id,
                    row=row,
                    packet=packet,
                    embedding=embedding,
                    execution_contract_id=contract["execution_contract_id"],
                )
            else:
                cell = run_live_cell(
                    arm_id=arm_id,
                    row=row,
                    packet=packet,
                    embedding=embedding,
                    execution_contract_id=contract["execution_contract_id"],
                )
            create_once_json(output, cell)
            print(
                canonical_json(
                    {
                        "split": split,
                        "arm_id": arm_id,
                        "condition_id": row["condition_id"],
                        "status": cell["status"],
                        "success": cell["endpoints"]["all_slot_program_exact"],
                        "model_calls": cell["accounting"]["model_calls"],
                    }
                ),
                flush=True,
            )
    receipt = build_split_receipt(root, split)
    create_once_json(root / f"{split}_receipt.json", receipt)
    return receipt


def _load_split_cells(root: Path, split: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in expected_cell_paths(split):
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        rows.append(strict_json(path, relative))
    return rows


def _arm_summary(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_arm = {arm: [row for row in cells if row["arm_id"] == arm] for arm in ARM_IDS}
    result: dict[str, Any] = {}
    for arm, rows in by_arm.items():
        pair_groups: dict[str, list[bool]] = {}
        for row in rows:
            pair_groups.setdefault(row["pair_id"], []).append(
                bool(row["endpoints"]["all_slot_program_exact"])
            )
        initial_wrong = sum(
            not row["endpoints"]["initial_all_slot_program_exact"] for row in rows
        )
        conversions = sum(row["endpoints"]["repair_conversion"] for row in rows)
        result[arm] = {
            "condition_count": len(rows),
            "all_slot_successes": sum(
                row["endpoints"]["all_slot_program_exact"] for row in rows
            ),
            "retrieval_required_successes": sum(
                row["endpoints"]["all_slot_program_exact"]
                for row in rows
                if row["endpoints"]["retrieval_required"]
            ),
            "nonretrieval_successes": sum(
                row["endpoints"]["all_slot_program_exact"]
                for row in rows
                if not row["endpoints"]["retrieval_required"]
            ),
            "correct_pairs": sum(
                len(values) == 2 and all(values) for values in pair_groups.values()
            ),
            "final_contract_violations": sum(
                row["endpoints"]["final_contract_violation"] for row in rows
            ),
            "initial_failures": initial_wrong,
            "repair_conversions": conversions,
            "repair_conversion_rate": round(conversions / initial_wrong, 12)
            if initial_wrong
            else None,
            "repair_regressions": sum(
                row["endpoints"]["repair_regression"] for row in rows
            ),
            "invalid_outputs": sum(row["accounting"]["invalid_outputs"] for row in rows),
            "refusals": sum(row["accounting"]["refusals"] for row in rows),
            "model_calls": sum(row["accounting"]["model_calls"] for row in rows),
            "prompt_tokens": sum(
                row["accounting"]["model_prompt_tokens"] for row in rows
            ),
            "completion_tokens": sum(
                row["accounting"]["model_completion_tokens"] for row in rows
            ),
        }
    return result


def _registered_contrasts(summary: Mapping[str, Any]) -> dict[str, Any]:
    plan = strict_json(design.PLAN_PATH, "M29-S factorial plan")
    return {
        row["contrast_id"]: {
            "left": row["left"],
            "right": row["right"],
            "primary": row["primary"],
            "success_difference": summary[row["left"]]["all_slot_successes"]
            - summary[row["right"]]["all_slot_successes"],
        }
        for row in plan["registered_contrasts"]
    }


def build_split_receipt(root: Path, split: str) -> dict[str, Any]:
    contract = strict_json(root / "contract.json", "M29-S execution contract")
    cells = _load_split_cells(root, split)
    summary = _arm_summary(cells)
    body = {
        "schema_version": "grideval-g7-m29s-split-receipt/v1",
        "classification": design.CLASSIFICATION,
        "execution_contract_id": contract["execution_contract_id"],
        "split": split,
        "cell_count": len(cells),
        "completed_cell_count": sum(row["status"] == "completed" for row in cells),
        "model_calls": sum(row["accounting"]["model_calls"] for row in cells),
        "scientific_summary": summary,
        "registered_contrasts": _registered_contrasts(summary),
        "source_hashes_still_frozen": validate_execution_contract(contract) == [],
        "access_boundary": _access_boundary(llm_accessed=True, embedding_accessed=True),
        "m29b_authorized": False,
    }
    return {"split_receipt_id": content_id("m29ssplitreceipt", body), **body}


def build_development_freeze(root: Path) -> dict[str, Any]:
    receipt_path = root / "development_receipt.json"
    receipt = strict_json(receipt_path, "M29-S development receipt")
    _validate_content_address(
        receipt, "split_receipt_id", "m29ssplitreceipt", "development receipt"
    )
    if receipt.get("split") != "development" or receipt.get("model_calls") != CALLS_PER_SPLIT:
        raise M29SCampaignError("development receipt is incomplete")
    contract = strict_json(root / "contract.json", "M29-S execution contract")
    issues = validate_execution_contract(contract)
    if issues:
        raise M29SCampaignError(f"cannot freeze drifted development sources: {issues}")
    cell_hashes = [
        {"path": relative, "sha256": sha256_file(root / relative)}
        for relative in expected_cell_paths("development")
    ]
    body = {
        "schema_version": "grideval-g7-m29s-development-freeze/v1",
        "classification": design.CLASSIFICATION,
        "execution_contract_id": contract["execution_contract_id"],
        "development_receipt": {
            "id": receipt["split_receipt_id"],
            "sha256": sha256_file(receipt_path),
        },
        "development_cell_hashes": cell_hashes,
        "source_hashes": copy.deepcopy(contract["source_hashes"]),
        "held_out_packet_loaded_by_runner": False,
        "source_or_prompt_adaptation_after_freeze": False,
        "m29b_authorized": False,
    }
    return {"development_freeze_id": content_id("m29sdevfreeze", body), **body}


def verify_development_freeze(
    root: Path, freeze: Mapping[str, Any] | None = None
) -> list[str]:
    issues: list[str] = []
    value = freeze or strict_json(root / "development_freeze.json", "development freeze")
    body = dict(value)
    identifier = body.pop("development_freeze_id", None)
    if identifier != content_id("m29sdevfreeze", body):
        issues.append("development_freeze_content_address")
    contract = strict_json(root / "contract.json", "M29-S execution contract")
    if value.get("execution_contract_id") != contract.get("execution_contract_id"):
        issues.append("development_freeze_contract")
    receipt_path = root / "development_receipt.json"
    if not receipt_path.is_file() or value.get("development_receipt", {}).get("sha256") != sha256_file(receipt_path):
        issues.append("development_freeze_receipt")
    for row in value.get("development_cell_hashes", []):
        path = root / row.get("path", "")
        if not path.is_file() or sha256_file(path) != row.get("sha256"):
            issues.append(f"development_freeze_cell:{row.get('path')}")
    if value.get("source_hashes") != contract.get("source_hashes"):
        issues.append("development_freeze_sources")
    issues.extend(validate_execution_contract(contract))
    return list(dict.fromkeys(issues))


def _mechanism_gate(summary: Mapping[str, Any], independent_clean: bool) -> dict[str, bool]:
    target = summary["IA4-SVR"]
    no_retrieval = summary["IA4-SV"]
    return {
        "minimum_all_slot_successes": target["all_slot_successes"] >= 12,
        "minimum_correct_pairs": target["correct_pairs"] >= 6,
        "maximum_final_violations": target["final_contract_violations"] == 0,
        "margin_over_staged_self": target["all_slot_successes"]
        - summary["IA4-SSR"]["all_slot_successes"]
        >= 4,
        "margin_over_flat_validator": target["all_slot_successes"]
        - summary["IA4-FVR"]["all_slot_successes"]
        >= 4,
        "margin_over_deterministic": target["all_slot_successes"]
        - summary["IA3-SX"]["all_slot_successes"]
        >= 4,
        "minimum_repair_conversion": (
            target["repair_conversion_rate"] is not None
            and target["repair_conversion_rate"] >= 0.5
        ),
        "maximum_repair_regressions": target["repair_regressions"] <= 1,
        "minimum_retrieval_required_margin": target["retrieval_required_successes"]
        - no_retrieval["retrieval_required_successes"]
        >= 2,
        "maximum_nonretrieval_degradation": target["nonretrieval_successes"]
        - no_retrieval["nonretrieval_successes"]
        >= -1,
        "primary_issues_empty": True,
        "independent_issues_empty": independent_clean,
    }


def build_primary_receipt(root: Path, *, independent_clean: bool = False) -> dict[str, Any]:
    contract = strict_json(root / "contract.json", "M29-S execution contract")
    development = strict_json(root / "development_receipt.json", "development receipt")
    held_out = strict_json(root / "held_out_receipt.json", "held-out receipt")
    freeze = strict_json(root / "development_freeze.json", "development freeze")
    issues = validate_execution_contract(contract) + verify_development_freeze(root, freeze)
    for receipt, split in ((development, "development"), (held_out, "held_out")):
        rebuilt = build_split_receipt(root, split)
        if canonical_json(receipt) != canonical_json(rebuilt):
            issues.append(f"{split}_receipt_mismatch")
    held_summary = held_out["scientific_summary"]
    gate_checks = _mechanism_gate(held_summary, independent_clean)
    totals = {
        "model_calls": development["model_calls"] + held_out["model_calls"],
        "prompt_tokens": sum(
            receipt["scientific_summary"][arm]["prompt_tokens"]
            for receipt in (development, held_out)
            for arm in ARM_IDS
        ),
        "completion_tokens": sum(
            receipt["scientific_summary"][arm]["completion_tokens"]
            for receipt in (development, held_out)
            for arm in ARM_IDS
        ),
    }
    if totals["model_calls"] != MAXIMUM_ADDITIONAL_CALLS:
        issues.append("model_call_total")
    body = {
        "schema_version": "grideval-g7-m29s-primary-receipt/v1",
        "classification": design.CLASSIFICATION,
        "execution_contract_id": contract["execution_contract_id"],
        "status": "passed" if not issues else "failed_qualification",
        "issues": list(dict.fromkeys(issues)),
        "development_receipt_id": development["split_receipt_id"],
        "development_freeze_id": freeze["development_freeze_id"],
        "held_out_receipt_id": held_out["split_receipt_id"],
        "development_summary": development["scientific_summary"],
        "held_out_summary": held_summary,
        "held_out_registered_contrasts": held_out["registered_contrasts"],
        "held_out_mechanism_gate_checks": gate_checks,
        "new_offline_complementarity_proposal_eligible": bool(
            not issues and all(gate_checks.values())
        ),
        "totals": totals,
        "access_boundary": _access_boundary(llm_accessed=True, embedding_accessed=True),
        "claim_boundary": contract["claim_boundary"],
        "m29b_authorized": False,
    }
    return {"primary_receipt_id": content_id("m29sprimary", body), **body}


def verify_primary_receipt(root: Path) -> list[str]:
    path = root / "primary_receipt.json"
    if not path.is_file():
        return ["missing_primary_receipt"]
    stored = strict_json(path, "M29-S primary receipt")
    independent_clean = bool(
        (root / "independent_audit_receipt.json").is_file()
        and strict_json(root / "independent_audit_receipt.json", "independent audit").get("status")
        == "passed"
    )
    rebuilt = build_primary_receipt(root, independent_clean=independent_clean)
    return [] if canonical_json(stored) == canonical_json(rebuilt) else ["primary_receipt_mismatch"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    split = commands.add_parser("prepare-splits")
    split.add_argument("--fixture", type=Path, required=True)
    split.add_argument("--output-root", type=Path, required=True)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--output", type=Path, required=True)
    embed = commands.add_parser("embed")
    embed.add_argument("--preflight", type=Path, required=True)
    embed.add_argument("--packet", type=Path, required=True)
    embed.add_argument("--output", type=Path, required=True)
    register = commands.add_parser("register")
    register.add_argument("--root", type=Path, required=True)
    register.add_argument("--design-contract", type=Path, required=True)
    register.add_argument("--plan-audit", type=Path, required=True)
    register.add_argument("--split-commitment", type=Path, required=True)
    register.add_argument("--preflight", type=Path, required=True)
    register.add_argument("--development-embedding", type=Path, required=True)
    register.add_argument("--held-out-embedding", type=Path, required=True)
    register.add_argument("--authorization-note-id", required=True)
    execute = commands.add_parser("execute-split")
    execute.add_argument("--root", type=Path, required=True)
    execute.add_argument("--split", choices=design.SPLITS, required=True)
    freeze = commands.add_parser("freeze-development")
    freeze.add_argument("--root", type=Path, required=True)
    primary = commands.add_parser("primary")
    primary.add_argument("--root", type=Path, required=True)
    primary.add_argument("--independent-clean", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare-splits":
        result = prepare_split_packets(
            fixture_path=args.fixture.resolve(), output_root=args.output_root.resolve()
        )
        print(canonical_json({"split_commitment_id": result["split_commitment_id"]}))
    elif args.command == "preflight":
        result = build_service_preflight()
        create_once_json(args.output, result)
        print(canonical_json({"service_preflight_id": result["service_preflight_id"]}))
    elif args.command == "embed":
        result = build_embedding_receipt(
            strict_json(args.preflight, "preflight"),
            strict_json(args.packet, "split packet"),
        )
        create_once_json(args.output, result)
        print(canonical_json({"embedding_receipt_id": result["embedding_receipt_id"]}))
    elif args.command == "register":
        result = register_attempt(
            args.root,
            design_contract_path=args.design_contract.resolve(),
            plan_audit_path=args.plan_audit.resolve(),
            split_commitment_path=args.split_commitment.resolve(),
            preflight_path=args.preflight.resolve(),
            development_embedding_path=args.development_embedding.resolve(),
            held_out_embedding_path=args.held_out_embedding.resolve(),
            authorization_note_id=args.authorization_note_id,
        )
        print(canonical_json({"execution_contract_id": result["execution_contract_id"]}))
    elif args.command == "execute-split":
        result = execute_split(args.root.resolve(), args.split)
        print(canonical_json({"split_receipt_id": result["split_receipt_id"], "model_calls": result["model_calls"]}))
    elif args.command == "freeze-development":
        result = build_development_freeze(args.root.resolve())
        create_once_json(args.root.resolve() / "development_freeze.json", result)
        print(canonical_json({"development_freeze_id": result["development_freeze_id"]}))
    elif args.command == "primary":
        result = build_primary_receipt(
            args.root.resolve(), independent_clean=args.independent_clean
        )
        create_once_json(args.root.resolve() / "primary_receipt.json", result)
        print(canonical_json({"primary_receipt_id": result["primary_receipt_id"], "status": result["status"]}))
    else:
        issues = verify_primary_receipt(args.root.resolve())
        print(canonical_json({"issues": issues}))
        raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
