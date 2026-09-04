"""Frozen offline contracts for the M29-A hybrid agent-optimizer study.

The module is deliberately simulator-free. It builds capability-filtered
development fixtures, typed optimizer requests/results, and a shared validator
boundary. It never contacts a model, starts a service, or accesses RKA.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .budget import DualBudget
from .candidates import CandidateLibrary, CandidateTemplate
from .orchestration_contract import (
    AuthorityProfile,
    CapabilityProfile,
    ContractViolation,
    ControllerDecision,
    InformationLevel,
    KnowledgeProfile,
    OrchestrationRung,
    PlanAction,
    PlanValidator,
    StrategyCard,
    StrategyLibrary,
    StrategyStep,
    ToolContract,
)


PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1N4BBH6TJ1Q6FBV2DNNS7Z8"
DECISION_ID = "dec_01M1N48392JT638G1E4VPYF2YZ"
CLASSIFICATION = "PRELIMINARY_ONLY"
DESIGN_CONTRACT_ID = (
    "m29contract_97d073f1ecbc03271346a6559dfc8367275a45a18519be13d38240da7bf423b0"
)
DESIGN_SCHEMA_VERSION = "grideval-g7-m29-counterfactual-contract/v1"
ATTACK_STATE_SCHEMA_VERSION = "grideval-g7-m29-attack-state/v1"
OPTIMIZATION_REQUEST_SCHEMA_VERSION = "grideval-g7-m29-optimization-request/v1"
OPTIMIZER_RESULT_SCHEMA_VERSION = "grideval-g7-m29-optimizer-result/v1"
OPTIMIZER_ID = "m29_grid_search_v1"
OPTIMIZER_SEED = 2901
COMMON_VALIDATOR_ID = "common_plan_validator_v1"
FROZEN_CANDIDATE_SURFACE_ID = (
    "m29surface_375078014f605fae2211b301f9ee54cfab6cecadf97f179e60fbe6a5ec9a220b"
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DESIGN_CONTRACT_PATH = (
    PACKAGE_ROOT / "artifacts" / "m29_hybrid_contract" / "contract.json"
)
OPTIMIZER_SOURCE_PATH = Path(__file__).resolve()

ARM_IDS = ("IA2", "IA3-O", "IA4-D", "IA4-H", "IA4-HG")
OPTIMIZER_ARMS = frozenset({"IA3-O", "IA4-H", "IA4-HG"})
LLM_ARMS = frozenset({"IA4-D", "IA4-H", "IA4-HG"})
STRATEGY_IDS = ("active_step", "reactive_shift", "low_energy_ramp")
TARGET_IDS = ("DER_A", "DER_B")
INFORMATION_LEVELS = {"none": 0, "partial": 1, "exact": 2}


def canonical_json(value: Any) -> str:
    """Return the one allowed canonical JSON encoding."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractViolation("M29 value is not canonical JSON") from exc


def canonical_copy(value: Any) -> Any:
    return json.loads(canonical_json(value))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return prefix + sha256_value(payload)


