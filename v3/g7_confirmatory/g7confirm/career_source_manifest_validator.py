"""Offline M13 synthetic validator for CAREER clean-source manifests.

The validator exercises M12 rules with synthetic content addresses, block IDs,
and review identities. A passing fixture is structural evidence only and can
never freeze a real source, issue a real review, or admit a real resource.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_resource_admission import REAL_RESOURCE_HOLD
from .career_source_freeze_design import (
    M9_CANDIDATE_IDS,
    PARTITION_ROLES,
    REVIEW_STATUS,
    build_career_source_freeze_design,
)
from .career_threshold_hold import THRESHOLD_STATUS
from .orchestration_contract import ContractViolation


SOURCE_MANIFEST_MATRIX_SCHEMA_VERSION = (
    "grideval-career-source-manifest-matrix/v1"
)
SOURCE_PACKAGE_ENVELOPE_SCHEMA_VERSION = (
    "grideval-career-source-package-envelope/v1"
)
SOURCE_PACKAGE_RECEIPT_SCHEMA_VERSION = (
    "grideval-career-source-package-receipt/v1"
)
M12_CONTRACT_ID = (
    "careersourcefreeze_648776649fcaa43a3ecce5fab19aced608c427646b086c0f6"
    "bc2128a611a61f3"
)
M13_DECISION_ID = "dec_01M1DNSMSJG0PP22RA8GC40CXX"
POSITIVE_VERDICT = "PASS_SYNTHETIC_STRUCTURE_ONLY"
NEGATIVE_VERDICT = "REJECTED_FAIL_CLOSED"

SHA256_RE = re.compile(r"^sha256_[0-9a-f]{64}$")

REQUIRED_EXTERNAL_ACCESS = {
    "model_calls": 0,
    "embedding_calls": 0,
    "real_tool_calls": 0,
    "simulator_calls": 0,
    "detector_calls": 0,
    "actuator_calls": 0,
    "evaluation_records_read": 0,
}

REQUIRED_PROHIBITED_ACCESS = {
    "treatment_arm_outcomes": False,
    "detector_or_alarm_outcomes": False,
    "evaluation_records": False,
    "factor_confirmation_outcomes": False,
    "independent_validation_outcomes_during_derivation": False,
    "other_factor_derived_resource": False,
    "online_feedback_or_updates": False,
    "untracked_or_unhashed_source_bytes": False,
}

REQUIRED_GOVERNANCE = {
    "development_only": True,
    "synthetic_fixtures_only": True,
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


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _content_id(prefix: str, value: Any, *, omit: Sequence[str] = ()) -> str:
    content = json.loads(_canonical_json(value))
    if isinstance(content, dict):
        for key in omit:
            content.pop(key, None)
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def envelope_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m13envelope", payload, omit=("envelope_id",))


def package_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m13package", payload, omit=("source_package_id",))


def partition_manifest_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id(
        "m13partitions", payload, omit=("partition_manifest_id",)
    )


def review_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m13review", payload, omit=("review_id",))


def receipt_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m13receipt", payload, omit=("receipt_id",))


def matrix_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m13matrix", payload, omit=("matrix_id",))


def _synthetic_hash(label: str) -> str:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return f"sha256_{digest}"


def _review(
    *, stage: str, reviewer_id: str, author_id: str, package_id: str
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "review_id": "pending",
        "stage": stage,
        "reviewer_id": reviewer_id,
        "author_id": author_id,
        "bound_source_package_id": package_id,
        "decision": POSITIVE_VERDICT,
        "synthetic_fixture": True,
        "real_review_status_after": REVIEW_STATUS,
    }
    payload["review_id"] = review_id_for(payload)
    return payload


def build_synthetic_envelope(*, factor: str, fixture_id: str) -> dict[str, Any]:
    """Build one structurally positive synthetic source-package envelope."""

    if factor not in {"S", "M"}:
        raise ContractViolation("M13 synthetic envelope factor must be S or M")
    m12 = build_career_source_freeze_design().to_dict()
    profile = copy.deepcopy(m12["clean_source_profiles"][factor])
    slots = {
        name: _synthetic_hash(f"{fixture_id}:{factor}:{name}")
        for name in profile["empirical_slots"]
    }
    derivation = copy.deepcopy(profile["derivation_contract"])
    if factor == "M":
        derivation["algorithm_family"] = (
            "synthetic_fixture_deterministic_ranker_only"
        )
    package: dict[str, Any] = {
        "source_package_id": "pending",
        "profile_id": profile["profile_id"],
        "factor": factor,
        "synthetic_fixture": True,
        "tracked_source": True,
        "content_addresses": slots,
        "information_grant": copy.deepcopy(profile["information_grant"]),
        "derivation_contract": derivation,
        "output_manifest_template": copy.deepcopy(
            profile["output_manifest_template"]
        ),
    }
    package["source_package_id"] = package_id_for(package)

    assignments = {
        role: f"synthetic_{fixture_id}_{index:02d}"
        for index, role in enumerate(PARTITION_ROLES, start=1)
    }
    partition_manifest: dict[str, Any] = {
        "partition_manifest_id": "pending",
        "sample_identity": (
            "factor_role_run_seed_operating_cell_episode_block"
        ),
        "assignments": assignments,
        "outcomes_observed_before_assignment": False,
        "synthetic_fixture": True,
        "real_partition_status_after": "UNASSIGNED_DESIGN_ONLY",
    }
    partition_manifest["partition_manifest_id"] = (
        partition_manifest_id_for(partition_manifest)
    )
    author_id = f"synthetic_author_{factor}"
    reviews = [
        _review(
            stage="source_lineage_and_partition_review",
            reviewer_id=f"synthetic_lineage_reviewer_{factor}",
            author_id=author_id,
            package_id=package["source_package_id"],
        ),
        _review(
            stage="capability_semantics_and_reproducibility_review",
            reviewer_id=f"synthetic_method_reviewer_{factor}",
            author_id=author_id,
            package_id=package["source_package_id"],
        ),
    ]
    envelope: dict[str, Any] = {
        "schema_version": SOURCE_PACKAGE_ENVELOPE_SCHEMA_VERSION,
        "envelope_id": "pending",
        "m12_contract_id": M12_CONTRACT_ID,
        "fixture_id": fixture_id,
        "factor": factor,
        "synthetic_fixture": True,
        "source_package": package,
        "partition_manifest": partition_manifest,
        "review_receipts": reviews,
        "prohibited_access": dict(REQUIRED_PROHIBITED_ACCESS),
        "external_access": dict(REQUIRED_EXTERNAL_ACCESS),
    }
    envelope["envelope_id"] = envelope_id_for(envelope)
    return envelope


def _validate_source_package(
    factor: str, package: Mapping[str, Any], expected: Mapping[str, Any]
) -> set[str]:
    codes: set[str] = set()
    required_fields = {
        "source_package_id",
        "profile_id",
        "factor",
        "synthetic_fixture",
        "tracked_source",
        "content_addresses",
        "information_grant",
        "derivation_contract",
        "output_manifest_template",
    }
    if set(package) != required_fields:
        return {"source_package_fields_drift"}
    if package["source_package_id"] != package_id_for(package):
        codes.add("source_package_content_address_mismatch")
    if package["profile_id"] != expected["profile_id"]:
        codes.add("profile_identity_drift")
    if package["factor"] != factor or package["synthetic_fixture"] is not True:
        codes.add("non_synthetic_or_factor_drift")
    if package["tracked_source"] is not True:
        codes.add("untracked_source")
    addresses = package["content_addresses"]
    if not isinstance(addresses, dict) or set(addresses) != set(
            expected["empirical_slots"]):
        codes.add("content_address_slots_drift")
    else:
        for slot, value in addresses.items():
            if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
                codes.add(f"missing_or_invalid_content_address:{slot}")
    if package["information_grant"] != expected["information_grant"]:
        codes.add("information_grant_drift")
    if package["output_manifest_template"] != (
            expected["output_manifest_template"]):
        codes.add("output_manifest_template_drift")

    derivation = package["derivation_contract"]
    expected_derivation = copy.deepcopy(expected["derivation_contract"])
    if factor == "M":
        expected_derivation["algorithm_family"] = (
            "synthetic_fixture_deterministic_ranker_only"
        )
    if not isinstance(derivation, dict):
        return codes | {"derivation_contract_fields_drift"}
    if set(derivation) != set(expected_derivation):
        return codes | {"derivation_contract_fields_drift"}
    if factor == "S":
        if (
            derivation["authority_surface"] != (
                expected_derivation["authority_surface"]
            )
            or derivation["controlled_device_count"] != 1
            or derivation["other_device_authority"] is not False
        ):
            codes.add("S_authority_expansion")
        if derivation["reactive_power_axis"] != (
                "outside_primary_scope_not_zero_imputed"):
            codes.add("S_reactive_axis_scope_drift")
        exempt = {
            "authority_surface",
            "controlled_device_count",
            "other_device_authority",
            "reactive_power_axis",
        }
    else:
        if (
            derivation["candidate_library_fingerprint"] != (
                expected_derivation["candidate_library_fingerprint"]
            )
            or derivation["ordered_candidate_ids"] != list(M9_CANDIDATE_IDS)
        ):
            codes.add("M_candidate_library_drift")
        if derivation["new_raw_observations_added"] is not False:
            codes.add("M_new_observation_grant")
        if derivation["online_update"] is not False:
            codes.add("M_online_update_enabled")
        if derivation["uses_S_derived_resource"] is not False:
            codes.add("M_cross_factor_resource_dependency")
        exempt = {
            "candidate_library_fingerprint",
            "ordered_candidate_ids",
            "new_raw_observations_added",
            "online_update",
            "uses_S_derived_resource",
        }
    for key, value in expected_derivation.items():
        if key not in exempt and derivation[key] != value:
            codes.add("derivation_contract_semantics_drift")
            break
    return codes


def _validate_partition_manifest(manifest: Mapping[str, Any]) -> set[str]:
    required_fields = {
        "partition_manifest_id",
        "sample_identity",
        "assignments",
        "outcomes_observed_before_assignment",
        "synthetic_fixture",
        "real_partition_status_after",
    }
    if set(manifest) != required_fields:
        return {"partition_manifest_fields_drift"}
    codes: set[str] = set()
    if manifest["partition_manifest_id"] != partition_manifest_id_for(manifest):
        codes.add("partition_manifest_content_address_mismatch")
    if manifest["sample_identity"] != (
            "factor_role_run_seed_operating_cell_episode_block"):
        codes.add("partition_sample_identity_drift")
    assignments = manifest["assignments"]
    if not isinstance(assignments, dict) or set(assignments) != set(
            PARTITION_ROLES):
        codes.add("partition_assignment_roles_drift")
    elif (
        any(not isinstance(value, str) or not value for value in assignments.values())
        or len(set(assignments.values())) != len(assignments)
    ):
        codes.add("partition_overlap_or_invalid_assignment")
    if manifest["outcomes_observed_before_assignment"] is not False:
        codes.add("partition_assignment_after_outcome_access")
    if manifest["synthetic_fixture"] is not True:
        codes.add("real_partition_assignment_not_authorized")
    if manifest["real_partition_status_after"] != "UNASSIGNED_DESIGN_ONLY":
        codes.add("real_partition_status_transition")
    return codes


def _validate_reviews(
    reviews: Any, *, source_package_id: str
) -> set[str]:
    if not isinstance(reviews, list) or len(reviews) != 2:
        return {"review_count_or_shape_drift"}
    expected_stages = [
        "source_lineage_and_partition_review",
        "capability_semantics_and_reproducibility_review",
    ]
    codes: set[str] = set()
    reviewer_ids: list[str] = []
    for index, review in enumerate(reviews):
        if not isinstance(review, dict) or set(review) != {
            "review_id",
            "stage",
            "reviewer_id",
            "author_id",
            "bound_source_package_id",
            "decision",
            "synthetic_fixture",
            "real_review_status_after",
        }:
            codes.add("review_count_or_shape_drift")
            continue
        if review["review_id"] != review_id_for(review):
            codes.add("review_content_address_mismatch")
        if review["stage"] != expected_stages[index]:
            codes.add("review_stage_order_drift")
        if review["bound_source_package_id"] != source_package_id:
            codes.add("review_package_binding_mismatch")
        if review["decision"] != POSITIVE_VERDICT:
            codes.add("review_decision_overclaim_or_drift")
        if review["synthetic_fixture"] is not True:
            codes.add("real_review_not_authorized")
        if review["real_review_status_after"] != REVIEW_STATUS:
            codes.add("real_review_status_transition")
        if not isinstance(review["reviewer_id"], str) or not review[
                "reviewer_id"]:
            codes.add("reviewer_independence_violation")
        else:
            reviewer_ids.append(review["reviewer_id"])
        if review["reviewer_id"] == review["author_id"]:
            codes.add("reviewer_independence_violation")
    if len(reviewer_ids) != 2 or len(set(reviewer_ids)) != 2:
        codes.add("reviewer_independence_violation")
    return codes


def violation_codes(envelope: Mapping[str, Any]) -> list[str]:
    """Return deterministic fail-closed reason codes for one envelope."""

    copied = json.loads(_canonical_json(envelope))
    required_fields = {
        "schema_version",
        "envelope_id",
        "m12_contract_id",
        "fixture_id",
        "factor",
        "synthetic_fixture",
        "source_package",
        "partition_manifest",
        "review_receipts",
        "prohibited_access",
        "external_access",
    }
    if set(copied) != required_fields:
        return ["envelope_fields_drift"]
    codes: set[str] = set()
    if copied["schema_version"] != SOURCE_PACKAGE_ENVELOPE_SCHEMA_VERSION:
        codes.add("envelope_schema_drift")
    if copied["envelope_id"] != envelope_id_for(copied):
        codes.add("envelope_content_address_mismatch")
    if copied["m12_contract_id"] != M12_CONTRACT_ID:
        codes.add("M12_contract_lineage_drift")
    factor = copied["factor"]
    if factor not in {"S", "M"}:
        return sorted(codes | {"unknown_factor"})
    if copied["synthetic_fixture"] is not True:
        codes.add("real_source_validation_not_authorized")
    m12 = build_career_source_freeze_design().to_dict()
    package = copied["source_package"]
    if not isinstance(package, dict):
        codes.add("source_package_fields_drift")
        source_package_id = "missing"
    else:
        codes.update(
            _validate_source_package(
                factor, package, m12["clean_source_profiles"][factor]
            )
        )
        source_package_id = package.get("source_package_id", "missing")
    partition_manifest = copied["partition_manifest"]
    if not isinstance(partition_manifest, dict):
        codes.add("partition_manifest_fields_drift")
    else:
        codes.update(_validate_partition_manifest(partition_manifest))
    codes.update(
        _validate_reviews(
            copied["review_receipts"],
            source_package_id=source_package_id,
        )
    )
    access = copied["prohibited_access"]
    if access != REQUIRED_PROHIBITED_ACCESS:
        if isinstance(access, dict) and set(access) == set(
                REQUIRED_PROHIBITED_ACCESS):
            if any(value is not False for value in access.values()):
                codes.add("prohibited_outcome_or_resource_access")
            else:
                codes.add("prohibited_access_accounting_drift")
        else:
            codes.add("prohibited_access_accounting_drift")
    if copied["external_access"] != REQUIRED_EXTERNAL_ACCESS:
        codes.add("external_access_or_accounting_drift")
    return sorted(codes)


def evaluate_source_package(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one synthetic envelope and return a sealed receipt."""

    copied = json.loads(_canonical_json(envelope))
    reasons = violation_codes(copied)
    accepted = not reasons
    payload: dict[str, Any] = {
        "schema_version": SOURCE_PACKAGE_RECEIPT_SCHEMA_VERSION,
        "receipt_id": "pending",
        "m12_contract_id": M12_CONTRACT_ID,
        "fixture_id": copied.get("fixture_id", "missing_fixture_id"),
        "envelope_id": copied.get("envelope_id", "missing_envelope_id"),
        "factor": copied.get("factor", "unknown"),
        "accepted": accepted,
        "verdict": POSITIVE_VERDICT if accepted else NEGATIVE_VERDICT,
        "reason_codes": reasons,
        "real_source_status_after": "UNBUILT_DESIGN_ONLY",
        "real_partition_status_after": "UNASSIGNED_DESIGN_ONLY",
        "real_review_status_after": REVIEW_STATUS,
        "scientific_threshold_status_after": THRESHOLD_STATUS,
        "real_resource_status_after": REAL_RESOURCE_HOLD,
        "evaluation_status_after": "SEALED",
        "external_access": dict(REQUIRED_EXTERNAL_ACCESS),
        "interpretation": "source_manifest_validator_structure_only",
    }
    payload["receipt_id"] = receipt_id_for(payload)
    return payload


MUTATION_CASES = (
    ("S_partition_overlap", "S", "partition_overlap",
     "partition_overlap_or_invalid_assignment"),
    ("S_untracked_source", "S", "untracked_source", "untracked_source"),
    ("S_authority_expansion", "S", "authority_expansion",
     "S_authority_expansion"),
    ("S_reactive_zero_imputation", "S", "reactive_zero_imputation",
     "S_reactive_axis_scope_drift"),
    ("M_missing_physical_instantiation", "M",
     "missing_physical_instantiation",
     "missing_or_invalid_content_address:engineering_instantiation_manifest_sha256"),
    ("M_candidate_drift", "M", "candidate_drift",
     "M_candidate_library_drift"),
    ("M_new_observation", "M", "new_observation",
     "M_new_observation_grant"),
    ("M_online_update", "M", "online_update", "M_online_update_enabled"),
    ("M_detector_outcome_contamination", "M", "detector_contamination",
     "prohibited_outcome_or_resource_access"),
    ("M_cross_factor_dependency", "M", "cross_factor_dependency",
     "M_cross_factor_resource_dependency"),
    ("S_reviewer_reuse", "S", "reviewer_reuse",
     "reviewer_independence_violation"),
    ("M_review_binding_drift", "M", "review_binding_drift",
     "review_package_binding_mismatch"),
)


