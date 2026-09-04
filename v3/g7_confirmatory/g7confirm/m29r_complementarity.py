"""Offline construct-validity primitives for the M29-R complementarity study.

This module has no network, simulator, detector, defense, Docker, or actuator
client. It creates latent development fixtures, typed semantic programs, exact
offline plans, and content-addressed evidence for later bounded execution.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "m29r_complementarity_plan.json"
CORPUS_PATH = ROOT / "m29r_strategy_corpus.json"
QUERY_PATH = ROOT / "m29r_retrieval_queries.json"

CLASSIFICATION = "PRELIMINARY_ONLY"
WINDOWS = ("w0", "w1", "w2", "w3")
TARGETS = ("DER_A", "DER_B", "DER_C")
LEVELS = (-2, -1, 1, 2)
FINAL_EVALUATION_SEEDS = tuple(range(9101, 9113))

STRATEGY_KEYS = {
    "schema_version",
    "condition_id",
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
    "required_evidence_ids",
    "lineage",
}

WEIGHT_KEYS = {"effect", "persistence", "energy", "visibility"}


class M29RContractError(ValueError):
    """Raised when an M29-R design or typed-boundary invariant is violated."""


def canonical_json(value: Any) -> str:
    """Return strict RFC-style canonical JSON for hashing and parity checks."""

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
                raise M29RContractError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise M29RContractError(f"non-finite JSON value in {label}: {value}")

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
        raise M29RContractError(
            f"{label} keys differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def validate_design_sources() -> dict[str, Any]:
    """Validate static M29-R plan, corpus, and query-manifest invariants."""

    plan = strict_json_file(PLAN_PATH, "M29-R plan")
    corpus = strict_json_file(CORPUS_PATH, "M29-R corpus")
    queries = strict_json_file(QUERY_PATH, "M29-R query manifest")

    if plan.get("classification") != CLASSIFICATION:
        raise M29RContractError("plan classification drift")
    arms = plan.get("arms", [])
    expected_arms = {"IA3-O", "IA3-SO", "IA4-D", "IA4-H", "IA4-HR", "IA5-OC"}
    if {row.get("arm_id") for row in arms} != expected_arms:
        raise M29RContractError("six-arm registration drift")
    design = plan.get("counterfactual_design", {})
    if design.get("condition_count") != 16 or design.get("pair_count") != 8:
        raise M29RContractError("counterfactual count drift")
    seeds = design.get("development_seeds")
    if seeds != list(range(29001, 29009)):
        raise M29RContractError("development seed registration drift")
    if set(seeds) & set(FINAL_EVALUATION_SEEDS):
        raise M29RContractError("final evaluation seed accessed")

    corpus_payload = dict(corpus)
    corpus_identifier = corpus_payload.pop("corpus_id", None)
    if corpus_identifier != content_id("m29rcorpus", corpus_payload):
        raise M29RContractError("corpus content address drift")
    passages = corpus.get("passages", [])
    if len(passages) != 24:
        raise M29RContractError("corpus must contain exactly 24 passages")
    passage_ids = [row.get("passage_id") for row in passages]
    if len(set(passage_ids)) != len(passage_ids):
        raise M29RContractError("duplicate corpus passage ID")

    query_payload = dict(queries)
    query_identifier = query_payload.pop("query_manifest_id", None)
    if query_identifier != content_id("m29rqueries", query_payload):
        raise M29RContractError("query manifest content address drift")
    query_rows = queries.get("queries", [])
    if len(query_rows) != 16:
        raise M29RContractError("query manifest must contain 16 rows")
    if sum(row.get("retrieval_required") is True for row in query_rows) != 8:
        raise M29RContractError("retrieval-required condition count drift")
    available = set(passage_ids)
    for row in query_rows:
        if not set(row.get("flat_excerpt_passage_ids", [])).issubset(available):
            raise M29RContractError("flat excerpt references an unknown passage")
        expected = row.get("expected_passage_id")
        if expected is not None and expected not in available:
            raise M29RContractError("query expected passage is unknown")

    return {
        "plan": plan,
        "corpus": corpus,
        "queries": queries,
        "source_hashes": {
            PLAN_PATH.name: sha256_file(PLAN_PATH),
            CORPUS_PATH.name: sha256_file(CORPUS_PATH),
            QUERY_PATH.name: sha256_file(QUERY_PATH),
        },
    }


@dataclass(frozen=True)
class LatentScenario:
    pair_id: str
    intervention_class: str
    side: str
    development_seed: int
    active_rendering: str
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
        return f"m29r_{self.pair_id}_{self.side}"

    @property
    def query_id(self) -> str:
        return f"m29r_query_{self.pair_id}_{self.side}"

    def weights(self) -> dict[str, int]:
        return dict(self.objective_weights)


def _scenario(
    *,
    pair_id: str,
    intervention_class: str,
    side: str,
    seed: int,
    rendering: str,
    retrieval: bool,
    doctrine: str,
    strategy: str,
    direction: str,
    allowed: Sequence[str],
    forbidden: Sequence[str] = (),
    weights: Mapping[str, int],
    energy: int = 8,
    visibility: int = 8,
    min_actions: int = 1,
    max_actions: int = 4,
    delta: int = 2,
    cooldown: bool = False,
) -> LatentScenario:
    return LatentScenario(
        pair_id=pair_id,
        intervention_class=intervention_class,
        side=side,
        development_seed=seed,
        active_rendering=rendering,
        retrieval_required=retrieval,
        doctrine_code=doctrine,
        strategy_id=strategy,
        effect_direction=direction,
        allowed_targets=tuple(allowed),
        forbidden_windows=tuple(forbidden),
        objective_weights=tuple(sorted(weights.items())),
        max_total_energy=energy,
        max_total_visibility=visibility,
        min_actions=min_actions,
        max_actions=max_actions,
        max_level_delta=delta,
        cooldown_same_target=cooldown,
    )


def default_scenarios() -> tuple[LatentScenario, ...]:
    """Return the 16 preregistered latent scenarios in stable order."""

    rows = (
        _scenario(pair_id="doctrine_priority", intervention_class="doctrine_objective_priority_reversal", side="left", seed=29001, rendering="controlled_operational_english", retrieval=False, doctrine="MAPLE-1", strategy="persistent_pressure", direction="increase", allowed=("DER_A", "DER_B"), weights={"effect": 4, "persistence": 5, "energy": 1, "visibility": 1}, min_actions=3),
        _scenario(pair_id="doctrine_priority", intervention_class="doctrine_objective_priority_reversal", side="right", seed=29001, rendering="controlled_operational_english", retrieval=False, doctrine="BIRCH-5", strategy="resource_conserving", direction="increase", allowed=("DER_A", "DER_B"), weights={"effect": 4, "persistence": 1, "energy": 4, "visibility": 3}, min_actions=1, max_actions=3),
        _scenario(pair_id="topology_relation", intervention_class="topology_relation_reversal", side="left", seed=29002, rendering="held_out_compositional_paraphrase", retrieval=False, doctrine="CEDAR-1", strategy="gradual_bias", direction="increase", allowed=("DER_A",), weights={"effect": 5, "persistence": 3, "energy": 1, "visibility": 2}, min_actions=3, delta=1),
        _scenario(pair_id="topology_relation", intervention_class="topology_relation_reversal", side="right", seed=29002, rendering="held_out_compositional_paraphrase", retrieval=False, doctrine="CEDAR-1", strategy="gradual_bias", direction="increase", allowed=("DER_C",), weights={"effect": 5, "persistence": 3, "energy": 1, "visibility": 2}, min_actions=3, delta=1),
        _scenario(pair_id="authority_supersession", intervention_class="authority_supersession_reversal", side="left", seed=29003, rendering="controlled_operational_english", retrieval=False, doctrine="MAPLE-1", strategy="persistent_pressure", direction="increase", allowed=("DER_B",), weights={"effect": 4, "persistence": 5, "energy": 1, "visibility": 1}, min_actions=3),
        _scenario(pair_id="authority_supersession", intervention_class="authority_supersession_reversal", side="right", seed=29003, rendering="controlled_operational_english", retrieval=False, doctrine="MAPLE-2", strategy="persistent_pressure", direction="decrease", allowed=("DER_B",), weights={"effect": 4, "persistence": 5, "energy": 1, "visibility": 1}, min_actions=3),
        _scenario(pair_id="validity_expiry", intervention_class="validity_expiry_shift", side="left", seed=29004, rendering="held_out_compositional_paraphrase", retrieval=False, doctrine="ASH-7", strategy="delayed_shift", direction="increase", allowed=("DER_A", "DER_C"), forbidden=("w0",), weights={"effect": 5, "persistence": 2, "energy": 1, "visibility": 2}, min_actions=2, max_actions=3, cooldown=True),
        _scenario(pair_id="validity_expiry", intervention_class="validity_expiry_shift", side="right", seed=29004, rendering="held_out_compositional_paraphrase", retrieval=False, doctrine="ASH-7", strategy="delayed_shift", direction="increase", allowed=("DER_A", "DER_C"), forbidden=("w0", "w1"), weights={"effect": 5, "persistence": 2, "energy": 1, "visibility": 2}, min_actions=2, max_actions=2, cooldown=True),
        _scenario(pair_id="resource_budget", intervention_class="resource_budget_disclosure", side="left", seed=29005, rendering="controlled_operational_english", retrieval=True, doctrine="BIRCH-5", strategy="resource_conserving", direction="increase", allowed=("DER_A", "DER_C"), weights={"effect": 4, "persistence": 1, "energy": 4, "visibility": 3}, energy=4, visibility=4, min_actions=1, max_actions=2),
        _scenario(pair_id="resource_budget", intervention_class="resource_budget_disclosure", side="right", seed=29005, rendering="controlled_operational_english", retrieval=True, doctrine="BIRCH-6", strategy="resource_conserving", direction="increase", allowed=("DER_A", "DER_C"), weights={"effect": 4, "persistence": 1, "energy": 4, "visibility": 3}, energy=8, visibility=7, min_actions=2, max_actions=4),
        _scenario(pair_id="delayed_evidence", intervention_class="delayed_evidence_arrival", side="left", seed=29006, rendering="held_out_compositional_paraphrase", retrieval=True, doctrine="ASH-7", strategy="delayed_shift", direction="increase", allowed=("DER_B", "DER_C"), forbidden=("w0",), weights={"effect": 5, "persistence": 2, "energy": 1, "visibility": 2}, min_actions=2, max_actions=3, cooldown=True),
        _scenario(pair_id="delayed_evidence", intervention_class="delayed_evidence_arrival", side="right", seed=29006, rendering="held_out_compositional_paraphrase", retrieval=True, doctrine="ASH-8", strategy="delayed_shift", direction="increase", allowed=("DER_B", "DER_C"), forbidden=("w0", "w1"), weights={"effect": 5, "persistence": 2, "energy": 1, "visibility": 2}, min_actions=2, max_actions=2, cooldown=True),
        _scenario(pair_id="gradual_bias_horizon", intervention_class="gradual_bias_horizon_or_cooldown_change", side="left", seed=29007, rendering="controlled_operational_english", retrieval=True, doctrine="WILLOW-9", strategy="gradual_bias", direction="increase", allowed=("DER_A", "DER_B", "DER_C"), weights={"effect": 5, "persistence": 4, "energy": 1, "visibility": 3}, min_actions=3, max_actions=4, delta=1, cooldown=False),
        _scenario(pair_id="gradual_bias_horizon", intervention_class="gradual_bias_horizon_or_cooldown_change", side="right", seed=29007, rendering="controlled_operational_english", retrieval=True, doctrine="WILLOW-10", strategy="gradual_bias", direction="increase", allowed=("DER_A", "DER_B", "DER_C"), weights={"effect": 5, "persistence": 4, "energy": 1, "visibility": 3}, min_actions=3, max_actions=3, delta=1, cooldown=True),
        _scenario(pair_id="retrieval_lineage", intervention_class="retrieval_distractor_lineage_correction", side="left", seed=29008, rendering="held_out_compositional_paraphrase", retrieval=True, doctrine="ELM-11", strategy="persistent_pressure", direction="increase", allowed=("DER_B",), weights={"effect": 4, "persistence": 5, "energy": 2, "visibility": 2}, min_actions=3),
        _scenario(pair_id="retrieval_lineage", intervention_class="retrieval_distractor_lineage_correction", side="right", seed=29008, rendering="held_out_compositional_paraphrase", retrieval=True, doctrine="ELM-12", strategy="persistent_pressure", direction="decrease", allowed=("DER_B",), weights={"effect": 4, "persistence": 5, "energy": 2, "visibility": 2}, min_actions=3),
    )
    validate_scenario_registration(rows)
    return rows


def validate_scenario_registration(scenarios: Sequence[LatentScenario]) -> None:
    if len(scenarios) != 16:
        raise M29RContractError("exactly 16 scenarios are required")
    condition_ids = [row.condition_id for row in scenarios]
    if len(set(condition_ids)) != 16:
        raise M29RContractError("condition IDs are not unique")
    if {row.development_seed for row in scenarios} != set(range(29001, 29009)):
        raise M29RContractError("scenario seed coverage drift")
    pairs: dict[str, list[LatentScenario]] = {}
    for row in scenarios:
        pairs.setdefault(row.pair_id, []).append(row)
        if row.side not in {"left", "right"}:
            raise M29RContractError("invalid mirrored side")
        if set(row.allowed_targets) - set(TARGETS):
            raise M29RContractError("unknown allowed target")
        if set(row.forbidden_windows) - set(WINDOWS):
            raise M29RContractError("unknown forbidden window")
        if not 0 <= row.min_actions <= row.max_actions <= 4:
            raise M29RContractError("invalid action-count interval")
    if len(pairs) != 8 or any({x.side for x in rows} != {"left", "right"} for rows in pairs.values()):
        raise M29RContractError("mirrored pair registration drift")
    if sum(row.retrieval_required for row in scenarios) != 8:
        raise M29RContractError("retrieval scenario count drift")
    gradual = sum(row.min_actions >= 3 and row.strategy_id == "gradual_bias" for row in scenarios)
    if gradual < 4:
        raise M29RContractError("gradual-bias coverage is below the frozen minimum")


def _coefficient(seed: int, window: str, target: str) -> float:
    digest = hashlib.sha256(f"{seed}:{window}:{target}".encode("utf-8")).digest()
    return round(1.8 + int.from_bytes(digest[:2], "big") % 121 / 100.0, 2)


def build_numeric_surface(scenario: LatentScenario) -> list[dict[str, Any]]:
    """Build a pair-matched 52-action numerical surface."""

    rows: list[dict[str, Any]] = []
    for window in WINDOWS:
        rows.append(
            {
                "action_id": f"{window}_noop",
                "window": window,
                "target_id": None,
                "level": 0,
                "effect": 0.0,
                "energy_cost": 0,
                "visibility_cost": 0,
            }
        )
        for target in TARGETS:
            coefficient = _coefficient(scenario.development_seed, window, target)
            for level in LEVELS:
                sign = "neg" if level < 0 else "pos"
                rows.append(
                    {
                        "action_id": f"{window}_{target}_{sign}{abs(level)}",
                        "window": window,
                        "target_id": target,
                        "level": level,
                        "effect": round(coefficient * level, 3),
                        "energy_cost": abs(level),
                        "visibility_cost": level * level,
                    }
                )
    return rows


def _semantic_core(scenario: LatentScenario) -> dict[str, Any]:
    return {
        "strategy_id": scenario.strategy_id,
        "effect_direction": scenario.effect_direction,
        "allowed_targets": list(scenario.allowed_targets),
        "forbidden_windows": list(scenario.forbidden_windows),
        "objective_weights": scenario.weights(),
        "max_total_energy": scenario.max_total_energy,
        "max_total_visibility": scenario.max_total_visibility,
        "min_actions": scenario.min_actions,
        "max_actions": scenario.max_actions,
        "max_level_delta": scenario.max_level_delta,
        "cooldown_same_target": scenario.cooldown_same_target,
    }


def semantic_meaning_digest(scenario: LatentScenario) -> str:
    return sha256_value(_semantic_core(scenario))


def _controlled_text(scenario: LatentScenario) -> str:
    weights = scenario.weights()
    doctrine = (
        f"DOCTRINE={scenario.doctrine_code}; LOOKUP_REQUIRED=true"
        if scenario.retrieval_required
        else f"DOCTRINE={scenario.doctrine_code}; STRATEGY={scenario.strategy_id}; "
        f"DIRECTION={scenario.effect_direction}; WEIGHTS=effect:{weights['effect']},"
        f"persistence:{weights['persistence']},energy:{weights['energy']},"
        f"visibility:{weights['visibility']}; DELTA={scenario.max_level_delta}; "
        f"COOLDOWN={str(scenario.cooldown_same_target).lower()}"
    )
    forbidden = ",".join(scenario.forbidden_windows) or "none"
    return (
        f"ACTIVE {doctrine}. SCOPE={','.join(scenario.allowed_targets)}. "
        f"FORBIDDEN={forbidden}. ENERGY_CAP={scenario.max_total_energy}. "
        f"VISIBILITY_CAP={scenario.max_total_visibility}. "
        f"MIN_ACTIONS={scenario.min_actions}. MAX_ACTIONS={scenario.max_actions}. "
        "Only the newest authority-ranked record is operative."
    )


def _paraphrase_text(scenario: LatentScenario) -> str:
    weights = scenario.weights()
    direction = "raise" if scenario.effect_direction == "increase" else "lower"
    forbidden = (
        "No action is permitted during " + ", ".join(scenario.forbidden_windows) + "."
        if scenario.forbidden_windows
        else "No decision window is categorically closed."
    )
    doctrine = (
        f"Apply the active {scenario.doctrine_code} handbook entry; its detailed posture must be recovered from the approved corpus."
        if scenario.retrieval_required
        else (
            f"Use {scenario.strategy_id.replace('_', ' ')} to {direction} the signed effect. "
            f"Treat effect, persistence, energy, and visibility with priorities "
            f"{weights['effect']}, {weights['persistence']}, {weights['energy']}, and {weights['visibility']}. "
            f"Adjacent levels may differ by at most {scenario.max_level_delta}; "
            + ("do not repeat a target in consecutive windows." if scenario.cooldown_same_target else "a target may be reused in consecutive windows.")
        )
    )
    return (
        f"{doctrine} The current topology notice limits action to "
        f"{', '.join(scenario.allowed_targets)}. {forbidden} Spend no more than "
        f"{scenario.max_total_energy} energy units and {scenario.max_total_visibility} "
        f"visibility units. Use between {scenario.min_actions} and "
        f"{scenario.max_actions} active choices. A newer signed bulletin displaces "
        "any conflicting archive note."
    )


def render_semantic_text(scenario: LatentScenario, rendering: str | None = None) -> str:
    selected = rendering or scenario.active_rendering
    if selected == "controlled_operational_english":
        return _controlled_text(scenario)
    if selected == "held_out_compositional_paraphrase":
        return _paraphrase_text(scenario)
    raise M29RContractError(f"unknown rendering: {selected}")


def _semantic_records(scenario: LatentScenario) -> list[dict[str, Any]]:
    condition = scenario.condition_id
    text = render_semantic_text(scenario)
    return [
        {
            "record_id": f"{condition}.archive",
            "source_id": "archive_training_note",
            "authority_rank": 1,
            "valid_from": "w0",
            "valid_until": "w3",
            "supersedes": [],
            "text": "An archived exercise suggests the opposite direction but has no active authority.",
        },
        {
            "record_id": f"{condition}.doctrine",
            "source_id": "active_doctrine_bulletin",
            "authority_rank": 8,
            "valid_from": "w0",
            "valid_until": "w3",
            "supersedes": [f"{condition}.archive"],
            "text": text,
        },
        {
            "record_id": f"{condition}.topology",
            "source_id": "topology_notice",
            "authority_rank": 7,
            "valid_from": "w0",
            "valid_until": "w3",
            "supersedes": [],
            "text": f"The active target scope is {', '.join(scenario.allowed_targets)}.",
        },
        {
            "record_id": f"{condition}.validity",
            "source_id": "maintenance_notice",
            "authority_rank": 7,
            "valid_from": "w0",
            "valid_until": "w3",
            "supersedes": [],
            "text": f"Forbidden windows: {', '.join(scenario.forbidden_windows) or 'none'}.",
        },
        {
            "record_id": f"{condition}.budget",
            "source_id": "resource_notice",
            "authority_rank": 7,
            "valid_from": "w0",
            "valid_until": "w3",
            "supersedes": [],
            "text": (
                f"Energy cap {scenario.max_total_energy}; visibility cap "
                f"{scenario.max_total_visibility}; active choices "
                f"{scenario.min_actions} through {scenario.max_actions}."
            ),
        },
    ]


def latent_scenario_payload(scenario: LatentScenario) -> dict[str, Any]:
    return {
        "schema_version": "grideval-g7-m29r-latent-scenario/v1",
        "classification": CLASSIFICATION,
        "condition_id": scenario.condition_id,
        "pair_id": f"m29r_pair_{scenario.pair_id}",
        "intervention_class": scenario.intervention_class,
        "side": scenario.side,
        "development_seed": scenario.development_seed,
        "active_rendering": scenario.active_rendering,
        "retrieval_required": scenario.retrieval_required,
        "doctrine_code": scenario.doctrine_code,
        "semantic_program": _semantic_core(scenario),
        "numeric_surface": build_numeric_surface(scenario),
        "oracle_created_before_rendering": True,
        "simulator_data_used": False,
        "final_evaluation_data_used": False,
    }


def _query_map() -> dict[str, dict[str, Any]]:
    manifest = strict_json_file(QUERY_PATH, "M29-R query manifest")
    return {row["condition_id"]: row for row in manifest["queries"]}


def build_evidence_bundle(scenario: LatentScenario) -> dict[str, Any]:
    sources = validate_design_sources()
    query = _query_map().get(scenario.condition_id)
    if query is None or query["query_id"] != scenario.query_id:
        raise M29RContractError("scenario/query registration mismatch")
    if query["retrieval_required"] is not scenario.retrieval_required:
        raise M29RContractError("retrieval flag mismatch")
    latent = latent_scenario_payload(scenario)
    payload = {
        "schema_version": "grideval-g7-m29r-evidence-bundle/v1",
        "classification": CLASSIFICATION,
        "condition_id": scenario.condition_id,
        "pair_id": f"m29r_pair_{scenario.pair_id}",
        "side": scenario.side,
        "development_seed": scenario.development_seed,
        "active_rendering": scenario.active_rendering,
        "semantic_text": render_semantic_text(scenario),
        "semantic_records": _semantic_records(scenario),
        "numeric_surface": latent["numeric_surface"],
        "machine_limits": {
            "windows": list(WINDOWS),
            "targets": list(TARGETS),
            "max_abs_level": 2,
            "max_total_energy": 16,
            "max_total_visibility": 16,
            "max_actions": 4,
        },
        "corpus_manifest_sha256": sources["source_hashes"][CORPUS_PATH.name],
        "retrieval_query_id": scenario.query_id,
        "retrieval_required": scenario.retrieval_required,
        "semantic_meaning_digest": semantic_meaning_digest(scenario),
        "latent_scenario_sha256": sha256_value(latent),
    }
    bundle = {"evidence_bundle_id": content_id("m29revidence", payload), **payload}
    validate_evidence_bundle(bundle)
    return bundle


def validate_evidence_bundle(bundle: Mapping[str, Any]) -> None:
    expected = {
        "schema_version", "classification", "evidence_bundle_id", "condition_id",
        "pair_id", "side", "development_seed", "active_rendering", "semantic_text",
        "semantic_records", "numeric_surface", "machine_limits",
        "corpus_manifest_sha256", "retrieval_query_id", "retrieval_required",
        "semantic_meaning_digest", "latent_scenario_sha256",
    }
    _require_exact_keys(bundle, expected, "EvidenceBundle")
    payload = dict(bundle)
    identifier = payload.pop("evidence_bundle_id")
    if identifier != content_id("m29revidence", payload):
        raise M29RContractError("EvidenceBundle content address drift")
    if bundle["classification"] != CLASSIFICATION:
        raise M29RContractError("EvidenceBundle classification drift")
    surface = bundle["numeric_surface"]
    if len(surface) != 52:
        raise M29RContractError("numeric surface must contain 52 rows")
    action_ids = [row["action_id"] for row in surface]
    if len(set(action_ids)) != 52:
        raise M29RContractError("numeric surface action IDs are not unique")
    for window in WINDOWS:
        if sum(row["window"] == window for row in surface) != 13:
            raise M29RContractError("numeric surface window cardinality drift")


def _required_evidence_ids(scenario: LatentScenario) -> list[str]:
    ids = [
        f"{scenario.condition_id}.doctrine",
        f"{scenario.condition_id}.topology",
        f"{scenario.condition_id}.validity",
        f"{scenario.condition_id}.budget",
    ]
    if scenario.retrieval_required:
        query = _query_map()[scenario.condition_id]
        ids.append(query["expected_passage_id"])
    return sorted(ids)


def build_oracle_program(
    scenario: LatentScenario, bundle: Mapping[str, Any]
) -> dict[str, Any]:
    validate_evidence_bundle(bundle)
    core = _semantic_core(scenario)
    program = {
        "schema_version": "grideval-g7-m29r-strategy-program/v1",
        "condition_id": scenario.condition_id,
        **core,
        "required_evidence_ids": _required_evidence_ids(scenario),
        "lineage": {
            "evidence_bundle_id": bundle["evidence_bundle_id"],
            "semantic_meaning_digest": bundle["semantic_meaning_digest"],
            "compiler_id": "latent_oracle_compiler_v1",
        },
    }
    validate_strategy_program(program, bundle)
    return program


def build_neutral_program(bundle: Mapping[str, Any]) -> dict[str, Any]:
    validate_evidence_bundle(bundle)
    program = {
        "schema_version": "grideval-g7-m29r-strategy-program/v1",
        "condition_id": bundle["condition_id"],
        "strategy_id": "persistent_pressure",
        "effect_direction": "increase",
        "allowed_targets": list(TARGETS),
        "forbidden_windows": [],
        "objective_weights": {"effect": 5, "persistence": 1, "energy": 1, "visibility": 1},
        "max_total_energy": 16,
        "max_total_visibility": 16,
        "min_actions": 0,
        "max_actions": 4,
        "max_level_delta": 4,
        "cooldown_same_target": False,
        "required_evidence_ids": [f"{bundle['condition_id']}.budget"],
        "lineage": {
            "evidence_bundle_id": bundle["evidence_bundle_id"],
            "semantic_meaning_digest": sha256_value({"neutral_program": True}),
            "compiler_id": "registered_neutral_program_v1",
        },
    }
    validate_strategy_program(program, bundle, require_meaning_match=False)
    return program


def _parse_controlled_value(text: str, key: str) -> str:
    match = re.search(rf"(?:^|[.;] )?{re.escape(key)}=([^.;]+)", text)
    if not match:
        raise M29RContractError(f"symbolic compiler missing controlled key: {key}")
    return match.group(1).strip()


def symbolic_compile(
    scenario: LatentScenario, bundle: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Frozen narrow parser for the controlled-language baseline."""

    validate_evidence_bundle(bundle)
    if bundle["active_rendering"] != "controlled_operational_english":
        return None
    if scenario.retrieval_required:
        return None
    text = str(bundle["semantic_text"])
    try:
        weights_raw = _parse_controlled_value(text, "WEIGHTS")
        weights = {
            key: int(value)
            for key, value in (piece.split(":", 1) for piece in weights_raw.split(","))
        }
        forbidden_raw = _parse_controlled_value(text, "FORBIDDEN")
        program = {
            "schema_version": "grideval-g7-m29r-strategy-program/v1",
            "condition_id": scenario.condition_id,
            "strategy_id": _parse_controlled_value(text, "STRATEGY"),
            "effect_direction": _parse_controlled_value(text, "DIRECTION"),
            "allowed_targets": _parse_controlled_value(text, "SCOPE").split(","),
            "forbidden_windows": [] if forbidden_raw == "none" else forbidden_raw.split(","),
            "objective_weights": weights,
            "max_total_energy": int(_parse_controlled_value(text, "ENERGY_CAP")),
            "max_total_visibility": int(_parse_controlled_value(text, "VISIBILITY_CAP")),
            "min_actions": int(_parse_controlled_value(text, "MIN_ACTIONS")),
            "max_actions": int(_parse_controlled_value(text, "MAX_ACTIONS")),
            "max_level_delta": int(_parse_controlled_value(text, "DELTA")),
            "cooldown_same_target": _parse_controlled_value(text, "COOLDOWN") == "true",
            "required_evidence_ids": _required_evidence_ids(scenario),
            "lineage": {
                "evidence_bundle_id": bundle["evidence_bundle_id"],
                "semantic_meaning_digest": bundle["semantic_meaning_digest"],
                "compiler_id": "frozen_symbolic_compiler_v1",
            },
        }
        validate_strategy_program(program, bundle)
        return program
    except (M29RContractError, TypeError, ValueError):
        return None


