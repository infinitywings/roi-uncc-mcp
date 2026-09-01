"""Offline M10 admission contract for CAREER resources S and M.

Synthetic fixtures exercise structural admission logic only.  They cannot
admit a real process-relationship or predictive-ranking resource, and this
module has no external-service or runtime integration surface.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_stealth_contract import (
    FROZEN_EXPERIMENT_SPEC_SHA256,
    FROZEN_ROADMAP_REPORT_SHA256,
    GOVERNING_DRAFT_SHA256,
)
from .career_two_interval import M8_CONTRACT_ID
from .orchestration_contract import ContractViolation


RESOURCE_ADMISSION_SCHEMA_VERSION = "grideval-career-resource-admission/v1"
RESOURCE_ENVELOPE_SCHEMA_VERSION = "grideval-career-resource-envelope/v1"
ADMISSION_RECEIPT_SCHEMA_VERSION = "grideval-career-admission-receipt/v1"
FIXTURE_MATRIX_SCHEMA_VERSION = "grideval-career-admission-fixtures/v1"

M9_CONTRACT_ID = (
    "careertwoint_6d57736587a6a6ad2474392a0413b784fa9633ecfa94af572798b7419b1e73a5"
)
M9_PARITY_FINGERPRINT = (
    "sha256_6776210404947b827931f192f6c3a60edf58e91c586f53440287a147aaa9f671"
)
M9_CANDIDATE_LIBRARY_FINGERPRINT = (
    "sha256_0932044cd25b3c6e77e33086282246f82b67085286f90569cc1db04c3d584aec"
)
M10_DESIGN_DECISION_ID = "dec_01M1DKWNJPFEM5FZDSGMAMS9GB"

REAL_RESOURCE_HOLD = (
    "HOLD_PENDING_PREREGISTERED_THRESHOLDS_AND_INDEPENDENT_EVIDENCE"
)
POSITIVE_VERDICT = "PASS_SYNTHETIC_STRUCTURE_ONLY"
NEGATIVE_VERDICT = "REJECTED_FAIL_CLOSED"

REQUIRED_PARITY_ASSERTIONS = {
    "raw_observation_interface_unchanged": True,
    "action_authority_unchanged": True,
    "candidate_library_unchanged": True,
    "budget_unchanged": True,
    "revision_permission_unchanged": True,
    "safety_shield_unchanged": True,
    "confirmation_rule_unchanged": True,
    "evaluation_partition_sealed": True,
}

REQUIRED_EXTERNAL_ACCESS = {
    "model_calls": 0,
    "real_tool_calls": 0,
    "simulator_calls": 0,
    "detector_calls": 0,
    "embedding_calls": 0,
    "actuator_calls": 0,
    "evaluation_records_read": 0,
}


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
    return _content_id("careerresource", payload, omit=("contract_id",))


def envelope_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("resourceenv", payload, omit=("envelope_id",))


def receipt_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m10receipt", payload, omit=("receipt_id",))


def matrix_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m10matrix", payload, omit=("matrix_id",))


@dataclass(frozen=True)
class CareerResourceAdmissionContract:
    """Immutable semantic representation of the M10 admission contract."""

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
            "parity_anchor",
            "shared_admission_rules",
            "resource_profiles",
            "state_machine",
            "canonical_real_resource_status",
            "synthetic_fixture_gate",
            "limitations",
            "next_gate",
        }
        if set(content) != expected_fields:
            raise ContractViolation("M10 contract top-level fields drift")
        if content["schema_version"] != RESOURCE_ADMISSION_SCHEMA_VERSION:
            raise ContractViolation("unsupported M10 contract schema_version")
        if content["milestone"] != "M10":
            raise ContractViolation("resource admission must be milestone M10")
        if content["contract_id"] != contract_id_for(content):
            raise ContractViolation("M10 contract_id mismatch")

        required_governance = {
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
            "real_resource_admission_authorized": False,
        }
        if content["governance"] != required_governance:
            raise ContractViolation("M10 governance boundary drift")

        required_lineage = {
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "m8_contract_id": M8_CONTRACT_ID,
            "m9_contract_id": M9_CONTRACT_ID,
            "m10_design_decision": M10_DESIGN_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        }
        if content["source_lineage"] != required_lineage:
            raise ContractViolation("M10 source lineage drift")

        required_anchor = {
            "m9_contract_id": M9_CONTRACT_ID,
            "m9_parity_fingerprint": M9_PARITY_FINGERPRINT,
            "candidate_library_fingerprint": (
                M9_CANDIDATE_LIBRARY_FINGERPRINT
            ),
            "held_fixed_across_S_and_M": sorted({
                "raw_observation_interface",
                "action_authority",
                "candidate_library",
                "budgets",
                "revision_permission",
                "safety_shield",
                "confirmation_rule",
                "evaluation_partition",
            }),
        }
        if content["parity_anchor"] != required_anchor:
            raise ContractViolation("M10 M9 parity anchor drift")

        rules = content["shared_admission_rules"]
        required_rules = {
            "thresholds_frozen_before_validation_evidence": True,
            "resource_derivation_and_validation_partitions_disjoint": True,
            "validation_and_A_confirmation_partitions_disjoint": True,
            "treatment_outcomes_may_select_thresholds": False,
            "evaluation_records_may_be_read": False,
            "resource_update_policy": "frozen_read_only",
            "automatic_real_resource_admission": False,
            "failed_resource_policy": "reduce_factorial_prospectively",
            "metric_profile_substitution": "prohibited",
            "synthetic_fixture_role": "validator_structure_only",
        }
        if rules != required_rules:
            raise ContractViolation("M10 shared admission rules drift")

        profiles = content["resource_profiles"]
        if set(profiles) != {"S", "M"}:
            raise ContractViolation("M10 requires separate S and M profiles")
        _validate_profile(
            profiles["S"],
            factor="S",
            resource_type="validated_process_relationships",
            payload_schema="process_relationship_resource/v1",
            metrics={
                "directional_response_agreement",
                "normalized_response_error",
                "operating_envelope_coverage",
            },
            evidence_role="independent_held_out_action_validity",
        )
        _validate_profile(
            profiles["M"],
            factor="M",
            resource_type="validated_predictive_candidate_ranking",
            payload_schema="candidate_ranking_resource/v1",
            metrics={
                "pairwise_order_accuracy",
                "top_k_candidate_recall",
                "normalized_simple_regret",
            },
            evidence_role="independent_held_out_candidate_ranking",
        )
        if profiles["S"]["allowed_information"] == (
                profiles["M"]["allowed_information"]):
            raise ContractViolation("S and M information grants were collapsed")

        states = content["state_machine"]
        if states != {
            "states": [
                "draft",
                "thresholds_frozen",
                "evidence_attached",
                "eligible_for_independent_review",
                "rejected_fail_closed",
            ],
            "synthetic_terminal_state": "eligible_for_independent_review",
            "real_admission_terminal_state_present": False,
            "invalid_transition_policy": "rejected_fail_closed_no_retry",
        }:
            raise ContractViolation("M10 admission state machine drift")

        status = content["canonical_real_resource_status"]
        if status != {"S": REAL_RESOURCE_HOLD, "M": REAL_RESOURCE_HOLD}:
            raise ContractViolation("M10 real-resource HOLD status drift")

        gate = content["synthetic_fixture_gate"]
        required_checks = {
            "S_positive_structure_passes",
            "M_positive_structure_passes",
            "partition_overlap_rejected",
            "post_evidence_threshold_freeze_rejected",
            "parity_expansion_rejected",
            "candidate_library_drift_rejected",
            "online_update_rejected",
            "treatment_outcome_leak_rejected",
            "real_resource_status_remains_hold",
            "all_external_access_zero",
            "all_receipts_content_addressed",
        }
        if set(gate.get("required_checks", ())) != required_checks:
            raise ContractViolation("M10 synthetic fixture checks drift")
        if gate.get("passing_interpretation") != (
                "admission_validator_structure_only"):
            raise ContractViolation("M10 fixture interpretation drift")

        required_limitations = {
            "no_real_S_resource_validated_or_admitted",
            "no_real_M_resource_validated_or_admitted",
            "no_scientific_threshold_selected",
            "no_physical_or_ranking_performance_claim",
            "no_A_factor_outcome_claim",
            "no_llm_or_tool_use_claim",
            "no_runtime_or_campaign_authorization",
        }
        if set(content["limitations"]) != required_limitations:
            raise ContractViolation("M10 limitations drift")
        if content["next_gate"] != {
            "id": "M11_development_only_threshold_preregistration",
            "scope": "source_lineage_and_metric_threshold_plan_only",
            "requires_independent_review": True,
            "model_call": False,
            "real_tool_execution": False,
            "simulator_or_detector_access": False,
        }:
            raise ContractViolation("unexpected M10 next gate")


def _validate_profile(
    profile: Mapping[str, Any],
    *,
    factor: str,
    resource_type: str,
    payload_schema: str,
    metrics: set[str],
    evidence_role: str,
) -> None:
    expected_fields = {
        "factor",
        "resource_type",
        "payload_schema",
        "allowed_information",
        "forbidden_information",
        "validation_evidence_role",
        "required_metrics",
        "threshold_status",
        "resource_behavior",
    }
    if set(profile) != expected_fields:
        raise ContractViolation(f"M10 {factor} profile fields drift")
    if profile["factor"] != factor:
        raise ContractViolation(f"M10 {factor} factor label drift")
    if profile["resource_type"] != resource_type:
        raise ContractViolation(f"M10 {factor} resource type drift")
    if profile["payload_schema"] != payload_schema:
        raise ContractViolation(f"M10 {factor} payload schema drift")
    if set(profile["required_metrics"]) != metrics:
        raise ContractViolation(f"M10 {factor} metric profile drift")
    if profile["validation_evidence_role"] != evidence_role:
        raise ContractViolation(f"M10 {factor} evidence role drift")
    if profile["threshold_status"] != (
            "uninstantiated_pending_development_preregistration"):
        raise ContractViolation(f"M10 {factor} threshold status drift")
    if profile["resource_behavior"] != "frozen_read_only_no_online_update":
        raise ContractViolation(f"M10 {factor} behavior drift")
    if not profile["allowed_information"]:
        raise ContractViolation(f"M10 {factor} allowed information is empty")
    required_forbidden = {
        "evaluation_outcomes",
        "A_treatment_outcomes",
        "detector_scores",
        "new_raw_observations",
        "new_action_authority",
        "online_updates",
    }
    if set(profile["forbidden_information"]) != required_forbidden:
        raise ContractViolation(f"M10 {factor} forbidden information drift")


def _violation_codes(
    contract: CareerResourceAdmissionContract,
    envelope: Mapping[str, Any],
) -> list[str]:
    """Return deterministic fail-closed reason codes for one envelope."""

    codes: set[str] = set()
    expected_fields = {
        "schema_version",
        "envelope_id",
        "contract_id",
        "fixture_id",
        "factor",
        "synthetic_fixture",
        "resource_manifest",
        "validation_protocol",
        "validation_evidence",
        "parity_assertion",
        "external_access",
    }
    if set(envelope) != expected_fields:
        return ["envelope_fields_drift"]
    if envelope.get("schema_version") != RESOURCE_ENVELOPE_SCHEMA_VERSION:
        codes.add("envelope_schema_drift")
    if envelope.get("envelope_id") != envelope_id_for(envelope):
        codes.add("envelope_content_address_mismatch")
    if envelope.get("contract_id") != contract.contract_id:
        codes.add("contract_lineage_mismatch")
    factor = envelope.get("factor")
    profiles = contract.to_dict()["resource_profiles"]
    if factor not in profiles:
        return sorted(codes | {"unknown_factor"})
    if envelope.get("synthetic_fixture") is not True:
        codes.add("real_resource_not_authorized")

    profile = profiles[factor]
    manifest_value = envelope.get("resource_manifest", {})
    if not isinstance(manifest_value, dict):
        codes.add("resource_manifest_fields_drift")
        manifest: dict[str, Any] = {}
    else:
        manifest = manifest_value
    required_manifest = {
        "resource_id",
        "resource_type",
        "payload_schema",
        "derivation_partition_id",
        "update_policy",
        "information_grant",
        "candidate_library_fingerprint",
        "contains_executable_actions",
    }
    if set(manifest) != required_manifest:
        codes.add("resource_manifest_fields_drift")
    else:
        if not isinstance(manifest["resource_id"], str) or not manifest[
                "resource_id"].strip():
            codes.add("resource_identifier_invalid")
        if manifest["resource_type"] != profile["resource_type"]:
            codes.add("resource_type_mismatch")
        if manifest["payload_schema"] != profile["payload_schema"]:
            codes.add("payload_schema_mismatch")
        if manifest["update_policy"] != "frozen_read_only":
            codes.add("online_update_or_mutation_enabled")
        grant = manifest["information_grant"]
        if (
            not isinstance(grant, list)
            or not all(isinstance(item, str) for item in grant)
            or set(grant) != set(profile["allowed_information"])
        ):
            codes.add("information_grant_drift")
        if manifest["candidate_library_fingerprint"] != (
                M9_CANDIDATE_LIBRARY_FINGERPRINT):
            codes.add("candidate_library_drift")
        if manifest["contains_executable_actions"] is not False:
            codes.add("executable_action_payload_forbidden")

    protocol_value = envelope.get("validation_protocol", {})
    if not isinstance(protocol_value, dict):
        codes.add("validation_protocol_fields_drift")
        protocol: dict[str, Any] = {}
    else:
        protocol = protocol_value
    required_protocol = {
        "evidence_role",
        "validation_partition_id",
        "disjoint_from_partition_ids",
        "threshold_basis",
        "threshold_freeze_sequence",
        "metric_thresholds",
    }
    if set(protocol) != required_protocol:
        codes.add("validation_protocol_fields_drift")
    evidence_value = envelope.get("validation_evidence", {})
    if not isinstance(evidence_value, dict):
        codes.add("validation_evidence_fields_drift")
        evidence: dict[str, Any] = {}
    else:
        evidence = evidence_value
    required_evidence = {
        "source",
        "validation_partition_id",
        "evidence_sequence",
        "treatment_outcomes_accessed",
        "evaluation_records_accessed",
        "metric_observations",
    }
    if set(evidence) != required_evidence:
        codes.add("validation_evidence_fields_drift")

    if set(protocol) == required_protocol and set(evidence) == required_evidence:
        if protocol["evidence_role"] != profile["validation_evidence_role"]:
            codes.add("evidence_role_substitution")
        validation_partition = protocol["validation_partition_id"]
        if evidence["validation_partition_id"] != validation_partition:
            codes.add("validation_partition_lineage_mismatch")
        disjoint_value = protocol["disjoint_from_partition_ids"]
        if (
            isinstance(disjoint_value, list)
            and all(isinstance(item, str) for item in disjoint_value)
        ):
            disjoint = set(disjoint_value)
        else:
            disjoint = set()
            codes.add("validation_partition_set_invalid")
        derivation = manifest.get("derivation_partition_id")
        if (
            validation_partition == derivation
            or derivation not in disjoint
            or "A_confirmation_partition" not in disjoint
        ):
            codes.add("validation_partition_not_independent")
        if protocol["threshold_basis"] != (
                "synthetic_fixture_only_not_scientific_threshold"):
            codes.add("threshold_basis_overclaim")
        freeze_sequence = protocol["threshold_freeze_sequence"]
        evidence_sequence = evidence["evidence_sequence"]
        if (
            isinstance(freeze_sequence, bool)
            or isinstance(evidence_sequence, bool)
            or not isinstance(freeze_sequence, int)
            or not isinstance(evidence_sequence, int)
        ):
            codes.add("threshold_or_evidence_sequence_invalid")
        elif freeze_sequence >= evidence_sequence:
            codes.add("threshold_not_frozen_before_evidence")
        if evidence["treatment_outcomes_accessed"] is not False:
            codes.add("treatment_outcome_leak")
        if evidence["evaluation_records_accessed"] is not False:
            codes.add("evaluation_partition_leak")
        codes.update(_metric_violations(profile, protocol, evidence))

    parity_value = envelope.get("parity_assertion", {})
    if not isinstance(parity_value, dict):
        codes.add("parity_assertion_fields_drift")
        parity: dict[str, Any] = {}
    else:
        parity = parity_value
    required_parity_fields = {
        "m9_contract_id",
        "m9_parity_fingerprint",
        "candidate_library_fingerprint",
        "assertions",
    }
    if set(parity) != required_parity_fields:
        codes.add("parity_assertion_fields_drift")
    else:
        if parity["m9_contract_id"] != M9_CONTRACT_ID:
            codes.add("m9_contract_anchor_drift")
        if parity["m9_parity_fingerprint"] != M9_PARITY_FINGERPRINT:
            codes.add("m9_parity_anchor_drift")
        if parity["candidate_library_fingerprint"] != (
                M9_CANDIDATE_LIBRARY_FINGERPRINT):
            codes.add("candidate_library_drift")
        if parity["assertions"] != REQUIRED_PARITY_ASSERTIONS:
            codes.add("parity_expansion_or_drift")

    if envelope.get("external_access") != REQUIRED_EXTERNAL_ACCESS:
        codes.add("external_access_or_accounting_drift")
    return sorted(codes)


def _metric_violations(
    profile: Mapping[str, Any],
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> set[str]:
    codes: set[str] = set()
    thresholds = protocol["metric_thresholds"]
    observations = evidence["metric_observations"]
    required = set(profile["required_metrics"])
    if not isinstance(thresholds, dict) or not isinstance(observations, dict):
        return {"metric_profile_incomplete_or_substituted"}
    if set(thresholds) != required or set(observations) != required:
        return {"metric_profile_incomplete_or_substituted"}
    for metric_id in required:
        threshold = thresholds[metric_id]
        observation = observations[metric_id]
        if not isinstance(threshold, dict) or set(threshold) != {
                "direction", "value"}:
            codes.add("metric_threshold_fields_drift")
            continue
        if not isinstance(observation, dict) or set(observation) != {
                "value", "synthetic"}:
            codes.add("metric_observation_fields_drift")
            continue
        if observation["synthetic"] is not True:
            codes.add("fixture_metric_not_declared_synthetic")
        threshold_value = threshold["value"]
        observed_value = observation["value"]
        if (
            isinstance(threshold_value, bool)
            or isinstance(observed_value, bool)
            or not isinstance(threshold_value, (int, float))
            or not isinstance(observed_value, (int, float))
            or not math.isfinite(float(threshold_value))
            or not math.isfinite(float(observed_value))
        ):
            codes.add("metric_value_invalid")
            continue
        direction = threshold["direction"]
        if direction == "at_least":
            passed = float(observed_value) >= float(threshold_value)
        elif direction == "at_most":
            passed = float(observed_value) <= float(threshold_value)
        else:
            codes.add("metric_direction_invalid")
            continue
        if not passed:
            codes.add(f"metric_failed:{metric_id}")
    return codes


def evaluate_resource_admission(
    contract: CareerResourceAdmissionContract,
    envelope: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one synthetic envelope and return a content-addressed receipt."""

    copied = json.loads(_canonical_json(envelope))
    reasons = _violation_codes(contract, copied)
    accepted = not reasons
    payload: dict[str, Any] = {
        "schema_version": ADMISSION_RECEIPT_SCHEMA_VERSION,
        "receipt_id": "pending",
        "contract_id": contract.contract_id,
        "fixture_id": copied.get("fixture_id", "missing_fixture_id"),
        "envelope_id": copied.get("envelope_id", "missing_envelope_id"),
        "factor": copied.get("factor", "unknown"),
        "accepted": accepted,
        "verdict": POSITIVE_VERDICT if accepted else NEGATIVE_VERDICT,
        "reason_codes": reasons,
        "real_resource_status_after": REAL_RESOURCE_HOLD,
        "external_access": dict(REQUIRED_EXTERNAL_ACCESS),
        "interpretation": "admission_validator_structure_only",
    }
    payload["receipt_id"] = receipt_id_for(payload)
    return payload


def _profile(
    *,
    factor: str,
    resource_type: str,
    payload_schema: str,
    allowed_information: set[str],
    evidence_role: str,
    metrics: set[str],
) -> dict[str, Any]:
    return {
        "factor": factor,
        "resource_type": resource_type,
        "payload_schema": payload_schema,
        "allowed_information": sorted(allowed_information),
        "forbidden_information": sorted({
            "evaluation_outcomes",
            "A_treatment_outcomes",
            "detector_scores",
            "new_raw_observations",
            "new_action_authority",
            "online_updates",
        }),
        "validation_evidence_role": evidence_role,
        "required_metrics": sorted(metrics),
        "threshold_status": (
            "uninstantiated_pending_development_preregistration"
        ),
        "resource_behavior": "frozen_read_only_no_online_update",
    }


def build_career_resource_admission_contract(
) -> CareerResourceAdmissionContract:
    """Build the canonical M10 S/M admission contract."""

    governance = {
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
        "real_resource_admission_authorized": False,
    }
    content: dict[str, Any] = {
        "schema_version": RESOURCE_ADMISSION_SCHEMA_VERSION,
        "contract_id": "pending",
        "milestone": "M10",
        "title": "Offline CAREER S and M independent resource admission",
        "governance": governance,
        "source_lineage": {
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "m8_contract_id": M8_CONTRACT_ID,
            "m9_contract_id": M9_CONTRACT_ID,
            "m10_design_decision": M10_DESIGN_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        },
        "parity_anchor": {
            "m9_contract_id": M9_CONTRACT_ID,
            "m9_parity_fingerprint": M9_PARITY_FINGERPRINT,
            "candidate_library_fingerprint": (
                M9_CANDIDATE_LIBRARY_FINGERPRINT
            ),
            "held_fixed_across_S_and_M": sorted({
                "raw_observation_interface",
                "action_authority",
                "candidate_library",
                "budgets",
                "revision_permission",
                "safety_shield",
                "confirmation_rule",
                "evaluation_partition",
            }),
        },
        "shared_admission_rules": {
            "thresholds_frozen_before_validation_evidence": True,
            "resource_derivation_and_validation_partitions_disjoint": True,
            "validation_and_A_confirmation_partitions_disjoint": True,
            "treatment_outcomes_may_select_thresholds": False,
            "evaluation_records_may_be_read": False,
            "resource_update_policy": "frozen_read_only",
            "automatic_real_resource_admission": False,
            "failed_resource_policy": "reduce_factorial_prospectively",
            "metric_profile_substitution": "prohibited",
            "synthetic_fixture_role": "validator_structure_only",
        },
        "resource_profiles": {
            "S": _profile(
                factor="S",
                resource_type="validated_process_relationships",
                payload_schema="process_relationship_resource/v1",
                allowed_information={
                    "relationship_identifier",
                    "action_family",
                    "qualitative_response_direction",
                    "operating_envelope_reference",
                },
                evidence_role="independent_held_out_action_validity",
                metrics={
                    "directional_response_agreement",
                    "normalized_response_error",
                    "operating_envelope_coverage",
                },
            ),
            "M": _profile(
                factor="M",
                resource_type="validated_predictive_candidate_ranking",
                payload_schema="candidate_ranking_resource/v1",
                allowed_information={
                    "candidate_identifier",
                    "read_only_predicted_score",
                    "read_only_rank",
                    "model_version_identifier",
                },
                evidence_role="independent_held_out_candidate_ranking",
                metrics={
                    "pairwise_order_accuracy",
                    "top_k_candidate_recall",
                    "normalized_simple_regret",
                },
            ),
        },
        "state_machine": {
            "states": [
                "draft",
                "thresholds_frozen",
                "evidence_attached",
                "eligible_for_independent_review",
                "rejected_fail_closed",
            ],
            "synthetic_terminal_state": "eligible_for_independent_review",
            "real_admission_terminal_state_present": False,
            "invalid_transition_policy": "rejected_fail_closed_no_retry",
        },
        "canonical_real_resource_status": {
            "S": REAL_RESOURCE_HOLD,
            "M": REAL_RESOURCE_HOLD,
        },
        "synthetic_fixture_gate": {
            "required_checks": sorted({
                "S_positive_structure_passes",
                "M_positive_structure_passes",
                "partition_overlap_rejected",
                "post_evidence_threshold_freeze_rejected",
                "parity_expansion_rejected",
                "candidate_library_drift_rejected",
                "online_update_rejected",
                "treatment_outcome_leak_rejected",
                "real_resource_status_remains_hold",
                "all_external_access_zero",
                "all_receipts_content_addressed",
            }),
            "passing_interpretation": "admission_validator_structure_only",
        },
        "limitations": sorted({
            "no_real_S_resource_validated_or_admitted",
            "no_real_M_resource_validated_or_admitted",
            "no_scientific_threshold_selected",
            "no_physical_or_ranking_performance_claim",
            "no_A_factor_outcome_claim",
            "no_llm_or_tool_use_claim",
            "no_runtime_or_campaign_authorization",
        }),
        "next_gate": {
            "id": "M11_development_only_threshold_preregistration",
            "scope": "source_lineage_and_metric_threshold_plan_only",
            "requires_independent_review": True,
            "model_call": False,
            "real_tool_execution": False,
            "simulator_or_detector_access": False,
        },
    }
    content["contract_id"] = contract_id_for(content)
    return CareerResourceAdmissionContract(content)


