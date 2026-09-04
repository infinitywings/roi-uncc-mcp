"""Qualify the M24 adapter through the common offline M5 transaction path.

This module performs local, deterministic IA3/IA4 replay only. It invokes the
real read-only M24 adapter but never contacts a model, network, container,
simulator, detector, defense, embedding service, or physical actuator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

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
from .ia4_smoke_fixture import (
    build_m4_smoke_adapter,
    build_smoke_capability_profile,
)
from .ia4_tool_loop import (
    FixtureToolResult,
    IAInteractiveSession,
    M5_TOOL_REQUEST_SCHEMA_VERSION,
    MatchedIA3ObserveThenSelect,
    RealAdapterToolResult,
    build_m5_protocol,
)
from .m24_independent_audit import verify_audit_receipt as verify_m24_audit
from .m24_read_only_adapter import (
    EmpiricalSensitivityAdapter,
    build_contract as build_m24_contract,
    verify_qualification as verify_m24_qualification,
)
from .manifest import create_once_json
from .orchestration_contract import (
    ContractViolation,
    OrchestrationRung,
    TypedObservation,
)


CONTRACT_SCHEMA_VERSION = "grideval-g7-m25-adapter-transaction-contract/v1"
QUALIFICATION_SCHEMA_VERSION = (
    "grideval-g7-m25-adapter-transaction-qualification/v1"
)
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01M1MVY5SHFG6Z1JJBWRPE66DM"
DECISION_ID = "dec_01M1MVXEYYVZ9CVQ19XFH7S92P"
CLASSIFICATION = "PRELIMINARY_ONLY"

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
M25_CODE_PATH = Path(__file__).resolve()
M5_CORE_PATH = Path(__file__).with_name("ia4_tool_loop.py")
SCHEMA_PATH = PACKAGE_ROOT / "m25_adapter_transaction.schema.json"
M5_CONTRACT_PATH = PACKAGE_ROOT / "artifacts" / "ia4_interactive_contract_m5.json"
M7_CONTRACT_PATH = PACKAGE_ROOT / "artifacts" / "ia4_counterfactual_contract_m7.json"
M24_ROOT = PACKAGE_ROOT / "artifacts" / "m24_read_only_adapter_attempt1"
M24_CONTRACT_PATH = M24_ROOT / "contract.json"
M24_QUALIFICATION_PATH = M24_ROOT / "qualification_receipt.json"
M24_AUDIT_PATH = M24_ROOT / "independent_audit_receipt.json"

EXPECTED_M5_CONTRACT_SHA256 = (
    "0092296aac177db2aa932cb48f0d8c256d45a769af471e14a3524fceecc8090a"
)
EXPECTED_M5_PROTOCOL_ID = (
    "m5proto_d3de5a4295d510abbe1b4b20dd52dc2fd23de72f67a0da8e9d6b118085a39d49"
)
EXPECTED_M7_CONTRACT_SHA256 = (
    "4cef8444c56c40ff493ed3add9847d43d9d12c72f9f1714597e7566109d26de2"
)
EXPECTED_M7_CONTRACT_ID = (
    "m7contract_fc1b2a552f322effb0ff27a451154699528c7f26da875e204178820d19fc45b3"
)
EXPECTED_M7_PROTOCOL_ID = (
    "m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff"
)
EXPECTED_M7_SEARCH_SURFACE_ID = (
    "surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78"
)
EXPECTED_M24_CONTRACT_SHA256 = (
    "95965833d0d49cb021fe4af89e2cd830d4cd904a2de6f7d12aad2ecd33721ee3"
)
EXPECTED_M24_CONTRACT_ID = (
    "m24contract_c92535c44ed39b2d8f42555fee19977aebcc764fd17841c7e8a0736d7b560575"
)
EXPECTED_M24_QUALIFICATION_SHA256 = (
    "6201770ced6029cf1c54a1d61b9d7a73d3c05c19d8edb83e9339df4d62fa65b8"
)
EXPECTED_M24_QUALIFICATION_ID = (
    "m24qual_e2dada84a81f064527590dcef69ac29bed40767a32f8a295048251257879de41"
)
EXPECTED_M24_AUDIT_SHA256 = (
    "7149de87a983e96850676b335e89a58e3c9e1f0b0b804b07b8d74cf9df49a787"
)
EXPECTED_M24_AUDIT_ID = (
    "m24audit_f4869f93d8bc5f8d9dcac137a4ea9893fef30722445905ce9e10233b59526e7a"
)
EXPECTED_LEGACY_FIXTURE_RESULT_SHA256 = (
    "0a0d364173120eb25f3b7892a989e76ba897270a728e68e72ceacca0ca6629e2"
)
EXPECTED_LEGACY_FIXTURE_RECEIPT_SHA256 = (
    "5a7af50c3b56e45238b8f96f93cbefd72813a8dc9b81faa7e1a28465ae314ff9"
)
CALL_ID = "call_m25_real_adapter_0001"
DECISION_CORE_ID = "m25_offline_argmax_replay"
FORBIDDEN_CONSUMER_KEYS = {
    "adapter_invocation_receipt",
    "access_boundary",
    "audit_binding",
    "contract_id",
    "files_read",
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
        raise ContractViolation("M25 value is not canonical JSON") from exc


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_sha256(value: Any) -> str:
    encoded = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strict_json_file(path: Path, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ContractViolation(f"{label} contains duplicate field: {key}")
            result[key] = item
        return result

    def reject_constant(item: str) -> None:
        raise ContractViolation(f"{label} contains non-finite constant: {item}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation(f"{label} is not one UTF-8 JSON value") from exc


def _self_addressed(value: Mapping[str, Any], *, field: str, prefix: str) -> bool:
    content = _canonical_copy(value)
    actual = content.pop(field, None)
    return actual == prefix + _sha256_value(content)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _load_exact_upstream() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    expected_hashes = {
        M5_CONTRACT_PATH: EXPECTED_M5_CONTRACT_SHA256,
        M7_CONTRACT_PATH: EXPECTED_M7_CONTRACT_SHA256,
        M24_CONTRACT_PATH: EXPECTED_M24_CONTRACT_SHA256,
        M24_QUALIFICATION_PATH: EXPECTED_M24_QUALIFICATION_SHA256,
        M24_AUDIT_PATH: EXPECTED_M24_AUDIT_SHA256,
    }
    for path, expected in expected_hashes.items():
        if _sha256_file(path) != expected:
            raise ContractViolation(f"M25 upstream file hash drift: {_relative(path)}")

    m5 = _strict_json_file(M5_CONTRACT_PATH, "M5 contract")
    m7 = _strict_json_file(M7_CONTRACT_PATH, "M7 contract")
    m24 = _strict_json_file(M24_CONTRACT_PATH, "M24 contract")
    qualification = _strict_json_file(
        M24_QUALIFICATION_PATH, "M24 qualification"
    )
    audit = _strict_json_file(M24_AUDIT_PATH, "M24 independent audit")
    if m5.get("protocol", {}).get("protocol_id") != EXPECTED_M5_PROTOCOL_ID:
        raise ContractViolation("M5 protocol identity drift")
    if (m7.get("contract_id") != EXPECTED_M7_CONTRACT_ID or
            m7.get("protocol", {}).get("protocol_id") != EXPECTED_M7_PROTOCOL_ID or
            m7.get("protocol", {}).get("base_search_surface_id") !=
            EXPECTED_M7_SEARCH_SURFACE_ID):
        raise ContractViolation("M7 identity drift")
    if m24 != build_m24_contract():
        raise ContractViolation("M24 contract drifts from current adapter bytes")
    if (m24.get("contract_id") != EXPECTED_M24_CONTRACT_ID or
            m24.get("source_admitted") is not False):
        raise ContractViolation("M24 contract identity or admission drift")
    if verify_m24_qualification(M24_ROOT):
        raise ContractViolation("M24 qualification no longer verifies")
    if (qualification.get("qualification_id") !=
            EXPECTED_M24_QUALIFICATION_ID or
            qualification.get("status") != "passed" or
            qualification.get("source_admitted") is not False):
        raise ContractViolation("M24 qualification identity or boundary drift")
    if (audit.get("audit_id") != EXPECTED_M24_AUDIT_ID or
            audit.get("status") != "passed" or audit.get("issues") != [] or
            verify_m24_audit(M24_ROOT, audit)):
        raise ContractViolation("M24 independent audit no longer passes")
    return (
        _canonical_copy(m24),
        _canonical_copy(qualification),
        _canonical_copy(audit),
    )


def _legacy_fixture_hashes() -> dict[str, str]:
    protocol = build_m5_protocol(build_m4_smoke_adapter())
    session = IAInteractiveSession(
        protocol=protocol,
        profile=build_smoke_capability_profile(OrchestrationRung.IA4),
        observation=TypedObservation(
            0,
            0,
            {"context": "synthetic_interface_fixture", "voltage_pu": 1.0},
        ),
        history=(),
        decision_core_id="fixture_ia4",
    )
    request = session.next_request()
    session.accept_model_turn(
        request_sha256=request["request_sha256"],
        payload=MatchedIA3ObserveThenSelect().tool_request(session),
        model_id=session.decision_core_id,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    outstanding = session.outstanding_request
    if outstanding is None:
        raise ContractViolation("legacy fixture did not request its tool")
    result = FixtureToolResult.build(
        protocol=protocol,
        request=outstanding,
        output={
            "schema_version": "observation-result/v1",
            "window": 0,
            "time_s": 0,
            "values": {"prior_alarm": False, "voltage_pu": 0.99},
        },
    )
    result_sha = _sha256_value(result.to_dict())
    session.submit_tool_result(result)
    request = session.next_request()
    terminal = {
        "schema_version": IA4_RESPONSE_SCHEMA_VERSION,
        "search_surface_id": protocol.adapter.search_surface.search_surface_id,
        "decision": "plan",
        "candidate_id": protocol.adapter.candidate_library.ids()[0],
        "rationale": "Return a terminal fixture decision.",
        "used_tool_call_ids": [item.call_id for item in session.tool_calls],
    }
    session.accept_model_turn(
        request_sha256=request["request_sha256"],
        payload=terminal,
        model_id=session.decision_core_id,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    return {
        "fixture_result_sha256": result_sha,
        "fixture_episode_receipt_sha256": _sha256_value(session.receipt()),
    }


def _assert_legacy_anchors() -> dict[str, str]:
    anchors = _legacy_fixture_hashes()
    if anchors != {
        "fixture_result_sha256": EXPECTED_LEGACY_FIXTURE_RESULT_SHA256,
        "fixture_episode_receipt_sha256": (
            EXPECTED_LEGACY_FIXTURE_RECEIPT_SHA256
        ),
    }:
        raise ContractViolation("legacy M5 fixture bytes drift")
    protocol = build_m7_protocol(build_m7_adapter())
    if (protocol.protocol_id != EXPECTED_M7_PROTOCOL_ID or
            protocol.adapter.search_surface.search_surface_id !=
            EXPECTED_M7_SEARCH_SURFACE_ID):
        raise ContractViolation("M7 protocol or search-surface identity drift")
    return anchors


def build_contract() -> dict[str, Any]:
    """Build the deterministic M25 registration before any adapter call."""

    m24, qualification, audit = _load_exact_upstream()
    anchors = _assert_legacy_anchors()
    content = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M25",
        "classification": CLASSIFICATION,
        "status": "REGISTERED_OFFLINE_NO_M25_TRANSACTION",
        "development_only": True,
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "source_admitted": False,
        "bindings": {
            "M25_transaction_code": {
                "path": _relative(M25_CODE_PATH),
                "sha256": _sha256_file(M25_CODE_PATH),
            },
            "M5_transaction_core": {
                "path": _relative(M5_CORE_PATH),
                "sha256": _sha256_file(M5_CORE_PATH),
                "protocol_id": EXPECTED_M5_PROTOCOL_ID,
            },
            "qualification_schema": {
                "path": _relative(SCHEMA_PATH),
                "sha256": _sha256_file(SCHEMA_PATH),
            },
            "M5_contract": {
                "path": _relative(M5_CONTRACT_PATH),
                "sha256": EXPECTED_M5_CONTRACT_SHA256,
            },
            "M7_contract": {
                "path": _relative(M7_CONTRACT_PATH),
                "sha256": EXPECTED_M7_CONTRACT_SHA256,
                "contract_id": EXPECTED_M7_CONTRACT_ID,
                "protocol_id": EXPECTED_M7_PROTOCOL_ID,
                "search_surface_id": EXPECTED_M7_SEARCH_SURFACE_ID,
            },
            "M24_contract": {
                "path": _relative(M24_CONTRACT_PATH),
                "sha256": EXPECTED_M24_CONTRACT_SHA256,
                "contract_id": m24["contract_id"],
            },
            "M24_qualification": {
                "path": _relative(M24_QUALIFICATION_PATH),
                "sha256": EXPECTED_M24_QUALIFICATION_SHA256,
                "qualification_id": qualification["qualification_id"],
            },
            "M24_independent_audit": {
                "path": _relative(M24_AUDIT_PATH),
                "sha256": EXPECTED_M24_AUDIT_SHA256,
                "audit_id": audit["audit_id"],
            },
        },
        "legacy_compatibility_anchors": anchors,
        "transaction_contract": {
            "participant_rungs": ["IA3", "IA4"],
            "decision_core_mode": "offline_deterministic_argmax_replay",
            "tool_name": M7_TOOL_NAME,
            "exact_arguments": {
                "metric": M7_METRIC,
                "target_ids": list(M7_TARGETS),
            },
            "call_id": CALL_ID,
            "real_adapter_calls_per_rung": 1,
            "tool_calls_per_rung": 1,
            "model_transport_calls": 0,
            "outer_rollouts": 0,
            "simulation_time_advance_s": 0.0,
            "consumer_provenance_separation_required": True,
        },
        "access_boundary": {
            "real_local_read_only_adapter_authorized": True,
            "synthetic_fixture_injection_authorized": False,
            "external_tool_execution_authorized": False,
            "model_transport_authorized": False,
            "embedding_access_authorized": False,
            "detector_access_authorized": False,
            "defense_access_authorized": False,
            "network_access_authorized": False,
            "docker_access_authorized": False,
            "simulator_access_authorized": False,
            "physical_actuator_authorized": False,
            "evaluation_access_authorized": False,
        },
        "scientific_boundary": {
            "establishes": [
                "real_M24_adapter_result_accepted_by_common_M5_transaction",
                "legacy_fixture_byte_compatibility",
                "model_facing_provenance_separation",
                "offline_IA3_IA4_consumer_byte_parity",
                "real_fixture_external_execution_distinction",
            ],
            "does_not_establish": [
                "M23_source_admission",
                "current_LLM_behavior_or_advantage",
                "attacker_effectiveness_or_physical_harm",
                "detector_or_defense_effectiveness",
                "runtime_or_campaign_safety",
                "confirmatory_or_publication_grade_evidence",
            ],
        },
    }
    contract = _canonical_copy(content)
    contract["contract_id"] = "m25contract_" + _sha256_value(content)
    return contract


def _tool_request(session: IAInteractiveSession) -> dict[str, Any]:
    return {
        "schema_version": M5_TOOL_REQUEST_SCHEMA_VERSION,
        "protocol_id": session.protocol.protocol_id,
        "base_search_surface_id": (
            session.protocol.adapter.search_surface.search_surface_id
        ),
        "turn_index": 0,
        "decision": "tool_request",
        "call_id": CALL_ID,
        "tool_name": M7_TOOL_NAME,
        "arguments": {"metric": M7_METRIC, "target_ids": list(M7_TARGETS)},
        "rationale": "Acquire the shared empirical sensitivity payload.",
    }


def _candidate_for_target(protocol: Any, target: str) -> str:
    matches = [
        candidate.candidate_id
        for candidate in protocol.adapter.candidate_library.candidates
        if candidate.steps[0].actions[0].device_id == target
    ]
    if len(matches) != 1:
        raise ContractViolation("M25 target does not map to one M7 candidate")
    return matches[0]


def _run_transaction(*, rung: OrchestrationRung,
                     m24_contract: Mapping[str, Any]) -> dict[str, Any]:
    protocol = build_m7_protocol(build_m7_adapter())
    session = IAInteractiveSession(
        protocol=protocol,
        profile=build_m7_capability_profile(rung),
        observation=TypedObservation(
            window=0,
            time_s=0,
            values={
                "context": "m25_offline_empirical_adapter_transaction",
                "candidate_difference": "target_only",
            },
        ),
        history=(),
        decision_core_id=DECISION_CORE_ID,
    )
    first_request = session.next_request()
    tool_payload = _tool_request(session)
    session.accept_model_turn(
        request_sha256=first_request["request_sha256"],
        payload=tool_payload,
        model_id=DECISION_CORE_ID,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    outstanding = session.outstanding_request
    if outstanding is None:
        raise ContractViolation("M25 session did not create an outstanding request")

    actual_reads: list[str] = []

    def tracked_read(path: Path) -> bytes:
        actual_reads.append(_relative(path))
        return path.read_bytes()

    adapter = EmpiricalSensitivityAdapter(
        contract=m24_contract,
        read_bytes=tracked_read,
    )
    invocation = adapter.invoke(
        arguments=outstanding.arguments,
        caller_rung=rung.value,
    )
    result = RealAdapterToolResult.build(
        protocol=protocol,
        request=outstanding,
        output=invocation.payload,
        adapter_invocation_receipt=invocation.receipt,
        caller_rung=rung,
        wall_clock_ms=0.0,
    )
    session.submit_tool_result(result)

    values = invocation.payload["values"]
    selected_target = max(M7_TARGETS, key=lambda target: float(values[target]))
    selected_candidate = _candidate_for_target(protocol, selected_target)
    second_request = session.next_request()
    terminal_payload = {
        "schema_version": IA4_RESPONSE_SCHEMA_VERSION,
        "search_surface_id": protocol.adapter.search_surface.search_surface_id,
        "decision": "plan",
        "candidate_id": selected_candidate,
        "rationale": (
            "Select the registered target with the larger empirical sensitivity."
        ),
        "used_tool_call_ids": [item.call_id for item in session.tool_calls],
    }
    session.accept_model_turn(
        request_sha256=second_request["request_sha256"],
        payload=terminal_payload,
        model_id=DECISION_CORE_ID,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    receipt = session.receipt(model_transport_used=False)
    validation = validate_m7_terminal_receipt(
        protocol=protocol,
        receipt=receipt,
        rung=rung,
    )
    if validation.get("accepted") is not True:
        raise ContractViolation("M25 terminal plan failed common validation")
    if actual_reads != invocation.receipt["files_read"]:
        raise ContractViolation("M25 actual read log differs from M24 provenance")
    tool_events = [
        item for item in receipt["transcript"]
        if item.get("event") == "tool_result"
    ]
    if len(tool_events) != 1:
        raise ContractViolation("M25 transcript lacks one consumer tool result")
    return {
        "rung": rung.value,
        "decision_core_id": DECISION_CORE_ID,
        "tool_request": tool_payload,
        "tool_request_sha256": _sha256_value(tool_payload),
        "consumer_tool_result_event": tool_events[0],
        "consumer_tool_result_event_sha256": _sha256_value(tool_events[0]),
        "adapter_invocation_receipt_sha256": _sha256_value(invocation.receipt),
        "actual_files_read": actual_reads,
        "selected_target": selected_target,
        "selected_candidate_id": selected_candidate,
        "validation": validation,
        "session_receipt": receipt,
    }


def build_qualification_receipt(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Run one real local adapter transaction for each matched rung."""

    expected_contract = build_contract()
    if _canonical_copy(contract) != expected_contract:
        raise ContractViolation("stored M25 contract drifts from current bytes")
    m24_contract, _, _ = _load_exact_upstream()
    transactions = {
        rung.value: _run_transaction(rung=rung, m24_contract=m24_contract)
        for rung in (OrchestrationRung.IA3, OrchestrationRung.IA4)
    }
    ia3 = transactions["IA3"]
    ia4 = transactions["IA4"]
    ia3_tool = ia3["session_receipt"]["tool_results"][0]
    ia4_tool = ia4["session_receipt"]["tool_results"][0]
    ia3_invocation = ia3_tool["adapter_invocation_receipt"]
    ia4_invocation = ia4_tool["adapter_invocation_receipt"]
    parity = {
        "same_tool_request_bytes": ia3["tool_request"] == ia4["tool_request"],
        "same_tool_request_sha256": (
            ia3["tool_request_sha256"] == ia4["tool_request_sha256"]
        ),
        "same_adapter_request_canonical_bytes": (
            ia3_invocation["request_canonical_json"] ==
            ia4_invocation["request_canonical_json"]
        ),
        "same_adapter_payload_canonical_bytes": (
            ia3_invocation["payload_canonical_json"] ==
            ia4_invocation["payload_canonical_json"]
        ),
        "same_adapter_payload_sha256": (
            ia3_invocation["payload_sha256"] == ia4_invocation["payload_sha256"]
        ),
        "same_consumer_tool_result_event_bytes": (
            ia3["consumer_tool_result_event"] ==
            ia4["consumer_tool_result_event"]
        ),
        "same_exact_file_reads": (
            ia3["actual_files_read"] == ia4["actual_files_read"]
        ),
        "same_selected_target_and_candidate": (
            ia3["selected_target"] == ia4["selected_target"] and
            ia3["selected_candidate_id"] == ia4["selected_candidate_id"]
        ),
        "same_zero_cost_accounting": (
            ia3["session_receipt"]["accounting"] ==
            ia4["session_receipt"]["accounting"] == {
                "model_turns": 2,
                "tool_calls": 1,
                "outer_rollouts": 0,
                "total_model_tokens": 0,
            }
        ),
    }
    if not all(parity.values()):
        raise ContractViolation("M25 IA3/IA4 transaction parity failed")

    consumer_json = _canonical_json(ia3["consumer_tool_result_event"])
    separation = {
        "consumer_event_has_no_provenance_keys": all(
            key not in consumer_json for key in FORBIDDEN_CONSUMER_KEYS
        ),
        "consumer_output_is_exact_M24_payload": (
            ia3["consumer_tool_result_event"]["output"] ==
            json.loads(ia3_invocation["payload_canonical_json"])
        ),
        "episode_receipt_retains_adapter_provenance": (
            "adapter_invocation_receipt" in ia3_tool and
            "adapter_invocation_receipt" in ia4_tool
        ),
        "real_fixture_external_states_are_distinct": all(
            item["session_receipt"]["tool_execution_used"] is True and
            item["session_receipt"][
                "real_local_read_only_adapter_executed"
            ] is True and
            item["session_receipt"]["synthetic_fixture_injected"] is False and
            item["session_receipt"]["external_tool_execution_used"] is False
            for item in transactions.values()
        ),
    }
    if not all(separation.values()):
        raise ContractViolation("M25 provenance separation failed")

    content = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "mission_id": MISSION_ID,
        "decision_id": DECISION_ID,
        "milestone": "M25",
        "classification": CLASSIFICATION,
        "status": "passed",
        "development_only": True,
        "campaign_authorized": False,
        "confirmatory_claim_authorized": False,
        "evaluation_opened": False,
        "source_admitted": False,
        "contract_id": expected_contract["contract_id"],
        "contract_sha256": _artifact_sha256(expected_contract),
        "transactions": transactions,
        "parity": parity,
        "provenance_separation": separation,
        "access_seals": {
            "real_local_read_only_adapter_executed": True,
            "synthetic_fixture_injected": False,
            "external_tool_execution_used": False,
            "model_transport_used": False,
            "embedding_accessed": False,
            "detector_accessed": False,
            "defense_accessed": False,
            "network_accessed": False,
            "docker_accessed": False,
            "simulator_accessed": False,
            "physical_actuator_accessed": False,
            "evaluation_accessed": False,
            "simulation_time_advance_s": 0.0,
            "outer_rollout_cost": 0,
        },
        "limitations": [
            "The M23 source remains PRELIMINARY_ONLY and unadmitted.",
            "The IA4 actor is an offline deterministic replay, not a live LLM.",
            "No attacker impact, detector, defense, or runtime claim is supported.",
            "Final evaluation seeds and confirmatory execution remain sealed.",
        ],
    }
    receipt = _canonical_copy(content)
    receipt["qualification_id"] = "m25qual_" + _sha256_value(content)
    return receipt


def verify_qualification(root: Path) -> list[str]:
    """Verify checked-in M25 artifacts against current exact code and evidence."""

    try:
        contract = _strict_json_file(root / "contract.json", "M25 contract")
        receipt = _strict_json_file(
            root / "qualification_receipt.json", "M25 qualification receipt"
        )
        expected_contract = build_contract()
        expected_receipt = build_qualification_receipt(expected_contract)
    except (ContractViolation, OSError, TypeError, ValueError) as exc:
        return [f"M25_qualification_unreadable_or_invalid:{exc}"]
    issues: list[str] = []
    if contract != expected_contract:
        issues.append("M25_contract_content_drift")
    if receipt != expected_receipt:
        issues.append("M25_receipt_content_drift")
    if not _self_addressed(
            receipt, field="qualification_id", prefix="m25qual_"):
        issues.append("M25_receipt_self_address_drift")
    if receipt.get("status") != "passed":
        issues.append("M25_status_not_passed")
    if receipt.get("source_admitted") is not False:
        issues.append("M25_source_admission_boundary_opened")
    seals = receipt.get("access_seals", {})
    if (seals.get("evaluation_accessed") is not False or
            seals.get("model_transport_used") is not False or
            seals.get("simulator_accessed") is not False):
        issues.append("M25_offline_boundary_opened")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["build-contract", "run", "verify"], required=True
    )
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.mode == "build-contract":
        root.mkdir(parents=True, exist_ok=False)
        contract = build_contract()
        create_once_json(root / "contract.json", contract)
        print(json.dumps({
            "status": contract["status"],
            "contract_id": contract["contract_id"],
        }, indent=2))
        return 0
    if args.mode == "run":
        contract = _strict_json_file(root / "contract.json", "M25 contract")
        receipt = build_qualification_receipt(contract)
        create_once_json(root / "qualification_receipt.json", receipt)
        print(json.dumps({
            "status": receipt["status"],
            "qualification_id": receipt["qualification_id"],
            "payload_sha256": receipt["transactions"]["IA3"][
                "session_receipt"
            ]["tool_results"][0]["adapter_invocation_receipt"][
                "payload_sha256"
            ],
        }, indent=2))
        return 0
    issues = verify_qualification(root)
    print(json.dumps({"issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
