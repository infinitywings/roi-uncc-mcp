"""Offline primitives for the M29-S semantic-compiler mechanism study.

The module defines disjoint latent conditions, visible evidence, flat and
staged interfaces, deterministic validation tools, exact semantic scoring,
and a content-addressed design fixture. It contains no network, simulator,
Docker, detector, defense, or actuator client.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "m29s_factorial_plan.json"
LEDGER_SCHEMA_PATH = ROOT / "m29s_evidence_ledger.schema.json"
SLOTS_SCHEMA_PATH = ROOT / "m29s_semantic_slots.schema.json"
PROGRAM_SCHEMA_PATH = ROOT / "m29s_strategy_program.schema.json"
M29R_FIXTURE_PATH = ROOT / "artifacts/m29r_design_attempt1/design_fixture.json"

CLASSIFICATION = "PRELIMINARY_ONLY"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1PK13X15NDM52ZH40Z5TAZS"
DECISION_ID = "dec_01M1PMESQHHNCE5XK066EQB79X"
SPLITS = ("development", "held_out")
SIDES = ("left", "right")
WINDOWS = ("t0", "t1", "t2", "t3")
TARGETS = ("GRID_NORTH_A", "GRID_SOUTH_B", "GRID_EAST_C", "GRID_WEST_D")
AUTHORITY_ORDER = ("emergency", "operator", "planning", "advisory")
STRATEGIES = (
    "gradual_bias",
    "delayed_shift",
    "persistent_pressure",
    "resource_conserving",
)
WEIGHT_KEYS = ("effect", "persistence", "energy", "visibility")
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
REFERENCE_ARMS = ("IA4-C1", "IA4-C1R")
CONTROL_ARMS = ("IA3-SX", "IA5-OC")
FINAL_EVALUATION_SEEDS = tuple(range(9101, 9113))
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


class M29SContractError(ValueError):
    """Raised when an M29-S design or interface invariant is violated."""


def canonical_json(value: Any) -> str:
    """Return deterministic strict JSON for hashes and parity checks."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_copy(value: Any) -> Any:
    return json.loads(canonical_json(value))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}_{sha256_value(payload)}"


def strict_json_file(path: Path, label: str) -> Any:
    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M29SContractError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise M29SContractError(f"non-finite JSON value in {label}: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_pairs,
        parse_constant=reject_constant,
    )


def _require_exact_keys(
    payload: Mapping[str, Any], expected: set[str], label: str
) -> None:
    actual = set(payload)
    if actual != expected:
        raise M29SContractError(
            f"{label} keys differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")


@dataclass(frozen=True)
class LatentCondition:
    """One preregistered semantic-compilation condition."""

    split: str
    pair_id: str
    construct: str
    side: str
    seed: int
    rendering: str
    retrieval_required: bool
    doctrine_code: str
    strategy_id: str
    effect_direction: str
    allowed_targets: tuple[str, ...]
    forbidden_windows: tuple[str, ...]
    objective_weights: tuple[tuple[str, int], ...]
    max_total_energy: int
    max_total_visibility: int
    min_actions: int
    max_actions: int
    max_level_delta: int
    cooldown_same_target: bool

    @property
    def condition_id(self) -> str:
        return f"m29s_{self.split}_{self.pair_id}_{self.side}"

    @property
    def pair_key(self) -> str:
        return f"m29s_{self.split}_pair_{self.pair_id}"

    @property
    def doctrine_passage_id(self) -> str:
        return f"m29s_doc_{_slug(self.doctrine_code)}"

    def weights(self) -> dict[str, int]:
        return dict(self.objective_weights)


def _condition(
    *,
    split: str,
    pair_id: str,
    construct: str,
    side: str,
    seed: int,
    rendering: str,
    retrieval: bool,
    doctrine: str,
    strategy: str,
    direction: str,
    targets: Sequence[str],
    forbidden: Sequence[str] = (),
    weights: Mapping[str, int],
    energy: int = 8,
    visibility: int = 8,
    minimum: int = 1,
    maximum: int = 4,
    delta: int = 2,
    cooldown: bool = False,
) -> LatentCondition:
    return LatentCondition(
        split=split,
        pair_id=pair_id,
        construct=construct,
        side=side,
        seed=seed,
        rendering=rendering,
        retrieval_required=retrieval,
        doctrine_code=doctrine,
        strategy_id=strategy,
        effect_direction=direction,
        allowed_targets=tuple(targets),
        forbidden_windows=tuple(forbidden),
        objective_weights=tuple(sorted(weights.items())),
        max_total_energy=energy,
        max_total_visibility=visibility,
        min_actions=minimum,
        max_actions=maximum,
        max_level_delta=delta,
        cooldown_same_target=cooldown,
    )


def _split_conditions(split: str) -> tuple[LatentCondition, ...]:
    if split not in SPLITS:
        raise M29SContractError(f"unknown split: {split}")
    held = split == "held_out"
    base_seed = 39201 if held else 39101
    codes = (
        ("AURORA-51", "AURORA-52"),
        ("BOREAL-53", "BOREAL-54"),
        ("CIRRUS-55", "CIRRUS-56"),
        ("DELTA-57", "DELTA-58"),
        ("EQUINOX-59", "EQUINOX-60"),
        ("FJORD-61", "FJORD-62"),
        ("GLACIER-63", "GLACIER-64"),
        ("HARBOR-65", "HARBOR-66"),
    ) if held else (
        ("ORCHID-31", "ORCHID-32"),
        ("QUARTZ-33", "QUARTZ-34"),
        ("RAVEN-35", "RAVEN-36"),
        ("SIERRA-37", "SIERRA-38"),
        ("TUNDRA-39", "TUNDRA-40"),
        ("UMBER-41", "UMBER-42"),
        ("VIOLET-43", "VIOLET-44"),
        ("YARROW-45", "YARROW-46"),
    )
    render = "held_out_relational_prose" if held else "development_operational_prose"
    offset = 1 if held else 0
    rows = (
        _condition(split=split, pair_id="doctrine_direction", construct="doctrine_direction", side="left", seed=base_seed, rendering=render, retrieval=False, doctrine=codes[0][0], strategy="persistent_pressure", direction="increase", targets=(TARGETS[offset], TARGETS[(offset + 1) % 4]), weights={"effect": 5, "persistence": 4, "energy": 1, "visibility": 2}, minimum=3),
        _condition(split=split, pair_id="doctrine_direction", construct="doctrine_direction", side="right", seed=base_seed, rendering=render, retrieval=False, doctrine=codes[0][1], strategy="delayed_shift", direction="decrease", targets=(TARGETS[offset], TARGETS[(offset + 1) % 4]), forbidden=("t0",), weights={"effect": 4, "persistence": 2, "energy": 2, "visibility": 3}, minimum=2, maximum=3, cooldown=True),
        _condition(split=split, pair_id="authority_supersession", construct="authority_supersession", side="left", seed=base_seed + 1, rendering=render, retrieval=False, doctrine=codes[1][0], strategy="resource_conserving", direction="increase", targets=(TARGETS[(offset + 2) % 4],), weights={"effect": 4, "persistence": 1, "energy": 5, "visibility": 3}, energy=5, visibility=6, maximum=2),
        _condition(split=split, pair_id="authority_supersession", construct="authority_supersession", side="right", seed=base_seed + 1, rendering=render, retrieval=False, doctrine=codes[1][1], strategy="gradual_bias", direction="decrease", targets=(TARGETS[(offset + 3) % 4],), weights={"effect": 5, "persistence": 4, "energy": 1, "visibility": 2}, minimum=3, delta=1),
        _condition(split=split, pair_id="validity_expiry", construct="validity_expiry", side="left", seed=base_seed + 2, rendering=render, retrieval=False, doctrine=codes[2][0], strategy="delayed_shift", direction="increase", targets=(TARGETS[offset], TARGETS[(offset + 2) % 4]), forbidden=("t0",), weights={"effect": 5, "persistence": 2, "energy": 1, "visibility": 2}, minimum=2, maximum=3, cooldown=True),
        _condition(split=split, pair_id="validity_expiry", construct="validity_expiry", side="right", seed=base_seed + 2, rendering=render, retrieval=False, doctrine=codes[2][1], strategy="delayed_shift", direction="increase", targets=(TARGETS[offset], TARGETS[(offset + 2) % 4]), forbidden=("t0", "t1"), weights={"effect": 5, "persistence": 2, "energy": 1, "visibility": 2}, minimum=2, maximum=2, cooldown=True),
        _condition(split=split, pair_id="topology_scope", construct="topology_scope", side="left", seed=base_seed + 3, rendering=render, retrieval=False, doctrine=codes[3][0], strategy="gradual_bias", direction="increase", targets=((TARGETS[1], TARGETS[2]) if held else (TARGETS[0], TARGETS[2])), weights={"effect": 5, "persistence": 3, "energy": 1, "visibility": 2}, minimum=3, delta=1),
        _condition(split=split, pair_id="topology_scope", construct="topology_scope", side="right", seed=base_seed + 3, rendering=render, retrieval=False, doctrine=codes[3][1], strategy="gradual_bias", direction="increase", targets=((TARGETS[0], TARGETS[3]) if held else (TARGETS[1], TARGETS[3])), weights={"effect": 5, "persistence": 3, "energy": 1, "visibility": 2}, minimum=3, delta=1),
        _condition(split=split, pair_id="resource_budget", construct="resource_budget", side="left", seed=base_seed + 4, rendering=render, retrieval=True, doctrine=codes[4][0], strategy="resource_conserving", direction="increase", targets=(TARGETS[offset], TARGETS[(offset + 3) % 4]), weights={"effect": 4, "persistence": 1, "energy": 5, "visibility": 4}, energy=5 + offset, visibility=6 + offset, maximum=2),
        _condition(split=split, pair_id="resource_budget", construct="resource_budget", side="right", seed=base_seed + 4, rendering=render, retrieval=True, doctrine=codes[4][1], strategy="resource_conserving", direction="increase", targets=(TARGETS[offset], TARGETS[(offset + 3) % 4]), weights={"effect": 4, "persistence": 1, "energy": 5, "visibility": 4}, energy=9 + offset, visibility=10 + offset, minimum=2, maximum=4),
        _condition(split=split, pair_id="objective_cooldown", construct="objective_cooldown", side="left", seed=base_seed + 5, rendering=render, retrieval=True, doctrine=codes[5][0], strategy="gradual_bias", direction="increase", targets=(TARGETS[(offset + 1) % 4], TARGETS[(offset + 2) % 4]), weights={"effect": 5, "persistence": 5, "energy": 1, "visibility": 2}, minimum=3, delta=1, cooldown=False),
        _condition(split=split, pair_id="objective_cooldown", construct="objective_cooldown", side="right", seed=base_seed + 5, rendering=render, retrieval=True, doctrine=codes[5][1], strategy="gradual_bias", direction="increase", targets=(TARGETS[(offset + 1) % 4], TARGETS[(offset + 2) % 4]), weights={"effect": 5, "persistence": 4, "energy": 1, "visibility": 3}, minimum=3, maximum=3, delta=1, cooldown=True),
        _condition(split=split, pair_id="delayed_lineage", construct="delayed_lineage", side="left", seed=base_seed + 6, rendering=render, retrieval=True, doctrine=codes[6][0], strategy="delayed_shift", direction="decrease", targets=(TARGETS[(offset + 2) % 4], TARGETS[(offset + 3) % 4]), forbidden=("t0",), weights={"effect": 5, "persistence": 2, "energy": 2, "visibility": 2}, minimum=2, maximum=3, cooldown=True),
        _condition(split=split, pair_id="delayed_lineage", construct="delayed_lineage", side="right", seed=base_seed + 6, rendering=render, retrieval=True, doctrine=codes[6][1], strategy="delayed_shift", direction="increase", targets=(TARGETS[(offset + 2) % 4], TARGETS[(offset + 3) % 4]), forbidden=("t0", "t1"), weights={"effect": 5, "persistence": 2, "energy": 2, "visibility": 2}, minimum=2, maximum=2, cooldown=True),
        _condition(split=split, pair_id="retrieval_doctrine", construct="retrieval_doctrine", side="left", seed=base_seed + 7, rendering=render, retrieval=True, doctrine=codes[7][0], strategy="persistent_pressure", direction="increase", targets=(TARGETS[(offset + 1) % 4],), weights={"effect": 4, "persistence": 5, "energy": 2, "visibility": 2}, minimum=3),
        _condition(split=split, pair_id="retrieval_doctrine", construct="retrieval_doctrine", side="right", seed=base_seed + 7, rendering=render, retrieval=True, doctrine=codes[7][1], strategy="resource_conserving", direction="decrease", targets=(TARGETS[(offset + 1) % 4],), weights={"effect": 4, "persistence": 1, "energy": 5, "visibility": 3}, energy=6 + offset, visibility=7 + offset, maximum=2),
    )
    return rows


