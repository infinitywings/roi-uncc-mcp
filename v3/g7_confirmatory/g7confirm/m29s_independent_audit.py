"""Independent byte-level and endpoint audit for an M29-S attempt.

This module intentionally does not import the M29-S campaign or semantic
compiler.  It recomputes content addresses, visible-input lineage, factorial
call parity, staged projection, semantic endpoints, and access seals directly
from frozen JSON artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = "PRELIMINARY_ONLY"
SPLITS = ("development", "held_out")
SLOT_KEYS = (
    "strategy_id",
    "effect_direction",
    "allowed_targets",
    "forbidden_windows",
    "objective_weights",
    "max_total_energy",
    "max_total_visibility",
    "min_actions",
    "max_actions",
    "max_level_delta",
    "cooldown_same_target",
)
CONTROL_ARMS = ("IA3-SX", "IA5-OC")
REFERENCE_ARMS = ("IA4-C1", "IA4-C1R")
FACTORIAL_ARMS = (
    "IA4-FS",
    "IA4-FSR",
    "IA4-FV",
    "IA4-FVR",
    "IA4-SS",
    "IA4-SSR",
    "IA4-SV",
    "IA4-SVR",
)
ARM_IDS = CONTROL_ARMS + REFERENCE_ARMS + FACTORIAL_ARMS
CALLS = {
    **{arm: 0 for arm in CONTROL_ARMS},
    **{arm: 1 for arm in REFERENCE_ARMS},
    **{arm: 2 for arm in FACTORIAL_ARMS},
}
ARM_FACTORS = {
    "IA3-SX": ("staged", "deterministic_internal_checks", False),
    "IA5-OC": ("latent", "none", False),
    "IA4-C1": ("flat", "none", False),
    "IA4-C1R": ("flat", "none", True),
    "IA4-FS": ("flat", "neutral_self_revision", False),
    "IA4-FSR": ("flat", "neutral_self_revision", True),
    "IA4-FV": ("flat", "validator_guided_revision", False),
    "IA4-FVR": ("flat", "validator_guided_revision", True),
    "IA4-SS": ("staged", "neutral_self_revision", False),
    "IA4-SSR": ("staged", "neutral_self_revision", True),
    "IA4-SV": ("staged", "validator_guided_revision", False),
    "IA4-SVR": ("staged", "validator_guided_revision", True),
}
NEUTRAL_MESSAGE = (
    "Review the initial draft using only the original visible input. "
    "Return the final response in the same registered schema. Treat all "
    "fields as unverified and do not add external facts."
)
VALIDATOR_CODES = {
    "schema",
    "evidence_unknown",
    "evidence_missing",
    "authority_conflict",
    "expired_record",
    "topology_inconsistent",
    "budget_inconsistent",
    "weights_inconsistent",
    "cooldown_inconsistent",
}
VALIDATOR_SLOTS = set(SLOT_KEYS) | {"strategy_program", "required_evidence_ids"}


class M29SIndependentAuditError(ValueError):
    """Raised when an independent audit artifact is malformed."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}_{sha256_value(payload)}"


def strict_json(path: Path, label: str) -> Any:
    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M29SIndependentAuditError(f"duplicate key in {label}: {key}")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(
            M29SIndependentAuditError(f"non-finite value in {label}: {value}")
        ),
    )


def create_once_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        handle.write("\n")


def _resolve_stored_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _content_address_issues(
    payload: Mapping[str, Any], field: str, prefix: str, label: str
) -> list[str]:
    body = dict(payload)
    identifier = body.pop(field, None)
    return [] if identifier == content_id(prefix, body) else [f"content_address:{label}"]


def _artifact(contract: Mapping[str, Any], section: str, split: str | None = None) -> dict[str, Any]:
    ref = contract[section] if split is None else contract[section][split]
    path = _resolve_stored_path(ref["path"])
    if not path.is_file() or sha256_file(path) != ref["sha256"]:
        raise M29SIndependentAuditError(f"artifact drift: {section}/{split or ''}")
    return strict_json(path, f"{section}/{split or ''}")