def _readdress_envelope(
    envelope: dict[str, Any], *, preserve_review_binding: bool = False
) -> None:
    package = envelope["source_package"]
    package["source_package_id"] = package_id_for(package)
    for review in envelope["review_receipts"]:
        if not preserve_review_binding:
            review["bound_source_package_id"] = package["source_package_id"]
        review["review_id"] = review_id_for(review)
    partitions = envelope["partition_manifest"]
    partitions["partition_manifest_id"] = partition_manifest_id_for(partitions)
    envelope["envelope_id"] = envelope_id_for(envelope)


def apply_synthetic_mutation(
    envelope: Mapping[str, Any], mutation_id: str
) -> dict[str, Any]:
    """Apply one declared synthetic fault and refresh enclosing addresses."""

    mutated = json.loads(_canonical_json(envelope))
    package = mutated["source_package"]
    derivation = package["derivation_contract"]
    if mutation_id == "partition_overlap":
        assignments = mutated["partition_manifest"]["assignments"]
        assignments["S_independent_validation"] = assignments[
            "S_source_derivation"
        ]
    elif mutation_id == "untracked_source":
        package["tracked_source"] = False
    elif mutation_id == "authority_expansion":
        derivation["controlled_device_count"] = 2
    elif mutation_id == "reactive_zero_imputation":
        derivation["reactive_power_axis"] = "included_as_all_zero_matrix"
    elif mutation_id == "missing_physical_instantiation":
        package["content_addresses"][
            "engineering_instantiation_manifest_sha256"
        ] = None
    elif mutation_id == "candidate_drift":
        derivation["ordered_candidate_ids"].reverse()
    elif mutation_id == "new_observation":
        derivation["new_raw_observations_added"] = True
    elif mutation_id == "online_update":
        derivation["online_update"] = True
    elif mutation_id == "detector_contamination":
        mutated["prohibited_access"]["detector_or_alarm_outcomes"] = True
    elif mutation_id == "cross_factor_dependency":
        derivation["uses_S_derived_resource"] = True
    elif mutation_id == "reviewer_reuse":
        mutated["review_receipts"][1]["reviewer_id"] = (
            mutated["review_receipts"][0]["reviewer_id"]
        )
    elif mutation_id == "review_binding_drift":
        mutated["review_receipts"][1]["bound_source_package_id"] = (
            "m13package_" + ("0" * 64)
        )
    else:
        raise ContractViolation(f"unknown M13 synthetic mutation: {mutation_id}")
    _readdress_envelope(
        mutated, preserve_review_binding=(mutation_id == "review_binding_drift")
    )
    return mutated


