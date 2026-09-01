from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from g7confirm.career_resource_admission import (
    M9_CONTRACT_ID,
    M9_PARITY_FINGERPRINT,
    NEGATIVE_VERDICT,
    POSITIVE_VERDICT,
    REAL_RESOURCE_HOLD,
    RESOURCE_ADMISSION_SCHEMA_VERSION,
    CareerResourceAdmissionContract,
    build_career_resource_admission_contract,
    build_m10_artifact,
    build_synthetic_fixture_matrix,
    contract_id_for,
    envelope_id_for,
    evaluate_resource_admission,
    load_m10_artifact,
    receipt_id_for,
)
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PACKAGE_ROOT / "artifacts" / "career_resource_admission_m10.json"
SCHEMA_PATH = PACKAGE_ROOT / "career_resource_admission.schema.json"
EXPECTED_CONTRACT_ID = (
    "careerresource_f3b0033341368b5eca92d350d4f06906eb969dffd5855f5829e26a0f5a97c2ca"
)
EXPECTED_MATRIX_ID = (
    "m10matrix_407d4406d6fa06ec18df691364e49a17b873054c6279d116e0ec998c52f0b6f7"
)


def readdress_envelope(payload: dict) -> dict:
    payload["envelope_id"] = envelope_id_for(payload)
    return payload


class CareerResourceAdmissionTests(unittest.TestCase):
    def test_checked_in_artifact_matches_canonical_builder(self):
        built = build_m10_artifact()
        stored = load_m10_artifact(ARTIFACT_PATH)

        self.assertEqual(stored, built)
        self.assertEqual(built["contract"]["contract_id"], EXPECTED_CONTRACT_ID)
        self.assertEqual(
            built["synthetic_fixture_evidence"]["matrix_id"],
            EXPECTED_MATRIX_ID,
        )

    def test_schema_is_parseable_and_names_contract_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"],
                         "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            schema["properties"]["contract"]["properties"]
            ["schema_version"]["const"],
            RESOURCE_ADMISSION_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])

    def test_positive_S_and_M_fixtures_pass_structure_only(self):
        matrix = build_synthetic_fixture_matrix(
            build_career_resource_admission_contract()
        )
        positives = [item for item in matrix["receipts"] if item["accepted"]]

        self.assertEqual({item["factor"] for item in positives}, {"S", "M"})
        self.assertEqual({item["verdict"] for item in positives},
                         {POSITIVE_VERDICT})
        self.assertEqual(
            {item["real_resource_status_after"] for item in positives},
            {REAL_RESOURCE_HOLD},
        )

    def test_every_preregistered_negative_fixture_fails_with_expected_code(self):
        matrix = build_synthetic_fixture_matrix(
            build_career_resource_admission_contract()
        )
        by_fixture = {item["fixture_id"]: item for item in matrix["receipts"]}
        expected = {
            "S_partition_overlap": "validation_partition_not_independent",
            "M_post_evidence_threshold_freeze": (
                "threshold_not_frozen_before_evidence"
            ),
            "S_parity_expansion": "parity_expansion_or_drift",
            "M_candidate_library_drift": "candidate_library_drift",
            "M_online_update": "online_update_or_mutation_enabled",
            "S_treatment_outcome_leak": "treatment_outcome_leak",
        }

        for fixture_id, reason in expected.items():
            with self.subTest(fixture_id=fixture_id):
                receipt = by_fixture[fixture_id]
                self.assertFalse(receipt["accepted"])
                self.assertEqual(receipt["verdict"], NEGATIVE_VERDICT)
                self.assertIn(reason, receipt["reason_codes"])

    def test_real_resource_envelope_cannot_be_automatically_admitted(self):
        contract = build_career_resource_admission_contract()
        matrix = build_synthetic_fixture_matrix(contract)
        payload = copy.deepcopy(matrix["envelopes"][0])
        payload["synthetic_fixture"] = False
        readdress_envelope(payload)

        receipt = evaluate_resource_admission(contract, payload)

        self.assertFalse(receipt["accepted"])
        self.assertIn("real_resource_not_authorized", receipt["reason_codes"])
        self.assertEqual(receipt["real_resource_status_after"],
                         REAL_RESOURCE_HOLD)

    def test_metric_profile_substitution_fails_closed(self):
        contract = build_career_resource_admission_contract()
        payload = copy.deepcopy(
            build_synthetic_fixture_matrix(contract)["envelopes"][0]
        )
        payload["validation_protocol"]["metric_thresholds"].pop(
            "operating_envelope_coverage"
        )
        readdress_envelope(payload)

        receipt = evaluate_resource_admission(contract, payload)

        self.assertIn(
            "metric_profile_incomplete_or_substituted", receipt["reason_codes"]
        )

    def test_synthetic_metric_below_declared_fixture_threshold_is_rejected(self):
        contract = build_career_resource_admission_contract()
        payload = copy.deepcopy(
            build_synthetic_fixture_matrix(contract)["envelopes"][1]
        )
        payload["validation_evidence"]["metric_observations"][
            "pairwise_order_accuracy"]["value"] = 0.10
        readdress_envelope(payload)

        receipt = evaluate_resource_admission(contract, payload)

        self.assertIn(
            "metric_failed:pairwise_order_accuracy", receipt["reason_codes"]
        )

    def test_information_grant_cannot_add_raw_observations(self):
        contract = build_career_resource_admission_contract()
        payload = copy.deepcopy(
            build_synthetic_fixture_matrix(contract)["envelopes"][0]
        )
        payload["resource_manifest"]["information_grant"].append(
            "new_raw_observations"
        )
        readdress_envelope(payload)

        receipt = evaluate_resource_admission(contract, payload)

        self.assertIn("information_grant_drift", receipt["reason_codes"])

    def test_evaluation_partition_access_is_rejected(self):
        contract = build_career_resource_admission_contract()
        payload = copy.deepcopy(
            build_synthetic_fixture_matrix(contract)["envelopes"][1]
        )
        payload["validation_evidence"]["evaluation_records_accessed"] = True
        readdress_envelope(payload)

        receipt = evaluate_resource_admission(contract, payload)

        self.assertIn("evaluation_partition_leak", receipt["reason_codes"])

    def test_malformed_nested_payload_rejects_instead_of_crashing(self):
        contract = build_career_resource_admission_contract()
        payload = copy.deepcopy(
            build_synthetic_fixture_matrix(contract)["envelopes"][0]
        )
        payload["resource_manifest"] = ["not", "an", "object"]
        readdress_envelope(payload)

        receipt = evaluate_resource_admission(contract, payload)

        self.assertFalse(receipt["accepted"])
        self.assertIn("resource_manifest_fields_drift", receipt["reason_codes"])

    def test_contract_content_address_rejects_unacknowledged_mutation(self):
        payload = build_career_resource_admission_contract().to_dict()
        payload["title"] = "mutated"

        with self.assertRaisesRegex(ContractViolation, "contract_id mismatch"):
            CareerResourceAdmissionContract(payload)

    def test_readdressed_contract_cannot_enable_real_admission(self):
        payload = build_career_resource_admission_contract().to_dict()
        payload["governance"]["real_resource_admission_authorized"] = True
        payload["contract_id"] = contract_id_for(payload)

        with self.assertRaisesRegex(ContractViolation, "governance"):
            CareerResourceAdmissionContract(payload)

    def test_M9_parity_anchor_and_real_hold_are_explicit(self):
        contract = build_career_resource_admission_contract().to_dict()

        self.assertEqual(contract["parity_anchor"]["m9_contract_id"],
                         M9_CONTRACT_ID)
        self.assertEqual(contract["parity_anchor"]["m9_parity_fingerprint"],
                         M9_PARITY_FINGERPRINT)
        self.assertEqual(contract["canonical_real_resource_status"], {
            "S": REAL_RESOURCE_HOLD,
            "M": REAL_RESOURCE_HOLD,
        })

    def test_all_receipts_are_content_addressed_and_offline(self):
        matrix = build_synthetic_fixture_matrix(
            build_career_resource_admission_contract()
        )

        for receipt in matrix["receipts"]:
            self.assertEqual(receipt["receipt_id"], receipt_id_for(receipt))
            self.assertTrue(all(
                value == 0 for value in receipt["external_access"].values()
            ))
        self.assertTrue(all(matrix["checks"].values()))
        self.assertEqual(
            matrix["verdict"], "PASS_ADMISSION_VALIDATOR_STRUCTURE_ONLY"
        )


if __name__ == "__main__":
    unittest.main()