def default_conditions(split: str | None = None) -> tuple[LatentCondition, ...]:
    """Return one split or both preregistered splits in stable order."""

    rows = _split_conditions(split) if split else sum((_split_conditions(x) for x in SPLITS), ())
    validate_condition_registration(rows, expected_splits=(split,) if split else SPLITS)
    return rows


def semantic_core(condition: LatentCondition) -> dict[str, Any]:
    return {
        "strategy_id": condition.strategy_id,
        "effect_direction": condition.effect_direction,
        "allowed_targets": list(condition.allowed_targets),
        "forbidden_windows": list(condition.forbidden_windows),
        "objective_weights": condition.weights(),
        "max_total_energy": condition.max_total_energy,
        "max_total_visibility": condition.max_total_visibility,
        "min_actions": condition.min_actions,
        "max_actions": condition.max_actions,
        "max_level_delta": condition.max_level_delta,
        "cooldown_same_target": condition.cooldown_same_target,
    }


def latent_payload(condition: LatentCondition) -> dict[str, Any]:
    return {
        "schema_version": "grideval-g7-m29s-latent-condition/v1",
        "classification": CLASSIFICATION,
        "condition_id": condition.condition_id,
        "split": condition.split,
        "pair_id": condition.pair_key,
        "construct": condition.construct,
        "side": condition.side,
        "seed": condition.seed,
        "rendering": condition.rendering,
        "retrieval_required": condition.retrieval_required,
        "doctrine_code": condition.doctrine_code,
        "semantic_program": semantic_core(condition),
        "oracle_created_before_rendering": True,
        "simulator_data_used": False,
        "final_evaluation_data_used": False,
    }


def validate_condition_registration(
    rows: Sequence[LatentCondition], *, expected_splits: Sequence[str]
) -> None:
    expected_count = 16 * len(expected_splits)
    if len(rows) != expected_count:
        raise M29SContractError(f"expected {expected_count} conditions")
    if len({row.condition_id for row in rows}) != len(rows):
        raise M29SContractError("condition IDs are not unique")
    if {row.split for row in rows} != set(expected_splits):
        raise M29SContractError("split coverage drift")
    if {row.seed for row in rows} & set(FINAL_EVALUATION_SEEDS):
        raise M29SContractError("final evaluation seed accessed")
    if any(row.side not in SIDES for row in rows):
        raise M29SContractError("invalid mirrored side")
    if any(set(row.allowed_targets) - set(TARGETS) for row in rows):
        raise M29SContractError("unknown target")
    if any(set(row.forbidden_windows) - set(WINDOWS) for row in rows):
        raise M29SContractError("unknown window")
    for split in expected_splits:
        selected = [row for row in rows if row.split == split]
        if len({row.seed for row in selected}) != 8:
            raise M29SContractError("seed coverage drift")
        if sum(row.retrieval_required for row in selected) != 8:
            raise M29SContractError("retrieval-required balance drift")
        pairs: dict[str, set[str]] = {}
        for row in selected:
            pairs.setdefault(row.pair_id, set()).add(row.side)
        if len(pairs) != 8 or any(sides != set(SIDES) for sides in pairs.values()):
            raise M29SContractError("mirrored-pair registration drift")


def validate_design_sources() -> dict[str, Any]:
    """Validate the factorial plan and strict interface schemas."""

    plan = strict_json_file(PLAN_PATH, "M29-S plan")
    schemas = {
        path.name: strict_json_file(path, path.name)
        for path in (LEDGER_SCHEMA_PATH, SLOTS_SCHEMA_PATH, PROGRAM_SCHEMA_PATH)
    }
    if plan.get("classification") != CLASSIFICATION:
        raise M29SContractError("plan classification drift")
    if plan.get("project_id") != PROJECT_ID or plan.get("mission_id") != MISSION_ID:
        raise M29SContractError("plan project or mission drift")
    if plan.get("decision_id") != DECISION_ID:
        raise M29SContractError("plan decision drift")
    arms = plan.get("arms", [])
    expected = set(FACTORIAL_ARMS + REFERENCE_ARMS + CONTROL_ARMS)
    if {row.get("arm_id") for row in arms} != expected or len(arms) != 12:
        raise M29SContractError("registered arm matrix drift")
    factor_rows = [row for row in arms if row.get("causal_factorial") is True]
    combinations = {
        (row.get("interface"), row.get("feedback"), row.get("retrieval"))
        for row in factor_rows
    }
    expected_combinations = {
        (interface, feedback, retrieval)
        for interface in ("flat", "staged")
        for feedback in ("neutral_self_revision", "validator_guided_revision")
        for retrieval in (False, True)
    }
    if combinations != expected_combinations or len(factor_rows) != 8:
        raise M29SContractError("2 x 2 x 2 factorial coverage drift")
    if any(row.get("model_calls_per_cell") != 2 for row in factor_rows):
        raise M29SContractError("factorial call parity drift")
    references = [row for row in arms if row.get("arm_id") in REFERENCE_ARMS]
    if any(row.get("model_calls_per_cell") != 1 for row in references):
        raise M29SContractError("reference call count drift")
    calls_per_split = 16 * sum(int(row.get("model_calls_per_cell", 0)) for row in arms)
    contract = plan.get("model_contract", {})
    if calls_per_split != 288 or contract.get("maximum_calls_per_split") != 288:
        raise M29SContractError("per-split call ceiling drift")
    if contract.get("maximum_additional_calls") != 576:
        raise M29SContractError("additional call ceiling drift")
    if contract.get("prior_cumulative_calls") + contract.get("maximum_additional_calls") != 677:
        raise M29SContractError("cumulative call arithmetic drift")
    if contract.get("maximum_cumulative_calls") > contract.get("pi_authorized_cumulative_ceiling"):
        raise M29SContractError("PI call authorization exceeded")
    if contract.get("retry_count") != 0:
        raise M29SContractError("retry count drift")
    for name, schema in schemas.items():
        if schema.get("additionalProperties") is not False:
            raise M29SContractError(f"{name} is not strict")
        if not str(schema.get("$schema", "")).endswith("2020-12/schema"):
            raise M29SContractError(f"{name} schema version drift")
    return {
        "plan": plan,
        "schemas": schemas,
        "source_hashes": {
            path.name: sha256_file(path)
            for path in (PLAN_PATH, LEDGER_SCHEMA_PATH, SLOTS_SCHEMA_PATH, PROGRAM_SCHEMA_PATH)
        },
    }


def _record_id(condition: LatentCondition, suffix: str) -> str:
    return f"m29s_ev_{condition.split}_{condition.pair_id}_{condition.side}_{suffix}"


