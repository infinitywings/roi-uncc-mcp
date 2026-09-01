"""Bounded M6 model transport over the offline M5 read-only fixture protocol."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .budget import DualBudget
from .ia4_model import OpenAICompletionRecord, extract_openai_completion
from .ia4_smoke_fixture import (
    build_m4_smoke_adapter,
    build_smoke_capability_profile,
)
from .ia4_tool_loop import (
    FixtureToolResult,
    IAInteractiveSession,
    InteractiveState,
    M5InteractiveProtocol,
    build_m5_protocol,
)
from .model_client import ModelClientError, discover_model, request_json
from .orchestration_contract import (
    ContractViolation,
    ControllerDecision,
    InformationLevel,
    OrchestrationRung,
    PlanValidator,
    SideEffectClass,
    ToolCallRecord,
    TypedObservation,
)


M6_OVERLAY_SCHEMA_VERSION = "grideval-g7-ia4-interactive-model-overlay/v1"
M6_REQUEST_SCHEMA_VERSION = "grideval-g7-ia4-interactive-model-request/v1"
M6_SMOKE_SCHEMA_VERSION = "grideval-g7-ia4-interactive-model-smoke/v1"
M6_TOOL_CALL_ID = "call_observe_model_0001"


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ModelClientError("interactive model value is not canonical JSON") from exc


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_bare_object(content: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ModelClientError(
                    f"interactive completion contains duplicate field: {key}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ModelClientError(
            f"interactive completion contains non-finite constant: {value}"
        )

    try:
        payload = json.loads(
            content,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ModelClientError(
            "interactive completion is not one exact JSON value"
        ) from exc
    if not isinstance(payload, dict):
        raise ModelClientError("interactive completion must be a JSON object")
    return payload


@dataclass(frozen=True)
class M6ModelOverlay:
    """Content-addressed authority and resource overlay for one M6 smoke."""

    protocol: M5InteractiveProtocol
    model_id: str
    development_seeds: tuple[int, ...]
    temperature: float = 0.0
    max_tokens_per_turn: int = 512
    timeout_s: float = 120.0

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ModelClientError("M6 model_id is required")
        if len(self.development_seeds) < 2:
            raise ModelClientError("M6 requires two declared development seeds")
        if len(set(self.development_seeds)) != len(self.development_seeds):
            raise ModelClientError("M6 development seeds contain duplicates")
        if not math.isfinite(float(self.temperature)) or not (
                0.0 <= self.temperature <= 1.0):
            raise ModelClientError("M6 temperature must lie in [0, 1]")
        if not 1 <= int(self.max_tokens_per_turn) <= (
                self.protocol.max_completion_tokens_per_turn):
            raise ModelClientError("M6 output cap exceeds the M5 per-turn cap")
        if not math.isfinite(float(self.timeout_s)) or not (
                0.0 < self.timeout_s <= 180.0):
            raise ModelClientError("M6 timeout_s must lie in (0, 180]")

    def content_dict(self) -> dict[str, Any]:
        return {
            "schema_version": M6_OVERLAY_SCHEMA_VERSION,
            "development_only": True,
            "campaign_authorized": False,
            "evaluation_sealed": True,
            "base_protocol_id": self.protocol.protocol_id,
            "base_protocol_model_transport_authorized": False,
            "overlay_model_transport_authorized": True,
            "tool_execution_authorized": False,
            "fixture_injection_authorized": True,
            "simulator_access_authorized": False,
            "detector_access_authorized": False,
            "embedding_access_authorized": False,
            "model_id": self.model_id,
            "development_seeds": list(self.development_seeds[:2]),
            "temperature": float(self.temperature),
            "max_tokens_per_turn": int(self.max_tokens_per_turn),
            "timeout_s": float(self.timeout_s),
            "network_request_cap": 3,
            "completion_request_cap": 2,
            "tool_call_id": M6_TOOL_CALL_ID,
            "turn_policy": [
                "turn_0_must_request_observe_state",
                "inject_exact_content_addressed_fixture_without_execution",
                "turn_1_must_terminate",
            ],
            "failure_policy": "no_retry_preserve_receipt_fail_closed",
        }

    @property
    def overlay_id(self) -> str:
        return "m6overlay_" + _sha256(self.content_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self.content_dict()
        payload["overlay_id"] = self.overlay_id
        return payload


@dataclass(frozen=True)
class M6ModelRequest:
    """Exact session and chat request fingerprints for one M6 turn."""

    turn_index: int
    session_request: Mapping[str, Any]
    chat_payload: Mapping[str, Any]
    session_request_sha256: str
    chat_request_sha256: str

    def __post_init__(self) -> None:
        if self.session_request.get("request_sha256") != (
                self.session_request_sha256):
            raise ModelClientError("M6 session request fingerprint mismatch")
        chat = _canonical_copy(self.chat_payload)
        if self.chat_request_sha256 != _sha256(chat):
            raise ModelClientError("M6 chat request fingerprint mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": M6_REQUEST_SCHEMA_VERSION,
            "turn_index": self.turn_index,
            "session_request": _canonical_copy(self.session_request),
            "chat_payload": _canonical_copy(self.chat_payload),
            "session_request_sha256": self.session_request_sha256,
            "chat_request_sha256": self.chat_request_sha256,
        }


def _stage_response_format(session: IAInteractiveSession, *,
                           require_tool: bool) -> dict[str, Any]:
    variants = session.response_schema()["oneOf"]
    selected = []
    for variant in variants:
        decision = variant["properties"]["decision"]["const"]
        if (decision == "tool_request") is require_tool:
            selected.append(variant)
    if not selected:
        raise ModelClientError("M6 stage response schema has no variants")

    def provider_subset(value: Any) -> Any:
        """Drop advisory keywords unsupported by the vLLM guided decoder."""

        if isinstance(value, Mapping):
            return {
                key: provider_subset(item)
                for key, item in value.items()
                if key != "uniqueItems"
            }
        if isinstance(value, list):
            return [provider_subset(item) for item in value]
        return value

    guided = selected[0] if len(selected) == 1 else {"oneOf": selected}
    if require_tool:
        guided = _canonical_copy(guided)
        guided["properties"]["call_id"] = {"const": M6_TOOL_CALL_ID}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": (
                "g7_m6_tool_request" if require_tool else "g7_m6_terminal"
            ),
            "strict": True,
            "schema": _canonical_copy(provider_subset(guided)),
        },
    }


def build_m6_model_request(*, overlay: M6ModelOverlay,
                           session: IAInteractiveSession,
                           require_tool: bool) -> M6ModelRequest:
    """Build one stage-locked OpenAI-compatible request without sending it."""

    turn = session.turn_index
    if turn not in (0, 1):
        raise ModelClientError("M6 supports only turn indices 0 and 1")
    if require_tool is not (turn == 0):
        raise ModelClientError("M6 stage does not match the session turn")
    session_request = session.next_request()
    system = (
        "You are the IA4 decision core in a development-only interactive "
        "protocol qualification. A plan is non-actuating and remains subject "
        "to external validation. Governance flags constrain the harness, not "
        "candidate selection. On turn 0, request the declared read-only "
        "observe_state tool exactly once. The harness will inject a frozen "
        f"fixture without executing a tool. Use call_id {M6_TOOL_CALL_ID}. "
        "On turn 1, use only that result and "
        "the supplied content-addressed surface to select one unchanged "
        "candidate, issue a safety refusal, or choose no action. Never request "
        "an undeclared tool, edit a candidate, infer hidden detector data, or "
        "claim runtime evidence. Return exactly one JSON object matching the "
        "stage schema and no markdown or extra text."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": _canonical_json(session_request)},
    ]
    chat_payload = {
        "model": overlay.model_id,
        "temperature": float(overlay.temperature),
        "max_tokens": int(overlay.max_tokens_per_turn),
        "seed": int(overlay.development_seeds[turn]),
        "stream": False,
        "n": 1,
        "response_format": _stage_response_format(
            session, require_tool=require_tool
        ),
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": messages,
    }
    return M6ModelRequest(
        turn_index=turn,
        session_request=session_request,
        chat_payload=chat_payload,
        session_request_sha256=session_request["request_sha256"],
        chat_request_sha256=_sha256(chat_payload),
    )


def _session_usage(record: OpenAICompletionRecord) -> dict[str, int]:
    result: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = record.usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ModelClientError(f"M6 completion usage is missing {key}")
        result[key] = value
    return result


def _fixture_output() -> dict[str, Any]:
    return {
        "schema_version": "observation-result/v1",
        "window": 0,
        "time_s": 0,
        "values": {"prior_alarm": False, "voltage_pu": 0.99},
    }


def perform_bounded_interactive_model_smoke(
        *, base_url: str, overlay: M6ModelOverlay) -> dict[str, Any]:
    """Perform one discovery and at most two completions over a fixture result."""

    adapter = overlay.protocol.adapter
    session = IAInteractiveSession(
        protocol=overlay.protocol,
        profile=build_smoke_capability_profile(OrchestrationRung.IA4),
        observation=TypedObservation(
            0,
            0,
            {
                "context": "synthetic_interface_fixture",
                "prior_alarm": False,
                "voltage_pu": 1.0,
            },
        ),
        history=(),
        decision_core_id=overlay.model_id,
    )
    network_requests = 0
    completion_requests = 0
    request_records: list[dict[str, Any]] = []
    completion_records: list[dict[str, Any]] = []
    model_record: dict[str, Any] | None = None
    injected_result: FixtureToolResult | None = None
    error: str | None = None

    try:
        network_requests += 1
        discovered = discover_model(base_url, overlay.model_id, overlay.timeout_s)
        model_record = {
            key: discovered.get(key)
            for key in ("id", "owned_by", "root", "max_model_len")
            if key in discovered
        }
        for stage in range(2):
            require_tool = stage == 0
            request = build_m6_model_request(
                overlay=overlay,
                session=session,
                require_tool=require_tool,
            )
            request_records.append(request.to_dict())
            network_requests += 1
            completion_requests += 1
            body = request_json(
                base_url.rstrip("/") + "/chat/completions",
                timeout_s=overlay.timeout_s,
                payload=dict(request.chat_payload),
            )
            completion = extract_openai_completion(
                body, expected_model_id=overlay.model_id
            )
            completion_records.append(completion.to_dict())
            payload = _parse_bare_object(completion.content)
            expected_decision = "tool_request" if require_tool else None
            if require_tool and payload.get("decision") != expected_decision:
                reason = "M6 turn 0 did not request observe_state"
                session.fail_closed(reason)
                raise ContractViolation(reason)
            if not require_tool and payload.get("decision") == "tool_request":
                reason = "M6 turn 1 did not terminate"
                session.fail_closed(reason)
                raise ContractViolation(reason)
            session.accept_model_turn(
                request_sha256=request.session_request_sha256,
                payload=payload,
                model_id=overlay.model_id,
                usage=_session_usage(completion),
            )
            if require_tool:
                if session.state is not InteractiveState.AWAITING_TOOL_RESULT:
                    raise ContractViolation("M6 turn 0 did not enter tool-result state")
                outstanding = session.outstanding_request
                assert outstanding is not None
                if outstanding.tool_name != "observe_state":
                    raise ContractViolation("M6 requested the wrong tool")
                injected_result = FixtureToolResult.build(
                    protocol=overlay.protocol,
                    request=outstanding,
                    output=_fixture_output(),
                    wall_clock_ms=0.0,
                )
                session.submit_tool_result(injected_result)
                continue
            if session.state is not InteractiveState.TERMINAL:
                raise ContractViolation("M6 terminal turn did not terminate")

        if session.state is not InteractiveState.TERMINAL:
            raise ContractViolation("M6 exhausted completion cap without termination")
        status = "passed"
    except (ModelClientError, ContractViolation) as exc:
        error = str(exc)
        if session.state in {
                InteractiveState.AWAITING_MODEL,
                InteractiveState.AWAITING_TOOL_RESULT}:
            session.fail_closed(error)
        status = "failed_closed"

    if network_requests > 3 or completion_requests > 2:
        raise ModelClientError("M6 transport exceeded its hard request cap")
    receipt = (
        session.receipt()
        if session.state in {InteractiveState.TERMINAL, InteractiveState.FAILED_CLOSED}
        else None
    )
    return {
        "status": status,
        "error": error,
        "network_requests": network_requests,
        "completion_requests": completion_requests,
        "model_record": model_record,
        "requests": request_records,
        "completions": completion_records,
        "injected_tool_result": (
            injected_result.to_dict() if injected_result else None
        ),
        "session_receipt": receipt,
        "tool_execution_used": False,
        "simulator_accessed": False,
        "detector_accessed": False,
        "embedding_accessed": False,
    }


def build_default_m6_overlay(*, model_id: str,
                             development_seeds: Sequence[int],
                             timeout_s: float) -> M6ModelOverlay:
    """Build the fixed M6 overlay from the unchanged M4/M5 synthetic surface."""

    return M6ModelOverlay(
        protocol=build_m5_protocol(build_m4_smoke_adapter()),
        model_id=model_id,
        development_seeds=tuple(map(int, development_seeds)),
        temperature=0.0,
        max_tokens_per_turn=512,
        timeout_s=timeout_s,
    )


def validate_m6_terminal_receipt(*, overlay: M6ModelOverlay,
                                 receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Replay a terminal receipt through the common plan and budget validator."""

    if receipt.get("state") != InteractiveState.TERMINAL.value:
        raise ContractViolation("M6 receipt is not terminal")
    if receipt.get("protocol_id") != overlay.protocol.protocol_id:
        raise ContractViolation("M6 receipt protocol_id mismatch")
    if receipt.get("actor_rung") != OrchestrationRung.IA4.value:
        raise ContractViolation("M6 receipt is not an IA4 episode")
    terminal = receipt.get("terminal_decision")
    if not isinstance(terminal, Mapping) or terminal.get("kind") != "plan":
        raise ContractViolation("M6 receipt does not contain a terminal plan")
    candidate_id = terminal.get("candidate_id")
    rationale = terminal.get("plan", {}).get("rationale")
    if not isinstance(candidate_id, str) or not isinstance(rationale, str):
        raise ContractViolation("M6 terminal plan lineage is incomplete")
    candidate = overlay.protocol.adapter.candidate_library.get(candidate_id)
    plan = candidate.instantiate(OrchestrationRung.IA4, rationale)
    if plan.to_dict() != terminal.get("plan"):
        raise ContractViolation("M6 terminal plan bytes drift from its candidate")
    decision = ControllerDecision.submit(
        plan,
        reason="m5_interactive_candidate_selection",
        candidate_id=candidate_id,
    )
    calls: list[ToolCallRecord] = []
    for item in receipt.get("tool_calls", []):
        calls.append(ToolCallRecord(
            call_id=item["call_id"],
            caller_rung=OrchestrationRung(item["caller_rung"]),
            tool_name=item["tool_name"],
            input_schema_version=item["input_schema_version"],
            output_schema_version=item["output_schema_version"],
            side_effect_class=SideEffectClass(item["side_effect_class"]),
            simulation_time_advance_s=item["simulation_time_advance_s"],
            outer_rollout_cost=item["outer_rollout_cost"],
            wall_clock_ms=item["wall_clock_ms"],
            model_tokens=item["model_tokens"],
            returned_information_level=InformationLevel[
                item["returned_information_level"].upper()
            ],
            validation_result=item["validation_result"],
        ))
    profile = build_smoke_capability_profile(OrchestrationRung.IA4)
    validation = PlanValidator(
        profile=profile,
        strategy_library=overlay.protocol.adapter.strategy_library,
        tool_contract=overlay.protocol.adapter.tool_contract,
        dual_budget=DualBudget(
            window_cap=profile.authority.perturbed_window_cap,
            apparent_energy_cap_kvah=profile.authority.apparent_energy_cap_kvah,
            window_seconds=10.0,
        ),
    ).evaluate(
        decision,
        benign={"DER_A": (0.0, 0.0), "DER_B": (0.0, 0.0)},
        tool_calls=tuple(calls),
    )
    return validation.to_dict()
