"""Deterministic offline reference controllers for IA0 through IA3."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from .candidates import CandidateLibrary, CandidateRewardSpec
from .orchestration_contract import (
    CapabilityProfile,
    ContractViolation,
    ControllerDecision,
    OrchestrationRung,
    OutcomeRecord,
    StrategyLibrary,
    TypedObservation,
    bounded_visible_history,
)


class Orchestrator(Protocol):
    """The interface shared by reference and future LLM decision cores."""

    profile: CapabilityProfile

    def decide(self, observation: TypedObservation,
               history: Sequence[OutcomeRecord]) -> ControllerDecision:
        ...


class _ReferenceOrchestrator:
    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary,
                 expected_rung: OrchestrationRung):
        if profile.rung is not expected_rung:
            raise ContractViolation(
                f"profile rung must be {expected_rung.value}, got {profile.rung.value}"
            )
        missing = set(profile.allowed_strategy_ids) - set(strategy_library.ids())
        if missing:
            raise ContractViolation(
                f"profile references strategies absent from library: {sorted(missing)}"
            )
        self.profile = profile
        self.strategy_library = strategy_library

    def _card_decision(self, strategy_id: str, rationale: str) -> ControllerDecision:
        if strategy_id not in self.profile.allowed_strategy_ids:
            raise ContractViolation(f"strategy is not allowed: {strategy_id}")
        card = self.strategy_library.get(strategy_id)
        return ControllerDecision.submit(
            card.instantiate(self.profile.rung, rationale),
            reason="typed_strategy_plan",
        )

    def _bounded_history(self, history: Sequence[OutcomeRecord], *,
                         current_window: int) -> Sequence[OutcomeRecord]:
        return bounded_visible_history(
            self.profile, current_window=current_window, history=history
        )


class IA0StaticFrozen(_ReferenceOrchestrator):
    """Replay a frozen window-to-strategy schedule without reading feedback."""

    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary,
                 schedule: Mapping[int, str]):
        super().__init__(
            profile=profile,
            strategy_library=strategy_library,
            expected_rung=OrchestrationRung.IA0,
        )
        if any(int(window) < 0 for window in schedule):
            raise ContractViolation("IA0 schedule windows must be non-negative")
        for strategy_id in schedule.values():
            if strategy_id not in profile.allowed_strategy_ids:
                raise ContractViolation(f"IA0 schedule uses disallowed strategy: {strategy_id}")
        self.schedule = {int(window): strategy_id for window, strategy_id in schedule.items()}

    def decide(self, observation: TypedObservation,
               history: Sequence[OutcomeRecord]) -> ControllerDecision:
        del history
        strategy_id = self.schedule.get(observation.window)
        if strategy_id is None:
            return ControllerDecision.no_action("outside_frozen_schedule")
        return self._card_decision(
            strategy_id,
            rationale=f"Replay frozen IA0 schedule at window {observation.window}.",
        )


class IA1LibraryOpenLoop(_ReferenceOrchestrator):
    """Choose one frozen card before the episode and never switch it."""

    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary, strategy_id: str):
        super().__init__(
            profile=profile,
            strategy_library=strategy_library,
            expected_rung=OrchestrationRung.IA1,
        )
        if strategy_id not in profile.allowed_strategy_ids:
            raise ContractViolation(f"IA1 selected a disallowed strategy: {strategy_id}")
        self.strategy_id = strategy_id

    def decide(self, observation: TypedObservation,
               history: Sequence[OutcomeRecord]) -> ControllerDecision:
        del observation, history
        return self._card_decision(
            self.strategy_id,
            rationale="Use the frozen IA1 open-loop strategy selection.",
        )


class FixedMaximumPowerComparator(IA1LibraryOpenLoop):
    """Explicit hand-crafted static comparator for fixed maximum-power behavior."""

    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary, strategy_id: str):
        card = strategy_library.get(strategy_id)
        if not card.fixed_maximum_power:
            raise ContractViolation(
                "fixed maximum-power comparator requires a card marked fixed_maximum_power"
            )
        super().__init__(
            profile=profile,
            strategy_library=strategy_library,
            strategy_id=strategy_id,
        )


@dataclass(frozen=True)
class RoutingRule:
    """One frozen scalar predicate used by the deterministic IA2 router."""

    field_name: str
    operator_name: str
    threshold: float
    strategy_id: str

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ContractViolation("routing rule field_name is required")
        if self.operator_name not in {"lt", "lte", "gt", "gte", "eq"}:
            raise ContractViolation(f"unsupported routing operator: {self.operator_name}")
        if not math.isfinite(float(self.threshold)):
            raise ContractViolation("routing threshold must be finite")
        if not self.strategy_id:
            raise ContractViolation("routing rule strategy_id is required")

    def matches(self, observation: TypedObservation) -> bool:
        value = observation.numeric(self.field_name)
        if value is None:
            return False
        threshold = float(self.threshold)
        if self.operator_name == "lt":
            return value < threshold
        if self.operator_name == "lte":
            return value <= threshold
        if self.operator_name == "gt":
            return value > threshold
        if self.operator_name == "gte":
            return value >= threshold
        return math.isclose(value, threshold, rel_tol=0.0, abs_tol=1e-12)


class IA2RuleInteractive(_ReferenceOrchestrator):
    """Switch cards using a frozen, ordered rule table over typed feedback."""

    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary,
                 rules: Sequence[RoutingRule], default_strategy_id: str):
        super().__init__(
            profile=profile,
            strategy_library=strategy_library,
            expected_rung=OrchestrationRung.IA2,
        )
        if default_strategy_id not in profile.allowed_strategy_ids:
            raise ContractViolation("IA2 default strategy is not allowed")
        for rule in rules:
            if rule.strategy_id not in profile.allowed_strategy_ids:
                raise ContractViolation(
                    f"IA2 routing rule uses disallowed strategy: {rule.strategy_id}"
                )
        self.rules = tuple(rules)
        self.default_strategy_id = default_strategy_id

    def decide(self, observation: TypedObservation,
               history: Sequence[OutcomeRecord]) -> ControllerDecision:
        del history
        selected = self.default_strategy_id
        matched_rule: RoutingRule | None = None
        for rule in self.rules:
            if rule.matches(observation):
                selected = rule.strategy_id
                matched_rule = rule
                break
        rationale = (
            f"IA2 rule {matched_rule.field_name} {matched_rule.operator_name} "
            f"{matched_rule.threshold} selected {selected}."
            if matched_rule else f"IA2 default route selected {selected}."
        )
        return self._card_decision(selected, rationale=rationale)


class IA3UCBAdaptive(_ReferenceOrchestrator):
    """A deterministic UCB1 strategy selector over bounded prior outcomes."""

    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary,
                 exploration_weight: float = math.sqrt(2.0)):
        super().__init__(
            profile=profile,
            strategy_library=strategy_library,
            expected_rung=OrchestrationRung.IA3,
        )
        if not math.isfinite(float(exploration_weight)) or exploration_weight < 0:
            raise ContractViolation("exploration_weight must be finite and non-negative")
        self.exploration_weight = float(exploration_weight)

    def decide(self, observation: TypedObservation,
               history: Sequence[OutcomeRecord]) -> ControllerDecision:
        allowed = tuple(sorted(self.profile.allowed_strategy_ids))
        bounded = self._bounded_history(
            history, current_window=observation.window
        )
        rewards: dict[str, list[float]] = {strategy_id: [] for strategy_id in allowed}
        for item in bounded:
            if item.strategy_id in rewards and item.reward is not None:
                rewards[item.strategy_id].append(float(item.reward))

        untried = [strategy_id for strategy_id in allowed if not rewards[strategy_id]]
        if untried:
            selected = untried[0]
            rationale = f"IA3 UCB initialization selected untried strategy {selected}."
            return self._card_decision(selected, rationale)

        total = sum(len(values) for values in rewards.values())
        if total <= 0:
            raise ContractViolation("IA3 has no usable history after initialization")
        scored: list[tuple[float, str]] = []
        for strategy_id, values in rewards.items():
            mean = sum(values) / len(values)
            bonus = self.exploration_weight * math.sqrt(math.log(total) / len(values))
            scored.append((mean + bonus, strategy_id))
        best_score = max(score for score, _ in scored)
        selected = min(
            strategy_id
            for score, strategy_id in scored
            if math.isclose(score, best_score, rel_tol=0.0, abs_tol=1e-12)
        )
        return self._card_decision(
            selected,
            rationale=f"IA3 UCB selected {selected} with score {best_score:.12g}.",
        )


class IA3CandidateUCBAdaptive(_ReferenceOrchestrator):
    """Deterministic UCB1 credit assignment over fully specified candidates."""

    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary,
                 candidate_library: CandidateLibrary,
                 reward_spec: CandidateRewardSpec,
                 exploration_weight: float = math.sqrt(2.0)):
        super().__init__(
            profile=profile,
            strategy_library=strategy_library,
            expected_rung=OrchestrationRung.IA3,
        )
        if len(candidate_library.candidates) > profile.candidate_count_cap:
            raise ContractViolation("candidate library exceeds candidate_count_cap")
        if profile.history_limit < len(candidate_library.candidates):
            raise ContractViolation(
                "history_limit must retain at least one outcome per candidate"
            )
        if not math.isfinite(float(exploration_weight)) or exploration_weight < 0:
            raise ContractViolation("exploration_weight must be finite and non-negative")
        for candidate in candidate_library.candidates:
            if len(candidate.steps) > profile.max_strategies_per_plan:
                raise ContractViolation("candidate exceeds max_strategies_per_plan")
            for step in candidate.steps:
                if step.strategy_id not in profile.allowed_strategy_ids:
                    raise ContractViolation("candidate uses a disallowed strategy")
                strategy_library.get(step.strategy_id).validate_step(step)
            if len(candidate.target_ids) > profile.authority.max_targets_per_plan:
                raise ContractViolation("candidate exceeds max_targets_per_plan")
            if not set(candidate.target_ids).issubset(
                    profile.authority.allowed_devices):
                raise ContractViolation("candidate targets an unauthorized device")
        self.candidate_library = candidate_library
        self.reward_spec = reward_spec
        self.exploration_weight = float(exploration_weight)

    def decide(self, observation: TypedObservation,
               history: Sequence[OutcomeRecord]) -> ControllerDecision:
        candidate_ids = self.candidate_library.ids()
        rewards: dict[str, list[float]] = {
            candidate_id: [] for candidate_id in candidate_ids
        }
        for item in self._bounded_history(
                history, current_window=observation.window):
            if item.reward is None:
                continue
            if item.candidate_id is None:
                raise ContractViolation(
                    "candidate-aware IA3 requires candidate_id on rewarded history"
                )
            if item.candidate_id not in rewards:
                raise ContractViolation(
                    f"history references unknown candidate: {item.candidate_id}"
                )
            expected_strategy_id = "+".join(
                self.candidate_library.get(item.candidate_id).strategy_ids
            )
            if item.strategy_id != expected_strategy_id:
                raise ContractViolation(
                    "history strategy_id does not match candidate lineage"
                )
            rewards[item.candidate_id].append(
                self.reward_spec.objective_value(item.reward)
            )

        untried = [candidate_id for candidate_id in candidate_ids
                   if not rewards[candidate_id]]
        if untried:
            selected = untried[0]
            rationale = (
                f"IA3 candidate UCB initialization selected untried {selected}."
            )
            return self._candidate_decision(selected, rationale)

        total = sum(len(values) for values in rewards.values())
        if total <= 0:
            raise ContractViolation("IA3 has no usable candidate history")
        scored: list[tuple[float, str]] = []
        for candidate_id, values in rewards.items():
            mean = sum(values) / len(values)
            bonus = self.exploration_weight * math.sqrt(
                math.log(total) / len(values)
            )
            scored.append((mean + bonus, candidate_id))
        best_score = max(score for score, _ in scored)
        selected = min(
            candidate_id
            for score, candidate_id in scored
            if math.isclose(score, best_score, rel_tol=0.0, abs_tol=1e-12)
        )
        return self._candidate_decision(
            selected,
            f"IA3 candidate UCB selected {selected} with score {best_score:.12g}.",
        )

    def _candidate_decision(self, candidate_id: str,
                            rationale: str) -> ControllerDecision:
        candidate = self.candidate_library.get(candidate_id)
        plan = candidate.instantiate(self.profile.rung, rationale)
        return ControllerDecision.submit(
            plan,
            reason="typed_candidate_plan",
            candidate_id=candidate_id,
        )
