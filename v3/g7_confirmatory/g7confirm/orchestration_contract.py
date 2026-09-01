"""Offline contracts for capability-conditioned attack orchestration."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Iterable, Mapping, Sequence

from .budget import BudgetDecision, Command, CommandMap, DualBudget


PLAN_SCHEMA_VERSION = "grideval-g7-typed-plan/v1"
OBSERVATION_SCHEMA_VERSION = "grideval-g7-observation/v1"
OUTCOME_SCHEMA_VERSION = "grideval-g7-outcome-history/v1"
TRACE_SCHEMA_VERSION = "grideval-g7-intent-realization-trace/v1"


class ContractViolation(ValueError):
    """Raised when an offline orchestration contract fails closed."""


class InformationLevel(IntEnum):
    """Information precision granted on one attacker-knowledge axis."""

    NONE = 0
    PARTIAL = 1
    EXACT = 2


class KnowledgeAxis(str, Enum):
    GRID = "grid"
    DETECTOR = "detector"
    TRAINING_DATA = "training_data"
    DEFENSE = "defense"
    FEEDBACK = "feedback"


class OrchestrationRung(str, Enum):
    IA0 = "IA0"
    IA1 = "IA1"
    IA2 = "IA2"
    IA3 = "IA3"
    IA4 = "IA4"
    IA5 = "IA5"


class SideEffectClass(str, Enum):
    READ_ONLY_NO_TIME_ADVANCE = "read_only_no_time_advance"
    SIMULATION_TIME_ADVANCING = "simulation_time_advancing"
    OUTER_ROLLOUT_CONSUMING = "outer_rollout_consuming"
    ACTUATING = "actuating"


class DecisionKind(str, Enum):
    PLAN = "plan"
    SAFETY_REFUSAL = "safety_refusal"
    NO_ACTION = "no_action"


class OutcomeStatus(str, Enum):
    ACCEPTED_EFFECTIVE = "accepted_effective"
    ACCEPTED_BENIGN = "accepted_benign"
    SAFETY_REFUSAL = "safety_refusal"
    NO_ACTION = "no_action"
    CONTRACT_REJECTION = "contract_rejection"
    BUDGET_REJECTION = "budget_rejection"


@dataclass(frozen=True)
class KnowledgeProfile:
    """The five-dimensional attacker knowledge vector K."""

    grid: InformationLevel = InformationLevel.NONE
    detector: InformationLevel = InformationLevel.NONE
    training_data: InformationLevel = InformationLevel.NONE
    defense: InformationLevel = InformationLevel.NONE
    feedback: InformationLevel = InformationLevel.NONE

    def level(self, axis: KnowledgeAxis) -> InformationLevel:
        return InformationLevel(getattr(self, axis.value))

    def to_dict(self) -> dict[str, str]:
        return {
            axis.value: self.level(axis).name.lower()
            for axis in KnowledgeAxis
        }


@dataclass(frozen=True)
class AuthorityProfile:
    """Operational authority A, independent of knowledge and orchestration."""

    allowed_devices: frozenset[str]
    allow_active_power: bool
    allow_reactive_power: bool
    max_targets_per_plan: int
    perturbed_window_cap: int
    apparent_energy_cap_kvah: float
    feedback_delay_windows: int = 0

    def __post_init__(self) -> None:
        if not self.allowed_devices:
            raise ContractViolation("authority must name at least one allowed device")
        if any(not item for item in self.allowed_devices):
            raise ContractViolation("authority contains an empty device identifier")
        if int(self.max_targets_per_plan) <= 0:
            raise ContractViolation("max_targets_per_plan must be positive")
        if int(self.max_targets_per_plan) > len(self.allowed_devices):
            raise ContractViolation("max_targets_per_plan exceeds allowed device count")
        if int(self.perturbed_window_cap) < 0:
            raise ContractViolation("perturbed_window_cap must be non-negative")
        if not math.isfinite(float(self.apparent_energy_cap_kvah)):
            raise ContractViolation("apparent_energy_cap_kvah must be finite")
        if float(self.apparent_energy_cap_kvah) < 0:
            raise ContractViolation("apparent_energy_cap_kvah must be non-negative")
        if int(self.feedback_delay_windows) < 0:
            raise ContractViolation("feedback_delay_windows must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_devices": sorted(self.allowed_devices),
            "allow_active_power": self.allow_active_power,
            "allow_reactive_power": self.allow_reactive_power,
            "max_targets_per_plan": self.max_targets_per_plan,
            "perturbed_window_cap": self.perturbed_window_cap,
            "apparent_energy_cap_kvah": self.apparent_energy_cap_kvah,
            "feedback_delay_windows": self.feedback_delay_windows,
        }


@dataclass(frozen=True)
class CapabilityProfile:
    """One declared K/A/IA capability cell and its resource contract."""

    profile_id: str
    rung: OrchestrationRung
    knowledge: KnowledgeProfile
    authority: AuthorityProfile
    allowed_strategy_ids: frozenset[str]
    allowed_tool_names: frozenset[str]
    tool_call_cap: int
    outer_rollout_cap: int
    history_limit: int
    candidate_count_cap: int
    max_strategies_per_plan: int = 1

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ContractViolation("profile_id is required")
        if not self.allowed_strategy_ids:
            raise ContractViolation("at least one strategy must be allowed")
        if int(self.tool_call_cap) < 0:
            raise ContractViolation("tool_call_cap must be non-negative")
        if int(self.outer_rollout_cap) < 0:
            raise ContractViolation("outer_rollout_cap must be non-negative")
        if int(self.history_limit) < 0:
            raise ContractViolation("history_limit must be non-negative")
        if int(self.candidate_count_cap) <= 0:
            raise ContractViolation("candidate_count_cap must be positive")
        if int(self.max_strategies_per_plan) <= 0:
            raise ContractViolation("max_strategies_per_plan must be positive")

    def parity_payload(self) -> dict[str, Any]:
        """Return all fields that must match when only the decision core changes."""

        return {
            "knowledge": self.knowledge.to_dict(),
            "authority": self.authority.to_dict(),
            "allowed_strategy_ids": sorted(self.allowed_strategy_ids),
            "allowed_tool_names": sorted(self.allowed_tool_names),
            "tool_call_cap": self.tool_call_cap,
            "outer_rollout_cap": self.outer_rollout_cap,
            "history_limit": self.history_limit,
            "candidate_count_cap": self.candidate_count_cap,
            "max_strategies_per_plan": self.max_strategies_per_plan,
        }

    def parity_fingerprint(self) -> str:
        encoded = json.dumps(
            self.parity_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def assert_capability_parity(left: CapabilityProfile,
                             right: CapabilityProfile) -> None:
    """Fail unless two profiles differ only in identity and IA decision core."""

    if left.parity_payload() != right.parity_payload():
        raise ContractViolation(
            f"capability parity mismatch: {left.profile_id} != {right.profile_id}"
        )


def bounded_visible_history(profile: CapabilityProfile, *, current_window: int,
                            history: Sequence["OutcomeRecord"]
                            ) -> tuple["OutcomeRecord", ...]:
    """Apply the shared ordering, feedback-delay, and history-length contract."""

    windows = [item.window for item in history]
    if windows != sorted(windows):
        raise ContractViolation("history must use non-decreasing window order")
    visible_through = int(current_window) - profile.authority.feedback_delay_windows
    visible = tuple(item for item in history if item.window <= visible_through)
    if profile.history_limit == 0:
        return ()
    return visible[-profile.history_limit:]


def candidate_id_for_steps(steps: Sequence["StrategyStep"]) -> str:
    """Return the rung-independent content address for strategy steps."""

    payload = {"steps": [step.to_dict() for step in steps]}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return "cand_" + hashlib.sha256(encoded).hexdigest()[:20]


@dataclass(frozen=True)
class PlanAction:
    device_id: str
    p_kw: float
    q_kvar: float

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ContractViolation("plan action requires a device_id")
        if not math.isfinite(float(self.p_kw)):
            raise ContractViolation("p_kw must be finite")
        if not math.isfinite(float(self.q_kvar)):
            raise ContractViolation("q_kvar must be finite")

    def command(self) -> Command:
        return float(self.p_kw), float(self.q_kvar)

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "p_kw": float(self.p_kw),
            "q_kvar": float(self.q_kvar),
        }


@dataclass(frozen=True)
class NumericParameterSpec:
    """One bounded numeric strategy parameter shared across IA rungs."""

    name: str
    minimum: float
    maximum: float
    default: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ContractViolation("parameter spec requires a name")
        values = (float(self.minimum), float(self.maximum), float(self.default))
        if not all(math.isfinite(item) for item in values):
            raise ContractViolation("parameter bounds and default must be finite")
        if self.minimum > self.maximum:
            raise ContractViolation("parameter minimum exceeds maximum")
        self.validate(self.default)

    def validate(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ContractViolation(f"parameter {self.name} must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ContractViolation(f"parameter {self.name} must be finite")
        if numeric < self.minimum or numeric > self.maximum:
            raise ContractViolation(f"parameter {self.name} is outside its bounds")

    def to_dict(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "minimum": float(self.minimum),
            "maximum": float(self.maximum),
            "default": float(self.default),
        }


@dataclass(frozen=True)
class ParameterValue:
    name: str
    value: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ContractViolation("parameter value requires a name")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ContractViolation(f"parameter {self.name} must be numeric")
        if not math.isfinite(float(self.value)):
            raise ContractViolation(f"parameter {self.name} must be finite")

    def to_dict(self) -> dict[str, float | str]:
        return {"name": self.name, "value": float(self.value)}


@dataclass(frozen=True)
class StrategyStep:
    """One strategy instance, its typed parameters, and materialized actions."""

    strategy_id: str
    parameters: tuple[ParameterValue, ...]
    actions: tuple[PlanAction, ...]

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ContractViolation("strategy step requires a strategy_id")
        if not self.actions:
            raise ContractViolation(
                "strategy step requires at least one materialized action"
            )
        names = [item.name for item in self.parameters]
        if len(names) != len(set(names)):
            raise ContractViolation("strategy step contains duplicate parameters")
        devices = [action.device_id for action in self.actions]
        if len(devices) != len(set(devices)):
            raise ContractViolation("strategy step contains duplicate device actions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "parameters": [item.to_dict() for item in self.parameters],
            "actions": [action.to_dict() for action in self.actions],
        }


@dataclass(frozen=True)
class TypedPlan:
    source_rung: OrchestrationRung
    steps: tuple[StrategyStep, ...]
    rationale: str
    schema_version: str = PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PLAN_SCHEMA_VERSION:
            raise ContractViolation("unsupported typed-plan schema_version")
        if not self.steps:
            raise ContractViolation("typed plan requires at least one strategy step")
        strategy_ids = [step.strategy_id for step in self.steps]
        if len(strategy_ids) != len(set(strategy_ids)):
            raise ContractViolation("typed plan contains duplicate strategy steps")
        if not self.rationale.strip():
            raise ContractViolation("plan rationale is required")
        if len(self.rationale) > 2000:
            raise ContractViolation("plan rationale exceeds 2000 characters")
        self.commands()

    @property
    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(step.strategy_id for step in self.steps)

    @property
    def strategy_id(self) -> str:
        """Return a stable label for single-card and composed plans."""

        return "+".join(self.strategy_ids)

    def commands(self) -> dict[str, Command]:
        commands: dict[str, Command] = {}
        for step in self.steps:
            for action in step.actions:
                if action.device_id in commands:
                    raise ContractViolation(
                        "composed strategy steps target the same device"
                    )
                commands[action.device_id] = action.command()
        return commands

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_rung": self.source_rung.value,
            "steps": [step.to_dict() for step in self.steps],
            "rationale": self.rationale,
            "plan_id": self.plan_id,
        }

    @property
    def plan_id(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "source_rung": self.source_rung.value,
            "steps": [step.to_dict() for step in self.steps],
            "rationale": self.rationale,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return "plan_" + hashlib.sha256(encoded).hexdigest()[:20]


@dataclass(frozen=True)
class TypedObservation:
    window: int
    time_s: int
    values: Mapping[str, float | int | bool | str]
    schema_version: str = OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != OBSERVATION_SCHEMA_VERSION:
            raise ContractViolation("unsupported observation schema_version")
        if int(self.window) < 0:
            raise ContractViolation("observation window must be non-negative")
        if int(self.time_s) < 0:
            raise ContractViolation("observation time_s must be non-negative")
        if any(not key for key in self.values):
            raise ContractViolation("observation contains an empty field name")
        for key, value in self.values.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(float(value)):
                    raise ContractViolation(f"observation field {key} must be finite")

    def numeric(self, field_name: str) -> float | None:
        value = self.values.get(field_name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "window": int(self.window),
            "time_s": int(self.time_s),
            "values": dict(sorted(self.values.items())),
        }


@dataclass(frozen=True)
class OutcomeRecord:
    """One prior orchestration outcome visible to a history-aware controller."""

    window: int
    strategy_id: str
    reward: float | None
    status: OutcomeStatus
    candidate_id: str | None = None
    schema_version: str = OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != OUTCOME_SCHEMA_VERSION:
            raise ContractViolation("unsupported outcome schema_version")
        if int(self.window) < 0:
            raise ContractViolation("outcome window must be non-negative")
        if not self.strategy_id:
            raise ContractViolation("outcome strategy_id is required")
        if self.candidate_id is not None and not self.candidate_id:
            raise ContractViolation("candidate_id cannot be empty")
        if self.reward is not None and not math.isfinite(float(self.reward)):
            raise ContractViolation("outcome reward must be finite")

    @property
    def credit_key(self) -> str:
        """Return candidate-level lineage when available, else legacy strategy ID."""

        return self.candidate_id or self.strategy_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "window": int(self.window),
            "strategy_id": self.strategy_id,
            "candidate_id": self.candidate_id,
            "reward": None if self.reward is None else float(self.reward),
            "status": self.status.value,
        }


@dataclass(frozen=True)
class ControllerDecision:
    kind: DecisionKind
    reason: str
    plan: TypedPlan | None = None
    candidate_id: str | None = None

    def __post_init__(self) -> None:
        if not self.reason:
            raise ContractViolation("controller decision reason is required")
        if self.kind is DecisionKind.PLAN and self.plan is None:
            raise ContractViolation("plan decision requires a typed plan")
        if self.kind is not DecisionKind.PLAN and self.plan is not None:
            raise ContractViolation("non-plan decision cannot contain a typed plan")
        if self.kind is not DecisionKind.PLAN and self.candidate_id is not None:
            raise ContractViolation("non-plan decision cannot contain a candidate_id")
        if self.candidate_id is not None and not self.candidate_id:
            raise ContractViolation("candidate_id cannot be empty")

    @classmethod
    def submit(cls, plan: TypedPlan, reason: str, *,
               candidate_id: str | None = None) -> "ControllerDecision":
        return cls(
            kind=DecisionKind.PLAN,
            reason=reason,
            plan=plan,
            candidate_id=candidate_id,
        )

    @classmethod
    def refuse(cls, reason: str) -> "ControllerDecision":
        return cls(kind=DecisionKind.SAFETY_REFUSAL, reason=reason)

    @classmethod
    def no_action(cls, reason: str) -> "ControllerDecision":
        return cls(kind=DecisionKind.NO_ACTION, reason=reason)


@dataclass(frozen=True)
class StrategyCard:
    """A frozen strategy template shared by all relevant IA rungs."""

    strategy_id: str
    family: str
    description: str
    default_actions: tuple[PlanAction, ...]
    eligible_devices: frozenset[str]
    p_kw_bounds: tuple[float, float]
    q_kvar_bounds: tuple[float, float]
    parameter_specs: tuple[NumericParameterSpec, ...] = ()
    component_tags: frozenset[str] = field(default_factory=frozenset)
    fixed_maximum_power: bool = False

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ContractViolation("strategy card requires a strategy_id")
        if not self.family:
            raise ContractViolation("strategy card requires a family")
        if not self.description:
            raise ContractViolation("strategy card requires a description")
        if not self.eligible_devices:
            raise ContractViolation("strategy card requires eligible devices")
        if any(not device_id for device_id in self.eligible_devices):
            raise ContractViolation("strategy card contains an empty device identifier")
        self._validate_bounds(self.p_kw_bounds, "p_kw_bounds")
        self._validate_bounds(self.q_kvar_bounds, "q_kvar_bounds")
        names = [item.name for item in self.parameter_specs]
        if len(names) != len(set(names)):
            raise ContractViolation("strategy card contains duplicate parameter specs")
        if names != sorted(names):
            raise ContractViolation(
                "strategy card parameter specs must use canonical name order"
            )
        default_devices = [item.device_id for item in self.default_actions]
        if default_devices != sorted(default_devices):
            raise ContractViolation(
                "strategy card default actions must use canonical device order"
            )
        self.validate_step(self.default_step())

    @staticmethod
    def _validate_bounds(bounds: tuple[float, float], name: str) -> None:
        if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
            raise ContractViolation(f"{name} must contain a minimum and maximum")
        lower, upper = float(bounds[0]), float(bounds[1])
        if not math.isfinite(lower) or not math.isfinite(upper):
            raise ContractViolation(f"{name} must be finite")
        if lower > upper:
            raise ContractViolation(f"{name} minimum exceeds maximum")

    def default_step(self) -> StrategyStep:
        return StrategyStep(
            strategy_id=self.strategy_id,
            parameters=tuple(
                ParameterValue(spec.name, spec.default)
                for spec in self.parameter_specs
            ),
            actions=self.default_actions,
        )

    def validate_step(self, step: StrategyStep) -> None:
        if step.strategy_id != self.strategy_id:
            raise ContractViolation("strategy step does not match its card")
        expected = {spec.name: spec for spec in self.parameter_specs}
        supplied = {item.name: item for item in step.parameters}
        if set(supplied) != set(expected):
            raise ContractViolation("strategy step parameter names do not match its card")
        for name, spec in expected.items():
            spec.validate(supplied[name].value)
        for action in step.actions:
            if action.device_id not in self.eligible_devices:
                raise ContractViolation(
                    f"strategy step targets an ineligible device: {action.device_id}"
                )
            if not self.p_kw_bounds[0] <= action.p_kw <= self.p_kw_bounds[1]:
                raise ContractViolation("strategy step p_kw is outside its card envelope")
            if not self.q_kvar_bounds[0] <= action.q_kvar <= self.q_kvar_bounds[1]:
                raise ContractViolation(
                    "strategy step q_kvar is outside its card envelope"
                )

    def instantiate(self, rung: OrchestrationRung, rationale: str, *,
                    parameters: tuple[ParameterValue, ...] | None = None,
                    actions: tuple[PlanAction, ...] | None = None) -> TypedPlan:
        step = StrategyStep(
            strategy_id=self.strategy_id,
            parameters=(parameters if parameters is not None
                        else self.default_step().parameters),
            actions=actions if actions is not None else self.default_actions,
        )
        self.validate_step(step)
        return TypedPlan(
            source_rung=rung,
            steps=(step,),
            rationale=rationale,
        )


class StrategyLibrary:
    """Immutable lookup surface for frozen strategy cards."""

    def __init__(self, cards: Iterable[StrategyCard]):
        ordered = tuple(cards)
        if not ordered:
            raise ContractViolation("strategy library cannot be empty")
        ids = [card.strategy_id for card in ordered]
        if len(ids) != len(set(ids)):
            raise ContractViolation("strategy library contains duplicate IDs")
        self._cards = ordered
        self._by_id = {card.strategy_id: card for card in ordered}

    @property
    def cards(self) -> tuple[StrategyCard, ...]:
        return self._cards

    def get(self, strategy_id: str) -> StrategyCard:
        try:
            return self._by_id[strategy_id]
        except KeyError as exc:
            raise ContractViolation(f"unknown strategy_id: {strategy_id}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(card.strategy_id for card in self._cards)

    def describe_allowed(self, allowed_ids: Iterable[str]) -> tuple[dict[str, Any], ...]:
        """Return exact card definitions for the allowed decision surface."""

        requested = tuple(sorted(allowed_ids))
        missing = set(requested) - set(self._by_id)
        if missing:
            raise ContractViolation(
                f"strategy library is missing allowed cards: {sorted(missing)}"
            )
        return tuple(
            {
                "strategy_id": card.strategy_id,
                "family": card.family,
                "description": card.description,
                "default_actions": [
                    action.to_dict() for action in card.default_actions
                ],
                "eligible_devices": sorted(card.eligible_devices),
                "p_kw_bounds": [float(item) for item in card.p_kw_bounds],
                "q_kvar_bounds": [float(item) for item in card.q_kvar_bounds],
                "parameter_specs": [
                    item.to_dict() for item in card.parameter_specs
                ],
                "component_tags": sorted(card.component_tags),
                "fixed_maximum_power": card.fixed_maximum_power,
            }
            for card in (self._by_id[strategy_id] for strategy_id in requested)
        )

    def fingerprint(self) -> str:
        payload = self.describe_allowed(self.ids())
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    side_effect_class: SideEffectClass
    information_axis: KnowledgeAxis | None = None
    minimum_information_level: InformationLevel = InformationLevel.NONE
    input_schema_version: str = "input/v1"
    output_schema_version: str = "output/v1"

    def __post_init__(self) -> None:
        if not self.name:
            raise ContractViolation("tool spec requires a name")
        if not self.input_schema_version or not self.output_schema_version:
            raise ContractViolation("tool schema versions are required")
        if self.information_axis is None:
            if self.minimum_information_level is not InformationLevel.NONE:
                raise ContractViolation(
                    "axis-free tool cannot require a non-none information level"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "input_schema_version": self.input_schema_version,
            "output_schema_version": self.output_schema_version,
            "side_effect_class": self.side_effect_class.value,
            "information_axis": (
                self.information_axis.value if self.information_axis else None
            ),
            "minimum_information_level": (
                self.minimum_information_level.name.lower()
            ),
        }


@dataclass(frozen=True)
class ToolCallRecord:
    call_id: str
    caller_rung: OrchestrationRung
    tool_name: str
    input_schema_version: str
    output_schema_version: str
    side_effect_class: SideEffectClass
    simulation_time_advance_s: float
    outer_rollout_cost: int
    wall_clock_ms: float
    model_tokens: int
    returned_information_level: InformationLevel
    validation_result: str

    def __post_init__(self) -> None:
        for name in (
            "call_id", "tool_name", "input_schema_version", "output_schema_version",
            "validation_result",
        ):
            if not getattr(self, name):
                raise ContractViolation(f"tool call {name} is required")
        if not math.isfinite(float(self.simulation_time_advance_s)):
            raise ContractViolation("simulation_time_advance_s must be finite")
        if float(self.simulation_time_advance_s) < 0:
            raise ContractViolation("simulation_time_advance_s must be non-negative")
        if int(self.outer_rollout_cost) < 0:
            raise ContractViolation("outer_rollout_cost must be non-negative")
        if not math.isfinite(float(self.wall_clock_ms)) or float(self.wall_clock_ms) < 0:
            raise ContractViolation("wall_clock_ms must be finite and non-negative")
        if int(self.model_tokens) < 0:
            raise ContractViolation("model_tokens must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "caller_rung": self.caller_rung.value,
            "tool_name": self.tool_name,
            "input_schema_version": self.input_schema_version,
            "output_schema_version": self.output_schema_version,
            "side_effect_class": self.side_effect_class.value,
            "simulation_time_advance_s": float(self.simulation_time_advance_s),
            "outer_rollout_cost": int(self.outer_rollout_cost),
            "wall_clock_ms": float(self.wall_clock_ms),
            "model_tokens": int(self.model_tokens),
            "returned_information_level": (
                self.returned_information_level.name.lower()
            ),
            "validation_result": self.validation_result,
        }


class ToolContract:
    """Validate tool visibility, information access, and declared side effects."""

    def __init__(self, specs: Iterable[ToolSpec]):
        ordered = tuple(specs)
        names = [spec.name for spec in ordered]
        if len(names) != len(set(names)):
            raise ContractViolation("tool contract contains duplicate names")
        self._specs = {spec.name: spec for spec in ordered}

    def validate_calls(self, profile: CapabilityProfile,
                       calls: Sequence[ToolCallRecord]) -> None:
        if len(calls) > profile.tool_call_cap:
            raise ContractViolation("tool_call_cap exceeded")
        rollout_cost = 0
        seen_call_ids: set[str] = set()
        for call in calls:
            if call.call_id in seen_call_ids:
                raise ContractViolation("duplicate tool call_id")
            seen_call_ids.add(call.call_id)
            if call.caller_rung is not profile.rung:
                raise ContractViolation("tool caller rung does not match capability profile")
            if call.tool_name not in profile.allowed_tool_names:
                raise ContractViolation(f"tool is not allowed: {call.tool_name}")
            try:
                spec = self._specs[call.tool_name]
            except KeyError as exc:
                raise ContractViolation(f"tool is not registered: {call.tool_name}") from exc
            if call.input_schema_version != spec.input_schema_version:
                raise ContractViolation("tool input schema version mismatch")
            if call.output_schema_version != spec.output_schema_version:
                raise ContractViolation("tool output schema version mismatch")
            if call.side_effect_class is not spec.side_effect_class:
                raise ContractViolation("tool side-effect class mismatch")
            if (call.simulation_time_advance_s > 0 and
                    spec.side_effect_class is not SideEffectClass.SIMULATION_TIME_ADVANCING):
                raise ContractViolation("tool silently advanced simulation time")
            if (spec.side_effect_class is SideEffectClass.READ_ONLY_NO_TIME_ADVANCE and
                    call.simulation_time_advance_s != 0):
                raise ContractViolation("read-only tool advanced simulation time")
            if (call.outer_rollout_cost > 0 and
                    spec.side_effect_class is not SideEffectClass.OUTER_ROLLOUT_CONSUMING):
                raise ContractViolation("non-rollout tool declared rollout cost")
            if (spec.information_axis is not None and
                    profile.knowledge.level(spec.information_axis) <
                    spec.minimum_information_level):
                raise ContractViolation(
                    f"knowledge profile cannot call tool: {call.tool_name}"
                )
            if spec.information_axis is not None:
                granted = profile.knowledge.level(spec.information_axis)
                if call.returned_information_level > granted:
                    raise ContractViolation("tool returned information above K profile")
            elif call.returned_information_level is not InformationLevel.NONE:
                raise ContractViolation("axis-free tool returned undeclared information")
            rollout_cost += int(call.outer_rollout_cost)
        if rollout_cost > profile.outer_rollout_cap:
            raise ContractViolation("outer_rollout_cap exceeded")

    def describe_allowed(self, allowed_names: Iterable[str]) -> tuple[dict[str, Any], ...]:
        """Return the exact ordered tool surface granted to one profile."""

        payload: list[dict[str, Any]] = []
        for name in sorted(allowed_names):
            if name not in self._specs:
                raise ContractViolation(f"tool is not registered: {name}")
            payload.append(self._specs[name].to_dict())
        return tuple(payload)

    def schema_fingerprint(self, allowed_names: Iterable[str]) -> str:
        payload = self.describe_allowed(allowed_names)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ValidationOutcome:
    status: OutcomeStatus
    reason: str
    plan_id: str | None
    strategy_id: str | None
    candidate_id: str | None
    plan_submitted: bool
    valid_plan: bool
    accepted: bool
    effective_action: bool
    safety_refusal: bool
    commands: Mapping[str, Command]
    budget_decision: BudgetDecision | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "plan_id": self.plan_id,
            "strategy_id": self.strategy_id,
            "candidate_id": self.candidate_id,
            "plan_submitted": self.plan_submitted,
            "valid_plan": self.valid_plan,
            "accepted": self.accepted,
            "effective_action": self.effective_action,
            "safety_refusal": self.safety_refusal,
            "commands": {
                key: [float(value[0]), float(value[1])]
                for key, value in sorted(self.commands.items())
            },
            "budget_decision": (
                self.budget_decision.to_dict() if self.budget_decision else None
            ),
        }


class PlanValidator:
    """Apply one fail-closed contract before any plan can reach an actuator."""

    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary,
                 tool_contract: ToolContract, dual_budget: DualBudget):
        self.profile = profile
        self.strategy_library = strategy_library
        self.tool_contract = tool_contract
        self.dual_budget = dual_budget
        authority = profile.authority
        if authority.perturbed_window_cap != dual_budget.window_cap:
            raise ContractViolation("authority and DualBudget window caps differ")
        if not math.isclose(
            authority.apparent_energy_cap_kvah,
            dual_budget.energy_cap,
            rel_tol=0.0,
            abs_tol=dual_budget.tolerance,
        ):
            raise ContractViolation("authority and DualBudget energy caps differ")

    def evaluate(self, decision: ControllerDecision, *, benign: CommandMap,
                 tool_calls: Sequence[ToolCallRecord] = ()) -> ValidationOutcome:
        try:
            self.tool_contract.validate_calls(self.profile, tool_calls)
        except ContractViolation as exc:
            plan = decision.plan
            return ValidationOutcome(
                status=OutcomeStatus.CONTRACT_REJECTION,
                reason=str(exc),
                plan_id=plan.plan_id if plan else None,
                strategy_id=plan.strategy_id if plan else None,
                candidate_id=decision.candidate_id,
                plan_submitted=plan is not None,
                valid_plan=False,
                accepted=False,
                effective_action=False,
                safety_refusal=(decision.kind is DecisionKind.SAFETY_REFUSAL),
                commands={},
            )
        if decision.kind is DecisionKind.SAFETY_REFUSAL:
            return ValidationOutcome(
                status=OutcomeStatus.SAFETY_REFUSAL,
                reason=decision.reason,
                plan_id=None,
                strategy_id=None,
                candidate_id=None,
                plan_submitted=False,
                valid_plan=False,
                accepted=False,
                effective_action=False,
                safety_refusal=True,
                commands={},
            )
        if decision.kind is DecisionKind.NO_ACTION:
            return ValidationOutcome(
                status=OutcomeStatus.NO_ACTION,
                reason=decision.reason,
                plan_id=None,
                strategy_id=None,
                candidate_id=None,
                plan_submitted=False,
                valid_plan=False,
                accepted=True,
                effective_action=False,
                safety_refusal=False,
                commands={},
            )
        assert decision.plan is not None
        plan = decision.plan
        try:
            if (decision.candidate_id is not None and
                    decision.candidate_id != candidate_id_for_steps(plan.steps)):
                raise ContractViolation(
                    "candidate_id does not match submitted plan content"
                )
            commands = self._validate_plan(plan, benign)
        except (ContractViolation, ValueError) as exc:
            return ValidationOutcome(
                status=OutcomeStatus.CONTRACT_REJECTION,
                reason=str(exc),
                plan_id=plan.plan_id,
                strategy_id=plan.strategy_id,
                candidate_id=decision.candidate_id,
                plan_submitted=True,
                valid_plan=False,
                accepted=False,
                effective_action=False,
                safety_refusal=False,
                commands={},
            )

        budget_decision = self.dual_budget.try_admit(commands, benign)
        if not budget_decision.accepted:
            return ValidationOutcome(
                status=OutcomeStatus.BUDGET_REJECTION,
                reason=budget_decision.reason,
                plan_id=plan.plan_id,
                strategy_id=plan.strategy_id,
                candidate_id=decision.candidate_id,
                plan_submitted=True,
                valid_plan=True,
                accepted=False,
                effective_action=False,
                safety_refusal=False,
                commands={},
                budget_decision=budget_decision,
            )
        effective = bool(budget_decision.commands)
        return ValidationOutcome(
            status=(OutcomeStatus.ACCEPTED_EFFECTIVE if effective
                    else OutcomeStatus.ACCEPTED_BENIGN),
            reason=budget_decision.reason,
            plan_id=plan.plan_id,
            strategy_id=plan.strategy_id,
            candidate_id=decision.candidate_id,
            plan_submitted=True,
            valid_plan=True,
            accepted=True,
            effective_action=effective,
            safety_refusal=False,
            commands=budget_decision.commands,
            budget_decision=budget_decision,
        )

    def _validate_plan(self, plan: TypedPlan,
                       benign: CommandMap) -> dict[str, Command]:
        if plan.source_rung is not self.profile.rung:
            raise ContractViolation("plan source rung does not match capability profile")
        if len(plan.steps) > self.profile.max_strategies_per_plan:
            raise ContractViolation("plan exceeds max_strategies_per_plan")
        for step in plan.steps:
            if step.strategy_id not in self.profile.allowed_strategy_ids:
                raise ContractViolation("strategy is not allowed by capability profile")
            self.strategy_library.get(step.strategy_id).validate_step(step)
        commands = plan.commands()
        unknown = set(commands) - self.profile.authority.allowed_devices
        if unknown:
            raise ContractViolation(f"plan targets unauthorized devices: {sorted(unknown)}")
        if len(commands) > self.profile.authority.max_targets_per_plan:
            raise ContractViolation("plan exceeds max_targets_per_plan")
        for device_id, command in commands.items():
            if device_id not in benign:
                raise ContractViolation(f"missing benign command for {device_id}")
            proposed_p, proposed_q = command
            benign_p, benign_q = DualBudget._coerce(benign[device_id], device_id)
            if (not self.profile.authority.allow_active_power and
                    not math.isclose(proposed_p, benign_p, abs_tol=self.dual_budget.tolerance)):
                raise ContractViolation("active-power authority exceeded")
            if (not self.profile.authority.allow_reactive_power and
                    not math.isclose(proposed_q, benign_q, abs_tol=self.dual_budget.tolerance)):
                raise ContractViolation("reactive-power authority exceeded")
        return commands


def summarize_outcomes(outcomes: Sequence[ValidationOutcome], *,
                       tool_calls: Sequence[ToolCallRecord] = ()) -> dict[str, Any]:
    """Produce refusal and effective-action metrics without silent exclusions."""

    total = len(outcomes)
    submitted = sum(item.plan_submitted for item in outcomes)
    valid = sum(item.valid_plan for item in outcomes)
    accepted = sum(item.accepted for item in outcomes)
    effective = sum(item.effective_action for item in outcomes)
    refusals = sum(item.safety_refusal for item in outcomes)
    contract_rejections = sum(
        item.status is OutcomeStatus.CONTRACT_REJECTION for item in outcomes
    )
    budget_rejections = sum(
        item.status is OutcomeStatus.BUDGET_REJECTION for item in outcomes
    )

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "decisions": total,
        "plans_submitted": submitted,
        "valid_plans": valid,
        "accepted_decisions": accepted,
        "effective_actions": effective,
        "safety_refusals": refusals,
        "contract_rejections": contract_rejections,
        "budget_rejections": budget_rejections,
        "valid_proposal_rate": ratio(valid, submitted),
        "safety_refusal_rate": ratio(refusals, total),
        "effective_action_rate": ratio(effective, total),
        "target_diversity": len({
            device_id
            for outcome in outcomes
            if outcome.effective_action
            for device_id in outcome.commands
        }),
        "tool_calls": len(tool_calls),
        "outer_rollout_cost": sum(item.outer_rollout_cost for item in tool_calls),
        "wall_clock_ms": sum(item.wall_clock_ms for item in tool_calls),
        "model_tokens": sum(item.model_tokens for item in tool_calls),
    }


def build_intent_trace(*, profile: CapabilityProfile,
                       decision: ControllerDecision,
                       outcome: ValidationOutcome,
                       tool_calls: Sequence[ToolCallRecord],
                       delivered: Mapping[str, Command] | None = None,
                       accepted_by_device: Mapping[str, Command] | None = None,
                       realized_pq: Mapping[str, Command] | None = None) -> dict[str, Any]:
    """Create an offline lineage record without claiming runtime observations."""

    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "profile_id": profile.profile_id,
        "rung": profile.rung.value,
        "decision_kind": decision.kind.value,
        "decision_reason": decision.reason,
        "candidate_id": decision.candidate_id,
        "requested_plan": decision.plan.to_dict() if decision.plan else None,
        "validation": outcome.to_dict(),
        "tool_calls": [
            {
                "call_id": call.call_id,
                "caller_rung": call.caller_rung.value,
                "tool_name": call.tool_name,
                "input_schema_version": call.input_schema_version,
                "output_schema_version": call.output_schema_version,
                "side_effect_class": call.side_effect_class.value,
                "simulation_time_advance_s": call.simulation_time_advance_s,
                "outer_rollout_cost": call.outer_rollout_cost,
                "wall_clock_ms": call.wall_clock_ms,
                "model_tokens": call.model_tokens,
                "returned_information_level": call.returned_information_level.name.lower(),
                "validation_result": call.validation_result,
            }
            for call in tool_calls
        ],
        "delivered": _serialize_commands(delivered),
        "accepted_by_device": _serialize_commands(accepted_by_device),
        "realized_pq": _serialize_commands(realized_pq),
        "runtime_evidence": any(
            item is not None for item in (delivered, accepted_by_device, realized_pq)
        ),
    }


def _serialize_commands(commands: Mapping[str, Command] | None) -> Any:
    if commands is None:
        return None
    return {
        key: [float(value[0]), float(value[1])]
        for key, value in sorted(commands.items())
    }