def _base_envelope(
    contract: CareerResourceAdmissionContract,
    *,
    factor: str,
    fixture_id: str,
) -> dict[str, Any]:
    profile = contract.to_dict()["resource_profiles"][factor]
    if factor == "S":
        threshold_specs = {
            "directional_response_agreement": {
                "direction": "at_least", "value": 0.80},
            "normalized_response_error": {
                "direction": "at_most", "value": 0.20},
            "operating_envelope_coverage": {
                "direction": "at_least", "value": 0.80},
        }
        metric_values = {
            "directional_response_agreement": 0.90,
            "normalized_response_error": 0.10,
            "operating_envelope_coverage": 0.90,
        }
    else:
        threshold_specs = {
            "pairwise_order_accuracy": {
                "direction": "at_least", "value": 0.75},
            "top_k_candidate_recall": {
                "direction": "at_least", "value": 0.75},
            "normalized_simple_regret": {
                "direction": "at_most", "value": 0.25},
        }
        metric_values = {
            "pairwise_order_accuracy": 0.85,
            "top_k_candidate_recall": 0.85,
            "normalized_simple_regret": 0.15,
        }
    derivation_partition = f"synthetic_{factor}_resource_derivation"
    validation_partition = f"synthetic_{factor}_independent_validation"
    payload: dict[str, Any] = {
        "schema_version": RESOURCE_ENVELOPE_SCHEMA_VERSION,
        "envelope_id": "pending",
        "contract_id": contract.contract_id,
        "fixture_id": fixture_id,
        "factor": factor,
        "synthetic_fixture": True,
        "resource_manifest": {
            "resource_id": f"synthetic_{factor}_structure_only",
            "resource_type": profile["resource_type"],
            "payload_schema": profile["payload_schema"],
            "derivation_partition_id": derivation_partition,
            "update_policy": "frozen_read_only",
            "information_grant": profile["allowed_information"],
            "candidate_library_fingerprint": (
                M9_CANDIDATE_LIBRARY_FINGERPRINT
            ),
            "contains_executable_actions": False,
        },
        "validation_protocol": {
            "evidence_role": profile["validation_evidence_role"],
            "validation_partition_id": validation_partition,
            "disjoint_from_partition_ids": [
                derivation_partition,
                "A_confirmation_partition",
            ],
            "threshold_basis": (
                "synthetic_fixture_only_not_scientific_threshold"
            ),
            "threshold_freeze_sequence": 1,
            "metric_thresholds": threshold_specs,
        },
        "validation_evidence": {
            "source": "synthetic_structural_fixture",
            "validation_partition_id": validation_partition,
            "evidence_sequence": 2,
            "treatment_outcomes_accessed": False,
            "evaluation_records_accessed": False,
            "metric_observations": {
                key: {"value": value, "synthetic": True}
                for key, value in metric_values.items()
            },
        },
        "parity_assertion": {
            "m9_contract_id": M9_CONTRACT_ID,
            "m9_parity_fingerprint": M9_PARITY_FINGERPRINT,
            "candidate_library_fingerprint": (
                M9_CANDIDATE_LIBRARY_FINGERPRINT
            ),
            "assertions": dict(REQUIRED_PARITY_ASSERTIONS),
        },
        "external_access": dict(REQUIRED_EXTERNAL_ACCESS),
    }
    payload["envelope_id"] = envelope_id_for(payload)
    return payload


