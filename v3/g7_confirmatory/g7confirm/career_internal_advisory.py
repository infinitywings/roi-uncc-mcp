"""M16 local-LLM advisory evidence with explicit Brain adjudication.

The advisory is design feedback, not external review or scientific approval.
Its validator preserves model provenance, rejects unmanifested evidence, and
keeps every M15 sealed action false.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_two_tier_gate import (
    DEFERRED_EXTERNAL_CHECKPOINT_ID,
    PI_CONFIRMATION_JOURNAL_ID,
    SEALED_ACTIONS,
    TWO_TIER_DECISION_ID,
    build_career_two_tier_gate,
    verify_checked_in_two_tier_gate,
)
from .orchestration_contract import ContractViolation


INTERNAL_ADVISORY_SCHEMA_VERSION = "grideval-career-internal-advisory/v1"
INTERNAL_ADVISORY_STATUS = "INTERNAL_ADVISORY_COMPLETED_NOT_EXTERNAL_REVIEW"
M16_BACKBRIEF_JOURNAL_ID = "jrn_01M1M9SBTCJPN1J2MZQM38880H"
EXPECTED_REVIEW_SHA256 = (
    "de226e18ad97fa2de78ca80ab6ecd418e7f48c215db1aadd7a79b06f4ced2e8a"
)

INPUT_MANIFEST = (
    ("v3/g7_confirmatory/M8_CAREER_STEALTH_BIAS_DESIGN.md", 11540,
     "98397028c636be788e8a8d168193d562f8a2c2e39cf3d9f7ab46608dadfda6ad"),
    ("v3/g7_confirmatory/M9_CAREER_TWO_INTERVAL_FIXTURE_REPORT.md", 7528,
     "cb69eedc1e9761b1544d45e9ef6ff83f22b2ab0aa4ed180d37bf8cddc2d9cf75"),
    ("v3/g7_confirmatory/M10_CAREER_RESOURCE_ADMISSION_REPORT.md", 7832,
     "df2d5ddec56257fae73f21061f3b3a143e0e0d76fbe2163cf3bbddff13cddf3a"),
    ("v3/g7_confirmatory/M11_CAREER_THRESHOLD_HOLD_REPORT.md", 7302,
     "3897a8c20d1fe6934bd45ba0d3f94197c98fed4b9aaaf71735aca6efff960c3c"),
    ("v3/g7_confirmatory/M12_CAREER_SOURCE_FREEZE_DESIGN_REPORT.md", 8202,
     "9bc457d5ea84453198902753eb5fbd5f4c5743e318eb6fff8d763ca16e87317c"),
    ("v3/g7_confirmatory/M13_CAREER_SOURCE_MANIFEST_VALIDATOR_REPORT.md", 5901,
     "862b8fc6edca22d48118eca8424e99c2c693dc552ff068852504e2b359401e34"),
    ("v3/g7_confirmatory/M14_CAREER_SOURCE_REVIEW_PACKET_REPORT.md", 7074,
     "9e0a77c75c46db88604b67d6ba512bbb45baf5a9a3c40a04be67a24e739bcff7"),
    ("v3/g7_confirmatory/M15_CAREER_TWO_TIER_GATE_REPORT.md", 5051,
     "15295e0c0da0b3e304f1f3a6897ba327a158e490d20933bb2a37e9c7c854462e"),
    ("v3/g7_confirmatory/RED_TEAM_DESIGN.md", 8094,
     "155e5b9240555c741005df84dd5b4642ca5fe9ad2a9f1757391585621dae5607"),
    ("v3/g7_confirmatory/RESEARCH_PROTOCOL.md", 5618,
     "c3b4d3d4ecef19e7b21a4656f4b12e8d105d63ad50fd1a3c4c9af242cd16c813"),
    ("v3/g7_confirmatory/ORCHESTRATION_CONTRACT.md", 41127,
     "2bfb23ffb8e17aac9f4c2ec41755d7cf97b01b1c70fc93cef26a637544294d3b"),
    ("v3/g7_confirmatory/DETECTOR_DEFENSE_REVIEW.md", 7375,
     "26198dd831adf2e189955d3862d0902fdd2aeebc8b5413d8d07da4aa4121a3e5"),
    ("v3/g7_confirmatory/experiment_spec.yaml", 5433,
     "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"),
)

TRANSPORT_RECORD = {
    "advisory_session_id": "m16_local_qwen_advisory_attempt_3",
    "endpoint": "http://ccil1s26m8hj6lws:8000/v1",
    "model_record": {
        "id": "qwen3.6-35b-a3b",
        "max_model_len": 262144,
        "owned_by": "vllm",
        "root": "QuantTrio/Qwen3.6-35B-A3B-AWQ",
    },
    "request_sha256": (
        "d0ef5406f3d812abd79b07ed5e1790c324486ad2bf41b7a0b8ef2a563f47a6d3"
    ),
    "seed": 1616,
    "temperature": 0.0,
    "finish_reason": "stop",
    "usage": {
        "completion_tokens": 2011,
        "prompt_tokens": 30997,
        "prompt_tokens_details": None,
        "total_tokens": 33008,
    },
    "attempts": [
        {
            "attempt": 1,
            "response_contract": "full_strict_schema",
            "status": "FAILED_CLOSED_INVALID_JSON_CONTROL_CHARACTER",
            "accepted": False,
        },
        {
            "attempt": 2,
            "response_contract": "full_strict_schema_compatibility_parser",
            "status": "FAILED_CLOSED_JSON_DELIMITER_ERROR",
            "accepted": False,
        },
        {
            "attempt": 3,
            "response_contract": "compact_strict_schema",
            "status": "ACCEPTED_FOR_INTERNAL_ADVISORY",
            "accepted": True,
        },
    ],
    "model_completions_attempted": 3,
    "accepted_completions": 1,
    "embedding_service_used": False,
    "model_or_embedding_service_started_or_restarted": False,
    "simulator_detector_or_actuator_accessed": False,
    "evaluation_records_accessed": False,
}

ADJUDICATION = {
    "F10": {
        "disposition": "ACCEPT_WITH_CORRECTION",
        "reason": (
            "The source-contamination diagnosis is useful, but M12-M15 are "
            "already complete; only further offline contract checks may proceed."
        ),
        "offline_action": (
            "Carry the single-aggregator and exact-library constraints into "
            "future design-only validators."
        ),
        "deferred_action": "Generate or admit real S/M sources only after the external gate.",
        "may_change_sealed_actions": False,
    },
    "F20": {
        "disposition": "ACCEPT_WITH_CORRECTION",
        "reason": (
            "The synthetic-versus-physical limitation is correct; its proposed "
            "M10-M14 sequence is stale because those milestones are complete."
        ),
        "offline_action": "Preserve the M9 causal isolation claim and label it protocol-only.",
        "deferred_action": (
            "Test physical consequence and stealth only after all prerequisite "
            "gates."
        ),
        "may_change_sealed_actions": False,
    },
    "F30": {
        "disposition": "ACCEPT_FOR_OFFLINE_DESIGN",
        "reason": (
            "The proposed strategy families target power-system-specific "
            "command-to-physics structure."
        ),
        "offline_action": (
            "Specify riding-the-wave and coordinated-P/Q cases as "
            "non-executable strategy contracts."
        ),
        "deferred_action": (
            "Run these strategies against detectors only after external review "
            "and calibration authorization."
        ),
        "may_change_sealed_actions": False,
    },
    "F40": {
        "disposition": "ACCEPT_WITH_CORRECTION",
        "reason": (
            "The partition-leakage question remains valid, but the M14 packet "
            "already exists and is now preserved rather than newly prepared."
        ),
        "offline_action": "Retain the leakage question in the dormant external-review materials.",
        "deferred_action": "Obtain external reviewer assessment before source or partition work.",
        "may_change_sealed_actions": False,
    },
    "F50": {
        "disposition": "REJECT_GOVERNANCE_CONFLICT",
        "reason": (
            "The recommendation assigns threshold setting to M16, which directly "
            "conflicts with the M15 seal on threshold fitting and detector calibration."
        ),
        "offline_action": (
            "Design detector test contracts without fitting thresholds or "
            "accessing calibration records."
        ),
        "deferred_action": (
            "Calibrate detectors only after external review and separate "
            "explicit authorization."
        ),
        "may_change_sealed_actions": False,
    },
    "F60": {
        "disposition": "ACCEPT_WITH_CORRECTION",
        "reason": (
            "The two-tier interpretation is correct, but the claim that model "
            "access is unauthorized is false: M15 permits the existing local model "
            "on synthetic or non-evaluation inputs."
        ),
        "offline_action": (
            "Keep local model use bounded, disclosed, advisory-only, and "
            "non-evaluative."
        ),
        "deferred_action": (
            "Never count local model advice as an external receipt or scientific "
            "approval."
        ),
        "may_change_sealed_actions": False,
    },
    "F70": {
        "disposition": "ACCEPT_FOR_OFFLINE_DESIGN",
        "reason": "Matched IA3/IA4 parity is required for interpretable LLM capability ablations.",
        "offline_action": "Specify parity-preserving ladder and ablation contracts.",
        "deferred_action": "Execute ladder comparisons only after the relevant runtime gates.",
        "may_change_sealed_actions": False,
    },
}

GOVERNANCE = {
    "internal_advisory_only": True,
    "external_review_completed": False,
    "external_receipt_created_or_accepted": False,
    "external_checkpoint_resolved": False,
    "scientific_approval_granted": False,
    "input_scope_design_or_non_evaluation_only": True,
    **SEALED_ACTIONS,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def review_sha256_for(review: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(review).encode("utf-8")).hexdigest()


def advisory_id_for(payload: Mapping[str, Any]) -> str:
    content = json.loads(_canonical_json(payload))
    content.pop("advisory_id", None)
    return "m16advisory_" + hashlib.sha256(
        _canonical_json(content).encode("utf-8")
    ).hexdigest()


def _manifest() -> list[dict[str, Any]]:
    return [
        {"path": path, "bytes": size, "sha256": digest}
        for path, size, digest in INPUT_MANIFEST
    ]


def verify_advisory_inputs(repo_root: str | Path) -> list[str]:
    root = Path(repo_root)
    issues = verify_checked_in_two_tier_gate(root)
    for relative_path, expected_bytes, expected_sha256 in INPUT_MANIFEST:
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
class CareerInternalAdvisory:
    _canonical_content: str

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        self._validate(copied)
        object.__setattr__(self, "_canonical_content", _canonical_json(copied))

    @property
    def advisory_id(self) -> str:
        return self.to_dict()["advisory_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    @staticmethod
    def _validate(content: Mapping[str, Any]) -> None:
        if not isinstance(content, Mapping) or set(content) != {
            "schema_version", "advisory_id", "milestone", "title", "status",
            "source_lineage", "transport", "input_manifest", "review_sha256",
            "review", "brain_adjudication", "governance", "limitations",
            "next_gate",
        }:
            raise ContractViolation("M16 advisory top-level fields drift")
        if content["schema_version"] != INTERNAL_ADVISORY_SCHEMA_VERSION:
            raise ContractViolation("unsupported M16 advisory schema_version")
        if content["advisory_id"] != advisory_id_for(content):
            raise ContractViolation("M16 advisory content address mismatch")
        if content["milestone"] != "M16" or content["status"] != INTERNAL_ADVISORY_STATUS:
            raise ContractViolation("M16 advisory status drift")
        if content["source_lineage"] != {
            "M15_gate_id": build_career_two_tier_gate().gate_id,
            "PI_confirmation_journal_id": PI_CONFIRMATION_JOURNAL_ID,
            "M16_backbrief_journal_id": M16_BACKBRIEF_JOURNAL_ID,
            "two_tier_decision_id": TWO_TIER_DECISION_ID,
            "deferred_external_checkpoint_id": DEFERRED_EXTERNAL_CHECKPOINT_ID,
            "base_commit": "d50bc565a539c8f8252df9e2532bf25ac6cb2785",
        }:
            raise ContractViolation("M16 advisory source lineage drift")
        if content["transport"] != TRANSPORT_RECORD:
            raise ContractViolation("M16 advisory transport record drift")
        if content["input_manifest"] != _manifest():
            raise ContractViolation("M16 advisory input manifest drift")
        review = content["review"]
        if content["review_sha256"] != review_sha256_for(review):
            raise ContractViolation("M16 advisory review digest mismatch")
        if content["review_sha256"] != EXPECTED_REVIEW_SHA256:
            raise ContractViolation("M16 advisory accepted review bytes drift")
        _validate_review(review)
        if content["brain_adjudication"] != ADJUDICATION:
            raise ContractViolation("M16 Brain adjudication drift")
        if content["governance"] != GOVERNANCE:
            raise ContractViolation("M16 governance boundary drift")
        if set(content["limitations"]) != {
            "not_external_or_independent_review",
            "not_scientific_approval",
            "two_failed_model_outputs_preserved_as_transport_status_only",
            "model_advice_contains_stale_or_conflicting_recommendations",
            "no_embedding_simulator_detector_actuator_or_evaluation_access",
            "no_sealed_action_authorized",
        }:
            raise ContractViolation("M16 advisory limitations drift")
        if content["next_gate"] != {
            "id": "M17_offline_attack_defense_trial_matrix",
            "offline_only": True,
            "must_incorporate_Brain_adjudication": True,
            "may_change_sealed_actions": False,
            "deferred_external_gate_remains_open": True,
        }:
            raise ContractViolation("M16 next gate drift")


def _validate_review(review: Any) -> None:
    if not isinstance(review, Mapping) or set(review) != {
        "review_status", "executive_assessment", "findings",
        "next_offline_actions", "deferred_actions", "experimental_ladder",
        "power_system_invariants", "detector_defense_tests", "stop_conditions",
    }:
        raise ContractViolation("M16 accepted review shape drift")
    if review["review_status"] != "ADVISORY_ONLY_NOT_EXTERNAL_REVIEW":
        raise ContractViolation("M16 review claimed external authority")
    findings = review["findings"]
    if not isinstance(findings, Sequence) or isinstance(findings, (str, bytes)):
        raise ContractViolation("M16 findings must be a sequence")
    if {item.get("finding_id") for item in findings} != set(ADJUDICATION):
        raise ContractViolation("M16 finding IDs do not match adjudication")
    allowed_paths = {path for path, _, _ in INPUT_MANIFEST}
    if any(item.get("evidence_path") not in allowed_paths for item in findings):
        raise ContractViolation("M16 review cites unmanifested evidence")
    if set(review["detector_defense_tests"]) != {
        "black_box", "gray_box", "white_box",
    }:
        raise ContractViolation("M16 access-model matrix drift")


def load_career_internal_advisory(path: str | Path) -> CareerInternalAdvisory:
    return CareerInternalAdvisory(json.loads(Path(path).read_text(encoding="utf-8")))


def verify_checked_in_internal_advisory(repo_root: str | Path) -> list[str]:
    root = Path(repo_root)
    issues = verify_advisory_inputs(root)
    path = root / "v3/g7_confirmatory/artifacts/career_internal_advisory_m16.json"
    try:
        load_career_internal_advisory(path)
    except (ContractViolation, OSError, ValueError, TypeError) as exc:
        issues.append(f"internal_advisory:{exc}")
    return issues
