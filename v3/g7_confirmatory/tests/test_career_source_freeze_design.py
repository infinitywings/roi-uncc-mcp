from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from g7confirm.career_source_freeze_design import (
    M9_CANDIDATE_IDS,
    M12_STATUS,
    PARTITION_ROLES,
    PARTITION_STATUS,
    PROFILE_STATUS,
    REVIEW_STATUS,
    SOURCE_FREEZE_DESIGN_SCHEMA_VERSION,
    CareerSourceFreezeDesign,
    build_career_source_freeze_design,
    contract_id_for,
    load_career_source_freeze_design,
)
from g7confirm.career_resource_admission import (
    M9_CANDIDATE_LIBRARY_FINGERPRINT,
)
from g7confirm.career_threshold_hold import THRESHOLD_STATUS
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = (
    PACKAGE_ROOT / "artifacts" / "career_source_freeze_design_m12.json"
)
SCHEMA_PATH = PACKAGE_ROOT / "career_source_freeze_design.schema.json"
EXPECTED_CONTRACT_ID = (
    "careersourcefreeze_648776649fcaa43a3ecce5fab19aced608c427646b086c0f6"
    "bc2128a611a61f3"
)


def readdress(payload: dict) -> dict:
    payload["contract_id"] = contract_id_for(payload)
    return payload


