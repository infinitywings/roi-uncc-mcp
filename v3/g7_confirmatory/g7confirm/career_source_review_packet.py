"""M14 independent-review packet for CAREER source-generation prerequisites.

The packet is ready to be reviewed but contains no review disposition. It
binds an exact committed snapshot and cannot authorize partition assignment,
source generation, threshold selection, or runtime access.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_resource_admission import REAL_RESOURCE_HOLD
from .career_source_freeze_design import M9_CANDIDATE_IDS, REVIEW_STATUS
from .career_threshold_hold import THRESHOLD_STATUS
from .orchestration_contract import ContractViolation


SOURCE_REVIEW_PACKET_SCHEMA_VERSION = "grideval-career-source-review-packet/v1"
M13_MATRIX_ID = (
    "m13matrix_4025c6e7342d20113eb56bfd0c75676f9160389db968456b88603f61156ae7a3"
)
M14_DECISION_ID = "dec_01M1DPBJJQR8346RVZBKFSBDH7"
M13_BASE_COMMIT = "cbccdaa069784adbb3c03d130a42c5d0027ce16d"
PACKET_STATUS = "READY_FOR_INDEPENDENT_REVIEW_NOT_APPROVED"
OPEN_STATUS = "OPEN_NOT_SATISFIED"

REQUIRED_GOVERNANCE = {
    "development_only": True,
    "packet_preparation_only": True,
    "campaign_authorized": False,
    "evaluation_sealed": True,
    "real_source_generation_authorized": False,
    "real_partition_assignment_authorized": False,
    "real_review_receipt_issuance_authorized": False,
    "scientific_threshold_freeze_authorized": False,
    "real_resource_admission_authorized": False,
    "model_or_embedding_access_authorized": False,
    "tool_simulator_detector_or_actuator_access_authorized": False,
}

REVIEW_QUESTIONS = (
    "Does the eight-role partition design prevent derivation, threshold, "
    "validation, confirmation, and evaluation leakage?",
    "Does S preserve the single-EV active-setpoint authority and exclude an "
    "unvalidated reactive channel?",
    "Does M preserve the exact ordered M9 candidate IDs and require a "
    "separate physical-instantiation manifest?",
    "Do information grants keep A, S, and M independently interpretable?",
    "Are content-addressing, deterministic reproduction, reviewer "
    "independence, and abort criteria sufficient before source generation?",
    "Are all proposed runtime quantities and algorithm choices correctly "
    "left unset pending review?",
)

REVIEW_SNAPSHOT = (
    ("v3/g7_confirmatory/experiment_spec.yaml", 5433,
     "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"),
    ("v3/g7_confirmatory/roadmap_2026/report.html", 445019,
     "c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b"),
    ("v3/g7_confirmatory/artifacts/career_stealth_contract_m8.json", 10796,
     "8ab204b567cc3959eeccfdc61719b201ec8030aef1cc11a16ceb632350a19bea"),
    ("v3/g7_confirmatory/artifacts/career_two_interval_fixture_m9.json", 15464,
     "5c03d8590d705a5fd20730ce319c970d6f683e7e72d8992f310b735327e677e6"),
    ("v3/g7_confirmatory/artifacts/career_resource_admission_m10.json", 45809,
     "60c1bb2c7a73c2cc2a6904b291ce50f6754fb390a7519cc855b92864bf275683"),
    ("v3/g7_confirmatory/artifacts/career_threshold_hold_m11.json", 10838,
     "6a58f7b98a421f9107e23bb95f9d5fc9c3d2c9777d0dcbd467586d6d833dc25a"),
    ("v3/g7_confirmatory/artifacts/career_source_freeze_design_m12.json", 13315,
     "7801e1b2c1fd3a50daa6c3660c47a20992305de771205c93c575d6bdf91aa464"),
    ("v3/g7_confirmatory/g7confirm/career_source_freeze_design.py", 34538,
     "fdc450dacee1ade01c0b361fc7028bd3b6df5ffde21946635c272323fe98544e"),
    ("v3/g7_confirmatory/career_source_freeze_design.schema.json", 8904,
     "d43874b2411d4e594cd3d5aa4d1ff1eb04e06a50ed0200726f84130c63fe7675"),
    ("v3/g7_confirmatory/artifacts/career_source_manifest_matrix_m13.json", 26460,
     "85917e3be3655a06012b68a21cb08355064367ab8b2b5dbcf4c75b05e08845b0"),
    ("v3/g7_confirmatory/g7confirm/career_source_manifest_validator.py", 34607,
     "2d59ec65edc3fd78c52053bab0a95d67352077bdff5f7ad184bd4b53e43beaca"),
    ("v3/g7_confirmatory/career_source_manifest_matrix.schema.json", 7444,
     "4c96583aa09ba26175fca3117d6cc979a5e79016db9f8bc765b46f4fa1425d0f"),
    ("v3/g7_confirmatory/M13_CAREER_SOURCE_MANIFEST_VALIDATOR_REPORT.md", 5901,
     "862b8fc6edca22d48118eca8424e99c2c693dc552ff068852504e2b359401e34"),
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _content_id(prefix: str, value: Any, *, omit: Sequence[str] = ()) -> str:
    content = json.loads(_canonical_json(value))
    if isinstance(content, dict):
        for key in omit:
            content.pop(key, None)
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def packet_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m14reviewpacket", payload, omit=("packet_id",))


def _snapshot_manifest() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "bytes": size,
            "sha256": digest,
            "git_tracked_at_base_commit": True,
        }
        for path, size, digest in REVIEW_SNAPSHOT
    ]


def verify_review_snapshot(repo_root: str | Path) -> list[str]:
    """Return exact-byte mismatches for the declared M14 review snapshot."""

    root = Path(repo_root)
    issues: list[str] = []
    for relative_path, expected_bytes, expected_sha256 in REVIEW_SNAPSHOT:
        path = root / relative_path
        if not path.is_file():
            issues.append(f"missing:{relative_path}")
            continue
        content = path.read_bytes()
        if len(content) != expected_bytes:
            issues.append(f"byte_count_mismatch:{relative_path}")
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected_sha256:
            issues.append(f"sha256_mismatch:{relative_path}")
    return issues


def _open_prerequisite(item_id: str, description: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "description": description,
        "status": OPEN_STATUS,
        "evidence_id": None,
    }


@dataclass(frozen=True)
class CareerSourceReviewPacket:
    """Immutable semantic representation of the M14 review packet."""

    _canonical_content: str

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        self._validate(copied)
        object.__setattr__(self, "_canonical_content", _canonical_json(copied))

    @property
    def packet_id(self) -> str:
        return self.to_dict()["packet_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    @staticmethod
    def _validate(content: Mapping[str, Any]) -> None:
        expected_fields = {
            "schema_version",
            "packet_id",
            "milestone",
            "title",
            "status",
            "governance",
            "source_lineage",
            "exact_review_snapshot",
            "review_scope",
            "prerequisite_register",
            "proposed_generation_envelopes",
            "independent_review_protocol",
            "abort_conditions",
            "canonical_status",
            "limitations",
            "next_gate",
        }
        if set(content) != expected_fields:
            raise ContractViolation("M14 review-packet top-level fields drift")
        if content["schema_version"] != SOURCE_REVIEW_PACKET_SCHEMA_VERSION:
            raise ContractViolation("unsupported M14 review-packet schema_version")
        if content["milestone"] != "M14":
            raise ContractViolation("source review packet must be M14")
        if content["packet_id"] != packet_id_for(content):
            raise ContractViolation("M14 review packet_id mismatch")
        if content["status"] != PACKET_STATUS:
            raise ContractViolation("M14 packet approval status drift")
        if content["governance"] != REQUIRED_GOVERNANCE:
            raise ContractViolation("M14 governance boundary drift")
        if content["source_lineage"] != {
            "m13_matrix_id": M13_MATRIX_ID,
            "m13_base_commit": M13_BASE_COMMIT,
            "m14_decision": M14_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        }:
            raise ContractViolation("M14 source lineage drift")
        if content["exact_review_snapshot"] != _snapshot_manifest():
            raise ContractViolation("M14 exact review snapshot drift")
        _validate_review_scope(content["review_scope"])
        _validate_prerequisites(content["prerequisite_register"])
        _validate_generation_envelopes(content["proposed_generation_envelopes"])
        _validate_review_protocol(content["independent_review_protocol"])
        if set(content["abort_conditions"]) != {
            "review_snapshot_byte_or_commit_mismatch",
            "any_prerequisite_missing_or_changed",
            "reviewer_identity_conflict_or_reuse",
            "review_receipt_not_bound_to_exact_packet",
            "partition_overlap_or_outcome_informed_assignment",
            "authority_observation_or_candidate_scope_expansion",
            "treatment_detector_confirmation_or_evaluation_outcome_access",
            "unreviewed_numeric_engineering_or_model_choice",
            "unbounded_or_campaign_scale_execution_request",
            "any_external_service_or_runtime_access_before_separate_authorization",
        }:
            raise ContractViolation("M14 abort conditions drift")
        if content["canonical_status"] != {
            "packet": PACKET_STATUS,
            "independent_review": REVIEW_STATUS,
            "S_source_package": "UNBUILT_DESIGN_ONLY",
            "M_source_package": "UNBUILT_DESIGN_ONLY",
            "partition_assignments": "UNASSIGNED_DESIGN_ONLY",
            "S_scientific_threshold": THRESHOLD_STATUS,
            "M_scientific_threshold": THRESHOLD_STATUS,
            "S_real_resource": REAL_RESOURCE_HOLD,
            "M_real_resource": REAL_RESOURCE_HOLD,
            "evaluation": "SEALED",
            "campaign": "HOLD",
        }:
            raise ContractViolation("M14 canonical status drift")
        if set(content["limitations"]) != {
            "packet_prepared_by_non_independent_executor",
            "no_independent_review_or_disposition_recorded",
            "no_real_source_partition_or_runtime_instantiated",
            "no_numeric_engineering_or_model_choice",
            "no_scientific_threshold_or_resource_admission",
            "no_physical_ranking_or_factor_effect_claim",
            "no_evaluation_or_campaign_authorization",
        }:
            raise ContractViolation("M14 limitations drift")
        if content["next_gate"] != {
            "id": "M15_post_independent_review_resolution",
            "requires_two_bound_independent_review_receipts": True,
            "permitted_without_receipts": "packet_revision_only",
            "real_source_generation_authorized": False,
            "real_partition_assignment_authorized": False,
            "model_or_embedding_call": False,
            "simulator_or_detector_access": False,
            "evaluation_access": False,
        }:
            raise ContractViolation("unexpected M14 next gate")


def _validate_review_scope(scope: Mapping[str, Any]) -> None:
    if set(scope) != {"questions", "out_of_scope"}:
        raise ContractViolation("M14 review scope fields drift")
    if set(scope["questions"]) != set(REVIEW_QUESTIONS):
        raise ContractViolation("M14 review questions drift")
    if set(scope["out_of_scope"]) != {
        "scientific_threshold_selection",
        "real_source_or_partition_generation",
        "detector_calibration_or_stealth_claim",
        "treatment_effect_estimation",
        "evaluation_or_campaign_execution",
    }:
        raise ContractViolation("M14 review scope expanded")


def _validate_prerequisites(register: Mapping[str, Any]) -> None:
    expected_ids = {
        "S": {
            "tracked_deterministic_generator",
            "operating_cell_registry",
            "development_seed_registry",
            "symmetric_perturbation_schedule",
            "numeric_precision_policy",
            "S_source_partition_assignment",
        },
        "M": {
            "tracked_deterministic_ranker",
            "algorithm_family_selection",
            "engineering_instantiation_manifest",
            "primary_endpoint_definition",
            "feature_schema",
            "development_seed_registry",
            "M_source_partition_assignment",
        },
        "shared": {
            "independent_reviewer_identities",
            "two_bound_acceptance_receipts",
            "bounded_source_generation_authorization",
        },
    }
    if set(register) != set(expected_ids):
        raise ContractViolation("M14 prerequisite factors drift")
    for factor, expected in expected_ids.items():
        items = register[factor]
        if {item.get("id") for item in items} != expected:
            raise ContractViolation(f"M14 {factor} prerequisite IDs drift")
        for item in items:
            if set(item) != {"id", "description", "status", "evidence_id"}:
                raise ContractViolation("M14 prerequisite fields drift")
            if item["status"] != OPEN_STATUS or item["evidence_id"] is not None:
                raise ContractViolation("M14 prerequisite was self-satisfied")


def _validate_generation_envelopes(envelopes: Mapping[str, Any]) -> None:
    if set(envelopes) != {"S", "M"}:
        raise ContractViolation("M14 requires separate S and M envelopes")
    common = {
        "status",
        "purpose",
        "future_runtime_dependency",
        "numeric_values",
        "allowed_outputs",
        "prohibited_access",
    }
    for factor, envelope in envelopes.items():
        expected = common | ({"authority"} if factor == "S" else {
            "candidate_binding", "ranker_constraints"})
        if set(envelope) != expected:
            raise ContractViolation(f"M14 {factor} generation fields drift")
        if envelope["status"] != "NOT_AUTHORIZED_REVIEW_PROPOSAL_ONLY":
            raise ContractViolation(f"M14 {factor} generation was authorized")
        if envelope["purpose"] != f"{factor}_development_source_derivation_only":
            raise ContractViolation(f"M14 {factor} purpose drift")
        if envelope["future_runtime_dependency"] != (
                "requires_separate_bounded_simulator_overlay_after_review"):
            raise ContractViolation(f"M14 {factor} runtime boundary drift")
        if not envelope["numeric_values"] or any(
                value is not None for value in envelope["numeric_values"].values()):
            raise ContractViolation(f"M14 {factor} numeric value was selected")
        required_prohibited = {
            "model_service",
            "embedding_service",
            "detector_or_alarm_outcomes",
            "treatment_or_confirmation_outcomes",
            "evaluation_records",
            "other_factor_derived_resource",
            "online_update",
        }
        if set(envelope["prohibited_access"]) != required_prohibited:
            raise ContractViolation(f"M14 {factor} prohibited access drift")
    if envelopes["S"]["authority"] != {
        "surface": "single_ev_aggregator_setpoint",
        "controlled_variable": "active_charging_setpoint",
        "controlled_device_count": 1,
        "response_variable": "exposed_bus_voltage_telemetry",
        "reactive_power_axis": "outside_primary_scope_not_zero_imputed",
    }:
        raise ContractViolation("M14 S authority drift")
    if set(envelopes["S"]["numeric_values"]) != {
        "probe_amplitude",
        "operating_cell_count",
        "seed_count",
        "episode_count",
        "runtime_cap",
    }:
        raise ContractViolation("M14 S numeric slot identities drift")
    if envelopes["S"]["allowed_outputs"] != [
        "content_addressed_raw_input_manifest",
        "content_addressed_S_relationship_resource",
    ]:
        raise ContractViolation("M14 S output scope drift")
    if envelopes["M"]["candidate_binding"] != {
        "ordered_candidate_ids": list(M9_CANDIDATE_IDS),
        "physical_instantiation_manifest": None,
        "primary_endpoint_definition": None,
    }:
        raise ContractViolation("M14 M candidate binding drift")
    if envelopes["M"]["ranker_constraints"] != {
        "algorithm_family": None,
        "new_raw_observations": False,
        "online_update": False,
        "uses_S_derived_resource": False,
        "tie_break_rule": "frozen_M9_candidate_order",
    }:
        raise ContractViolation("M14 M ranker constraints drift")
    if set(envelopes["M"]["numeric_values"]) != {
        "training_block_count",
        "context_count",
        "seed_count",
        "model_complexity_cap",
        "runtime_cap",
    }:
        raise ContractViolation("M14 M numeric slot identities drift")
    if envelopes["M"]["allowed_outputs"] != [
        "content_addressed_training_input_manifest",
        "content_addressed_frozen_ranker",
        "content_addressed_M_ranking_resource",
    ]:
        raise ContractViolation("M14 M output scope drift")


def _validate_review_protocol(protocol: Mapping[str, Any]) -> None:
    if set(protocol) != {
        "required_roles",
        "required_distinct_reviewers",
        "packet_preparer_may_review",
        "allowed_dispositions",
        "disposition_slots",
        "acceptance_rule",
        "snapshot_mutation_policy",
    }:
        raise ContractViolation("M14 review protocol fields drift")
    roles = [
        "independent_data_lineage_reviewer",
        "independent_domain_method_reviewer",
    ]
    if protocol["required_roles"] != roles:
        raise ContractViolation("M14 reviewer roles drift")
    if protocol["required_distinct_reviewers"] != 2:
        raise ContractViolation("M14 reviewer count drift")
    if protocol["packet_preparer_may_review"] is not False:
        raise ContractViolation("M14 self-review was enabled")
    if protocol["allowed_dispositions"] != [
        "accept_exact_packet",
        "request_changes",
        "reject",
    ]:
        raise ContractViolation("M14 review disposition vocabulary drift")
    slots = protocol["disposition_slots"]
    if [slot.get("reviewer_role") for slot in slots] != roles:
        raise ContractViolation("M14 disposition slot roles drift")
    for slot in slots:
        if slot != {
            "reviewer_role": slot["reviewer_role"],
            "reviewer_id": None,
            "disposition": None,
            "comments_sha256": None,
            "bound_packet_id": None,
            "receipt_id": None,
            "status": REVIEW_STATUS,
        }:
            raise ContractViolation("M14 review disposition was populated")
    if protocol["acceptance_rule"] != (
            "two_distinct_non_preparer_acceptances_bound_to_exact_packet"):
        raise ContractViolation("M14 acceptance rule drift")
    if protocol["snapshot_mutation_policy"] != (
            "any_byte_change_invalidates_both_reviews"):
        raise ContractViolation("M14 snapshot mutation policy drift")


def _prohibited_access() -> list[str]:
    return sorted({
        "model_service",
        "embedding_service",
        "detector_or_alarm_outcomes",
        "treatment_or_confirmation_outcomes",
        "evaluation_records",
        "other_factor_derived_resource",
        "online_update",
    })


def build_career_source_review_packet() -> CareerSourceReviewPacket:
    """Build the canonical M14 independent-review packet."""

    prerequisites = {
        "S": [
            _open_prerequisite("tracked_deterministic_generator",
                               "Tracked deterministic S source generator"),
            _open_prerequisite("operating_cell_registry",
                               "Frozen development operating-cell registry"),
            _open_prerequisite("development_seed_registry",
                               "Frozen S development-seed registry"),
            _open_prerequisite("symmetric_perturbation_schedule",
                               "Frozen paired symmetric probe schedule"),
            _open_prerequisite("numeric_precision_policy",
                               "Frozen units, precision, and rounding policy"),
            _open_prerequisite("S_source_partition_assignment",
                               "Outcome-blind S source partition assignment"),
        ],
        "M": [
            _open_prerequisite("tracked_deterministic_ranker",
                               "Tracked deterministic M ranker implementation"),
            _open_prerequisite("algorithm_family_selection",
                               "Prospective ranker-family selection"),
            _open_prerequisite("engineering_instantiation_manifest",
                               "M9-ID-preserving physical instantiation"),
            _open_prerequisite("primary_endpoint_definition",
                               "Frozen primary-endpoint computation"),
            _open_prerequisite("feature_schema",
                               "Frozen no-new-observation feature schema"),
            _open_prerequisite("development_seed_registry",
                               "Frozen M development-seed registry"),
            _open_prerequisite("M_source_partition_assignment",
                               "Outcome-blind M source partition assignment"),
        ],
        "shared": [
            _open_prerequisite("independent_reviewer_identities",
                               "Two distinct non-preparer reviewers"),
            _open_prerequisite("two_bound_acceptance_receipts",
                               "Two acceptances bound to exact packet bytes"),
            _open_prerequisite("bounded_source_generation_authorization",
                               "Separate bounded development authorization"),
        ],
    }
    content: dict[str, Any] = {
        "schema_version": SOURCE_REVIEW_PACKET_SCHEMA_VERSION,
        "packet_id": "pending",
        "milestone": "M14",
        "title": "CAREER independent clean-source generation review packet",
        "status": PACKET_STATUS,
        "governance": dict(REQUIRED_GOVERNANCE),
        "source_lineage": {
            "m13_matrix_id": M13_MATRIX_ID,
            "m13_base_commit": M13_BASE_COMMIT,
            "m14_decision": M14_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        },
        "exact_review_snapshot": _snapshot_manifest(),
        "review_scope": {
            "questions": sorted(REVIEW_QUESTIONS),
            "out_of_scope": sorted({
                "scientific_threshold_selection",
                "real_source_or_partition_generation",
                "detector_calibration_or_stealth_claim",
                "treatment_effect_estimation",
                "evaluation_or_campaign_execution",
            }),
        },
        "prerequisite_register": prerequisites,
        "proposed_generation_envelopes": {
            "S": {
                "status": "NOT_AUTHORIZED_REVIEW_PROPOSAL_ONLY",
                "purpose": "S_development_source_derivation_only",
                "future_runtime_dependency": (
                    "requires_separate_bounded_simulator_overlay_after_review"
                ),
                "authority": {
                    "surface": "single_ev_aggregator_setpoint",
                    "controlled_variable": "active_charging_setpoint",
                    "controlled_device_count": 1,
                    "response_variable": "exposed_bus_voltage_telemetry",
                    "reactive_power_axis": (
                        "outside_primary_scope_not_zero_imputed"
                    ),
                },
                "numeric_values": {
                    "probe_amplitude": None,
                    "operating_cell_count": None,
                    "seed_count": None,
                    "episode_count": None,
                    "runtime_cap": None,
                },
                "allowed_outputs": [
                    "content_addressed_raw_input_manifest",
                    "content_addressed_S_relationship_resource",
                ],
                "prohibited_access": _prohibited_access(),
            },
            "M": {
                "status": "NOT_AUTHORIZED_REVIEW_PROPOSAL_ONLY",
                "purpose": "M_development_source_derivation_only",
                "future_runtime_dependency": (
                    "requires_separate_bounded_simulator_overlay_after_review"
                ),
                "candidate_binding": {
                    "ordered_candidate_ids": list(M9_CANDIDATE_IDS),
                    "physical_instantiation_manifest": None,
                    "primary_endpoint_definition": None,
                },
                "ranker_constraints": {
                    "algorithm_family": None,
                    "new_raw_observations": False,
                    "online_update": False,
                    "uses_S_derived_resource": False,
                    "tie_break_rule": "frozen_M9_candidate_order",
                },
                "numeric_values": {
                    "training_block_count": None,
                    "context_count": None,
                    "seed_count": None,
                    "model_complexity_cap": None,
                    "runtime_cap": None,
                },
                "allowed_outputs": [
                    "content_addressed_training_input_manifest",
                    "content_addressed_frozen_ranker",
                    "content_addressed_M_ranking_resource",
                ],
                "prohibited_access": _prohibited_access(),
            },
        },
        "independent_review_protocol": {
            "required_roles": [
                "independent_data_lineage_reviewer",
                "independent_domain_method_reviewer",
            ],
            "required_distinct_reviewers": 2,
            "packet_preparer_may_review": False,
            "allowed_dispositions": [
                "accept_exact_packet",
                "request_changes",
                "reject",
            ],
            "disposition_slots": [
                {
                    "reviewer_role": "independent_data_lineage_reviewer",
                    "reviewer_id": None,
                    "disposition": None,
                    "comments_sha256": None,
                    "bound_packet_id": None,
                    "receipt_id": None,
                    "status": REVIEW_STATUS,
                },
                {
                    "reviewer_role": "independent_domain_method_reviewer",
                    "reviewer_id": None,
                    "disposition": None,
                    "comments_sha256": None,
                    "bound_packet_id": None,
                    "receipt_id": None,
                    "status": REVIEW_STATUS,
                },
            ],
            "acceptance_rule": (
                "two_distinct_non_preparer_acceptances_bound_to_exact_packet"
            ),
            "snapshot_mutation_policy": (
                "any_byte_change_invalidates_both_reviews"
            ),
        },
        "abort_conditions": sorted({
            "review_snapshot_byte_or_commit_mismatch",
            "any_prerequisite_missing_or_changed",
            "reviewer_identity_conflict_or_reuse",
            "review_receipt_not_bound_to_exact_packet",
            "partition_overlap_or_outcome_informed_assignment",
            "authority_observation_or_candidate_scope_expansion",
            "treatment_detector_confirmation_or_evaluation_outcome_access",
            "unreviewed_numeric_engineering_or_model_choice",
            "unbounded_or_campaign_scale_execution_request",
            "any_external_service_or_runtime_access_before_separate_authorization",
        }),
        "canonical_status": {
            "packet": PACKET_STATUS,
            "independent_review": REVIEW_STATUS,
            "S_source_package": "UNBUILT_DESIGN_ONLY",
            "M_source_package": "UNBUILT_DESIGN_ONLY",
            "partition_assignments": "UNASSIGNED_DESIGN_ONLY",
            "S_scientific_threshold": THRESHOLD_STATUS,
            "M_scientific_threshold": THRESHOLD_STATUS,
            "S_real_resource": REAL_RESOURCE_HOLD,
            "M_real_resource": REAL_RESOURCE_HOLD,
            "evaluation": "SEALED",
            "campaign": "HOLD",
        },
        "limitations": sorted({
            "packet_prepared_by_non_independent_executor",
            "no_independent_review_or_disposition_recorded",
            "no_real_source_partition_or_runtime_instantiated",
            "no_numeric_engineering_or_model_choice",
            "no_scientific_threshold_or_resource_admission",
            "no_physical_ranking_or_factor_effect_claim",
            "no_evaluation_or_campaign_authorization",
        }),
        "next_gate": {
            "id": "M15_post_independent_review_resolution",
            "requires_two_bound_independent_review_receipts": True,
            "permitted_without_receipts": "packet_revision_only",
            "real_source_generation_authorized": False,
            "real_partition_assignment_authorized": False,
            "model_or_embedding_call": False,
            "simulator_or_detector_access": False,
            "evaluation_access": False,
        },
    }
    content["packet_id"] = packet_id_for(content)
    return CareerSourceReviewPacket(content)


def load_career_source_review_packet(path: str | Path) -> CareerSourceReviewPacket:
    """Load and semantically validate a checked-in M14 review packet."""

    return CareerSourceReviewPacket(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )
