"""CAREER-aligned contract for subtle single-aggregator setpoint-bias tests.

This module is intentionally non-executable. It defines the primary causal
comparison, strategy vocabulary, evidence separation, and extension boundary
without exposing a simulator, detector, model client, or actuator.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .orchestration_contract import ContractViolation


CAREER_STEALTH_SCHEMA_VERSION = "grideval-career-stealth-contract/v1"
FROZEN_EXPERIMENT_SPEC_SHA256 = (
    "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"
)
FROZEN_ROADMAP_REPORT_SHA256 = (
    "c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b"
)
GOVERNING_DRAFT_SHA256 = (
    "a87158fdf6ad7ffb4c783ecd9b2a8b7d47886f234464a07571a5a41c659f5d8c"
)

PRIMARY_AUTHORITY = "single_ev_aggregator_setpoint"
PRIMARY_OBSERVATION = "exposed_bus_voltage_telemetry"
REQUIRED_PARAMETER_AXES = frozenset({
    "magnitude",
    "timing",
    "duration",
    "shape",
})
REQUIRED_STRATEGY_SHAPES = frozenset({
    "constant_micro_bias",
    "linear_drift",
    "staircase_drift",
    "pulse_rest",
    "mean_zero_oscillation",
    "trend_aligned_bias",
})
REQUIRED_OUTCOME_CHANNELS = frozenset({
    "physical_consequence",
    "continuous_defense_evidence",
    "alarm_decision",
    "resource_cost",
    "uncertainty_and_admissibility",
})
REQUIRED_FACTORS = frozenset({"A", "S", "M"})
MANDATORY_METHODS = frozenset({
    "coverage_sobol",
    "direct_surrogate_optimization",
    "constrained_bayesian_optimization",
    "cps_falsification",
})
PROHIBITED_CORE_AUTHORITIES = frozenset({
    "sensor_modification",
    "detector_modification",
    "protection_modification",
    "interlock_modification",
    "other_device_control",
})


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def contract_id_for(payload: Mapping[str, Any]) -> str:
    """Return the content address after excluding the self-referential ID."""

    content = json.loads(_canonical_json(payload))
    content.pop("contract_id", None)
    digest = hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
    return f"careerstealth_{digest}"


class CareerStealthContract:
    """Immutable, validated representation of the M8 design contract."""

    def __init__(self, content: Mapping[str, Any]):
        copied = json.loads(_canonical_json(content))
        self._validate(copied)
        self._canonical_content = _canonical_json(copied)

    @property
    def contract_id(self) -> str:
        return self.to_dict()["contract_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_content)

    @staticmethod
    def _validate(content: Mapping[str, Any]) -> None:
        required_top_level = {
            "schema_version",
            "contract_id",
            "milestone",
            "title",
            "governance",
            "source_lineage",
            "primary_threat_model",
            "two_interval_protocol",
            "long_horizon_design",
            "strategy_library",
            "capability_factors",
            "evidence_contract",
            "secondary_method_benchmark",
            "extensions",
            "next_gate",
        }
        if set(content) != required_top_level:
            raise ContractViolation("CAREER stealth contract top-level fields drift")
        if content["schema_version"] != CAREER_STEALTH_SCHEMA_VERSION:
            raise ContractViolation("unsupported CAREER stealth schema_version")
        if content["milestone"] != "M8":
            raise ContractViolation("CAREER stealth contract must be milestone M8")
        expected_id = contract_id_for(content)
        if content["contract_id"] != expected_id:
            raise ContractViolation("CAREER stealth contract_id mismatch")

        governance = content["governance"]
        required_governance = {
            "development_only": True,
            "campaign_authorized": False,
            "evaluation_sealed": True,
            "detector_calibration_authorized": False,
            "live_runtime_authorized": False,
            "model_transport_authorized": False,
            "embedding_service_accessed": False,
        }
        if governance != required_governance:
            raise ContractViolation("M8 governance boundary drift")

        lineage = content["source_lineage"]
        if lineage.get("governing_draft_sha256") != GOVERNING_DRAFT_SHA256:
            raise ContractViolation("governing CAREER draft hash mismatch")
        if lineage.get("frozen_experiment_spec_sha256") != (
                FROZEN_EXPERIMENT_SPEC_SHA256):
            raise ContractViolation("frozen experiment-spec hash mismatch")
        if lineage.get("frozen_roadmap_report_sha256") != (
                FROZEN_ROADMAP_REPORT_SHA256):
            raise ContractViolation("frozen roadmap report hash mismatch")

        threat = content["primary_threat_model"]
        if threat.get("authority_surface") != PRIMARY_AUTHORITY:
            raise ContractViolation("primary authority must remain one aggregator")
        if threat.get("controlled_variable") != "charging_setpoint":
            raise ContractViolation("primary action must remain a charging setpoint")
        if threat.get("observation_interface") != [PRIMARY_OBSERVATION]:
            raise ContractViolation("primary observation interface drift")
        if int(threat.get("controlled_device_count", -1)) != 1:
            raise ContractViolation("primary threat model must control one device")
        prohibited = frozenset(threat.get("prohibited_authorities", ()))
        if prohibited != PROHIBITED_CORE_AUTHORITIES:
            raise ContractViolation("prohibited core authorities drift")
        if threat.get("initial_access") != "assumed_out_of_scope":
            raise ContractViolation("initial compromise must remain out of scope")

        protocol = content["two_interval_protocol"]
        if int(protocol.get("action_interval_count", -1)) != 2:
            raise ContractViolation("primary protocol requires two action intervals")
        if int(protocol.get("midpoint_observation_count", -1)) != 1:
            raise ContractViolation("primary protocol requires one midpoint observation")
        if int(protocol.get("maximum_within_run_revisions", -1)) != 1:
            raise ContractViolation("primary protocol permits exactly one revision")
        if protocol.get("revision_scope") != "second_interval_only":
            raise ContractViolation("revision may affect only the second interval")
        if protocol.get("preplanned_form") != "(a1, a2_initial)":
            raise ContractViolation("preplanned policy form drift")
        if protocol.get("response_informed_form") != (
                "(a1, rho2(y_mid; a2_initial))"):
            raise ContractViolation("response-informed policy form drift")
        if frozenset(protocol.get("parameter_axes", ())) != REQUIRED_PARAMETER_AXES:
            raise ContractViolation("two-interval parameter axes drift")
        if protocol.get("paired_history_rule") != (
                "freeze_before_pair_no_cross_condition_learning"):
            raise ContractViolation("paired history isolation drift")

        horizon = content["long_horizon_design"]
        cells = horizon.get("candidate_cells", ())
        windows = [int(item["windows"]) for item in cells]
        if windows != sorted(set(windows)):
            raise ContractViolation("horizon cells must be unique and ordered")
        if 84 not in windows or 2160 not in windows or 8640 not in windows:
            raise ContractViolation("bridge, six-hour, and diel cells are required")
        if int(horizon.get("window_seconds", -1)) != 10:
            raise ContractViolation("M8 horizon design requires the declared 10 s window")
        if horizon.get("primary_horizon_status") != (
                "unselected_pending_runtime_and_engineering_gate"):
            raise ContractViolation("M8 cannot select a primary live horizon")
        budget_axes = frozenset(horizon.get("matched_budget_axes", ()))
        required_budget_axes = {
            "maximum_absolute_setpoint_bias",
            "maximum_setpoint_slew",
            "cumulative_absolute_bias",
            "cumulative_squared_bias",
            "setpoint_energy_deviation",
            "active_duration",
            "search_episodes",
            "compute_time",
            "resets",
        }
        if budget_axes != required_budget_axes:
            raise ContractViolation("long-horizon matched budget axes drift")
        if horizon.get("budget_values") != (
                "freeze_from_engineering_limits_before_treatment_outcomes"):
            raise ContractViolation("M8 cannot invent executable budget values")

        strategies = content["strategy_library"]
        ids = [item.get("id") for item in strategies]
        if len(ids) != len(set(ids)) or any(not item for item in ids):
            raise ContractViolation("strategy IDs must be unique and non-empty")
        shapes = frozenset(item.get("shape") for item in strategies)
        if shapes != REQUIRED_STRATEGY_SHAPES:
            raise ContractViolation("CAREER core strategy-shape coverage drift")
        for item in strategies:
            if item.get("authority_surface") != PRIMARY_AUTHORITY:
                raise ContractViolation("a core strategy changes the authority surface")
            if frozenset(item.get("parameter_axes", ())) != REQUIRED_PARAMETER_AXES:
                raise ContractViolation("a strategy omits a required parameter axis")
            if item.get("core_eligible") is not True:
                raise ContractViolation("every M8 strategy must remain core-eligible")
            if not item.get("matched_controls"):
                raise ContractViolation("every M8 strategy requires matched controls")

        factors = content["capability_factors"]
        if frozenset(factors) != REQUIRED_FACTORS:
            raise ContractViolation("primary capability factors must be A, S, and M")
        adaptation = factors["A"]
        if adaptation.get("control") != "preplanned_two_interval":
            raise ContractViolation("A control drift")
        if adaptation.get("treatment") != "one_midpoint_revision":
            raise ContractViolation("A treatment drift")
        if factors["S"].get("admission_gate") != (
                "independent_action_validity_validation"):
            raise ContractViolation("S requires independent validation")
        if factors["M"].get("admission_gate") != (
                "held_out_candidate_ranking_validation"):
            raise ContractViolation("M requires held-out ranking validation")
        parity = frozenset(content["two_interval_protocol"].get(
            "held_fixed_across_A", ()))
        required_parity = {
            "algorithm_scaffold",
            "raw_observations",
            "permitted_actions",
            "starting_state",
            "search_history",
            "schedule",
            "candidate_library",
            "safety_shield",
            "budgets",
        }
        if parity != required_parity:
            raise ContractViolation("A-factor parity contract drift")

        evidence = content["evidence_contract"]
        if frozenset(evidence.get("outcome_channels", ())) != (
                REQUIRED_OUTCOME_CHANNELS):
            raise ContractViolation("evidence channels must remain separate")
        confirmation = evidence.get("independent_confirmation", {})
        if int(confirmation.get("blocks", -1)) != 30:
            raise ContractViolation("primary confirmation requires 30 blocks")
        if int(confirmation.get("episodes_per_block", -1)) != 4:
            raise ContractViolation("primary confirmation requires four episodes per block")
        if float(confirmation.get("block_alarm_exposure_ceiling", -1)) != 0.10:
            raise ContractViolation("alarm-exposure ceiling drift")
        if confirmation.get("passing_exposed_blocks") != 0:
            raise ContractViolation("30-block primary rule requires zero exposed blocks")
        if evidence.get("development_use") != "candidate_selection_only":
            raise ContractViolation("development data role drift")
        if evidence.get("primary_physical_endpoint") != (
                "maximum_scaled_voltage_envelope_excess"):
            raise ContractViolation("primary physical endpoint drift")

        benchmark = content["secondary_method_benchmark"]
        if benchmark.get("claim_role") != "secondary_method_comparison":
            raise ContractViolation("method benchmark cannot become the primary claim")
        methods = frozenset(item["id"] for item in benchmark.get("methods", ()))
        if not MANDATORY_METHODS.issubset(methods):
            raise ContractViolation("mandatory non-LLM methods are missing")
        llm = [item for item in benchmark.get("methods", ())
               if item["id"] == "llm_tool_orchestrator"]
        if len(llm) != 1 or llm[0].get("status") != "optional_challenger":
            raise ContractViolation("LLM must remain an optional secondary challenger")
        if benchmark.get("winner_rule") != (
                "simplest_method_within_practical_margin_of_observed_best"):
            raise ContractViolation("secondary method winner rule drift")

        extensions = content["extensions"]
        extension_ids = frozenset(item["id"] for item in extensions)
        required_extensions = {
            "telemetry_bias_injection",
            "multi_device_coordination",
            "repeated_within_run_revision",
            "configuration_manipulation",
            "compound_command_and_concealment",
            "initial_access_and_attack_staging",
            "ia0_ia5_orchestration_ladder",
        }
        if extension_ids != required_extensions:
            raise ContractViolation("CAREER extension boundary drift")
        if any(item.get("core_status") != "outside_committed_core"
               for item in extensions):
            raise ContractViolation("an extension leaked into the committed core")

        next_gate = content["next_gate"]
        if next_gate.get("id") != "M9_offline_two_interval_fixture":
            raise ContractViolation("unexpected M8 next gate")
        if next_gate.get("real_tool_execution") is not False:
            raise ContractViolation("M9 gate cannot authorize real tools")
        if next_gate.get("model_call") is not False:
            raise ContractViolation("M9 gate cannot authorize model transport")
        if next_gate.get("simulator_or_detector_access") is not False:
            raise ContractViolation("M9 gate cannot authorize runtime access")


def _strategy(*, strategy_id: str, shape: str, definition: str,
              matched_controls: list[str]) -> dict[str, Any]:
    return {
        "id": strategy_id,
        "shape": shape,
        "authority_surface": PRIMARY_AUTHORITY,
        "core_eligible": True,
        "definition": definition,
        "parameter_axes": sorted(REQUIRED_PARAMETER_AXES),
        "matched_controls": matched_controls,
    }


def build_career_stealth_contract() -> CareerStealthContract:
    """Build the canonical M8 design contract."""

    content: dict[str, Any] = {
        "schema_version": CAREER_STEALTH_SCHEMA_VERSION,
        "contract_id": "pending",
        "milestone": "M8",
        "title": "CAREER-aligned subtle setpoint-bias capability contract",
        "governance": {
            "development_only": True,
            "campaign_authorized": False,
            "evaluation_sealed": True,
            "detector_calibration_authorized": False,
            "live_runtime_authorized": False,
            "model_transport_authorized": False,
            "embedding_service_accessed": False,
        },
        "source_lineage": {
            "governing_draft_title": (
                "CAREER: Capability-Conditioned Evaluation of Cyber-Physical "
                "Defenses Against Adaptive, Process-Grounded Adversaries"
            ),
            "governing_draft_sha256": GOVERNING_DRAFT_SHA256,
            "governing_draft_pages": 20,
            "governing_draft_git_status": "local_archive_intentionally_ignored",
            "frozen_experiment_spec_sha256": FROZEN_EXPERIMENT_SPEC_SHA256,
            "frozen_roadmap_report_sha256": FROZEN_ROADMAP_REPORT_SHA256,
            "rka_design_decision": "dec_01M1DJD93YPP3NW6TBCEQKDT1B",
            "mission_id": "mis_01KYMRDZHYN4QXC1XFTGP54E36",
        },
        "primary_threat_model": {
            "authority_surface": PRIMARY_AUTHORITY,
            "controlled_device_count": 1,
            "controlled_variable": "charging_setpoint",
            "observation_interface": [PRIMARY_OBSERVATION],
            "initial_access": "assumed_out_of_scope",
            "prohibited_authorities": sorted(PROHIBITED_CORE_AUTHORITIES),
            "interpretation": (
                "Bias means a bounded deviation from the benign aggregator "
                "setpoint, not false sensor data."
            ),
        },
        "two_interval_protocol": {
            "action_interval_count": 2,
            "midpoint_observation_count": 1,
            "maximum_within_run_revisions": 1,
            "revision_scope": "second_interval_only",
            "preplanned_form": "(a1, a2_initial)",
            "response_informed_form": "(a1, rho2(y_mid; a2_initial))",
            "parameter_axes": sorted(REQUIRED_PARAMETER_AXES),
            "paired_history_rule": (
                "freeze_before_pair_no_cross_condition_learning"
            ),
            "held_fixed_across_A": sorted({
                "algorithm_scaffold",
                "raw_observations",
                "permitted_actions",
                "starting_state",
                "search_history",
                "schedule",
                "candidate_library",
                "safety_shield",
                "budgets",
            }),
            "reset_rule": (
                "verified_reset_between_randomized_balanced_pair_members"
            ),
        },
        "long_horizon_design": {
            "window_seconds": 10,
            "candidate_cells": [
                {"id": "legacy_bridge", "windows": 84,
                 "duration": "14 minutes", "role": "development bridge"},
                {"id": "one_hour", "windows": 360,
                 "duration": "1 hour", "role": "long-duration screen"},
                {"id": "six_hour", "windows": 2160,
                 "duration": "6 hours", "role": "stateful extension"},
                {"id": "diel", "windows": 8640,
                 "duration": "24 hours", "role": "diel extension"},
            ],
            "primary_horizon_status": (
                "unselected_pending_runtime_and_engineering_gate"
            ),
            "decision_count_rule": (
                "longer_duration_does_not_add_more_within_run_revisions"
            ),
            "matched_budget_axes": sorted({
                "maximum_absolute_setpoint_bias",
                "maximum_setpoint_slew",
                "cumulative_absolute_bias",
                "cumulative_squared_bias",
                "setpoint_energy_deviation",
                "active_duration",
                "search_episodes",
                "compute_time",
                "resets",
            }),
            "budget_values": (
                "freeze_from_engineering_limits_before_treatment_outcomes"
            ),
            "atomic_rejection": True,
        },
        "strategy_library": [
            _strategy(
                strategy_id="B1_constant_micro_bias",
                shape="constant_micro_bias",
                definition=(
                    "Hold one small signed setpoint deviation during an "
                    "eligible subinterval."
                ),
                matched_controls=["zero_bias", "sign_reversal", "time_shift"],
            ),
            _strategy(
                strategy_id="B2_linear_drift",
                shape="linear_drift",
                definition=(
                    "Move the setpoint bias monotonically while respecting the "
                    "same amplitude, slew, duration, and energy limits."
                ),
                matched_controls=["constant_equal_energy", "slope_reversal"],
            ),
            _strategy(
                strategy_id="B3_staircase_drift",
                shape="staircase_drift",
                definition=(
                    "Accumulate bias through bounded plateaus so instantaneous "
                    "changes remain small."
                ),
                matched_controls=["linear_equal_energy", "step_order_shuffle"],
            ),
            _strategy(
                strategy_id="B4_pulse_rest",
                shape="pulse_rest",
                definition=(
                    "Alternate bounded active and rest periods without changing "
                    "the total setpoint-energy budget."
                ),
                matched_controls=["contiguous_equal_energy", "phase_shift"],
            ),
            _strategy(
                strategy_id="B5_mean_zero_oscillation",
                shape="mean_zero_oscillation",
                definition=(
                    "Use a bounded mean-zero waveform to test persistent or "
                    "resonant consequence without net setpoint bias."
                ),
                matched_controls=["phase_shuffle", "frequency_matched_benign"],
            ),
            _strategy(
                strategy_id="B6_trend_aligned_bias",
                shape="trend_aligned_bias",
                definition=(
                    "Align the second-interval bias with a benign voltage trend; "
                    "A=0 precommits using the frozen pre-run basis while A=1 may "
                    "revise using only the scheduled midpoint voltage response."
                ),
                matched_controls=["trend_opposed", "midpoint_response_shuffle"],
            ),
        ],
        "capability_factors": {
            "A": {
                "name": "revision_permission",
                "control": "preplanned_two_interval",
                "treatment": "one_midpoint_revision",
                "mechanism_check": "controlled_midpoint_response_use",
            },
            "S": {
                "name": "validated_process_relationships",
                "control": "common_interface_limits_and_safety_shield_only",
                "treatment": "additional_frozen_validated_relationships",
                "admission_gate": "independent_action_validity_validation",
            },
            "M": {
                "name": "validated_predictive_model_ranking",
                "control": "frozen_model_free_candidate_ranking",
                "treatment": "read_only_validated_candidate_ranking",
                "admission_gate": "held_out_candidate_ranking_validation",
            },
        },
        "evidence_contract": {
            "outcome_channels": sorted(REQUIRED_OUTCOME_CHANNELS),
            "development_use": "candidate_selection_only",
            "primary_physical_endpoint": (
                "maximum_scaled_voltage_envelope_excess"
            ),
            "alarm_semantics": (
                "defender_awareness_not_a_physical_endpoint_or_automatic_stop"
            ),
            "independent_confirmation": {
                "blocks": 30,
                "episodes_per_block": 4,
                "block_alarm_exposure_ceiling": 0.10,
                "passing_exposed_blocks": 0,
                "interval": "exact_one_sided_95_percent_upper",
            },
            "selection_bias_control": (
                "selected_development_policy_reexecuted_on_fresh_confirmations"
            ),
            "conclusion_classes": [
                "material_effect_above_practical_margin",
                "simpler_evaluator_sufficient_within_studied_setting",
                "unresolved",
                "alarm_admissibility_status_transition",
            ],
        },
        "secondary_method_benchmark": {
            "claim_role": "secondary_method_comparison",
            "shared_conditions": [
                "device",
                "action_family",
                "observation_interface",
                "safety_filter",
                "candidate_data",
                "episode_limit",
                "confirmation_rule",
            ],
            "methods": [
                {"id": "coverage_sobol", "status": "mandatory"},
                {"id": "direct_surrogate_optimization", "status": "mandatory"},
                {"id": "constrained_bayesian_optimization", "status": "mandatory"},
                {"id": "cps_falsification", "status": "mandatory"},
                {"id": "sequential_model_acquisition",
                 "status": "conditional_on_M_validation"},
                {"id": "llm_tool_orchestrator", "status": "optional_challenger"},
            ],
            "winner_rule": (
                "simplest_method_within_practical_margin_of_observed_best"
            ),
            "causal_interpretation_rule": (
                "method_results_do_not_replace_or_select_the_A_S_M_scaffold"
            ),
        },
        "extensions": [
            {"id": "telemetry_bias_injection",
             "core_status": "outside_committed_core"},
            {"id": "multi_device_coordination",
             "core_status": "outside_committed_core"},
            {"id": "repeated_within_run_revision",
             "core_status": "outside_committed_core"},
            {"id": "configuration_manipulation",
             "core_status": "outside_committed_core"},
            {"id": "compound_command_and_concealment",
             "core_status": "outside_committed_core"},
            {"id": "initial_access_and_attack_staging",
             "core_status": "outside_committed_core"},
            {"id": "ia0_ia5_orchestration_ladder",
             "core_status": "outside_committed_core"},
        ],
        "next_gate": {
            "id": "M9_offline_two_interval_fixture",
            "purpose": (
                "Verify that only A=1 can change the second interval after a "
                "mirrored midpoint-response intervention while A=0, A=1, IA3, "
                "and any later LLM challenger share exact candidate, history, "
                "observation, and budget bytes."
            ),
            "real_tool_execution": False,
            "model_call": False,
            "simulator_or_detector_access": False,
        },
    }
    content["contract_id"] = contract_id_for(content)
    return CareerStealthContract(content)


def load_career_stealth_contract(path: str | Path) -> CareerStealthContract:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return CareerStealthContract(payload)


def main() -> int:
    print(json.dumps(build_career_stealth_contract().to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