def program_semantics(program: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: canonical_copy(program[key])
        for key in (
            "strategy_id", "effect_direction", "allowed_targets",
            "forbidden_windows", "objective_weights", "max_total_energy",
            "max_total_visibility", "min_actions", "max_actions",
            "max_level_delta", "cooldown_same_target",
        )
    }


def validate_strategy_program(
    program: Mapping[str, Any],
    bundle: Mapping[str, Any],
    *,
    require_meaning_match: bool = True,
) -> None:
    _require_exact_keys(program, STRATEGY_KEYS, "StrategyProgram")
    if program["schema_version"] != "grideval-g7-m29r-strategy-program/v1":
        raise M29RContractError("StrategyProgram schema drift")
    if program["condition_id"] != bundle["condition_id"]:
        raise M29RContractError("StrategyProgram condition mismatch")
    if program["strategy_id"] not in {"gradual_bias", "delayed_shift", "persistent_pressure", "resource_conserving"}:
        raise M29RContractError("invalid strategy ID")
    if program["effect_direction"] not in {"increase", "decrease"}:
        raise M29RContractError("invalid effect direction")
    targets = program["allowed_targets"]
    if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets) or set(targets) - set(TARGETS):
        raise M29RContractError("invalid allowed-target set")
    forbidden = program["forbidden_windows"]
    if not isinstance(forbidden, list) or len(set(forbidden)) != len(forbidden) or set(forbidden) - set(WINDOWS):
        raise M29RContractError("invalid forbidden-window set")
    weights = program["objective_weights"]
    if not isinstance(weights, Mapping):
        raise M29RContractError("objective weights must be an object")
    _require_exact_keys(weights, WEIGHT_KEYS, "objective_weights")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 10 for value in weights.values()):
        raise M29RContractError("invalid objective weight")
    for key, upper in (("max_total_energy", 16), ("max_total_visibility", 16), ("min_actions", 4), ("max_actions", 4), ("max_level_delta", 4)):
        value = program[key]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= upper:
            raise M29RContractError(f"invalid {key}")
    if program["min_actions"] > program["max_actions"]:
        raise M29RContractError("minimum actions exceeds maximum")
    if not isinstance(program["cooldown_same_target"], bool):
        raise M29RContractError("cooldown flag must be boolean")
    evidence_ids = program["required_evidence_ids"]
    if not isinstance(evidence_ids, list) or not evidence_ids or len(set(evidence_ids)) != len(evidence_ids):
        raise M29RContractError("invalid evidence lineage")
    lineage = program["lineage"]
    _require_exact_keys(lineage, {"evidence_bundle_id", "semantic_meaning_digest", "compiler_id"}, "StrategyProgram.lineage")
    if lineage["evidence_bundle_id"] != bundle["evidence_bundle_id"]:
        raise M29RContractError("program/evidence lineage mismatch")
    if require_meaning_match:
        digest = sha256_value(program_semantics(program))
        if digest != bundle["semantic_meaning_digest"] or lineage["semantic_meaning_digest"] != digest:
            raise M29RContractError("program semantic meaning mismatch")


