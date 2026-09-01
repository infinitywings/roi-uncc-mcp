"""M12 clean-source freeze design for the CAREER S and M resources.

This module specifies source-package, partition, and review requirements. It
does not generate a real source, assign a data block, issue a review receipt,
select a threshold, or expose any runtime or external-service path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_resource_admission import (
    M9_CANDIDATE_LIBRARY_FINGERPRINT,
    M9_CONTRACT_ID,
    M9_PARITY_FINGERPRINT,
    REAL_RESOURCE_HOLD,
)
from .career_stealth_contract import (
    FROZEN_EXPERIMENT_SPEC_SHA256,
    FROZEN_ROADMAP_REPORT_SHA256,
    GOVERNING_DRAFT_SHA256,
)
from .career_threshold_hold import THRESHOLD_STATUS
from .orchestration_contract import ContractViolation


SOURCE_FREEZE_DESIGN_SCHEMA_VERSION = "grideval-career-source-freeze-design/v1"
M11_CONTRACT_ID = (
    "careerthresholdhold_4ff524e10e76cc36a68aec92ac6fcddda99802cf0699e419"
    "f930ad1f03588468"
)
M12_DECISION_ID = "dec_01M1DN5GNS59V8GEP19E08T4PW"
M12_STATUS = "DESIGN_ONLY_SOURCE_PREREQUISITES_SPECIFIED"
PROFILE_STATUS = "UNINSTANTIATED_DESIGN_ONLY"
PARTITION_STATUS = "UNASSIGNED_DESIGN_ONLY"
REVIEW_STATUS = "UNISSUED_DESIGN_ONLY"

M9_CANDIDATE_IDS = (
    "fixtureplan_426a4d927d38c4798b99250d8383c60994a91a466bec21df3e22e15d4d973938",
    "fixtureplan_abaacb00f37f6a00d731bf09a8a71823f9036f04d2727001ef478d08de5b9c96",
    "fixtureplan_627b5c82da4d000905602be7bbd05b666c4521c7182e222b55d82129549ec7aa",
)

PARTITION_ROLES = (
    "S_source_derivation",
    "S_threshold_design",
    "S_independent_validation",
    "M_source_derivation",
    "M_threshold_design",
    "M_independent_validation",
    "ASM_factor_confirmation",
    "evaluation_sealed",
)

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
    "real_source_generation_authorized": False,
    "partition_assignment_authorized": False,
    "review_receipt_issuance_authorized": False,
    "scientific_threshold_freeze_authorized": False,
    "real_resource_admission_authorized": False,
}

COMMON_PROHIBITED_INPUTS = frozenset({
    "treatment_arm_outcomes",
    "detector_or_alarm_outcomes",
    "evaluation_records",
    "factor_confirmation_outcomes",
    "independent_validation_outcomes_during_derivation",
    "other_factor_derived_resource",
    "online_feedback_or_updates",
    "untracked_or_unhashed_source_bytes",
})


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
    """Return the content address for an M12 design payload."""

    return _content_id("careersourcefreeze", payload, omit=("contract_id",))


def _all_null(slots: Mapping[str, Any]) -> bool:
    return bool(slots) and all(value is None for value in slots.values())


@dataclass(frozen=True)
class CareerSourceFreezeDesign:
    """Immutable semantic representation of the M12 design contract."""

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
            "status",
            "governance",
            "source_lineage",
            "partition_registry",
            "clean_source_profiles",
            "review_protocol",
            "canonical_status",
            "limitations",
            "next_gate",
        }
        if set(content) != expected_fields:
            raise ContractViolation("M12 source-freeze top-level fields drift")
        if content["schema_version"] != SOURCE_FREEZE_DESIGN_SCHEMA_VERSION:
            raise ContractViolation("unsupported M12 source-freeze schema_version")
        if content["milestone"] != "M12":
            raise ContractViolation("source-freeze design must be milestone M12")
        if content["contract_id"] != contract_id_for(content):
            raise ContractViolation("M12 source-freeze contract_id mismatch")
        if content["status"] != M12_STATUS:
            raise ContractViolation("M12 design status drift")
        if content["governance"] != REQUIRED_GOVERNANCE:
            raise ContractViolation("M12 governance boundary drift")

        required_lineage = {
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "m9_contract_id": M9_CONTRACT_ID,
            "m9_parity_fingerprint": M9_PARITY_FINGERPRINT,
            "m9_candidate_library_fingerprint": (
                M9_CANDIDATE_LIBRARY_FINGERPRINT
            ),
            "m11_contract_id": M11_CONTRACT_ID,
            "m12_decision": M12_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        }
        if content["source_lineage"] != required_lineage:
            raise ContractViolation("M12 source lineage drift")

        _validate_partition_registry(content["partition_registry"])
        profiles = content["clean_source_profiles"]
        if set(profiles) != {"S", "M"}:
            raise ContractViolation("M12 requires separate S and M profiles")
        _validate_s_profile(profiles["S"])
        _validate_m_profile(profiles["M"])
        _validate_review_protocol(content["review_protocol"])

        expected_status = {
            "S_source_package": "UNBUILT_DESIGN_ONLY",
            "M_source_package": "UNBUILT_DESIGN_ONLY",
            "partition_assignments": PARTITION_STATUS,
            "review_receipts": REVIEW_STATUS,
            "S_scientific_threshold": THRESHOLD_STATUS,
            "M_scientific_threshold": THRESHOLD_STATUS,
            "S_real_resource": REAL_RESOURCE_HOLD,
            "M_real_resource": REAL_RESOURCE_HOLD,
            "evaluation": "SEALED",
            "campaign": "HOLD",
        }
        if content["canonical_status"] != expected_status:
            raise ContractViolation("M12 canonical status drift")

        required_limitations = {
            "no_real_source_or_partition_instantiated",
            "no_review_receipt_issued",
            "no_scientific_threshold_or_estimator_finalized",
            "no_real_resource_validated_or_admitted",
            "no_physical_ranking_or_factor_effect_claim",
            "no_model_embedding_tool_or_runtime_access",
            "no_evaluation_or_campaign_authorization",
        }
        if set(content["limitations"]) != required_limitations:
            raise ContractViolation("M12 limitations drift")

        if content["next_gate"] != {
            "id": "M13_offline_synthetic_source_manifest_validator",
            "scope": "synthetic_positive_and_negative_manifests_only",
            "may_freeze_real_sources": False,
            "may_assign_real_partitions": False,
            "may_issue_real_review_receipts": False,
            "may_select_scientific_thresholds": False,
            "model_or_embedding_call": False,
            "simulator_or_detector_access": False,
            "evaluation_access": False,
        }:
            raise ContractViolation("unexpected M12 next gate")


def _validate_partition_registry(registry: Mapping[str, Any]) -> None:
    expected_fields = {
        "status",
        "sample_identity",
        "roles",
        "assignments",
        "pairwise_disjoint_empirical_blocks",
        "cross_factor_empirical_block_reuse",
        "shared_static_inputs_allowed",
        "derived_resource_dependency",
        "assignment_freeze_order",
    }
    if set(registry) != expected_fields:
        raise ContractViolation("M12 partition-registry fields drift")
    if registry["status"] != PARTITION_STATUS:
        raise ContractViolation("M12 partition registry was instantiated")
    if registry["sample_identity"] != (
            "factor_role_run_seed_operating_cell_episode_block"):
        raise ContractViolation("M12 partition sample identity drift")
    roles = registry["roles"]
    if [item.get("id") for item in roles] != list(PARTITION_ROLES):
        raise ContractViolation("M12 partition role order or identity drift")
    expected_scopes = {
        "S_source_derivation": ("S", "derive_clean_source_only"),
        "S_threshold_design": ("S", "future_threshold_design_only"),
        "S_independent_validation": ("S", "future_action_validity_only"),
        "M_source_derivation": ("M", "derive_clean_source_only"),
        "M_threshold_design": ("M", "future_threshold_design_only"),
        "M_independent_validation": ("M", "future_ranking_validity_only"),
        "ASM_factor_confirmation": ("ASM", "future_factor_effect_only"),
        "evaluation_sealed": ("evaluation", "sealed_no_access"),
    }
    for item in roles:
        if set(item) != {"id", "factor_scope", "purpose", "status"}:
            raise ContractViolation("M12 partition-role fields drift")
        scope, purpose = expected_scopes[item["id"]]
        if item["factor_scope"] != scope or item["purpose"] != purpose:
            raise ContractViolation("M12 partition role semantics drift")
        if item["status"] != PARTITION_STATUS:
            raise ContractViolation("M12 partition role was assigned")
    if set(registry["assignments"]) != set(PARTITION_ROLES):
        raise ContractViolation("M12 partition assignment keys drift")
    if not _all_null(registry["assignments"]):
        raise ContractViolation("M12 cannot assign empirical partitions")
    if registry["pairwise_disjoint_empirical_blocks"] is not True:
        raise ContractViolation("M12 empirical partitions must be disjoint")
    if registry["cross_factor_empirical_block_reuse"] is not False:
        raise ContractViolation("M12 cross-factor block reuse must be disabled")
    if registry["shared_static_inputs_allowed"] != [
        "tracked_code_bytes",
        "frozen_environment_manifest",
        "frozen_feeder_configuration",
        "M9_protocol_and_candidate_definitions",
    ]:
        raise ContractViolation("M12 shared-static-input policy drift")
    if registry["derived_resource_dependency"] != (
            "S_and_M_must_not_depend_on_each_others_derived_resource"):
        raise ContractViolation("M12 S/M resource independence drift")
    if registry["assignment_freeze_order"] != [
        "freeze_sample_identity",
        "freeze_partition_role_registry",
        "assign_content_addressed_blocks_without_outcome_access",
        "verify_pairwise_disjointness",
        "independent_partition_review",
        "freeze_assignment_manifest_before_derivation",
    ]:
        raise ContractViolation("M12 partition freeze order drift")


def _validate_profile_common(profile: Mapping[str, Any], factor: str) -> None:
    expected_fields = {
        "profile_id",
        "factor",
        "status",
        "information_grant",
        "empirical_slots",
        "derivation_contract",
        "output_manifest_template",
        "freeze_sequence",
        "prohibited_inputs",
    }
    if set(profile) != expected_fields:
        raise ContractViolation(f"M12 {factor} profile fields drift")
    if profile["profile_id"] != f"CAREER_{factor}_clean_source/v1":
        raise ContractViolation(f"M12 {factor} profile ID drift")
    if profile["factor"] != factor or profile["status"] != PROFILE_STATUS:
        raise ContractViolation(f"M12 {factor} profile was instantiated")
    if not _all_null(profile["empirical_slots"]):
        raise ContractViolation(f"M12 {factor} empirical slot was populated")
    if set(profile["prohibited_inputs"]) != COMMON_PROHIBITED_INPUTS:
        raise ContractViolation(f"M12 {factor} prohibited inputs drift")
    expected_sequence = [
        "freeze_tracked_generator_and_static_inputs",
        f"freeze_{factor}_source_partition_assignment",
        "derive_deterministically_without_validation_outcomes",
        "content_address_input_and_output_manifests",
        "complete_two_independent_reviews",
        "freeze_source_package_before_threshold_design",
    ]
    if profile["freeze_sequence"] != expected_sequence:
        raise ContractViolation(f"M12 {factor} freeze sequence drift")


def _validate_s_profile(profile: Mapping[str, Any]) -> None:
    _validate_profile_common(profile, "S")
    if profile["information_grant"] != {
        "adds": "validated_process_relationship_records_only",
        "raw_observation_interface_changed": False,
        "action_authority_changed": False,
        "candidate_scores_or_ranks_added": False,
    }:
        raise ContractViolation("M12 S information grant drift")
    required_slots = {
        "tracked_generator_commit",
        "generator_sha256",
        "environment_manifest_sha256",
        "feeder_configuration_sha256",
        "operating_cell_registry_sha256",
        "development_seed_registry_sha256",
        "symmetric_perturbation_schedule_sha256",
        "source_partition_assignment_sha256",
        "raw_input_manifest_sha256",
        "derived_relationship_resource_sha256",
    }
    if set(profile["empirical_slots"]) != required_slots:
        raise ContractViolation("M12 S empirical slot identities drift")
    derivation = profile["derivation_contract"]
    if derivation != {
        "authority_surface": "single_ev_aggregator_setpoint",
        "controlled_device_count": 1,
        "controlled_variable": "active_charging_setpoint",
        "response_variable": "exposed_bus_voltage_telemetry",
        "reactive_power_axis": "outside_primary_scope_not_zero_imputed",
        "other_device_authority": False,
        "generator_mode": "tracked_deterministic_offline_derivation",
        "perturbation_design": "paired_symmetric_development_probes",
        "operating_cell_policy": "registry_frozen_before_source_generation",
        "numeric_precision_policy": "freeze_before_source_generation",
        "reproducibility_rule": "same_manifest_produces_identical_bytes",
        "output_granularity": "operating_cell_action_response_relationship",
    }:
        raise ContractViolation("M12 S derivation contract drift")
    if profile["output_manifest_template"] != {
        "schema_version": "grideval-career-S-relationship-resource/v1",
        "required_record_fields": [
            "operating_cell_id",
            "action_id",
            "signed_active_setpoint_delta",
            "voltage_response_statistic",
            "qualitative_response_direction",
            "source_block_id",
        ],
        "resource_mutable": False,
        "scientific_values_present": False,
    }:
        raise ContractViolation("M12 S output template drift")


def _validate_m_profile(profile: Mapping[str, Any]) -> None:
    _validate_profile_common(profile, "M")
    if profile["information_grant"] != {
        "adds": "validated_candidate_scores_and_ranks_only",
        "raw_observation_interface_changed": False,
        "action_authority_changed": False,
        "process_relationship_records_added": False,
    }:
        raise ContractViolation("M12 M information grant drift")
    required_slots = {
        "tracked_ranker_commit",
        "ranker_sha256",
        "environment_manifest_sha256",
        "feature_schema_sha256",
        "engineering_instantiation_manifest_sha256",
        "endpoint_definition_sha256",
        "development_seed_registry_sha256",
        "source_partition_assignment_sha256",
        "training_input_manifest_sha256",
        "frozen_model_sha256",
        "derived_ranking_resource_sha256",
    }
    if set(profile["empirical_slots"]) != required_slots:
        raise ContractViolation("M12 M empirical slot identities drift")
    derivation = profile["derivation_contract"]
    if set(derivation) != {
        "candidate_contract_id",
        "candidate_library_fingerprint",
        "ordered_candidate_ids",
        "physical_instantiation_binding",
        "predicted_endpoint",
        "conditioning_interface",
        "new_raw_observations_added",
        "algorithm_family",
        "ranker_mode",
        "tie_break_rule",
        "online_update",
        "uses_S_derived_resource",
        "reproducibility_rule",
        "output_granularity",
    }:
        raise ContractViolation("M12 M derivation fields drift")
    if derivation["candidate_contract_id"] != M9_CONTRACT_ID:
        raise ContractViolation("M12 M candidate contract drift")
    if derivation["candidate_library_fingerprint"] != (
            M9_CANDIDATE_LIBRARY_FINGERPRINT):
        raise ContractViolation("M12 M candidate fingerprint drift")
    if derivation["ordered_candidate_ids"] != list(M9_CANDIDATE_IDS):
        raise ContractViolation("M12 M candidate IDs or order drift")
    if derivation["physical_instantiation_binding"] != (
            "required_separate_manifest_preserving_M9_candidate_ids"):
        raise ContractViolation("M12 M physical-instantiation binding drift")
    if derivation["predicted_endpoint"] != (
            "maximum_scaled_voltage_envelope_excess"):
        raise ContractViolation("M12 M predicted endpoint drift")
    if derivation["conditioning_interface"] != (
            "only_context_already_visible_under_the_active_A_condition"):
        raise ContractViolation("M12 M conditioning interface drift")
    if derivation["new_raw_observations_added"] is not False:
        raise ContractViolation("M12 M added a raw observation")
    if derivation["algorithm_family"] != "unselected_before_source_review":
        raise ContractViolation("M12 M algorithm was selected prematurely")
    if derivation["ranker_mode"] != "tracked_deterministic_frozen_read_only":
        raise ContractViolation("M12 M ranker mode drift")
    if derivation["tie_break_rule"] != "frozen_M9_candidate_order":
        raise ContractViolation("M12 M tie-break rule drift")
    if derivation["online_update"] is not False:
        raise ContractViolation("M12 M cannot update online")
    if derivation["uses_S_derived_resource"] is not False:
        raise ContractViolation("M12 M cannot depend on the S resource")
    if derivation["reproducibility_rule"] != (
            "same_manifest_produces_identical_bytes"):
        raise ContractViolation("M12 M reproducibility rule drift")
    if derivation["output_granularity"] != "context_candidate_score_and_rank":
        raise ContractViolation("M12 M output granularity drift")
    if profile["output_manifest_template"] != {
        "schema_version": "grideval-career-M-ranking-resource/v1",
        "required_record_fields": [
            "context_id",
            "candidate_id",
            "predicted_primary_endpoint_score",
            "rank",
            "model_version_id",
            "source_block_id",
        ],
        "resource_mutable": False,
        "scientific_values_present": False,
    }:
        raise ContractViolation("M12 M output template drift")


def _validate_review_protocol(protocol: Mapping[str, Any]) -> None:
    expected_fields = {
        "status",
        "required_distinct_reviewers",
        "author_may_review",
        "review_order",
        "receipt_templates",
        "receipt_binding_fields",
        "threshold_design_release_rule",
    }
    if set(protocol) != expected_fields:
        raise ContractViolation("M12 review-protocol fields drift")
    if protocol["status"] != REVIEW_STATUS:
        raise ContractViolation("M12 review receipt was issued")
    if protocol["required_distinct_reviewers"] != 2:
        raise ContractViolation("M12 requires two distinct reviewers")
    if protocol["author_may_review"] is not False:
        raise ContractViolation("M12 cannot permit self-review")
    if protocol["review_order"] != [
        "source_lineage_and_partition_review",
        "capability_semantics_and_reproducibility_review",
    ]:
        raise ContractViolation("M12 review order drift")
    templates = protocol["receipt_templates"]
    if set(templates) != {
            "source_lineage_and_partition_review",
            "capability_semantics_and_reproducibility_review"}:
        raise ContractViolation("M12 review template identities drift")
    expected_roles = {
        "source_lineage_and_partition_review": (
            "independent_data_lineage_reviewer"
        ),
        "capability_semantics_and_reproducibility_review": (
            "independent_domain_method_reviewer"
        ),
    }
    for template_id, template in templates.items():
        if template != {
            "reviewer_role": expected_roles[template_id],
            "reviewer_id": None,
            "reviewed_profile_ids": [],
            "bound_manifest_sha256": None,
            "decision": None,
            "receipt_id": None,
            "status": REVIEW_STATUS,
        }:
            raise ContractViolation("M12 review receipt template was populated")
    if protocol["receipt_binding_fields"] != [
        "M12_contract_id",
        "profile_id",
        "tracked_code_revision",
        "static_input_hashes",
        "partition_assignment_hash",
        "input_manifest_hash",
        "output_manifest_hash",
    ]:
        raise ContractViolation("M12 review receipt binding drift")
    if protocol["threshold_design_release_rule"] != (
            "both_distinct_reviews_accept_exact_frozen_source_package"):
        raise ContractViolation("M12 threshold release rule drift")


def _empty_slots(names: set[str]) -> dict[str, None]:
    return {name: None for name in sorted(names)}


def _partition_registry() -> dict[str, Any]:
    scopes = {
        "S_source_derivation": ("S", "derive_clean_source_only"),
        "S_threshold_design": ("S", "future_threshold_design_only"),
        "S_independent_validation": ("S", "future_action_validity_only"),
        "M_source_derivation": ("M", "derive_clean_source_only"),
        "M_threshold_design": ("M", "future_threshold_design_only"),
        "M_independent_validation": ("M", "future_ranking_validity_only"),
        "ASM_factor_confirmation": ("ASM", "future_factor_effect_only"),
        "evaluation_sealed": ("evaluation", "sealed_no_access"),
    }
    return {
        "status": PARTITION_STATUS,
        "sample_identity": (
            "factor_role_run_seed_operating_cell_episode_block"
        ),
        "roles": [
            {
                "id": role,
                "factor_scope": scopes[role][0],
                "purpose": scopes[role][1],
                "status": PARTITION_STATUS,
            }
            for role in PARTITION_ROLES
        ],
        "assignments": {role: None for role in PARTITION_ROLES},
        "pairwise_disjoint_empirical_blocks": True,
        "cross_factor_empirical_block_reuse": False,
        "shared_static_inputs_allowed": [
            "tracked_code_bytes",
            "frozen_environment_manifest",
            "frozen_feeder_configuration",
            "M9_protocol_and_candidate_definitions",
        ],
        "derived_resource_dependency": (
            "S_and_M_must_not_depend_on_each_others_derived_resource"
        ),
        "assignment_freeze_order": [
            "freeze_sample_identity",
            "freeze_partition_role_registry",
            "assign_content_addressed_blocks_without_outcome_access",
            "verify_pairwise_disjointness",
            "independent_partition_review",
            "freeze_assignment_manifest_before_derivation",
        ],
    }


def _profile_common(factor: str, empirical_slots: set[str]) -> dict[str, Any]:
    return {
        "profile_id": f"CAREER_{factor}_clean_source/v1",
        "factor": factor,
        "status": PROFILE_STATUS,
        "empirical_slots": _empty_slots(empirical_slots),
        "freeze_sequence": [
            "freeze_tracked_generator_and_static_inputs",
            f"freeze_{factor}_source_partition_assignment",
            "derive_deterministically_without_validation_outcomes",
            "content_address_input_and_output_manifests",
            "complete_two_independent_reviews",
            "freeze_source_package_before_threshold_design",
        ],
        "prohibited_inputs": sorted(COMMON_PROHIBITED_INPUTS),
    }


def _s_profile() -> dict[str, Any]:
    profile = _profile_common("S", {
        "tracked_generator_commit",
        "generator_sha256",
        "environment_manifest_sha256",
        "feeder_configuration_sha256",
        "operating_cell_registry_sha256",
        "development_seed_registry_sha256",
        "symmetric_perturbation_schedule_sha256",
        "source_partition_assignment_sha256",
        "raw_input_manifest_sha256",
        "derived_relationship_resource_sha256",
    })
    profile.update({
        "information_grant": {
            "adds": "validated_process_relationship_records_only",
            "raw_observation_interface_changed": False,
            "action_authority_changed": False,
            "candidate_scores_or_ranks_added": False,
        },
        "derivation_contract": {
            "authority_surface": "single_ev_aggregator_setpoint",
            "controlled_device_count": 1,
            "controlled_variable": "active_charging_setpoint",
            "response_variable": "exposed_bus_voltage_telemetry",
            "reactive_power_axis": "outside_primary_scope_not_zero_imputed",
            "other_device_authority": False,
            "generator_mode": "tracked_deterministic_offline_derivation",
            "perturbation_design": "paired_symmetric_development_probes",
            "operating_cell_policy": (
                "registry_frozen_before_source_generation"
            ),
            "numeric_precision_policy": "freeze_before_source_generation",
            "reproducibility_rule": "same_manifest_produces_identical_bytes",
            "output_granularity": (
                "operating_cell_action_response_relationship"
            ),
        },
        "output_manifest_template": {
            "schema_version": "grideval-career-S-relationship-resource/v1",
            "required_record_fields": [
                "operating_cell_id",
                "action_id",
                "signed_active_setpoint_delta",
                "voltage_response_statistic",
                "qualitative_response_direction",
                "source_block_id",
            ],
            "resource_mutable": False,
            "scientific_values_present": False,
        },
    })
    return profile


def _m_profile() -> dict[str, Any]:
    profile = _profile_common("M", {
        "tracked_ranker_commit",
        "ranker_sha256",
        "environment_manifest_sha256",
        "feature_schema_sha256",
        "engineering_instantiation_manifest_sha256",
        "endpoint_definition_sha256",
        "development_seed_registry_sha256",
        "source_partition_assignment_sha256",
        "training_input_manifest_sha256",
        "frozen_model_sha256",
        "derived_ranking_resource_sha256",
    })
    profile.update({
        "information_grant": {
            "adds": "validated_candidate_scores_and_ranks_only",
            "raw_observation_interface_changed": False,
            "action_authority_changed": False,
            "process_relationship_records_added": False,
        },
        "derivation_contract": {
            "candidate_contract_id": M9_CONTRACT_ID,
            "candidate_library_fingerprint": (
                M9_CANDIDATE_LIBRARY_FINGERPRINT
            ),
            "ordered_candidate_ids": list(M9_CANDIDATE_IDS),
            "physical_instantiation_binding": (
                "required_separate_manifest_preserving_M9_candidate_ids"
            ),
            "predicted_endpoint": "maximum_scaled_voltage_envelope_excess",
            "conditioning_interface": (
                "only_context_already_visible_under_the_active_A_condition"
            ),
            "new_raw_observations_added": False,
            "algorithm_family": "unselected_before_source_review",
            "ranker_mode": "tracked_deterministic_frozen_read_only",
            "tie_break_rule": "frozen_M9_candidate_order",
            "online_update": False,
            "uses_S_derived_resource": False,
            "reproducibility_rule": "same_manifest_produces_identical_bytes",
            "output_granularity": "context_candidate_score_and_rank",
        },
        "output_manifest_template": {
            "schema_version": "grideval-career-M-ranking-resource/v1",
            "required_record_fields": [
                "context_id",
                "candidate_id",
                "predicted_primary_endpoint_score",
                "rank",
                "model_version_id",
                "source_block_id",
            ],
            "resource_mutable": False,
            "scientific_values_present": False,
        },
    })
    return profile


def _review_protocol() -> dict[str, Any]:
    return {
        "status": REVIEW_STATUS,
        "required_distinct_reviewers": 2,
        "author_may_review": False,
        "review_order": [
            "source_lineage_and_partition_review",
            "capability_semantics_and_reproducibility_review",
        ],
        "receipt_templates": {
            "source_lineage_and_partition_review": {
                "reviewer_role": "independent_data_lineage_reviewer",
                "reviewer_id": None,
                "reviewed_profile_ids": [],
                "bound_manifest_sha256": None,
                "decision": None,
                "receipt_id": None,
                "status": REVIEW_STATUS,
            },
            "capability_semantics_and_reproducibility_review": {
                "reviewer_role": "independent_domain_method_reviewer",
                "reviewer_id": None,
                "reviewed_profile_ids": [],
                "bound_manifest_sha256": None,
                "decision": None,
                "receipt_id": None,
                "status": REVIEW_STATUS,
            },
        },
        "receipt_binding_fields": [
            "M12_contract_id",
            "profile_id",
            "tracked_code_revision",
            "static_input_hashes",
            "partition_assignment_hash",
            "input_manifest_hash",
            "output_manifest_hash",
        ],
        "threshold_design_release_rule": (
            "both_distinct_reviews_accept_exact_frozen_source_package"
        ),
    }


def build_career_source_freeze_design() -> CareerSourceFreezeDesign:
    """Build the canonical M12 clean-source freeze design artifact."""

    content: dict[str, Any] = {
        "schema_version": SOURCE_FREEZE_DESIGN_SCHEMA_VERSION,
        "contract_id": "pending",
        "milestone": "M12",
        "title": "CAREER S/M clean-source freeze and review design",
        "status": M12_STATUS,
        "governance": dict(REQUIRED_GOVERNANCE),
        "source_lineage": {
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "m9_contract_id": M9_CONTRACT_ID,
            "m9_parity_fingerprint": M9_PARITY_FINGERPRINT,
            "m9_candidate_library_fingerprint": (
                M9_CANDIDATE_LIBRARY_FINGERPRINT
            ),
            "m11_contract_id": M11_CONTRACT_ID,
            "m12_decision": M12_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        },
        "partition_registry": _partition_registry(),
        "clean_source_profiles": {
            "S": _s_profile(),
            "M": _m_profile(),
        },
        "review_protocol": _review_protocol(),
        "canonical_status": {
            "S_source_package": "UNBUILT_DESIGN_ONLY",
            "M_source_package": "UNBUILT_DESIGN_ONLY",
            "partition_assignments": PARTITION_STATUS,
            "review_receipts": REVIEW_STATUS,
            "S_scientific_threshold": THRESHOLD_STATUS,
            "M_scientific_threshold": THRESHOLD_STATUS,
            "S_real_resource": REAL_RESOURCE_HOLD,
            "M_real_resource": REAL_RESOURCE_HOLD,
            "evaluation": "SEALED",
            "campaign": "HOLD",
        },
        "limitations": sorted({
            "no_real_source_or_partition_instantiated",
            "no_review_receipt_issued",
            "no_scientific_threshold_or_estimator_finalized",
            "no_real_resource_validated_or_admitted",
            "no_physical_ranking_or_factor_effect_claim",
            "no_model_embedding_tool_or_runtime_access",
            "no_evaluation_or_campaign_authorization",
        }),
        "next_gate": {
            "id": "M13_offline_synthetic_source_manifest_validator",
            "scope": "synthetic_positive_and_negative_manifests_only",
            "may_freeze_real_sources": False,
            "may_assign_real_partitions": False,
            "may_issue_real_review_receipts": False,
            "may_select_scientific_thresholds": False,
            "model_or_embedding_call": False,
            "simulator_or_detector_access": False,
            "evaluation_access": False,
        },
    }
    content["contract_id"] = contract_id_for(content)
    return CareerSourceFreezeDesign(content)


def load_career_source_freeze_design(path: str | Path) -> CareerSourceFreezeDesign:
    """Load and semantically validate a checked-in M12 design artifact."""

    return CareerSourceFreezeDesign(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )
