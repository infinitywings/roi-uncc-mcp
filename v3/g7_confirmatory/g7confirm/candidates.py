"""Deterministic bounded candidate spaces for capability-matched controllers."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .budget import Command, DualBudget
from .orchestration_contract import (
    CapabilityProfile,
    ContractViolation,
    NumericParameterSpec,
    OrchestrationRung,
    ParameterValue,
    PlanAction,
    StrategyCard,
    StrategyLibrary,
    StrategyStep,
    TypedPlan,
    candidate_id_for_steps,
)


CANDIDATE_RECEIPT_SCHEMA_VERSION = "grideval-g7-candidate-space-receipt/v1"


@dataclass(frozen=True)
class CandidateGenerationSpec:
    """Finite design and overflow policy for one shared candidate space."""

    candidate_cap: int
    enumeration_cap: int
    parameter_fractions: tuple[float, ...] = (0.0, 0.5, 1.0)
    action_fractions: tuple[float, ...] = (0.0, 0.5, 1.0)
    composition_orders: tuple[int, ...] = (1, 2)
    selection_seed: str = "grideval-g7-candidate-space-v1"
    include_card_defaults: bool = True

    def __post_init__(self) -> None:
        if int(self.candidate_cap) <= 0:
            raise ContractViolation("candidate_cap must be positive")
        if int(self.enumeration_cap) < int(self.candidate_cap):
            raise ContractViolation("enumeration_cap must be at least candidate_cap")
        self._validate_fractions(self.parameter_fractions, "parameter_fractions")
        self._validate_fractions(self.action_fractions, "action_fractions")
        if not self.composition_orders:
            raise ContractViolation("composition_orders cannot be empty")
        if tuple(sorted(set(self.composition_orders))) != self.composition_orders:
            raise ContractViolation(
                "composition_orders must be unique and strictly increasing"
            )
        if self.composition_orders[0] != 1:
            raise ContractViolation("composition_orders must include singleton order 1")
        if any(int(order) <= 0 for order in self.composition_orders):
            raise ContractViolation("composition orders must be positive")
        if not self.selection_seed:
            raise ContractViolation("selection_seed is required")

    @staticmethod
    def _validate_fractions(values: tuple[float, ...], name: str) -> None:
        if not values:
            raise ContractViolation(f"{name} cannot be empty")
        numeric = tuple(float(item) for item in values)
        if any(not math.isfinite(item) for item in numeric):
            raise ContractViolation(f"{name} must be finite")
        if any(item < 0.0 or item > 1.0 for item in numeric):
            raise ContractViolation(f"{name} must lie in [0, 1]")
        if tuple(sorted(set(numeric))) != numeric:
            raise ContractViolation(f"{name} must be unique and strictly increasing")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_cap": self.candidate_cap,
            "enumeration_cap": self.enumeration_cap,
            "parameter_fractions": list(self.parameter_fractions),
            "action_fractions": list(self.action_fractions),
            "composition_orders": list(self.composition_orders),
            "selection_seed": self.selection_seed,
            "include_card_defaults": self.include_card_defaults,
            "overflow_policy": "required_defaults_then_stratified_hash_round_robin",
        }


@dataclass(frozen=True)
class CandidateTemplate:
    """A rung-independent, content-addressed fully specified plan template."""

    steps: tuple[StrategyStep, ...]
    origins: frozenset[str]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ContractViolation("candidate template requires at least one step")
        if not self.origins:
            raise ContractViolation("candidate template requires at least one origin")
        strategy_ids = [step.strategy_id for step in self.steps]
        if len(strategy_ids) != len(set(strategy_ids)):
            raise ContractViolation("candidate contains duplicate strategy steps")
        if strategy_ids != sorted(strategy_ids):
            raise ContractViolation("candidate strategy steps must use canonical order")
        for step in self.steps:
            parameter_names = [item.name for item in step.parameters]
            if parameter_names != sorted(parameter_names):
                raise ContractViolation(
                    "candidate parameters must use canonical name order"
                )
            device_ids = [item.device_id for item in step.actions]
            if device_ids != sorted(device_ids):
                raise ContractViolation(
                    "candidate actions must use canonical device order"
                )
        devices = [
            action.device_id
            for step in self.steps
            for action in step.actions
        ]
        if len(devices) != len(set(devices)):
            raise ContractViolation("candidate contains overlapping device actions")

    @property
    def candidate_id(self) -> str:
        return candidate_id_for_steps(self.steps)

    @property
    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(step.strategy_id for step in self.steps)

    @property
    def target_ids(self) -> tuple[str, ...]:
        return tuple(sorted(
            action.device_id
            for step in self.steps
            for action in step.actions
        ))

    @property
    def coverage_group(self) -> str:
        assignments: list[str] = []
        for step in self.steps:
            targets = ",".join(sorted(
                action.device_id for action in step.actions
            ))
            assignments.append(f"{step.strategy_id}@{targets}")
        return f"order{len(self.steps)}:{'+'.join(assignments)}"

    def canonical_payload(self) -> dict[str, Any]:
        return {"steps": [step.to_dict() for step in self.steps]}

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "origins": sorted(self.origins),
            "composition_order": len(self.steps),
            "strategy_ids": list(self.strategy_ids),
            "target_ids": list(self.target_ids),
            **self.canonical_payload(),
        }

    def instantiate(self, rung: OrchestrationRung, rationale: str) -> TypedPlan:
        return TypedPlan(source_rung=rung, steps=self.steps, rationale=rationale)


class CandidateLibrary:
    """Immutable shared candidate surface for IA3 and future IA4."""

    def __init__(self, candidates: Iterable[CandidateTemplate]):
        ordered = tuple(candidates)
        if not ordered:
            raise ContractViolation("candidate library cannot be empty")
        ids = [item.candidate_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise ContractViolation("candidate library contains duplicate IDs")
        self._candidates = ordered
        self._by_id = {item.candidate_id: item for item in ordered}

    @property
    def candidates(self) -> tuple[CandidateTemplate, ...]:
        return self._candidates

    def get(self, candidate_id: str) -> CandidateTemplate:
        try:
            return self._by_id[candidate_id]
        except KeyError as exc:
            raise ContractViolation(f"unknown candidate_id: {candidate_id}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(item.candidate_id for item in self._candidates)

    def surface_payload(self) -> tuple[dict[str, Any], ...]:
        """Return the exact ordered candidate content visible to decision cores."""

        return tuple({
            "candidate_id": item.candidate_id,
            "composition_order": len(item.steps),
            "strategy_ids": list(item.strategy_ids),
            "target_ids": list(item.target_ids),
            **item.canonical_payload(),
        } for item in self._candidates)

    def fingerprint(self) -> str:
        payload = [
            {"candidate_id": item["candidate_id"], "steps": item["steps"]}
            for item in self.surface_payload()
        ]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()

    def coverage_summary(self) -> dict[str, Any]:
        return {
            "candidate_count": len(self._candidates),
            "strategy_ids": sorted({
                strategy_id
                for item in self._candidates
                for strategy_id in item.strategy_ids
            }),
            "target_ids": sorted({
                target_id
                for item in self._candidates
                for target_id in item.target_ids
            }),
            "composition_orders": sorted({
                len(item.steps) for item in self._candidates
            }),
            "coverage_groups": sorted({
                item.coverage_group for item in self._candidates
            }),
        }


def assert_candidate_library_parity(left: CandidateLibrary,
                                    right: CandidateLibrary) -> None:
    """Fail unless two decision cores receive identical ordered candidates."""

    if left.fingerprint() != right.fingerprint():
        raise ContractViolation("candidate-library parity mismatch")


@dataclass(frozen=True)
class CandidateRewardSpec:
    """A finite preregistered scalar objective for candidate credit assignment."""

    metric_name: str
    minimum: float
    maximum: float
    direction: str = "maximize"

    def __post_init__(self) -> None:
        if not self.metric_name:
            raise ContractViolation("reward metric_name is required")
        if self.direction not in {"maximize", "minimize"}:
            raise ContractViolation("reward direction must be maximize or minimize")
        lower, upper = float(self.minimum), float(self.maximum)
        if not math.isfinite(lower) or not math.isfinite(upper):
            raise ContractViolation("reward bounds must be finite")
        if lower >= upper:
            raise ContractViolation("reward minimum must be below maximum")

    def objective_value(self, raw_reward: float) -> float:
        if isinstance(raw_reward, bool) or not isinstance(raw_reward, (int, float)):
            raise ContractViolation("candidate reward must be numeric")
        value = float(raw_reward)
        lower, upper = float(self.minimum), float(self.maximum)
        if not math.isfinite(value):
            raise ContractViolation("candidate reward must be finite")
        if value < lower or value > upper:
            raise ContractViolation("candidate reward is outside preregistered bounds")
        normalized = (value - lower) / (upper - lower)
        return normalized if self.direction == "maximize" else 1.0 - normalized

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "minimum": float(self.minimum),
            "maximum": float(self.maximum),
            "direction": self.direction,
            "missing_reward_policy": "no_credit_update",
        }

    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def assert_reward_spec_parity(left: CandidateRewardSpec,
                              right: CandidateRewardSpec) -> None:
    if left.fingerprint() != right.fingerprint():
        raise ContractViolation("candidate-reward parity mismatch")


@dataclass(frozen=True)
class CandidateGenerationReceipt:
    spec: CandidateGenerationSpec
    raw_candidate_count: int
    retained_candidate_count: int
    raw_group_counts: Mapping[str, int]
    retained_group_counts: Mapping[str, int]
    required_default_ids: tuple[str, ...]
    candidate_library_fingerprint: str
    coverage: Mapping[str, Any]
    schema_version: str = CANDIDATE_RECEIPT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "development_only": True,
            "campaign_authorized": False,
            "evaluation_sealed": True,
            "spec": self.spec.to_dict(),
            "raw_candidate_count": self.raw_candidate_count,
            "retained_candidate_count": self.retained_candidate_count,
            "truncated": self.raw_candidate_count > self.retained_candidate_count,
            "raw_group_counts": dict(sorted(self.raw_group_counts.items())),
            "retained_group_counts": dict(
                sorted(self.retained_group_counts.items())
            ),
            "required_default_ids": list(self.required_default_ids),
            "candidate_library_fingerprint": self.candidate_library_fingerprint,
            "coverage": dict(self.coverage),
        }


def generate_candidate_library(
        *, profile: CapabilityProfile, strategy_library: StrategyLibrary,
        benign_commands: Mapping[str, Command],
        spec: CandidateGenerationSpec) -> tuple[
            CandidateLibrary, CandidateGenerationReceipt
        ]:
    """Enumerate, validate, and reproducibly retain a bounded candidate space."""

    if spec.candidate_cap != profile.candidate_count_cap:
        raise ContractViolation(
            "candidate_cap must equal the capability profile candidate_count_cap"
        )
    if max(spec.composition_orders) > profile.max_strategies_per_plan:
        raise ContractViolation(
            "composition order exceeds profile max_strategies_per_plan"
        )
    missing_cards = set(profile.allowed_strategy_ids) - set(strategy_library.ids())
    if missing_cards:
        raise ContractViolation(
            f"profile references strategies absent from library: {sorted(missing_cards)}"
        )
    benign = _canonical_benign(profile, benign_commands)
    unique: dict[str, CandidateTemplate] = {}
    required_default_ids: set[str] = set()

    def add_candidate(candidate: CandidateTemplate, *, required: bool = False) -> None:
        _validate_candidate(candidate, profile, strategy_library, benign)
        candidate_id = candidate.candidate_id
        existing = unique.get(candidate_id)
        if existing is None:
            unique[candidate_id] = candidate
            if len(unique) > spec.enumeration_cap:
                raise ContractViolation(
                    "candidate enumeration_cap exceeded; narrow the declared grid"
                )
        elif existing.origins != candidate.origins:
            unique[candidate_id] = CandidateTemplate(
                steps=existing.steps,
                origins=existing.origins | candidate.origins,
            )
        if required:
            required_default_ids.add(candidate_id)

    cards = [
        strategy_library.get(strategy_id)
        for strategy_id in sorted(profile.allowed_strategy_ids)
    ]
    impossible_orders = [
        order for order in spec.composition_orders if order > len(cards)
    ]
    if impossible_orders:
        raise ContractViolation(
            f"composition orders exceed distinct strategy count: {impossible_orders}"
        )
    for card in cards:
        eligible_targets = sorted(
            card.eligible_devices & profile.authority.allowed_devices
        )
        if not eligible_targets:
            raise ContractViolation(
                f"strategy has no authorized eligible target: {card.strategy_id}"
            )
        default_step = _authority_adjusted_default(card, profile, benign)
        if spec.include_card_defaults and default_step is not None:
            add_candidate(
                CandidateTemplate(
                    steps=(default_step,), origins=frozenset({"card_default"})
                ),
                required=True,
            )
        parameter_sets = _parameter_grid(card.parameter_specs, spec)
        fallback_action = card.default_actions[0]
        defaults_by_target = {
            action.device_id: action for action in card.default_actions
        }
        for target_id in eligible_targets:
            default_action = defaults_by_target.get(target_id, fallback_action)
            base_p, base_q = benign[target_id]
            p_values = (
                _bounded_values(
                    card.p_kw_bounds, spec.action_fractions, default_action.p_kw
                )
                if profile.authority.allow_active_power else (base_p,)
            )
            q_values = (
                _bounded_values(
                    card.q_kvar_bounds, spec.action_fractions, default_action.q_kvar
                )
                if profile.authority.allow_reactive_power else (base_q,)
            )
            for parameters, p_kw, q_kvar in itertools.product(
                    parameter_sets, p_values, q_values):
                step = StrategyStep(
                    strategy_id=card.strategy_id,
                    parameters=parameters,
                    actions=(PlanAction(target_id, p_kw, q_kvar),),
                )
                add_candidate(CandidateTemplate(
                    steps=(step,), origins=frozenset({"factorial_grid"})
                ))
        maximum_targets = min(
            profile.authority.max_targets_per_plan,
            len(eligible_targets),
        )
        for target_count in range(2, maximum_targets + 1):
            for target_ids in itertools.combinations(
                    eligible_targets, target_count):
                actions: list[PlanAction] = []
                for target_id in target_ids:
                    default_action = defaults_by_target.get(
                        target_id, fallback_action
                    )
                    base_p, base_q = benign[target_id]
                    actions.append(PlanAction(
                        target_id,
                        (default_action.p_kw
                         if profile.authority.allow_active_power else base_p),
                        (default_action.q_kvar
                         if profile.authority.allow_reactive_power else base_q),
                    ))
                step = StrategyStep(
                    strategy_id=card.strategy_id,
                    parameters=tuple(
                        ParameterValue(item.name, item.default)
                        for item in card.parameter_specs
                    ),
                    actions=tuple(actions),
                )
                add_candidate(CandidateTemplate(
                    steps=(step,), origins=frozenset({"target_set_default"})
                ))

    singletons = tuple(
        item for item in unique.values() if len(item.steps) == 1
    )
    for order in spec.composition_orders:
        if order == 1:
            continue
        for parts in itertools.combinations(singletons, order):
            strategy_ids = [part.steps[0].strategy_id for part in parts]
            if len(strategy_ids) != len(set(strategy_ids)):
                continue
            devices = [
                action.device_id
                for part in parts
                for action in part.steps[0].actions
            ]
            if len(devices) != len(set(devices)):
                continue
            if len(devices) > profile.authority.max_targets_per_plan:
                continue
            steps = tuple(sorted(
                (part.steps[0] for part in parts),
                key=lambda item: item.strategy_id,
            ))
            add_candidate(CandidateTemplate(
                steps=steps, origins=frozenset({"composition_grid"})
            ))

    selected = _select_candidates(
        candidates=tuple(unique.values()),
        required_default_ids=required_default_ids,
        spec=spec,
    )
    library = CandidateLibrary(selected)
    receipt = CandidateGenerationReceipt(
        spec=spec,
        raw_candidate_count=len(unique),
        retained_candidate_count=len(selected),
        raw_group_counts=_group_counts(unique.values()),
        retained_group_counts=_group_counts(selected),
        required_default_ids=tuple(sorted(required_default_ids)),
        candidate_library_fingerprint=library.fingerprint(),
        coverage=library.coverage_summary(),
    )
    return library, receipt


def _canonical_benign(profile: CapabilityProfile,
                      commands: Mapping[str, Command]) -> dict[str, Command]:
    benign: dict[str, Command] = {}
    for device_id in sorted(profile.authority.allowed_devices):
        if device_id not in commands:
            raise ContractViolation(f"missing benign command for {device_id}")
        benign[device_id] = DualBudget._coerce(commands[device_id], device_id)
    return benign


def _authority_adjusted_default(card: StrategyCard, profile: CapabilityProfile,
                                benign: Mapping[str, Command]) -> StrategyStep | None:
    actions: list[PlanAction] = []
    for action in card.default_actions:
        if action.device_id not in profile.authority.allowed_devices:
            return None
        base_p, base_q = benign[action.device_id]
        actions.append(PlanAction(
            action.device_id,
            action.p_kw if profile.authority.allow_active_power else base_p,
            action.q_kvar if profile.authority.allow_reactive_power else base_q,
        ))
    step = StrategyStep(
        strategy_id=card.strategy_id,
        parameters=tuple(
            ParameterValue(item.name, item.default)
            for item in card.parameter_specs
        ),
        actions=tuple(actions),
    )
    try:
        card.validate_step(step)
    except ContractViolation:
        return None
    return step


def _parameter_grid(specs: Iterable[NumericParameterSpec],
                    generation: CandidateGenerationSpec) -> tuple[
                        tuple[ParameterValue, ...], ...
                    ]:
    ordered = tuple(specs)
    if not ordered:
        return ((),)
    axes = [
        _bounded_values(
            (item.minimum, item.maximum),
            generation.parameter_fractions,
            item.default,
        )
        for item in ordered
    ]
    return tuple(
        tuple(ParameterValue(item.name, value)
              for item, value in zip(ordered, values))
        for values in itertools.product(*axes)
    )


def _bounded_values(bounds: tuple[float, float], fractions: tuple[float, ...],
                    default: float) -> tuple[float, ...]:
    lower, upper = float(bounds[0]), float(bounds[1])
    values = [lower + (upper - lower) * fraction for fraction in fractions]
    values.append(float(default))
    return tuple(sorted(set(values)))


def _validate_candidate(candidate: CandidateTemplate,
                        profile: CapabilityProfile,
                        strategy_library: StrategyLibrary,
                        benign: Mapping[str, Command]) -> None:
    if len(candidate.steps) > profile.max_strategies_per_plan:
        raise ContractViolation("candidate exceeds max_strategies_per_plan")
    commands: dict[str, Command] = {}
    for step in candidate.steps:
        if step.strategy_id not in profile.allowed_strategy_ids:
            raise ContractViolation("candidate uses a disallowed strategy")
        strategy_library.get(step.strategy_id).validate_step(step)
        for action in step.actions:
            if action.device_id not in profile.authority.allowed_devices:
                raise ContractViolation("candidate targets an unauthorized device")
            if action.device_id in commands:
                raise ContractViolation("candidate has overlapping device actions")
            base_p, base_q = benign[action.device_id]
            if (not profile.authority.allow_active_power and
                    not math.isclose(action.p_kw, base_p, abs_tol=1e-9)):
                raise ContractViolation("candidate exceeds active-power authority")
            if (not profile.authority.allow_reactive_power and
                    not math.isclose(action.q_kvar, base_q, abs_tol=1e-9)):
                raise ContractViolation("candidate exceeds reactive-power authority")
            commands[action.device_id] = action.command()
    if len(commands) > profile.authority.max_targets_per_plan:
        raise ContractViolation("candidate exceeds max_targets_per_plan")


def _selection_rank(candidate: CandidateTemplate, seed: str) -> str:
    return hashlib.sha256(
        f"{seed}:{candidate.candidate_id}".encode("utf-8")
    ).hexdigest()


def _select_candidates(*, candidates: tuple[CandidateTemplate, ...],
                       required_default_ids: set[str],
                       spec: CandidateGenerationSpec) -> tuple[CandidateTemplate, ...]:
    by_id = {item.candidate_id: item for item in candidates}
    if not required_default_ids.issubset(by_id):
        raise ContractViolation("required default candidate is missing")
    rank_key = lambda item: (_selection_rank(item, spec.selection_seed),
                             item.candidate_id)
    if len(candidates) <= spec.candidate_cap:
        return tuple(sorted(candidates, key=rank_key))
    if len(required_default_ids) > spec.candidate_cap:
        raise ContractViolation("candidate_cap cannot retain all required defaults")

    selected_ids = set(required_default_ids)
    groups: dict[str, list[CandidateTemplate]] = {}
    for item in candidates:
        if item.candidate_id not in selected_ids:
            groups.setdefault(item.coverage_group, []).append(item)
    for values in groups.values():
        values.sort(key=rank_key)

    covered = {by_id[item].coverage_group for item in selected_ids}
    uncovered = [name for name in sorted(groups) if name not in covered]
    if len(selected_ids) + len(uncovered) > spec.candidate_cap:
        raise ContractViolation(
            "candidate_cap is too small to retain every coverage group"
        )
    for group_name in uncovered:
        selected_ids.add(groups[group_name].pop(0).candidate_id)

    group_names = sorted(groups)
    while len(selected_ids) < spec.candidate_cap:
        progressed = False
        for group_name in group_names:
            pool = groups[group_name]
            while pool and pool[0].candidate_id in selected_ids:
                pool.pop(0)
            if not pool:
                continue
            selected_ids.add(pool.pop(0).candidate_id)
            progressed = True
            if len(selected_ids) == spec.candidate_cap:
                break
        if not progressed:
            break
    if len(selected_ids) != spec.candidate_cap:
        raise ContractViolation("candidate selection failed to fill candidate_cap")
    return tuple(sorted((by_id[item] for item in selected_ids), key=rank_key))


def _group_counts(candidates: Iterable[CandidateTemplate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in candidates:
        counts[item.coverage_group] = counts.get(item.coverage_group, 0) + 1
    return counts