def _verify_contract(contract: Mapping[str, Any]) -> list[str]:
    issues = _content_address_issues(
        contract, "execution_contract_id", "m29sexec", "execution_contract"
    )
    if contract.get("classification") != CLASSIFICATION:
        issues.append("contract_classification")
    if contract.get("arm_ids") != list(ARM_IDS):
        issues.append("contract_arms")
    budget = contract.get("authorization_budget", {})
    if budget.get("prior_model_calls") != 101:
        issues.append("contract_prior_calls")
    if budget.get("contracted_new_model_calls") != 576:
        issues.append("contract_new_calls")
    if budget.get("maximum_cumulative_model_calls") != 677:
        issues.append("contract_cumulative_calls")
    if budget.get("pi_authorized_cumulative_ceiling") != 1000:
        issues.append("contract_authorization")
    if budget.get("remaining_after_attempt") != 323:
        issues.append("contract_authorization_arithmetic")
    policy = contract.get("attempt_policy", {})
    expected_policy = {
        "create_once": True,
        "retry_count": 0,
        "overwrite": False,
        "development_before_held_out": True,
        "held_out_requires_development_freeze": True,
        "adaptation_after_development": False,
    }
    if policy != expected_policy:
        issues.append("contract_attempt_policy")
    for row in contract.get("source_hashes", []):
        relative = row.get("path")
        path = ROOT / relative if isinstance(relative, str) else ROOT / "missing"
        if not path.is_file() or row.get("sha256") != sha256_file(path):
            issues.append(f"contract_source_hash:{relative}")
    access = contract.get("access_boundary", {})
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
        if access.get(key) is not False:
            issues.append(f"contract_access:{key}")
    if contract.get("m29b_authorized") is not False:
        issues.append("contract_m29b_opened")
    return issues