def _semantic_sentence(condition: LatentCondition) -> str:
    weights = condition.weights()
    return (
        f"Doctrine {condition.doctrine_code}: Strategy={condition.strategy_id}; "
        f"Direction={condition.effect_direction}; "
        f"Weights=effect:{weights['effect']},persistence:{weights['persistence']},"
        f"energy:{weights['energy']},visibility:{weights['visibility']}; "
        f"Delta={condition.max_level_delta}; "
        f"Cooldown={str(condition.cooldown_same_target).lower()}."
    )


def build_visible_records(condition: LatentCondition) -> list[dict[str, Any]]:
    """Render visible evidence without exposing latent or oracle fields."""

    archive_id = _record_id(condition, "archive")
    expired_id = _record_id(condition, "expired")
    directive_id = _record_id(condition, "directive")
    topology_id = _record_id(condition, "topology")
    constraint_id = _record_id(condition, "constraints")
    semantic_text = (
        f"Active directive selects doctrine {condition.doctrine_code}. "
        "Resolve its semantic fields from the authoritative doctrine corpus."
        if condition.retrieval_required
        else _semantic_sentence(condition)
    )
    forbidden = ",".join(condition.forbidden_windows) or "none"
    records = [
        {
            "record_id": archive_id,
            "record_type": "doctrine",
            "authority": "advisory",
            "issued_order": 1,
            "valid_from": "t0",
            "valid_until": "t3",
            "status": "superseded",
            "supersedes": [],
            "text": "Archived guidance proposes an incompatible semantic program and has no current authority.",
        },
        {
            "record_id": expired_id,
            "record_type": "doctrine",
            "authority": "planning",
            "issued_order": 2,
            "valid_from": "t0",
            "valid_until": "t1",
            "status": "expired",
            "supersedes": [archive_id],
            "text": "An older planning instruction expired before the current compilation window.",
        },
        {
            "record_id": directive_id,
            "record_type": "doctrine",
            "authority": "emergency" if condition.side == "right" else "operator",
            "issued_order": 5,
            "valid_from": "t0",
            "valid_until": "t3",
            "status": "active",
            "supersedes": [archive_id, expired_id],
            "text": semantic_text,
        },
        {
            "record_id": topology_id,
            "record_type": "topology",
            "authority": "operator",
            "issued_order": 4,
            "valid_from": "t0",
            "valid_until": "t3",
            "status": "active",
            "supersedes": [],
            "text": (
                f"Active scope targets={','.join(condition.allowed_targets)}; "
                f"forbidden_windows={forbidden}."
            ),
        },
        {
            "record_id": constraint_id,
            "record_type": "constraints",
            "authority": "operator",
            "issued_order": 4,
            "valid_from": "t0",
            "valid_until": "t3",
            "status": "active",
            "supersedes": [],
            "text": (
                f"Limits energy={condition.max_total_energy}; "
                f"visibility={condition.max_total_visibility}; "
                f"actions={condition.min_actions}..{condition.max_actions}."
            ),
        },
    ]
    if condition.rendering == "held_out_relational_prose":
        records = [records[1], records[3], records[0], records[4], records[2]]
    return records


def build_corpus(conditions: Sequence[LatentCondition] | None = None) -> dict[str, Any]:
    selected = tuple(conditions or default_conditions())
    passages = [
        {
            "passage_id": row.doctrine_passage_id,
            "doctrine_code": row.doctrine_code,
            "text": _semantic_sentence(row),
            "authority": "authoritative",
            "tags": [row.strategy_id, row.effect_direction, row.split],
        }
        for row in selected
    ]
    for index in range(16):
        passages.append(
            {
                "passage_id": f"m29s_doc_DISTRACTOR_{index + 1:02d}",
                "doctrine_code": f"DISTRACTOR-{index + 1:02d}",
                "text": "Archived cross-domain example; it is not authoritative for any M29-S condition.",
                "authority": "archived",
                "tags": ["distractor", "archived"],
            }
        )
    body = {
        "schema_version": "grideval-g7-m29s-corpus/v1",
        "classification": CLASSIFICATION,
        "passages": passages,
    }
    return {"corpus_id": content_id("m29scorpus", body), **body}


