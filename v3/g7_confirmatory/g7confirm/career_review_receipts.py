"""Fail-closed M14A intake for externally issued M14 review receipts.

This module validates declarations and content bindings. It does not establish
reviewer identity, issue receipts, resolve an RKA checkpoint, or authorize any
source generation, runtime, evaluation, or campaign activity.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_source_review_packet import M13_BASE_COMMIT
from .orchestration_contract import ContractViolation


RECEIPT_SCHEMA_VERSION = "grideval-career-review-receipt/v1"
INTAKE_SCHEMA_VERSION = "grideval-career-review-receipt-intake/v1"
M14_PACKET_ID = (
    "m14reviewpacket_6efed441aebe881691b3596321ca7255edf67af8d24ef59412be923"
    "e12098b25"
)
M14_PACKET_FILE_SHA256 = (
    "fc4339b93b99b278e4d0392622778edf4b38a7949c0e2401a5f18b409fcba5b8"
)
M14_PACKET_FILE_BYTES = 14284
M14_SNAPSHOT_MANIFEST_SHA256 = (
    "1af4941f031344c1e5d1ea5bb238e6ab669e7f32702230d1ef7bb96e94f1e39c"
)
M14_REVIEW_SCOPE_SHA256 = (
    "32f6d0c5ba48d3370a860ab12b0b24fe1908817ee61c35bee88c9191b39edde6"
)
M14_DECISION_ID = "dec_01M1DPBJJQR8346RVZBKFSBDH7"
M14A_DECISION_ID = "dec_01M1DPZR2QH6DHAK0CET23Q9E4"
M14_CHECKPOINT_ID = "chk_01M1DPSAD7H2MGY49QDJNYPK1M"

REQUIRED_ROLES = (
    "independent_data_lineage_reviewer",
    "independent_domain_method_reviewer",
)
ALLOWED_DISPOSITIONS = (
    "accept_exact_packet",
    "request_changes",
    "reject",
)
ARTIFACT_CLASSES = (
    "external_review_receipt",
    "synthetic_conformance_fixture",
)
QUESTION_SHA256S = (
    "eaf95378d0dc93760d478c83d7a64f5f941cfd6bf6ed40689c354801280f64ba",
    "c06b061ea3bbba84d118fc38ec6622c654cebf27807523bf168bd1ced92fbc26",
    "d32dd1794813635d2199daa33f756b1336d3c68ebae56a9cf12565d386896a35",
    "43412da0fa4764713cdea1b830c2c57000eb77e026ab7430b1f7109f8ad2757a",
    "4e02c586001ba3f6b9b1cec3c8efc25e90a8e9f639a51f3479471bc603e1c994",
    "7fb4c836c01b67c8dfb0a79603feb44b32fcaa9edf690824806443a785c014b4",
)

INCOMPLETE = "INCOMPLETE_NOT_APPROVED"
INVALID = "INVALID_NOT_APPROVED"
CHANGES_REQUIRED = "CHANGES_REQUIRED_NOT_APPROVED"
REJECTED = "REJECTED_NOT_APPROVED"
SYNTHETIC_PASS = "SYNTHETIC_MECHANICS_PASS_NO_AUTHORITY"
READY_FOR_GOVERNANCE = (
    "READY_FOR_EXTERNAL_GOVERNANCE_RESOLUTION_NOT_APPROVED"
)

REQUIRED_GOVERNANCE = {
    "receipt_intake_only": True,
    "identity_established_by_software": False,
    "receipt_issuance_authorized": False,
    "checkpoint_resolution_authorized": False,
    "source_generation_authorized": False,
    "partition_assignment_authorized": False,
    "threshold_selection_authorized": False,
    "resource_admission_authorized": False,
    "model_or_embedding_access_authorized": False,
    "tool_simulator_detector_or_actuator_access_authorized": False,
    "evaluation_access_authorized": False,
    "campaign_authorized": False,
}

_RECEIPT_FIELDS = {
    "schema_version",
    "receipt_id",
    "artifact_class",
    "bound_packet",
    "reviewer",
    "review",
    "governance",
}
_BOUND_PACKET_FIELDS = {
    "packet_id",
    "packet_file_sha256",
    "packet_file_bytes",
    "m13_base_commit",
    "snapshot_manifest_sha256",
    "review_scope_sha256",
}
_REVIEWER_FIELDS = {
    "reviewer_id",
    "reviewer_role",
    "identity_verification_reference",
    "is_packet_preparer",
    "participated_in_source_generation",
    "independent_from_other_required_reviewer",
    "conflict_of_interest_declared",
}
_REVIEW_FIELDS = {
    "disposition",
    "comments",
    "comments_sha256",
    "answered_question_sha256s",
    "issued_at_utc",
    "attestations",
}
_ATTESTATIONS = {
    "reviewed_exact_packet_bytes": True,
    "reviewed_all_six_questions": True,
    "decision_made_without_packet_preparer_influence": True,
    "no_treatment_confirmation_or_evaluation_outcome_access": True,
    "no_model_embedding_tool_simulator_detector_or_actuator_access": True,
}
_ISSUED_AT_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
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


def comments_sha256(comments: str) -> str:
    """Return the exact UTF-8 SHA-256 used by a receipt."""

    return hashlib.sha256(comments.encode("utf-8")).hexdigest()


def receipt_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m14reviewreceipt", payload, omit=("receipt_id",))


def intake_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m14aintake", payload, omit=("contract_id",))


def _validate_bound_packet(binding: Mapping[str, Any]) -> None:
    if set(binding) != _BOUND_PACKET_FIELDS:
        raise ContractViolation("review receipt packet-binding fields drift")
    if binding != {
        "packet_id": M14_PACKET_ID,
        "packet_file_sha256": M14_PACKET_FILE_SHA256,
        "packet_file_bytes": M14_PACKET_FILE_BYTES,
        "m13_base_commit": M13_BASE_COMMIT,
        "snapshot_manifest_sha256": M14_SNAPSHOT_MANIFEST_SHA256,
        "review_scope_sha256": M14_REVIEW_SCOPE_SHA256,
    }:
        raise ContractViolation("review receipt is not bound to exact M14 bytes")


def _validate_reviewer(
    reviewer: Mapping[str, Any], artifact_class: str
) -> None:
    if set(reviewer) != _REVIEWER_FIELDS:
        raise ContractViolation("reviewer declaration fields drift")
    reviewer_id = reviewer["reviewer_id"]
    verification = reviewer["identity_verification_reference"]
    if not isinstance(reviewer_id, str) or not 3 <= len(reviewer_id) <= 128:
        raise ContractViolation("reviewer_id must contain 3 to 128 characters")
    if reviewer["reviewer_role"] not in REQUIRED_ROLES:
        raise ContractViolation("reviewer role is not an M14 required role")
    if not isinstance(verification, str) or len(verification) < 8:
        raise ContractViolation("external identity verification is missing")
    if reviewer["is_packet_preparer"] is not False:
        raise ContractViolation("packet preparer cannot issue a review receipt")
    if reviewer["participated_in_source_generation"] is not False:
        raise ContractViolation("source generator cannot issue this receipt")
    if reviewer["independent_from_other_required_reviewer"] is not True:
        raise ContractViolation("reviewer independence was not attested")
    if reviewer["conflict_of_interest_declared"] is not False:
        raise ContractViolation("declared reviewer conflict requires resolution")
    synthetic_id = reviewer_id.startswith("synthetic_")
    synthetic_ref = verification.startswith("synthetic://")
    if artifact_class == "synthetic_conformance_fixture":
        if not synthetic_id or not synthetic_ref:
            raise ContractViolation("synthetic receipt identity is not explicit")
    elif synthetic_id or synthetic_ref:
        raise ContractViolation("external receipt uses synthetic identity markers")


def _validate_review(review: Mapping[str, Any]) -> None:
    if set(review) != _REVIEW_FIELDS:
        raise ContractViolation("review declaration fields drift")
    if review["disposition"] not in ALLOWED_DISPOSITIONS:
        raise ContractViolation("unsupported review disposition")
    comments = review["comments"]
    if not isinstance(comments, str) or not comments.strip():
        raise ContractViolation("review comments must be non-empty")
    if review["comments_sha256"] != comments_sha256(comments):
        raise ContractViolation("review comments SHA-256 mismatch")
    if review["answered_question_sha256s"] != list(QUESTION_SHA256S):
        raise ContractViolation("review did not bind all six M14 questions")
    issued_at = review["issued_at_utc"]
    if not isinstance(issued_at, str) or not _ISSUED_AT_PATTERN.fullmatch(
        issued_at
    ):
        raise ContractViolation("issued_at_utc must be a second-resolution UTC time")
    if review["attestations"] != _ATTESTATIONS:
        raise ContractViolation("review attestations are incomplete or changed")


@dataclass(frozen=True)
class CareerReviewReceipt:
    """Immutable semantic representation of one declared review receipt."""

    _canonical_content: str

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        self._validate(copied)
        object.__setattr__(self, "_canonical_content", _canonical_json(copied))

    @property
    def receipt_id(self) -> str:
        return self.to_dict()["receipt_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    @staticmethod
    def _validate(content: Mapping[str, Any]) -> None:
        if set(content) != _RECEIPT_FIELDS:
            raise ContractViolation("review receipt top-level fields drift")
        if content["schema_version"] != RECEIPT_SCHEMA_VERSION:
            raise ContractViolation("unsupported review receipt schema_version")
        if content["artifact_class"] not in ARTIFACT_CLASSES:
            raise ContractViolation("unsupported review receipt artifact_class")
        if content["receipt_id"] != receipt_id_for(content):
            raise ContractViolation("review receipt content address mismatch")
        _validate_bound_packet(content["bound_packet"])
        _validate_reviewer(content["reviewer"], content["artifact_class"])
        _validate_review(content["review"])
        if content["governance"] != REQUIRED_GOVERNANCE:
            raise ContractViolation("review receipt governance boundary drift")


@dataclass(frozen=True)
class ReviewBundleResult:
    """Fail-closed receipt-set evaluation with no authorization side effect."""

    status: str
    receipts_seen: int
    valid_receipt_ids: tuple[str, ...]
    reviewer_roles: tuple[str, ...]
    reviewer_ids: tuple[str, ...]
    dispositions: tuple[str, ...]
    failure_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "receipts_seen": self.receipts_seen,
            "valid_receipt_ids": list(self.valid_receipt_ids),
            "reviewer_roles": list(self.reviewer_roles),
            "reviewer_ids": list(self.reviewer_ids),
            "dispositions": list(self.dispositions),
            "failure_reasons": list(self.failure_reasons),
            "checkpoint_id": M14_CHECKPOINT_ID,
            "checkpoint_status": "OPEN_REQUIRES_EXTERNAL_RESOLUTION",
            "authorization": {
                "source_generation": False,
                "partition_assignment": False,
                "threshold_selection": False,
                "resource_admission": False,
                "model_or_embedding_access": False,
                "tool_simulator_detector_or_actuator_access": False,
                "evaluation_access": False,
                "campaign": False,
            },
        }


def _bundle_result(
    status: str,
    receipts: Sequence[CareerReviewReceipt],
    reasons: Sequence[str] = (),
    *,
    receipts_seen: int | None = None,
) -> ReviewBundleResult:
    payloads = [receipt.to_dict() for receipt in receipts]
    return ReviewBundleResult(
        status=status,
        receipts_seen=len(payloads) if receipts_seen is None else receipts_seen,
        valid_receipt_ids=tuple(item["receipt_id"] for item in payloads),
        reviewer_roles=tuple(item["reviewer"]["reviewer_role"] for item in payloads),
        reviewer_ids=tuple(item["reviewer"]["reviewer_id"] for item in payloads),
        dispositions=tuple(item["review"]["disposition"] for item in payloads),
        failure_reasons=tuple(reasons),
    )


def evaluate_review_receipts(
    receipts: Sequence[Mapping[str, Any]],
) -> ReviewBundleResult:
    """Validate a receipt set without issuing approval or changing state."""

    validated: list[CareerReviewReceipt] = []
    failures: list[str] = []
    for index, payload in enumerate(receipts):
        try:
            validated.append(CareerReviewReceipt(payload))
        except (ContractViolation, KeyError, TypeError, ValueError) as exc:
            failures.append(f"receipt_{index}:{exc}")
    if failures:
        return _bundle_result(
            INVALID, validated, failures, receipts_seen=len(receipts)
        )
    if len(validated) != 2:
        return _bundle_result(
            INCOMPLETE,
            validated,
            ("exactly_two_receipts_required",),
            receipts_seen=len(receipts),
        )

    payloads = [receipt.to_dict() for receipt in validated]
    receipt_ids = [item["receipt_id"] for item in payloads]
    roles = [item["reviewer"]["reviewer_role"] for item in payloads]
    reviewer_ids = [item["reviewer"]["reviewer_id"] for item in payloads]
    artifact_classes = [item["artifact_class"] for item in payloads]
    bundle_failures: list[str] = []
    if len(set(receipt_ids)) != 2:
        bundle_failures.append("receipt_ids_not_distinct")
    if set(roles) != set(REQUIRED_ROLES):
        bundle_failures.append("required_role_coverage_failed")
    if len(set(reviewer_ids)) != 2:
        bundle_failures.append("reviewer_identities_not_distinct")
    if len(set(artifact_classes)) != 1:
        bundle_failures.append("mixed_external_and_synthetic_receipts")
    if bundle_failures:
        return _bundle_result(INVALID, validated, bundle_failures)

    dispositions = [item["review"]["disposition"] for item in payloads]
    if "reject" in dispositions:
        return _bundle_result(REJECTED, validated)
    if "request_changes" in dispositions:
        return _bundle_result(CHANGES_REQUIRED, validated)
    if dispositions != ["accept_exact_packet", "accept_exact_packet"]:
        return _bundle_result(INVALID, validated, ("acceptance_rule_failed",))
    if artifact_classes[0] == "synthetic_conformance_fixture":
        return _bundle_result(SYNTHETIC_PASS, validated)
    return _bundle_result(READY_FOR_GOVERNANCE, validated)


def build_synthetic_review_receipt(
    reviewer_role: str,
    reviewer_id: str,
    *,
    disposition: str = "accept_exact_packet",
    comments: str = "Synthetic conformance fixture; no review authority.",
) -> CareerReviewReceipt:
    """Build an unmistakably synthetic receipt for offline mechanics tests."""

    if reviewer_role not in REQUIRED_ROLES:
        raise ContractViolation("synthetic fixture uses an unsupported role")
    if not reviewer_id.startswith("synthetic_"):
        raise ContractViolation("synthetic reviewer_id must start with synthetic_")
    content: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": "pending",
        "artifact_class": "synthetic_conformance_fixture",
        "bound_packet": {
            "packet_id": M14_PACKET_ID,
            "packet_file_sha256": M14_PACKET_FILE_SHA256,
            "packet_file_bytes": M14_PACKET_FILE_BYTES,
            "m13_base_commit": M13_BASE_COMMIT,
            "snapshot_manifest_sha256": M14_SNAPSHOT_MANIFEST_SHA256,
            "review_scope_sha256": M14_REVIEW_SCOPE_SHA256,
        },
        "reviewer": {
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
            "identity_verification_reference": (
                f"synthetic://conformance/{reviewer_id}"
            ),
            "is_packet_preparer": False,
            "participated_in_source_generation": False,
            "independent_from_other_required_reviewer": True,
            "conflict_of_interest_declared": False,
        },
        "review": {
            "disposition": disposition,
            "comments": comments,
            "comments_sha256": comments_sha256(comments),
            "answered_question_sha256s": list(QUESTION_SHA256S),
            "issued_at_utc": "2000-01-01T00:00:00Z",
            "attestations": dict(_ATTESTATIONS),
        },
        "governance": dict(REQUIRED_GOVERNANCE),
    }
    content["receipt_id"] = receipt_id_for(content)
    return CareerReviewReceipt(content)


def _case(
    case_id: str,
    receipts_count: int,
    artifact_classes: Sequence[str],
    injected_fault: str | None,
    expected_status: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "receipts_count": receipts_count,
        "artifact_classes": list(artifact_classes),
        "injected_fault": injected_fault,
        "expected_status": expected_status,
        "fixture_only": True,
    }


def build_review_receipt_intake_contract() -> dict[str, Any]:
    """Build the canonical M14A packet-support and conformance contract."""

    cases = [
        _case("zero_receipts", 0, [], None, INCOMPLETE),
        _case("one_synthetic_acceptance", 1,
              ["synthetic_conformance_fixture"], None, INCOMPLETE),
        _case("two_synthetic_acceptances", 2,
              ["synthetic_conformance_fixture"] * 2, None, SYNTHETIC_PASS),
        _case("duplicate_reviewer", 2,
              ["synthetic_conformance_fixture"] * 2,
              "reviewer_identities_not_distinct", INVALID),
        _case("duplicate_role", 2,
              ["synthetic_conformance_fixture"] * 2,
              "required_role_coverage_failed", INVALID),
        _case("wrong_packet_id", 2,
              ["synthetic_conformance_fixture"] * 2,
              "packet_id_mismatch", INVALID),
        _case("wrong_packet_file_hash", 2,
              ["synthetic_conformance_fixture"] * 2,
              "packet_file_sha256_mismatch", INVALID),
        _case("wrong_base_commit", 2,
              ["synthetic_conformance_fixture"] * 2,
              "m13_base_commit_mismatch", INVALID),
        _case("wrong_snapshot_digest", 2,
              ["synthetic_conformance_fixture"] * 2,
              "snapshot_manifest_sha256_mismatch", INVALID),
        _case("self_review", 2,
              ["synthetic_conformance_fixture"] * 2,
              "packet_preparer_declared", INVALID),
        _case("comments_hash_mismatch", 2,
              ["synthetic_conformance_fixture"] * 2,
              "comments_sha256_mismatch", INVALID),
        _case("content_address_mismatch", 2,
              ["synthetic_conformance_fixture"] * 2,
              "receipt_id_mismatch", INVALID),
        _case("request_changes", 2,
              ["synthetic_conformance_fixture"] * 2, None, CHANGES_REQUIRED),
        _case("reject", 2,
              ["synthetic_conformance_fixture"] * 2, None, REJECTED),
        _case("mixed_artifact_classes", 2,
              ["synthetic_conformance_fixture", "external_review_receipt"],
              "mixed_external_and_synthetic_receipts", INVALID),
        _case("two_external_shape_acceptances", 2,
              ["external_review_receipt"] * 2, None, READY_FOR_GOVERNANCE),
    ]
    content: dict[str, Any] = {
        "schema_version": INTAKE_SCHEMA_VERSION,
        "contract_id": "pending",
        "milestone": "M14A",
        "title": "CAREER M14 external review-receipt intake contract",
        "status": "OFFLINE_INTAKE_READY_M14_CHECKPOINT_OPEN",
        "source_lineage": {
            "m14_packet_id": M14_PACKET_ID,
            "m14_packet_file_sha256": M14_PACKET_FILE_SHA256,
            "m14_packet_file_bytes": M14_PACKET_FILE_BYTES,
            "m13_base_commit": M13_BASE_COMMIT,
            "m14_decision_id": M14_DECISION_ID,
            "m14a_decision_id": M14A_DECISION_ID,
            "m14_checkpoint_id": M14_CHECKPOINT_ID,
        },
        "governance": dict(REQUIRED_GOVERNANCE),
        "receipt_contract": {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "required_roles": list(REQUIRED_ROLES),
            "allowed_dispositions": list(ALLOWED_DISPOSITIONS),
            "required_distinct_receipts": 2,
            "required_distinct_reviewer_identities": 2,
            "required_packet_binding": {
                "packet_id": M14_PACKET_ID,
                "packet_file_sha256": M14_PACKET_FILE_SHA256,
                "packet_file_bytes": M14_PACKET_FILE_BYTES,
                "m13_base_commit": M13_BASE_COMMIT,
                "snapshot_manifest_sha256": M14_SNAPSHOT_MANIFEST_SHA256,
                "review_scope_sha256": M14_REVIEW_SCOPE_SHA256,
            },
            "identity_assurance_boundary": (
                "software_validates_declared_reference_only_external_governance_"
                "establishes_identity_and_independence"
            ),
        },
        "bundle_state_machine": {
            "states": [
                INCOMPLETE,
                INVALID,
                CHANGES_REQUIRED,
                REJECTED,
                SYNTHETIC_PASS,
                READY_FOR_GOVERNANCE,
            ],
            "mechanical_acceptance_rule": (
                "two_distinct_external_non_preparer_acceptances_with_exact_roles_"
                "and_exact_packet_binding"
            ),
            "ready_state_is_approval": False,
            "automatic_checkpoint_resolution": False,
            "automatic_authorization": False,
        },
        "canonical_conformance_matrix": cases,
        "limitations": sorted({
            "no_real_receipt_checked_in",
            "no_reviewer_identity_established_by_software",
            "no_independent_review_performed",
            "no_checkpoint_resolution",
            "no_source_generation_or_partition_assignment",
            "no_threshold_selection_or_resource_admission",
            "no_model_embedding_tool_simulator_detector_or_actuator_access",
            "no_evaluation_or_campaign_authorization",
        }),
        "next_gate": {
            "id": "M15_post_independent_review_resolution",
            "requires_two_genuine_external_receipts": True,
            "requires_external_identity_and_independence_verification": True,
            "requires_explicit_RKA_checkpoint_resolution": True,
            "source_generation_authorized": False,
            "evaluation_access": False,
            "campaign_authorized": False,
        },
    }
    content["contract_id"] = intake_id_for(content)
    return content


def load_review_receipt(path: str | Path) -> CareerReviewReceipt:
    """Load one externally supplied or explicit synthetic receipt."""

    return CareerReviewReceipt(json.loads(Path(path).read_text(encoding="utf-8")))


def load_review_receipt_intake_contract(path: str | Path) -> dict[str, Any]:
    """Load and exactly validate the checked-in M14A intake contract."""

    content = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = build_review_receipt_intake_contract()
    if content != expected:
        raise ContractViolation("M14A intake contract differs from canonical build")
    return content