def _mutated_envelope(
    envelope: Mapping[str, Any],
    *,
    fixture_id: str,
    mutation: str,
) -> dict[str, Any]:
    payload = json.loads(_canonical_json(envelope))
    payload["fixture_id"] = fixture_id
    if mutation == "partition_overlap":
        payload["validation_protocol"]["validation_partition_id"] = (
            payload["resource_manifest"]["derivation_partition_id"]
        )
        payload["validation_evidence"]["validation_partition_id"] = (
            payload["resource_manifest"]["derivation_partition_id"]
        )
    elif mutation == "post_evidence_threshold_freeze":
        payload["validation_protocol"]["threshold_freeze_sequence"] = 3
    elif mutation == "parity_expansion":
        payload["parity_assertion"]["assertions"][
            "raw_observation_interface_unchanged"] = False
    elif mutation == "candidate_library_drift":
        drift = "sha256_" + "0" * 64
        payload["resource_manifest"]["candidate_library_fingerprint"] = drift
        payload["parity_assertion"]["candidate_library_fingerprint"] = drift
    elif mutation == "online_update":
        payload["resource_manifest"]["update_policy"] = "online_update"
    elif mutation == "treatment_outcome_leak":
        payload["validation_evidence"]["treatment_outcomes_accessed"] = True
    else:
        raise ValueError(f"unknown M10 synthetic mutation: {mutation}")
    payload["envelope_id"] = envelope_id_for(payload)
    return payload


