"""Fail-closed offline M5 protocol for interactive IA3/IA4 tool use.

This module defines protocol state and validates recorded fixtures. It never
contacts a model, executes a tool, advances simulation time, or actuates a DER.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from .budget import DualBudget
from .ia4_adapter import IA4FixtureAdapter, IA4_RESPONSE_SCHEMA_VERSION
from .ia4_smoke_fixture import (
    build_smoke_capability_profile,
)
from .orchestration_contract import (
    CapabilityProfile,
    ContractViolation,
    ControllerDecision,
    InformationLevel,
    KnowledgeAxis,
    OrchestrationRung,
    OutcomeRecord,
    PlanValidator,
    SideEffectClass,
    ToolCallRecord,
    TypedObservation,
    assert_capability_parity,
)


M5_PROTOCOL_SCHEMA_VERSION = "grideval-g7-ia4-interactive-protocol/v1"
M5_MODEL_REQUEST_SCHEMA_VERSION = "grideval-g7-ia4-interactive-request/v1"
M5_TOOL_REQUEST_SCHEMA_VERSION = "grideval-g7-ia4-tool-request/v1"
M5_TOOL_RESULT_SCHEMA_VERSION = "grideval-g7-ia4-tool-result/v1"
M5_REAL_ADAPTER_TOOL_RESULT_SCHEMA_VERSION = (
    "grideval-g7-m5-real-adapter-tool-result/v1"
)
M5_EPISODE_RECEIPT_SCHEMA_VERSION = "grideval-g7-ia4-interactive-receipt/v1"
M5_CONTRACT_ARTIFACT_SCHEMA_VERSION = "grideval-g7-m5-contract-artifact/v1"


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
        raise ContractViolation("value is not canonical JSON") from exc


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_exact_keys(payload: Mapping[str, Any], expected: set[str],
                        label: str) -> None:
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ContractViolation(
            f"{label} fields differ: missing={missing}, extra={extra}"
        )


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
    if expected == "null":
        return value is None
    raise ContractViolation(f"unsupported strict-schema type: {expected}")


def validate_strict_json_schema(instance: Any, schema: Mapping[str, Any], *,
                                path: str = "$") -> None:
    """Validate the deliberately small JSON-Schema subset used by M5 tools."""

    allowed_keywords = {
        "type", "properties", "required", "additionalProperties", "items",
        "minItems", "maxItems", "uniqueItems", "enum", "const", "minimum",
        "maximum", "minLength", "maxLength",
    }
    unknown = set(schema) - allowed_keywords
    if unknown:
        raise ContractViolation(
            f"{path} uses unsupported strict-schema keywords: {sorted(unknown)}"
        )
    if "const" in schema and instance != schema["const"]:
        raise ContractViolation(f"{path} does not match const")
    if "enum" in schema and instance not in schema["enum"]:
        raise ContractViolation(f"{path} is outside enum")
    expected_type = schema.get("type")
    if expected_type is not None:
        types = [expected_type] if isinstance(expected_type, str) else expected_type
        if not isinstance(types, list) or not all(
                isinstance(item, str) for item in types):
            raise ContractViolation(f"{path} has an invalid type declaration")
        if not any(_matches_type(instance, item) for item in types):
            raise ContractViolation(f"{path} has the wrong JSON type")

    if isinstance(instance, Mapping):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, Mapping) or not isinstance(required, list):
            raise ContractViolation(f"{path} has an invalid object schema")
        missing = set(required) - set(instance)
        if missing:
            raise ContractViolation(f"{path} is missing fields: {sorted(missing)}")
        if schema.get("additionalProperties") is False:
            extra = set(instance) - set(properties)
            if extra:
                raise ContractViolation(f"{path} has extra fields: {sorted(extra)}")
        for key, value in instance.items():
            if key in properties:
                validate_strict_json_schema(
                    value, properties[key], path=f"{path}.{key}"
                )

    if isinstance(instance, list):
        if len(instance) < int(schema.get("minItems", 0)):
            raise ContractViolation(f"{path} has too few items")
        if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
            raise ContractViolation(f"{path} has too many items")
        if schema.get("uniqueItems"):
            encoded = [_canonical_json(item) for item in instance]
            if len(encoded) != len(set(encoded)):
                raise ContractViolation(f"{path} contains duplicate items")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, value in enumerate(instance):
                validate_strict_json_schema(
                    value, item_schema, path=f"{path}[{index}]"
                )

    if isinstance(instance, str):
        if len(instance) < int(schema.get("minLength", 0)):
            raise ContractViolation(f"{path} is too short")
        if "maxLength" in schema and len(instance) > int(schema["maxLength"]):
            raise ContractViolation(f"{path} is too long")

    if (isinstance(instance, (int, float)) and
            not isinstance(instance, bool)):
        numeric = float(instance)
        if not math.isfinite(numeric):
            raise ContractViolation(f"{path} must be finite")
        if "minimum" in schema and numeric < float(schema["minimum"]):
            raise ContractViolation(f"{path} is below minimum")
        if "maximum" in schema and numeric > float(schema["maximum"]):
            raise ContractViolation(f"{path} is above maximum")


class InteractiveState(str, Enum):
    AWAITING_MODEL = "awaiting_model"
    AWAITING_TOOL_RESULT = "awaiting_tool_result"
    TERMINAL = "terminal"
    FAILED_CLOSED = "failed_closed"


@dataclass(frozen=True)
class M5ToolDefinition:
    """Exact schema and non-actuating cost contract for one M5 tool."""

    name: str
    input_schema_version: str
    output_schema_version: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    side_effect_class: SideEffectClass
    information_axis: KnowledgeAxis
    returned_information_level: InformationLevel
    simulation_time_advance_s: float = 0.0
    outer_rollout_cost: int = 0

    def __post_init__(self) -> None:
        if not self.name or not self.input_schema_version:
            raise ContractViolation("M5 tool name and input schema are required")
        if not self.output_schema_version:
            raise ContractViolation("M5 tool output schema is required")
        if self.side_effect_class is not SideEffectClass.READ_ONLY_NO_TIME_ADVANCE:
            raise ContractViolation("M5 offline tools must be read-only")
        if float(self.simulation_time_advance_s) != 0.0:
            raise ContractViolation("M5 offline tools cannot advance simulation time")
        if int(self.outer_rollout_cost) != 0:
            raise ContractViolation("M5 offline tools cannot consume rollouts")
        _canonical_json(self.input_schema)
        _canonical_json(self.output_schema)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "input_schema_version": self.input_schema_version,
            "output_schema_version": self.output_schema_version,
            "input_schema": _canonical_copy(self.input_schema),
            "output_schema": _canonical_copy(self.output_schema),
            "side_effect_class": self.side_effect_class.value,
            "information_axis": self.information_axis.value,
            "returned_information_level": self.returned_information_level.name.lower(),
            "simulation_time_advance_s": float(self.simulation_time_advance_s),
            "outer_rollout_cost": int(self.outer_rollout_cost),
        }


class M5InteractiveProtocol:
    """Content-addressed state, schema, and episode-budget manifest."""

    def __init__(self, *, adapter: IA4FixtureAdapter,
                 tool_definitions: Sequence[M5ToolDefinition],
                 max_model_turns: int = 3, max_tool_calls: int = 1,
                 max_completion_tokens_per_turn: int = 512,
                 max_total_model_tokens: int = 8192):
        definitions = tuple(tool_definitions)
        if not definitions:
            raise ContractViolation("M5 protocol requires at least one tool")
        names = [item.name for item in definitions]
        if len(names) != len(set(names)):
            raise ContractViolation("M5 protocol contains duplicate tool names")
        if not 1 <= int(max_model_turns) <= 8:
            raise ContractViolation("max_model_turns must lie in [1, 8]")
        if not 0 <= int(max_tool_calls) <= adapter.profile.tool_call_cap:
            raise ContractViolation("max_tool_calls exceeds the capability profile")
        if int(max_model_turns) <= int(max_tool_calls):
            raise ContractViolation("M5 protocol must reserve a terminal model turn")
        if not 1 <= int(max_completion_tokens_per_turn) <= 1000:
            raise ContractViolation(
                "max_completion_tokens_per_turn must lie in [1, 1000]"
            )
        if int(max_total_model_tokens) < int(max_completion_tokens_per_turn):
            raise ContractViolation("total token cap is below the per-turn cap")

        declared = {
            item["name"]: item
            for item in adapter.tool_contract.describe_allowed(names)
        }
        for definition in definitions:
            item = declared[definition.name]
            expected = {
                "name": definition.name,
                "input_schema_version": definition.input_schema_version,
                "output_schema_version": definition.output_schema_version,
                "side_effect_class": definition.side_effect_class.value,
                "information_axis": definition.information_axis.value,
                "minimum_information_level": (
                    definition.returned_information_level.name.lower()
                ),
            }
            if item != expected:
                raise ContractViolation(
                    f"M5 tool definition drifts from base surface: {definition.name}"
                )

        self.adapter = adapter
        self.tool_definitions = definitions
        self.max_model_turns = int(max_model_turns)
        self.max_tool_calls = int(max_tool_calls)
        self.max_completion_tokens_per_turn = int(
            max_completion_tokens_per_turn
        )
        self.max_total_model_tokens = int(max_total_model_tokens)
        self._by_name = {item.name: item for item in definitions}

    def content_dict(self) -> dict[str, Any]:
        return {
            "schema_version": M5_PROTOCOL_SCHEMA_VERSION,
            "development_only": True,
            "campaign_authorized": False,
            "evaluation_sealed": True,
            "model_transport_authorized": False,
            "tool_execution_authorized": False,
            "simulator_access_authorized": False,
            "detector_access_authorized": False,
            "participant_rungs": ["IA3", "IA4"],
            "base_search_surface_id": self.adapter.search_surface.search_surface_id,
            "enabled_tools": [item.to_dict() for item in self.tool_definitions],
            "state_machine": {
                "initial": InteractiveState.AWAITING_MODEL.value,
                "states": [item.value for item in InteractiveState],
                "accepted_transitions": [
                    "awaiting_model->awaiting_tool_result",
                    "awaiting_tool_result->awaiting_model",
                    "awaiting_model->terminal",
                    "any_nonterminal->failed_closed",
                ],
                "one_outstanding_call": True,
                "terminal_is_immutable": True,
                "invalid_input_policy": "consume_presented_turn_and_fail_closed",
                "automatic_retry": False,
            },
            "episode_caps": {
                "model_turns": self.max_model_turns,
                "tool_calls": self.max_tool_calls,
                "outer_rollouts": 0,
                "completion_tokens_per_turn": self.max_completion_tokens_per_turn,
                "total_model_tokens": self.max_total_model_tokens,
            },
            "schema_versions": {
                "model_request": M5_MODEL_REQUEST_SCHEMA_VERSION,
                "tool_request": M5_TOOL_REQUEST_SCHEMA_VERSION,
                "tool_result": M5_TOOL_RESULT_SCHEMA_VERSION,
                "terminal_response": IA4_RESPONSE_SCHEMA_VERSION,
                "episode_receipt": M5_EPISODE_RECEIPT_SCHEMA_VERSION,
            },
            "matched_control": {
                "rung": "IA3",
                "same_base_surface": True,
                "same_tool_schema_and_fixture": True,
                "same_call_and_rollout_caps": True,
                "same_terminal_candidate_set": True,
                "actual_model_compute_match_deferred": True,
            },
        }

    @property
    def protocol_id(self) -> str:
        return "m5proto_" + _sha256(self.content_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self.content_dict()
        payload["protocol_id"] = self.protocol_id
        return payload

    def tool(self, name: str) -> M5ToolDefinition:
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise ContractViolation(f"M5 tool is not enabled: {name}") from exc


@dataclass(frozen=True)
class ParsedToolRequest:
    turn_index: int
    call_id: str
    tool_name: str
    arguments: Mapping[str, Any]
    rationale: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": _canonical_copy(self.arguments),
            "rationale": self.rationale,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class FixtureToolResult:
    protocol_id: str
    call_id: str
    tool_name: str
    output_schema_version: str
    output: Mapping[str, Any]
    returned_information_level: InformationLevel
    simulation_time_advance_s: float
    outer_rollout_cost: int
    wall_clock_ms: float
    source_fixture_id: str

    @classmethod
    def build(cls, *, protocol: M5InteractiveProtocol,
              request: ParsedToolRequest, output: Mapping[str, Any],
              wall_clock_ms: float = 0.0) -> "FixtureToolResult":
        definition = protocol.tool(request.tool_name)
        canonical_output = _canonical_copy(output)
        validate_strict_json_schema(canonical_output, definition.output_schema)
        fixture_payload = {
            "protocol_id": protocol.protocol_id,
            "call_id": request.call_id,
            "tool_name": request.tool_name,
            "output_schema_version": definition.output_schema_version,
            "output": canonical_output,
        }
        return cls(
            protocol_id=protocol.protocol_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            output_schema_version=definition.output_schema_version,
            output=canonical_output,
            returned_information_level=definition.returned_information_level,
            simulation_time_advance_s=definition.simulation_time_advance_s,
            outer_rollout_cost=definition.outer_rollout_cost,
            wall_clock_ms=float(wall_clock_ms),
            source_fixture_id="fixture_" + _sha256(fixture_payload)[:20],
        )

    def __post_init__(self) -> None:
        if not self.protocol_id or not self.call_id or not self.tool_name:
            raise ContractViolation("tool result identity fields are required")
        if not self.output_schema_version or not self.source_fixture_id:
            raise ContractViolation("tool result schema and fixture IDs are required")
        if not math.isfinite(float(self.wall_clock_ms)) or self.wall_clock_ms < 0:
            raise ContractViolation("tool result wall_clock_ms is invalid")

    @property
    def fingerprint(self) -> str:
        return _sha256(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": M5_TOOL_RESULT_SCHEMA_VERSION,
            "protocol_id": self.protocol_id,
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "output_schema_version": self.output_schema_version,
            "output": _canonical_copy(self.output),
            "returned_information_level": (
                self.returned_information_level.name.lower()
            ),
            "simulation_time_advance_s": float(self.simulation_time_advance_s),
            "outer_rollout_cost": int(self.outer_rollout_cost),
            "wall_clock_ms": float(self.wall_clock_ms),
            "source_fixture_id": self.source_fixture_id,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


def _validate_real_adapter_invocation(
        receipt: Mapping[str, Any], *, definition: M5ToolDefinition,
        request: ParsedToolRequest, output: Mapping[str, Any],
        caller_rung: OrchestrationRung) -> dict[str, Any]:
    """Validate generic M24 invocation provenance without importing M24."""

    if not isinstance(receipt, Mapping):
        raise ContractViolation("real adapter invocation receipt must be an object")
    checked = _canonical_copy(receipt)
    _require_exact_keys(
        checked,
        {
            "schema_version", "contract_id", "caller_rung", "tool_name",
            "request_schema_version", "output_schema_version",
            "request_canonical_json", "request_sha256",
            "payload_canonical_json", "payload_sha256", "payload_fields",
            "target_alias_map", "source_binding", "audit_binding",
            "files_read", "side_effects", "access_boundary", "invocation_id",
        },
        "real adapter invocation receipt",
    )
    if checked["schema_version"] != (
            "grideval-g7-m24-read-only-adapter-invocation/v1"):
        raise ContractViolation("real adapter invocation schema mismatch")
    if (not isinstance(checked["contract_id"], str) or
            not checked["contract_id"].startswith("m24contract_")):
        raise ContractViolation("real adapter contract identity is invalid")
    if checked["caller_rung"] != caller_rung.value:
        raise ContractViolation("real adapter caller rung mismatch")
    if checked["tool_name"] != request.tool_name:
        raise ContractViolation("real adapter tool name mismatch")
    if checked["request_schema_version"] != definition.input_schema_version:
        raise ContractViolation("real adapter request schema mismatch")
    if checked["output_schema_version"] != definition.output_schema_version:
        raise ContractViolation("real adapter output schema mismatch")

    request_json = _canonical_json(request.arguments)
    payload_json = _canonical_json(output)
    if checked["request_canonical_json"] != request_json:
        raise ContractViolation("real adapter request canonical bytes mismatch")
    if checked["request_sha256"] != hashlib.sha256(
            request_json.encode("utf-8")).hexdigest():
        raise ContractViolation("real adapter request hash mismatch")
    if checked["payload_canonical_json"] != payload_json:
        raise ContractViolation("real adapter payload canonical bytes mismatch")
    if checked["payload_sha256"] != hashlib.sha256(
            payload_json.encode("utf-8")).hexdigest():
        raise ContractViolation("real adapter payload hash mismatch")
    payload_fields = checked["payload_fields"]
    if (not isinstance(payload_fields, list) or
            len(payload_fields) != len(set(payload_fields)) or
            set(payload_fields) != set(output)):
        raise ContractViolation("real adapter payload field binding mismatch")

    aliases = checked["target_alias_map"]
    values = output.get("values")
    if (not isinstance(aliases, Mapping) or not isinstance(values, Mapping) or
            set(aliases) != set(values) or
            not all(isinstance(value, str) and value for value in aliases.values())):
        raise ContractViolation("real adapter target alias binding mismatch")

    source = checked["source_binding"]
    if not isinstance(source, Mapping):
        raise ContractViolation("real adapter source binding is invalid")
    _require_exact_keys(
        source,
        {
            "source_id", "source_sha256", "contract_id", "classification",
            "admitted", "full_internal_response_vectors_preserved_by_exact_byte_reference",
        },
        "real adapter source binding",
    )
    if (not isinstance(source["source_id"], str) or
            not source["source_id"].startswith("m23source_") or
            not isinstance(source["contract_id"], str) or
            not source["contract_id"].startswith("m23contract_") or
            source["classification"] != "PRELIMINARY_ONLY" or
            source["admitted"] is not False or
            source[
                "full_internal_response_vectors_preserved_by_exact_byte_reference"
            ] is not True or
            not isinstance(source["source_sha256"], str) or
            not re.fullmatch(r"[0-9a-f]{64}", source["source_sha256"])):
        raise ContractViolation("real adapter source binding drift")

    audit = checked["audit_binding"]
    if not isinstance(audit, Mapping):
        raise ContractViolation("real adapter audit binding is invalid")
    _require_exact_keys(
        audit,
        {"audit_id", "audit_sha256", "status", "issues"},
        "real adapter audit binding",
    )
    if (not isinstance(audit["audit_id"], str) or
            not audit["audit_id"].startswith("m23audit_") or
            not isinstance(audit["audit_sha256"], str) or
            not re.fullmatch(r"[0-9a-f]{64}", audit["audit_sha256"]) or
            audit["status"] != "passed" or audit["issues"] != []):
        raise ContractViolation("real adapter audit binding drift")

    files_read = checked["files_read"]
    if (not isinstance(files_read, list) or len(files_read) != 2 or
            len(set(files_read)) != 2 or
            not all(isinstance(path, str) and path for path in files_read)):
        raise ContractViolation("real adapter file-read provenance mismatch")
    expected_side_effects = {
        "class": "read_only_no_time_advance",
        "simulation_time_advance_s": 0.0,
        "outer_rollout_cost": 0,
        "file_writes": 0,
    }
    if checked["side_effects"] != expected_side_effects:
        raise ContractViolation("real adapter side-effect provenance drift")
    expected_access = {
        "real_local_read_only_adapter_executed": True,
        "external_tool_execution_used": False,
        "model_accessed": False,
        "embedding_accessed": False,
        "detector_accessed": False,
        "defense_accessed": False,
        "network_accessed": False,
        "docker_accessed": False,
        "simulator_accessed": False,
        "physical_actuator_accessed": False,
        "evaluation_accessed": False,
    }
    if checked["access_boundary"] != expected_access:
        raise ContractViolation("real adapter access boundary drift")

    address_content = _canonical_copy(checked)
    invocation_id = address_content.pop("invocation_id")
    if invocation_id != "m24invoke_" + _sha256(address_content):
        raise ContractViolation("real adapter invocation self-address mismatch")
    return checked


@dataclass(frozen=True)
class RealAdapterToolResult:
    """A real read-only adapter result with non-consumer provenance."""

    protocol_id: str
    call_id: str
    tool_name: str
    output_schema_version: str
    output: Mapping[str, Any]
    returned_information_level: InformationLevel
    simulation_time_advance_s: float
    outer_rollout_cost: int
    wall_clock_ms: float
    adapter_invocation_receipt: Mapping[str, Any]

    @classmethod
    def build(cls, *, protocol: M5InteractiveProtocol,
              request: ParsedToolRequest, output: Mapping[str, Any],
              adapter_invocation_receipt: Mapping[str, Any],
              caller_rung: OrchestrationRung,
              wall_clock_ms: float = 0.0) -> "RealAdapterToolResult":
        definition = protocol.tool(request.tool_name)
        canonical_output = _canonical_copy(output)
        validate_strict_json_schema(canonical_output, definition.output_schema)
        checked_receipt = _validate_real_adapter_invocation(
            adapter_invocation_receipt,
            definition=definition,
            request=request,
            output=canonical_output,
            caller_rung=caller_rung,
        )
        return cls(
            protocol_id=protocol.protocol_id,
            call_id=request.call_id,
            tool_name=request.tool_name,
            output_schema_version=definition.output_schema_version,
            output=canonical_output,
            returned_information_level=definition.returned_information_level,
            simulation_time_advance_s=definition.simulation_time_advance_s,
            outer_rollout_cost=definition.outer_rollout_cost,
            wall_clock_ms=float(wall_clock_ms),
            adapter_invocation_receipt=checked_receipt,
        )

    def __post_init__(self) -> None:
        if not self.protocol_id or not self.call_id or not self.tool_name:
            raise ContractViolation("real tool result identity fields are required")
        if not self.output_schema_version:
            raise ContractViolation("real tool result schema is required")
        if not math.isfinite(float(self.wall_clock_ms)) or self.wall_clock_ms < 0:
            raise ContractViolation("real tool result wall_clock_ms is invalid")
        if not isinstance(self.adapter_invocation_receipt, Mapping):
            raise ContractViolation("real tool result provenance is invalid")

    def consumer_dict(self) -> dict[str, Any]:
        """Return only the envelope and payload visible to the next actor turn."""

        return {
            "schema_version": M5_TOOL_RESULT_SCHEMA_VERSION,
            "protocol_id": self.protocol_id,
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "output_schema_version": self.output_schema_version,
            "output": _canonical_copy(self.output),
            "returned_information_level": (
                self.returned_information_level.name.lower()
            ),
            "simulation_time_advance_s": float(self.simulation_time_advance_s),
            "outer_rollout_cost": int(self.outer_rollout_cost),
            "wall_clock_ms": float(self.wall_clock_ms),
        }

    @property
    def fingerprint(self) -> str:
        return _sha256(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": M5_REAL_ADAPTER_TOOL_RESULT_SCHEMA_VERSION,
            "result_kind": "real_local_read_only_adapter",
            **{
                key: value
                for key, value in self.consumer_dict().items()
                if key != "schema_version"
            },
            "adapter_invocation_receipt": _canonical_copy(
                self.adapter_invocation_receipt
            ),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


def _validate_usage(usage: Mapping[str, Any], *, completion_cap: int) -> dict[str, int]:
    _require_exact_keys(
        usage,
        {"prompt_tokens", "completion_tokens", "total_tokens"},
        "model usage",
    )
    result: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ContractViolation(f"model usage {key} is invalid")
        result[key] = value
    if result["total_tokens"] != (
            result["prompt_tokens"] + result["completion_tokens"]):
        raise ContractViolation("model usage total_tokens is inconsistent")
    if result["completion_tokens"] > completion_cap:
        raise ContractViolation("completion token cap exceeded")
    return result


class IAInteractiveSession:
    """Transactional M5 session for an IA3 control or IA4 decision core."""

    def __init__(self, *, protocol: M5InteractiveProtocol,
                 profile: CapabilityProfile, observation: TypedObservation,
                 history: Sequence[OutcomeRecord], decision_core_id: str):
        if profile.rung not in {OrchestrationRung.IA3, OrchestrationRung.IA4}:
            raise ContractViolation("M5 session requires IA3 or IA4")
        if not decision_core_id:
            raise ContractViolation("decision_core_id is required")
        assert_capability_parity(profile, protocol.adapter.profile)
        self.protocol = protocol
        self.profile = profile
        self.decision_core_id = decision_core_id
        self.decision_context = protocol.adapter.build_request(observation, history)
        self.state = InteractiveState.AWAITING_MODEL
        self.turn_index = 0
        self.model_turn_count = 0
        self.total_model_tokens = 0
        self._outstanding: ParsedToolRequest | None = None
        self._tool_calls: list[ToolCallRecord] = []
        self._tool_results: list[
            FixtureToolResult | RealAdapterToolResult
        ] = []
        self._model_turns: list[dict[str, Any]] = []
        self._transcript: list[dict[str, Any]] = []
        self.terminal_decision: ControllerDecision | None = None
        self.failure_reason: str | None = None

    @property
    def tool_calls(self) -> tuple[ToolCallRecord, ...]:
        return tuple(self._tool_calls)

    @property
    def outstanding_request(self) -> ParsedToolRequest | None:
        return self._outstanding

    def _assert_state(self, expected: InteractiveState) -> None:
        if self.state is not expected:
            reason = (
                f"session state is {self.state.value}, expected {expected.value}"
            )
            if self.state in {
                    InteractiveState.AWAITING_MODEL,
                    InteractiveState.AWAITING_TOOL_RESULT}:
                self._fail_closed(reason)
            raise ContractViolation(reason)

    def _fail_closed(self, reason: str) -> None:
        self.failure_reason = reason
        self.state = InteractiveState.FAILED_CLOSED
        self._transcript.append({"event": "failed_closed", "reason": reason})

    def fail_closed(self, reason: str) -> None:
        """Record an execution-overlay rejection without enabling recovery."""

        if self.state not in {
                InteractiveState.AWAITING_MODEL,
                InteractiveState.AWAITING_TOOL_RESULT}:
            raise ContractViolation("only a live M5 session can fail closed")
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation("fail-closed reason is required")
        self._fail_closed(reason)

    def response_schema(self) -> dict[str, Any]:
        surface_id = self.protocol.adapter.search_surface.search_surface_id
        candidate_ids = list(self.protocol.adapter.candidate_library.ids())
        tool_variants = []
        for definition in self.protocol.tool_definitions:
            tool_variants.append({
                "type": "object",
                "properties": {
                    "schema_version": {"const": M5_TOOL_REQUEST_SCHEMA_VERSION},
                    "protocol_id": {"const": self.protocol.protocol_id},
                    "base_search_surface_id": {"const": surface_id},
                    "turn_index": {"const": self.turn_index},
                    "decision": {"const": "tool_request"},
                    "call_id": {
                        "type": "string", "minLength": 1, "maxLength": 80,
                    },
                    "tool_name": {"const": definition.name},
                    "arguments": _canonical_copy(definition.input_schema),
                    "rationale": {
                        "type": "string", "minLength": 1, "maxLength": 2000,
                    },
                },
                "required": [
                    "schema_version", "protocol_id", "base_search_surface_id",
                    "turn_index", "decision", "call_id", "tool_name",
                    "arguments", "rationale",
                ],
                "additionalProperties": False,
            })
        common = {
            "schema_version": {"const": IA4_RESPONSE_SCHEMA_VERSION},
            "search_surface_id": {"const": surface_id},
            "rationale": {"type": "string", "minLength": 1, "maxLength": 2000},
            "used_tool_call_ids": {
                "type": "array",
                "const": [item.call_id for item in self._tool_calls],
            },
        }
        terminal = [{
            "type": "object",
            "properties": {
                **common,
                "decision": {"const": "plan"},
                "candidate_id": {"type": "string", "enum": candidate_ids},
            },
            "required": [
                "schema_version", "search_surface_id", "decision",
                "candidate_id", "rationale", "used_tool_call_ids",
            ],
            "additionalProperties": False,
        }]
        for decision in ("safety_refusal", "no_action"):
            terminal.append({
                "type": "object",
                "properties": {**common, "decision": {"const": decision}},
                "required": [
                    "schema_version", "search_surface_id", "decision",
                    "rationale", "used_tool_call_ids",
                ],
                "additionalProperties": False,
            })
        return {"oneOf": tool_variants + terminal}

    def next_request(self) -> dict[str, Any]:
        self._assert_state(InteractiveState.AWAITING_MODEL)
        if self.model_turn_count >= self.protocol.max_model_turns:
            self._fail_closed("model turn cap exhausted before terminal decision")
            raise ContractViolation(self.failure_reason or "model turn cap exhausted")
        request = {
            "schema_version": M5_MODEL_REQUEST_SCHEMA_VERSION,
            "protocol_id": self.protocol.protocol_id,
            "base_search_surface_id": (
                self.protocol.adapter.search_surface.search_surface_id
            ),
            "actor_rung": self.profile.rung.value,
            "decision_core_id": self.decision_core_id,
            "turn_index": self.turn_index,
            "remaining_budget": {
                "model_turns": (
                    self.protocol.max_model_turns - self.model_turn_count
                ),
                "tool_calls": (
                    self.protocol.max_tool_calls - len(self._tool_calls)
                ),
                "total_model_tokens": (
                    self.protocol.max_total_model_tokens - self.total_model_tokens
                ),
                "outer_rollouts": 0,
            },
            "decision_context": _canonical_copy(self.decision_context),
            "transcript": _canonical_copy(self._transcript),
            "response_schema": self.response_schema(),
        }
        request["request_sha256"] = _sha256(request)
        return request

    def _parse_tool_request(self, payload: Mapping[str, Any]) -> ParsedToolRequest:
        expected = {
            "schema_version", "protocol_id", "base_search_surface_id",
            "turn_index", "decision", "call_id", "tool_name", "arguments",
            "rationale",
        }
        _require_exact_keys(payload, expected, "tool request")
        if payload["schema_version"] != M5_TOOL_REQUEST_SCHEMA_VERSION:
            raise ContractViolation("tool request schema_version mismatch")
        if payload["protocol_id"] != self.protocol.protocol_id:
            raise ContractViolation("tool request protocol_id mismatch")
        if payload["base_search_surface_id"] != (
                self.protocol.adapter.search_surface.search_surface_id):
            raise ContractViolation("tool request search surface mismatch")
        if payload["turn_index"] != self.turn_index:
            raise ContractViolation("tool request turn_index mismatch")
        if payload["decision"] != "tool_request":
            raise ContractViolation("tool request decision mismatch")
        call_id = payload["call_id"]
        if not isinstance(call_id, str) or not re.fullmatch(
                r"call_[A-Za-z0-9_-]{1,75}", call_id):
            raise ContractViolation("tool request call_id is invalid")
        if call_id in {item.call_id for item in self._tool_calls}:
            raise ContractViolation("tool request reuses a call_id")
        if len(self._tool_calls) >= self.protocol.max_tool_calls:
            raise ContractViolation("tool call cap exceeded")
        if self.model_turn_count + 1 >= self.protocol.max_model_turns:
            raise ContractViolation("tool request would consume the terminal turn")
        tool_name = payload["tool_name"]
        if not isinstance(tool_name, str):
            raise ContractViolation("tool request tool_name must be a string")
        definition = self.protocol.tool(tool_name)
        if tool_name not in self.profile.allowed_tool_names:
            raise ContractViolation("tool request exceeds profile authority")
        if self.profile.knowledge.level(definition.information_axis) < (
                definition.returned_information_level):
            raise ContractViolation("tool request exceeds the K profile")
        arguments = payload["arguments"]
        validate_strict_json_schema(arguments, definition.input_schema)
        rationale = payload["rationale"]
        if (not isinstance(rationale, str) or not rationale.strip() or
                len(rationale) > 2000):
            raise ContractViolation("tool request rationale is invalid")
        canonical = _canonical_copy(payload)
        return ParsedToolRequest(
            turn_index=self.turn_index,
            call_id=call_id,
            tool_name=tool_name,
            arguments=_canonical_copy(arguments),
            rationale=rationale,
            fingerprint=_sha256(canonical),
        )

    def _parse_terminal(self, payload: Mapping[str, Any]) -> ControllerDecision:
        decision_name = payload.get("decision")
        common = {
            "schema_version", "search_surface_id", "decision", "rationale",
            "used_tool_call_ids",
        }
        expected = common | ({"candidate_id"} if decision_name == "plan" else set())
        _require_exact_keys(payload, expected, "terminal response")
        if payload["schema_version"] != IA4_RESPONSE_SCHEMA_VERSION:
            raise ContractViolation("terminal response schema_version mismatch")
        if payload["search_surface_id"] != (
                self.protocol.adapter.search_surface.search_surface_id):
            raise ContractViolation("terminal response search surface mismatch")
        rationale = payload["rationale"]
        if (not isinstance(rationale, str) or not rationale.strip() or
                len(rationale) > 2000):
            raise ContractViolation("terminal response rationale is invalid")
        used_ids = payload["used_tool_call_ids"]
        expected_ids = [item.call_id for item in self._tool_calls]
        if used_ids != expected_ids:
            raise ContractViolation("terminal tool lineage is incomplete or reordered")
        self.protocol.adapter.tool_contract.validate_calls(
            self.profile, self._tool_calls
        )
        if decision_name == "plan":
            candidate_id = payload["candidate_id"]
            if not isinstance(candidate_id, str):
                raise ContractViolation("terminal candidate_id must be a string")
            candidate = self.protocol.adapter.candidate_library.get(candidate_id)
            plan = candidate.instantiate(self.profile.rung, rationale)
            return ControllerDecision.submit(
                plan,
                reason="m5_interactive_candidate_selection",
                candidate_id=candidate_id,
            )
        if decision_name == "safety_refusal":
            return ControllerDecision.refuse(rationale)
        if decision_name == "no_action":
            return ControllerDecision.no_action(rationale)
        raise ContractViolation("terminal decision is unsupported")

    def accept_model_turn(self, *, request_sha256: str,
                          payload: Mapping[str, Any], model_id: str,
                          usage: Mapping[str, Any]) -> None:
        self._assert_state(InteractiveState.AWAITING_MODEL)
        try:
            request = self.next_request()
            self.model_turn_count += 1
            if request_sha256 != request["request_sha256"]:
                raise ContractViolation("model turn request_sha256 mismatch")
            if not isinstance(model_id, str) or not model_id:
                raise ContractViolation("model_id is required")
            checked_usage = _validate_usage(
                usage,
                completion_cap=self.protocol.max_completion_tokens_per_turn,
            )
            next_total = self.total_model_tokens + checked_usage["total_tokens"]
            if next_total > self.protocol.max_total_model_tokens:
                raise ContractViolation("total model token cap exceeded")

            self.total_model_tokens = next_total
            if not isinstance(payload, Mapping):
                raise ContractViolation("model turn payload must be an object")
            canonical_payload = _canonical_copy(payload)
            decision_name = canonical_payload.get("decision")
            turn_record = {
                "turn_index": self.turn_index,
                "request_sha256": request_sha256,
                "model_id": model_id,
                "usage": checked_usage,
                "payload": canonical_payload,
                "response_sha256": _sha256(canonical_payload),
            }
            if decision_name == "tool_request":
                parsed = self._parse_tool_request(canonical_payload)
                self._outstanding = parsed
                turn_record["accepted_as"] = "tool_request"
                self._model_turns.append(turn_record)
                self._transcript.append({
                    "event": "tool_request",
                    **parsed.to_dict(),
                })
                self.state = InteractiveState.AWAITING_TOOL_RESULT
                return

            decision = self._parse_terminal(canonical_payload)
            self.terminal_decision = decision
            turn_record["accepted_as"] = decision.kind.value
            self._model_turns.append(turn_record)
            self._transcript.append({
                "event": "terminal_decision",
                "kind": decision.kind.value,
                "candidate_id": decision.candidate_id,
                "reason": decision.reason,
            })
            self.state = InteractiveState.TERMINAL
        except ContractViolation as exc:
            if self.state not in {
                    InteractiveState.TERMINAL, InteractiveState.FAILED_CLOSED}:
                self._fail_closed(str(exc))
            raise

    def submit_tool_result(
            self, result: FixtureToolResult | RealAdapterToolResult) -> None:
        self._assert_state(InteractiveState.AWAITING_TOOL_RESULT)
        try:
            request = self._outstanding
            if request is None:
                raise ContractViolation("tool result has no outstanding request")
            if not isinstance(result, (FixtureToolResult, RealAdapterToolResult)):
                raise ContractViolation("tool result has the wrong type")
            definition = self.protocol.tool(request.tool_name)
            if result.protocol_id != self.protocol.protocol_id:
                raise ContractViolation("tool result protocol_id mismatch")
            if result.call_id != request.call_id:
                raise ContractViolation("tool result call_id mismatch")
            if result.tool_name != request.tool_name:
                raise ContractViolation("tool result tool_name mismatch")
            if result.output_schema_version != definition.output_schema_version:
                raise ContractViolation("tool result output schema mismatch")
            if result.returned_information_level is not (
                    definition.returned_information_level):
                raise ContractViolation("tool result information level mismatch")
            if result.simulation_time_advance_s != 0.0:
                raise ContractViolation("M5 fixture advanced simulation time")
            if result.outer_rollout_cost != 0:
                raise ContractViolation("M5 fixture consumed an outer rollout")
            validate_strict_json_schema(result.output, definition.output_schema)
            if isinstance(result, FixtureToolResult):
                rebuilt_fixture = FixtureToolResult.build(
                    protocol=self.protocol,
                    request=request,
                    output=result.output,
                    wall_clock_ms=result.wall_clock_ms,
                )
                if result.source_fixture_id != rebuilt_fixture.source_fixture_id:
                    raise ContractViolation("tool result fixture lineage mismatch")
                transcript_result = result.to_dict()
                accepted_result = result
            else:
                rebuilt_real = RealAdapterToolResult.build(
                    protocol=self.protocol,
                    request=request,
                    output=result.output,
                    adapter_invocation_receipt=(
                        result.adapter_invocation_receipt
                    ),
                    caller_rung=self.profile.rung,
                    wall_clock_ms=result.wall_clock_ms,
                )
                if result.to_dict() != rebuilt_real.to_dict():
                    raise ContractViolation("real adapter result lineage mismatch")
                transcript_result = result.consumer_dict()
                accepted_result = rebuilt_real
            call = ToolCallRecord(
                call_id=request.call_id,
                caller_rung=self.profile.rung,
                tool_name=request.tool_name,
                input_schema_version=definition.input_schema_version,
                output_schema_version=definition.output_schema_version,
                side_effect_class=definition.side_effect_class,
                simulation_time_advance_s=0.0,
                outer_rollout_cost=0,
                wall_clock_ms=result.wall_clock_ms,
                model_tokens=0,
                returned_information_level=result.returned_information_level,
                validation_result="accepted",
            )
            candidate_calls = [*self._tool_calls, call]
            self.protocol.adapter.tool_contract.validate_calls(
                self.profile, candidate_calls
            )
            self._tool_calls.append(call)
            self._tool_results.append(accepted_result)
            self._transcript.append({"event": "tool_result", **transcript_result})
            self._outstanding = None
            self.turn_index += 1
            self.state = InteractiveState.AWAITING_MODEL
        except ContractViolation as exc:
            if self.state is not InteractiveState.FAILED_CLOSED:
                self._fail_closed(str(exc))
            raise

    def receipt(self, *, model_transport_used: bool = False) -> dict[str, Any]:
        """Emit a terminal receipt with execution-overlay transport provenance."""

        if self.state not in {
                InteractiveState.TERMINAL, InteractiveState.FAILED_CLOSED}:
            raise ContractViolation("cannot emit a receipt for a live M5 session")
        if not isinstance(model_transport_used, bool):
            raise ContractViolation("model_transport_used must be boolean")
        decision = self.terminal_decision
        real_adapter_used = any(
            isinstance(item, RealAdapterToolResult)
            for item in self._tool_results
        )
        payload = {
            "schema_version": M5_EPISODE_RECEIPT_SCHEMA_VERSION,
            "protocol_id": self.protocol.protocol_id,
            "base_search_surface_id": (
                self.protocol.adapter.search_surface.search_surface_id
            ),
            "actor_rung": self.profile.rung.value,
            "decision_core_id": self.decision_core_id,
            "development_only": True,
            "campaign_authorized": False,
            "evaluation_sealed": True,
            "model_transport_used": model_transport_used,
            "tool_execution_used": real_adapter_used,
            "simulator_accessed": False,
            "detector_accessed": False,
            "embedding_accessed": False,
            "state": self.state.value,
            "failure_reason": self.failure_reason,
            "model_turns": _canonical_copy(self._model_turns),
            "tool_calls": [item.to_dict() for item in self._tool_calls],
            "tool_results": [item.to_dict() for item in self._tool_results],
            "transcript": _canonical_copy(self._transcript),
            "accounting": {
                "model_turns": self.model_turn_count,
                "tool_calls": len(self._tool_calls),
                "outer_rollouts": sum(
                    item.outer_rollout_cost for item in self._tool_calls
                ),
                "total_model_tokens": self.total_model_tokens,
            },
            "terminal_decision": None if decision is None else {
                "kind": decision.kind.value,
                "candidate_id": decision.candidate_id,
                "reason": decision.reason,
                "plan": decision.plan.to_dict() if decision.plan else None,
            },
        }
        if real_adapter_used:
            payload.update({
                "real_local_read_only_adapter_executed": True,
                "synthetic_fixture_injected": False,
                "external_tool_execution_used": False,
            })
        return payload


class MatchedIA3ObserveThenSelect:
    """Deterministic IA3 control using the exact M5 tool/result interface."""

    def tool_request(self, session: IAInteractiveSession) -> dict[str, Any]:
        return {
            "schema_version": M5_TOOL_REQUEST_SCHEMA_VERSION,
            "protocol_id": session.protocol.protocol_id,
            "base_search_surface_id": (
                session.protocol.adapter.search_surface.search_surface_id
            ),
            "turn_index": session.turn_index,
            "decision": "tool_request",
            "call_id": "call_observe_0001",
            "tool_name": "observe_state",
            "arguments": {"fields": ["prior_alarm", "voltage_pu"]},
            "rationale": "Acquire the one shared read-only observation fixture.",
        }

    def terminal_response(self, session: IAInteractiveSession, *,
                          observation_output: Mapping[str, Any]) -> dict[str, Any]:
        voltage = observation_output["values"]["voltage_pu"]
        candidate_ids = session.protocol.adapter.candidate_library.ids()
        selected = candidate_ids[0] if float(voltage) <= 1.0 else candidate_ids[1]
        return {
            "schema_version": IA4_RESPONSE_SCHEMA_VERSION,
            "search_surface_id": (
                session.protocol.adapter.search_surface.search_surface_id
            ),
            "decision": "plan",
            "candidate_id": selected,
            "rationale": (
                "Apply the deterministic threshold rule to the shared fixture."
            ),
            "used_tool_call_ids": [item.call_id for item in session.tool_calls],
        }


def build_m5_protocol(adapter: IA4FixtureAdapter) -> M5InteractiveProtocol:
    """Build the read-only synthetic M5 protocol over the unchanged M4 surface."""

    observe = M5ToolDefinition(
        name="observe_state",
        input_schema_version="observation-query/v1",
        output_schema_version="observation-result/v1",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["fields"],
            "properties": {
                "fields": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 2,
                    "uniqueItems": True,
                    "items": {"type": "string", "enum": [
                        "prior_alarm", "voltage_pu",
                    ]},
                },
            },
        },
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "window", "time_s", "values"],
            "properties": {
                "schema_version": {"const": "observation-result/v1"},
                "window": {"type": "integer", "minimum": 0},
                "time_s": {"type": "integer", "minimum": 0},
                "values": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["prior_alarm", "voltage_pu"],
                    "properties": {
                        "prior_alarm": {"type": "boolean"},
                        "voltage_pu": {"type": "number", "minimum": 0.0,
                                       "maximum": 2.0},
                    },
                },
            },
        },
        side_effect_class=SideEffectClass.READ_ONLY_NO_TIME_ADVANCE,
        information_axis=KnowledgeAxis.GRID,
        returned_information_level=InformationLevel.PARTIAL,
    )
    return M5InteractiveProtocol(
        adapter=adapter,
        tool_definitions=(observe,),
        max_model_turns=3,
        max_tool_calls=1,
        max_completion_tokens_per_turn=512,
        max_total_model_tokens=8192,
    )


def _zero_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _run_fixture_episode(*, protocol: M5InteractiveProtocol,
                         rung: OrchestrationRung,
                         decision_core_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = build_smoke_capability_profile(rung)
    session = IAInteractiveSession(
        protocol=protocol,
        profile=profile,
        observation=TypedObservation(
            0,
            0,
            {"context": "synthetic_interface_fixture", "voltage_pu": 1.0},
        ),
        history=(),
        decision_core_id=decision_core_id,
    )
    policy = MatchedIA3ObserveThenSelect()
    first = session.next_request()
    session.accept_model_turn(
        request_sha256=first["request_sha256"],
        payload=policy.tool_request(session),
        model_id=decision_core_id,
        usage=_zero_usage(),
    )
    outstanding = session.outstanding_request
    assert outstanding is not None
    output = {
        "schema_version": "observation-result/v1",
        "window": 0,
        "time_s": 0,
        "values": {"prior_alarm": False, "voltage_pu": 0.99},
    }
    session.submit_tool_result(FixtureToolResult.build(
        protocol=protocol,
        request=outstanding,
        output=output,
        wall_clock_ms=0.0,
    ))
    second = session.next_request()
    session.accept_model_turn(
        request_sha256=second["request_sha256"],
        payload=policy.terminal_response(
            session, observation_output=output
        ),
        model_id=decision_core_id,
        usage=_zero_usage(),
    )
    assert session.terminal_decision is not None
    validator = PlanValidator(
        profile=profile,
        strategy_library=protocol.adapter.strategy_library,
        tool_contract=protocol.adapter.tool_contract,
        dual_budget=DualBudget(
            window_cap=profile.authority.perturbed_window_cap,
            apparent_energy_cap_kvah=profile.authority.apparent_energy_cap_kvah,
            window_seconds=10.0,
        ),
    )
    validation = validator.evaluate(
        session.terminal_decision,
        benign={"DER_A": (0.0, 0.0), "DER_B": (0.0, 0.0)},
        tool_calls=session.tool_calls,
    ).to_dict()
    return session.receipt(), validation


def build_m5_contract_artifact(*, adapter: IA4FixtureAdapter,
                               spec_file_sha256: str) -> dict[str, Any]:
    """Build deterministic fixture evidence for both sides of the M5 protocol."""

    if not re.fullmatch(r"[0-9a-f]{64}", spec_file_sha256):
        raise ContractViolation("spec_file_sha256 is invalid")
    protocol = build_m5_protocol(adapter)
    ia4_receipt, ia4_validation = _run_fixture_episode(
        protocol=protocol,
        rung=OrchestrationRung.IA4,
        decision_core_id="fixture_ia4_observe_then_select",
    )
    ia3_receipt, ia3_validation = _run_fixture_episode(
        protocol=protocol,
        rung=OrchestrationRung.IA3,
        decision_core_id="matched_ia3_observe_then_select",
    )
    ia4_tool = ia4_receipt["tool_results"][0]
    ia3_tool = ia3_receipt["tool_results"][0]
    parity = {
        "same_protocol_id": (
            ia4_receipt["protocol_id"] == ia3_receipt["protocol_id"]
        ),
        "same_base_search_surface_id": (
            ia4_receipt["base_search_surface_id"] ==
            ia3_receipt["base_search_surface_id"]
        ),
        "same_tool_arguments": (
            ia4_receipt["model_turns"][0]["payload"]["arguments"] ==
            ia3_receipt["model_turns"][0]["payload"]["arguments"]
        ),
        "same_tool_fixture": ia4_tool["source_fixture_id"] == ia3_tool[
            "source_fixture_id"
        ],
        "same_tool_result": ia4_tool["output"] == ia3_tool["output"],
        "same_tool_call_count": (
            ia4_receipt["accounting"]["tool_calls"] ==
            ia3_receipt["accounting"]["tool_calls"]
        ),
        "same_outer_rollout_cost": (
            ia4_receipt["accounting"]["outer_rollouts"] ==
            ia3_receipt["accounting"]["outer_rollouts"] == 0
        ),
        "same_terminal_candidate": (
            ia4_receipt["terminal_decision"]["candidate_id"] ==
            ia3_receipt["terminal_decision"]["candidate_id"]
        ),
        "both_pass_common_plan_validator": (
            ia4_validation["accepted"] is True and
            ia3_validation["accepted"] is True
        ),
    }
    if not all(parity.values()):
        raise ContractViolation("M5 matched-control fixture lost parity")
    return {
        "schema_version": M5_CONTRACT_ARTIFACT_SCHEMA_VERSION,
        "project_id": "prj_01KYMPK10PE9YH1TJ84PAVB9Z6",
        "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        "spec_file_sha256": spec_file_sha256,
        "scope": "offline_fixture_protocol_only",
        "development_only": True,
        "campaign_authorized": False,
        "evaluation_sealed": True,
        "model_transport_used": False,
        "tool_execution_used": False,
        "simulator_accessed": False,
        "detector_accessed": False,
        "embedding_accessed": False,
        "status": "passed",
        "protocol": protocol.to_dict(),
        "episodes": {
            "ia4_fixture": {
                "receipt": ia4_receipt,
                "plan_validation": ia4_validation,
            },
            "ia3_matched_control": {
                "receipt": ia3_receipt,
                "plan_validation": ia3_validation,
            },
        },
        "parity_assertions": parity,
        "limitations": [
            "The IA4 episode uses fixture decisions and is not model evidence.",
            "The tool result is injected from a content-addressed fixture; no tool ran.",
            "Actual IA3 versus IA4 model-compute matching remains a later gate.",
            "No strategy-quality, grid-harm, detector, or campaign claim is supported.",
        ],
    }
