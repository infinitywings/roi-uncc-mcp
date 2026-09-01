from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from g7confirm.career_stealth_contract import (
    CAREER_STEALTH_SCHEMA_VERSION,
    CareerStealthContract,
    build_career_stealth_contract,
    contract_id_for,
    load_career_stealth_contract,
)
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PACKAGE_ROOT / "artifacts" / "career_stealth_contract_m8.json"
SCHEMA_PATH = PACKAGE_ROOT / "career_stealth_contract.schema.json"
EXPECTED_CONTRACT_ID = (
    "careerstealth_3091a0e686e43b483906a37733f26dfb4cef9fd90d2ae56226e47003b3cdd394"
)


def readdress(payload: dict) -> dict:
    payload["contract_id"] = contract_id_for(payload)
    return payload


class CareerStealthContractTests(unittest.TestCase):
    def test_checked_in_artifact_matches_canonical_builder(self):
        built = build_career_stealth_contract()
        stored = load_career_stealth_contract(ARTIFACT_PATH)

        self.assertEqual(built.contract_id, EXPECTED_CONTRACT_ID)
        self.assertEqual(stored.contract_id, EXPECTED_CONTRACT_ID)
        self.assertEqual(stored.to_dict(), built.to_dict())

    def test_schema_is_parseable_and_names_the_contract_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"],
                         "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            CAREER_STEALTH_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])

    def test_content_address_rejects_unacknowledged_mutation(self):
        payload = build_career_stealth_contract().to_dict()
        payload["title"] = "mutated"

        with self.assertRaisesRegex(ContractViolation, "contract_id mismatch"):
            CareerStealthContract(payload)

    def test_core_rejects_sensor_authority_even_after_readdressing(self):
        payload = build_career_stealth_contract().to_dict()
        payload["primary_threat_model"]["authority_surface"] = (
            "measurement_injection"
        )

        with self.assertRaisesRegex(ContractViolation, "one aggregator"):
            CareerStealthContract(readdress(payload))

    def test_core_rejects_more_than_one_midpoint_revision(self):
        payload = build_career_stealth_contract().to_dict()
        payload["two_interval_protocol"]["maximum_within_run_revisions"] = 2

        with self.assertRaisesRegex(ContractViolation, "exactly one revision"):
            CareerStealthContract(readdress(payload))

    def test_every_strategy_stays_on_the_same_authority_surface(self):
        payload = build_career_stealth_contract().to_dict()
        payload["strategy_library"][1]["authority_surface"] = (
            "single_ev_aggregator_plus_sensor"
        )

        with self.assertRaisesRegex(ContractViolation, "authority surface"):
            CareerStealthContract(readdress(payload))

    def test_long_duration_does_not_grant_more_decisions(self):
        payload = build_career_stealth_contract().to_dict()
        windows = [
            item["windows"]
            for item in payload["long_horizon_design"]["candidate_cells"]
        ]

        self.assertIn(8640, windows)
        self.assertEqual(
            payload["two_interval_protocol"]["action_interval_count"], 2
        )
        self.assertEqual(
            payload["two_interval_protocol"]["maximum_within_run_revisions"], 1
        )

    def test_primary_A_comparison_requires_full_parity(self):
        payload = build_career_stealth_contract().to_dict()
        payload["two_interval_protocol"]["held_fixed_across_A"].remove(
            "budgets"
        )

        with self.assertRaisesRegex(ContractViolation, "parity contract"):
            CareerStealthContract(readdress(payload))

    def test_llm_cannot_be_promoted_to_primary_claim(self):
        payload = build_career_stealth_contract().to_dict()
        payload["secondary_method_benchmark"]["claim_role"] = (
            "primary_causal_comparison"
        )

        with self.assertRaisesRegex(ContractViolation, "primary claim"):
            CareerStealthContract(readdress(payload))

    def test_evidence_channels_cannot_be_collapsed(self):
        payload = build_career_stealth_contract().to_dict()
        payload["evidence_contract"]["outcome_channels"].remove(
            "continuous_defense_evidence"
        )

        with self.assertRaisesRegex(ContractViolation, "remain separate"):
            CareerStealthContract(readdress(payload))

    def test_broader_ia_ladder_remains_an_explicit_extension(self):
        payload = build_career_stealth_contract().to_dict()
        extensions = {item["id"]: item for item in payload["extensions"]}

        self.assertEqual(
            extensions["ia0_ia5_orchestration_ladder"]["core_status"],
            "outside_committed_core",
        )

    def test_governance_flags_fail_closed(self):
        for key in (
            "campaign_authorized",
            "detector_calibration_authorized",
            "live_runtime_authorized",
            "model_transport_authorized",
            "embedding_service_accessed",
        ):
            with self.subTest(key=key):
                payload = copy.deepcopy(build_career_stealth_contract().to_dict())
                payload["governance"][key] = True
                with self.assertRaisesRegex(ContractViolation, "governance"):
                    CareerStealthContract(readdress(payload))


if __name__ == "__main__":
    unittest.main()
