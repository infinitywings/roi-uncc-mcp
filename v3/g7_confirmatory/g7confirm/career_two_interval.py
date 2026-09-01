"""Offline CAREER two-interval fixture for the M9 revision-permission gate.

The fixture uses qualitative, non-executable action tokens and synthetic
midpoint observations.  It proves protocol isolation only: no method in this
module can call a model, tool, simulator, detector, embedding service, or
actuator.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_stealth_contract import (
    FROZEN_EXPERIMENT_SPEC_SHA256,
    FROZEN_ROADMAP_REPORT_SHA256,
    GOVERNING_DRAFT_SHA256,
)
from .orchestration_contract import ContractViolation


TWO_INTERVAL_SCHEMA_VERSION = "grideval-career-two-interval-contract/v1"
RECEIPT_SCHEMA_VERSION = "grideval-career-two-interval-receipt/v1"
PAIR_SCHEMA_VERSION = "grideval-career-two-interval-pair/v1"
M8_CONTRACT_ID = (
    "careerstealth_3091a0e686e43b483906a37733f26dfb4cef9fd90d2ae56226e47003b3cdd394"
)
M9_DESIGN_DECISION_ID = "dec_01M1DK7XKSN2DPEZ3EGYZAHKJW"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _content_id(prefix: str, value: Any, *, omit: Sequence[str] = ()) -> str:
    content = json.loads(_canonical_json(value))
    if isinstance(content, dict):
        for key in omit:
            content.pop(key, None)
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def contract_id_for(payload: Mapping[str, Any]) -> str:
    """Return the M9 contract content address."""

    return _content_id("careertwoint", payload, omit=("contract_id",))


def plan_id_for(payload: Mapping[str, Any]) -> str:
    """Return a content address for one qualitative two-interval plan."""

    return _content_id("fixtureplan", payload, omit=("plan_id",))


def observation_id_for(payload: Mapping[str, Any]) -> str:
    """Return a content address for one synthetic midpoint observation."""

    return _content_id("fixtureobs", payload, omit=("observation_id",))


def receipt_id_for(payload: Mapping[str, Any]) -> str:
    """Return a content address for one terminal fixture receipt."""

    return _content_id("m9receipt", payload, omit=("receipt_id",))


def pair_id_for(payload: Mapping[str, Any]) -> str:
    """Return a content address for the four-receipt mirrored pair."""

    return _content_id("m9pair", payload, omit=("pair_id",))


def _fingerprint(value: Any) -> str:
    return _content_id("sha256", value)


class CapabilityCondition(str, Enum):
    """The only intervention in the M9 causal fixture."""

    PREPLANNED = "A0_preplanned"
    RESPONSE_INFORMED = "A1_response_informed"


class SessionState(str, Enum):
    """Fail-closed states for one two-interval fixture episode."""

    PRECOMMITTED = "precommitted"
    AWAITING_MIDPOINT_DECISION = "awaiting_midpoint_decision"
    TERMINAL = "terminal"
    FAILED_CLOSED = "failed_closed"


REQUIRED_GOVERNANCE = {
    "development_only": True,
    "campaign_authorized": False,
    "evaluation_sealed": True,
    "detector_calibration_authorized": False,
    "live_runtime_authorized": False,
    "model_transport_authorized": False,
    "real_tool_execution_authorized": False,
    "embedding_service_accessed": False,
    "simulator_accessed": False,
    "detector_accessed": False,
    "actuator_accessed": False,
}


@dataclass(frozen=True)
class CareerTwoIntervalContract:
    """Immutable validated form of the content-addressed M9 contract."""

    _canonical_content: str

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        self._validate(copied)
        object.__setattr__(self, "_canonical_content", _canonical_json(copied))

    @property
    def contract_id(self) -> str:
        return self.to_dict()["contract_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    @staticmethod
    def _validate(content: Mapping[str, Any]) -> None:
        expected_fields = {
            "schema_version",
            "contract_id",
            "milestone",
            "title",
            "governance",
            "source_lineage",
            "protocol",
            "parity_inputs",
            "candidate_library",
            "fixture_pair",
            "reference_policy",
            "acceptance_gate",
            "limitations",
            "next_gate",
        }
        if set(content) != expected_fields:
            raise ContractViolation("M9 contract top-level fields drift")
        if content["schema_version"] != TWO_INTERVAL_SCHEMA_VERSION:
            raise ContractViolation("unsupported M9 contract schema_version")
        if content["milestone"] != "M9":
            raise ContractViolation("two-interval contract must be milestone M9")
        if content["contract_id"] != contract_id_for(content):
            raise ContractViolation("M9 contract_id mismatch")
        if content["governance"] != REQUIRED_GOVERNANCE:
            raise ContractViolation("M9 governance boundary drift")

        lineage = content["source_lineage"]
        required_lineage = {
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "m8_contract_id": M8_CONTRACT_ID,
            "m9_design_decision": M9_DESIGN_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        }
        if lineage != required_lineage:
            raise ContractViolation("M9 source lineage drift")

        protocol = content["protocol"]
        required_protocol = {
            "action_interval_count": 2,
            "midpoint_observation_count": 1,
            "maximum_treatment_revisions": 1,
            "control_revision_count": 0,
            "revision_scope": "second_interval_only",
            "revision_window": "after_midpoint_before_second_interval",
            "first_interval_immutable": True,
            "terminal_state_immutable": True,
            "invalid_transition_policy": "fail_closed_no_retry",
            "paired_history_rule": "freeze_before_pair_no_cross_condition_learning",
            "physical_units_present": False,
            "executable_setpoints_present": False,
        }
        if protocol != required_protocol:
            raise ContractViolation("M9 two-interval protocol drift")

        parity = content["parity_inputs"]
        required_parity_keys = {
            "initial_plan_id",
            "candidate_library_fingerprint",
            "observation_schema",
            "observation_schema_fingerprint",
            "history",
            "history_fingerprint",
            "budget",
            "budget_fingerprint",
            "schedule",
            "schedule_fingerprint",
            "safety_shield",
            "safety_shield_fingerprint",
            "parity_fingerprint",
        }
        if set(parity) != required_parity_keys:
            raise ContractViolation("M9 parity fields drift")
        for payload_key in (
            "observation_schema",
            "history",
            "budget",
            "schedule",
            "safety_shield",
        ):
            fingerprint_key = f"{payload_key}_fingerprint"
            if parity[fingerprint_key] != _fingerprint(parity[payload_key]):
                raise ContractViolation(
                    f"M9 {payload_key.replace('_', '-')} fingerprint mismatch"
                )
        parity_payload = {key: parity[key] for key in sorted(parity)
                          if key != "parity_fingerprint"}
        if parity["parity_fingerprint"] != _fingerprint(parity_payload):
            raise ContractViolation("M9 parity fingerprint mismatch")

        plans = content["candidate_library"]
        if len(plans) != 3:
            raise ContractViolation("M9 requires exactly three fixture plans")
        plan_ids = [plan.get("plan_id") for plan in plans]
        if len(set(plan_ids)) != len(plan_ids):
            raise ContractViolation("M9 fixture plan IDs must be unique")
        for plan in plans:
            if plan.get("plan_id") != plan_id_for(plan):
                raise ContractViolation("M9 fixture plan_id mismatch")
            intervals = plan.get("intervals", ())
            if len(intervals) != 2:
                raise ContractViolation("every fixture plan needs two intervals")
            if [item.get("index") for item in intervals] != [1, 2]:
                raise ContractViolation("fixture interval order drift")
            if any(item.get("executable") is not False for item in intervals):
                raise ContractViolation("M9 plans must remain non-executable")
            if any(set(item) != {
                    "index", "strategy_id", "qualitative_direction",
                    "magnitude_token", "executable"} for item in intervals):
                raise ContractViolation("M9 fixture interval fields drift")

        initial_id = parity["initial_plan_id"]
        plan_by_id = {plan["plan_id"]: plan for plan in plans}
        if initial_id not in plan_by_id:
            raise ContractViolation("M9 initial plan is outside the library")
        first_fingerprints = {
            _fingerprint(plan["intervals"][0]) for plan in plans
        }
        if len(first_fingerprints) != 1:
            raise ContractViolation("M9 candidate first intervals must be identical")
        if parity["candidate_library_fingerprint"] != _fingerprint(plans):
            raise ContractViolation("M9 candidate-library fingerprint mismatch")

        fixtures = content["fixture_pair"]
        if len(fixtures) != 2:
            raise ContractViolation("M9 requires a mirrored fixture pair")
        signs = {fixture.get("trend_sign") for fixture in fixtures}
        if signs != {"negative", "positive"}:
            raise ContractViolation("M9 midpoint observations must be mirrored")
        fixture_ids = set()
        for fixture in fixtures:
            if fixture.get("observation_id") != observation_id_for(fixture):
                raise ContractViolation("M9 observation_id mismatch")
            if fixture.get("synthetic") is not True:
                raise ContractViolation("M9 observations must remain synthetic")
            if fixture.get("physical_claim") is not False:
                raise ContractViolation("M9 observation cannot make a physical claim")
            fixture_ids.add(fixture["observation_id"])
        if len(fixture_ids) != 2:
            raise ContractViolation("M9 observation IDs must be unique")

        policy = content["reference_policy"]
        if set(policy) != {
                "role", "control_rule", "treatment_rule", "mapping",
                "claim_boundary"}:
            raise ContractViolation("M9 reference-policy fields drift")
        if policy["role"] != "deterministic_protocol_witness_only":
            raise ContractViolation("M9 reference policy role drift")
        if policy["control_rule"] != "retain_precommitted_plan":
            raise ContractViolation("M9 A0 policy must retain the initial plan")
        if policy["treatment_rule"] != "map_trend_sign_to_declared_plan":
            raise ContractViolation("M9 A1 witness rule drift")
        if policy["claim_boundary"] != (
                "not_an_attack_effectiveness_or_reasoning_policy"):
            raise ContractViolation("M9 reference-policy claim boundary drift")
        mapping = policy["mapping"]
        if set(mapping) != {"negative", "positive"}:
            raise ContractViolation("M9 witness mapping must cover both signs")
        if mapping["negative"] == mapping["positive"]:
            raise ContractViolation(
                "M9 mirrored observations must select distinct plans"
            )
        if initial_id in mapping.values():
            raise ContractViolation(
                "M9 treatment must exercise one revision per fixture"
            )
        if not set(mapping.values()).issubset(plan_by_id):
            raise ContractViolation("M9 witness mapping references an unknown plan")
        for sign, plan_id in mapping.items():
            direction = plan_by_id[plan_id]["intervals"][1][
                "qualitative_direction"]
            if direction != sign:
                raise ContractViolation("M9 witness mapping direction drift")

        gate = content["acceptance_gate"]
        required_checks = {
            "A0_same_terminal_plan_across_mirrors",
            "A1_distinct_terminal_plans_across_mirrors",
            "A0_zero_revisions",
            "A1_exactly_one_revision_per_fixture",
            "first_interval_identical_everywhere",
            "all_parity_fingerprints_identical",
            "all_external_access_flags_false",
            "all_receipts_terminal_and_content_addressed",
        }
        if set(gate.get("required_checks", ())) != required_checks:
            raise ContractViolation("M9 acceptance checks drift")
        if gate.get("passing_interpretation") != "protocol_isolation_only":
            raise ContractViolation("M9 gate interpretation drift")

        required_limitations = {
            "no_physical_effect_claim",
            "no_stealth_or_alarm_claim",
            "no_policy_quality_claim",
            "no_llm_or_tool_use_claim",
            "no_runtime_readiness_claim",
            "no_campaign_authorization",
        }
        if set(content["limitations"]) != required_limitations:
            raise ContractViolation("M9 limitations drift")
        next_gate = content["next_gate"]
        if next_gate != {
            "id": "M10_validated_resource_admission_contracts",
            "scope": "offline_contracts_for_S_and_M_only",
            "model_call": False,
            "real_tool_execution": False,
            "simulator_or_detector_access": False,
        }:
            raise ContractViolation("unexpected M9 next gate")


class TwoIntervalSession:
    """One deterministic, fail-closed episode under the M9 contract."""

    def __init__(
        self,
        contract: CareerTwoIntervalContract,
        capability_condition: CapabilityCondition,
    ):
        self.contract = contract
        self.capability_condition = CapabilityCondition(capability_condition)
        content = contract.to_dict()
        self._plans = {
            item["plan_id"]: item for item in content["candidate_library"]
        }
        self._initial_plan_id = content["parity_inputs"]["initial_plan_id"]
        self._terminal_plan_id: str | None = None
        self._observation: dict[str, Any] | None = None
        self._revision_count = 0
        self._state = SessionState.PRECOMMITTED
        self._states = [self._state.value]

    @property
    def state(self) -> SessionState:
        return self._state

    def _fail(self, message: str) -> None:
        if self._state != SessionState.FAILED_CLOSED:
            self._state = SessionState.FAILED_CLOSED
            self._states.append(self._state.value)
        raise ContractViolation(message)

    def present_midpoint(self, observation: Mapping[str, Any]) -> None:
        """Present exactly one declared synthetic midpoint observation."""

        if self._state != SessionState.PRECOMMITTED:
            self._fail("midpoint observation is out of order")
        copied = json.loads(_canonical_json(observation))
        allowed = {
            item["observation_id"]: item
            for item in self.contract.to_dict()["fixture_pair"]
        }
        if copied.get("observation_id") not in allowed:
            self._fail("midpoint observation is outside the frozen fixture pair")
        if copied != allowed[copied["observation_id"]]:
            self._fail("midpoint observation bytes drift")
        self._observation = copied
        self._state = SessionState.AWAITING_MIDPOINT_DECISION
        self._states.append(self._state.value)

    def retain_precommitted_plan(self) -> dict[str, Any]:
        """Finalize without revising the second interval."""

        if self._state != SessionState.AWAITING_MIDPOINT_DECISION:
            self._fail("retain decision is outside the midpoint window")
        self._terminal_plan_id = self._initial_plan_id
        self._state = SessionState.TERMINAL
        self._states.append(self._state.value)
        return self.receipt()

    def revise_second_interval(self, plan_id: str) -> dict[str, Any]:
        """Apply the sole A1 revision to a declared second interval."""

        if self._state != SessionState.AWAITING_MIDPOINT_DECISION:
            self._fail("revision is outside the midpoint window")
        if self.capability_condition != CapabilityCondition.RESPONSE_INFORMED:
            self._fail("A0 does not have revision permission")
        if self._revision_count != 0:
            self._fail("M9 permits at most one revision")
        if plan_id not in self._plans:
            self._fail("revised plan is outside the frozen candidate library")
        if plan_id == self._initial_plan_id:
            self._fail("unchanged second interval must use retain")
        initial = self._plans[self._initial_plan_id]
        revised = self._plans[plan_id]
        if revised["intervals"][0] != initial["intervals"][0]:
            self._fail("revision attempted to change the first interval")
        self._revision_count = 1
        self._terminal_plan_id = plan_id
        self._state = SessionState.TERMINAL
        self._states.append(self._state.value)
        return self.receipt()

    def receipt(self) -> dict[str, Any]:
        """Build a terminal content-addressed receipt."""

        if self._state != SessionState.TERMINAL:
            self._fail("receipt requested before terminal state")
        assert self._observation is not None
        assert self._terminal_plan_id is not None
        content = self.contract.to_dict()
        initial = self._plans[self._initial_plan_id]
        terminal = self._plans[self._terminal_plan_id]
        payload: dict[str, Any] = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "receipt_id": "pending",
            "contract_id": self.contract.contract_id,
            "capability_condition": self.capability_condition.value,
            "midpoint_observation_id": self._observation["observation_id"],
            "trend_sign": self._observation["trend_sign"],
            "state_sequence": list(self._states),
            "initial_plan_id": self._initial_plan_id,
            "terminal_plan_id": self._terminal_plan_id,
            "first_interval_fingerprint": _fingerprint(initial["intervals"][0]),
            "initial_second_interval_fingerprint": _fingerprint(
                initial["intervals"][1]
            ),
            "terminal_second_interval_fingerprint": _fingerprint(
                terminal["intervals"][1]
            ),
            "revision_count": self._revision_count,
            "revision_applied": self._revision_count == 1,
            "parity_fingerprint": content["parity_inputs"]["parity_fingerprint"],
            "external_access": {
                "model_calls": 0,
                "real_tool_calls": 0,
                "simulator_calls": 0,
                "detector_calls": 0,
                "embedding_calls": 0,
                "actuator_calls": 0,
                "evaluation_records_read": 0,
            },
            "interpretation": "protocol_isolation_only",
        }
        payload["receipt_id"] = receipt_id_for(payload)
        _validate_receipt(payload, self.contract)
        return payload


def _validate_receipt(
    receipt: Mapping[str, Any], contract: CareerTwoIntervalContract
) -> None:
    expected_fields = {
        "schema_version",
        "receipt_id",
        "contract_id",
        "capability_condition",
        "midpoint_observation_id",
        "trend_sign",
        "state_sequence",
        "initial_plan_id",
        "terminal_plan_id",
        "first_interval_fingerprint",
        "initial_second_interval_fingerprint",
        "terminal_second_interval_fingerprint",
        "revision_count",
        "revision_applied",
        "parity_fingerprint",
        "external_access",
        "interpretation",
    }
    if set(receipt) != expected_fields:
        raise ContractViolation("M9 receipt fields drift")
    if receipt["schema_version"] != RECEIPT_SCHEMA_VERSION:
        raise ContractViolation("unsupported M9 receipt schema_version")
    if receipt["receipt_id"] != receipt_id_for(receipt):
        raise ContractViolation("M9 receipt_id mismatch")
    if receipt["contract_id"] != contract.contract_id:
        raise ContractViolation("M9 receipt contract mismatch")
    condition = CapabilityCondition(receipt["capability_condition"])
    if condition == CapabilityCondition.PREPLANNED:
        allowed_revisions = {0}
    else:
        allowed_revisions = {0, 1}
    if receipt["revision_count"] not in allowed_revisions:
        raise ContractViolation("M9 receipt revision count drift")
    if receipt["revision_applied"] != (receipt["revision_count"] == 1):
        raise ContractViolation("M9 receipt revision flag drift")
    if receipt["state_sequence"] != [
            SessionState.PRECOMMITTED.value,
            SessionState.AWAITING_MIDPOINT_DECISION.value,
            SessionState.TERMINAL.value]:
        raise ContractViolation("M9 terminal state sequence drift")
    if any(value != 0 for value in receipt["external_access"].values()):
        raise ContractViolation("M9 receipt reports external access")
    expected_access = {
        "model_calls",
        "real_tool_calls",
        "simulator_calls",
        "detector_calls",
        "embedding_calls",
        "actuator_calls",
        "evaluation_records_read",
    }
    if set(receipt["external_access"]) != expected_access:
        raise ContractViolation("M9 receipt external-access fields drift")
    if receipt["interpretation"] != "protocol_isolation_only":
        raise ContractViolation("M9 receipt overclaims its interpretation")
    content = contract.to_dict()
    plans = {item["plan_id"]: item for item in content["candidate_library"]}
    observations = {
        item["observation_id"]: item for item in content["fixture_pair"]
    }
    initial_id = content["parity_inputs"]["initial_plan_id"]
    if receipt["initial_plan_id"] != initial_id:
        raise ContractViolation("M9 receipt initial plan drift")
    if receipt["terminal_plan_id"] not in plans:
        raise ContractViolation("M9 receipt terminal plan is unknown")
    if receipt["midpoint_observation_id"] not in observations:
        raise ContractViolation("M9 receipt midpoint observation is unknown")
    if observations[receipt["midpoint_observation_id"]]["trend_sign"] != (
            receipt["trend_sign"]):
        raise ContractViolation("M9 receipt trend-sign lineage drift")
    initial = plans[initial_id]
    terminal = plans[receipt["terminal_plan_id"]]
    if receipt["first_interval_fingerprint"] != _fingerprint(
            initial["intervals"][0]):
        raise ContractViolation("M9 receipt first-interval fingerprint drift")
    if terminal["intervals"][0] != initial["intervals"][0]:
        raise ContractViolation("M9 receipt changed the first interval")
    if receipt["initial_second_interval_fingerprint"] != _fingerprint(
            initial["intervals"][1]):
        raise ContractViolation("M9 receipt initial second interval drift")
    if receipt["terminal_second_interval_fingerprint"] != _fingerprint(
            terminal["intervals"][1]):
        raise ContractViolation("M9 receipt terminal second interval drift")
    if receipt["parity_fingerprint"] != content["parity_inputs"][
            "parity_fingerprint"]:
        raise ContractViolation("M9 receipt parity fingerprint drift")
    if receipt["revision_count"] == 0 and receipt["terminal_plan_id"] != initial_id:
        raise ContractViolation("M9 receipt changed plan without a revision")
    if receipt["revision_count"] == 1 and receipt["terminal_plan_id"] == initial_id:
        raise ContractViolation("M9 receipt revision did not change the plan")


def run_reference_episode(
    contract: CareerTwoIntervalContract,
    capability_condition: CapabilityCondition,
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Run one deterministic witness episode over the offline fixture."""

    session = TwoIntervalSession(contract, capability_condition)
    session.present_midpoint(observation)
    if capability_condition == CapabilityCondition.PREPLANNED:
        return session.retain_precommitted_plan()
    sign = observation["trend_sign"]
    plan_id = contract.to_dict()["reference_policy"]["mapping"][sign]
    return session.revise_second_interval(plan_id)


def run_mirrored_fixture_pair(
    contract: CareerTwoIntervalContract,
) -> dict[str, Any]:
    """Run A0 and A1 over both frozen mirrored midpoint observations."""

    receipts = []
    for observation in contract.to_dict()["fixture_pair"]:
        for condition in (
            CapabilityCondition.PREPLANNED,
            CapabilityCondition.RESPONSE_INFORMED,
        ):
            receipts.append(run_reference_episode(contract, condition, observation))

    by_condition = {
        condition.value: [
            item for item in receipts
            if item["capability_condition"] == condition.value
        ]
        for condition in CapabilityCondition
    }
    checks = {
        "A0_same_terminal_plan_across_mirrors": (
            len({item["terminal_plan_id"] for item in
                 by_condition[CapabilityCondition.PREPLANNED.value]}) == 1
        ),
        "A1_distinct_terminal_plans_across_mirrors": (
            len({item["terminal_plan_id"] for item in
                 by_condition[CapabilityCondition.RESPONSE_INFORMED.value]}) == 2
        ),
        "A0_zero_revisions": all(
            item["revision_count"] == 0
            for item in by_condition[CapabilityCondition.PREPLANNED.value]
        ),
        "A1_exactly_one_revision_per_fixture": all(
            item["revision_count"] == 1
            for item in by_condition[CapabilityCondition.RESPONSE_INFORMED.value]
        ),
        "first_interval_identical_everywhere": (
            len({item["first_interval_fingerprint"] for item in receipts}) == 1
        ),
        "all_parity_fingerprints_identical": (
            len({item["parity_fingerprint"] for item in receipts}) == 1
        ),
        "all_external_access_flags_false": all(
            all(value == 0 for value in item["external_access"].values())
            for item in receipts
        ),
        "all_receipts_terminal_and_content_addressed": all(
            item["state_sequence"][-1] == SessionState.TERMINAL.value
            and item["receipt_id"] == receipt_id_for(item)
            for item in receipts
        ),
    }
    if set(checks) != set(
            contract.to_dict()["acceptance_gate"]["required_checks"]):
        raise ContractViolation("M9 computed checks do not match preregistration")
    if not all(checks.values()):
        failed = sorted(key for key, value in checks.items() if not value)
        raise ContractViolation(f"M9 mirrored fixture failed: {failed}")
    payload: dict[str, Any] = {
        "schema_version": PAIR_SCHEMA_VERSION,
        "pair_id": "pending",
        "contract_id": contract.contract_id,
        "receipts": receipts,
        "checks": checks,
        "verdict": "PASS_PROTOCOL_ISOLATION_ONLY",
    }
    payload["pair_id"] = pair_id_for(payload)
    return payload


def _plan(role: str, second_strategy: str, direction: str) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "plan_id": "pending",
        "role": role,
        "intervals": [
            {
                "index": 1,
                "strategy_id": "B1_constant_micro_bias",
                "qualitative_direction": "fixed_shared_reference",
                "magnitude_token": "uninstantiated_low_amplitude_token",
                "executable": False,
            },
            {
                "index": 2,
                "strategy_id": second_strategy,
                "qualitative_direction": direction,
                "magnitude_token": "uninstantiated_low_amplitude_token",
                "executable": False,
            },
        ],
    }
    plan["plan_id"] = plan_id_for(plan)
    return plan


def _observation(condition_id: str, trend_sign: str) -> dict[str, Any]:
    observation: dict[str, Any] = {
        "observation_id": "pending",
        "condition_id": condition_id,
        "schema": "synthetic_midpoint_voltage_trend/v1",
        "trend_sign": trend_sign,
        "synthetic": True,
        "physical_claim": False,
        "units": "qualitative_fixture_token",
    }
    observation["observation_id"] = observation_id_for(observation)
    return observation


def build_career_two_interval_contract() -> CareerTwoIntervalContract:
    """Build the canonical M9 protocol-isolation contract."""

    initial = _plan(
        "precommitted_initial",
        "B1_constant_micro_bias",
        "fixed_shared_reference",
    )
    positive = _plan(
        "positive_midpoint_witness",
        "B6_trend_aligned_bias",
        "positive",
    )
    negative = _plan(
        "negative_midpoint_witness",
        "B6_trend_aligned_bias",
        "negative",
    )
    plans = [initial, negative, positive]
    observation_schema = {
        "schema": "synthetic_midpoint_voltage_trend/v1",
        "fields": ["condition_id", "trend_sign"],
        "trend_sign_enum": ["negative", "positive"],
        "units": "qualitative_fixture_token",
    }
    history = {
        "history": [],
        "frozen_before_pair": True,
        "cross_condition_learning": False,
    }
    budget = {
        "source": "M8_matched_budget_axes",
        "values": "uninstantiated",
        "execution_authorized": False,
    }
    schedule = {
        "interval_count": 2,
        "midpoint_count": 1,
        "duration": "uninstantiated",
    }
    safety_shield = {
        "status": "interface_placeholder_only",
        "execution_authorized": False,
    }
    parity_base = {
        "initial_plan_id": initial["plan_id"],
        "candidate_library_fingerprint": _fingerprint(plans),
        "observation_schema": observation_schema,
        "observation_schema_fingerprint": _fingerprint(observation_schema),
        "history": history,
        "history_fingerprint": _fingerprint(history),
        "budget": budget,
        "budget_fingerprint": _fingerprint(budget),
        "schedule": schedule,
        "schedule_fingerprint": _fingerprint(schedule),
        "safety_shield": safety_shield,
        "safety_shield_fingerprint": _fingerprint(safety_shield),
    }
    parity = dict(parity_base)
    parity["parity_fingerprint"] = _fingerprint(parity_base)
    fixtures = [
        _observation("mirror_negative", "negative"),
        _observation("mirror_positive", "positive"),
    ]
    content: dict[str, Any] = {
        "schema_version": TWO_INTERVAL_SCHEMA_VERSION,
        "contract_id": "pending",
        "milestone": "M9",
        "title": "Offline CAREER two-interval revision-permission fixture",
        "governance": dict(REQUIRED_GOVERNANCE),
        "source_lineage": {
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "m8_contract_id": M8_CONTRACT_ID,
            "m9_design_decision": M9_DESIGN_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        },
        "protocol": {
            "action_interval_count": 2,
            "midpoint_observation_count": 1,
            "maximum_treatment_revisions": 1,
            "control_revision_count": 0,
            "revision_scope": "second_interval_only",
            "revision_window": "after_midpoint_before_second_interval",
            "first_interval_immutable": True,
            "terminal_state_immutable": True,
            "invalid_transition_policy": "fail_closed_no_retry",
            "paired_history_rule": "freeze_before_pair_no_cross_condition_learning",
            "physical_units_present": False,
            "executable_setpoints_present": False,
        },
        "parity_inputs": parity,
        "candidate_library": plans,
        "fixture_pair": fixtures,
        "reference_policy": {
            "role": "deterministic_protocol_witness_only",
            "control_rule": "retain_precommitted_plan",
            "treatment_rule": "map_trend_sign_to_declared_plan",
            "mapping": {
                "negative": negative["plan_id"],
                "positive": positive["plan_id"],
            },
            "claim_boundary": "not_an_attack_effectiveness_or_reasoning_policy",
        },
        "acceptance_gate": {
            "required_checks": sorted({
                "A0_same_terminal_plan_across_mirrors",
                "A1_distinct_terminal_plans_across_mirrors",
                "A0_zero_revisions",
                "A1_exactly_one_revision_per_fixture",
                "first_interval_identical_everywhere",
                "all_parity_fingerprints_identical",
                "all_external_access_flags_false",
                "all_receipts_terminal_and_content_addressed",
            }),
            "passing_interpretation": "protocol_isolation_only",
        },
        "limitations": sorted({
            "no_physical_effect_claim",
            "no_stealth_or_alarm_claim",
            "no_policy_quality_claim",
            "no_llm_or_tool_use_claim",
            "no_runtime_readiness_claim",
            "no_campaign_authorization",
        }),
        "next_gate": {
            "id": "M10_validated_resource_admission_contracts",
            "scope": "offline_contracts_for_S_and_M_only",
            "model_call": False,
            "real_tool_execution": False,
            "simulator_or_detector_access": False,
        },
    }
    content["contract_id"] = contract_id_for(content)
    return CareerTwoIntervalContract(content)


def build_m9_artifact() -> dict[str, Any]:
    """Build the canonical checked-in M9 contract plus passing evidence."""

    contract = build_career_two_interval_contract()
    return {
        "contract": contract.to_dict(),
        "fixture_pair_evidence": run_mirrored_fixture_pair(contract),
    }


def load_m9_artifact(path: str | Path) -> dict[str, Any]:
    """Load and semantically validate a checked-in M9 artifact."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(payload) != {"contract", "fixture_pair_evidence"}:
        raise ContractViolation("M9 artifact fields drift")
    contract = CareerTwoIntervalContract(payload["contract"])
    expected = run_mirrored_fixture_pair(contract)
    if payload["fixture_pair_evidence"] != expected:
        raise ContractViolation("M9 fixture-pair evidence mismatch")
    return payload
