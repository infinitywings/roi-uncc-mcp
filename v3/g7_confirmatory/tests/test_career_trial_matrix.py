from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from g7confirm.career_trial_matrix import (
    HARD_STOPS,
    INPUT_ASSETS,
    PARITY_INVARIANTS,
    POWER_SYSTEM_INVARIANTS,
    TRIAL_MATRIX_SCHEMA_VERSION,
    TRIAL_MATRIX_STATUS,
    CareerTrialMatrix,
    build_career_trial_matrix,
    load_career_trial_matrix,
    trial_matrix_id_for,
    verify_checked_in_trial_matrix,
    verify_input_assets,
)
from g7confirm.cli import build_parser, main
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
ARTIFACT_PATH = PACKAGE_ROOT / "artifacts/career_trial_matrix_m17.json"
SCHEMA_PATH = PACKAGE_ROOT / "career_trial_matrix.schema.json"
EXPECTED_MATRIX_ID = (
    "m17trialmatrix_8ce2c71c1eab533f04a75b15ea17d3e223587bbf4089149d6ac1e8105cbd169d"
)


def readdress(payload: dict) -> dict:
    payload["matrix_id"] = trial_matrix_id_for(payload)
    return payload


def run_cli(argv: list[str]) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv)
    payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    return exit_code, payload, stderr.getvalue()


