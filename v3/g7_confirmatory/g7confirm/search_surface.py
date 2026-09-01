"""Content-addressed shared search surfaces for IA3/IA4 comparisons."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .candidates import CandidateLibrary, CandidateRewardSpec
from .orchestration_contract import (
    OBSERVATION_SCHEMA_VERSION,
    OUTCOME_SCHEMA_VERSION,
    PLAN_SCHEMA_VERSION,
    CapabilityProfile,
    ContractViolation,
    OrchestrationRung,
    StrategyLibrary,
    ToolContract,
)


SEARCH_SURFACE_SCHEMA_VERSION = "grideval-g7-search-surface/v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class SearchSurfaceManifest:
    """Immutable canonical payload shared by both decision cores."""

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        if copied.get("schema_version") != SEARCH_SURFACE_SCHEMA_VERSION:
            raise ContractViolation("unsupported search-surface schema_version")
        if copied.get("development_only") is not True:
            raise ContractViolation("search surface must remain development-only")
        if copied.get("campaign_authorized") is not False:
            raise ContractViolation("search surface cannot authorize a campaign")
        if copied.get("evaluation_sealed") is not True:
            raise ContractViolation("search surface must keep evaluation sealed")
        self._canonical_content = _canonical_json(copied)

    @property
    def search_surface_id(self) -> str:
        digest = hashlib.sha256(
            self._canonical_content.encode("utf-8")
        ).hexdigest()
        return f"surface_{digest}"

    def content_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    def to_dict(self) -> dict[str, Any]:
        payload = self.content_dict()
        payload["search_surface_id"] = self.search_surface_id
        return payload

    def fingerprint(self) -> str:
        return self.search_surface_id.removeprefix("surface_")


def build_search_surface(*, profile: CapabilityProfile,
                         strategy_library: StrategyLibrary,
                         candidate_library: CandidateLibrary,
                         reward_spec: CandidateRewardSpec,
                         tool_contract: ToolContract) -> SearchSurfaceManifest:
    """Build one rung-neutral manifest after validating all exposed content."""

    if profile.rung not in {OrchestrationRung.IA3, OrchestrationRung.IA4}:
        raise ContractViolation("shared search surface requires an IA3 or IA4 profile")
    candidates = candidate_library.candidates
    if len(candidates) > profile.candidate_count_cap:
        raise ContractViolation("candidate library exceeds candidate_count_cap")
    if profile.history_limit < len(candidates):
        raise ContractViolation(
            "history_limit must retain at least one outcome per candidate"
        )

    for candidate in candidates:
        if len(candidate.steps) > profile.max_strategies_per_plan:
            raise ContractViolation("candidate exceeds max_strategies_per_plan")
        if len(candidate.target_ids) > profile.authority.max_targets_per_plan:
            raise ContractViolation("candidate exceeds max_targets_per_plan")
        if not set(candidate.target_ids).issubset(
                profile.authority.allowed_devices):
            raise ContractViolation("candidate targets an unauthorized device")
        for step in candidate.steps:
            if step.strategy_id not in profile.allowed_strategy_ids:
                raise ContractViolation("candidate uses a disallowed strategy")
            strategy_library.get(step.strategy_id).validate_step(step)

    strategy_cards = strategy_library.describe_allowed(
        profile.allowed_strategy_ids
    )
    candidate_payload = candidate_library.surface_payload()
    tool_specs = tool_contract.describe_allowed(profile.allowed_tool_names)
    content = {
        "schema_version": SEARCH_SURFACE_SCHEMA_VERSION,
        "development_only": True,
        "campaign_authorized": False,
        "evaluation_sealed": True,
        "participant_rungs": ["IA3", "IA4"],
        "contract_versions": {
            "typed_plan": PLAN_SCHEMA_VERSION,
            "observation": OBSERVATION_SCHEMA_VERSION,
            "outcome_history": OUTCOME_SCHEMA_VERSION,
        },
        "capability": {
            "payload": profile.parity_payload(),
            "fingerprint": profile.parity_fingerprint(),
        },
        "strategy_library": {
            "cards": strategy_cards,
            "fingerprint": _fingerprint(strategy_cards),
        },
        "candidate_library": {
            "candidate_count": len(candidates),
            "ordered_candidate_ids": candidate_library.ids(),
            "candidates": candidate_payload,
            "fingerprint": candidate_library.fingerprint(),
        },
        "reward": {
            "spec": reward_spec.to_dict(),
            "fingerprint": reward_spec.fingerprint(),
        },
        "tools": {
            "specs": tool_specs,
            "fingerprint": tool_contract.schema_fingerprint(
                profile.allowed_tool_names
            ),
        },
    }
    return SearchSurfaceManifest(content)


def assert_search_surface_parity(left: SearchSurfaceManifest,
                                 right: SearchSurfaceManifest) -> None:
    """Fail unless IA3 and IA4 receive byte-equivalent canonical surfaces."""

    if left.search_surface_id != right.search_surface_id:
        raise ContractViolation("IA3/IA4 search-surface parity mismatch")
