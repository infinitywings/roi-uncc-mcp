"""Run one bounded live-model decision over the exact M25 real-adapter path.

M26 is decision-only. It may contact the already-running registered model and
invoke the local read-only M24 adapter once, but it never starts a service,
executes a selected plan, advances simulation time, or accesses evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ia4_adapter import IA4_RESPONSE_SCHEMA_VERSION
from .ia4_counterfactual import (
    M7_METRIC,
    M7_TARGETS,
    M7_TOOL_NAME,
    build_m7_adapter,
    build_m7_capability_profile,
    build_m7_protocol,
    validate_m7_terminal_receipt,
)
from .ia4_model import OpenAICompletionRecord, extract_openai_completion
from .ia4_tool_loop import (
    IAInteractiveSession,
    InteractiveState,
    M5_TOOL_REQUEST_SCHEMA_VERSION,
    RealAdapterToolResult,
)
from .m24_read_only_adapter import (
    EmpiricalSensitivityAdapter,
    build_contract as build_m24_contract,
)
from .m25_adapter_transaction import (
    build_contract as build_m25_contract,
    verify_qualification as verify_m25_qualification,
)
from .m25_independent_audit import verify_audit_receipt as verify_m25_audit
from .manifest import create_once_json
from .model_client import ModelClientError, discover_model, request_json
from .orchestration_contract import (
    ContractViolation,
    OrchestrationRung,
    TypedObservation,
)
from .preliminary_only_gate import (
    LLM_SERVICE_IDENTITY,
    validate_preliminary_action_request,
)


CONTRACT_SCHEMA_VERSION = "grideval-g7-m26-live-empirical-contract/v1"
RECEIPT_SCHEMA_VERSION = "grideval-g7-m26-live-empirical-receipt/v1"
REQUEST_SCHEMA_VERSION = "grideval-g7-m26-live-empirical-request/v1"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MYHTSJACSDYVE60Y80K6AJ"
DECISION_ID = "dec_01M1MYH0XYEVZA6SARSND8DJG4"
CLASSIFICATION = "PRELIMINARY_ONLY"
MODEL_ID = "qwen3.6-35b-a3b"
BASE_URL = "http://ccil1s26m8hj6lws:8000/v1"
DEVELOPMENT_SEEDS = (8107, 8108)
BUDGET_ID = "m26_one_discovery_two_completions_one_real_adapter"
CALL_ID = "call_m26_real_adapter_0001"
MAX_TOKENS_PER_TURN = 512
TIMEOUT_S = 120.0

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
M26_CODE_PATH = Path(__file__).resolve()
M5_CORE_PATH = Path(__file__).with_name("ia4_tool_loop.py")
SCHEMA_PATH = PACKAGE_ROOT / "m26_live_empirical_decision.schema.json"
SPEC_PATH = PACKAGE_ROOT / "experiment_spec.yaml"
M18_GATE_PATH = PACKAGE_ROOT / "artifacts" / "preliminary_only_gate_m18.json"
M7_CONTRACT_PATH = PACKAGE_ROOT / "artifacts" / "ia4_counterfactual_contract_m7.json"
M24_ROOT = PACKAGE_ROOT / "artifacts" / "m24_read_only_adapter_attempt1"
M24_CONTRACT_PATH = M24_ROOT / "contract.json"
M24_QUALIFICATION_PATH = M24_ROOT / "qualification_receipt.json"
M24_AUDIT_PATH = M24_ROOT / "independent_audit_receipt.json"
M25_ROOT = PACKAGE_ROOT / "artifacts" / "m25_adapter_transaction_attempt1"
M25_CONTRACT_PATH = M25_ROOT / "contract.json"
M25_QUALIFICATION_PATH = M25_ROOT / "qualification_receipt.json"
M25_AUDIT_PATH = M25_ROOT / "independent_audit_receipt.json"
ROADMAP_PATH = PACKAGE_ROOT / "roadmap_2026" / "report.html"
ORCHESTRATION_PATH = PACKAGE_ROOT / "ORCHESTRATION_CONTRACT.md"

EXPECTED_SOURCE_HASHES = {
    "experiment_spec": "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d",
    "M18_gate": "e31a49d758700a3d30e4d7e3d5469b831b3f52370954fa92238eac6aa4dc3e9d",
    "M5_transaction_core": "1292c635a97550cd0246bcce9955ab5e2538e9657a1c823b86cbca643f1df6f6",
    "M7_contract": "4cef8444c56c40ff493ed3add9847d43d9d12c72f9f1714597e7566109d26de2",
    "M24_contract": "95965833d0d49cb021fe4af89e2cd830d4cd904a2de6f7d12aad2ecd33721ee3",
    "M24_qualification": "6201770ced6029cf1c54a1d61b9d7a73d3c05c19d8edb83e9339df4d62fa65b8",
    "M24_independent_audit": "7149de87a983e96850676b335e89a58e3c9e1f0b0b804b07b8d74cf9df49a787",
    "M25_contract": "43fe76b9396fb5511902632085b6645e2d0af522026959449ddcc2960958785b",
    "M25_qualification": "e0fa95cfeaaae1dbe576844f6a7dd7f44af0d5f3251cbc14adf2d6ecba2c837e",
    "M25_independent_audit": "ff07cf12ec365a54b50b0d16d0d5501a194aec63961df3dae55469aff0a178bc",
    "roadmap_report": "c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b",
    "orchestration_contract": "2bfb23ffb8e17aac9f4c2ec41755d7cf97b01b1c70fc93cef26a637544294d3b",
}
EXPECTED_M7_PROTOCOL_ID = (
    "m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff"
)
EXPECTED_M7_SEARCH_SURFACE_ID = (
    "surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78"
)
EXPECTED_M24_PAYLOAD_SHA256 = (
    "c397c90c3240643c75323a166432ea67e1cae94648ec1dff2edbc9564c52d5e8"
)
EXPECTED_M25_CONTRACT_ID = (
    "m25contract_00400d7db95cdb2a0e30e8e66100dccc00742f6b9d4d8ddfa71334bc65615d27"
)
EXPECTED_M25_QUALIFICATION_ID = (
    "m25qual_1d3ffc1e3d2adc6fd442286a9c9f48326cf49bea8f3dc67232ae34f628be1b6c"
)
EXPECTED_M25_AUDIT_ID = (
    "m25audit_d6f3b79e83de9834d2d8b4e123b4ebe18f5d1b1e80e9b31cc410a1cb70578398"
)
FORBIDDEN_CONSUMER_KEYS = {
    "access_boundary",
    "adapter_invocation_receipt",
    "audit_binding",
    "contract_id",
    "files_read",
    "fingerprint",
    "invocation_id",
    "result_kind",
    "source_binding",
    "target_alias_map",
}


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
        raise ModelClientError("M26 value is not canonical JSON") from exc


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_json_file(path: Path, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ModelClientError(f"{label} contains duplicate field: {key}")
            result[key] = item
        return result

    def reject_constant(item: str) -> None:
        raise ModelClientError(f"{label} contains non-finite constant: {item}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelClientError(f"{label} is not one UTF-8 JSON value") from exc


def _artifact_sha256(value: Any) -> str:
    encoded = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _source_bindings() -> dict[str, dict[str, Any]]:
    paths = {
        "experiment_spec": SPEC_PATH,
        "M18_gate": M18_GATE_PATH,
        "M5_transaction_core": M5_CORE_PATH,
        "M7_contract": M7_CONTRACT_PATH,
        "M24_contract": M24_CONTRACT_PATH,
        "M24_qualification": M24_QUALIFICATION_PATH,
        "M24_independent_audit": M24_AUDIT_PATH,
        "M25_contract": M25_CONTRACT_PATH,
        "M25_qualification": M25_QUALIFICATION_PATH,
        "M25_independent_audit": M25_AUDIT_PATH,
        "roadmap_report": ROADMAP_PATH,
        "orchestration_contract": ORCHESTRATION_PATH,
    }
    bindings: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        digest = _sha256_file(path)
        if digest != EXPECTED_SOURCE_HASHES[name]:
            raise ModelClientError(f"M26 source hash drift: {name}")
        bindings[name] = {
            "path": _relative(path),
            "bytes": path.stat().st_size,
            "sha256": digest,
        }
    bindings["M26_code"] = {
        "path": _relative(M26_CODE_PATH),
        "bytes": M26_CODE_PATH.stat().st_size,
        "sha256": _sha256_file(M26_CODE_PATH),
    }
    bindings["M26_schema"] = {
        "path": _relative(SCHEMA_PATH),
        "bytes": SCHEMA_PATH.stat().st_size,
        "sha256": _sha256_file(SCHEMA_PATH),
    }
    return bindings


def _load_m25_payload() -> tuple[dict[str, Any], str]:
    stored_contract = _strict_json_file(M25_CONTRACT_PATH, "M25 contract")
    stored_receipt = _strict_json_file(M25_QUALIFICATION_PATH, "M25 receipt")
    stored_audit = _strict_json_file(M25_AUDIT_PATH, "M25 audit")
    if stored_contract != build_m25_contract():
        raise ModelClientError("M25 contract no longer matches executable bytes")
    if verify_m25_qualification(M25_ROOT):
        raise ModelClientError("M25 qualification verification failed")
    if verify_m25_audit(M25_ROOT, stored_audit):
        raise ModelClientError("M25 independent audit verification failed")
    if (
        stored_contract.get("contract_id") != EXPECTED_M25_CONTRACT_ID
        or stored_receipt.get("qualification_id")
        != EXPECTED_M25_QUALIFICATION_ID
        or stored_audit.get("audit_id") != EXPECTED_M25_AUDIT_ID
    ):
        raise ModelClientError("M25 content identity drift")
    transaction = stored_receipt.get("transactions", {}).get("IA3", {})
    payload = transaction.get("consumer_tool_result_event", {}).get("output")
    candidate_id = transaction.get("selected_candidate_id")
    if not isinstance(payload, dict) or not isinstance(candidate_id, str):
        raise ModelClientError("M25 deterministic control is incomplete")
    if _sha256_value(payload) != EXPECTED_M24_PAYLOAD_SHA256:
        raise ModelClientError("M25 empirical payload drift")
    if transaction.get("selected_target") != "DER_B":
        raise ModelClientError("M25 deterministic target drift")
    return _canonical_copy(payload), candidate_id


def build_action_request(seed: int) -> dict[str, Any]:
    if seed not in DEVELOPMENT_SEEDS:
        raise ModelClientError("M26 seed is outside the registered turn pair")
    request = {
        "action_id": f"m26_llm_turn_seed{seed}",
        "action_type": "local_LLM_inference",
        "partition_role": "attack_development",
        "seed": seed,
        "output_classification": CLASSIFICATION,
        "create_once": True,
        "manifest_sha256": EXPECTED_SOURCE_HASHES["M18_gate"],
        "code_sha256": _sha256_file(M26_CODE_PATH),
        "config_sha256": EXPECTED_SOURCE_HASHES["experiment_spec"],
        "budget_id": BUDGET_ID,
        "paired_benign_id": None,
        "final_evaluation_data_accessed": False,
        "physical_field_actuator": False,
        "starts_or_restarts_service": False,
        "retain_failures": True,
        "local_service_identity": LLM_SERVICE_IDENTITY,
    }
    issues = validate_preliminary_action_request(request)
    if issues:
        raise ModelClientError(f"M26 action request rejected: {issues}")
    return request


def _load_action_requests(paths: Sequence[Path]) -> list[dict[str, Any]]:
    if len(paths) != 2:
        raise ModelClientError("M26 requires exactly two action requests")
    requests = [_strict_json_file(path, "M26 action request") for path in paths]
    requests.sort(key=lambda item: int(item.get("seed", -1)))
    expected = [build_action_request(seed) for seed in DEVELOPMENT_SEEDS]
    if requests != expected:
        raise ModelClientError("M26 action request bytes drift")
    return requests


def build_contract(action_request_paths: Sequence[Path]) -> dict[str, Any]:
    """Build the exact M26 registration before any network or adapter call."""

    sources = _source_bindings()
    action_requests = _load_action_requests(action_request_paths)
    payload, expected_candidate = _load_m25_payload()
    protocol = build_m7_protocol(build_m7_adapter())
    if (
        protocol.protocol_id != EXPECTED_M7_PROTOCOL_ID
        or protocol.adapter.search_surface.search_surface_id
        != EXPECTED_M7_SEARCH_SURFACE_ID
    ):
        raise ModelClientError("M26 M7 identity drift")
    values = payload.get("values", {})
    expected_target = max(M7_TARGETS, key=lambda target: float(values[target]))
    if expected_target != "DER_B":
        raise ModelClientError("M26 preregistered empirical winner drift")
    content = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M26",
        "classification": CLASSIFICATION,
        "status": "REGISTERED_NO_NETWORK_OR_ADAPTER_CALL",
        "development_only": True,
        "campaign_authorized": False,
        "evaluation_opened": False,
        "source_admitted": False,
        "model_service": {
            "identity": LLM_SERVICE_IDENTITY,
            "model_id": MODEL_ID,
            "base_url": BASE_URL,
            "must_already_be_running": True,
            "start_or_restart_allowed": False,
        },
        "source_bindings": sources,
        "action_requests": action_requests,
        "exact_interface": {
            "protocol_id": protocol.protocol_id,
            "search_surface_id": (
                protocol.adapter.search_surface.search_surface_id
            ),
            "tool_name": M7_TOOL_NAME,
            "tool_arguments": {
                "metric": M7_METRIC,
                "target_ids": list(M7_TARGETS),
            },
            "call_id": CALL_ID,
            "candidate_ids": list(protocol.adapter.candidate_library.ids()),
        },
        "matched_IA3_control": {
            "source": "exact_M25_IA3_transaction",
            "consumer_payload": payload,
            "consumer_payload_sha256": _sha256_value(payload),
            "decision_rule": (
                "maximize_abs_p_kw_times_voltage_stress_gain_pu_per_kw"
            ),
            "expected_target": expected_target,
            "expected_candidate_id": expected_candidate,
        },
        "model_overlay": {
            "development_seeds": list(DEVELOPMENT_SEEDS),
            "temperature": 0.0,
            "max_tokens_per_turn": MAX_TOKENS_PER_TURN,
            "timeout_s": TIMEOUT_S,
            "turns": 2,
        },
        "hard_caps": {
            "model_discovery_requests": 1,
            "completion_requests": 2,
            "real_local_adapter_invocations": 1,
            "tool_calls": 1,
            "outer_rollouts": 0,
            "simulation_time_advance_s": 0.0,
            "retry_within_attempt": 0,
        },
        "access_boundary": {
            "model_transport_authorized": True,
            "network_access_authorized_for_registered_model_only": True,
            "real_local_read_only_adapter_authorized": True,
            "synthetic_fixture_injection_authorized": False,
            "external_tool_execution_authorized": False,
            "docker_access_authorized": False,
            "simulator_access_authorized": False,
            "embedding_access_authorized": False,
            "detector_access_authorized": False,
            "defense_access_authorized": False,
            "physical_actuator_authorized": False,
            "evaluation_access_authorized": False,
        },
        "primary_endpoint": {
            "name": "live_IA4_matches_preregistered_IA3_on_real_payload",
            "pass_rule": (
                "two_turn_protocol_terminal_plan_valid_and_candidate_equals_"
                "preregistered_IA3_candidate"
            ),
        },
        "failure_policy": "create_once_retain_and_stop_without_retry",
        "scientific_boundary": {
            "establishes_on_pass": [
                "current_service_structured_two_turn_transport",
                "current_service_consumes_real_M24_result_through_M5",
                "single_payload_live_IA4_and_deterministic_IA3_agreement",
            ],
            "does_not_establish": [
                "M23_source_admission_or_stability",
                "LLM_advantage_or_strategy_learning",
                "candidate_switching_under_empirical_counterfactuals",
                "attacker_effectiveness_or_grid_impact",
                "detector_or_defense_effectiveness",
                "runtime_safety_or_confirmatory_evidence",
            ],
        },
    }
    contract = _canonical_copy(content)
    contract["contract_id"] = "m26contract_" + _sha256_value(content)
    return contract


def validate_contract(
    contract: Mapping[str, Any], action_request_paths: Sequence[Path],
) -> None:
    if _canonical_copy(contract) != build_contract(action_request_paths):
        raise ModelClientError("stored M26 contract drifts from executable bytes")


def _parse_bare_object(content: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ModelClientError(
                    f"M26 completion contains duplicate field: {key}"
                )
            result[key] = item
        return result

    def reject_constant(item: str) -> None:
        raise ModelClientError(
            f"M26 completion contains non-finite constant: {item}"
        )

    try:
        payload = json.loads(
            content,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ModelClientError("M26 completion is not one exact JSON value") from exc
    if not isinstance(payload, dict):
        raise ModelClientError("M26 completion must be a JSON object")
    return payload


def _provider_stage_schema(
    session: IAInteractiveSession, *, require_tool: bool,
) -> dict[str, Any]:
    variants = [
        item
        for item in session.response_schema()["oneOf"]
        if (
            (item["properties"]["decision"]["const"] == "tool_request")
            is require_tool
        )
    ]
    if not variants:
        raise ModelClientError("M26 stage response schema has no variants")
    guided = variants[0] if len(variants) == 1 else {"oneOf": variants}
    if require_tool:
        guided = _canonical_copy(guided)
        guided["properties"]["call_id"] = {"const": CALL_ID}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "g7_m26_tool_request" if require_tool else "g7_m26_terminal",
            "strict": True,
            "schema": _canonical_copy(guided),
        },
    }


@dataclass(frozen=True)
class M26ModelRequest:
    turn_index: int
    session_request: Mapping[str, Any]
    chat_payload: Mapping[str, Any]
    session_request_sha256: str
    chat_request_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "turn_index": self.turn_index,
            "session_request": _canonical_copy(self.session_request),
            "chat_payload": _canonical_copy(self.chat_payload),
            "session_request_sha256": self.session_request_sha256,
            "chat_request_sha256": self.chat_request_sha256,
        }


def _new_session() -> IAInteractiveSession:
    protocol = build_m7_protocol(build_m7_adapter())
    return IAInteractiveSession(
        protocol=protocol,
        profile=build_m7_capability_profile(OrchestrationRung.IA4),
        observation=TypedObservation(
            window=0,
            time_s=0,
            values={
                "context": "m26_live_empirical_adapter_decision",
                "candidate_difference": "target_only",
            },
        ),
        history=(),
        decision_core_id=MODEL_ID,
    )


def build_model_request(
    *, session: IAInteractiveSession, require_tool: bool,
) -> M26ModelRequest:
    """Build one stage-locked request without contacting the model."""

    turn = session.turn_index
    if turn not in (0, 1) or require_tool is not (turn == 0):
        raise ModelClientError("M26 request stage does not match the session turn")
    request = session.next_request()
    system = (
        "You are the IA4 decision core in a development-only empirical tool-use "
        "qualification. The two candidates have identical strategy, magnitude, "
        "budget, and authority; only their target differs. On turn 0, request "
        f"the declared read-only {M7_TOOL_NAME} tool exactly once with metric "
        f"{M7_METRIC}, target_ids [DER_A, DER_B], and call_id {CALL_ID}. The "
        "harness will invoke one registered local read-only empirical adapter; "
        "it will not run a simulator or execute a plan. On turn 1, compute each "
        "candidate's predicted absolute voltage stress as abs(p_kw) multiplied "
        "by the returned target gain, then select the single unchanged candidate "
        "with the larger value. Use only the supplied result; do not infer source "
        "provenance, detector data, uncertainty, or runtime evidence. A plan is "
        "non-actuating and remains externally validated. Return exactly one JSON "
        "object matching the stage schema, with no markdown or extra text."
    )
    chat_payload = {
        "model": MODEL_ID,
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS_PER_TURN,
        "seed": DEVELOPMENT_SEEDS[turn],
        "stream": False,
        "n": 1,
        "response_format": _provider_stage_schema(
            session, require_tool=require_tool
        ),
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _canonical_json(request)},
        ],
    }
    return M26ModelRequest(
        turn_index=turn,
        session_request=request,
        chat_payload=chat_payload,
        session_request_sha256=request["request_sha256"],
        chat_request_sha256=_sha256_value(chat_payload),
    )


def _usage(record: OpenAICompletionRecord) -> dict[str, int]:
    result: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = record.usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ModelClientError(f"M26 completion usage is missing {key}")
        result[key] = value
    return result


def _candidate_for_target(session: IAInteractiveSession, target: str) -> str:
    matches = [
        candidate.candidate_id
        for candidate in session.protocol.adapter.candidate_library.candidates
        if candidate.steps[0].actions[0].device_id == target
    ]
    if len(matches) != 1:
        raise ContractViolation("M26 target does not map to one candidate")
    return matches[0]


def perform_live_attempt(
    *, base_url: str, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Use one discovery, two completions, and one real local adapter at most."""

    if base_url.rstrip("/") != BASE_URL:
        raise ModelClientError("M26 endpoint differs from the registered service")
    session = _new_session()
    network_requests = 0
    completion_requests = 0
    adapter_invocations = 0
    request_records: list[dict[str, Any]] = []
    completion_records: list[dict[str, Any]] = []
    model_record: dict[str, Any] | None = None
    actual_files_read: list[str] = []
    error: str | None = None

    try:
        network_requests += 1
        discovered = discover_model(base_url, MODEL_ID, TIMEOUT_S)
        model_record = {
            key: discovered.get(key)
            for key in ("id", "owned_by", "root", "max_model_len")
            if key in discovered
        }
        for stage in range(2):
            require_tool = stage == 0
            request = build_model_request(
                session=session, require_tool=require_tool
            )
            request_records.append(request.to_dict())
            network_requests += 1
            completion_requests += 1
            body = request_json(
                base_url.rstrip("/") + "/chat/completions",
                timeout_s=TIMEOUT_S,
                payload=dict(request.chat_payload),
            )
            completion = extract_openai_completion(
                body, expected_model_id=MODEL_ID
            )
            completion_records.append(completion.to_dict())
            payload = _parse_bare_object(completion.content)
            if require_tool and payload.get("decision") != "tool_request":
                raise ContractViolation(
                    "M26 turn 0 did not request observe_sensitivity"
                )
            if not require_tool and payload.get("decision") == "tool_request":
                raise ContractViolation("M26 turn 1 did not terminate")
            session.accept_model_turn(
                request_sha256=request.session_request_sha256,
                payload=payload,
                model_id=MODEL_ID,
                usage=_usage(completion),
            )
            if not require_tool:
                if session.state is not InteractiveState.TERMINAL:
                    raise ContractViolation("M26 terminal response did not terminate")
                continue

            outstanding = session.outstanding_request
            if (
                session.state is not InteractiveState.AWAITING_TOOL_RESULT
                or outstanding is None
            ):
                raise ContractViolation("M26 did not enter tool-result state")
            if (
                outstanding.tool_name != M7_TOOL_NAME
                or outstanding.call_id != CALL_ID
            ):
                raise ContractViolation("M26 tool request identity drift")
            if adapter_invocations >= 1:
                raise ContractViolation("M26 adapter invocation cap exceeded")

            def tracked_read(path: Path) -> bytes:
                actual_files_read.append(_relative(path))
                return path.read_bytes()

            adapter = EmpiricalSensitivityAdapter(
                contract=build_m24_contract(),
                read_bytes=tracked_read,
            )
            invocation = adapter.invoke(
                arguments=outstanding.arguments,
                caller_rung=OrchestrationRung.IA4.value,
            )
            adapter_invocations += 1
            expected_payload = contract["matched_IA3_control"]["consumer_payload"]
            if _canonical_copy(invocation.payload) != expected_payload:
                raise ContractViolation("M26 real payload differs from preregistration")
            result = RealAdapterToolResult.build(
                protocol=session.protocol,
                request=outstanding,
                output=invocation.payload,
                adapter_invocation_receipt=invocation.receipt,
                caller_rung=OrchestrationRung.IA4,
                wall_clock_ms=0.0,
            )
            session.submit_tool_result(result)

        execution_status = "completed"
    except (ModelClientError, ContractViolation, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
        if session.state in {
            InteractiveState.AWAITING_MODEL,
            InteractiveState.AWAITING_TOOL_RESULT,
        }:
            session.fail_closed(error)
        execution_status = "failed_closed"

    if network_requests > 3 or completion_requests > 2 or adapter_invocations > 1:
        raise ModelClientError("M26 hard request or adapter cap exceeded")
    receipt = session.receipt(model_transport_used=network_requests > 0)
    consumer_events = [
        item for item in receipt["transcript"] if item.get("event") == "tool_result"
    ]
    consumer_event = consumer_events[0] if len(consumer_events) == 1 else None
    terminal = receipt.get("terminal_decision") or {}
    selected_candidate = terminal.get("candidate_id")
    selected_target = None
    validation = None
    if execution_status == "completed" and isinstance(selected_candidate, str):
        candidate = session.protocol.adapter.candidate_library.get(selected_candidate)
        selected_target = candidate.steps[0].actions[0].device_id
        validation = validate_m7_terminal_receipt(
            protocol=session.protocol,
            receipt=receipt,
            rung=OrchestrationRung.IA4,
        )
    expected_candidate = contract["matched_IA3_control"]["expected_candidate_id"]
    ia3_agreement = selected_candidate == expected_candidate
    qualified = (
        execution_status == "completed"
        and terminal.get("kind") == "plan"
        and validation is not None
        and validation.get("accepted") is True
        and ia3_agreement
        and adapter_invocations == 1
        and consumer_event is not None
    )
    status = (
        "passed"
        if qualified
        else "failed_qualification"
        if execution_status == "completed"
        else "failed_closed"
    )
    if execution_status == "completed" and not qualified and error is None:
        error = "terminal decision did not satisfy the M26 primary endpoint"
    return {
        "status": status,
        "execution_status": execution_status,
        "error": error,
        "network_requests": network_requests,
        "model_discovery_requests": 1 if model_record is not None else 1,
        "completion_requests": completion_requests,
        "adapter_invocations": adapter_invocations,
        "model_record": model_record,
        "requests": request_records,
        "completions": completion_records,
        "actual_files_read": actual_files_read,
        "consumer_tool_result_event": consumer_event,
        "consumer_payload_sha256": (
            None
            if consumer_event is None
            else _sha256_value(consumer_event.get("output"))
        ),
        "expected_target": contract["matched_IA3_control"]["expected_target"],
        "expected_candidate_id": expected_candidate,
        "selected_target": selected_target,
        "selected_candidate_id": selected_candidate,
        "matched_IA3_candidate_agreement": ia3_agreement,
        "validation": validation,
        "session_receipt": receipt,
        "model_transport_used": network_requests > 0,
        "real_local_read_only_adapter_executed": adapter_invocations == 1,
        "synthetic_fixture_injected": False,
        "external_tool_execution_used": False,
        "docker_accessed": False,
        "simulator_accessed": False,
        "embedding_accessed": False,
        "detector_accessed": False,
        "defense_accessed": False,
        "physical_actuator_accessed": False,
        "evaluation_accessed": False,
        "final_evaluation_seeds_accessed": [],
    }


def build_receipt(
    *, contract: Mapping[str, Any], result: Mapping[str, Any],
) -> dict[str, Any]:
    content = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M26",
        "classification": CLASSIFICATION,
        "contract_id": contract["contract_id"],
        "result": _canonical_copy(result),
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "source_admitted": False,
        "model_service_started_or_restarted": False,
        "docker_accessed": False,
        "simulator_accessed": False,
        "embedding_accessed": False,
        "detector_accessed": False,
        "defense_accessed": False,
        "physical_actuator_accessed": False,
        "evaluation_accessed": False,
        "final_evaluation_seeds_accessed": [],
    }
    receipt = _canonical_copy(content)
    receipt["receipt_id"] = "m26receipt_" + _sha256_value(content)
    return receipt


def verify_receipt(
    receipt: Mapping[str, Any], contract: Mapping[str, Any],
) -> list[str]:
    """Verify a passing M26 receipt and every registered access seal."""

    issues: list[str] = []
    content = _canonical_copy(receipt)
    receipt_id = content.pop("receipt_id", None)
    if receipt_id != "m26receipt_" + _sha256_value(content):
        issues.append("receipt_content_address_drift")
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        issues.append("schema_version_drift")
    if receipt.get("contract_id") != contract.get("contract_id"):
        issues.append("contract_id_drift")
    if receipt.get("classification") != CLASSIFICATION:
        issues.append("classification_drift")
    for field in (
        "campaign_authorized",
        "confirmatory_claim_authorized",
        "evaluation_opened",
        "source_admitted",
        "model_service_started_or_restarted",
        "docker_accessed",
        "simulator_accessed",
        "embedding_accessed",
        "detector_accessed",
        "defense_accessed",
        "physical_actuator_accessed",
        "evaluation_accessed",
    ):
        if receipt.get(field) is not False:
            issues.append(f"access_boundary_drift:{field}")
    if receipt.get("final_evaluation_seeds_accessed") != []:
        issues.append("final_evaluation_accessed")

    result = receipt.get("result", {})
    if not isinstance(result, Mapping):
        return sorted(set([*issues, "result_missing"]))
    if result.get("status") != "passed":
        issues.append("live_empirical_regression_not_passed")
    expected_counts = {
        "network_requests": 3,
        "model_discovery_requests": 1,
        "completion_requests": 2,
        "adapter_invocations": 1,
    }
    for field, expected in expected_counts.items():
        if result.get(field) != expected:
            issues.append(f"request_count_drift:{field}")
    if (result.get("model_record") or {}).get("id") != MODEL_ID:
        issues.append("model_identity_drift")
    if len(result.get("requests", [])) != 2:
        issues.append("model_request_record_count_drift")
    if len(result.get("completions", [])) != 2:
        issues.append("completion_record_count_drift")
    if result.get("consumer_payload_sha256") != EXPECTED_M24_PAYLOAD_SHA256:
        issues.append("consumer_payload_drift")
    if result.get("expected_candidate_id") != (
        contract.get("matched_IA3_control", {}).get("expected_candidate_id")
    ):
        issues.append("expected_candidate_drift")
    if result.get("selected_candidate_id") != result.get("expected_candidate_id"):
        issues.append("candidate_agreement_failed")
    if result.get("matched_IA3_candidate_agreement") is not True:
        issues.append("matched_IA3_agreement_failed")
    if (result.get("validation") or {}).get("accepted") is not True:
        issues.append("common_terminal_validation_failed")
    consumer_event = result.get("consumer_tool_result_event")
    if not isinstance(consumer_event, Mapping):
        issues.append("consumer_tool_result_missing")
    else:
        consumer_json = _canonical_json(consumer_event)
        for key in FORBIDDEN_CONSUMER_KEYS:
            if key in consumer_json:
                issues.append(f"consumer_provenance_leak:{key}")
        if consumer_event.get("output") != (
            contract.get("matched_IA3_control", {}).get("consumer_payload")
        ):
            issues.append("consumer_payload_not_byte_equal_to_IA3")
    true_fields = (
        "model_transport_used",
        "real_local_read_only_adapter_executed",
    )
    false_fields = (
        "synthetic_fixture_injected",
        "external_tool_execution_used",
        "docker_accessed",
        "simulator_accessed",
        "embedding_accessed",
        "detector_accessed",
        "defense_accessed",
        "physical_actuator_accessed",
        "evaluation_accessed",
    )
    for field in true_fields:
        if result.get(field) is not True:
            issues.append(f"nested_access_boundary_drift:{field}")
    for field in false_fields:
        if result.get(field) is not False:
            issues.append(f"nested_access_boundary_drift:{field}")
    if result.get("final_evaluation_seeds_accessed") != []:
        issues.append("nested_final_evaluation_accessed")
    session = result.get("session_receipt", {})
    if session.get("state") != "terminal":
        issues.append("session_not_terminal")
    if session.get("model_transport_used") is not True:
        issues.append("session_model_transport_drift")
    if session.get("real_local_read_only_adapter_executed") is not True:
        issues.append("session_real_adapter_drift")
    if session.get("synthetic_fixture_injected") is not False:
        issues.append("session_fixture_state_drift")
    if session.get("external_tool_execution_used") is not False:
        issues.append("session_external_tool_state_drift")
    accounting = session.get("accounting", {})
    if accounting.get("model_turns") != 2 or accounting.get("tool_calls") != 1:
        issues.append("session_accounting_drift")
    if accounting.get("outer_rollouts") != 0:
        issues.append("outer_rollout_used")
    return sorted(set(issues))


def register_artifacts(root: Path) -> dict[str, Any]:
    """Create the two action requests and contract without online access."""

    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for seed in DEVELOPMENT_SEEDS:
        path = root / f"action_request_seed{seed}.json"
        create_once_json(path, build_action_request(seed))
        paths.append(path)
    contract = build_contract(paths)
    create_once_json(root / "contract.json", contract)
    return contract


def action_request_paths(root: Path) -> tuple[Path, Path]:
    return tuple(
        root / f"action_request_seed{seed}.json" for seed in DEVELOPMENT_SEEDS
    )  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["register", "run", "verify"], required=True
    )
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args(argv)
    root = args.artifact_root
    paths = action_request_paths(root)

    if args.mode == "register":
        contract = register_artifacts(root)
        print(
            json.dumps(
                {"status": "registered", "contract_id": contract["contract_id"]},
                indent=2,
            )
        )
        return 0

    contract = _strict_json_file(root / "contract.json", "M26 contract")
    validate_contract(contract, paths)
    if args.mode == "run":
        result = perform_live_attempt(base_url=args.base_url, contract=contract)
        receipt = build_receipt(contract=contract, result=result)
        create_once_json(root / "receipt.json", receipt)
        issues = verify_receipt(receipt, contract)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "receipt_id": receipt["receipt_id"],
                    "issues": issues,
                    "selected_candidate_id": result["selected_candidate_id"],
                    "total_model_tokens": result["session_receipt"]["accounting"][
                        "total_model_tokens"
                    ],
                },
                indent=2,
            )
        )
        return int(bool(issues))

    receipt = _strict_json_file(root / "receipt.json", "M26 receipt")
    issues = verify_receipt(receipt, contract)
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