class CareerTrialMatrixTests(unittest.TestCase):
    def test_checked_in_artifact_matches_canonical_builder(self):
        stored = load_career_trial_matrix(ARTIFACT_PATH)
        built = build_career_trial_matrix()

        self.assertEqual(stored.to_dict(), built.to_dict())
        self.assertEqual(stored.matrix_id, EXPECTED_MATRIX_ID)
        self.assertEqual(stored.matrix_id, trial_matrix_id_for(stored.to_dict()))
        self.assertEqual(stored.to_dict()["status"], TRIAL_MATRIX_STATUS)

    def test_schema_is_closed_and_names_contract_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            TRIAL_MATRIX_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(
            schema["properties"]["governance"]["additionalProperties"]
        )

    def test_input_assets_and_upstream_M16_are_exact(self):
        self.assertEqual(len(INPUT_ASSETS), 6)
        self.assertEqual(verify_input_assets(REPO_ROOT), [])
        self.assertEqual(verify_checked_in_trial_matrix(REPO_ROOT), [])

    def test_CAREER_core_and_red_team_extension_are_not_pooled(self):
        tracks = build_career_trial_matrix().to_dict()["scope_tracks"]

        self.assertEqual(
            [track["id"] for track in tracks],
            ["CAREER_CORE_ASM", "RED_TEAM_IA_EXTENSION"],
        )
        self.assertEqual(
            tracks[0]["pooling_rule"], "never_pool_with_red_team_extension"
        )
        self.assertEqual(
            tracks[1]["pooling_rule"], "report_separately_from_CAREER_core"
        )

    def test_ladder_adds_one_declared_capability_per_transition(self):
        ladder = build_career_trial_matrix().to_dict()["capability_ladder"]

        self.assertEqual(
            [rung["id"] for rung in ladder],
            [
                "IA0_static_frozen",
                "IA1_library_open_loop",
                "IA2_rule_interactive",
                "IA3_nonllm_adaptive",
                "IA4_llm_orchestrator",
                "IA5_llm_planner_critic",
            ],
        )
        self.assertEqual(len({rung["adds_only"] for rung in ladder}), 6)
        self.assertTrue(
            all(rung["knowledge_and_authority_orthogonal"] for rung in ladder)
        )
        self.assertEqual(ladder[4]["matched_against"], "IA3_nonllm_adaptive")
        self.assertEqual(ladder[5]["matched_against"], "IA4_compute_matched")

    def test_subtle_long_horizon_strategies_have_matched_controls(self):
        strategies = build_career_trial_matrix().to_dict()["strategy_families"]
        by_id = {strategy["id"]: strategy for strategy in strategies}

        self.assertEqual(len(strategies), 10)
        for strategy in strategies:
            self.assertTrue(strategy["matched_control"])
            self.assertEqual(
                strategy["numeric_parameters"],
                "deferred_to_M18_preliminary_registry",
            )
        for required in (
            "S3_ramp_drift",
            "S6_riding_the_wave",
            "S7_pq_coordinated",
            "S9_state_exhaustion",
            "S10_adaptive_evasion",
        ):
            self.assertIn(required, by_id)

    def test_black_gray_white_profiles_change_information_not_authority(self):
        contract = build_career_trial_matrix().to_dict()["knowledge_contract"]

        self.assertEqual(
            contract["axes"],
            ["grid", "detector", "training_data", "defense", "feedback"],
        )
        self.assertEqual(
            [profile["label"] for profile in contract["profiles"]],
            [
                "black_box_zero_feedback",
                "black_box_delayed_feedback",
                "gray_box",
                "white_box",
            ],
        )
        self.assertNotIn("authority", contract["axes"])
        self.assertNotIn("compute", contract["axes"])

    def test_detector_defense_stack_exposes_known_gaps_and_costs(self):
        stacks = build_career_trial_matrix().to_dict()[
            "detector_defense_contracts"
        ]

        self.assertEqual(len(stacks["detectors"]), 8)
        self.assertEqual(len(stacks["defenses"]), 5)
        self.assertTrue(all(item["known_gap"] for item in stacks["detectors"]))
        self.assertTrue(
            all(item["operational_cost_required"] for item in stacks["defenses"])
        )

    def test_parity_and_power_system_invariants_are_complete(self):
        matrix = build_career_trial_matrix().to_dict()

        self.assertEqual(matrix["parity_invariants"], PARITY_INVARIANTS)
        self.assertEqual(
            matrix["power_system_invariants"], POWER_SYSTEM_INVARIANTS
        )
        self.assertIn(
            "preserve_local_Volt_VAR_arbitration_and_remote_Q_override_semantics",
            matrix["power_system_invariants"],
        )
        self.assertIn(
            "same_tool_schemas_outputs_side_effects_and_call_caps_for_IA3_IA4",
            matrix["parity_invariants"],
        )

    def test_M17_does_not_authorize_preliminary_or_final_execution(self):
        matrix = build_career_trial_matrix().to_dict()
        governance = matrix["governance"]

        self.assertFalse(matrix["executable"])
        self.assertFalse(governance["M17_may_execute_trials"])
        self.assertFalse(
            governance[
                "M17_may_assign_sources_partitions_resources_or_thresholds"
            ]
        )
        self.assertTrue(
            governance["M18_gate_required_before_any_preliminary_runtime_action"]
        )
        self.assertTrue(
            governance["final_evaluation_and_confirmatory_campaign_sealed"]
        )

    def test_final_stage_remains_empty_and_sealed(self):
        stage = build_career_trial_matrix().to_dict()["trial_stages"][-1]

        self.assertEqual(stage["id"], "T3_final_confirmatory")
        self.assertEqual(
            stage["mode"],
            "SEALED_PENDING_POST_PRELIMINARY_EXTERNAL_CONSULTATION",
        )
        self.assertEqual(stage["rungs"], [])
        self.assertEqual(stage["knowledge_profiles"], [])

    def test_hard_stops_cover_leakage_parity_and_failure_accounting(self):
        self.assertIn("evaluation_partition_or_seed_access", HARD_STOPS)
        self.assertIn(
            "knowledge_authority_budget_or_interface_mismatch", HARD_STOPS
        )
        self.assertIn(
            "silent_failed_run_refusal_timeout_or_invalid_action_removal",
            HARD_STOPS,
        )

    def test_unaddressed_mutation_breaks_content_address(self):
        payload = build_career_trial_matrix().to_dict()
        payload["governance"]["M17_may_execute_trials"] = True

        with self.assertRaisesRegex(ContractViolation, "content address"):
            CareerTrialMatrix(payload)

    def test_readdressed_execution_mutation_is_rejected(self):
        payload = build_career_trial_matrix().to_dict()
        payload["governance"]["M17_may_execute_trials"] = True

        with self.assertRaisesRegex(ContractViolation, "governance"):
            CareerTrialMatrix(readdress(payload))

    def test_readdressed_ladder_or_knowledge_mutation_is_rejected(self):
        ladder_payload = copy.deepcopy(build_career_trial_matrix().to_dict())
        ladder_payload["capability_ladder"][4]["matched_against"] = (
            "IA2_rule_interactive"
        )
        with self.assertRaisesRegex(ContractViolation, "capability_ladder"):
            CareerTrialMatrix(readdress(ladder_payload))

        knowledge_payload = copy.deepcopy(build_career_trial_matrix().to_dict())
        knowledge_payload["knowledge_contract"]["profiles"][0]["K"][
            "detector"
        ] = "exact"
        with self.assertRaisesRegex(ContractViolation, "knowledge_contract"):
            CareerTrialMatrix(readdress(knowledge_payload))

    def test_trial_matrix_cli_is_read_only_and_has_no_unseal_command(self):
        exit_code, payload, stderr = run_cli([
            "career-trial-matrix-preflight",
            "--repo-root",
            str(REPO_ROOT),
        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["status"], TRIAL_MATRIX_STATUS)
        self.assertFalse(payload["executable"])
        self.assertTrue(payload["final_evaluation_sealed"])
        self.assertEqual(payload["issues"], [])
        self.assertEqual(payload["files_created_or_modified"], 0)
        self.assertEqual(payload["RKA_writes"], 0)

        choices = build_parser()._subparsers._group_actions[0].choices
        self.assertIn("career-trial-matrix-preflight", choices)
        self.assertNotIn("career-trial-matrix-unseal", choices)
        self.assertNotIn("career-final-evaluation-open", choices)


if __name__ == "__main__":
    unittest.main()