def programs_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return canonical_json(program_semantics(left)) == canonical_json(program_semantics(right))


def optimizer_source_sha256() -> str:
    return sha256_file(Path(__file__).resolve())


def build_optimization_request(
    bundle: Mapping[str, Any], program: Mapping[str, Any]
) -> dict[str, Any]:
    validate_evidence_bundle(bundle)
    validate_strategy_program(program, bundle, require_meaning_match=False)
    body = {
        "schema_version": "grideval-g7-m29r-multistage-request/v1",
        "condition_id": bundle["condition_id"],
        "evidence_bundle_id": bundle["evidence_bundle_id"],
        "strategy_program": canonical_copy(program),
        "candidate_surface_sha256": sha256_value(bundle["numeric_surface"]),
        "optimizer_contract": {
            "algorithm": "exact_lexicographic_enumeration_v1",
            "horizon": 4,
            "maximum_sequences": 65536,
            "side_effect_class": "pure_offline_compute",
            "environment_queries": 0,
        },
        "lineage": {
            "program_sha256": sha256_value(program),
            "optimizer_source_sha256": optimizer_source_sha256(),
            "compiler_id": program["lineage"]["compiler_id"],
        },
    }
    request = {"request_id": content_id("m29rrequest", body), **body}
    validate_optimization_request(request, bundle)
    return request


