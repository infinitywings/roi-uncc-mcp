"""M14B exact-byte handoff for external M14 reviewers.

The handoff exposes empty worksheets and read-only verification inputs. It
cannot issue a receipt, establish reviewer identity, resolve a checkpoint, or
authorize source generation or runtime access.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_review_receipts import (
    M14_CHECKPOINT_ID,
    M14_PACKET_FILE_BYTES,
    M14_PACKET_FILE_SHA256,
    M14_PACKET_ID,
    M14_REVIEW_SCOPE_SHA256,
    M14_SNAPSHOT_MANIFEST_SHA256,
    QUESTION_SHA256S,
    REQUIRED_ROLES,
)
from .career_source_review_packet import M13_BASE_COMMIT
from .orchestration_contract import ContractViolation


HANDOFF_SCHEMA_VERSION = "grideval-career-reviewer-handoff/v1"
WORKSHEET_SCHEMA_VERSION = "grideval-career-reviewer-worksheet/v1"
M14A_INTAKE_ID = (
    "m14aintake_a4f22ef8dd509e486adc32cdd7623c3682fc2148ff8a48831f606fc256553ba4"
)
M14A_BASE_COMMIT = "363cbb48a678d1ea6b123ad5bc6aadf5c7b7635a"
M14B_DECISION_ID = "dec_01M1DQQMY05E8KV19X5WHVHRC0"
HANDOFF_STATUS = "EXACT_HANDOFF_READY_NOT_APPROVED"
WORKSHEET_STATUS = "EMPTY_UNISSUED_NOT_A_RECEIPT"

SUPPORT_SNAPSHOT = (
    (
        "v3/g7_confirmatory/artifacts/career_source_review_packet_m14.json",
        14284,
        "fc4339b93b99b278e4d0392622778edf4b38a7949c0e2401a5f18b409fcba5b8",
    ),
    (
        "v3/g7_confirmatory/M14_CAREER_SOURCE_REVIEW_PACKET_REPORT.md",
        7074,
        "9e0a77c75c46db88604b67d6ba512bbb45baf5a9a3c40a04be67a24e739bcff7",
    ),
    (
        "v3/g7_confirmatory/career_review_receipt.schema.json",
        6247,
        "e3a13d63e945d7c258fd7361c9d903fcf0af6f57d9f35163f81c9e9b5a719475",
    ),
    (
        "v3/g7_confirmatory/artifacts/career_review_receipt_intake_m14a.json",
        8807,
        "eaa6d9ccb483392f5bb98518cf8eb565c59328a2e3f50ae7a2a92334357d4fe2",
    ),
    (
        "v3/g7_confirmatory/M14A_CAREER_REVIEW_RECEIPT_INTAKE_REPORT.md",
        6054,
        "384678c4532c9b959349bb2bcdc985f9056f7e8e7db4fe37e163c2a55f8626f3",
    ),
    (
        "v3/g7_confirmatory/g7confirm/career_review_receipts.py",
        22930,
        "c838819c33667eaf32115e6b08ddc5f3acdce194fdad6f3c4d2c9651e3cd53f4",
    ),
)

REQUIRED_GOVERNANCE = {
    "reviewer_handoff_only": True,
    "worksheet_is_receipt": False,
    "receipt_creation_or_finalization_authorized": False,
    "identity_established_by_software": False,
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

_WORKSHEET_FIELDS = {
    "schema_version",
    "worksheet_id",
    "artifact_class",
    "status",
    "bound_review",
    "reviewer_role",
    "reviewer_fields",
    "question_fields",
    "review_fields",
    "completion_rule",
    "governance",
    "limitations",
}
_NULL_REVIEWER_FIELDS = {
    "reviewer_id": None,
    "identity_verification_reference": None,
    "is_packet_preparer": None,
    "participated_in_source_generation": None,
    "independent_from_other_required_reviewer": None,
    "conflict_of_interest_declared": None,
}
_NULL_REVIEW_FIELDS = {
    "comments": None,
    "comments_sha256": None,
    "disposition": None,
    "issued_at_utc": None,
    "receipt_id": None,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _content_id(prefix: str, value: Any, *, omit: Sequence[str]) -> str:
    content = json.loads(_canonical_json(value))
    for key in omit:
        content.pop(key, None)
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def worksheet_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m14bworksheet", payload, omit=("worksheet_id",))


def handoff_id_for(payload: Mapping[str, Any]) -> str:
    return _content_id("m14bhandoff", payload, omit=("handoff_id",))


def _support_manifest() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "bytes": size,
            "sha256": digest,
            "git_tracked_at_base_commit": True,
        }
        for path, size, digest in SUPPORT_SNAPSHOT
    ]


def verify_handoff_snapshot(repo_root: str | Path) -> list[str]:
    """Return exact-byte issues for the committed M14B support snapshot."""

    root = Path(repo_root)
    issues: list[str] = []
    for relative_path, expected_bytes, expected_sha256 in SUPPORT_SNAPSHOT:
        path = root / relative_path
        if not path.is_file():
            issues.append(f"missing:{relative_path}")
            continue
        content = path.read_bytes()
        if len(content) != expected_bytes:
            issues.append(f"byte_count_mismatch:{relative_path}")
        if hashlib.sha256(content).hexdigest() != expected_sha256:
            issues.append(f"sha256_mismatch:{relative_path}")
    return issues


@dataclass(frozen=True)
class CareerReviewerWorksheet:
    """Immutable empty worksheet that is deliberately not a review receipt."""

    _canonical_content: str

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        self._validate(copied)
        object.__setattr__(self, "_canonical_content", _canonical_json(copied))

    @property
    def worksheet_id(self) -> str:
        return self.to_dict()["worksheet_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    @staticmethod
    def _validate(content: Mapping[str, Any]) -> None:
        if not isinstance(content, Mapping) or set(content) != _WORKSHEET_FIELDS:
            raise ContractViolation("M14B worksheet top-level fields drift")
        if content["schema_version"] != WORKSHEET_SCHEMA_VERSION:
            raise ContractViolation("unsupported M14B worksheet schema_version")
        if content["worksheet_id"] != worksheet_id_for(content):
            raise ContractViolation("M14B worksheet content address mismatch")
        if content["artifact_class"] != "empty_reviewer_worksheet_not_a_receipt":
            raise ContractViolation("M14B worksheet was promoted to a receipt")
        if content["status"] != WORKSHEET_STATUS:
            raise ContractViolation("M14B worksheet status drift")
        if content["bound_review"] != {
            "packet_id": M14_PACKET_ID,
            "packet_file_sha256": M14_PACKET_FILE_SHA256,
            "packet_file_bytes": M14_PACKET_FILE_BYTES,
            "snapshot_manifest_sha256": M14_SNAPSHOT_MANIFEST_SHA256,
            "review_scope_sha256": M14_REVIEW_SCOPE_SHA256,
            "m13_base_commit": M13_BASE_COMMIT,
            "m14a_intake_id": M14A_INTAKE_ID,
            "m14_checkpoint_id": M14_CHECKPOINT_ID,
        }:
            raise ContractViolation("M14B worksheet review binding drift")
        if content["reviewer_role"] not in REQUIRED_ROLES:
            raise ContractViolation("M14B worksheet role is not required")
        if content["reviewer_fields"] != _NULL_REVIEWER_FIELDS:
            raise ContractViolation("M14B worksheet reviewer fields were populated")
        expected_questions = [
            {
                "ordinal": index,
                "question_sha256": digest,
                "answer": None,
                "finding_references": [],
            }
            for index, digest in enumerate(QUESTION_SHA256S, start=1)
        ]
        if content["question_fields"] != expected_questions:
            raise ContractViolation(
                "M14B worksheet questions were populated or changed"
            )
        if content["review_fields"] != _NULL_REVIEW_FIELDS:
            raise ContractViolation("M14B worksheet review fields were populated")
        if content["completion_rule"] != (
            "worksheet_never_becomes_evidence_external_reviewer_must_issue_a_"
            "separate_content_addressed_M14A_receipt"
        ):
            raise ContractViolation("M14B worksheet completion rule drift")
        if content["governance"] != REQUIRED_GOVERNANCE:
            raise ContractViolation("M14B worksheet governance boundary drift")
        if set(content["limitations"]) != {
            "not_a_review_receipt",
            "no_reviewer_identity_or_independence_evidence",
            "no_answers_comments_or_disposition",
            "no_checkpoint_resolution_or_authorization",
        }:
            raise ContractViolation("M14B worksheet limitations drift")


def build_reviewer_worksheet(reviewer_role: str) -> CareerReviewerWorksheet:
    """Build one canonical role-specific empty reviewer worksheet."""

    if reviewer_role not in REQUIRED_ROLES:
        raise ContractViolation("unsupported M14B reviewer role")
    content: dict[str, Any] = {
        "schema_version": WORKSHEET_SCHEMA_VERSION,
        "worksheet_id": "pending",
        "artifact_class": "empty_reviewer_worksheet_not_a_receipt",
        "status": WORKSHEET_STATUS,
        "bound_review": {
            "packet_id": M14_PACKET_ID,
            "packet_file_sha256": M14_PACKET_FILE_SHA256,
            "packet_file_bytes": M14_PACKET_FILE_BYTES,
            "snapshot_manifest_sha256": M14_SNAPSHOT_MANIFEST_SHA256,
            "review_scope_sha256": M14_REVIEW_SCOPE_SHA256,
            "m13_base_commit": M13_BASE_COMMIT,
            "m14a_intake_id": M14A_INTAKE_ID,
            "m14_checkpoint_id": M14_CHECKPOINT_ID,
        },
        "reviewer_role": reviewer_role,
        "reviewer_fields": dict(_NULL_REVIEWER_FIELDS),
        "question_fields": [
            {
                "ordinal": index,
                "question_sha256": digest,
                "answer": None,
                "finding_references": [],
            }
            for index, digest in enumerate(QUESTION_SHA256S, start=1)
        ],
        "review_fields": dict(_NULL_REVIEW_FIELDS),
        "completion_rule": (
            "worksheet_never_becomes_evidence_external_reviewer_must_issue_a_"
            "separate_content_addressed_M14A_receipt"
        ),
        "governance": dict(REQUIRED_GOVERNANCE),
        "limitations": sorted({
            "not_a_review_receipt",
            "no_reviewer_identity_or_independence_evidence",
            "no_answers_comments_or_disposition",
            "no_checkpoint_resolution_or_authorization",
        }),
    }
    content["worksheet_id"] = worksheet_id_for(content)
    return CareerReviewerWorksheet(content)


def build_reviewer_handoff_contract() -> dict[str, Any]:
    """Build the canonical M14B external-review handoff contract."""

    worksheets = [
        {
            "reviewer_role": role,
            "worksheet_id": build_reviewer_worksheet(role).worksheet_id,
            "artifact_path": (
                "v3/g7_confirmatory/artifacts/reviewer_handoff/"
                + ("data_lineage_worksheet_m14b.json" if index == 0 else
                   "domain_method_worksheet_m14b.json")
            ),
            "status": WORKSHEET_STATUS,
        }
        for index, role in enumerate(REQUIRED_ROLES)
    ]
    content: dict[str, Any] = {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "handoff_id": "pending",
        "milestone": "M14B",
        "title": "CAREER M14 external reviewer handoff",
        "status": HANDOFF_STATUS,
        "source_lineage": {
            "m14a_base_commit": M14A_BASE_COMMIT,
            "m14b_decision_id": M14B_DECISION_ID,
            "m14_packet_id": M14_PACKET_ID,
            "m14a_intake_id": M14A_INTAKE_ID,
            "m14_checkpoint_id": M14_CHECKPOINT_ID,
        },
        "support_snapshot": _support_manifest(),
        "worksheets": worksheets,
        "read_only_commands": {
            "preflight": (
                "python3 -m g7confirm.cli career-review-preflight "
                "--repo-root <repo-root>"
            ),
            "single_receipt": (
                "python3 -m g7confirm.cli career-review-receipt "
                "--receipt <receipt.json>"
            ),
            "receipt_bundle": (
                "python3 -m g7confirm.cli career-review-bundle "
                "--receipt <lineage.json> --receipt <domain.json>"
            ),
            "commands_create_or_modify_files": False,
            "commands_write_RKA": False,
        },
        "governance": dict(REQUIRED_GOVERNANCE),
        "limitations": sorted({
            "no_real_receipt_checked_in_or_issued",
            "no_reviewer_identity_established",
            "no_independent_review_performed",
            "no_checkpoint_resolution",
            "no_source_generation_partition_or_threshold_authorization",
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
    content["handoff_id"] = handoff_id_for(content)
    return content


def load_reviewer_worksheet(path: str | Path) -> CareerReviewerWorksheet:
    """Load and validate an empty checked-in M14B worksheet."""

    return CareerReviewerWorksheet(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def load_reviewer_handoff_contract(path: str | Path) -> dict[str, Any]:
    """Load and exactly validate the checked-in M14B handoff contract."""

    content = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = build_reviewer_handoff_contract()
    if content != expected:
        raise ContractViolation("M14B handoff differs from canonical build")
    return content


def verify_checked_in_handoff(repo_root: str | Path) -> list[str]:
    """Verify support bytes plus canonical contract and worksheet artifacts."""

    root = Path(repo_root)
    issues = verify_handoff_snapshot(root)
    package_root = root / "v3/g7_confirmatory"
    try:
        load_reviewer_handoff_contract(
            package_root / "artifacts/career_reviewer_handoff_m14b.json"
        )
    except (ContractViolation, OSError, ValueError, TypeError) as exc:
        issues.append(f"handoff_contract:{exc}")
    worksheet_paths = (
        package_root / "artifacts/reviewer_handoff/data_lineage_worksheet_m14b.json",
        package_root / "artifacts/reviewer_handoff/domain_method_worksheet_m14b.json",
    )
    for path, role in zip(worksheet_paths, REQUIRED_ROLES):
        try:
            worksheet = load_reviewer_worksheet(path)
            if worksheet.to_dict()["reviewer_role"] != role:
                issues.append(f"worksheet_role_mismatch:{path}")
        except (ContractViolation, OSError, ValueError, TypeError) as exc:
            issues.append(f"worksheet:{path}:{exc}")
    return issues
