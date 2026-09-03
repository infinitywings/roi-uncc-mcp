"""M15 two-tier gate for offline development with deferred external review.

The contract permits narrowly enumerated offline engineering and local
advisory work. It does not authorize source creation, scientific fitting,
runtime evaluation, or campaign execution. The prior M14 review machinery is
preserved byte-for-byte for the deferred pre-source and pre-evaluation gate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_reviewer_handoff import M14A_INTAKE_ID
from .career_review_receipts import M14_PACKET_ID
from .orchestration_contract import ContractViolation


TWO_TIER_GATE_SCHEMA_VERSION = "grideval-career-two-tier-gate/v1"
TWO_TIER_GATE_STATUS = (
    "OFFLINE_DEVELOPMENT_AUTHORIZED_EXTERNAL_REVIEW_DEFERRED"
)
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01KYMRDZHYN4QXC1XFTGP54E36"
PI_CONFIRMATION_JOURNAL_ID = "jrn_01M1M9594BX7M4JPQK0SMPXAQ8"
CONFIRMATION_BRIEF_JOURNAL_ID = "jrn_01M1M8VE9XHW8NC9APWFAVXFS7"
TWO_TIER_DECISION_ID = "dec_01M1M95MNV67RVB4BZJDG4CGVX"
RESOLVED_M14_CHECKPOINT_ID = "chk_01M1DPSAD7H2MGY49QDJNYPK1M"
DEFERRED_EXTERNAL_CHECKPOINT_ID = "chk_01M1M97DN5EWDKSM4T1CMT76J6"
M14B_BASE_COMMIT = "0f285cf7c53949dd43a9a03b11ff475cf9b5954b"
M14B_HANDOFF_ID = (
    "m14bhandoff_b860b6a66def594f90aee3cd5dc675e3e0ec182d873a021f8284f1566cf7b6a3"
)

FROZEN_ASSETS = (
    (
        "v3/g7_confirmatory/roadmap_2026/report.html",
        445019,
        "c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b",
    ),
    (
        "v3/g7_confirmatory/experiment_spec.yaml",
        5433,
        "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d",
    ),
)

HISTORICAL_REVIEW_ASSETS = (
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
    (
        "v3/g7_confirmatory/artifacts/career_reviewer_handoff_m14b.json",
        4588,
        "1f4cf1614cc2bd659668073e1d7b3bd3fc08f6bb1defcd74dd9841def0221434",
    ),
    (
        "v3/g7_confirmatory/M14B_CAREER_REVIEWER_HANDOFF_REPORT.md",
        6949,
        "ade47186697bae20b81091b905ad2ab8b87e4dab2c9d0d5cc40daf9efda68903",
    ),
    (
        "v3/g7_confirmatory/career_reviewer_handoff.schema.json",
        5403,
        "1eff5ccbec789ecdb79676dbc35dc30f20c9b0f2a1d82b34147c29e0a127350f",
    ),
    (
        "v3/g7_confirmatory/career_reviewer_worksheet.schema.json",
        3286,
        "7f9fa32161a31a1717c6079897ae61b98a296f953c4680a576dabb184e826253",
    ),
    (
        "v3/g7_confirmatory/artifacts/reviewer_handoff/data_lineage_worksheet_m14b.json",
        3466,
        "316b84caf4d6c45b317d16c815be4e3792f162421d402845decda8dc8fa3bc9b",
    ),
    (
        "v3/g7_confirmatory/artifacts/reviewer_handoff/domain_method_worksheet_m14b.json",
        3467,
        "5f47839ca13efd01c05b9d04938683eae3cf351395f88de471bd345fa0389628",
    ),
    (
        "v3/g7_confirmatory/g7confirm/career_reviewer_handoff.py",
        15368,
        "91a2ed4337052cddeed49b3c5cbd871aa0153267508fb1118a54cf8db0dccea3",
    ),
)

OFFLINE_PERMISSIONS = {
    "contract_and_schema_authoring": True,
    "implementation_and_unit_testing": True,
    "synthetic_fixture_generation": True,
    "internal_advisory_review": True,
    "local_LLM_on_synthetic_or_non_evaluation_inputs": True,
    "existing_embedding_service_on_synthetic_or_non_evaluation_inputs": True,
    "RKA_provenance_writes": True,
    "start_or_restart_model_or_embedding_service": False,
}

SEALED_ACTIONS = {
    "real_source_generation": False,
    "real_source_modification": False,
    "partition_assignment": False,
    "resource_admission": False,
    "numeric_threshold_selection": False,
    "threshold_fitting": False,
    "detector_calibration": False,
    "simulator_execution": False,
    "actuator_execution": False,
    "runtime_evaluation": False,
    "evaluation_record_access": False,
    "campaign_execution": False,
    "external_receipt_issuance_by_local_advisor": False,
    "external_gate_resolution_by_local_advisor": False,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def gate_id_for(payload: Mapping[str, Any]) -> str:
    content = json.loads(_canonical_json(payload))
    content.pop("gate_id", None)
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return f"m15twotier_{digest}"


def _file_manifest(
    entries: Sequence[tuple[str, int, str]],
) -> list[dict[str, Any]]:
    return [
        {"path": path, "bytes": size, "sha256": digest}
        for path, size, digest in entries
    ]


def _verify_snapshot(
    repo_root: str | Path,
    entries: Sequence[tuple[str, int, str]],
) -> list[str]:
    root = Path(repo_root)
    issues: list[str] = []
    for relative_path, expected_bytes, expected_sha256 in entries:
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


def verify_preserved_assets(repo_root: str | Path) -> list[str]:
    """Return exact-byte issues for frozen and historical review assets."""

    return _verify_snapshot(
        repo_root,
        FROZEN_ASSETS + HISTORICAL_REVIEW_ASSETS,
    )


@dataclass(frozen=True)
class CareerTwoTierGate:
    """Immutable semantic representation of the M15 two-tier gate."""

    _canonical_content: str

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        self._validate(copied)
        object.__setattr__(self, "_canonical_content", _canonical_json(copied))

    @property
    def gate_id(self) -> str:
        return self.to_dict()["gate_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    @staticmethod
    def _validate(content: Mapping[str, Any]) -> None:
        expected_fields = {
            "schema_version",
            "gate_id",
            "milestone",
            "title",
            "status",
            "source_lineage",
            "frozen_assets",
            "historical_review_assets",
            "offline_permissions",
            "sealed_actions",
            "internal_advisory_boundary",
            "deferred_external_gate",
            "limitations",
            "next_gate",
        }
        if not isinstance(content, Mapping) or set(content) != expected_fields:
            raise ContractViolation("M15 two-tier gate top-level fields drift")
        if content["schema_version"] != TWO_TIER_GATE_SCHEMA_VERSION:
            raise ContractViolation("unsupported M15 two-tier gate schema_version")
        if content["gate_id"] != gate_id_for(content):
            raise ContractViolation("M15 two-tier gate content address mismatch")
        if content["milestone"] != "M15":
            raise ContractViolation("two-tier gate must be milestone M15")
        if content["status"] != TWO_TIER_GATE_STATUS:
            raise ContractViolation("M15 two-tier gate status drift")

        expected_lineage = {
            "project_id": PROJECT_ID,
            "mission_id": MISSION_ID,
            "confirmation_brief_journal_id": CONFIRMATION_BRIEF_JOURNAL_ID,
            "pi_confirmation_journal_id": PI_CONFIRMATION_JOURNAL_ID,
            "two_tier_decision_id": TWO_TIER_DECISION_ID,
            "resolved_M14_checkpoint_id": RESOLVED_M14_CHECKPOINT_ID,
            "deferred_external_checkpoint_id": DEFERRED_EXTERNAL_CHECKPOINT_ID,
            "M14B_base_commit": M14B_BASE_COMMIT,
            "M14_packet_id": M14_PACKET_ID,
            "M14A_intake_id": M14A_INTAKE_ID,
            "M14B_handoff_id": M14B_HANDOFF_ID,
        }
        if content["source_lineage"] != expected_lineage:
            raise ContractViolation("M15 source lineage drift")
        if content["frozen_assets"] != _file_manifest(FROZEN_ASSETS):
            raise ContractViolation("M15 frozen asset binding drift")
        if content["historical_review_assets"] != _file_manifest(
            HISTORICAL_REVIEW_ASSETS
        ):
            raise ContractViolation("M15 historical review asset binding drift")
        if content["offline_permissions"] != OFFLINE_PERMISSIONS:
            raise ContractViolation("M15 offline permission boundary drift")
        if content["sealed_actions"] != SEALED_ACTIONS:
            raise ContractViolation("M15 sealed action boundary drift")

        advisory = content["internal_advisory_boundary"]
        if advisory != {
            "advisory_only": True,
            "may_use_synthetic_or_non_evaluation_inputs_only": True,
            "must_disclose_model_service_and_session_identity": True,
            "may_not_claim_external_independence": True,
            "may_not_issue_or_finalize_external_receipts": True,
            "may_not_resolve_the_deferred_external_gate": True,
            "advisory_findings_are_not_scientific_approval": True,
        }:
            raise ContractViolation("M15 internal advisory boundary drift")

        deferred = content["deferred_external_gate"]
        if deferred != {
            "checkpoint_id": DEFERRED_EXTERNAL_CHECKPOINT_ID,
            "status": "OPEN_NON_BLOCKING_FOR_OFFLINE_DEVELOPMENT_ONLY",
            "external_review_complete": False,
            "accepted_receipt_count": 0,
            "required_receipt_count": 2,
            "distinct_external_reviewer_identities_required": True,
            "M14_packet_and_receipt_machinery_preserved": True,
            "required_before_every_sealed_action": True,
            "resolution_requires_explicit_RKA_governance": True,
        }:
            raise ContractViolation("M15 deferred external gate drift")

        if set(content["limitations"]) != {
            "no_external_review_completed_or_waived",
            "no_real_source_or_partition_action",
            "no_resource_admission_or_scientific_threshold",
            "no_detector_calibration",
            "no_simulator_actuator_or_runtime_evaluation",
            "no_campaign_authorization",
            "local_advice_cannot_satisfy_external_review",
        }:
            raise ContractViolation("M15 limitations drift")
        if content["next_gate"] != {
            "id": "M16_internal_advisory_offline_design_review",
            "offline_only": True,
            "requires_M15_exact_byte_preflight": True,
            "may_change_sealed_actions": False,
            "deferred_external_gate_remains_open": True,
        }:
            raise ContractViolation("M15 next gate drift")


def build_career_two_tier_gate() -> CareerTwoTierGate:
    """Build the canonical M15 two-tier gate contract."""

    content: dict[str, Any] = {
        "schema_version": TWO_TIER_GATE_SCHEMA_VERSION,
        "gate_id": "pending",
        "milestone": "M15",
        "title": "CAREER two-tier gate for offline development",
        "status": TWO_TIER_GATE_STATUS,
        "source_lineage": {
            "project_id": PROJECT_ID,
            "mission_id": MISSION_ID,
            "confirmation_brief_journal_id": CONFIRMATION_BRIEF_JOURNAL_ID,
            "pi_confirmation_journal_id": PI_CONFIRMATION_JOURNAL_ID,
            "two_tier_decision_id": TWO_TIER_DECISION_ID,
            "resolved_M14_checkpoint_id": RESOLVED_M14_CHECKPOINT_ID,
            "deferred_external_checkpoint_id": DEFERRED_EXTERNAL_CHECKPOINT_ID,
            "M14B_base_commit": M14B_BASE_COMMIT,
            "M14_packet_id": M14_PACKET_ID,
            "M14A_intake_id": M14A_INTAKE_ID,
            "M14B_handoff_id": M14B_HANDOFF_ID,
        },
        "frozen_assets": _file_manifest(FROZEN_ASSETS),
        "historical_review_assets": _file_manifest(HISTORICAL_REVIEW_ASSETS),
        "offline_permissions": dict(OFFLINE_PERMISSIONS),
        "sealed_actions": dict(SEALED_ACTIONS),
        "internal_advisory_boundary": {
            "advisory_only": True,
            "may_use_synthetic_or_non_evaluation_inputs_only": True,
            "must_disclose_model_service_and_session_identity": True,
            "may_not_claim_external_independence": True,
            "may_not_issue_or_finalize_external_receipts": True,
            "may_not_resolve_the_deferred_external_gate": True,
            "advisory_findings_are_not_scientific_approval": True,
        },
        "deferred_external_gate": {
            "checkpoint_id": DEFERRED_EXTERNAL_CHECKPOINT_ID,
            "status": "OPEN_NON_BLOCKING_FOR_OFFLINE_DEVELOPMENT_ONLY",
            "external_review_complete": False,
            "accepted_receipt_count": 0,
            "required_receipt_count": 2,
            "distinct_external_reviewer_identities_required": True,
            "M14_packet_and_receipt_machinery_preserved": True,
            "required_before_every_sealed_action": True,
            "resolution_requires_explicit_RKA_governance": True,
        },
        "limitations": sorted({
            "no_external_review_completed_or_waived",
            "no_real_source_or_partition_action",
            "no_resource_admission_or_scientific_threshold",
            "no_detector_calibration",
            "no_simulator_actuator_or_runtime_evaluation",
            "no_campaign_authorization",
            "local_advice_cannot_satisfy_external_review",
        }),
        "next_gate": {
            "id": "M16_internal_advisory_offline_design_review",
            "offline_only": True,
            "requires_M15_exact_byte_preflight": True,
            "may_change_sealed_actions": False,
            "deferred_external_gate_remains_open": True,
        },
    }
    content["gate_id"] = gate_id_for(content)
    return CareerTwoTierGate(content)


def load_career_two_tier_gate(path: str | Path) -> CareerTwoTierGate:
    """Load and validate an M15 two-tier gate artifact."""

    return CareerTwoTierGate(json.loads(Path(path).read_text(encoding="utf-8")))


def verify_checked_in_two_tier_gate(repo_root: str | Path) -> list[str]:
    """Verify preserved bytes and the exact checked-in canonical M15 artifact."""

    root = Path(repo_root)
    issues = verify_preserved_assets(root)
    artifact_path = (
        root / "v3/g7_confirmatory/artifacts/career_two_tier_gate_m15.json"
    )
    try:
        stored = load_career_two_tier_gate(artifact_path).to_dict()
        expected = build_career_two_tier_gate().to_dict()
        if stored != expected:
            issues.append("two_tier_contract:differs_from_canonical_build")
    except (ContractViolation, OSError, ValueError, TypeError) as exc:
        issues.append(f"two_tier_contract:{exc}")
    return issues