def _visible_digest(request: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    messages = request.get("messages", [])
    if len(messages) < 2 or messages[1].get("role") != "user":
        raise M29SIndependentAuditError("initial request messages malformed")
    visible = json.loads(messages[1]["content"])
    return sha256_value(visible), visible


def _program(draft: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(draft, Mapping):
        return None
    value = draft.get("strategy_program")
    return value if isinstance(value, Mapping) else None


def _sorted_semantic(value: Any, slot: str) -> Any:
    if slot in {"allowed_targets", "forbidden_windows"} and isinstance(value, list):
        return sorted(value)
    return value


def _score(
    draft: Mapping[str, Any] | None,
    interface: str,
    oracle: Mapping[str, Any],
    visible: Mapping[str, Any],
) -> dict[str, Any]:
    program = _program(draft)
    oracle_program = oracle["strategy_program"]
    slots = {
        key: bool(
            program is not None
            and canonical_json(_sorted_semantic(program.get(key), key))
            == canonical_json(_sorted_semantic(oracle_program[key], key))
        )
        for key in SLOT_KEYS
    }
    expected_ids = sorted(oracle_program["required_evidence_ids"])
    lineage = bool(
        program is not None
        and sorted(program.get("required_evidence_ids", [])) == expected_ids
    )
    ledger_exact: bool | None = None
    slot_lineage: bool | None = None
    if interface == "staged":
        records = visible["visible_evidence"]["records"]
        digest = sha256_value(visible)
        expected_ledger = {
            "schema_version": "grideval-g7-m29s-evidence-ledger/v1",
            "condition_id": visible["visible_evidence"]["condition_id"],
            "active_evidence_ids": sorted(
                row["record_id"] for row in records if row["status"] == "active"
            ),
            "superseded_evidence_ids": sorted(
                row["record_id"] for row in records if row["status"] == "superseded"
            ),
            "expired_evidence_ids": sorted(
                row["record_id"] for row in records if row["status"] == "expired"
            ),
            "unresolved_conflict_ids": [],
            "authority_order": ["emergency", "operator", "planning", "advisory"],
            "visible_input_digest": digest,
        }
        ledger_exact = bool(
            draft
            and canonical_json(draft.get("evidence_ledger"))
            == canonical_json(expected_ledger)
        )
        submitted_slots = draft.get("semantic_slots", {}).get("slots", {}) if draft else {}
        oracle_slots = oracle["semantic_slots"]["slots"]
        slot_lineage = bool(
            set(submitted_slots) == set(SLOT_KEYS)
            and all(
                sorted(submitted_slots[key].get("supporting_evidence_ids", []))
                == sorted(oracle_slots[key]["supporting_evidence_ids"])
                for key in SLOT_KEYS
            )
        )
        lineage = bool(lineage and slot_lineage)
    success = bool(
        all(slots.values())
        and lineage
        and (interface != "staged" or ledger_exact is True)
    )
    return {
        "per_slot_exact": slots,
        "correct_slot_count": sum(slots.values()),
        "program_semantics_exact": all(slots.values()),
        "evidence_lineage_exact": lineage,
        "evidence_ledger_exact": ledger_exact,
        "semantic_slot_lineage_exact": slot_lineage,
        "all_slot_program_exact": success,
    }


def _projection_issues(
    draft: Mapping[str, Any] | None, label: str
) -> list[str]:
    if not isinstance(draft, Mapping):
        return []
    slots = draft.get("semantic_slots")
    program = draft.get("strategy_program")
    if not isinstance(slots, Mapping) or not isinstance(program, Mapping):
        return [f"staged_components:{label}"]
    rows = slots.get("slots", {})
    if set(rows) != set(SLOT_KEYS):
        return [f"staged_slot_coverage:{label}"]
    for key in SLOT_KEYS:
        expected = _sorted_semantic(rows[key].get("value"), key)
        observed = _sorted_semantic(program.get(key), key)
        if canonical_json(expected) != canonical_json(observed):
            return [f"staged_projection:{label}:{key}"]
    evidence = sorted(
        {
            evidence_id
            for key in SLOT_KEYS
            for evidence_id in rows[key].get("supporting_evidence_ids", [])
        }
    )
    if evidence != sorted(program.get("required_evidence_ids", [])):
        return [f"staged_projection_evidence:{label}"]
    return []


def _diagnostic_issues(value: Any, label: str) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"validator_diagnostics_absent:{label}"]
    if set(value) != {
        "schema_version",
        "draft_id",
        "visible_input_digest",
        "diagnostics",
    }:
        return [f"validator_diagnostics_fields:{label}"]
    issues: list[str] = []
    for row in value.get("diagnostics", []):
        if set(row) != {"code", "slot"}:
            issues.append(f"validator_diagnostic_row_fields:{label}")
        elif row["code"] not in VALIDATOR_CODES or row["slot"] not in VALIDATOR_SLOTS:
            issues.append(f"validator_diagnostic_value:{label}")
    lowered = canonical_json(value).lower()
    for forbidden in ('"expected"', '"correct"', '"score"', '"label"'):
        if forbidden in lowered:
            issues.append(f"validator_leak:{label}:{forbidden}")
    return issues


def _verify_cell(
    cell: Mapping[str, Any],
    row: Mapping[str, Any],
    contract: Mapping[str, Any],
    packet: Mapping[str, Any],
    embedding: Mapping[str, Any],
) -> tuple[list[str], Mapping[str, Any] | None]:
    label = f"{cell.get('split')}/{cell.get('arm_id')}/{cell.get('condition_id')}"
    issues = _content_address_issues(cell, "cell_id", "m29scell", label)
    arm = cell.get("arm_id")
    if arm not in ARM_IDS:
        return [*issues, f"cell_arm:{label}"], None
    interface, feedback, retrieval = ARM_FACTORS[arm]
    if cell.get("execution_contract_id") != contract.get("execution_contract_id"):
        issues.append(f"cell_contract:{label}")
    if cell.get("classification") != CLASSIFICATION:
        issues.append(f"cell_classification:{label}")
    if cell.get("condition_id") != row["condition_id"] or cell.get("split") != row["split"]:
        issues.append(f"cell_identity:{label}")
    accounting = cell.get("accounting", {})
    if accounting.get("model_calls") != CALLS[arm]:
        issues.append(f"cell_model_calls:{label}")
    access = cell.get("access_boundary", {})
    if access.get("llm_accessed") is not (arm not in CONTROL_ARMS):
        issues.append(f"cell_llm_access:{label}")
    if access.get("existing_embedding_accessed") is not retrieval:
        issues.append(f"cell_embedding_access:{label}")
    for key in (
        "model_or_embedding_service_started_or_restarted",
        "embedding_configuration_changed",
        "docker_accessed",
        "helics_accessed",
        "opender_accessed",
        "gridlabd_accessed",
        "simulator_accessed",
        "detector_accessed",
        "defense_accessed",
        "network_impairment_accessed",
        "physical_actuator_accessed",
        "final_evaluation_accessed",
        "rka_governance_attacker_view_accessed",
    ):
        if access.get(key) is not False:
            issues.append(f"cell_access:{label}:{key}")
    if access.get("final_evaluation_seeds_accessed") != []:
        issues.append(f"cell_final_seeds:{label}")

    visible: Mapping[str, Any] | None = None
    corpus_by_id = {
        value["passage_id"]: value for value in packet["corpus"]["passages"]
    }
    query = next(
        value
        for value in packet["query_manifest"]["queries"]
        if value["condition_id"] == row["condition_id"]
    )
    if arm == "IA5-OC" and row["latent_condition"]["retrieval_required"]:
        expected_passage_ids = row["oracle_retrieval_passage_ids"]
    elif retrieval:
        retrieval_row = next(
            value
            for value in embedding["retrievals"]
            if value["condition_id"] == row["condition_id"]
        )
        expected_passage_ids = [value["passage_id"] for value in retrieval_row["top_k"]]
    else:
        expected_passage_ids = query["flat_passage_ids"]
    if cell.get("corpus_view_passage_ids") != expected_passage_ids:
        issues.append(f"cell_corpus_view:{label}")
    if arm in CONTROL_ARMS:
        if cell.get("initial_request") is not None or cell.get("revision_request") is not None:
            issues.append(f"control_model_request:{label}")
    else:
        request = cell.get("initial_request")
        if not isinstance(request, Mapping):
            issues.append(f"initial_request_absent:{label}")
        else:
            try:
                digest, visible = _visible_digest(request)
                if canonical_json(visible["visible_evidence"]) != canonical_json(row["visible_evidence"]):
                    issues.append(f"visible_evidence:{label}")
                if [item["passage_id"] for item in visible["corpus_passages"]] != cell.get("corpus_view_passage_ids"):
                    issues.append(f"corpus_view:{label}")
                expected_passages = [corpus_by_id[value] for value in expected_passage_ids]
                if canonical_json(visible["corpus_passages"]) != canonical_json(expected_passages):
                    issues.append(f"corpus_passage_bytes:{label}")
                schema_text = canonical_json(
                    request.get("response_format", {}).get("json_schema", {}).get("schema")
                )
                if "uniqueItems" in schema_text or '"$ref"' in schema_text:
                    issues.append(f"provider_schema_projection:{label}")
                if request.get("temperature") != 0 or request.get("max_tokens") != 900:
                    issues.append(f"model_sampling:{label}")
                if request.get("stream") is not False or request.get("n") != 1:
                    issues.append(f"model_cardinality:{label}")
                program = _program(cell.get("final_draft"))
                if program is not None and program.get("visible_input_digest") != digest:
                    issues.append(f"program_input_lineage:{label}")
            except Exception as exc:
                issues.append(f"initial_request_parse:{label}:{type(exc).__name__}")
        if CALLS[arm] == 1:
            if cell.get("revision_request") is not None or cell.get("revision_response") is not None:
                issues.append(f"reference_revision:{label}")
        else:
            revision = cell.get("revision_request")
            if not isinstance(revision, Mapping):
                issues.append(f"revision_request_absent:{label}")
            else:
                messages = revision.get("messages", [])
                if len(messages) != 4:
                    issues.append(f"revision_message_count:{label}")
                elif feedback == "neutral_self_revision":
                    if messages[-1].get("content") != NEUTRAL_MESSAGE:
                        issues.append(f"neutral_revision_message:{label}")
                    if cell.get("validator_diagnostics") is not None:
                        issues.append(f"neutral_received_diagnostics:{label}")
                else:
                    issues.extend(_diagnostic_issues(cell.get("validator_diagnostics"), label))
                    encoded = canonical_json(cell.get("validator_diagnostics"))
                    if not str(messages[-1].get("content", "")).endswith(encoded):
                        issues.append(f"validator_message_lineage:{label}")
    if interface == "staged":
        issues.extend(_projection_issues(cell.get("initial_draft"), f"{label}:initial"))
        issues.extend(_projection_issues(cell.get("final_draft"), f"{label}:final"))
    if visible is None and arm in CONTROL_ARMS:
        visible = {
            "visible_evidence": row["visible_evidence"],
            "corpus_passages": [corpus_by_id[value] for value in expected_passage_ids],
        }
    if visible is not None:
        initial_scored = _score(
            cell.get("initial_draft"),
            "staged" if interface in {"staged", "latent"} else "flat",
            row["independent_oracle"],
            visible,
        )
        scored = _score(
            cell.get("final_draft"),
            "staged" if interface in {"staged", "latent"} else "flat",
            row["independent_oracle"],
            visible,
        )
        if canonical_json(initial_scored) != canonical_json(cell.get("initial_scores")):
            issues.append(f"initial_scores:{label}")
        recorded = cell.get("final_scores")
        if canonical_json(scored) != canonical_json(recorded):
            issues.append(f"final_scores:{label}")
        expected_endpoints = {
            **scored,
            "initial_all_slot_program_exact": initial_scored["all_slot_program_exact"],
            "repair_conversion": bool(
                not initial_scored["all_slot_program_exact"]
                and scored["all_slot_program_exact"]
            ),
            "repair_regression": bool(
                initial_scored["all_slot_program_exact"]
                and not scored["all_slot_program_exact"]
            ),
            "final_contract_violation": cell.get("final_draft") is None
            if arm not in CONTROL_ARMS
            else False,
            "retrieval_required": bool(row["latent_condition"]["retrieval_required"]),
        }
        if canonical_json(expected_endpoints) != canonical_json(cell.get("endpoints")):
            issues.append(f"endpoints:{label}")
    response_records = [cell.get("initial_response")]
    if CALLS[arm] == 2:
        response_records.append(cell.get("revision_response"))
    expected_prompt_tokens = sum(
        int(value.get("usage", {}).get("prompt_tokens", 0))
        for value in response_records
        if isinstance(value, Mapping)
    )
    expected_completion_tokens = sum(
        int(value.get("usage", {}).get("completion_tokens", 0))
        for value in response_records
        if isinstance(value, Mapping)
    )
    if accounting.get("model_prompt_tokens") != expected_prompt_tokens:
        issues.append(f"cell_prompt_tokens:{label}")
    if accounting.get("model_completion_tokens") != expected_completion_tokens:
        issues.append(f"cell_completion_tokens:{label}")
    return issues, visible


def _embedding_issues(
    receipt: Mapping[str, Any], packet: Mapping[str, Any], split: str
) -> list[str]:
    issues: list[str] = []
    passages = packet["corpus"]["passages"]
    queries = packet["query_manifest"]["queries"]
    passage_vectors = receipt.get("passage_vectors", [])
    query_vectors = receipt.get("query_vectors", [])
    if len(passage_vectors) != len(passages) or len(query_vectors) != len(queries):
        return [f"embedding_vector_cardinality:{split}"]
    if any(len(value) != 1024 for value in [*passage_vectors, *query_vectors]):
        issues.append(f"embedding_vector_dimensions:{split}")
        return issues
    def cosine(left: Sequence[float], right: Sequence[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            raise M29SIndependentAuditError("zero-norm embedding")
        return dot / (left_norm * right_norm)
    by_condition = {
        value["condition_id"]: value for value in receipt.get("retrievals", [])
    }
    passage_ids = [value["passage_id"] for value in passages]
    for query, vector in zip(queries, query_vectors):
        expected = sorted(
            (
                {
                    "passage_id": passage_id,
                    "cosine_similarity": round(cosine(vector, candidate), 12),
                }
                for passage_id, candidate in zip(passage_ids, passage_vectors)
            ),
            key=lambda value: (-value["cosine_similarity"], value["passage_id"]),
        )[:4]
        observed = by_condition.get(query["condition_id"], {}).get("top_k")
        if canonical_json(observed) != canonical_json(expected):
            issues.append(f"embedding_top_k:{split}:{query['condition_id']}")
    return issues


def _request_parity_issues(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    issues: list[str] = []
    by_key = {(row["arm_id"], row["condition_id"]): row for row in cells}
    matched = (
        ("IA4-C1", "IA4-FS", "IA4-FV"),
        ("IA4-C1R", "IA4-FSR", "IA4-FVR"),
        ("IA4-SS", "IA4-SV"),
        ("IA4-SSR", "IA4-SVR"),
    )
    condition_ids = sorted({row["condition_id"] for row in cells})
    for condition_id in condition_ids:
        for group in matched:
            rows = [by_key[(arm, condition_id)] for arm in group]
            requests = [row["initial_request"] for row in rows]
            if any(request is None for request in requests):
                continue
            canonical = [canonical_json(request) for request in requests]
            if len(set(canonical)) != 1:
                issues.append(f"initial_request_parity:{condition_id}:{','.join(group)}")
        for retrieval_group in (
            ("IA4-FS", "IA4-FV", "IA4-SS", "IA4-SV"),
            ("IA4-FSR", "IA4-FVR", "IA4-SSR", "IA4-SVR"),
        ):
            users = [
                by_key[(arm, condition_id)]["initial_request"]["messages"][1]
                for arm in retrieval_group
                if by_key[(arm, condition_id)]["initial_request"] is not None
            ]
            if users and len({canonical_json(value) for value in users}) != 1:
                issues.append(f"visible_input_parity:{condition_id}:{retrieval_group[0]}")
    return issues


def _scientific_summary(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split in SPLITS:
        result[split] = {}
        for arm in ARM_IDS:
            rows = [
                row for row in cells if row["split"] == split and row["arm_id"] == arm
            ]
            groups: dict[str, list[bool]] = {}
            for row in rows:
                groups.setdefault(row["pair_id"], []).append(
                    bool(row["endpoints"]["all_slot_program_exact"])
                )
            result[split][arm] = {
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
                    len(values) == 2 and all(values) for values in groups.values()
                ),
                "model_calls": sum(row["accounting"]["model_calls"] for row in rows),
                "final_contract_violations": sum(
                    row["endpoints"]["final_contract_violation"] for row in rows
                ),
                "repair_conversions": sum(
                    row["endpoints"]["repair_conversion"] for row in rows
                ),
                "repair_regressions": sum(
                    row["endpoints"]["repair_regression"] for row in rows
                ),
            }
    return result


def verify(root: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    issues: list[str] = []
    contract = strict_json(root / "contract.json", "M29-S contract")
    issues.extend(_verify_contract(contract))
    embeddings: dict[str, dict[str, Any]] = {}
    try:
        design_contract = _artifact(contract, "design_contract")
        if design_contract.get("design_contract_id") != contract["design_contract"]["id"]:
            issues.append("design_contract_identity")
        plan_audit = _artifact(contract, "plan_audit")
        if plan_audit.get("audit_id") != contract["plan_audit"]["id"]:
            issues.append("plan_audit_identity")
        if plan_audit.get("status") != "passed" or plan_audit.get("issues") != []:
            issues.append("plan_audit_status")
        preflight = _artifact(contract, "service_preflight")
        issues.extend(
            _content_address_issues(
                preflight, "service_preflight_id", "m29spreflight", "service_preflight"
            )
        )
        if preflight.get("llm", {}).get("id") != "qwen3.6-35b-a3b":
            issues.append("preflight_llm_identity")
        if preflight.get("embedding", {}).get("id") != "qwen3-embedding:0.6b":
            issues.append("preflight_embedding_identity")
        for split in SPLITS:
            embedding = _artifact(contract, "embedding_receipts", split)
            embeddings[split] = embedding
            issues.extend(
                _content_address_issues(
                    embedding, "embedding_receipt_id", "m29sembed", f"embedding:{split}"
                )
            )
            if embedding.get("model") != "qwen3-embedding:0.6b" or embedding.get("dimensions") != 1024:
                issues.append(f"embedding_identity:{split}")
            if embedding.get("accounting", {}).get("embedding_http_calls") != 2:
                issues.append(f"embedding_call_count:{split}")
    except Exception as exc:
        issues.append(f"contract_artifact_chain:{type(exc).__name__}")
    commitment = _artifact(contract, "split_commitment")
    issues.extend(
        _content_address_issues(
            commitment, "split_commitment_id", "m29ssplits", "split_commitment"
        )
    )
    packets: dict[str, dict[str, Any]] = {}
    for split in SPLITS:
        ref = commitment["packets"][split]
        path = _resolve_stored_path(ref["path"])
        if sha256_file(path) != ref["sha256"]:
            issues.append(f"split_packet_hash:{split}")
        packet = strict_json(path, f"M29-S {split} packet")
        packets[split] = packet
        issues.extend(
            _content_address_issues(packet, "split_packet_id", "m29spacket", f"packet:{split}")
        )
        if packet.get("split") != split or packet.get("condition_count") != 16:
            issues.append(f"split_packet_identity:{split}")
        if any(row.get("split") != split for row in packet.get("conditions", [])):
            issues.append(f"split_packet_cross_contamination:{split}")
        if split in embeddings:
            issues.extend(_embedding_issues(embeddings[split], packet, split))

    rows = {
        (row["split"], row["condition_id"]): row
        for packet in packets.values()
        for row in packet["conditions"]
    }
    cells: list[dict[str, Any]] = []
    expected_paths = set(contract.get("expected_cell_paths", []))
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.glob("cells/*/*/*.json")
    }
    if actual_paths != expected_paths:
        issues.append("attempt_cell_path_set")
    for relative in sorted(expected_paths):
        path = root / relative
        if not path.is_file():
            issues.append(f"missing_cell:{relative}")
            continue
        cell = strict_json(path, relative)
        cells.append(cell)
        row = rows.get((cell.get("split"), cell.get("condition_id")))
        if row is None:
            issues.append(f"cell_unknown_condition:{relative}")
            continue
        if cell.get("split") not in embeddings:
            issues.append(f"cell_embedding_receipt_absent:{relative}")
            continue
        cell_issues, _ = _verify_cell(
            cell,
            row,
            contract,
            packets[cell["split"]],
            embeddings[cell["split"]],
        )
        issues.extend(cell_issues)
    if len(cells) != 384:
        issues.append("cell_count")
    if sum(row.get("accounting", {}).get("model_calls", 0) for row in cells) != 576:
        issues.append("model_call_total")
    if len(cells) == 384:
        issues.extend(_request_parity_issues(cells))
    freeze_path = root / "development_freeze.json"
    if not freeze_path.is_file():
        issues.append("development_freeze_absent")
    else:
        freeze = strict_json(freeze_path, "development freeze")
        issues.extend(
            _content_address_issues(
                freeze, "development_freeze_id", "m29sdevfreeze", "development_freeze"
            )
        )
        if freeze.get("held_out_packet_loaded_by_runner") is not False:
            issues.append("development_freeze_heldout_access")
        for row in freeze.get("development_cell_hashes", []):
            path = root / row.get("path", "")
            if not path.is_file() or sha256_file(path) != row.get("sha256"):
                issues.append(f"development_freeze_cell:{row.get('path')}")
    return list(dict.fromkeys(issues)), cells, _scientific_summary(cells)


def build_audit_receipt(root: Path) -> dict[str, Any]:
    issues, cells, summary = verify(root)
    contract = strict_json(root / "contract.json", "M29-S contract")
    body = {
        "schema_version": "grideval-g7-m29s-independent-audit/v1",
        "classification": CLASSIFICATION,
        "execution_contract_id": contract.get("execution_contract_id"),
        "auditor_source_sha256": sha256_file(Path(__file__).resolve()),
        "independent_imports_campaign": False,
        "independent_imports_semantic_compiler": False,
        "source_hashes_recomputed": True,
        "content_addresses_recomputed": True,
        "visible_input_lineage_recomputed": True,
        "factorial_request_parity_recomputed": True,
        "staged_projection_recomputed": True,
        "semantic_endpoints_recomputed": True,
        "authorization_arithmetic_recomputed": True,
        "cell_count": len(cells),
        "model_calls": sum(
            row.get("accounting", {}).get("model_calls", 0) for row in cells
        ),
        "scientific_summary": summary,
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "m29b_authorized": False,
    }
    return {"audit_id": content_id("m29saudit", body), **body}


def verify_audit_receipt(root: Path) -> list[str]:
    path = root / "independent_audit_receipt.json"
    if not path.is_file():
        return ["missing_independent_audit_receipt"]
    stored = strict_json(path, "M29-S independent audit")
    rebuilt = build_audit_receipt(root)
    return [] if canonical_json(stored) == canonical_json(rebuilt) else [
        "independent_audit_receipt_mismatch"
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        receipt = build_audit_receipt(args.root.resolve())
        create_once_json(args.root.resolve() / "independent_audit_receipt.json", receipt)
        print(canonical_json({"audit_id": receipt["audit_id"], "status": receipt["status"], "issues": receipt["issues"]}))
        raise SystemExit(0 if receipt["status"] == "passed" else 1)
    issues = verify_audit_receipt(args.root.resolve())
    print(canonical_json({"issues": issues}))
    raise SystemExit(0 if not issues else 1)


if __name__ == "__main__":
    main()