class CareerSourceFreezeDesignTests(unittest.TestCase):
    def test_checked_in_artifact_matches_canonical_builder(self):
        built = build_career_source_freeze_design()
        stored = load_career_source_freeze_design(ARTIFACT_PATH)

        self.assertEqual(stored.to_dict(), built.to_dict())
        self.assertEqual(stored.contract_id, EXPECTED_CONTRACT_ID)
        self.assertEqual(stored.to_dict()["status"], M12_STATUS)

    def test_schema_is_parseable_and_names_design_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            SOURCE_FREEZE_DESIGN_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])

    def test_all_empirical_slots_remain_uninstantiated(self):
        profiles = build_career_source_freeze_design().to_dict()[
            "clean_source_profiles"
        ]

        for factor in ("S", "M"):
            self.assertEqual(profiles[factor]["status"], PROFILE_STATUS)
            self.assertTrue(profiles[factor]["empirical_slots"])
            self.assertTrue(
                all(value is None
                    for value in profiles[factor]["empirical_slots"].values())
            )
            self.assertFalse(
                profiles[factor]["output_manifest_template"]
                ["scientific_values_present"]
            )

    def test_partition_roles_are_unassigned_and_pairwise_disjoint(self):
        registry = build_career_source_freeze_design().to_dict()[
            "partition_registry"
        ]

        self.assertEqual(registry["status"], PARTITION_STATUS)
        self.assertEqual(
            [item["id"] for item in registry["roles"]], list(PARTITION_ROLES)
        )
        self.assertTrue(all(value is None
                            for value in registry["assignments"].values()))
        self.assertTrue(registry["pairwise_disjoint_empirical_blocks"])
        self.assertFalse(registry["cross_factor_empirical_block_reuse"])

    def test_readdressed_partition_assignment_is_rejected(self):
        payload = build_career_source_freeze_design().to_dict()
        payload["partition_registry"]["assignments"][
            "S_source_derivation"
        ] = "block_001"

        with self.assertRaisesRegex(ContractViolation, "assign empirical"):
            CareerSourceFreezeDesign(readdress(payload))

    def test_S_is_single_aggregator_active_setpoint_only(self):
        profile = build_career_source_freeze_design().to_dict()[
            "clean_source_profiles"]["S"]
        derivation = profile["derivation_contract"]

        self.assertEqual(
            derivation["authority_surface"], "single_ev_aggregator_setpoint"
        )
        self.assertEqual(derivation["controlled_device_count"], 1)
        self.assertEqual(
            derivation["controlled_variable"], "active_charging_setpoint"
        )
        self.assertEqual(
            derivation["reactive_power_axis"],
            "outside_primary_scope_not_zero_imputed",
        )
        self.assertFalse(derivation["other_device_authority"])

    def test_M_is_bound_to_exact_M9_library_and_primary_endpoint(self):
        derivation = build_career_source_freeze_design().to_dict()[
            "clean_source_profiles"]["M"]["derivation_contract"]

        self.assertEqual(
            derivation["candidate_library_fingerprint"],
            M9_CANDIDATE_LIBRARY_FINGERPRINT,
        )
        self.assertEqual(
            derivation["ordered_candidate_ids"], list(M9_CANDIDATE_IDS)
        )
        self.assertEqual(
            derivation["predicted_endpoint"],
            "maximum_scaled_voltage_envelope_excess",
        )
        self.assertEqual(
            derivation["physical_instantiation_binding"],
            "required_separate_manifest_preserving_M9_candidate_ids",
        )
        self.assertEqual(
            derivation["algorithm_family"],
            "unselected_before_source_review",
        )

    def test_M_adds_no_observation_authority_or_online_update(self):
        profile = build_career_source_freeze_design().to_dict()[
            "clean_source_profiles"]["M"]

        self.assertFalse(
            profile["information_grant"]["raw_observation_interface_changed"]
        )
        self.assertFalse(
            profile["information_grant"]["action_authority_changed"]
        )
        self.assertFalse(
            profile["derivation_contract"]["new_raw_observations_added"]
        )
        self.assertFalse(profile["derivation_contract"]["online_update"])

    def test_S_and_M_cannot_depend_on_each_other_or_contaminated_outcomes(self):
        payload = build_career_source_freeze_design().to_dict()
        registry = payload["partition_registry"]

        self.assertEqual(
            registry["derived_resource_dependency"],
            "S_and_M_must_not_depend_on_each_others_derived_resource",
        )
        for factor in ("S", "M"):
            prohibited = set(
                payload["clean_source_profiles"][factor]["prohibited_inputs"]
            )
            self.assertIn("treatment_arm_outcomes", prohibited)
            self.assertIn("detector_or_alarm_outcomes", prohibited)
            self.assertIn("evaluation_records", prohibited)
            self.assertIn("other_factor_derived_resource", prohibited)

    def test_review_receipts_are_empty_and_require_distinct_reviewers(self):
        review = build_career_source_freeze_design().to_dict()[
            "review_protocol"
        ]

        self.assertEqual(review["status"], REVIEW_STATUS)
        self.assertEqual(review["required_distinct_reviewers"], 2)
        self.assertFalse(review["author_may_review"])
        for template in review["receipt_templates"].values():
            self.assertIsNone(template["reviewer_id"])
            self.assertIsNone(template["bound_manifest_sha256"])
            self.assertIsNone(template["decision"])
            self.assertIsNone(template["receipt_id"])
            self.assertEqual(template["reviewed_profile_ids"], [])

    def test_readdressed_review_decision_is_rejected(self):
        payload = copy.deepcopy(build_career_source_freeze_design().to_dict())
        receipt = payload["review_protocol"]["receipt_templates"][
            "source_lineage_and_partition_review"
        ]
        receipt["reviewer_id"] = "reviewer_1"
        receipt["decision"] = "accept"

        with self.assertRaisesRegex(ContractViolation, "was populated"):
            CareerSourceFreezeDesign(readdress(payload))

    def test_governance_cannot_enable_real_source_generation(self):
        payload = build_career_source_freeze_design().to_dict()
        payload["governance"]["real_source_generation_authorized"] = True

        with self.assertRaisesRegex(ContractViolation, "governance"):
            CareerSourceFreezeDesign(readdress(payload))

    def test_content_address_rejects_unacknowledged_mutation(self):
        payload = build_career_source_freeze_design().to_dict()
        payload["clean_source_profiles"]["M"]["derivation_contract"][
            "candidate_library_fingerprint"
        ] = "sha256_" + ("0" * 64)

        with self.assertRaisesRegex(ContractViolation, "contract_id mismatch"):
            CareerSourceFreezeDesign(payload)

    def test_readdressed_M_candidate_drift_still_fails_semantics(self):
        payload = build_career_source_freeze_design().to_dict()
        payload["clean_source_profiles"]["M"]["derivation_contract"][
            "ordered_candidate_ids"
        ].reverse()

        with self.assertRaisesRegex(ContractViolation, "candidate IDs"):
            CareerSourceFreezeDesign(readdress(payload))

    def test_status_and_next_gate_remain_non_executable(self):
        payload = build_career_source_freeze_design().to_dict()
        status = payload["canonical_status"]
        next_gate = payload["next_gate"]

        self.assertEqual(status["S_scientific_threshold"], THRESHOLD_STATUS)
        self.assertEqual(status["M_scientific_threshold"], THRESHOLD_STATUS)
        self.assertEqual(status["evaluation"], "SEALED")
        self.assertEqual(status["campaign"], "HOLD")
        self.assertFalse(next_gate["may_freeze_real_sources"])
        self.assertFalse(next_gate["may_select_scientific_thresholds"])
        self.assertFalse(next_gate["model_or_embedding_call"])
        self.assertFalse(next_gate["simulator_or_detector_access"])
        self.assertFalse(next_gate["evaluation_access"])


if __name__ == "__main__":
    unittest.main()