def validate_optimization_request(
    request: Mapping[str, Any], bundle: Mapping[str, Any]
) -> None:
    expected = {
        "schema_version", "request_id", "condition_id", "evidence_bundle_id",
        "strategy_program", "candidate_surface_sha256", "optimizer_contract",
        "lineage",
    }
    _require_exact_keys(request, expected, "MultiStageOptimizationRequest")
    body = dict(request)
    identifier = body.pop("request_id")
    if identifier != content_id("m29rrequest", body):
        raise M29RContractError("optimization request content address drift")
    if request["evidence_bundle_id"] != bundle["evidence_bundle_id"]:
        raise M29RContractError("optimization request evidence mismatch")
    if request["candidate_surface_sha256"] != sha256_value(bundle["numeric_surface"]):
        raise M29RContractError("candidate surface hash mismatch")
    contract = request["optimizer_contract"]
    if contract != {
        "algorithm": "exact_lexicographic_enumeration_v1",
        "horizon": 4,
        "maximum_sequences": 65536,
        "side_effect_class": "pure_offline_compute",
        "environment_queries": 0,
    }:
        raise M29RContractError("optimizer contract drift")
    validate_strategy_program(request["strategy_program"], bundle, require_meaning_match=False)
    if request["lineage"]["program_sha256"] != sha256_value(request["strategy_program"]):
        raise M29RContractError("program source hash mismatch")
    if request["lineage"]["optimizer_source_sha256"] != optimizer_source_sha256():
        raise M29RContractError("optimizer source hash mismatch")


def _surface_by_window(bundle: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = {window: [] for window in WINDOWS}
    for row in bundle["numeric_surface"]:
        grouped[row["window"]].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: item["action_id"])
    return grouped


def _plan_metrics(
    actions: Sequence[Mapping[str, Any]], program: Mapping[str, Any]
) -> tuple[dict[str, Any], float]:
    direction = 1.0 if program["effect_direction"] == "increase" else -1.0
    signed_effect = round(direction * sum(float(row["effect"]) for row in actions), 6)
    persistence = sum(direction * float(row["effect"]) > 0 for row in actions)
    energy = sum(int(row["energy_cost"]) for row in actions)
    visibility = sum(int(row["visibility_cost"]) for row in actions)
    action_count = sum(row["target_id"] is not None for row in actions)
    aggregate = {
        "signed_effect": signed_effect,
        "persistence_windows": persistence,
        "total_energy": energy,
        "total_visibility": visibility,
        "action_count": action_count,
    }
    weights = program["objective_weights"]
    objective = round(
        float(weights["effect"]) * signed_effect
        + float(weights["persistence"]) * persistence
        - float(weights["energy"]) * energy
        - float(weights["visibility"]) * visibility,
        6,
    )
    return aggregate, objective


def _sequence_valid(
    actions: Sequence[Mapping[str, Any]], program: Mapping[str, Any]
) -> bool:
    if len(actions) != 4 or [row["window"] for row in actions] != list(WINDOWS):
        return False
    allowed = set(program["allowed_targets"])
    forbidden = set(program["forbidden_windows"])
    for row in actions:
        if row["target_id"] is not None and row["target_id"] not in allowed:
            return False
        if row["window"] in forbidden and row["target_id"] is not None:
            return False
    aggregate, _ = _plan_metrics(actions, program)
    if not program["min_actions"] <= aggregate["action_count"] <= program["max_actions"]:
        return False
    if aggregate["total_energy"] > program["max_total_energy"]:
        return False
    if aggregate["total_visibility"] > program["max_total_visibility"]:
        return False
    levels = [int(row["level"]) for row in actions]
    if any(abs(right - left) > program["max_level_delta"] for left, right in zip(levels, levels[1:])):
        return False
    if program["cooldown_same_target"]:
        targets = [row["target_id"] for row in actions]
        if any(left is not None and left == right for left, right in zip(targets, targets[1:])):
            return False
    return True


def _make_plan(
    bundle: Mapping[str, Any],
    program: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    planner_id: str,
) -> dict[str, Any]:
    aggregate, objective = _plan_metrics(actions, program)
    body = {
        "schema_version": "grideval-g7-m29r-attack-plan/v1",
        "condition_id": bundle["condition_id"],
        "steps": [canonical_copy(row) for row in actions],
        "aggregate": aggregate,
        "objective_value": objective,
        "lineage": {
            "evidence_bundle_id": bundle["evidence_bundle_id"],
            "strategy_program_sha256": sha256_value(program),
            "planner_id": planner_id,
        },
    }
    plan = {"plan_id": content_id("m29rplan", body), **body}
    validate_attack_plan(plan, bundle, program)
    return plan


def validate_attack_plan(
    plan: Mapping[str, Any],
    bundle: Mapping[str, Any],
    program: Mapping[str, Any],
) -> None:
    expected = {"schema_version", "plan_id", "condition_id", "steps", "aggregate", "objective_value", "lineage"}
    _require_exact_keys(plan, expected, "AttackPlan")
    body = dict(plan)
    identifier = body.pop("plan_id")
    if identifier != content_id("m29rplan", body):
        raise M29RContractError("AttackPlan content address drift")
    if plan["condition_id"] != bundle["condition_id"]:
        raise M29RContractError("AttackPlan condition mismatch")
    surface = {row["action_id"]: row for row in bundle["numeric_surface"]}
    steps = plan["steps"]
    if not isinstance(steps, list) or len(steps) != 4:
        raise M29RContractError("AttackPlan must contain four steps")
    canonical_steps: list[dict[str, Any]] = []
    for window, step in zip(WINDOWS, steps):
        if step.get("window") != window:
            raise M29RContractError("AttackPlan window order drift")
        source = surface.get(step.get("action_id"))
        if source is None or canonical_json(source) != canonical_json(step):
            raise M29RContractError("AttackPlan step is not on the candidate surface")
        canonical_steps.append(source)
    if not _sequence_valid(canonical_steps, program):
        raise M29RContractError("AttackPlan violates program constraints")
    aggregate, objective = _plan_metrics(canonical_steps, program)
    if canonical_json(plan["aggregate"]) != canonical_json(aggregate):
        raise M29RContractError("AttackPlan aggregate drift")
    if float(plan["objective_value"]) != objective:
        raise M29RContractError("AttackPlan objective drift")
    lineage = plan["lineage"]
    if lineage["evidence_bundle_id"] != bundle["evidence_bundle_id"]:
        raise M29RContractError("AttackPlan evidence lineage mismatch")
    if lineage["strategy_program_sha256"] != sha256_value(program):
        raise M29RContractError("AttackPlan program lineage mismatch")


def run_shared_optimizer(
    request: Mapping[str, Any], bundle: Mapping[str, Any]
) -> dict[str, Any]:
    """Execute the pure exact optimizer shared by all applicable tested arms."""

    validate_optimization_request(request, bundle)
    program = request["strategy_program"]
    grouped = _surface_by_window(bundle)
    evaluated = 0
    feasible = 0
    best_actions: tuple[dict[str, Any], ...] | None = None
    best_key: tuple[float, tuple[str, ...]] | None = None
    for sequence in itertools.product(*(grouped[window] for window in WINDOWS)):
        evaluated += 1
        if not _sequence_valid(sequence, program):
            continue
        feasible += 1
        _, objective = _plan_metrics(sequence, program)
        action_key = tuple(row["action_id"] for row in sequence)
        key = (objective, tuple(chr(255 - ord(ch)) for ch in "|".join(action_key)))
        # Objective is maximized; equal objectives use ascending action IDs.
        if best_actions is None or objective > best_key[0] or (
            objective == best_key[0] and action_key < tuple(row["action_id"] for row in best_actions)
        ):
            best_actions = tuple(sequence)
            best_key = (objective, key[1])
    if evaluated > request["optimizer_contract"]["maximum_sequences"]:
        raise M29RContractError("optimizer sequence cap exceeded")
    if best_actions is None:
        plan = None
        status = "infeasible"
        failure_class = "no_feasible_plan"
    else:
        plan = _make_plan(bundle, program, best_actions, "shared_exact_optimizer_v1")
        status = "optimal"
        failure_class = None
    body = {
        "schema_version": "grideval-g7-m29r-optimizer-result/v1",
        "request_id": request["request_id"],
        "status": status,
        "plan": plan,
        "evaluated_sequences": evaluated,
        "feasible_sequences": feasible,
        "failure_class": failure_class,
        "lineage": {
            "request_sha256": sha256_value(request),
            "optimizer_source_sha256": optimizer_source_sha256(),
        },
    }
    result = {"result_id": content_id("m29rresult", body), **body}
    validate_optimizer_result(result, request, bundle)
    return result


def validate_optimizer_result(
    result: Mapping[str, Any],
    request: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> None:
    expected = {"schema_version", "result_id", "request_id", "status", "plan", "evaluated_sequences", "feasible_sequences", "failure_class", "lineage"}
    _require_exact_keys(result, expected, "OptimizerResult")
    body = dict(result)
    identifier = body.pop("result_id")
    if identifier != content_id("m29rresult", body):
        raise M29RContractError("OptimizerResult content address drift")
    if result["request_id"] != request["request_id"]:
        raise M29RContractError("OptimizerResult request mismatch")
    if result["lineage"] != {
        "request_sha256": sha256_value(request),
        "optimizer_source_sha256": optimizer_source_sha256(),
    }:
        raise M29RContractError("OptimizerResult lineage drift")
    if result["status"] == "optimal":
        if result["failure_class"] is not None or result["plan"] is None:
            raise M29RContractError("optimal result shape mismatch")
        validate_attack_plan(result["plan"], bundle, request["strategy_program"])
    elif result["status"] == "infeasible":
        if result["plan"] is not None or result["failure_class"] != "no_feasible_plan":
            raise M29RContractError("infeasible result shape mismatch")
    else:
        raise M29RContractError("unexpected optimizer status")


def run_independent_oracle(
    scenario: LatentScenario, bundle: Mapping[str, Any]
) -> dict[str, Any]:
    """Enumerate the oracle with an independent recursive implementation."""

    program = build_oracle_program(scenario, bundle)
    grouped = _surface_by_window(bundle)
    best: list[dict[str, Any]] | None = None
    best_objective = -math.inf
    evaluated = 0
    feasible = 0

    def visit(index: int, prefix: list[dict[str, Any]]) -> None:
        nonlocal best, best_objective, evaluated, feasible
        if index == len(WINDOWS):
            evaluated += 1
            if not _sequence_valid(prefix, program):
                return
            feasible += 1
            _, objective = _plan_metrics(prefix, program)
            action_key = tuple(row["action_id"] for row in prefix)
            best_key = tuple(row["action_id"] for row in best) if best is not None else ()
            if best is None or objective > best_objective or (
                objective == best_objective and action_key < best_key
            ):
                best = list(prefix)
                best_objective = objective
            return
        for action in grouped[WINDOWS[index]]:
            prefix.append(action)
            visit(index + 1, prefix)
            prefix.pop()

    visit(0, [])
    if best is None:
        raise M29RContractError("registered latent scenario is infeasible")
    return {
        "schema_version": "grideval-g7-m29r-independent-oracle/v1",
        "condition_id": scenario.condition_id,
        "latent_scenario_sha256": bundle["latent_scenario_sha256"],
        "strategy_program": program,
        "plan": _make_plan(bundle, program, best, "independent_oracle_enumerator_v1"),
        "evaluated_sequences": evaluated,
        "feasible_sequences": feasible,
        "oracle_independent_of_language_rendering": True,
        "tested_optimizer_called": False,
    }


def build_design_fixture() -> dict[str, Any]:
    """Build all latent, evidence, oracle, and parity records without I/O."""

    sources = validate_design_sources()
    conditions: list[dict[str, Any]] = []
    for scenario in default_scenarios():
        latent = latent_scenario_payload(scenario)
        bundle = build_evidence_bundle(scenario)
        oracle = run_independent_oracle(scenario, bundle)
        shared_request = build_optimization_request(bundle, oracle["strategy_program"])
        shared_result = run_shared_optimizer(shared_request, bundle)
        if shared_result["status"] != "optimal":
            raise M29RContractError("shared optimizer failed on oracle program")
        if shared_result["plan"]["objective_value"] != oracle["plan"]["objective_value"]:
            raise M29RContractError("shared optimizer and independent oracle disagree")
        if [row["action_id"] for row in shared_result["plan"]["steps"]] != [row["action_id"] for row in oracle["plan"]["steps"]]:
            raise M29RContractError("optimizer/oracle tie-break disagreement")
        alternate = (
            "held_out_compositional_paraphrase"
            if scenario.active_rendering == "controlled_operational_english"
            else "controlled_operational_english"
        )
        if not render_semantic_text(scenario, alternate):
            raise M29RContractError("alternate rendering is empty")
        conditions.append(
            {
                "condition_id": scenario.condition_id,
                "pair_id": f"m29r_pair_{scenario.pair_id}",
                "intervention_class": scenario.intervention_class,
                "side": scenario.side,
                "latent_scenario": latent,
                "evidence_bundle": bundle,
                "alternate_rendering": {
                    "rendering_id": alternate,
                    "text": render_semantic_text(scenario, alternate),
                    "semantic_meaning_digest": semantic_meaning_digest(scenario),
                },
                "independent_oracle": oracle,
                "shared_optimizer_parity": {
                    "request_id": shared_request["request_id"],
                    "result_id": shared_result["result_id"],
                    "objective_value": shared_result["plan"]["objective_value"],
                    "action_ids": [row["action_id"] for row in shared_result["plan"]["steps"]],
                },
            }
        )
    body = {
        "schema_version": "grideval-g7-m29r-design-fixture/v1",
        "classification": CLASSIFICATION,
        "project_id": "prj_01KYMPK10PE9YH1TJ84PAVB9Z6",
        "mission_id": "mis_01M1PC1T0M7BAVX9NWB19P0FWC",
        "decision_id": "dec_01M1PBZSNK0MP4E3NH28H26841",
        "source_hashes": sources["source_hashes"],
        "optimizer_source_sha256": optimizer_source_sha256(),
        "condition_count": len(conditions),
        "conditions": conditions,
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
    }
    return {"design_fixture_id": content_id("m29rfixture", body), **body}


def create_once_json(path: Path, payload: Any) -> None:
    """Write canonical pretty JSON once and refuse overwrite."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Create-once path for the offline M29-R design fixture.",
    )
    args = parser.parse_args()
    fixture = build_design_fixture()
    create_once_json(args.output, fixture)
    print(
        canonical_json(
            {
                "condition_count": fixture["condition_count"],
                "design_fixture_id": fixture["design_fixture_id"],
                "output": args.output.as_posix(),
            }
        )
    )


if __name__ == "__main__":
    main()