def build_synthetic_fixture_matrix(
    contract: CareerResourceAdmissionContract,
) -> dict[str, Any]:
    """Exercise positive and negative structural fixtures for both profiles."""

    s_positive = _base_envelope(
        contract, factor="S", fixture_id="S_positive_structure"
    )
    m_positive = _base_envelope(
        contract, factor="M", fixture_id="M_positive_structure"
    )
    envelopes = [
        s_positive,
        m_positive,
        _mutated_envelope(
            s_positive,
            fixture_id="S_partition_overlap",
            mutation="partition_overlap",
        ),
        _mutated_envelope(
            m_positive,
            fixture_id="M_post_evidence_threshold_freeze",
            mutation="post_evidence_threshold_freeze",
        ),
        _mutated_envelope(
            s_positive,
            fixture_id="S_parity_expansion",
            mutation="parity_expansion",
        ),
        _mutated_envelope(
            m_positive,
            fixture_id="M_candidate_library_drift",
            mutation="candidate_library_drift",
        ),
        _mutated_envelope(
            m_positive,
            fixture_id="M_online_update",
            mutation="online_update",
        ),
        _mutated_envelope(
            s_positive,
            fixture_id="S_treatment_outcome_leak",
            mutation="treatment_outcome_leak",
        ),
    ]
    receipts = [
        evaluate_resource_admission(contract, envelope)
        for envelope in envelopes
    ]
    by_fixture = {item["fixture_id"]: item for item in receipts}
    checks = {
        "S_positive_structure_passes": (
            by_fixture["S_positive_structure"]["verdict"] == POSITIVE_VERDICT
        ),
        "M_positive_structure_passes": (
            by_fixture["M_positive_structure"]["verdict"] == POSITIVE_VERDICT
        ),
        "partition_overlap_rejected": (
            "validation_partition_not_independent"
            in by_fixture["S_partition_overlap"]["reason_codes"]
        ),
        "post_evidence_threshold_freeze_rejected": (
            "threshold_not_frozen_before_evidence"
            in by_fixture["M_post_evidence_threshold_freeze"]["reason_codes"]
        ),
        "parity_expansion_rejected": (
            "parity_expansion_or_drift"
            in by_fixture["S_parity_expansion"]["reason_codes"]
        ),
        "candidate_library_drift_rejected": (
            "candidate_library_drift"
            in by_fixture["M_candidate_library_drift"]["reason_codes"]
        ),
        "online_update_rejected": (
            "online_update_or_mutation_enabled"
            in by_fixture["M_online_update"]["reason_codes"]
        ),
        "treatment_outcome_leak_rejected": (
            "treatment_outcome_leak"
            in by_fixture["S_treatment_outcome_leak"]["reason_codes"]
        ),
        "real_resource_status_remains_hold": all(
            item["real_resource_status_after"] == REAL_RESOURCE_HOLD
            for item in receipts
        ),
        "all_external_access_zero": all(
            item["external_access"] == REQUIRED_EXTERNAL_ACCESS
            for item in receipts
        ),
        "all_receipts_content_addressed": all(
            item["receipt_id"] == receipt_id_for(item) for item in receipts
        ),
    }
    preregistered = set(
        contract.to_dict()["synthetic_fixture_gate"]["required_checks"]
    )
    if set(checks) != preregistered:
        raise ContractViolation("M10 computed checks do not match preregistration")
    if not all(checks.values()):
        failed = sorted(key for key, value in checks.items() if not value)
        raise ContractViolation(f"M10 synthetic fixture matrix failed: {failed}")
    payload: dict[str, Any] = {
        "schema_version": FIXTURE_MATRIX_SCHEMA_VERSION,
        "matrix_id": "pending",
        "contract_id": contract.contract_id,
        "envelopes": envelopes,
        "receipts": receipts,
        "checks": checks,
        "verdict": "PASS_ADMISSION_VALIDATOR_STRUCTURE_ONLY",
        "canonical_real_resource_status": {
            "S": REAL_RESOURCE_HOLD,
            "M": REAL_RESOURCE_HOLD,
        },
    }
    payload["matrix_id"] = matrix_id_for(payload)
    return payload


def build_m10_artifact() -> dict[str, Any]:
    """Build the canonical M10 contract and synthetic validation matrix."""

    contract = build_career_resource_admission_contract()
    return {
        "contract": contract.to_dict(),
        "synthetic_fixture_evidence": build_synthetic_fixture_matrix(contract),
    }


def load_m10_artifact(path: str | Path) -> dict[str, Any]:
    """Load and semantically rebuild a checked-in M10 artifact."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(payload) != {"contract", "synthetic_fixture_evidence"}:
        raise ContractViolation("M10 artifact fields drift")
    contract = CareerResourceAdmissionContract(payload["contract"])
    expected = build_synthetic_fixture_matrix(contract)
    if payload["synthetic_fixture_evidence"] != expected:
        raise ContractViolation("M10 synthetic fixture evidence mismatch")
    return payload