def build_query_manifest(
    conditions: Sequence[LatentCondition] | None = None,
    corpus: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected = tuple(conditions or default_conditions())
    corpus_value = corpus or build_corpus(selected)
    passage_ids = [row["passage_id"] for row in corpus_value["passages"]]
    distractors = [value for value in passage_ids if "DISTRACTOR" in value]
    queries: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        flat_ids = distractors[index % len(distractors):] + distractors[:index % len(distractors)]
        flat_ids = flat_ids[:4]
        if row.retrieval_required and row.side == "left":
            flat_ids = [row.doctrine_passage_id, *flat_ids[:3]]
        queries.append(
            {
                "query_id": f"m29s_query_{row.condition_id}",
                "condition_id": row.condition_id,
                "split": row.split,
                "retrieval_required": row.retrieval_required,
                "query": f"authoritative doctrine {row.doctrine_code} semantic fields",
                "expected_passage_id": row.doctrine_passage_id,
                "flat_passage_ids": flat_ids,
            }
        )
    body = {
        "schema_version": "grideval-g7-m29s-query-manifest/v1",
        "classification": CLASSIFICATION,
        "top_k": 4,
        "similarity": "cosine",
        "tie_break": "passage_id_ascending",
        "queries": queries,
    }
    return {"query_manifest_id": content_id("m29squeries", body), **body}


def build_visible_bundle(condition: LatentCondition) -> dict[str, Any]:
    records = build_visible_records(condition)
    body = {
        "schema_version": "grideval-g7-m29s-visible-evidence/v1",
        "classification": CLASSIFICATION,
        "condition_id": condition.condition_id,
        "split": condition.split,
        "pair_id": condition.pair_key,
        "side": condition.side,
        "seed": condition.seed,
        "retrieval_required": condition.retrieval_required,
        "current_window": "t3",
        "records": records,
        "query_id": f"m29s_query_{condition.condition_id}",
    }
    return {"visible_evidence_id": content_id("m29sevidence", body), **body}


def visible_input(
    bundle: Mapping[str, Any], passages: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "visible_evidence": canonical_copy(bundle),
        "corpus_passages": canonical_copy(list(passages)),
    }


def visible_input_digest(
    bundle: Mapping[str, Any], passages: Sequence[Mapping[str, Any]]
) -> str:
    return sha256_value(visible_input(bundle, passages))


def corpus_passages_by_id(corpus: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["passage_id"]: dict(row) for row in corpus["passages"]}


def flat_corpus_view(
    condition: LatentCondition,
    corpus: Mapping[str, Any],
    queries: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query = next(row for row in queries["queries"] if row["condition_id"] == condition.condition_id)
    by_id = corpus_passages_by_id(corpus)
    return [by_id[value] for value in query["flat_passage_ids"]]


def oracle_retrieval_view(
    condition: LatentCondition,
    corpus: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return a deterministic test view; live retrieval must use embeddings."""

    by_id = corpus_passages_by_id(corpus)
    expected = by_id[condition.doctrine_passage_id]
    distractors = [row for row in corpus["passages"] if "DISTRACTOR" in row["passage_id"]]
    return [expected, *distractors[:3]]


def build_oracle_ledger(
    bundle: Mapping[str, Any], passages: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    active = [row["record_id"] for row in bundle["records"] if row["status"] == "active"]
    superseded = [row["record_id"] for row in bundle["records"] if row["status"] == "superseded"]
    expired = [row["record_id"] for row in bundle["records"] if row["status"] == "expired"]
    return {
        "schema_version": "grideval-g7-m29s-evidence-ledger/v1",
        "condition_id": bundle["condition_id"],
        "active_evidence_ids": sorted(active),
        "superseded_evidence_ids": sorted(superseded),
        "expired_evidence_ids": sorted(expired),
        "unresolved_conflict_ids": [],
        "authority_order": list(AUTHORITY_ORDER),
        "visible_input_digest": visible_input_digest(bundle, passages),
    }


def _support_map(condition: LatentCondition) -> dict[str, list[str]]:
    doctrine_support = (
        condition.doctrine_passage_id
        if condition.retrieval_required
        else _record_id(condition, "directive")
    )
    topology = _record_id(condition, "topology")
    constraints = _record_id(condition, "constraints")
    return {
        "strategy_id": [doctrine_support],
        "effect_direction": [doctrine_support],
        "allowed_targets": [topology],
        "forbidden_windows": [topology],
        "objective_weights": [doctrine_support],
        "max_total_energy": [constraints],
        "max_total_visibility": [constraints],
        "min_actions": [constraints],
        "max_actions": [constraints],
        "max_level_delta": [doctrine_support],
        "cooldown_same_target": [doctrine_support],
    }


def build_oracle_slots(
    condition: LatentCondition,
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    values = semantic_core(condition)
    supports = _support_map(condition)
    return {
        "schema_version": "grideval-g7-m29s-semantic-slots/v1",
        "condition_id": condition.condition_id,
        "slots": {
            key: {
                "value": canonical_copy(values[key]),
                "supporting_evidence_ids": list(supports[key]),
            }
            for key in SLOT_KEYS
        },
        "visible_input_digest": visible_input_digest(bundle, passages),
    }


def project_slots_to_program(
    slots: Mapping[str, Any], *, compiler_id: str
) -> dict[str, Any]:
    """Project submitted slot values without correcting their semantics."""

    slot_rows = slots.get("slots", {})
    if set(slot_rows) != set(SLOT_KEYS):
        raise M29SContractError("semantic slot coverage drift")
    values = {key: canonical_copy(slot_rows[key]["value"]) for key in SLOT_KEYS}
    values["allowed_targets"] = sorted(values["allowed_targets"])
    values["forbidden_windows"] = sorted(values["forbidden_windows"])
    evidence_ids = sorted(
        {
            value
            for key in SLOT_KEYS
            for value in slot_rows[key]["supporting_evidence_ids"]
        }
    )
    return {
        "schema_version": "grideval-g7-m29s-strategy-program/v1",
        "condition_id": slots["condition_id"],
        **values,
        "required_evidence_ids": evidence_ids,
        "visible_input_digest": slots["visible_input_digest"],
        "compiler_id": compiler_id,
    }


def build_oracle_program(
    condition: LatentCondition,
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    slots = build_oracle_slots(condition, bundle, passages)
    return project_slots_to_program(slots, compiler_id="independent_latent_oracle_v1")


def validate_evidence_ledger(
    ledger: Mapping[str, Any],
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> None:
    expected_keys = {
        "schema_version", "condition_id", "active_evidence_ids",
        "superseded_evidence_ids", "expired_evidence_ids",
        "unresolved_conflict_ids", "authority_order", "visible_input_digest",
    }
    _require_exact_keys(ledger, expected_keys, "EvidenceLedger")
    if ledger["schema_version"] != "grideval-g7-m29s-evidence-ledger/v1":
        raise M29SContractError("EvidenceLedger schema drift")
    if ledger["condition_id"] != bundle["condition_id"]:
        raise M29SContractError("EvidenceLedger condition drift")
    if ledger["visible_input_digest"] != visible_input_digest(bundle, passages):
        raise M29SContractError("EvidenceLedger input lineage drift")
    record_ids = {row["record_id"] for row in bundle["records"]}
    for key in (
        "active_evidence_ids", "superseded_evidence_ids",
        "expired_evidence_ids", "unresolved_conflict_ids",
    ):
        values = ledger[key]
        if not isinstance(values, list) or len(values) != len(set(values)):
            raise M29SContractError(f"invalid EvidenceLedger field: {key}")
        if set(values) - record_ids:
            raise M29SContractError("EvidenceLedger references unknown evidence")
    if ledger["authority_order"] != list(AUTHORITY_ORDER):
        raise M29SContractError("EvidenceLedger authority order drift")


def _visible_ids(
    bundle: Mapping[str, Any], passages: Sequence[Mapping[str, Any]]
) -> set[str]:
    return {row["record_id"] for row in bundle["records"]} | {
        row["passage_id"] for row in passages
    }


def validate_semantic_slots(
    slots: Mapping[str, Any],
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> None:
    _require_exact_keys(
        slots,
        {"schema_version", "condition_id", "slots", "visible_input_digest"},
        "SemanticSlots",
    )
    if slots["schema_version"] != "grideval-g7-m29s-semantic-slots/v1":
        raise M29SContractError("SemanticSlots schema drift")
    if slots["condition_id"] != bundle["condition_id"]:
        raise M29SContractError("SemanticSlots condition drift")
    if slots["visible_input_digest"] != visible_input_digest(bundle, passages):
        raise M29SContractError("SemanticSlots input lineage drift")
    if set(slots["slots"]) != set(SLOT_KEYS):
        raise M29SContractError("SemanticSlots field coverage drift")
    visible_ids = _visible_ids(bundle, passages)
    for key in SLOT_KEYS:
        row = slots["slots"][key]
        _require_exact_keys(row, {"value", "supporting_evidence_ids"}, f"slot {key}")
        support = row["supporting_evidence_ids"]
        if not isinstance(support, list) or not support or len(support) != len(set(support)):
            raise M29SContractError(f"invalid support list for slot {key}")
        if set(support) - visible_ids:
            raise M29SContractError(f"unknown evidence for slot {key}")


def validate_strategy_program(
    program: Mapping[str, Any],
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> None:
    expected_keys = {
        "schema_version", "condition_id", *SLOT_KEYS,
        "required_evidence_ids", "visible_input_digest", "compiler_id",
    }
    _require_exact_keys(program, expected_keys, "StrategyProgram")
    if program["schema_version"] != "grideval-g7-m29s-strategy-program/v1":
        raise M29SContractError("StrategyProgram schema drift")
    if program["condition_id"] != bundle["condition_id"]:
        raise M29SContractError("StrategyProgram condition drift")
    if program["visible_input_digest"] != visible_input_digest(bundle, passages):
        raise M29SContractError("StrategyProgram input lineage drift")
    if program["strategy_id"] not in STRATEGIES:
        raise M29SContractError("invalid strategy ID")
    if program["effect_direction"] not in {"increase", "decrease"}:
        raise M29SContractError("invalid effect direction")
    targets = program["allowed_targets"]
    windows = program["forbidden_windows"]
    if not isinstance(targets, list) or not targets or set(targets) - set(TARGETS) or len(targets) != len(set(targets)):
        raise M29SContractError("invalid target set")
    if not isinstance(windows, list) or set(windows) - set(WINDOWS) or len(windows) != len(set(windows)):
        raise M29SContractError("invalid forbidden windows")
    weights = program["objective_weights"]
    if not isinstance(weights, Mapping) or set(weights) != set(WEIGHT_KEYS):
        raise M29SContractError("invalid objective weights")
    if any(type(value) is not int or not 0 <= value <= 10 for value in weights.values()):
        raise M29SContractError("invalid objective weight value")
    for key, maximum in (
        ("max_total_energy", 20), ("max_total_visibility", 20),
        ("min_actions", 4), ("max_actions", 4), ("max_level_delta", 4),
    ):
        value = program[key]
        if type(value) is not int or not 0 <= value <= maximum:
            raise M29SContractError(f"invalid {key}")
    if program["min_actions"] > program["max_actions"]:
        raise M29SContractError("minimum actions exceeds maximum")
    if type(program["cooldown_same_target"]) is not bool:
        raise M29SContractError("invalid cooldown flag")
    evidence = program["required_evidence_ids"]
    if not isinstance(evidence, list) or not evidence or len(evidence) != len(set(evidence)):
        raise M29SContractError("invalid required evidence")
    if set(evidence) - _visible_ids(bundle, passages):
        raise M29SContractError("program references unknown evidence")
    if not isinstance(program["compiler_id"], str) or not program["compiler_id"]:
        raise M29SContractError("invalid compiler ID")


def program_semantics(program: Mapping[str, Any]) -> dict[str, Any]:
    return {key: canonical_copy(program[key]) for key in SLOT_KEYS}


def programs_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_core = program_semantics(left)
    right_core = program_semantics(right)
    left_core["allowed_targets"] = sorted(left_core["allowed_targets"])
    right_core["allowed_targets"] = sorted(right_core["allowed_targets"])
    left_core["forbidden_windows"] = sorted(left_core["forbidden_windows"])
    right_core["forbidden_windows"] = sorted(right_core["forbidden_windows"])
    return canonical_json(left_core) == canonical_json(right_core)


def _find(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text)
    if not match:
        raise M29SContractError(f"deterministic compiler missing {label}")
    return match.group(1)


def strong_deterministic_compile(
    condition: LatentCondition,
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Compile only the registered controlled grammar in visible bytes."""

    doctrine_record = next(
        row for row in bundle["records"]
        if row["record_type"] == "doctrine" and row["status"] == "active"
    )
    semantic_text = doctrine_record["text"]
    if "Strategy=" not in semantic_text:
        matching = [
            row for row in passages
            if row.get("doctrine_code") == condition.doctrine_code
            and row.get("authority") == "authoritative"
        ]
        if len(matching) != 1:
            return None
        semantic_text = matching[0]["text"]
        doctrine_support = matching[0]["passage_id"]
    else:
        doctrine_support = doctrine_record["record_id"]
    topology = next(row for row in bundle["records"] if row["record_type"] == "topology" and row["status"] == "active")
    constraints = next(row for row in bundle["records"] if row["record_type"] == "constraints" and row["status"] == "active")
    try:
        weight_text = _find(r"Weights=([^;]+)", semantic_text, "weights")
        weights = {
            key: int(value)
            for key, value in (part.split(":", 1) for part in weight_text.split(","))
        }
        target_text = _find(r"targets=([^;]+)", topology["text"], "targets")
        forbidden_text = _find(r"forbidden_windows=([^\.]+)", topology["text"], "windows")
        limits = re.search(r"Limits energy=(\d+); visibility=(\d+); actions=(\d+)\.\.(\d+)\.", constraints["text"])
        if not limits:
            raise M29SContractError("deterministic compiler missing limits")
        values: dict[str, Any] = {
            "strategy_id": _find(r"Strategy=([a-z_]+)", semantic_text, "strategy"),
            "effect_direction": _find(r"Direction=([a-z]+)", semantic_text, "direction"),
            "allowed_targets": target_text.split(","),
            "forbidden_windows": [] if forbidden_text == "none" else forbidden_text.split(","),
            "objective_weights": weights,
            "max_total_energy": int(limits.group(1)),
            "max_total_visibility": int(limits.group(2)),
            "min_actions": int(limits.group(3)),
            "max_actions": int(limits.group(4)),
            "max_level_delta": int(_find(r"Delta=(\d+)", semantic_text, "delta")),
            "cooldown_same_target": _find(r"Cooldown=(true|false)", semantic_text, "cooldown") == "true",
        }
    except (M29SContractError, TypeError, ValueError):
        return None
    supports = {
        "strategy_id": [doctrine_support],
        "effect_direction": [doctrine_support],
        "allowed_targets": [topology["record_id"]],
        "forbidden_windows": [topology["record_id"]],
        "objective_weights": [doctrine_support],
        "max_total_energy": [constraints["record_id"]],
        "max_total_visibility": [constraints["record_id"]],
        "min_actions": [constraints["record_id"]],
        "max_actions": [constraints["record_id"]],
        "max_level_delta": [doctrine_support],
        "cooldown_same_target": [doctrine_support],
    }
    slots = {
        "schema_version": "grideval-g7-m29s-semantic-slots/v1",
        "condition_id": condition.condition_id,
        "slots": {
            key: {"value": values[key], "supporting_evidence_ids": supports[key]}
            for key in SLOT_KEYS
        },
        "visible_input_digest": visible_input_digest(bundle, passages),
    }
    try:
        validate_semantic_slots(slots, bundle, passages)
        program = project_slots_to_program(slots, compiler_id="strong_visible_parser_v1")
        validate_strategy_program(program, bundle, passages)
    except M29SContractError:
        return None
    return {
        "evidence_ledger": build_oracle_ledger(bundle, passages),
        "semantic_slots": slots,
        "strategy_program": program,
    }


def _extract_program(draft: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if "strategy_program" in draft and isinstance(draft["strategy_program"], Mapping):
        return draft["strategy_program"]
    if "schema_version" in draft and draft.get("schema_version") == "grideval-g7-m29s-strategy-program/v1":
        return draft
    return None


def validate_strategy_draft(
    condition: LatentCondition,
    draft: Mapping[str, Any],
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return value-free diagnostics derived only from visible evidence."""

    diagnostics: list[dict[str, str]] = []
    program = _extract_program(draft)
    if program is None:
        diagnostics.append({"code": "schema", "slot": "strategy_program"})
    else:
        try:
            validate_strategy_program(program, bundle, passages)
        except M29SContractError as exc:
            message = str(exc)
            if "unknown evidence" in message:
                diagnostics.append({"code": "evidence_unknown", "slot": "required_evidence_ids"})
            elif "evidence" in message or "lineage" in message:
                diagnostics.append({"code": "evidence_missing", "slot": "required_evidence_ids"})
            else:
                diagnostics.append({"code": "schema", "slot": "strategy_program"})
        visible_expected = strong_deterministic_compile(condition, bundle, passages)
        if visible_expected is not None:
            expected = visible_expected["strategy_program"]
            code_by_slot = {
                "strategy_id": "authority_conflict",
                "effect_direction": "authority_conflict",
                "allowed_targets": "topology_inconsistent",
                "forbidden_windows": "expired_record",
                "objective_weights": "weights_inconsistent",
                "max_total_energy": "budget_inconsistent",
                "max_total_visibility": "budget_inconsistent",
                "min_actions": "budget_inconsistent",
                "max_actions": "budget_inconsistent",
                "max_level_delta": "cooldown_inconsistent",
                "cooldown_same_target": "cooldown_inconsistent",
            }
            for slot in SLOT_KEYS:
                if slot not in program or canonical_json(program[slot]) != canonical_json(expected[slot]):
                    diagnostics.append({"code": code_by_slot[slot], "slot": slot})
            required = set(expected["required_evidence_ids"])
            provided = set(program.get("required_evidence_ids", []))
            if not required.issubset(provided):
                diagnostics.append({"code": "evidence_missing", "slot": "required_evidence_ids"})
    unique = sorted(
        {(row["code"], row["slot"]) for row in diagnostics},
        key=lambda value: (value[1], value[0]),
    )
    body = {
        "schema_version": "grideval-g7-m29s-validator-diagnostics/v1",
        "draft_id": content_id("m29sdraft", canonical_copy(draft)),
        "visible_input_digest": visible_input_digest(bundle, passages),
        "diagnostics": [{"code": code, "slot": slot} for code, slot in unique],
    }
    validate_diagnostics(body)
    return body


def validate_diagnostics(payload: Mapping[str, Any]) -> None:
    _require_exact_keys(
        payload,
        {"schema_version", "draft_id", "visible_input_digest", "diagnostics"},
        "ValidatorDiagnostics",
    )
    if payload["schema_version"] != "grideval-g7-m29s-validator-diagnostics/v1":
        raise M29SContractError("diagnostic schema drift")
    if not re.fullmatch(r"m29sdraft_[0-9a-f]{64}", payload["draft_id"]):
        raise M29SContractError("diagnostic draft lineage drift")
    if not re.fullmatch(r"[0-9a-f]{64}", payload["visible_input_digest"]):
        raise M29SContractError("diagnostic visible-input lineage drift")
    for row in payload["diagnostics"]:
        _require_exact_keys(row, {"code", "slot"}, "diagnostic row")
        if row["code"] not in VALIDATOR_CODES:
            raise M29SContractError("unknown diagnostic code")
        if row["slot"] not in set(SLOT_KEYS) | {"strategy_program", "required_evidence_ids"}:
            raise M29SContractError("unknown diagnostic slot")


def neutral_self_revision_message() -> str:
    return (
        "Review the initial draft using only the original visible input. "
        "Return the final response in the same registered schema. Treat all "
        "fields as unverified and do not add external facts."
    )


def provider_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Remove only provider-unsupported uniqueness annotations recursively."""

    if isinstance(schema, Mapping):
        return {
            key: provider_schema(value)
            for key, value in schema.items()
            if key not in {"$schema", "$id", "uniqueItems"}
        }
    if isinstance(schema, list):
        return [provider_schema(value) for value in schema]
    return copy.deepcopy(schema)


def response_schema(
    *,
    interface: str,
    condition_id: str,
    input_digest: str,
    compiler_id: str,
) -> dict[str, Any]:
    program = canonical_copy(strict_json_file(PROGRAM_SCHEMA_PATH, "program schema"))
    program["properties"]["condition_id"] = {"const": condition_id}
    program["properties"]["visible_input_digest"] = {"const": input_digest}
    program["properties"]["compiler_id"] = {"const": compiler_id}
    if interface == "flat":
        return provider_schema(program)
    if interface != "staged":
        raise M29SContractError(f"unknown interface: {interface}")
    ledger = canonical_copy(strict_json_file(LEDGER_SCHEMA_PATH, "ledger schema"))
    slots = canonical_copy(strict_json_file(SLOTS_SCHEMA_PATH, "slots schema"))
    for item in (ledger, slots):
        item["properties"]["condition_id"] = {"const": condition_id}
        item["properties"]["visible_input_digest"] = {"const": input_digest}
    return provider_schema({
        "type": "object",
        "additionalProperties": False,
        "required": ["evidence_ledger", "semantic_slots", "strategy_program"],
        "properties": {
            "evidence_ledger": ledger,
            "semantic_slots": slots,
            "strategy_program": program,
        },
    })


def arm_spec(arm_id: str) -> dict[str, Any]:
    plan = validate_design_sources()["plan"]
    try:
        return next(row for row in plan["arms"] if row["arm_id"] == arm_id)
    except StopIteration as exc:
        raise M29SContractError(f"unknown arm: {arm_id}") from exc


def build_initial_model_request(
    *,
    arm_id: str,
    condition: LatentCondition,
    bundle: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    spec = arm_spec(arm_id)
    if int(spec["model_calls_per_cell"]) == 0:
        raise M29SContractError("deterministic arm has no model request")
    interface = spec["interface"]
    digest = visible_input_digest(bundle, passages)
    compiler_id = f"qwen_m29s_{arm_id.lower().replace('-', '_')}"
    schema = response_schema(
        interface=interface,
        condition_id=condition.condition_id,
        input_digest=digest,
        compiler_id=compiler_id,
    )
    interface_instruction = (
        "Return only the final StrategyProgram JSON."
        if interface == "flat"
        else "Return EvidenceLedger, SemanticSlots with per-slot supporting evidence IDs, and a StrategyProgram that exactly projects those slot values."
    )
    seed_bytes = hashlib.sha256(f"{arm_id}:{condition.condition_id}:initial".encode("utf-8")).digest()
    seed = int.from_bytes(seed_bytes[:4], "big") & 0x7FFFFFFF
    return {
        "model": "qwen3.6-35b-a3b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You compile visible grid red-team evidence into a typed offline strategy program. "
                    "Use only supplied records and corpus passages. Resolve status, authority, validity, scope, budgets, and evidence lineage exactly. "
                    + interface_instruction
                ),
            },
            {"role": "user", "content": canonical_json(visible_input(bundle, passages))},
        ],
        "temperature": 0,
        "seed": seed,
        "max_tokens": 900,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": f"m29s_{interface}_response",
                "strict": True,
                "schema": schema,
            },
        },
    }


def slot_accuracy(
    program: Mapping[str, Any] | None,
    oracle: Mapping[str, Any],
) -> dict[str, bool]:
    if program is None:
        return {key: False for key in SLOT_KEYS}
    return {
        key: canonical_json(program.get(key)) == canonical_json(oracle[key])
        for key in SLOT_KEYS
    }


def build_design_fixture() -> dict[str, Any]:
    """Build the complete offline design fixture with sealed oracle fields."""

    sources = validate_design_sources()
    conditions = default_conditions()
    corpus = build_corpus(conditions)
    queries = build_query_manifest(conditions, corpus)
    rows: list[dict[str, Any]] = []
    for condition in conditions:
        bundle = build_visible_bundle(condition)
        flat = flat_corpus_view(condition, corpus, queries)
        retrieval = oracle_retrieval_view(condition, corpus)
        oracle_passages = retrieval if condition.retrieval_required else flat
        oracle_slots = build_oracle_slots(condition, bundle, oracle_passages)
        rows.append({
            "condition_id": condition.condition_id,
            "split": condition.split,
            "pair_id": condition.pair_key,
            "construct": condition.construct,
            "side": condition.side,
            "latent_condition": latent_payload(condition),
            "visible_evidence": bundle,
            "flat_passage_ids": [row["passage_id"] for row in flat],
            "oracle_retrieval_passage_ids": [row["passage_id"] for row in retrieval],
            "independent_oracle": {
                "evidence_ledger": build_oracle_ledger(bundle, oracle_passages),
                "semantic_slots": oracle_slots,
                "strategy_program": project_slots_to_program(
                    oracle_slots, compiler_id="independent_latent_oracle_v1"
                ),
                "tested_model_called": False,
                "validator_called": False,
            },
        })
    body = {
        "schema_version": "grideval-g7-m29s-design-fixture/v1",
        "classification": CLASSIFICATION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "conditions_per_split": 16,
        "condition_count": 32,
        "corpus": corpus,
        "query_manifest": queries,
        "conditions": rows,
        "source_hashes": sources["source_hashes"],
        "call_budget": {
            "calls_per_split": 288,
            "maximum_additional_calls": 576,
            "prior_cumulative_calls": 101,
            "maximum_cumulative_calls": 677,
            "pi_authorized_ceiling": 1000,
            "retry_count": 0,
        },
        "access_boundary": {
            "llm_accessed": False,
            "embedding_accessed": False,
            "embedding_service_started_or_restarted": False,
            "docker_accessed": False,
            "simulator_accessed": False,
            "detector_accessed": False,
            "defense_accessed": False,
            "network_impairment_accessed": False,
            "physical_actuator_accessed": False,
            "final_evaluation_accessed": False,
            "final_evaluation_seeds_accessed": [],
            "rka_governance_attacker_view_accessed": False,
        },
        "m29b_authorized": False,
        "claim_boundary": sources["plan"]["claim_boundary"],
    }
    return {"design_fixture_id": content_id("m29sfixture", body), **body}


def verify_m29r_disjointness(
    fixture: Mapping[str, Any],
    m29r_fixture_path: Path = M29R_FIXTURE_PATH,
) -> list[str]:
    """Return named overlap failures against the immutable M29-R fixture."""

    issues: list[str] = []
    prior = strict_json_file(m29r_fixture_path, "M29-R design fixture")
    prior_rows = prior["conditions"]
    current_rows = fixture["conditions"]
    prior_ids = {row["condition_id"] for row in prior_rows}
    current_ids = {row["condition_id"] for row in current_rows}
    if prior_ids & current_ids:
        issues.append("condition_id_overlap")
    prior_seeds = {row["latent_scenario"]["development_seed"] for row in prior_rows}
    current_seeds = {row["latent_condition"]["seed"] for row in current_rows}
    if prior_seeds & current_seeds:
        issues.append("seed_overlap")
    prior_digests = {row["evidence_bundle"]["semantic_meaning_digest"] for row in prior_rows}
    current_digests = {sha256_value(row["latent_condition"]["semantic_program"]) for row in current_rows}
    if prior_digests & current_digests:
        issues.append("semantic_digest_overlap")
    prior_bytes = {canonical_json(row["evidence_bundle"]["semantic_records"]) for row in prior_rows}
    current_bytes = {canonical_json(row["visible_evidence"]["records"]) for row in current_rows}
    if prior_bytes & current_bytes:
        issues.append("rendered_evidence_overlap")
    prior_doctrines = {row["latent_scenario"]["doctrine_code"] for row in prior_rows}
    current_doctrines = {row["latent_condition"]["doctrine_code"] for row in current_rows}
    if prior_doctrines & current_doctrines:
        issues.append("doctrine_identifier_overlap")
    return issues


def create_once_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite create-once artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = build_design_fixture()
    issues = verify_m29r_disjointness(fixture)
    if issues:
        raise M29SContractError(f"M29-R disjointness failed: {issues}")
    create_once_json(args.output, fixture)
    print(json.dumps({
        "status": "created",
        "output": str(args.output),
        "design_fixture_id": fixture["design_fixture_id"],
        "condition_count": fixture["condition_count"],
        "model_calls": 0,
        "embedding_calls": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
