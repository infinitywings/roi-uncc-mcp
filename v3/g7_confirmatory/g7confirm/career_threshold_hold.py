"""M11 source-lineage audit and threshold-preregistration HOLD contract.

The artifact produced here records why current exploratory sources cannot
support CAREER S/M threshold selection.  It intentionally contains no
scientific threshold values and exposes no runtime or external-service path.
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
from .orchestration_contract import ContractViolation


THRESHOLD_HOLD_SCHEMA_VERSION = "grideval-career-threshold-hold/v1"
M10_CONTRACT_ID = (
    "careerresource_f3b0033341368b5eca92d350d4f06906eb969dffd5855f5829e26a0f5a97c2ca"
)
M11_DECISION_ID = "dec_01M1DMKWJ9BM6YV2E0MNDJZRDJ"
M11_VERDICT = "HOLD_PREREQUISITES_NOT_MET"
THRESHOLD_STATUS = "UNSET_NOT_SCIENTIFICALLY_JUSTIFIED"
EXPLORATORY_ONLY = "INADMISSIBLE_EXPLORATORY_REFERENCE_ONLY"

SENSITIVITY_SHA256 = (
    "05d486024b5106dec266c512d008294ff41c6485011093baf67a9737293bf8f8"
)
BASELINE_TRACE_SHA256 = (
    "3945f0bc0bbe638c255d6284e6116661a116a415e93d45ee56cbd703cae5ab14"
)
L5B_TRACE_SHA256 = (
    "f41f40c610336b00bbc815d34d68831aa65f85e70508cb2df71ac1d57691a670"
)
L5B_SCRIPT_SHA256 = (
    "748f284fe7b90b25b8aea1328cbc72626a0dd0cf1f266720081bc33cdcfba4fb"
)

PROBE_TRACE_HASHES = {
    "DER_EV1_BESS": (
        "6071faf8b0ca7ea66f9842820d7c963f2238d415364edc5e61602324d5f5212a"
    ),
    "DER_EV3_PV": (
        "2416dee47304f263773059517414a440676d9647db495fe3ea4d9d7589ea77e3"
    ),
    "DER_EV4_BESS": (
        "5aad2a1681383d5e7cb8d5387b1dea10e1ed6708df75e52621fd7f2d809261d5"
    ),
    "DER_EV5_PV": (
        "1498c2324919d0703569f62f62329bb13f7f48eb1ac29ca8b020b4d2777b1357"
    ),
}

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
    "scientific_threshold_freeze_authorized": False,
    "real_resource_admission_authorized": False,
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
    return _content_id("careerthresholdhold", payload, omit=("contract_id",))


@dataclass(frozen=True)
class CareerThresholdHold:
    """Immutable semantic representation of the M11 HOLD artifact."""

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
            "verdict",
            "governance",
            "source_lineage",
            "audit_scope",
            "candidate_source_audit",
            "threshold_preregistration",
            "required_repairs",
            "canonical_status",
            "limitations",
            "next_gate",
        }
        if set(content) != expected_fields:
            raise ContractViolation("M11 HOLD top-level fields drift")
        if content["schema_version"] != THRESHOLD_HOLD_SCHEMA_VERSION:
            raise ContractViolation("unsupported M11 HOLD schema_version")
        if content["milestone"] != "M11":
            raise ContractViolation("threshold HOLD must be milestone M11")
        if content["contract_id"] != contract_id_for(content):
            raise ContractViolation("M11 HOLD contract_id mismatch")
        if content["verdict"] != M11_VERDICT:
            raise ContractViolation("M11 must remain a prerequisite HOLD")
        if content["governance"] != REQUIRED_GOVERNANCE:
            raise ContractViolation("M11 governance boundary drift")

        required_lineage = {
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "m9_contract_id": M9_CONTRACT_ID,
            "m10_contract_id": M10_CONTRACT_ID,
            "m11_decision": M11_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        }
        if content["source_lineage"] != required_lineage:
            raise ContractViolation("M11 source lineage drift")

        scope = content["audit_scope"]
        if scope.get("absence_claim") != "bounded_to_declared_scan_scope":
            raise ContractViolation("M11 source absence claim is unbounded")
        if scope.get("writes_performed") is not False:
            raise ContractViolation("M11 source audit must be read-only")
        if set(scope.get("scanned_roots", ())) != {
            "v3/opender_federate",
            "v3/g7_condition_freeze/20260830_r1",
            "v3/g7_confirmatory",
            "RKA_project_prj_01KYMPK10PE9YH1TJ84PAVB9Z6",
        }:
            raise ContractViolation("M11 declared audit scope drift")
        if set(scope.get("methods", ())) != {
            "targeted_filename_scan",
            "targeted_content_scan",
            "JSON_structure_and_lineage_inspection",
            "SHA256_and_byte_count",
            "Git_tracking_status",
            "RKA_targeted_retrieval",
            "read_only_numeric_consistency_check",
        }:
            raise ContractViolation("M11 audit methods drift")

        audit = content["candidate_source_audit"]
        if set(audit) != {"S", "M"}:
            raise ContractViolation("M11 requires separate S and M audits")
        _validate_s_audit(audit["S"])
        _validate_m_audit(audit["M"])

        prereg = content["threshold_preregistration"]
        if set(prereg) != {"S", "M", "shared_rules"}:
            raise ContractViolation("M11 threshold plan fields drift")
        _validate_metric_plan(
            prereg["S"],
            factor="S",
            metrics={
                "directional_response_agreement",
                "normalized_response_error",
                "operating_envelope_coverage",
            },
        )
        _validate_metric_plan(
            prereg["M"],
            factor="M",
            metrics={
                "pairwise_order_accuracy",
                "top_k_candidate_recall",
                "normalized_simple_regret",
            },
        )
        shared = prereg["shared_rules"]
        required_shared = {
            "threshold_values_must_be_null_in_M11": True,
            "synthetic_M10_values_may_be_reused": False,
            "exploratory_outcomes_may_select_thresholds": False,
            "treatment_or_evaluation_outcomes_may_be_read": False,
            "threshold_design_partition_required": True,
            "threshold_design_and_validation_partitions_disjoint": True,
            "independent_review_before_freeze": True,
            "missing_or_invalid_evidence_policy": "factor_not_admitted",
            "failed_factor_policy": "reduce_factorial_prospectively",
        }
        if shared != required_shared:
            raise ContractViolation("M11 shared threshold rules drift")

        repairs = content["required_repairs"]
        if set(repairs) != {"S", "M"}:
            raise ContractViolation("M11 requires separate S and M repairs")
        if "single_ev_aggregator_setpoint" not in repairs["S"]:
            raise ContractViolation("M11 S repair changed primary authority")
        if "exact_M9_candidate_library" not in repairs["M"]:
            raise ContractViolation("M11 M repair changed candidate scope")
        if not all(repairs.values()):
            raise ContractViolation("M11 repair list cannot be empty")

        status = content["canonical_status"]
        if status != {
            "S_real_resource": REAL_RESOURCE_HOLD,
            "M_real_resource": REAL_RESOURCE_HOLD,
            "S_scientific_threshold": THRESHOLD_STATUS,
            "M_scientific_threshold": THRESHOLD_STATUS,
            "evaluation": "SEALED",
            "campaign": "HOLD",
        }:
            raise ContractViolation("M11 canonical HOLD status drift")

        required_limitations = {
            "scoped_audit_does_not_prove_global_source_absence",
            "exploratory_sources_preserved_not_promoted",
            "no_real_resource_validated_or_admitted",
            "no_scientific_threshold_selected",
            "estimator_skeletons_not_final_analysis_plans",
            "no_physical_ranking_or_factor_effect_claim",
            "no_runtime_or_campaign_authorization",
        }
        if set(content["limitations"]) != required_limitations:
            raise ContractViolation("M11 limitations drift")
        if content["next_gate"] != {
            "id": "M12_clean_candidate_source_freeze_design",
            "scope": "offline_source_manifest_and_partition_design_only",
            "requires_independent_review": True,
            "runtime_authorized": False,
            "model_or_embedding_call": False,
            "simulator_or_detector_access": False,
        }:
            raise ContractViolation("unexpected M11 next gate")


def _validate_s_audit(audit: Mapping[str, Any]) -> None:
    if audit.get("candidate_status") != EXPLORATORY_ONLY:
        raise ContractViolation("M11 S candidate was promoted")
    artifact = audit.get("artifact", {})
    if artifact != {
        "path": "v3/opender_federate/sensitivity_g7.json",
        "bytes": 16497,
        "sha256": SENSITIVITY_SHA256,
        "git_tracked": False,
        "freeze_copy_byte_identical": True,
    }:
        raise ContractViolation("M11 S artifact audit drift")
    declared = audit.get("declared_structure", {})
    if declared.get("probe_based") is not True:
        raise ContractViolation("M11 S probe declaration drift")
    if declared.get("Sp_shape") != [4, 4]:
        raise ContractViolation("M11 S Sp shape drift")
    if declared.get("Sq_shape") != [4, 4]:
        raise ContractViolation("M11 S Sq shape drift")
    if declared.get("Sq_nonzero_entries") != 0:
        raise ContractViolation("M11 S Sq audit drift")
    if declared.get("reference_rows") != 84:
        raise ContractViolation("M11 S reference length drift")
    if len(declared.get("source_runs", ())) != 7:
        raise ContractViolation("M11 S source-run count drift")
    observed = audit.get("observed_lineage", {})
    if observed.get("reference_arrays_exactly_match_unlisted_baseline") is not True:
        raise ContractViolation("M11 S baseline equality finding drift")
    if observed.get("unlisted_baseline_sha256") != BASELINE_TRACE_SHA256:
        raise ContractViolation("M11 S baseline hash drift")
    if observed.get("probe_trace_hashes") != PROBE_TRACE_HASHES:
        raise ContractViolation("M11 S probe hashes drift")
    if observed.get("probe_paths_named_in_source_runs") is not False:
        raise ContractViolation("M11 S probe-lineage finding drift")
    if observed.get("generator_found_in_scoped_scan") is not False:
        raise ContractViolation("M11 S generator finding drift")
    required_disqualifiers = {
        "untracked_source_bytes",
        "source_runs_omit_exact_baseline",
        "probe_traces_not_content_bound_by_artifact",
        "generator_not_found_in_scoped_scan",
        "run_seed_and_operating_condition_lineage_incomplete",
        "four_device_authority_does_not_match_single_aggregator_core",
        "all_zero_Q_channel_not_validated_as_intentional_scope",
    }
    if set(audit.get("disqualifiers", ())) != required_disqualifiers:
        raise ContractViolation("M11 S disqualifier set drift")


def _validate_m_audit(audit: Mapping[str, Any]) -> None:
    if audit.get("candidate_status") != EXPLORATORY_ONLY:
        raise ContractViolation("M11 M candidate was promoted")
    if audit.get("eligible_candidate_found_in_scope") is not False:
        raise ContractViolation("M11 M source finding drift")
    trace = audit.get("exploratory_trace", {})
    if trace != {
        "path": "v3/opender_federate/g7_l5b_search_trace.json",
        "bytes": 1729,
        "sha256": L5B_TRACE_SHA256,
        "git_tracked": False,
        "episodes": 5,
        "contains_detector_informed_treatment_outcomes": True,
        "ranks_exact_M9_candidate_library": False,
    }:
        raise ContractViolation("M11 M trace audit drift")
    script = audit.get("associated_script", {})
    if script != {
        "path": "v3/opender_federate/g7_l5b_search.py",
        "bytes": 5159,
        "sha256": L5B_SCRIPT_SHA256,
        "git_tracked": False,
    }:
        raise ContractViolation("M11 M script audit drift")
    required_disqualifiers = {
        "untracked_source_bytes",
        "treatment_outcomes_used_for_search",
        "detector_outcomes_used_for_search",
        "candidate_space_not_M9_library",
        "no_independent_ranking_validation_partition",
        "no_frozen_read_only_ranking_artifact",
    }
    if set(audit.get("disqualifiers", ())) != required_disqualifiers:
        raise ContractViolation("M11 M disqualifier set drift")


def _validate_metric_plan(
    plan: Mapping[str, Any], *, factor: str, metrics: set[str]
) -> None:
    if plan.get("factor") != factor:
        raise ContractViolation(f"M11 {factor} metric-plan factor drift")
    if plan.get("status") != "DRAFT_PREREQUISITES_REQUIRED":
        raise ContractViolation(f"M11 {factor} metric-plan status drift")
    if plan.get("sample_unit") != "independent_validation_block_not_window":
        raise ContractViolation(f"M11 {factor} sample unit drift")
    if plan.get("threshold_design_partition") is not None:
        raise ContractViolation(f"M11 {factor} threshold partition invented")
    if plan.get("validation_partition") is not None:
        raise ContractViolation(f"M11 {factor} validation partition invented")
    metric_plans = plan.get("metrics", {})
    if set(metric_plans) != metrics:
        raise ContractViolation(f"M11 {factor} metric identities drift")
    for metric_id, metric in metric_plans.items():
        if metric.get("scientific_threshold") is not None:
            raise ContractViolation(
                f"M11 threshold was invented for {factor}:{metric_id}"
            )
        if metric.get("threshold_status") != THRESHOLD_STATUS:
            raise ContractViolation(
                f"M11 threshold status drift for {factor}:{metric_id}"
            )
        if metric.get("estimator_status") != (
                "draft_requires_source_freeze_and_independent_review"):
            raise ContractViolation(
                f"M11 estimator status drift for {factor}:{metric_id}"
            )
        if not metric.get("estimator_skeleton"):
            raise ContractViolation(
                f"M11 estimator skeleton missing for {factor}:{metric_id}"
            )
    if plan.get("uncertainty_plan") != (
            "cluster_aware_interval_over_independent_blocks_method_unselected"):
        raise ContractViolation(f"M11 {factor} uncertainty plan drift")
    if plan.get("missing_data_policy") != (
            "invalid_or_missing_block_fails_admission_completeness"):
        raise ContractViolation(f"M11 {factor} missing-data policy drift")


def _metric(
    estimator_skeleton: str,
) -> dict[str, Any]:
    return {
        "estimator_skeleton": estimator_skeleton,
        "estimator_status": (
            "draft_requires_source_freeze_and_independent_review"
        ),
        "scientific_threshold": None,
        "threshold_status": THRESHOLD_STATUS,
    }


def build_career_threshold_hold() -> CareerThresholdHold:
    """Build the canonical M11 source-audit and threshold HOLD artifact."""

    content: dict[str, Any] = {
        "schema_version": THRESHOLD_HOLD_SCHEMA_VERSION,
        "contract_id": "pending",
        "milestone": "M11",
        "title": "CAREER S/M source-lineage and threshold prerequisite HOLD",
        "verdict": M11_VERDICT,
        "governance": dict(REQUIRED_GOVERNANCE),
        "source_lineage": {
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "m9_contract_id": M9_CONTRACT_ID,
            "m10_contract_id": M10_CONTRACT_ID,
            "m11_decision": M11_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        },
        "audit_scope": {
            "scanned_roots": sorted({
                "v3/opender_federate",
                "v3/g7_condition_freeze/20260830_r1",
                "v3/g7_confirmatory",
                "RKA_project_prj_01KYMPK10PE9YH1TJ84PAVB9Z6",
            }),
            "methods": sorted({
                "targeted_filename_scan",
                "targeted_content_scan",
                "JSON_structure_and_lineage_inspection",
                "SHA256_and_byte_count",
                "Git_tracking_status",
                "RKA_targeted_retrieval",
                "read_only_numeric_consistency_check",
            }),
            "absence_claim": "bounded_to_declared_scan_scope",
            "writes_performed": False,
        },
        "candidate_source_audit": {
            "S": {
                "candidate_status": EXPLORATORY_ONLY,
                "artifact": {
                    "path": "v3/opender_federate/sensitivity_g7.json",
                    "bytes": 16497,
                    "sha256": SENSITIVITY_SHA256,
                    "git_tracked": False,
                    "freeze_copy_byte_identical": True,
                },
                "declared_structure": {
                    "probe_based": True,
                    "device_ids": [
                        "DER_EV4_BESS",
                        "DER_EV1_BESS",
                        "DER_EV3_PV",
                        "DER_EV5_PV",
                    ],
                    "Sp_shape": [4, 4],
                    "Sq_shape": [4, 4],
                    "Sq_nonzero_entries": 0,
                    "reference_rows": 84,
                    "source_runs": [
                        "g7_pilot_sm",
                        "g7_pilot_llm",
                        "g7_pilot_rnd1",
                        "g7_pilot_rnd2",
                        "g7_pilot_rnd_s1003",
                        "g7_pilot_rnd_s1004",
                        "g7_pilot_rnd_s1005",
                    ],
                },
                "observed_lineage": {
                    "reference_arrays_exactly_match_unlisted_baseline": True,
                    "unlisted_baseline_path": (
                        "v3/opender_federate/g7_pilot_b0/"
                        "multi_der_traces.json"
                    ),
                    "unlisted_baseline_sha256": BASELINE_TRACE_SHA256,
                    "probe_trace_hashes": dict(PROBE_TRACE_HASHES),
                    "probe_paths_named_in_source_runs": False,
                    "generator_found_in_scoped_scan": False,
                },
                "disqualifiers": sorted({
                    "untracked_source_bytes",
                    "source_runs_omit_exact_baseline",
                    "probe_traces_not_content_bound_by_artifact",
                    "generator_not_found_in_scoped_scan",
                    "run_seed_and_operating_condition_lineage_incomplete",
                    "four_device_authority_does_not_match_single_aggregator_core",
                    "all_zero_Q_channel_not_validated_as_intentional_scope",
                }),
                "historical_use": (
                    "retain_for_exploratory_L2_lineage_not_CAREER_admission"
                ),
            },
            "M": {
                "candidate_status": EXPLORATORY_ONLY,
                "eligible_candidate_found_in_scope": False,
                "exploratory_trace": {
                    "path": (
                        "v3/opender_federate/g7_l5b_search_trace.json"
                    ),
                    "bytes": 1729,
                    "sha256": L5B_TRACE_SHA256,
                    "git_tracked": False,
                    "episodes": 5,
                    "contains_detector_informed_treatment_outcomes": True,
                    "ranks_exact_M9_candidate_library": False,
                },
                "associated_script": {
                    "path": "v3/opender_federate/g7_l5b_search.py",
                    "bytes": 5159,
                    "sha256": L5B_SCRIPT_SHA256,
                    "git_tracked": False,
                },
                "disqualifiers": sorted({
                    "untracked_source_bytes",
                    "treatment_outcomes_used_for_search",
                    "detector_outcomes_used_for_search",
                    "candidate_space_not_M9_library",
                    "no_independent_ranking_validation_partition",
                    "no_frozen_read_only_ranking_artifact",
                }),
                "historical_use": (
                    "retain_for_exploratory_L5b_lineage_not_CAREER_admission"
                ),
            },
        },
        "threshold_preregistration": {
            "S": {
                "factor": "S",
                "status": "DRAFT_PREREQUISITES_REQUIRED",
                "sample_unit": "independent_validation_block_not_window",
                "threshold_design_partition": None,
                "validation_partition": None,
                "metrics": {
                    "directional_response_agreement": _metric(
                        "block_fraction_of_preregistered_action_response_"
                        "pairs_with_correct_signed_response"
                    ),
                    "normalized_response_error": _metric(
                        "block_response_error_scaled_by_frozen_engineering_"
                        "tolerance"
                    ),
                    "operating_envelope_coverage": _metric(
                        "fraction_of_preregistered_operating_cells_with_"
                        "complete_valid_evidence"
                    ),
                },
                "uncertainty_plan": (
                    "cluster_aware_interval_over_independent_blocks_"
                    "method_unselected"
                ),
                "missing_data_policy": (
                    "invalid_or_missing_block_fails_admission_completeness"
                ),
            },
            "M": {
                "factor": "M",
                "status": "DRAFT_PREREQUISITES_REQUIRED",
                "sample_unit": "independent_validation_block_not_window",
                "threshold_design_partition": None,
                "validation_partition": None,
                "metrics": {
                    "pairwise_order_accuracy": _metric(
                        "block_fraction_of_preregistered_candidate_pairs_"
                        "ranked_in_observed_order"
                    ),
                    "top_k_candidate_recall": _metric(
                        "block_recall_of_observed_best_candidates_with_k_"
                        "frozen_before_validation"
                    ),
                    "normalized_simple_regret": _metric(
                        "block_gap_between_observed_best_and_top_ranked_"
                        "candidate_scaled_by_frozen_outcome_range"
                    ),
                },
                "uncertainty_plan": (
                    "cluster_aware_interval_over_independent_blocks_"
                    "method_unselected"
                ),
                "missing_data_policy": (
                    "invalid_or_missing_block_fails_admission_completeness"
                ),
            },
            "shared_rules": {
                "threshold_values_must_be_null_in_M11": True,
                "synthetic_M10_values_may_be_reused": False,
                "exploratory_outcomes_may_select_thresholds": False,
                "treatment_or_evaluation_outcomes_may_be_read": False,
                "threshold_design_partition_required": True,
                "threshold_design_and_validation_partitions_disjoint": True,
                "independent_review_before_freeze": True,
                "missing_or_invalid_evidence_policy": "factor_not_admitted",
                "failed_factor_policy": "reduce_factorial_prospectively",
            },
        },
        "required_repairs": {
            "S": [
                "single_ev_aggregator_setpoint",
                "tracked_deterministic_source_generator",
                "content_addressed_input_and_output_manifests",
                "explicit_development_seed_and_operating_condition_lineage",
                "separate_threshold_design_and_validation_partitions",
                "independent_source_and_metric_review",
                "no_treatment_detector_or_evaluation_outcomes",
            ],
            "M": [
                "exact_M9_candidate_library",
                "tracked_frozen_read_only_ranker",
                "content_addressed_derivation_manifest",
                "separate_threshold_design_and_validation_partitions",
                "independent_source_and_metric_review",
                "no_online_update",
                "no_treatment_detector_or_evaluation_outcomes",
            ],
        },
        "canonical_status": {
            "S_real_resource": REAL_RESOURCE_HOLD,
            "M_real_resource": REAL_RESOURCE_HOLD,
            "S_scientific_threshold": THRESHOLD_STATUS,
            "M_scientific_threshold": THRESHOLD_STATUS,
            "evaluation": "SEALED",
            "campaign": "HOLD",
        },
        "limitations": sorted({
            "scoped_audit_does_not_prove_global_source_absence",
            "exploratory_sources_preserved_not_promoted",
            "no_real_resource_validated_or_admitted",
            "no_scientific_threshold_selected",
            "estimator_skeletons_not_final_analysis_plans",
            "no_physical_ranking_or_factor_effect_claim",
            "no_runtime_or_campaign_authorization",
        }),
        "next_gate": {
            "id": "M12_clean_candidate_source_freeze_design",
            "scope": "offline_source_manifest_and_partition_design_only",
            "requires_independent_review": True,
            "runtime_authorized": False,
            "model_or_embedding_call": False,
            "simulator_or_detector_access": False,
        },
    }
    content["contract_id"] = contract_id_for(content)
    return CareerThresholdHold(content)


def load_career_threshold_hold(path: str | Path) -> CareerThresholdHold:
    """Load and semantically validate a checked-in M11 HOLD artifact."""

    return CareerThresholdHold(json.loads(Path(path).read_text(encoding="utf-8")))
