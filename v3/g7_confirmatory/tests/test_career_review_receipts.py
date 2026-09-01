from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from g7confirm.career_review_receipts import (
    CHANGES_REQUIRED,
    INCOMPLETE,
    INVALID,
    M14_PACKET_FILE_BYTES,
    M14_PACKET_FILE_SHA256,
    M14_REVIEW_SCOPE_SHA256,
    M14_SNAPSHOT_MANIFEST_SHA256,
    READY_FOR_GOVERNANCE,
    RECEIPT_SCHEMA_VERSION,
    REJECTED,
    REQUIRED_GOVERNANCE,
    REQUIRED_ROLES,
    SYNTHETIC_PASS,
    CareerReviewReceipt,
    build_review_receipt_intake_contract,
    build_synthetic_review_receipt,
    evaluate_review_receipts,
    intake_id_for,
    load_review_receipt_intake_contract,
    receipt_id_for,
)
from g7confirm.career_source_review_packet import (
    build_career_source_review_packet,
)
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = (
    PACKAGE_ROOT / "artifacts" / "career_review_receipt_intake_m14a.json"
)
PACKET_PATH = PACKAGE_ROOT / "artifacts" / "career_source_review_packet_m14.json"
RECEIPT_SCHEMA_PATH = PACKAGE_ROOT / "career_review_receipt.schema.json"
INTAKE_SCHEMA_PATH = PACKAGE_ROOT / "career_review_receipt_intake.schema.json"
EXPECTED_CONTRACT_ID = (
    "m14aintake_a4f22ef8dd509e486adc32cdd7623c3682fc2148ff8a48831f606fc256553ba4"
)


def readdress(payload: dict) -> dict:
    payload["receipt_id"] = receipt_id_for(payload)
    return payload


def pair(
    first_disposition: str = "accept_exact_packet",
    second_disposition: str = "accept_exact_packet",
) -> list[dict]:
    return [
        build_synthetic_review_receipt(
            REQUIRED_ROLES[0],
            "synthetic_lineage_reviewer",
            disposition=first_disposition,
        ).to_dict(),
        build_synthetic_review_receipt(
            REQUIRED_ROLES[1],
            "synthetic_domain_reviewer",
            disposition=second_disposition,
        ).to_dict(),
    ]


def external_shape(payload: dict, reviewer_id: str) -> dict:
    converted = deepcopy(payload)
    converted["artifact_class"] = "external_review_receipt"
    converted["reviewer"]["reviewer_id"] = reviewer_id
    converted["reviewer"]["identity_verification_reference"] = (
        f"institutional-review-registry:{reviewer_id}"
    )
    converted["review"]["issued_at_utc"] = "2026-09-01T12:00:00Z"
    return readdress(converted)


class CareerReviewReceiptTests(unittest.TestCase):
    def test_checked_in_intake_contract_matches_canonical_builder(self):
        stored = load_review_receipt_intake_contract(ARTIFACT_PATH)
        built = build_review_receipt_intake_contract()

        self.assertEqual(stored, built)
        self.assertEqual(stored["contract_id"], EXPECTED_CONTRACT_ID)
        self.assertEqual(stored["contract_id"], intake_id_for(stored))
        self.assertEqual(
            stored["status"], "OFFLINE_INTAKE_READY_M14_CHECKPOINT_OPEN"
        )

    def test_both_schemas_parse_and_name_exact_versions(self):
        receipt_schema = json.loads(RECEIPT_SCHEMA_PATH.read_text())
        intake_schema = json.loads(INTAKE_SCHEMA_PATH.read_text())

        self.assertEqual(
            receipt_schema["properties"]["schema_version"]["const"],
            RECEIPT_SCHEMA_VERSION,
        )
        self.assertEqual(
            intake_schema["properties"]["milestone"]["const"], "M14A"
        )
        self.assertFalse(receipt_schema["additionalProperties"])
        self.assertFalse(intake_schema["additionalProperties"])

    def test_packet_file_and_semantic_digests_match_current_M14_bytes(self):
        packet_bytes = PACKET_PATH.read_bytes()
        packet = build_career_source_review_packet().to_dict()
        canonical = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

        self.assertEqual(len(packet_bytes), M14_PACKET_FILE_BYTES)
        self.assertEqual(
            hashlib.sha256(packet_bytes).hexdigest(), M14_PACKET_FILE_SHA256
        )
        self.assertEqual(
            hashlib.sha256(canonical(packet["exact_review_snapshot"])).hexdigest(),
            M14_SNAPSHOT_MANIFEST_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(canonical(packet["review_scope"])).hexdigest(),
            M14_REVIEW_SCOPE_SHA256,
        )

    def test_two_synthetic_acceptances_pass_mechanics_without_authority(self):
        result = evaluate_review_receipts(pair()).to_dict()

        self.assertEqual(result["status"], SYNTHETIC_PASS)
        self.assertEqual(
            result["checkpoint_status"], "OPEN_REQUIRES_EXTERNAL_RESOLUTION"
        )
        self.assertTrue(all(not value for value in result["authorization"].values()))

    def test_zero_and_one_receipt_are_incomplete(self):
        zero = evaluate_review_receipts([])
        one = evaluate_review_receipts(pair()[:1])

        self.assertEqual(zero.status, INCOMPLETE)
        self.assertEqual(one.status, INCOMPLETE)
        self.assertEqual(one.failure_reasons, ("exactly_two_receipts_required",))

    def test_duplicate_reviewer_identity_is_invalid(self):
        receipts = pair()
        receipts[1]["reviewer"]["reviewer_id"] = (
            receipts[0]["reviewer"]["reviewer_id"]
        )
        receipts[1]["reviewer"]["identity_verification_reference"] = (
            receipts[0]["reviewer"]["identity_verification_reference"]
        )
        readdress(receipts[1])

        result = evaluate_review_receipts(receipts)

        self.assertEqual(result.status, INVALID)
        self.assertIn("reviewer_identities_not_distinct", result.failure_reasons)

    def test_duplicate_role_is_invalid(self):
        receipts = pair()
        receipts[1]["reviewer"]["reviewer_role"] = REQUIRED_ROLES[0]
        readdress(receipts[1])

        result = evaluate_review_receipts(receipts)

        self.assertEqual(result.status, INVALID)
        self.assertIn("required_role_coverage_failed", result.failure_reasons)

    def test_wrong_packet_binding_is_invalid_even_when_readdressed(self):
        receipts = pair()
        receipts[0]["bound_packet"]["packet_file_sha256"] = "0" * 64
        readdress(receipts[0])

        result = evaluate_review_receipts(receipts)

        self.assertEqual(result.status, INVALID)
        self.assertIn(
            "not bound to exact M14 bytes", " ".join(result.failure_reasons)
        )

    def test_comments_hash_mismatch_is_invalid_even_when_readdressed(self):
        receipts = pair()
        receipts[0]["review"]["comments"] = "Changed after hashing."
        readdress(receipts[0])

        result = evaluate_review_receipts(receipts)

        self.assertEqual(result.status, INVALID)
        self.assertIn("comments SHA-256 mismatch", " ".join(result.failure_reasons))

    def test_packet_preparer_declaration_is_rejected(self):
        receipt = pair()[0]
        receipt["reviewer"]["is_packet_preparer"] = True
        readdress(receipt)

        with self.assertRaisesRegex(ContractViolation, "packet preparer"):
            CareerReviewReceipt(receipt)

    def test_missing_review_question_is_rejected(self):
        receipt = pair()[0]
        receipt["review"]["answered_question_sha256s"].pop()
        readdress(receipt)

        with self.assertRaisesRegex(ContractViolation, "all six"):
            CareerReviewReceipt(receipt)

    def test_request_changes_and_reject_never_open_the_gate(self):
        changes = evaluate_review_receipts(pair(second_disposition="request_changes"))
        reject = evaluate_review_receipts(pair(first_disposition="reject"))

        self.assertEqual(changes.status, CHANGES_REQUIRED)
        self.assertEqual(reject.status, REJECTED)
        self.assertFalse(changes.to_dict()["authorization"]["source_generation"])
        self.assertFalse(reject.to_dict()["authorization"]["source_generation"])

    def test_mixed_synthetic_and_external_shapes_are_invalid(self):
        receipts = pair()
        receipts[1] = external_shape(receipts[1], "external_domain_reviewer")

        result = evaluate_review_receipts(receipts)

        self.assertEqual(result.status, INVALID)
        self.assertIn(
            "mixed_external_and_synthetic_receipts", result.failure_reasons
        )

    def test_two_external_shapes_only_reach_not_approved_ready_state(self):
        receipts = pair()
        receipts[0] = external_shape(receipts[0], "external_lineage_reviewer")
        receipts[1] = external_shape(receipts[1], "external_domain_reviewer")

        result = evaluate_review_receipts(receipts).to_dict()

        self.assertEqual(result["status"], READY_FOR_GOVERNANCE)
        self.assertTrue(result["status"].endswith("NOT_APPROVED"))
        self.assertEqual(
            result["checkpoint_status"], "OPEN_REQUIRES_EXTERNAL_RESOLUTION"
        )
        self.assertTrue(all(not value for value in result["authorization"].values()))

    def test_content_address_mismatch_is_rejected(self):
        receipt = pair()[0]
        receipt["review"]["comments"] = "Mutated without readdressing."

        with self.assertRaisesRegex(ContractViolation, "content address"):
            CareerReviewReceipt(receipt)

    def test_conformance_matrix_has_sixteen_unique_fixture_only_cases(self):
        matrix = build_review_receipt_intake_contract()[
            "canonical_conformance_matrix"
        ]

        self.assertEqual(len(matrix), 16)
        self.assertEqual(len({case["case_id"] for case in matrix}), 16)
        self.assertTrue(all(case["fixture_only"] for case in matrix))
        self.assertIn(
            READY_FOR_GOVERNANCE,
            {case["expected_status"] for case in matrix},
        )

    def test_governance_preserves_every_operational_hold(self):
        contract = build_review_receipt_intake_contract()

        self.assertTrue(REQUIRED_GOVERNANCE["receipt_intake_only"])
        self.assertTrue(
            all(
                value is False
                for key, value in REQUIRED_GOVERNANCE.items()
                if key != "receipt_intake_only"
            )
        )
        self.assertFalse(contract["next_gate"]["source_generation_authorized"])
        self.assertFalse(contract["next_gate"]["evaluation_access"])
        self.assertFalse(contract["next_gate"]["campaign_authorized"])


if __name__ == "__main__":
    unittest.main()
