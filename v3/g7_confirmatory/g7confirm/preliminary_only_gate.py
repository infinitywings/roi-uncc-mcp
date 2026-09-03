"""M18 fail-closed governance for bounded PRELIMINARY_ONLY work.

M18 reserves disjoint purpose-specific seed partitions and enumerates the
actions that a later runtime integration may request.  It performs no source
generation, fitting, model call, simulation, or actuation itself.  Final
evaluation and confirmatory claims remain outside this gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_trial_matrix import (
    PROJECT_ID,
    MISSION_ID,
    verify_checked_in_trial_matrix,
)
from .orchestration_contract import ContractViolation


PRELIMINARY_GATE_SCHEMA_VERSION = "grideval-preliminary-only-gate/v1"
PRELIMINARY_GATE_STATUS = (
    "BOUNDED_ONLINE_DEVELOPMENT_AUTHORIZED_NO_RUN_EXECUTED"
)
M18_DECISION_ID = "dec_01M1MEP2VK98XN9KD935WDH39N"
SUPERSEDED_M18_DECISION_ID = "dec_01M1ME2CJ9WN5XBPY56C3AB714"
M18_BACKBRIEF_JOURNAL_ID = "jrn_01M1ME2TJXAE96SB65P851DY1B"
M18_APPROVAL_JOURNAL_ID = "jrn_01M1ME3433FM04A4T65RRMVAH2"
ONLINE_PI_DIRECTIVE_JOURNAL_ID = "jrn_01M1MEHG231KP7VRA9THV14KTD"
ONLINE_CONFIRMATION_BRIEF_JOURNAL_ID = "jrn_01M1MEJ2HR5CV1EM0F66KGYN2R"
ONLINE_PI_CONFIRMATION_JOURNAL_ID = "jrn_01M1MENKG6DHRRTSDW6WSJXBFS"
PRELIMINARY_FIRST_DECISION_ID = "dec_01M1MDB6Q97DXACWMN2EVE7Q9Q"
M17_EVIDENCE_JOURNAL_ID = "jrn_01M1ME102EMBDERJ6ZRM09XR98"
M17_COMMIT = "2cff8436d40ae75644bcdc050be6fa11b11f192d"
M17_MATRIX_ID = (
    "m17trialmatrix_8ce2c71c1eab533f04a75b15ea17d3e223587bbf4089149d6ac1e8105cbd169d"
)
LLM_SERVICE_IDENTITY = "qwen3.6-35b-a3b@http://ccil1s26m8hj6lws:8000/v1"
EMBEDDING_SERVICE_IDENTITY = "existing_project_embedding_service"

BOUND_ASSETS = (
    (
        "v3/g7_confirmatory/M17_CAREER_ATTACK_DEFENSE_TRIAL_MATRIX_REPORT.md",
        8569,
        "c7911b2bbf10f9094a813b6cc347c9466babee973e2a818dea8db15cf4fbf677",
    ),
    (
        "v3/g7_confirmatory/artifacts/career_trial_matrix_m17.json",
        18518,
        "4abb27945b19dab231f5ca2ab46e32359fa3b8d5d567e6d7159f51d0b0256595",
    ),
    (
        "v3/g7_confirmatory/career_trial_matrix.schema.json",
        11200,
        "bdb47ef78d8eda273eb21b1c9723b6e809a9405cec6f7bbdfed9cb028e8b7c6b",
    ),
    (
        "v3/g7_confirmatory/g7confirm/career_trial_matrix.py",
        22131,
        "e13b8014cfca4be9c66ff5b894b7fd4cc50d64ddaca035292415a832aa5aa0b9",
    ),
    (
        "v3/g7_confirmatory/experiment_spec.yaml",
        5433,
        "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d",
    ),
    (
        "v3/g7_confirmatory/roadmap_2026/report.html",
        445019,
        "c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b",
    ),
)

PARTITION_REGISTRY = (
    {
        "role": "runtime_qualification",
        "seeds": [5101, 5102, 5103, 5104],
        "classification": "PRELIMINARY_ONLY",
        "purpose": "bounded_benign_and_paired_runtime_lineage_checks",
        "may_read": True,
        "may_influence_design": True,
        "may_support_confirmatory_claims": False,
    },
    {
        "role": "system_identification",
        "seeds": list(range(6101, 6113)),
        "classification": "PRELIMINARY_ONLY",
        "purpose": "clean_process_relationship_and_sensitivity_generation",
        "may_read": True,
        "may_influence_design": True,
        "may_support_confirmatory_claims": False,
    },
    {
        "role": "detector_calibration",
        "seeds": list(range(7101, 7113)),
        "classification": "PRELIMINARY_ONLY",
        "purpose": "benign_only_preliminary_detector_parameter_fitting",
        "may_read": True,
        "may_influence_design": True,
        "may_support_confirmatory_claims": False,
    },
    {
        "role": "detector_audit",
        "seeds": list(range(7201, 7213)),
        "classification": "PRELIMINARY_ONLY",
        "purpose": "outcome_blind_preliminary_detector_stability_audit",
        "may_read": True,
        "may_influence_design": True,
        "may_support_confirmatory_claims": False,
    },
    {
        "role": "attack_development",
        "seeds": list(range(8101, 8113)),
        "classification": "PRELIMINARY_ONLY",
        "purpose": "strategy_mechanism_and_attacker_ladder_development",
        "may_read": True,
        "may_influence_design": True,
        "may_support_confirmatory_claims": False,
    },
    {
        "role": "preliminary_holdout",
        "seeds": list(range(8201, 8213)),
        "classification": "PRELIMINARY_ONLY",
        "purpose": "one_time_preliminary_replication_after_design_lock",
        "may_read": True,
        "may_influence_design": False,
        "may_support_confirmatory_claims": False,
    },
    {
        "role": "final_evaluation_reserved",
        "seeds": list(range(9101, 9113)),
        "classification": "FINAL_SEALED",
        "purpose": "reserved_for_later_confirmatory_freeze",
        "may_read": False,
        "may_influence_design": False,
        "may_support_confirmatory_claims": False,
    },
)

PRELIMINARY_PERMISSIONS = {
    "create_once_source_generation": True,
    "provisional_resource_admission": True,
    "numeric_threshold_selection": True,
    "threshold_fitting": True,
    "detector_calibration": True,
    "simulator_execution": True,
    "simulated_actuator_execution": True,
    "preliminary_runtime_evaluation": True,
    "preliminary_trial_batch_execution": True,
    "existing_local_LLM_inference": True,
    "existing_embedding_service_inference": True,
    "ephemeral_local_runtime_component_startup": True,
}

FINAL_SEALS = {
    "final_evaluation_partition_access": False,
    "final_evaluation_seed_use": False,
    "final_resource_admission": False,
    "final_threshold_or_detector_lock": False,
    "confirmatory_campaign_execution": False,
    "confirmatory_statistical_inference": False,
    "publication_grade_effectiveness_claim": False,
    "generalization_claim": False,
    "physical_field_device_actuation": False,
    "start_or_restart_model_or_embedding_service": False,
}

ACTION_PARTITIONS = {
    "source_generation": {"system_identification"},
    "provisional_resource_admission": {
        "system_identification",
        "detector_audit",
    },
    "threshold_fitting": {"detector_calibration"},
    "detector_calibration": {"detector_calibration"},
    "simulator_execution": {
        "runtime_qualification",
        "system_identification",
        "detector_calibration",
        "detector_audit",
        "attack_development",
        "preliminary_holdout",
    },
    "simulated_actuator_execution": {
        "runtime_qualification",
        "attack_development",
        "preliminary_holdout",
    },
    "preliminary_runtime_evaluation": {
        "runtime_qualification",
        "attack_development",
        "preliminary_holdout",
    },
    "preliminary_trial_batch": {
        "attack_development",
        "preliminary_holdout",
    },
    "local_LLM_inference": {"attack_development", "preliminary_holdout"},
    "embedding_inference": {
        "system_identification",
        "detector_audit",
        "attack_development",
        "preliminary_holdout",
    },
}

ACTION_REQUEST_FIELDS = {
    "action_id",
    "action_type",
    "partition_role",
    "seed",
    "output_classification",
    "create_once",
    "manifest_sha256",
    "code_sha256",
    "config_sha256",
    "budget_id",
    "paired_benign_id",
    "final_evaluation_data_accessed",
    "physical_field_actuator",
    "starts_or_restarts_service",
    "retain_failures",
    "local_service_identity",
}

RUNTIME_ACTIONS = {
    "simulated_actuator_execution",
    "preliminary_runtime_evaluation",
    "preliminary_trial_batch",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def preliminary_gate_id_for(payload: Mapping[str, Any]) -> str:
    content = json.loads(_canonical_json(payload))
    content.pop("gate_id", None)
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return f"m18preliminary_{digest}"


def _file_manifest(
    entries: Sequence[tuple[str, int, str]],
) -> list[dict[str, Any]]:
    return [
        {"path": path, "bytes": size, "sha256": digest}
        for path, size, digest in entries
    ]


def _canonical_payload() -> dict[str, Any]:
    content: dict[str, Any] = {
        "schema_version": PRELIMINARY_GATE_SCHEMA_VERSION,
        "gate_id": "pending",
        "milestone": "M18",
        "title": "GridEval bounded online development gate",
        "status": PRELIMINARY_GATE_STATUS,
        "executes_actions": False,
        "source_lineage": {
            "project_id": PROJECT_ID,
            "mission_id": MISSION_ID,
            "M18_decision_id": M18_DECISION_ID,
            "superseded_M18_decision_id": SUPERSEDED_M18_DECISION_ID,
            "M18_backbrief_journal_id": M18_BACKBRIEF_JOURNAL_ID,
            "M18_approval_journal_id": M18_APPROVAL_JOURNAL_ID,
            "online_PI_directive_journal_id": ONLINE_PI_DIRECTIVE_JOURNAL_ID,
            "online_confirmation_brief_journal_id": (
                ONLINE_CONFIRMATION_BRIEF_JOURNAL_ID
            ),
            "online_PI_confirmation_journal_id": (
                ONLINE_PI_CONFIRMATION_JOURNAL_ID
            ),
            "preliminary_first_decision_id": PRELIMINARY_FIRST_DECISION_ID,
            "M17_evidence_journal_id": M17_EVIDENCE_JOURNAL_ID,
            "M17_commit": M17_COMMIT,
            "M17_matrix_id": M17_MATRIX_ID,
        },
        "bound_assets": _file_manifest(BOUND_ASSETS),
        "partition_registry": list(PARTITION_REGISTRY),
        "preliminary_permissions": dict(PRELIMINARY_PERMISSIONS),
        "authorization_requirements": sorted({
            "action_type_must_match_partition_purpose",
            "all_outputs_classified_PRELIMINARY_ONLY",
            "all_inputs_code_config_and_outputs_content_addressed",
            "all_runtime_trials_have_a_paired_benign_lineage",
            "create_once_outputs_no_overwrite",
            "failures_refusals_timeouts_and_aborts_retained",
            "final_evaluation_access_flag_false",
            "fixed_budget_identifier_before_execution",
            "M18_preflight_zero_issues",
            "physical_field_actuator_flag_false",
            "runtime_component_teardown_recorded",
            "seed_registered_in_exactly_one_purpose_partition",
            "service_start_or_restart_flag_false",
        }),
        "service_boundary": {
            "LLM": {
                "identity": LLM_SERVICE_IDENTITY,
                "must_already_be_running": True,
                "start_or_restart_allowed": False,
            },
            "embedding": {
                "identity": EMBEDDING_SERVICE_IDENTITY,
                "must_use_existing_project_service": True,
                "start_or_restart_allowed": False,
                "live_identity_must_be_recorded_per_action": True,
            },
            "runtime_components": {
                "may_start_ephemeral_local_components": True,
                "must_record_process_and_version_identity": True,
                "must_record_teardown_status": True,
                "physical_field_connection_allowed": False,
            },
        },
        "final_seals": dict(FINAL_SEALS),
        "classification_policy": {
            "required_label": "PRELIMINARY_ONLY",
            "may_tune_design_from_development_partitions": True,
            "may_tune_design_from_preliminary_holdout": False,
            "may_support_confirmatory_claims": False,
            "prohibited_claim_classes": [
                "confirmatory_effect",
                "statistical_significance_as_final_evidence",
                "generalization",
                "publication_grade_defense_effectiveness",
            ],
        },
        "preliminary_package_completion": {
            "required_sections": [
                "scope_and_partition_registry",
                "source_and_resource_manifests",
                "environment_code_config_and_service_hashes",
                "trial_matrix_coverage_and_deviations",
                "detector_calibration_and_false_alarm_evidence",
                "paired_physical_harm_alarm_and_operational_cost_results",
                "failed_refused_timed_out_aborted_and_negative_runs",
                "preliminary_effect_sizes_intervals_and_known_limitations",
            ],
            "external_consultation_after_completion": True,
            "later_final_freeze_decision_required": True,
        },
        "abort_conditions": sorted({
            "bound_asset_drift",
            "cross_partition_seed_use_or_overlap",
            "evaluation_partition_or_seed_access",
            "existing_output_would_be_overwritten",
            "final_or_confirmatory_label_on_preliminary_output",
            "missing_pair_budget_or_content_address",
            "physical_field_actuation_requested",
            "service_start_or_restart_requested",
            "silent_failure_or_invalid_action_exclusion",
            "unregistered_action_partition_or_seed",
        }),
        "next_action": {
            "id": "M19_preliminary_runtime_qualification",
            "partition_role": "runtime_qualification",
            "initial_scope": "benign_lineage_then_one_paired_single_window_smoke",
            "max_windows_per_run": 1,
            "may_use_final_evaluation": False,
            "must_pass_M18_action_request_validation": True,
        },
    }
    content["gate_id"] = preliminary_gate_id_for(content)
    return content


@dataclass(frozen=True)
class PreliminaryOnlyGate:
    """Immutable semantic representation of the M18 governance overlay."""

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
        canonical = _canonical_payload()
        if not isinstance(content, Mapping) or set(content) != set(canonical):
            raise ContractViolation("M18 preliminary gate top-level fields drift")
        if content.get("schema_version") != PRELIMINARY_GATE_SCHEMA_VERSION:
            raise ContractViolation("unsupported M18 preliminary gate schema_version")
        if content.get("gate_id") != preliminary_gate_id_for(content):
            raise ContractViolation("M18 preliminary gate content address mismatch")
        if content.get("status") != PRELIMINARY_GATE_STATUS:
            raise ContractViolation("M18 preliminary gate status drift")
        if content.get("executes_actions") is not False:
            raise ContractViolation("M18 gate must not execute an action")
        for field, expected in canonical.items():
            if field == "gate_id":
                continue
            if content[field] != expected:
                raise ContractViolation(f"M18 {field} drift")
        _validate_partition_disjointness(content["partition_registry"])


def _validate_partition_disjointness(partitions: Sequence[Mapping[str, Any]]) -> None:
    owner_by_seed: dict[int, str] = {}
    for partition in partitions:
        role = str(partition["role"])
        for seed in partition["seeds"]:
            if seed in owner_by_seed:
                raise ContractViolation(
                    f"M18 partition overlap:{seed}:{owner_by_seed[seed]}:{role}"
                )
            owner_by_seed[seed] = role


def build_preliminary_only_gate() -> PreliminaryOnlyGate:
    """Build the canonical M18 governance contract."""

    return PreliminaryOnlyGate(_canonical_payload())


def load_preliminary_only_gate(path: str | Path) -> PreliminaryOnlyGate:
    """Load and validate an M18 governance artifact."""

    return PreliminaryOnlyGate(json.loads(Path(path).read_text(encoding="utf-8")))


def verify_bound_assets(repo_root: str | Path) -> list[str]:
    """Return exact-byte issues for M18-bound inputs."""

    root = Path(repo_root)
    issues: list[str] = []
    for relative_path, expected_bytes, expected_sha256 in BOUND_ASSETS:
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


def verify_checked_in_preliminary_gate(repo_root: str | Path) -> list[str]:
    """Verify the full M17 chain and checked-in M18 artifact."""

    root = Path(repo_root)
    issues = [
        f"M17:{issue}" for issue in verify_checked_in_trial_matrix(root)
    ]
    issues.extend(verify_bound_assets(root))
    artifact = root / "v3/g7_confirmatory/artifacts/preliminary_only_gate_m18.json"
    try:
        stored = load_preliminary_only_gate(artifact).to_dict()
        if stored != build_preliminary_only_gate().to_dict():
            issues.append("preliminary_gate:differs_from_canonical_build")
    except (ContractViolation, OSError, ValueError, TypeError) as exc:
        issues.append(f"preliminary_gate:{exc}")
    return issues


def validate_preliminary_action_request(request: Mapping[str, Any]) -> list[str]:
    """Return fail-closed issues for a proposed M18 preliminary action."""

    issues: list[str] = []
    if not isinstance(request, Mapping) or set(request) != ACTION_REQUEST_FIELDS:
        return ["action_request_fields_drift"]

    action_type = request["action_type"]
    role = request["partition_role"]
    seed = request["seed"]
    if action_type not in ACTION_PARTITIONS:
        issues.append("action_type_not_authorized")
    elif role not in ACTION_PARTITIONS[action_type]:
        issues.append("action_partition_purpose_mismatch")

    partition = next(
        (item for item in PARTITION_REGISTRY if item["role"] == role), None
    )
    if partition is None:
        issues.append("partition_role_not_registered")
    else:
        if seed not in partition["seeds"]:
            issues.append("seed_not_registered_for_partition")
        if not partition["may_read"]:
            issues.append("partition_is_sealed")
        if partition["classification"] != "PRELIMINARY_ONLY":
            issues.append("partition_not_preliminary_only")

    if request["output_classification"] != "PRELIMINARY_ONLY":
        issues.append("output_not_preliminary_only")
    if request["create_once"] is not True:
        issues.append("output_not_create_once")
    if request["retain_failures"] is not True:
        issues.append("failure_retention_not_enabled")
    if request["final_evaluation_data_accessed"] is not False:
        issues.append("final_evaluation_access_requested")
    if request["physical_field_actuator"] is not False:
        issues.append("physical_field_actuation_requested")
    if request["starts_or_restarts_service"] is not False:
        issues.append("service_start_or_restart_requested")

    for field in ("manifest_sha256", "code_sha256", "config_sha256"):
        value = request[field]
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            issues.append(f"invalid_{field}")
    for field in ("action_id", "budget_id"):
        if not isinstance(request[field], str) or not request[field]:
            issues.append(f"invalid_{field}")

    if action_type in RUNTIME_ACTIONS and not request["paired_benign_id"]:
        issues.append("paired_benign_lineage_required")
    if action_type == "local_LLM_inference":
        if request["local_service_identity"] != LLM_SERVICE_IDENTITY:
            issues.append("LLM_service_identity_mismatch")
    elif action_type == "embedding_inference":
        identity = request["local_service_identity"]
        if not isinstance(identity, str) or not identity.startswith(
            EMBEDDING_SERVICE_IDENTITY
        ):
            issues.append("embedding_service_identity_mismatch")
    elif request["local_service_identity"] is not None:
        issues.append("unexpected_local_service_identity")
    return sorted(set(issues))
