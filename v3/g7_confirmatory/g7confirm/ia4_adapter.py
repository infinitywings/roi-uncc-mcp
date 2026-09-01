"""Strict offline IA4 request builder and fixture-response adapter."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .candidates import CandidateLibrary, CandidateRewardSpec
from .orchestration_contract import (
    CapabilityProfile,
    ContractViolation,
    ControllerDecision,
    OrchestrationRung,
    OutcomeRecord,
    StrategyLibrary,
    ToolCallRecord,
    ToolContract,
    TypedObservation,
    bounded_visible_history,
)
from .search_surface import (
    SearchSurfaceManifest,
    assert_search_surface_parity,
    build_search_surface,
)


IA4_REQUEST_SCHEMA_VERSION = "grideval-g7-ia4-request/v1"
IA4_RESPONSE_SCHEMA_VERSION = "grideval-g7-ia4-fixture-response/v1"


def _canonical_fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class IA4FixtureResult:
    """Auditable result of parsing one already-recorded offline response."""

    decision: ControllerDecision
    validated_tool_calls: tuple[ToolCallRecord, ...]
    response_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": {
                "kind": self.decision.kind.value,
                "reason": self.decision.reason,
                "candidate_id": self.decision.candidate_id,
                "plan": self.decision.plan.to_dict() if self.decision.plan else None,
            },
            "validated_tool_calls": [
                item.to_dict() for item in self.validated_tool_calls
            ],
            "response_fingerprint": self.response_fingerprint,
        }


class IA4FixtureAdapter:
    """Serialize IA4 context and parse fixtures without executing a model or tool."""

    _COMMON_RESPONSE_KEYS = frozenset({
        "schema_version",
        "search_surface_id",
        "decision",
        "rationale",
        "used_tool_call_ids",
    })

    def __init__(self, *, profile: CapabilityProfile,
                 strategy_library: StrategyLibrary,
                 candidate_library: CandidateLibrary,
                 reward_spec: CandidateRewardSpec,
                 tool_contract: ToolContract,
                 search_surface: SearchSurfaceManifest):
        if profile.rung is not OrchestrationRung.IA4:
            raise ContractViolation("IA4 fixture adapter requires an IA4 profile")
        current_surface = build_search_surface(
            profile=profile,
            strategy_library=strategy_library,
            candidate_library=candidate_library,
            reward_spec=reward_spec,
            tool_contract=tool_contract,
        )
        assert_search_surface_parity(search_surface, current_surface)
        self.profile = profile
        self.strategy_library = strategy_library
        self.candidate_library = candidate_library
        self.reward_spec = reward_spec
        self.tool_contract = tool_contract
        self.search_surface = search_surface

    def build_request(self, observation: TypedObservation,
                      history: Sequence[OutcomeRecord]) -> dict[str, Any]:
        """Build a deterministic request payload; no external action is possible."""

        bounded = bounded_visible_history(
            self.profile,
            current_window=observation.window,
            history=history,
        )
        for item in bounded:
            if item.reward is not None and item.candidate_id is None:
                raise ContractViolation(
                    "candidate-aware IA4 requires candidate_id on rewarded history"
                )
            if item.candidate_id is None:
                continue
            candidate = self.candidate_library.get(item.candidate_id)
            expected_strategy_id = "+".join(candidate.strategy_ids)
            if item.strategy_id != expected_strategy_id:
                raise ContractViolation(
                    "history strategy_id does not match candidate lineage"
                )
            if item.reward is not None:
                self.reward_spec.objective_value(item.reward)

        return {
            "schema_version": IA4_REQUEST_SCHEMA_VERSION,
            "development_only": True,
            "campaign_authorized": False,
            "evaluation_sealed": True,
            "search_surface_id": self.search_surface.search_surface_id,
            "task": {
                "instruction": (
                    "Use the declared strategy cards, bounded candidates, visible "
                    "history, and only the declared tools to select exactly one "
                    "candidate, issue a safety refusal, or choose no action."
                ),
                "allowed_decisions": ["plan", "safety_refusal", "no_action"],
                "plan_policy": "select_one_candidate_id_without_modification",
                "tool_policy": "use_only_declared_tools_within_all_caps",
            },
            "search_surface": self.search_surface.to_dict(),
            "observation": observation.to_dict(),
            "visible_history": [item.to_dict() for item in bounded],
        }

    def parse_fixture_response(
            self, payload: Mapping[str, Any], *,
            tool_calls: Sequence[ToolCallRecord] = ()) -> IA4FixtureResult:
        """Fail closed on any response or recorded-tool deviation."""

        if not isinstance(payload, Mapping):
            raise ContractViolation("IA4 fixture response must be an object")
        if any(not isinstance(key, str) for key in payload):
            raise ContractViolation("IA4 fixture response keys must be strings")
        decision_name = payload.get("decision")
        expected_keys = set(self._COMMON_RESPONSE_KEYS)
        if decision_name == "plan":
            expected_keys.add("candidate_id")
        if set(payload) != expected_keys:
            raise ContractViolation("IA4 fixture response has unexpected fields")
        if payload.get("schema_version") != IA4_RESPONSE_SCHEMA_VERSION:
            raise ContractViolation("unsupported IA4 fixture-response schema_version")
        if payload.get("search_surface_id") != self.search_surface.search_surface_id:
            raise ContractViolation("IA4 response search_surface_id mismatch")
        if decision_name not in {"plan", "safety_refusal", "no_action"}:
            raise ContractViolation("unsupported IA4 decision")

        rationale = payload.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ContractViolation("IA4 response rationale is required")
        if len(rationale) > 2000:
            raise ContractViolation("IA4 response rationale exceeds 2000 characters")

        declared_call_ids = payload.get("used_tool_call_ids")
        if not isinstance(declared_call_ids, list) or any(
                not isinstance(item, str) or not item
                for item in declared_call_ids):
            raise ContractViolation("used_tool_call_ids must be a string array")
        if len(declared_call_ids) != len(set(declared_call_ids)):
            raise ContractViolation("used_tool_call_ids contains duplicates")
        calls = tuple(tool_calls)
        if any(not isinstance(item, ToolCallRecord) for item in calls):
            raise ContractViolation("tool_calls must contain ToolCallRecord values")
        if declared_call_ids != [item.call_id for item in calls]:
            raise ContractViolation("used_tool_call_ids do not match supplied tool calls")
        if any(item.validation_result != "accepted" for item in calls):
            raise ContractViolation("IA4 response used a non-accepted tool call")
        self.tool_contract.validate_calls(self.profile, calls)

        if decision_name == "plan":
            candidate_id = payload.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                raise ContractViolation("plan response requires a candidate_id")
            candidate = self.candidate_library.get(candidate_id)
            plan = candidate.instantiate(OrchestrationRung.IA4, rationale)
            decision = ControllerDecision.submit(
                plan,
                reason="ia4_fixture_candidate_selection",
                candidate_id=candidate_id,
            )
        elif decision_name == "safety_refusal":
            decision = ControllerDecision.refuse(rationale)
        else:
            decision = ControllerDecision.no_action(rationale)

        return IA4FixtureResult(
            decision=decision,
            validated_tool_calls=calls,
            response_fingerprint=_canonical_fingerprint(dict(payload)),
        )