def _fixture_cases_and_receipts(
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for factor in ("S", "M"):
        fixture_id = f"{factor}_positive_structure"
        envelope = build_synthetic_envelope(
            factor=factor, fixture_id=fixture_id
        )
        receipt = evaluate_source_package(envelope)
        cases.append({
            "fixture_id": fixture_id,
            "factor": factor,
            "mutation_id": None,
            "envelope_id": envelope["envelope_id"],
            "expected_accepted": True,
            "expected_reason_codes": [],
        })
        receipts.append(receipt)
    for fixture_id, factor, mutation_id, expected_reason in MUTATION_CASES:
        envelope = build_synthetic_envelope(
            factor=factor, fixture_id=fixture_id
        )
        envelope = apply_synthetic_mutation(envelope, mutation_id)
        receipt = evaluate_source_package(envelope)
        cases.append({
            "fixture_id": fixture_id,
            "factor": factor,
            "mutation_id": mutation_id,
            "envelope_id": envelope["envelope_id"],
            "expected_accepted": False,
            "expected_reason_codes": [expected_reason],
        })
        receipts.append(receipt)
    return cases, receipts


@dataclass(frozen=True)
class CareerSourceManifestMatrix:
    """Immutable semantic representation of the M13 fixture matrix."""

    _canonical_content: str

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        self._validate(copied)
        object.__setattr__(self, "_canonical_content", _canonical_json(copied))

    @property
    def matrix_id(self) -> str:
        return self.to_dict()["matrix_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    @staticmethod
    def _validate(content: Mapping[str, Any]) -> None:
        expected_fields = {
            "schema_version",
            "matrix_id",
            "milestone",
            "title",
            "governance",
            "source_lineage",
            "fixture_policy",
            "fixture_cases",
            "validation_receipts",
            "gate_checks",
            "canonical_status",
            "limitations",
            "next_gate",
        }
        if set(content) != expected_fields:
            raise ContractViolation("M13 matrix top-level fields drift")
        if content["schema_version"] != SOURCE_MANIFEST_MATRIX_SCHEMA_VERSION:
            raise ContractViolation("unsupported M13 matrix schema_version")
        if content["milestone"] != "M13":
            raise ContractViolation("source manifest matrix must be M13")
        if content["matrix_id"] != matrix_id_for(content):
            raise ContractViolation("M13 matrix_id mismatch")
        if content["governance"] != REQUIRED_GOVERNANCE:
            raise ContractViolation("M13 governance boundary drift")
        if content["source_lineage"] != {
            "m12_contract_id": M12_CONTRACT_ID,
            "m13_decision": M13_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        }:
            raise ContractViolation("M13 source lineage drift")
        if content["fixture_policy"] != {
            "positive_cases": 2,
            "negative_cases": 12,
            "single_declared_fault_per_negative": True,
            "scientific_values": "synthetic_structure_only",
            "positive_verdict": POSITIVE_VERDICT,
            "negative_verdict": NEGATIVE_VERDICT,
            "real_status_transition": False,
        }:
            raise ContractViolation("M13 fixture policy drift")
        cases, receipts = _fixture_cases_and_receipts()
        if content["fixture_cases"] != cases:
            raise ContractViolation("M13 fixture cases drift")
        if content["validation_receipts"] != receipts:
            raise ContractViolation("M13 validation receipts drift")
        if any(
            case["expected_reason_codes"] != receipt["reason_codes"]
            or case["expected_accepted"] != receipt["accepted"]
            for case, receipt in zip(cases, receipts)
        ):
            raise ContractViolation("M13 fixture expectation mismatch")
        if any(receipt["receipt_id"] != receipt_id_for(receipt)
               for receipt in receipts):
            raise ContractViolation("M13 receipt content address mismatch")
        required_checks = {
            "S_positive_structure_passes",
            "M_positive_structure_passes",
            "partition_overlap_rejected",
            "untracked_source_rejected",
            "S_authority_expansion_rejected",
            "S_reactive_zero_imputation_rejected",
            "M_missing_physical_instantiation_rejected",
            "M_candidate_drift_rejected",
            "M_new_observation_rejected",
            "M_online_update_rejected",
            "detector_outcome_contamination_rejected",
            "cross_factor_dependency_rejected",
            "reviewer_reuse_rejected",
            "review_binding_drift_rejected",
            "all_receipts_content_addressed",
            "all_external_access_zero",
            "all_real_statuses_unchanged",
        }
        if set(content["gate_checks"]) != required_checks:
            raise ContractViolation("M13 gate checks drift")
        if not all(content["gate_checks"].values()):
            raise ContractViolation("M13 gate check failed")
        if content["canonical_status"] != {
            "S_source_package": "UNBUILT_DESIGN_ONLY",
            "M_source_package": "UNBUILT_DESIGN_ONLY",
            "partition_assignments": "UNASSIGNED_DESIGN_ONLY",
            "review_receipts": REVIEW_STATUS,
            "S_scientific_threshold": THRESHOLD_STATUS,
            "M_scientific_threshold": THRESHOLD_STATUS,
            "S_real_resource": REAL_RESOURCE_HOLD,
            "M_real_resource": REAL_RESOURCE_HOLD,
            "evaluation": "SEALED",
            "campaign": "HOLD",
        }:
            raise ContractViolation("M13 canonical status drift")
        if set(content["limitations"]) != {
            "synthetic_hashes_blocks_and_reviewers_only",
            "no_real_source_partition_or_review",
            "no_scientific_threshold_or_resource_admission",
            "no_physical_ranking_or_factor_effect_claim",
            "no_external_runtime_or_evaluation_access",
            "no_campaign_authorization",
        }:
            raise ContractViolation("M13 limitations drift")
        if content["next_gate"] != {
            "id": "M14_independent_source_generation_prerequisite_review",
            "scope": "review_design_and_authorization_boundary_only",
            "real_source_generation_authorized": False,
            "real_partition_assignment_authorized": False,
            "model_or_embedding_call": False,
            "simulator_or_detector_access": False,
            "evaluation_access": False,
        }:
            raise ContractViolation("unexpected M13 next gate")


def build_career_source_manifest_matrix() -> CareerSourceManifestMatrix:
    """Build the canonical M13 synthetic validation matrix."""

    cases, receipts = _fixture_cases_and_receipts()
    gate_checks = {
        "S_positive_structure_passes": receipts[0]["accepted"],
        "M_positive_structure_passes": receipts[1]["accepted"],
        "partition_overlap_rejected": not receipts[2]["accepted"],
        "untracked_source_rejected": not receipts[3]["accepted"],
        "S_authority_expansion_rejected": not receipts[4]["accepted"],
        "S_reactive_zero_imputation_rejected": not receipts[5]["accepted"],
        "M_missing_physical_instantiation_rejected": (
            not receipts[6]["accepted"]
        ),
        "M_candidate_drift_rejected": not receipts[7]["accepted"],
        "M_new_observation_rejected": not receipts[8]["accepted"],
        "M_online_update_rejected": not receipts[9]["accepted"],
        "detector_outcome_contamination_rejected": not receipts[10][
            "accepted"
        ],
        "cross_factor_dependency_rejected": not receipts[11]["accepted"],
        "reviewer_reuse_rejected": not receipts[12]["accepted"],
        "review_binding_drift_rejected": not receipts[13]["accepted"],
        "all_receipts_content_addressed": all(
            receipt["receipt_id"] == receipt_id_for(receipt)
            for receipt in receipts
        ),
        "all_external_access_zero": all(
            receipt["external_access"] == REQUIRED_EXTERNAL_ACCESS
            for receipt in receipts
        ),
        "all_real_statuses_unchanged": all(
            receipt["real_source_status_after"] == "UNBUILT_DESIGN_ONLY"
            and receipt["real_partition_status_after"] == (
                "UNASSIGNED_DESIGN_ONLY"
            )
            and receipt["real_review_status_after"] == REVIEW_STATUS
            and receipt["scientific_threshold_status_after"] == (
                THRESHOLD_STATUS
            )
            and receipt["real_resource_status_after"] == REAL_RESOURCE_HOLD
            and receipt["evaluation_status_after"] == "SEALED"
            for receipt in receipts
        ),
    }
    content: dict[str, Any] = {
        "schema_version": SOURCE_MANIFEST_MATRIX_SCHEMA_VERSION,
        "matrix_id": "pending",
        "milestone": "M13",
        "title": "CAREER synthetic clean-source manifest validator matrix",
        "governance": dict(REQUIRED_GOVERNANCE),
        "source_lineage": {
            "m12_contract_id": M12_CONTRACT_ID,
            "m13_decision": M13_DECISION_ID,
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        },
        "fixture_policy": {
            "positive_cases": 2,
            "negative_cases": 12,
            "single_declared_fault_per_negative": True,
            "scientific_values": "synthetic_structure_only",
            "positive_verdict": POSITIVE_VERDICT,
            "negative_verdict": NEGATIVE_VERDICT,
            "real_status_transition": False,
        },
        "fixture_cases": cases,
        "validation_receipts": receipts,
        "gate_checks": gate_checks,
        "canonical_status": {
            "S_source_package": "UNBUILT_DESIGN_ONLY",
            "M_source_package": "UNBUILT_DESIGN_ONLY",
            "partition_assignments": "UNASSIGNED_DESIGN_ONLY",
            "review_receipts": REVIEW_STATUS,
            "S_scientific_threshold": THRESHOLD_STATUS,
            "M_scientific_threshold": THRESHOLD_STATUS,
            "S_real_resource": REAL_RESOURCE_HOLD,
            "M_real_resource": REAL_RESOURCE_HOLD,
            "evaluation": "SEALED",
            "campaign": "HOLD",
        },
        "limitations": sorted({
            "synthetic_hashes_blocks_and_reviewers_only",
            "no_real_source_partition_or_review",
            "no_scientific_threshold_or_resource_admission",
            "no_physical_ranking_or_factor_effect_claim",
            "no_external_runtime_or_evaluation_access",
            "no_campaign_authorization",
        }),
        "next_gate": {
            "id": "M14_independent_source_generation_prerequisite_review",
            "scope": "review_design_and_authorization_boundary_only",
            "real_source_generation_authorized": False,
            "real_partition_assignment_authorized": False,
            "model_or_embedding_call": False,
            "simulator_or_detector_access": False,
            "evaluation_access": False,
        },
    }
    content["matrix_id"] = matrix_id_for(content)
    return CareerSourceManifestMatrix(content)


def load_career_source_manifest_matrix(
    path: str | Path,
) -> CareerSourceManifestMatrix:
    """Load and semantically validate a checked-in M13 matrix artifact."""

    return CareerSourceManifestMatrix(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )
