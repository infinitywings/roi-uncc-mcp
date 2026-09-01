from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from g7confirm.career_source_manifest_validator import (
    M12_CONTRACT_ID,
    NEGATIVE_VERDICT,
    POSITIVE_VERDICT,
    REQUIRED_EXTERNAL_ACCESS,
    SOURCE_MANIFEST_MATRIX_SCHEMA_VERSION,
    CareerSourceManifestMatrix,
    apply_synthetic_mutation,
    build_career_source_manifest_matrix,
    build_synthetic_envelope,
    envelope_id_for,
    evaluate_source_package,
    load_career_source_manifest_matrix,
    matrix_id_for,
)
from g7confirm.career_source_freeze_design import (
    M9_CANDIDATE_IDS,
    PARTITION_ROLES,
    REVIEW_STATUS,
)
from g7confirm.career_threshold_hold import THRESHOLD_STATUS
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = (
    PACKAGE_ROOT / "artifacts" / "career_source_manifest_matrix_m13.json"
)
SCHEMA_PATH = PACKAGE_ROOT / "career_source_manifest_matrix.schema.json"
EXPECTED_MATRIX_ID = (
    "m13matrix_4025c6e7342d20113eb56bfd0c75676f9160389db968456b88603f61"
    "156ae7a3"
)


def readdress_matrix(payload: dict) -> dict:
    payload["matrix_id"] = matrix_id_for(payload)
    return payload


class CareerSourceManifestValidatorTests(unittest.TestCase):
    def test_checked_in_matrix_matches_canonical_builder(self):
        built = build_career_source_manifest_matrix()
        stored = load_career_source_manifest_matrix(ARTIFACT_PATH)

        self.assertEqual(stored.to_dict(), built.to_dict())
        self.assertEqual(stored.matrix_id, EXPECTED_MATRIX_ID)

    def test_schema_is_parseable_and_names_matrix_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            SOURCE_MANIFEST_MATRIX_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])

    def test_two_positive_fixtures_pass_structure_only(self):
        receipts = build_career_source_manifest_matrix().to_dict()[
            "validation_receipts"
        ]
        positive = [receipt for receipt in receipts if receipt["accepted"]]

        self.assertEqual(len(positive), 2)
        self.assertEqual({item["factor"] for item in positive}, {"S", "M"})
        self.assertTrue(
            all(item["verdict"] == POSITIVE_VERDICT for item in positive)
        )
        self.assertTrue(all(item["reason_codes"] == [] for item in positive))

    def test_twelve_single_fault_fixtures_fail_with_exact_reason(self):
        payload = build_career_source_manifest_matrix().to_dict()
        cases = payload["fixture_cases"]
        receipts = payload["validation_receipts"]
        negative_pairs = [
            (case, receipt)
            for case, receipt in zip(cases, receipts)
            if not case["expected_accepted"]
        ]

        self.assertEqual(len(negative_pairs), 12)
        for case, receipt in negative_pairs:
            self.assertFalse(receipt["accepted"], case["fixture_id"])
            self.assertEqual(receipt["verdict"], NEGATIVE_VERDICT)
            self.assertEqual(
                receipt["reason_codes"], case["expected_reason_codes"]
            )
            self.assertEqual(len(receipt["reason_codes"]), 1)

    def test_positive_packages_fill_every_slot_with_synthetic_hash(self):
        for factor in ("S", "M"):
            envelope = build_synthetic_envelope(
                factor=factor, fixture_id=f"test_{factor}_positive"
            )
            addresses = envelope["source_package"]["content_addresses"]

            self.assertTrue(addresses)
            self.assertTrue(
                all(value.startswith("sha256_") and len(value) == 71
                    for value in addresses.values())
            )
            self.assertTrue(envelope["source_package"]["synthetic_fixture"])

    def test_positive_partition_manifest_uses_all_unique_roles(self):
        envelope = build_synthetic_envelope(
            factor="S", fixture_id="test_partition_roles"
        )
        assignments = envelope["partition_manifest"]["assignments"]

        self.assertEqual(set(assignments), set(PARTITION_ROLES))
        self.assertEqual(len(set(assignments.values())), len(PARTITION_ROLES))
        self.assertFalse(
            envelope["partition_manifest"][
                "outcomes_observed_before_assignment"
            ]
        )

    def test_positive_reviews_are_distinct_non_author_and_package_bound(self):
        envelope = build_synthetic_envelope(
            factor="M", fixture_id="test_review_independence"
        )
        reviews = envelope["review_receipts"]
        package_id = envelope["source_package"]["source_package_id"]

        self.assertEqual(len(reviews), 2)
        self.assertNotEqual(reviews[0]["reviewer_id"], reviews[1]["reviewer_id"])
        for review in reviews:
            self.assertNotEqual(review["reviewer_id"], review["author_id"])
            self.assertEqual(review["bound_source_package_id"], package_id)
            self.assertEqual(review["decision"], POSITIVE_VERDICT)
            self.assertEqual(review["real_review_status_after"], REVIEW_STATUS)

    def test_candidate_reordering_rejects_after_content_readdress(self):
        envelope = build_synthetic_envelope(
            factor="M", fixture_id="test_candidate_drift"
        )
        mutated = apply_synthetic_mutation(envelope, "candidate_drift")
        receipt = evaluate_source_package(mutated)

        self.assertEqual(
            mutated["source_package"]["derivation_contract"]
            ["ordered_candidate_ids"],
            list(reversed(M9_CANDIDATE_IDS)),
        )
        self.assertEqual(receipt["reason_codes"], ["M_candidate_library_drift"])

    def test_unacknowledged_envelope_mutation_breaks_content_address(self):
        envelope = build_synthetic_envelope(
            factor="S", fixture_id="test_content_address"
        )
        envelope["partition_manifest"]["assignments"][
            "S_source_derivation"
        ] = "changed_without_readdress"
        receipt = evaluate_source_package(envelope)

        self.assertIn("envelope_content_address_mismatch", receipt["reason_codes"])
        self.assertIn(
            "partition_manifest_content_address_mismatch",
            receipt["reason_codes"],
        )

    def test_real_envelope_cannot_pass_the_synthetic_validator(self):
        envelope = build_synthetic_envelope(
            factor="S", fixture_id="test_real_rejection"
        )
        envelope["synthetic_fixture"] = False
        envelope["envelope_id"] = envelope_id_for(envelope)
        receipt = evaluate_source_package(envelope)

        self.assertFalse(receipt["accepted"])
        self.assertEqual(
            receipt["reason_codes"], ["real_source_validation_not_authorized"]
        )

    def test_receipts_preserve_every_real_hold(self):
        receipts = build_career_source_manifest_matrix().to_dict()[
            "validation_receipts"
        ]

        for receipt in receipts:
            self.assertEqual(receipt["real_source_status_after"],
                             "UNBUILT_DESIGN_ONLY")
            self.assertEqual(receipt["real_partition_status_after"],
                             "UNASSIGNED_DESIGN_ONLY")
            self.assertEqual(receipt["real_review_status_after"], REVIEW_STATUS)
            self.assertEqual(
                receipt["scientific_threshold_status_after"], THRESHOLD_STATUS
            )
            self.assertTrue(receipt["real_resource_status_after"].startswith(
                "HOLD_"))
            self.assertEqual(receipt["evaluation_status_after"], "SEALED")

    def test_all_receipts_record_zero_external_access(self):
        receipts = build_career_source_manifest_matrix().to_dict()[
            "validation_receipts"
        ]

        self.assertTrue(
            all(item["external_access"] == REQUIRED_EXTERNAL_ACCESS
                for item in receipts)
        )

    def test_matrix_governance_cannot_authorize_real_generation(self):
        payload = build_career_source_manifest_matrix().to_dict()
        payload["governance"]["real_source_generation_authorized"] = True

        with self.assertRaisesRegex(ContractViolation, "governance"):
            CareerSourceManifestMatrix(readdress_matrix(payload))

    def test_matrix_content_address_rejects_unacknowledged_mutation(self):
        payload = build_career_source_manifest_matrix().to_dict()
        payload["next_gate"]["evaluation_access"] = True

        with self.assertRaisesRegex(ContractViolation, "matrix_id mismatch"):
            CareerSourceManifestMatrix(payload)

    def test_malformed_nested_values_reject_without_crashing(self):
        envelope = build_synthetic_envelope(
            factor="M", fixture_id="test_malformed_nested"
        )
        envelope["source_package"] = []
        envelope["envelope_id"] = envelope_id_for(envelope)
        receipt = evaluate_source_package(envelope)

        self.assertFalse(receipt["accepted"])
        self.assertIn("source_package_fields_drift", receipt["reason_codes"])

    def test_next_gate_remains_review_only_and_offline(self):
        payload = build_career_source_manifest_matrix().to_dict()
        next_gate = payload["next_gate"]

        self.assertEqual(
            next_gate["id"],
            "M14_independent_source_generation_prerequisite_review",
        )
        self.assertFalse(next_gate["real_source_generation_authorized"])
        self.assertFalse(next_gate["real_partition_assignment_authorized"])
        self.assertFalse(next_gate["model_or_embedding_call"])
        self.assertFalse(next_gate["simulator_or_detector_access"])
        self.assertFalse(next_gate["evaluation_access"])
        self.assertEqual(payload["source_lineage"]["m12_contract_id"],
                         M12_CONTRACT_ID)


if __name__ == "__main__":
    unittest.main()
