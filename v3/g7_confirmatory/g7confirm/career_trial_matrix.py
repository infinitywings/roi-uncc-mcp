"""M17 non-executable attack-defense trial-matrix contract.

The contract separates the minimal CAREER two-interval causal design from the
broader IA0-IA5 red-team extension.  It fixes comparison structure, knowledge
profiles, detector/defense exposure, power-system invariants, and promotion
rules without assigning sources, seeds, thresholds, or executable resources.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .career_internal_advisory import verify_checked_in_internal_advisory
from .orchestration_contract import ContractViolation


TRIAL_MATRIX_SCHEMA_VERSION = "grideval-career-trial-matrix/v1"
TRIAL_MATRIX_STATUS = "OFFLINE_MATRIX_FROZEN_PRELIMINARY_GATE_REQUIRED"
PROJECT_ID = "prj_01KYMPK10PE9YH1TJ84PAVB9Z6"
MISSION_ID = "mis_01KYMRDZHYN4QXC1XFTGP54E36"
M17_DECISION_ID = "dec_01M1MAPMSFXE38S9QD8KSYG4XW"
PRELIMINARY_FIRST_DECISION_ID = "dec_01M1MDB6Q97DXACWMN2EVE7Q9Q"
PI_DIRECTIVE_JOURNAL_ID = "jrn_01M1MC21TXF1A682E6ZHQN7C70"
CONFIRMATION_BRIEF_JOURNAL_ID = "jrn_01M1MC2K7D22HNX6CQ6PGB3B6A"
PI_CONFIRMATION_JOURNAL_ID = "jrn_01M1MDAS6MN35JQ2NWFEMPEZXW"
RESOLVED_EXTERNAL_CHECKPOINT_ID = "chk_01M1M97DN5EWDKSM4T1CMT76J6"
M16_BASE_COMMIT = "179ebbb5ee7e68b9e6b2acd20503fe6d1473d290"
M16_ADVISORY_ID = (
    "m16advisory_b391e3b7601eae38ba1c9b5ecc5edc6115918be0043e9258327ef701b578933c"
)

INPUT_ASSETS = (
    (
        "v3/g7_confirmatory/M8_CAREER_STEALTH_BIAS_DESIGN.md",
        11540,
        "98397028c636be788e8a8d168193d562f8a2c2e39cf3d9f7ab46608dadfda6ad",
    ),
    (
        "v3/g7_confirmatory/RED_TEAM_DESIGN.md",
        8094,
        "155e5b9240555c741005df84dd5b4642ca5fe9ad2a9f1757391585621dae5607",
    ),
    (
        "v3/g7_confirmatory/artifacts/ai_v2_component_matrix.json",
        7306,
        "19ac61d36fbc31993739cf45a670951867d08561d8a3dfebae255d8344785559",
    ),
    (
        "v3/g7_confirmatory/roadmap_2026/roadmap_blueprint.json",
        69675,
        "59a2878f407e2b559a4a1cc21cd2d5f971e6a35e481dcc448c4f4a18e72430b5",
    ),
    (
        "v3/g7_confirmatory/M16_CAREER_INTERNAL_ADVISORY_REPORT.md",
        7524,
        "06737faa61376028f9e0fb398eb7cb7f473bbaee5bfcd8865af379c1162c8bd2",
    ),
    (
        "v3/g7_confirmatory/artifacts/career_internal_advisory_m16.json",
        17678,
        "679462039a5e2b811cf676d69d840b9101a0a8e37e2d9cd61062faae69d8f82f",
    ),
)

KNOWLEDGE_AXES = ("grid", "detector", "training_data", "defense", "feedback")
KNOWLEDGE_LEVELS = ("none", "partial", "exact")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def trial_matrix_id_for(payload: Mapping[str, Any]) -> str:
    content = json.loads(_canonical_json(payload))
    content.pop("matrix_id", None)
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return f"m17trialmatrix_{digest}"


def _file_manifest(
    entries: Sequence[tuple[str, int, str]],
) -> list[dict[str, Any]]:
    return [
        {"path": path, "bytes": size, "sha256": digest}
        for path, size, digest in entries
    ]


def _scope_tracks() -> list[dict[str, Any]]:
    return [
        {
            "id": "CAREER_CORE_ASM",
            "role": "primary_capability_conditioned_causal_design",
            "authority": "one_EV_aggregator_active_power_setpoint_only",
            "temporal_structure": "two_intervals_exactly_one_scheduled_midpoint_observation",
            "treatment": "one_response_informed_revision_of_interval_two",
            "controls": [
                "preplanned_interval_two",
                "same_candidate_library",
                "same_observation_schedule",
                "same_action_and_compute_budgets",
            ],
            "pooling_rule": "never_pool_with_red_team_extension",
        },
        {
            "id": "RED_TEAM_IA_EXTENSION",
            "role": "secondary_robustness_and_attacker_capability_benchmark",
            "authority": "AS_A_legitimate_DER_command_authority_only",
            "temporal_structure": "bounded_multiwindow_orchestration",
            "treatment": "IA0_IA5_and_declared_knowledge_profiles",
            "controls": [
                "adjacent_rung",
                "mechanism_matched",
                "compute_matched",
                "defense_unaware",
            ],
            "pooling_rule": "report_separately_from_CAREER_core",
        },
    ]


def _capability_ladder() -> list[dict[str, Any]]:
    rows = [
        (
            "IA0_static_frozen",
            None,
            "frozen_schedule",
            "Replay one predeclared strategy instance without outcome-conditioned switching.",
            "static_lower_bound",
        ),
        (
            "IA1_library_open_loop",
            "IA0_static_frozen",
            "strategy_library_selection",
            "Select and parameterize one frozen strategy card before the first window.",
            "IA1_minus_IA0",
        ),
        (
            "IA2_rule_interactive",
            "IA1_library_open_loop",
            "deterministic_feedback_switching",
            "Use a frozen rule table over delayed typed observations; no learning.",
            "IA2_minus_IA1",
        ),
        (
            "IA3_nonllm_adaptive",
            "IA2_rule_interactive",
            "algorithmic_credit_assignment",
            "Use deterministic bandit, Bayesian, or evolutionary adaptation over the shared surface.",
            "IA3_minus_IA2",
        ),
        (
            "IA4_llm_orchestrator",
            "IA3_nonllm_adaptive",
            "llm_strategy_and_tool_orchestration",
            "Replace only the IA3 decision core with an LLM emitting externally validated typed plans.",
            "IA4_minus_IA3",
        ),
        (
            "IA5_llm_planner_critic",
            "IA4_compute_matched",
            "bounded_critique_and_revision",
            "Add one critique-and-revision step without another environment observation.",
            "IA5_minus_IA4_compute_matched",
        ),
    ]
    return [
        {
            "id": rung_id,
            "matched_against": predecessor,
            "adds_only": increment,
            "controller_contract": contract,
            "estimand": estimand,
            "knowledge_and_authority_orthogonal": True,
        }
        for rung_id, predecessor, increment, contract, estimand in rows
    ]


def _strategy_families() -> list[dict[str, str]]:
    rows = [
        ("S1_step_corner", "immediate feasible P/Q corner", "maximum-power mechanic", "fast displacement and saturation"),
        ("S2_pulse_intermittent", "sparse pulse-rest schedule", "equal-energy contiguous bias", "excursion and recovery sequence"),
        ("S3_ramp_drift", "low-slew cumulative bias", "equal-energy constant and slope reversal", "small innovation with accumulating displacement"),
        ("S4_periodic_duty_cycle", "bounded amplitude-period schedule", "phase-shuffled equal-energy schedule", "spectral peak and path-dependent alarm"),
        ("S5_event_synchronized", "alignment with benign state transitions", "same actions at randomized offsets", "harm concentrated near exogenous events"),
        ("S6_riding_the_wave", "alignment with benign voltage direction", "trend-opposed and midpoint-response-shuffled", "incremental harm with low residual innovation"),
        ("S7_pq_coordinated", "coupled P/Q action under inverter kVA limits", "P-only and Q-only ablations", "device-specific saturation and P/Q asymmetry"),
        ("S8_spatial_subset", "phase- and location-aware DER subset", "uniform and random equal-authority subsets", "phase-specific propagation and imbalance"),
        ("S9_state_exhaustion", "SOC, irradiance, ramp, or mode-memory preparation", "state-reset and history-shuffled", "late-run harm after headroom depletion"),
        ("S10_adaptive_evasion", "joint harm and alarm-risk adaptation", "defense-unaware and transfer attacks", "harm-alarm Pareto improvement"),
    ]
    return [
        {
            "id": row[0],
            "grid_mechanism": row[1],
            "matched_control": row[2],
            "diagnostic_signature": row[3],
            "numeric_parameters": "deferred_to_M18_preliminary_registry",
        }
        for row in rows
    ]


def _knowledge_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": "K0_black_no_feedback",
            "label": "black_box_zero_feedback",
            "K": {"grid": "partial", "detector": "none", "training_data": "none", "defense": "none", "feedback": "none"},
            "exposure": "public_device_interface_and_bounds_only",
        },
        {
            "id": "K1_black_delayed_binary",
            "label": "black_box_delayed_feedback",
            "K": {"grid": "partial", "detector": "none", "training_data": "none", "defense": "none", "feedback": "partial"},
            "exposure": "typed_telemetry_plus_delayed_binary_success_or_alarm",
        },
        {
            "id": "K2_gray_balanced",
            "label": "gray_box",
            "K": {"grid": "partial", "detector": "partial", "training_data": "partial", "defense": "partial", "feedback": "partial"},
            "exposure": "approximate_topology_detector_family_and_bounded_probe_history",
        },
        {
            "id": "K3_white_exact",
            "label": "white_box",
            "K": {"grid": "exact", "detector": "exact", "training_data": "exact", "defense": "exact", "feedback": "exact"},
            "exposure": "frozen_exact_bytes_parameters_state_and_declared_training_distribution",
        },
    ]


def _detector_defense_contracts() -> dict[str, list[dict[str, Any]]]:
    detectors = [
        ("D0_envelope_policy", "command_and_device_limits", "invalid_or_policy_violating_commands", "within-envelope harmful commands"),
        ("D1_physics_residual_vsct", "network_measurements_and_sensitivity", "physics residual inconsistency", "physically consistent authority abuse"),
        ("D2_sequential_cusum", "calibrated_innovation_stream", "persistent small shifts", "operating-point drift false alarms"),
        ("D3_cross_layer_intent_response", "intent_delivery_acceptance_realized_PQ_response", "cross-layer inconsistency and authority abuse", "untrusted lineage"),
        ("D4_hybrid_central_local_ae", "central_residual_and_local_DER_features", "complementary system and local anomalies", "adaptive reconstruction evasion"),
        ("D5_temporal_state_prediction", "multivariate_time_series_and_optional_topology", "ramp and stateful temporal deviation", "compute and topology shift"),
        ("D6_graph_localization", "topology_and_multivariate_history", "phase-aware spatial anomalies", "feeder-transfer uncertainty"),
        ("DF_transparent_fusion", "frozen_member_scores_and_alarms", "complementary detection evidence", "trajectory false-alarm inflation"),
    ]
    defenses = [
        ("M0_alarm_only", "passive_observation", "separate detection from mitigation"),
        ("M1_safe_command_screen", "reject_or_project_unsafe_commands", "preventive intent-aware control"),
        ("M2_local_autonomous_fallback", "revert_to_frozen_safe_local_mode", "limit remote-authority abuse"),
        ("M3_physics_aware_watermark", "bounded_private_excitation", "active stealth-attack detection"),
        ("M4_event_triggered_mtd", "bounded_model_changing_response", "cost-aware active defense"),
    ]
    return {
        "detectors": [
            {"id": x[0], "inputs": x[1], "detects": x[2], "known_gap": x[3], "threshold_source": "M18_preliminary_only_or_later"}
            for x in detectors
        ],
        "defenses": [
            {"id": x[0], "action": x[1], "role": x[2], "operational_cost_required": True}
            for x in defenses
        ],
    }


def _trial_stages() -> list[dict[str, Any]]:
    return [
        {
            "id": "T0_offline_contract_qualification",
            "mode": "synthetic_non_executable",
            "rungs": ["IA0", "IA1", "IA2", "IA3", "IA4", "IA5"],
            "knowledge_profiles": ["K0", "K1", "K2", "K3"],
            "defense_scope": "schema_and_information_boundary_only",
            "promotion_rule": "all_contract_and_parity_checks_pass",
        },
        {
            "id": "T1_preliminary_mechanism_screen",
            "mode": "requires_M18_PRELIMINARY_ONLY_gate",
            "rungs": ["IA0", "IA1", "IA2", "IA3", "IA4"],
            "knowledge_profiles": ["K0", "K1"],
            "defense_scope": "D0_D3_with_M0_first_then_M1_M2",
            "promotion_rule": "retain_negative_results_and_advance_only_distinct_mechanisms_or_frontier_points",
        },
        {
            "id": "T2_preliminary_adaptive_stress",
            "mode": "requires_frozen_preliminary_detector_and_M18_amendment",
            "rungs": ["IA2", "IA3", "IA4", "IA5"],
            "knowledge_profiles": ["K1", "K2", "K3"],
            "defense_scope": "D0_D6_DF_crossed_sequentially_with_M0_M4",
            "promotion_rule": "outcome_blind_protocol_checks_then_predeclared_harm_alarm_cost_frontier",
        },
        {
            "id": "T3_final_confirmatory",
            "mode": "SEALED_PENDING_POST_PRELIMINARY_EXTERNAL_CONSULTATION",
            "rungs": [],
            "knowledge_profiles": [],
            "defense_scope": "none",
            "promotion_rule": "later_explicit_final_freeze_decision_required",
        },
    ]


PARITY_INVARIANTS = sorted({
    "same_action_authority",
    "same_candidate_library_and_composition_grammar_for_IA3_IA4_IA5",
    "same_feedback_delay_and_history_representation",
    "same_invalid_action_and_refusal_accounting",
    "same_outer_rollout_and_simulator_time_budget",
    "same_seed_lineage_within_each_paired_preliminary_trial",
    "same_tool_schemas_outputs_side_effects_and_call_caps_for_IA3_IA4",
    "same_total_model_call_and_token_caps_for_IA5_and_IA4_compute_control",
    "knowledge_vector_does_not_encode_authority_or_compute",
})

POWER_SYSTEM_INVARIANTS = sorted({
    "index_results_by_operating_point_phase_location_and_DER_type",
    "log_requested_admitted_accepted_and_realized_PQ_separately",
    "preserve_BESS_SOC_and_PV_irradiance_as_state_not_static_metadata",
    "preserve_inverter_kVA_saturation_priority_ramp_and_mode_transitions",
    "preserve_local_Volt_VAR_arbitration_and_remote_Q_override_semantics",
    "record_network_delivery_delay_loss_reordering_and_duplicate_lineage",
    "report_paired_benign_incremental_harm_not_attack_trajectory_alone",
    "separate_physical_consequence_continuous_score_alarm_and_mitigation_cost",
    "treat_alarm_exposure_per_trajectory_or_independent_block_not_per_row",
})

HARD_STOPS = sorted({
    "cross_track_pooling_between_CAREER_core_and_red_team_extension",
    "evaluation_partition_or_seed_access",
    "final_threshold_or_resource_lock",
    "hidden_detector_score_or_oracle_information",
    "knowledge_authority_budget_or_interface_mismatch",
    "silent_failed_run_refusal_timeout_or_invalid_action_removal",
    "silent_simulation_time_advance_or_unpriced_tool_side_effect",
    "unregistered_source_partition_threshold_detector_or_runtime_resource",
    "unchecked_LLM_text_to_actuator_path",
})


def _canonical_payload() -> dict[str, Any]:
    content: dict[str, Any] = {
        "schema_version": TRIAL_MATRIX_SCHEMA_VERSION,
        "matrix_id": "pending",
        "milestone": "M17",
        "title": "CAREER attack-defense trial matrix",
        "status": TRIAL_MATRIX_STATUS,
        "executable": False,
        "source_lineage": {
            "project_id": PROJECT_ID,
            "mission_id": MISSION_ID,
            "M17_decision_id": M17_DECISION_ID,
            "preliminary_first_decision_id": PRELIMINARY_FIRST_DECISION_ID,
            "pi_directive_journal_id": PI_DIRECTIVE_JOURNAL_ID,
            "confirmation_brief_journal_id": CONFIRMATION_BRIEF_JOURNAL_ID,
            "pi_confirmation_journal_id": PI_CONFIRMATION_JOURNAL_ID,
            "resolved_external_checkpoint_id": RESOLVED_EXTERNAL_CHECKPOINT_ID,
            "M16_base_commit": M16_BASE_COMMIT,
            "M16_advisory_id": M16_ADVISORY_ID,
        },
        "input_assets": _file_manifest(INPUT_ASSETS),
        "scope_tracks": _scope_tracks(),
        "capability_ladder": _capability_ladder(),
        "strategy_families": _strategy_families(),
        "knowledge_contract": {
            "axes": list(KNOWLEDGE_AXES),
            "levels": list(KNOWLEDGE_LEVELS),
            "profiles": _knowledge_profiles(),
            "white_box_release_rule": "exact_detector_defense_and_training_information_only_after_the_relevant_preliminary_package_is_frozen",
        },
        "detector_defense_contracts": _detector_defense_contracts(),
        "trial_stages": _trial_stages(),
        "estimable_contrasts": [
            "IA1_minus_IA0_strategy_library_value",
            "IA2_minus_IA1_feedback_switching_value",
            "IA3_minus_IA2_algorithmic_adaptation_value",
            "IA4_minus_IA3_LLM_orchestration_value",
            "IA5_minus_IA4_compute_matched_critique_value",
            "K1_minus_K0_delayed_feedback_value",
            "K2_minus_K1_gray_box_information_value",
            "K3_minus_K2_white_box_information_value",
            "mechanism_minus_matched_control",
            "defense_aware_minus_defense_unaware_under_equal_K",
            "mitigation_minus_alarm_only_with_operational_cost",
        ],
        "parity_invariants": PARITY_INVARIANTS,
        "power_system_invariants": POWER_SYSTEM_INVARIANTS,
        "governance": {
            "preliminary_first_authorized_in_RKA": True,
            "M17_may_execute_trials": False,
            "M17_may_assign_sources_partitions_resources_or_thresholds": False,
            "M18_gate_required_before_any_preliminary_runtime_action": True,
            "all_preliminary_outputs_must_be_labeled_PRELIMINARY_ONLY": True,
            "M14_review_machinery_preserved_as_dormant_provenance": True,
            "post_preliminary_external_consultation_required_before_final_freeze": True,
            "final_evaluation_and_confirmatory_campaign_sealed": True,
        },
        "hard_stops": HARD_STOPS,
        "next_gate": {
            "id": "M18_preliminary_only_governance",
            "may_authorize_bounded_preliminary_runtime": True,
            "must_register_source_partition_resource_threshold_and_run_purpose": True,
            "must_preserve_untouched_final_evaluation_partition": True,
            "may_unlock_final_evaluation_or_confirmatory_claims": False,
        },
    }
    content["matrix_id"] = trial_matrix_id_for(content)
    return content


@dataclass(frozen=True)
class CareerTrialMatrix:
    """Immutable semantic representation of the M17 trial matrix."""

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
        canonical = _canonical_payload()
        if not isinstance(content, Mapping) or set(content) != set(canonical):
            raise ContractViolation("M17 trial matrix top-level fields drift")
        if content.get("schema_version") != TRIAL_MATRIX_SCHEMA_VERSION:
            raise ContractViolation("unsupported M17 trial matrix schema_version")
        if content.get("matrix_id") != trial_matrix_id_for(content):
            raise ContractViolation("M17 trial matrix content address mismatch")
        if content.get("status") != TRIAL_MATRIX_STATUS:
            raise ContractViolation("M17 trial matrix status drift")
        if content.get("executable") is not False:
            raise ContractViolation("M17 trial matrix must remain non-executable")
        for field, expected in canonical.items():
            if field == "matrix_id":
                continue
            if content[field] != expected:
                raise ContractViolation(f"M17 {field} drift")


def build_career_trial_matrix() -> CareerTrialMatrix:
    """Build the canonical M17 non-executable trial matrix."""

    return CareerTrialMatrix(_canonical_payload())


def load_career_trial_matrix(path: str | Path) -> CareerTrialMatrix:
    """Load and validate an M17 trial-matrix artifact."""

    return CareerTrialMatrix(json.loads(Path(path).read_text(encoding="utf-8")))


def verify_input_assets(repo_root: str | Path) -> list[str]:
    """Return exact-byte issues for M17 inputs."""

    root = Path(repo_root)
    issues: list[str] = []
    for relative_path, expected_bytes, expected_sha256 in INPUT_ASSETS:
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


def verify_checked_in_trial_matrix(repo_root: str | Path) -> list[str]:
    """Verify M16, M17 inputs, and the checked-in canonical artifact."""

    root = Path(repo_root)
    issues = [
        f"M16:{issue}"
        for issue in verify_checked_in_internal_advisory(root)
    ]
    issues.extend(verify_input_assets(root))
    artifact = root / "v3/g7_confirmatory/artifacts/career_trial_matrix_m17.json"
    try:
        stored = load_career_trial_matrix(artifact).to_dict()
        if stored != build_career_trial_matrix().to_dict():
            issues.append("trial_matrix:differs_from_canonical_build")
    except (ContractViolation, OSError, ValueError, TypeError) as exc:
        issues.append(f"trial_matrix:{exc}")
    return issues