def strict_json_file(path: Path, label: str) -> Any:
    """Read one UTF-8 JSON value while rejecting duplicate keys and NaN."""

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ContractViolation(f"{label} contains duplicate field: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ContractViolation(f"{label} contains non-finite constant: {value}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation(f"{label} is not one UTF-8 JSON value") from exc


def _require_exact_keys(payload: Mapping[str, Any], expected: set[str],
                        label: str) -> None:
    actual = set(payload)
    if actual != expected:
        raise ContractViolation(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def validate_design_contract() -> dict[str, Any]:
    """Verify the frozen Gate-1 contract and every planning source byte."""

    contract = strict_json_file(DESIGN_CONTRACT_PATH, "M29 design contract")
    if not isinstance(contract, dict):
        raise ContractViolation("M29 design contract must be an object")
    if contract.get("schema_version") != DESIGN_SCHEMA_VERSION:
        raise ContractViolation("M29 design schema version drift")
    if contract.get("contract_id") != DESIGN_CONTRACT_ID:
        raise ContractViolation("M29 design contract identity drift")
    content = canonical_copy(contract)
    stored_id = content.pop("contract_id")
    if stored_id != content_id("m29contract_", content):
        raise ContractViolation("M29 design contract content address drift")
    manifest = contract.get("source_hash_manifest")
    if not isinstance(manifest, list) or len(manifest) != 7:
        raise ContractViolation("M29 source manifest must bind seven files")
    roles: set[str] = set()
    for item in manifest:
        if not isinstance(item, dict):
            raise ContractViolation("M29 source binding must be an object")
        _require_exact_keys(item, {"path", "sha256", "role"}, "source binding")
        path = PACKAGE_ROOT / str(item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ContractViolation(f"M29 source hash drift: {item['path']}")
        roles.add(str(item["role"]))
    if len(roles) != 7:
        raise ContractViolation("M29 source roles are not unique")
    if contract.get("prohibited_access") != [
        "docker",
        "simulator",
        "detector",
        "defense",
        "embedding",
        "physical_actuator",
        "evaluation_records",
        "evaluation_seeds_9101_9112",
        "rka_attacker_view",
    ]:
        raise ContractViolation("M29 prohibited-access boundary drift")
    return contract


@dataclass(frozen=True)
class M29Condition:
    """One side of one preregistered offline counterfactual pair."""

    condition_id: str
    intervention_id: str
    intervention_class: str
    side: str
    operating_point_id: str
    target_scores: Mapping[str, float]
    strategy_scores: Mapping[str, float]
    applicable_strategies: frozenset[str]
    invalid_strategy_targets: frozenset[str]
    remaining_window_budget: int
    remaining_energy_kvah: float
    feedback_delay_windows: int
    visible_history: tuple[Mapping[str, Any], ...]
    optimizer_mode: str
    optimizer_failure_class: str | None
    stale_rule_strategy: str
    current_evidence_strategy: str
    expected_strategy_id: str | None
    expected_target_id: str | None
    eligible_arms: frozenset[str]

    def __post_init__(self) -> None:
        if self.side not in {"left", "right"}:
            raise ContractViolation("M29 condition side must be left or right")
        if set(self.target_scores) != set(TARGET_IDS):
            raise ContractViolation("M29 condition must score both targets")
        if set(self.strategy_scores) != set(STRATEGY_IDS):
            raise ContractViolation("M29 condition must score every strategy")
        if not self.applicable_strategies.issubset(STRATEGY_IDS):
            raise ContractViolation("M29 condition uses an unknown strategy")
        if self.expected_strategy_id not in {*STRATEGY_IDS, None}:
            raise ContractViolation("M29 expected strategy is invalid")
        if self.expected_target_id not in {*TARGET_IDS, None}:
            raise ContractViolation("M29 expected target is invalid")
        if self.optimizer_mode not in {"normal", "infeasible", "tool_failure"}:
            raise ContractViolation("M29 optimizer mode is invalid")
        if self.optimizer_mode == "tool_failure" and not self.optimizer_failure_class:
            raise ContractViolation("M29 tool failure requires a failure class")
        if int(self.remaining_window_budget) < 0:
            raise ContractViolation("M29 remaining window budget is negative")
        if not math.isfinite(float(self.remaining_energy_kvah)):
            raise ContractViolation("M29 remaining energy must be finite")
        if float(self.remaining_energy_kvah) < 0:
            raise ContractViolation("M29 remaining energy is negative")
        if not self.eligible_arms.issubset(ARM_IDS):
            raise ContractViolation("M29 condition has an unknown eligible arm")

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "intervention_id": self.intervention_id,
            "intervention_class": self.intervention_class,
            "side": self.side,
            "operating_point_id": self.operating_point_id,
            "target_scores": {
                key: float(self.target_scores[key]) for key in TARGET_IDS
            },
            "strategy_scores": {
                key: float(self.strategy_scores[key]) for key in STRATEGY_IDS
            },
            "applicable_strategies": sorted(self.applicable_strategies),
            "invalid_strategy_targets": sorted(self.invalid_strategy_targets),
            "remaining_window_budget": int(self.remaining_window_budget),
            "remaining_energy_kvah": float(self.remaining_energy_kvah),
            "feedback_delay_windows": int(self.feedback_delay_windows),
            "visible_history": canonical_copy(self.visible_history),
            "optimizer_mode": self.optimizer_mode,
            "optimizer_failure_class": self.optimizer_failure_class,
            "stale_rule_strategy": self.stale_rule_strategy,
            "current_evidence_strategy": self.current_evidence_strategy,
            "expected_strategy_id": self.expected_strategy_id,
            "expected_target_id": self.expected_target_id,
            "eligible_arms": sorted(self.eligible_arms),
        }


def _condition(*, intervention_id: str, intervention_class: str, side: str,
               **overrides: Any) -> M29Condition:
    base: dict[str, Any] = {
        "condition_id": f"m29_{intervention_class}_{side}",
        "intervention_id": intervention_id,
        "intervention_class": intervention_class,
        "side": side,
        "operating_point_id": "op_high_load",
        "target_scores": {"DER_A": 0.8, "DER_B": 0.4},
        "strategy_scores": {
            "active_step": 1.0,
            "reactive_shift": 0.7,
            "low_energy_ramp": 0.4,
        },
        "applicable_strategies": frozenset(STRATEGY_IDS),
        "invalid_strategy_targets": frozenset(),
        "remaining_window_budget": 4,
        "remaining_energy_kvah": 2.0,
        "feedback_delay_windows": 0,
        "visible_history": (),
        "optimizer_mode": "normal",
        "optimizer_failure_class": None,
        "stale_rule_strategy": "active_step",
        "current_evidence_strategy": "active_step",
        "expected_strategy_id": "active_step",
        "expected_target_id": "DER_A",
        "eligible_arms": frozenset(ARM_IDS),
    }
    base.update(overrides)
    return M29Condition(**base)


def default_conditions() -> tuple[M29Condition, ...]:
    """Return the sixteen frozen counterfactual conditions in contract order."""

    optimizer_only = frozenset(OPTIMIZER_ARMS)
    return (
        _condition(
            intervention_id="cf1",
            intervention_class="sensitivity_reversal",
            side="left",
            target_scores={"DER_A": 0.8, "DER_B": 0.2},
            expected_target_id="DER_A",
        ),
        _condition(
            intervention_id="cf1",
            intervention_class="sensitivity_reversal",
            side="right",
            target_scores={"DER_A": 0.2, "DER_B": 0.8},
            expected_target_id="DER_B",
        ),
        _condition(
            intervention_id="cf2",
            intervention_class="operating_point_change",
            side="left",
            operating_point_id="op_high_load",
            applicable_strategies=frozenset({"active_step", "low_energy_ramp"}),
            expected_strategy_id="active_step",
        ),
        _condition(
            intervention_id="cf2",
            intervention_class="operating_point_change",
            side="right",
            operating_point_id="op_solar_noon",
            applicable_strategies=frozenset({"reactive_shift", "low_energy_ramp"}),
            strategy_scores={
                "active_step": 0.2,
                "reactive_shift": 1.0,
                "low_energy_ramp": 0.4,
            },
            current_evidence_strategy="reactive_shift",
            expected_strategy_id="reactive_shift",
        ),
        _condition(
            intervention_id="cf3",
            intervention_class="validity_hole",
            side="left",
        ),
        _condition(
            intervention_id="cf3",
            intervention_class="validity_hole",
            side="right",
            invalid_strategy_targets=frozenset({"active_step@DER_A"}),
            expected_target_id="DER_B",
        ),
        _condition(
            intervention_id="cf4",
            intervention_class="budget_change",
            side="left",
            remaining_window_budget=2,
            remaining_energy_kvah=0.10,
        ),
        _condition(
            intervention_id="cf4",
            intervention_class="budget_change",
            side="right",
            remaining_window_budget=1,
            remaining_energy_kvah=0.03,
            current_evidence_strategy="low_energy_ramp",
            expected_strategy_id="low_energy_ramp",
        ),
        _condition(
            intervention_id="cf5",
            intervention_class="delayed_feedback",
            side="left",
            target_scores={"DER_A": 0.2, "DER_B": 0.9},
            feedback_delay_windows=0,
            visible_history=(
                {"window": 1, "target_id": "DER_A", "reward": 0.2},
                {"window": 2, "target_id": "DER_B", "reward": 0.9},
            ),
            expected_target_id="DER_B",
        ),
        _condition(
            intervention_id="cf5",
            intervention_class="delayed_feedback",
            side="right",
            target_scores={"DER_A": 0.6, "DER_B": 0.3},
            feedback_delay_windows=1,
            visible_history=(
                {"window": 1, "target_id": "DER_A", "reward": 0.6},
            ),
            expected_target_id="DER_A",
        ),
        _condition(
            intervention_id="cf6",
            intervention_class="infeasible_optimizer_output",
            side="left",
            eligible_arms=optimizer_only,
        ),
        _condition(
            intervention_id="cf6",
            intervention_class="infeasible_optimizer_output",
            side="right",
            optimizer_mode="infeasible",
            expected_strategy_id=None,
            expected_target_id=None,
            eligible_arms=optimizer_only,
        ),
        _condition(
            intervention_id="cf7",
            intervention_class="tool_failure_class",
            side="left",
            eligible_arms=optimizer_only,
        ),
        _condition(
            intervention_id="cf7",
            intervention_class="tool_failure_class",
            side="right",
            optimizer_mode="tool_failure",
            optimizer_failure_class="TOOL_UNAVAILABLE",
            expected_strategy_id=None,
            expected_target_id=None,
            eligible_arms=optimizer_only,
        ),
        _condition(
            intervention_id="cf8",
            intervention_class="strategy_rule_contradiction",
            side="left",
        ),
        _condition(
            intervention_id="cf8",
            intervention_class="strategy_rule_contradiction",
            side="right",
            strategy_scores={
                "active_step": 0.2,
                "reactive_shift": 1.0,
                "low_energy_ramp": 0.4,
            },
            stale_rule_strategy="active_step",
            current_evidence_strategy="reactive_shift",
            expected_strategy_id="reactive_shift",
        ),
    )


def condition_map() -> dict[str, M29Condition]:
    conditions = default_conditions()
    result = {item.condition_id: item for item in conditions}
    if len(result) != 16:
        raise ContractViolation("M29 conditions are not uniquely identified")
    return result


def validate_condition_registration() -> None:
    """Bind executable fixtures to the frozen intervention matrix."""

    contract = validate_design_contract()
    conditions = condition_map()
    registered: list[str] = []
    classes: list[str] = []
    for item in contract["interventions"]:
        classes.append(item["class"])
        for side in ("left", "right"):
            condition_id = item[f"{side}_condition_id"]
            registered.append(condition_id)
            condition = conditions.get(condition_id)
            if condition is None:
                raise ContractViolation(f"missing M29 condition: {condition_id}")
            if condition.intervention_id != item["intervention_id"]:
                raise ContractViolation("M29 intervention identity drift")
            if condition.intervention_class != item["class"]:
                raise ContractViolation("M29 intervention class drift")
            if sorted(condition.eligible_arms) != sorted(item["eligible_arms"]):
                raise ContractViolation("M29 eligible-arm drift")
    if len(set(classes)) != 8 or len(set(registered)) != 16:
        raise ContractViolation("M29 intervention registration is incomplete")


def build_strategy_library() -> StrategyLibrary:
    """Return the frozen three-card M29 strategy library."""

    return StrategyLibrary((
        StrategyCard(
            strategy_id="active_step",
            family="active_power",
            description="One bounded active-power step at one declared DER.",
            default_actions=(PlanAction("DER_A", 30.0, 0.0),),
            eligible_devices=frozenset(TARGET_IDS),
            p_kw_bounds=(30.0, 30.0),
            q_kvar_bounds=(0.0, 0.0),
        ),
        StrategyCard(
            strategy_id="reactive_shift",
            family="reactive_power",
            description="One bounded reactive-power shift at one declared DER.",
            default_actions=(PlanAction("DER_A", 0.0, 20.0),),
            eligible_devices=frozenset(TARGET_IDS),
            p_kw_bounds=(0.0, 0.0),
            q_kvar_bounds=(20.0, 20.0),
        ),
        StrategyCard(
            strategy_id="low_energy_ramp",
            family="active_power",
            description="One low-energy active-power increment at one declared DER.",
            default_actions=(PlanAction("DER_A", 6.0, 0.0),),
            eligible_devices=frozenset(TARGET_IDS),
            p_kw_bounds=(6.0, 6.0),
            q_kvar_bounds=(0.0, 0.0),
        ),
    ))


def _step_for(strategy_id: str, target_id: str) -> StrategyStep:
    actions = {
        "active_step": PlanAction(target_id, 30.0, 0.0),
        "reactive_shift": PlanAction(target_id, 0.0, 20.0),
        "low_energy_ramp": PlanAction(target_id, 6.0, 0.0),
    }
    try:
        action = actions[strategy_id]
    except KeyError as exc:
        raise ContractViolation(f"unknown M29 strategy: {strategy_id}") from exc
    if target_id not in TARGET_IDS:
        raise ContractViolation(f"unknown M29 target: {target_id}")
    return StrategyStep(strategy_id=strategy_id, parameters=(), actions=(action,))


def build_candidate_library() -> CandidateLibrary:
    """Build the byte-identical six-candidate surface used by every arm."""

    return CandidateLibrary(
        CandidateTemplate(
            steps=(_step_for(strategy_id, target_id),),
            origins=frozenset({"m29_frozen_shared_surface"}),
        )
        for strategy_id in STRATEGY_IDS
        for target_id in TARGET_IDS
    )


def candidate_for(strategy_id: str, target_id: str,
                  library: CandidateLibrary | None = None) -> CandidateTemplate:
    candidates = library or build_candidate_library()
    matches = [
        item for item in candidates.candidates
        if item.strategy_ids == (strategy_id,) and item.target_ids == (target_id,)
    ]
    if len(matches) != 1:
        raise ContractViolation("strategy and target do not map to one candidate")
    return matches[0]


def candidate_energy_kvah(candidate: CandidateTemplate) -> float:
    action = candidate.steps[0].actions[0]
    return math.hypot(action.p_kw, action.q_kvar) * 10.0 / 3600.0


def candidate_is_feasible(condition: M29Condition,
                          candidate: CandidateTemplate) -> bool:
    strategy_id = candidate.strategy_ids[0]
    target_id = candidate.target_ids[0]
    if condition.optimizer_mode == "infeasible":
        return False
    if strategy_id not in condition.applicable_strategies:
        return False
    if f"{strategy_id}@{target_id}" in condition.invalid_strategy_targets:
        return False
    if condition.remaining_window_budget < 1:
        return False
    return candidate_energy_kvah(candidate) <= (
        condition.remaining_energy_kvah + 1e-12
    )


def _fact(fact_id: str, subject: str, predicate: str, value: Any, *,
          axis: str = "grid", level: str = "partial",
          evidence_lane: str = "EVIDENCE_VALID") -> dict[str, Any]:
    if isinstance(value, bool):
        object_value = "true" if value else "false"
    elif isinstance(value, float):
        object_value = format(value, ".12g")
    else:
        object_value = str(value)
    return {
        "fact_id": fact_id,
        "subject": subject,
        "predicate": predicate,
        "object": object_value,
        "information_axis": axis,
        "information_level": level,
        "evidence_lane": evidence_lane,
        "valid_from_window": 0,
        "valid_through_window": 4,
        "evidence_id": f"fixture_{fact_id.removeprefix('fact_')}",
    }


def canonical_facts(condition: M29Condition) -> tuple[dict[str, Any], ...]:
    """Build the only raw-information payload from which views are rendered."""

    facts = [
        _fact("fact_operating_point", "grid", "operating_point_id",
              condition.operating_point_id),
        _fact("fact_remaining_windows", "authority", "remaining_window_budget",
              condition.remaining_window_budget),
        _fact("fact_remaining_energy", "authority", "remaining_energy_kvah",
              condition.remaining_energy_kvah),
        _fact("fact_feedback_delay", "feedback", "delay_windows",
              condition.feedback_delay_windows, axis="feedback"),
        _fact("fact_optimizer_mode", "optimizer", "mode",
              condition.optimizer_mode),
        _fact("fact_stale_rule", "strategy", "stale_rule_strategy",
              condition.stale_rule_strategy),
        _fact("fact_current_evidence", "strategy", "current_evidence_strategy",
              condition.current_evidence_strategy),
    ]
    for target_id in TARGET_IDS:
        facts.append(_fact(
            f"fact_target_score_{target_id.lower()}",
            target_id,
            "synthetic_grid_stress_score",
            float(condition.target_scores[target_id]),
        ))
    for strategy_id in STRATEGY_IDS:
        facts.extend((
            _fact(
                f"fact_strategy_score_{strategy_id}",
                strategy_id,
                "strategy_score",
                float(condition.strategy_scores[strategy_id]),
            ),
            _fact(
                f"fact_strategy_applicable_{strategy_id}",
                strategy_id,
                "applicable",
                strategy_id in condition.applicable_strategies,
            ),
        ))
    invalid = ",".join(sorted(condition.invalid_strategy_targets)) or "none"
    facts.append(_fact(
        "fact_invalid_strategy_targets",
        "validity",
        "invalid_strategy_targets",
        invalid,
    ))
    if condition.optimizer_failure_class is not None:
        facts.append(_fact(
            "fact_optimizer_failure_class",
            "optimizer",
            "failure_class",
            condition.optimizer_failure_class,
        ))
    for index, item in enumerate(condition.visible_history):
        facts.append(_fact(
            f"fact_visible_history_{index:02d}",
            str(item["target_id"]),
            f"visible_reward_window_{int(item['window'])}",
            float(item["reward"]),
            axis="feedback",
        ))
    return tuple(sorted(facts, key=lambda item: item["fact_id"]))


def filter_facts_by_knowledge(
    facts: Sequence[Mapping[str, Any]], knowledge_profile: Mapping[str, str]
) -> tuple[dict[str, Any], ...]:
    """Filter facts by the frozen K vector without consulting governance state."""

    filtered: list[dict[str, Any]] = []
    for fact in facts:
        axis = str(fact["information_axis"])
        required = str(fact["information_level"])
        granted = knowledge_profile.get(axis, "none")
        if INFORMATION_LEVELS.get(granted, -1) >= INFORMATION_LEVELS[required]:
            filtered.append(canonical_copy(fact))
    return tuple(filtered)


def build_attack_state(condition: M29Condition) -> dict[str, Any]:
    """Return a content-addressed attacker state that contains no RKA fields."""

    knowledge = {
        "grid": "partial",
        "detector": "none",
        "training_data": "none",
        "defense": "none",
        "feedback": "partial",
    }
    facts = filter_facts_by_knowledge(canonical_facts(condition), knowledge)
    semantic_digest = sha256_value(list(facts))
    failure_events: list[dict[str, Any]] = []
    if condition.optimizer_mode == "infeasible":
        failure_events.append({
            "failure_id": "failure_no_feasible_candidate",
            "failure_class": "NO_FEASIBLE_CANDIDATE",
            "component": "optimizer",
            "terminal": True,
        })
    if condition.optimizer_mode == "tool_failure":
        failure_events.append({
            "failure_id": "failure_optimizer_tool_unavailable",
            "failure_class": condition.optimizer_failure_class,
            "component": "optimizer",
            "terminal": True,
        })
    if condition.stale_rule_strategy != condition.current_evidence_strategy:
        failure_events.append({
            "failure_id": "failure_strategy_rule_contradiction",
            "failure_class": "STRATEGY_RULE_CONTRADICTION",
            "component": "strategy",
            "terminal": False,
        })
    validity_status = (
        "invalid" if condition.invalid_strategy_targets else "valid"
    )
    content = {
        "schema_version": ATTACK_STATE_SCHEMA_VERSION,
        "condition_id": condition.condition_id,
        "knowledge_profile": knowledge,
        "canonical_facts": list(facts),
        "semantic_digest": semantic_digest,
        "strategies": [
            {
                "strategy_id": strategy_id,
                "applicability": (
                    f"Applicable only when fact_strategy_applicable_{strategy_id} "
                    "is true and the requested validity domain is valid."
                ),
                "required_tool": OPTIMIZER_ID,
                "failure_modes": [
                    "invalid_operating_point",
                    "insufficient_budget",
                    "optimizer_failure",
                ],
                "validity_domain_ids": [
                    f"{condition.operating_point_id}:{strategy_id}"
                ],
            }
            for strategy_id in STRATEGY_IDS
        ],
        "validity_domains": [
            {
                "validity_domain_id": (
                    f"{condition.operating_point_id}:{strategy_id}"
                ),
                "operating_point_ids": [condition.operating_point_id],
                "status": (
                    validity_status
                    if strategy_id == condition.expected_strategy_id
                    else "valid"
                ),
                "evidence_lane": "EVIDENCE_VALID",
            }
            for strategy_id in STRATEGY_IDS
        ],
        "failure_events": failure_events,
        "decision_lineage": [],
        "governance_separation": {
            "rka_exposed": False,
            "allowed_source_classes": [
                "development_fixture",
                "qualified_runtime_receipt",
            ],
        },
        "development_only": True,
        "evaluation_sealed": True,
    }
    state = canonical_copy(content)
    state["state_id"] = content_id("m29state_", content)
    return state


def render_flat_text(state: Mapping[str, Any]) -> dict[str, Any]:
    """Render canonical facts as deterministic flat text."""

    lines = [
        " | ".join((
            str(item["fact_id"]),
            str(item["subject"]),
            str(item["predicate"]),
            str(item["object"]),
            str(item["evidence_lane"]),
        ))
        for item in state["canonical_facts"]
    ]
    return {
        "representation": "flat_text",
        "condition_id": state["condition_id"],
        "semantic_digest": state["semantic_digest"],
        "text": "\n".join(lines),
    }


def render_structured_graph(state: Mapping[str, Any]) -> dict[str, Any]:
    """Render the same canonical facts as a relation list."""

    return {
        "representation": "structured_graph",
        "condition_id": state["condition_id"],
        "semantic_digest": state["semantic_digest"],
        "relations": [
            {
                "fact_id": item["fact_id"],
                "source": item["subject"],
                "relation": item["predicate"],
                "target": item["object"],
                "evidence_lane": item["evidence_lane"],
            }
            for item in state["canonical_facts"]
        ],
    }


def assert_representation_parity(
    flat: Mapping[str, Any], graph: Mapping[str, Any]
) -> None:
    if flat.get("semantic_digest") != graph.get("semantic_digest"):
        raise ContractViolation("M29 representation semantic digest mismatch")
    if flat.get("condition_id") != graph.get("condition_id"):
        raise ContractViolation("M29 representation condition mismatch")


def visible_history_digest(condition: M29Condition) -> str:
    return sha256_value(list(condition.visible_history))


def feedback_digest(condition: M29Condition) -> str:
    return sha256_value({
        "delay_windows": condition.feedback_delay_windows,
        "visible_history": list(condition.visible_history),
    })


def optimizer_source_sha256() -> str:
    """Return the exact byte identity shared by every optimizer-enabled arm."""

    return sha256_file(OPTIMIZER_SOURCE_PATH)


def build_optimization_request(
    condition: M29Condition, strategy_id: str, *, rationale: str,
    evidence_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compile one strategy choice into the strict deterministic tool request."""

    if strategy_id not in STRATEGY_IDS:
        raise ContractViolation("M29 optimizer request uses an unknown strategy")
    state = build_attack_state(condition)
    available_refs = [item["fact_id"] for item in state["canonical_facts"]]
    refs = list(evidence_refs) if evidence_refs is not None else available_refs[:16]
    if not refs or len(refs) > 16 or len(refs) != len(set(refs)):
        raise ContractViolation("M29 optimizer evidence refs are invalid")
    if not set(refs).issubset(available_refs):
        raise ContractViolation("M29 optimizer request cites an unavailable fact")
    content = {
        "schema_version": OPTIMIZATION_REQUEST_SCHEMA_VERSION,
        "condition_id": condition.condition_id,
        "strategy_id": strategy_id,
        "operating_point_id": condition.operating_point_id,
        "candidate_surface_id": FROZEN_CANDIDATE_SURFACE_ID,
        "attack_state_id": state["state_id"],
        "semantic_digest": state["semantic_digest"],
        "visible_history_digest": visible_history_digest(condition),
        "feedback_digest": feedback_digest(condition),
        "objective": {
            "metric": "synthetic_grid_stress_score",
            "direction": "maximize",
            "uncertainty_penalty": 0.0,
        },
        "constraints": {
            "allowed_target_ids": list(TARGET_IDS),
            "max_targets": 1,
            "p_kw_min": -30.0,
            "p_kw_max": 30.0,
            "q_kvar_min": -20.0,
            "q_kvar_max": 20.0,
            "remaining_window_budget": condition.remaining_window_budget,
            "remaining_energy_kvah": condition.remaining_energy_kvah,
            "validity_domain_id": (
                f"{condition.operating_point_id}:{strategy_id}"
            ),
        },
        "optimizer": {
            "optimizer_id": OPTIMIZER_ID,
            "source_sha256": optimizer_source_sha256(),
            "deterministic_seed": OPTIMIZER_SEED,
            "max_evaluations": 12,
        },
        "evidence_refs": refs,
        "environment_query_budget": 0,
        "evidence_lane": "EVIDENCE_VALID",
        "rationale": rationale.strip(),
    }
    request = canonical_copy(content)
    request["request_id"] = content_id("m29optreq_", content)
    validate_optimization_request(request, condition)
    return request


def validate_optimization_request(request: Mapping[str, Any],
                                  condition: M29Condition) -> None:
    expected = {
        "schema_version", "request_id", "condition_id", "strategy_id",
        "operating_point_id", "candidate_surface_id", "attack_state_id",
        "semantic_digest", "visible_history_digest", "feedback_digest",
        "objective", "constraints", "optimizer", "evidence_refs",
        "environment_query_budget", "evidence_lane", "rationale",
    }
    _require_exact_keys(request, expected, "OptimizationRequest")
    if request["schema_version"] != OPTIMIZATION_REQUEST_SCHEMA_VERSION:
        raise ContractViolation("M29 optimizer request schema drift")
    content = canonical_copy(request)
    stored_id = content.pop("request_id")
    if stored_id != content_id("m29optreq_", content):
        raise ContractViolation("M29 optimizer request content address drift")
    if request["condition_id"] != condition.condition_id:
        raise ContractViolation("M29 optimizer request condition drift")
    if request["strategy_id"] not in STRATEGY_IDS:
        raise ContractViolation("M29 optimizer request strategy drift")
    if request["candidate_surface_id"] != FROZEN_CANDIDATE_SURFACE_ID:
        raise ContractViolation("M29 optimizer request surface drift")
    state = build_attack_state(condition)
    if request["attack_state_id"] != state["state_id"]:
        raise ContractViolation("M29 optimizer request state drift")
    if request["semantic_digest"] != state["semantic_digest"]:
        raise ContractViolation("M29 optimizer request semantic digest drift")
    if request["visible_history_digest"] != visible_history_digest(condition):
        raise ContractViolation("M29 optimizer request history drift")
    if request["feedback_digest"] != feedback_digest(condition):
        raise ContractViolation("M29 optimizer request feedback drift")
    optimizer = request["optimizer"]
    if not isinstance(optimizer, Mapping):
        raise ContractViolation("M29 optimizer metadata must be an object")
    _require_exact_keys(
        optimizer,
        {"optimizer_id", "source_sha256", "deterministic_seed", "max_evaluations"},
        "OptimizationRequest.optimizer",
    )
    if optimizer != {
        "optimizer_id": OPTIMIZER_ID,
        "source_sha256": optimizer_source_sha256(),
        "deterministic_seed": OPTIMIZER_SEED,
        "max_evaluations": 12,
    }:
        raise ContractViolation("M29 optimizer metadata drift")
    constraints = request["constraints"]
    if not isinstance(constraints, Mapping):
        raise ContractViolation("M29 optimizer constraints must be an object")
    if constraints.get("remaining_window_budget") != condition.remaining_window_budget:
        raise ContractViolation("M29 optimizer window budget drift")
    if not math.isclose(
        float(constraints.get("remaining_energy_kvah", -1.0)),
        condition.remaining_energy_kvah,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ContractViolation("M29 optimizer energy budget drift")
    if request["environment_query_budget"] != 0:
        raise ContractViolation("M29 optimizer requested an environment query")
    rationale = request["rationale"]
    if not isinstance(rationale, str) or not rationale or len(rationale) > 1200:
        raise ContractViolation("M29 optimizer request rationale is invalid")
    refs = request["evidence_refs"]
    available = {item["fact_id"] for item in state["canonical_facts"]}
    if (
        not isinstance(refs, list)
        or not refs
        or len(refs) > 16
        or len(refs) != len(set(refs))
        or not set(refs).issubset(available)
    ):
        raise ContractViolation("M29 optimizer request evidence refs are invalid")


def run_optimizer(request: Mapping[str, Any],
                  condition: M29Condition) -> dict[str, Any]:
    """Run the pure deterministic search tool with zero environment queries."""

    validate_optimization_request(request, condition)
    status = "feasible"
    failure_class: str | None = None
    rows: list[dict[str, Any]] = []
    if condition.optimizer_mode == "tool_failure":
        status = "tool_failure"
        failure_class = condition.optimizer_failure_class
    else:
        library = build_candidate_library()
        candidates = [
            item for item in library.candidates
            if item.strategy_ids == (request["strategy_id"],)
        ]
        for item in candidates:
            target_id = item.target_ids[0]
            strategy_id = item.strategy_ids[0]
            feasible = candidate_is_feasible(condition, item)
            objective = (
                float(condition.target_scores[target_id])
                * float(condition.strategy_scores[strategy_id])
            )
            rows.append({
                "candidate_id": item.candidate_id,
                "strategy_id": strategy_id,
                "target_id": target_id,
                "p_kw": float(item.steps[0].actions[0].p_kw),
                "q_kvar": float(item.steps[0].actions[0].q_kvar),
                "objective_value": objective,
                "uncertainty": 0.0,
                "feasible": feasible,
                "validity_domain_id": (
                    f"{condition.operating_point_id}:{strategy_id}"
                ),
                "energy_kvah": candidate_energy_kvah(item),
            })
        rows.sort(key=lambda item: (
            not bool(item["feasible"]),
            -float(item["objective_value"]),
            str(item["candidate_id"]),
        ))
        for rank, item in enumerate(rows, start=1):
            item["rank"] = rank
        if not any(item["feasible"] for item in rows):
            status = "infeasible"
            failure_class = "NO_FEASIBLE_CANDIDATE"
    selected = next(
        (item["candidate_id"] for item in rows if item["feasible"]), None
    )
    semantic = {
        "request_id": request["request_id"],
        "status": status,
        "failure_class": failure_class,
        "ranked_candidates": rows,
        "selected_candidate_id": selected,
        "evaluations_used": len(rows),
        "optimizer_compute_units": len(rows),
        "environment_queries_used": 0,
    }
    content = {
        "schema_version": OPTIMIZER_RESULT_SCHEMA_VERSION,
        "request_id": request["request_id"],
        "optimizer_id": OPTIMIZER_ID,
        "optimizer_source_sha256": optimizer_source_sha256(),
        "status": status,
        "failure_class": failure_class,
        "ranked_candidates": rows,
        "selected_candidate_id": selected,
        "evaluations_used": len(rows),
        "optimizer_compute_units": len(rows),
        "environment_queries_used": 0,
        "wall_clock_ms": 0.0,
        "result_semantic_digest": sha256_value(semantic),
    }
    result = canonical_copy(content)
    result["result_id"] = content_id("m29optres_", content)
    validate_optimizer_result(result, request)
    return result


def validate_optimizer_result(result: Mapping[str, Any],
                              request: Mapping[str, Any]) -> None:
    expected = {
        "schema_version", "result_id", "request_id", "optimizer_id",
        "optimizer_source_sha256", "status", "failure_class",
        "ranked_candidates", "selected_candidate_id", "evaluations_used",
        "optimizer_compute_units", "environment_queries_used",
        "wall_clock_ms", "result_semantic_digest",
    }
    _require_exact_keys(result, expected, "OptimizerResult")
    if result["schema_version"] != OPTIMIZER_RESULT_SCHEMA_VERSION:
        raise ContractViolation("M29 optimizer result schema drift")
    content = canonical_copy(result)
    stored_id = content.pop("result_id")
    if stored_id != content_id("m29optres_", content):
        raise ContractViolation("M29 optimizer result content address drift")
    if result["request_id"] != request["request_id"]:
        raise ContractViolation("M29 optimizer result request drift")
    if result["optimizer_id"] != OPTIMIZER_ID:
        raise ContractViolation("M29 optimizer result identity drift")
    if result["optimizer_source_sha256"] != optimizer_source_sha256():
        raise ContractViolation("M29 optimizer result source drift")
    if result["environment_queries_used"] != 0:
        raise ContractViolation("M29 optimizer consumed an environment query")
    if result["status"] == "feasible" and result["selected_candidate_id"] is None:
        raise ContractViolation("M29 feasible result has no candidate")
    if result["status"] != "feasible" and result["selected_candidate_id"] is not None:
        raise ContractViolation("M29 failed result selected a candidate")


def deterministic_strategy(condition: M29Condition) -> str:
    """Frozen non-LLM meta-policy used by IA2 and IA3-O."""

    preferred = condition.current_evidence_strategy
    if preferred in condition.applicable_strategies:
        probe = candidate_for(preferred, "DER_A")
        if candidate_energy_kvah(probe) <= condition.remaining_energy_kvah + 1e-12:
            return preferred
    feasible_strategies = []
    for strategy_id in STRATEGY_IDS:
        if strategy_id not in condition.applicable_strategies:
            continue
        if any(candidate_is_feasible(
            condition, candidate_for(strategy_id, target_id)
        ) for target_id in TARGET_IDS):
            feasible_strategies.append(strategy_id)
    if not feasible_strategies:
        return preferred
    return max(
        feasible_strategies,
        key=lambda item: (float(condition.strategy_scores[item]), -STRATEGY_IDS.index(item)),
    )


def deterministic_target(condition: M29Condition, strategy_id: str) -> str | None:
    feasible = [
        target_id for target_id in TARGET_IDS
        if candidate_is_feasible(condition, candidate_for(strategy_id, target_id))
    ]
    if not feasible:
        return None
    return max(
        feasible,
        key=lambda item: (float(condition.target_scores[item]), -TARGET_IDS.index(item)),
    )


def _rung_for_arm(arm_id: str) -> OrchestrationRung:
    if arm_id == "IA2":
        return OrchestrationRung.IA2
    if arm_id == "IA3-O":
        return OrchestrationRung.IA3
    if arm_id in {"IA4-D", "IA4-H", "IA4-HG"}:
        return OrchestrationRung.IA4
    raise ContractViolation(f"unknown M29 arm: {arm_id}")


def build_profile(arm_id: str, condition: M29Condition) -> CapabilityProfile:
    return CapabilityProfile(
        profile_id=f"m29_{arm_id}_{condition.condition_id}",
        rung=_rung_for_arm(arm_id),
        knowledge=KnowledgeProfile(
            grid=InformationLevel.PARTIAL,
            feedback=InformationLevel.PARTIAL,
        ),
        authority=AuthorityProfile(
            allowed_devices=frozenset(TARGET_IDS),
            allow_active_power=True,
            allow_reactive_power=True,
            max_targets_per_plan=1,
            perturbed_window_cap=condition.remaining_window_budget,
            apparent_energy_cap_kvah=condition.remaining_energy_kvah,
            feedback_delay_windows=condition.feedback_delay_windows,
        ),
        allowed_strategy_ids=frozenset(STRATEGY_IDS),
        allowed_tool_names=frozenset(),
        tool_call_cap=0,
        outer_rollout_cap=0,
        history_limit=4,
        candidate_count_cap=6,
        max_strategies_per_plan=1,
    )


def validate_candidate(
    *, arm_id: str, condition: M29Condition, candidate_id: str,
    rationale: str, optimizer_result_id: str | None,
) -> dict[str, Any]:
    """Apply the one M29 wrapper and base PlanValidator before any admission."""

    library = build_candidate_library()
    try:
        candidate = library.get(candidate_id)
    except ContractViolation as exc:
        return {
            "common_validator_id": COMMON_VALIDATOR_ID,
            "accepted": False,
            "effective_decision": False,
            "reason": str(exc),
            "optimizer_result_id": optimizer_result_id,
            "base_validation": None,
        }
    if not candidate_is_feasible(condition, candidate):
        return {
            "common_validator_id": COMMON_VALIDATOR_ID,
            "accepted": False,
            "effective_decision": False,
            "reason": "candidate_outside_fixture_validity_or_budget",
            "optimizer_result_id": optimizer_result_id,
            "base_validation": None,
        }
    profile = build_profile(arm_id, condition)
    plan = candidate.instantiate(profile.rung, rationale.strip() or "M29 decision.")
    decision = ControllerDecision.submit(
        plan,
        reason="m29_typed_candidate_plan",
        candidate_id=candidate.candidate_id,
    )
    validator = PlanValidator(
        profile=profile,
        strategy_library=build_strategy_library(),
        tool_contract=ToolContract(()),
        dual_budget=DualBudget(
            window_cap=condition.remaining_window_budget,
            apparent_energy_cap_kvah=condition.remaining_energy_kvah,
            window_seconds=10.0,
        ),
    )
    outcome = validator.evaluate(
        decision,
        benign={target_id: (0.0, 0.0) for target_id in TARGET_IDS},
    )
    return {
        "common_validator_id": COMMON_VALIDATOR_ID,
        "accepted": outcome.accepted,
        "effective_decision": outcome.effective_action,
        "reason": outcome.reason,
        "optimizer_result_id": optimizer_result_id,
        "base_validation": outcome.to_dict(),
    }


def candidate_metadata(candidate_id: str) -> dict[str, Any]:
    candidate = build_candidate_library().get(candidate_id)
    return {
        "candidate_id": candidate.candidate_id,
        "strategy_id": candidate.strategy_ids[0],
        "target_id": candidate.target_ids[0],
        "energy_kvah": candidate_energy_kvah(candidate),
    }


def oracle_candidate(condition: M29Condition) -> str | None:
    if condition.expected_strategy_id is None or condition.expected_target_id is None:
        return None
    item = candidate_for(condition.expected_strategy_id, condition.expected_target_id)
    return item.candidate_id if candidate_is_feasible(condition, item) else None


def fixture_regret(condition: M29Condition,
                   selected_candidate_id: str | None) -> float | None:
    feasible = [
        item for item in build_candidate_library().candidates
        if candidate_is_feasible(condition, item)
    ]
    if not feasible:
        return 0.0 if selected_candidate_id is None else None
    oracle_score = max(
        float(condition.target_scores[item.target_ids[0]])
        * float(condition.strategy_scores[item.strategy_ids[0]])
        for item in feasible
    )
    if selected_candidate_id is None:
        return oracle_score
    selected = candidate_metadata(selected_candidate_id)
    selected_score = (
        float(condition.target_scores[selected["target_id"]])
        * float(condition.strategy_scores[selected["strategy_id"]])
    )
    return max(0.0, oracle_score - selected_score)
