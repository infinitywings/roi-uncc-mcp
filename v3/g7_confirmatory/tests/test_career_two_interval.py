from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from g7confirm.career_two_interval import (
    M8_CONTRACT_ID,
    CapabilityCondition,
    CareerTwoIntervalContract,
    SessionState,
    TWO_INTERVAL_SCHEMA_VERSION,
    TwoIntervalSession,
    build_career_two_interval_contract,
    build_m9_artifact,
    contract_id_for,
    load_m9_artifact,
    plan_id_for,
    receipt_id_for,
    run_mirrored_fixture_pair,
)
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PACKAGE_ROOT / "artifacts" / "career_two_interval_fixture_m9.json"
SCHEMA_PATH = PACKAGE_ROOT / "career_two_interval_fixture.schema.json"
EXPECTED_CONTRACT_ID = (
    "careertwoint_6d57736587a6a6ad2474392a0413b784fa9633ecfa94af572798b7419b1e73a5"
)
EXPECTED_PAIR_ID = (
    "m9pair_38433ef32d206640b826cd474ecc8c70f028d60385558b675eadc0734ec9a786"
)


class CareerTwoIntervalTests(unittest.TestCase):
    def test_checked_in_artifact_matches_canonical_builder(self):
        built = build_m9_artifact()
        stored = load_m9_artifact(ARTIFACT_PATH)

        self.assertEqual(built, stored)
        self.assertEqual(built["contract"]["contract_id"], EXPECTED_CONTRACT_ID)
        self.assertEqual(
            built["fixture_pair_evidence"]["pair_id"], EXPECTED_PAIR_ID
        )

    def test_schema_is_parseable_and_names_both_versions(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"],
                         "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            schema["properties"]["contract"]["properties"]
            ["schema_version"]["const"],
            TWO_INTERVAL_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])

    def test_A0_is_invariant_to_mirrored_midpoint_observations(self):
        pair = run_mirrored_fixture_pair(build_career_two_interval_contract())
        receipts = [item for item in pair["receipts"]
                    if item["capability_condition"] == "A0_preplanned"]

        self.assertEqual(len(receipts), 2)
        self.assertEqual(len({item["terminal_plan_id"] for item in receipts}), 1)
        self.assertEqual({item["revision_count"] for item in receipts}, {0})

    def test_A1_switches_only_the_second_interval_across_mirrors(self):
        pair = run_mirrored_fixture_pair(build_career_two_interval_contract())
        receipts = [item for item in pair["receipts"]
                    if item["capability_condition"] == "A1_response_informed"]

        self.assertEqual(len({item["terminal_plan_id"] for item in receipts}), 2)
        self.assertEqual({item["revision_count"] for item in receipts}, {1})
        self.assertEqual(
            len({item["first_interval_fingerprint"] for item in receipts}), 1
        )
        self.assertEqual(
            len({item["terminal_second_interval_fingerprint"]
                 for item in receipts}), 2
        )

    def test_all_four_receipts_share_exact_parity_and_initial_plan(self):
        pair = run_mirrored_fixture_pair(build_career_two_interval_contract())
        receipts = pair["receipts"]

        self.assertEqual(len({item["parity_fingerprint"] for item in receipts}), 1)
        self.assertEqual(len({item["initial_plan_id"] for item in receipts}), 1)
        self.assertTrue(all(pair["checks"].values()))
        self.assertEqual(pair["verdict"], "PASS_PROTOCOL_ISOLATION_ONLY")

    def test_A0_revision_attempt_fails_closed(self):
        contract = build_career_two_interval_contract()
        observation = contract.to_dict()["fixture_pair"][0]
        target = contract.to_dict()["reference_policy"]["mapping"]["negative"]
        session = TwoIntervalSession(contract, CapabilityCondition.PREPLANNED)
        session.present_midpoint(observation)

        with self.assertRaisesRegex(ContractViolation, "does not have"):
            session.revise_second_interval(target)
        self.assertEqual(session.state, SessionState.FAILED_CLOSED)

    def test_A1_may_retain_without_using_its_permission(self):
        contract = build_career_two_interval_contract()
        observation = contract.to_dict()["fixture_pair"][0]
        session = TwoIntervalSession(
            contract, CapabilityCondition.RESPONSE_INFORMED
        )
        session.present_midpoint(observation)

        receipt = session.retain_precommitted_plan()

        self.assertEqual(receipt["revision_count"], 0)
        self.assertFalse(receipt["revision_applied"])
        self.assertEqual(receipt["initial_plan_id"], receipt["terminal_plan_id"])
        self.assertEqual(session.state, SessionState.TERMINAL)

    def test_revision_before_midpoint_fails_closed(self):
        contract = build_career_two_interval_contract()
        target = contract.to_dict()["reference_policy"]["mapping"]["negative"]
        session = TwoIntervalSession(
            contract, CapabilityCondition.RESPONSE_INFORMED
        )

        with self.assertRaisesRegex(ContractViolation, "outside the midpoint"):
            session.revise_second_interval(target)
        self.assertEqual(session.state, SessionState.FAILED_CLOSED)

    def test_second_decision_after_terminal_fails_closed(self):
        contract = build_career_two_interval_contract()
        observation = contract.to_dict()["fixture_pair"][0]
        target = contract.to_dict()["reference_policy"]["mapping"]["negative"]
        session = TwoIntervalSession(
            contract, CapabilityCondition.RESPONSE_INFORMED
        )
        session.present_midpoint(observation)
        session.revise_second_interval(target)

        with self.assertRaisesRegex(ContractViolation, "outside the midpoint"):
            session.revise_second_interval(target)
        self.assertEqual(session.state, SessionState.FAILED_CLOSED)

    def test_mutated_observation_bytes_fail_closed(self):
        contract = build_career_two_interval_contract()
        observation = copy.deepcopy(contract.to_dict()["fixture_pair"][0])
        observation["trend_sign"] = "positive"
        session = TwoIntervalSession(
            contract, CapabilityCondition.RESPONSE_INFORMED
        )

        with self.assertRaisesRegex(ContractViolation, "bytes drift"):
            session.present_midpoint(observation)
        self.assertEqual(session.state, SessionState.FAILED_CLOSED)

    def test_content_address_rejects_unacknowledged_contract_mutation(self):
        payload = build_career_two_interval_contract().to_dict()
        payload["title"] = "mutated"

        with self.assertRaisesRegex(ContractViolation, "contract_id mismatch"):
            CareerTwoIntervalContract(payload)

    def test_readdressed_first_interval_mutation_still_fails(self):
        payload = build_career_two_interval_contract().to_dict()
        plan = payload["candidate_library"][1]
        plan["intervals"][0]["strategy_id"] = "B2_linear_drift"
        plan["plan_id"] = plan_id_for(plan)
        payload["contract_id"] = contract_id_for(payload)

        with self.assertRaisesRegex(ContractViolation, "first intervals"):
            CareerTwoIntervalContract(payload)

    def test_receipt_mutation_breaks_content_address(self):
        pair = run_mirrored_fixture_pair(build_career_two_interval_contract())
        receipt = copy.deepcopy(pair["receipts"][0])
        original_id = receipt["receipt_id"]
        receipt["trend_sign"] = "mutated"

        self.assertNotEqual(receipt_id_for(receipt), original_id)

    def test_governance_and_lineage_remain_offline_and_M8_bound(self):
        contract = build_career_two_interval_contract().to_dict()

        self.assertEqual(contract["source_lineage"]["m8_contract_id"],
                         M8_CONTRACT_ID)
        self.assertFalse(contract["governance"]["model_transport_authorized"])
        self.assertFalse(
            contract["governance"]["real_tool_execution_authorized"]
        )
        self.assertFalse(contract["governance"]["simulator_accessed"])
        self.assertFalse(contract["governance"]["detector_accessed"])
        self.assertFalse(contract["governance"]["embedding_service_accessed"])
        self.assertTrue(contract["governance"]["evaluation_sealed"])


if __name__ == "__main__":
    unittest.main()
