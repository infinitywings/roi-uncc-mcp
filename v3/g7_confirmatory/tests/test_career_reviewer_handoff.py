from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path

from g7confirm.career_review_receipts import (
    REQUIRED_ROLES,
    build_synthetic_review_receipt,
)
from g7confirm.career_reviewer_handoff import (
    HANDOFF_SCHEMA_VERSION,
    HANDOFF_STATUS,
    M14A_BASE_COMMIT,
    REQUIRED_GOVERNANCE,
    SUPPORT_SNAPSHOT,
    WORKSHEET_SCHEMA_VERSION,
    WORKSHEET_STATUS,
    CareerReviewerWorksheet,
    build_reviewer_handoff_contract,
    build_reviewer_worksheet,
    handoff_id_for,
    load_reviewer_handoff_contract,
    load_reviewer_worksheet,
    verify_checked_in_handoff,
    verify_handoff_snapshot,
    worksheet_id_for,
)
from g7confirm.cli import build_parser, main
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
HANDOFF_PATH = PACKAGE_ROOT / "artifacts/career_reviewer_handoff_m14b.json"
WORKSHEET_PATHS = (
    PACKAGE_ROOT / "artifacts/reviewer_handoff/data_lineage_worksheet_m14b.json",
    PACKAGE_ROOT / "artifacts/reviewer_handoff/domain_method_worksheet_m14b.json",
)
HANDOFF_SCHEMA_PATH = PACKAGE_ROOT / "career_reviewer_handoff.schema.json"
WORKSHEET_SCHEMA_PATH = PACKAGE_ROOT / "career_reviewer_worksheet.schema.json"
EXPECTED_HANDOFF_ID = (
    "m14bhandoff_b860b6a66def594f90aee3cd5dc675e3e0ec182d873a021f8284f1566cf7b6a3"
)


def readdress_worksheet(payload: dict) -> dict:
    payload["worksheet_id"] = worksheet_id_for(payload)
    return payload


def run_cli(argv: list[str]) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv)
    payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    return exit_code, payload, stderr.getvalue()


class CareerReviewerHandoffTests(unittest.TestCase):
    def test_checked_in_handoff_matches_canonical_builder(self):
        stored = load_reviewer_handoff_contract(HANDOFF_PATH)
        built = build_reviewer_handoff_contract()

        self.assertEqual(stored, built)
        self.assertEqual(stored["handoff_id"], EXPECTED_HANDOFF_ID)
        self.assertEqual(stored["handoff_id"], handoff_id_for(stored))
        self.assertEqual(stored["status"], HANDOFF_STATUS)

    def test_both_role_specific_worksheets_match_canonical_builders(self):
        stored = [load_reviewer_worksheet(path) for path in WORKSHEET_PATHS]

        self.assertEqual(
            [worksheet.to_dict()["reviewer_role"] for worksheet in stored],
            list(REQUIRED_ROLES),
        )
        self.assertEqual(
            [worksheet.to_dict() for worksheet in stored],
            [build_reviewer_worksheet(role).to_dict() for role in REQUIRED_ROLES],
        )
        self.assertNotEqual(stored[0].worksheet_id, stored[1].worksheet_id)

    def test_handoff_and_worksheet_schemas_parse(self):
        handoff_schema = json.loads(HANDOFF_SCHEMA_PATH.read_text())
        worksheet_schema = json.loads(WORKSHEET_SCHEMA_PATH.read_text())

        self.assertEqual(
            handoff_schema["properties"]["schema_version"]["const"],
            HANDOFF_SCHEMA_VERSION,
        )
        self.assertEqual(
            worksheet_schema["properties"]["schema_version"]["const"],
            WORKSHEET_SCHEMA_VERSION,
        )
        self.assertFalse(handoff_schema["additionalProperties"])
        self.assertFalse(worksheet_schema["additionalProperties"])

    def test_six_support_files_match_exact_committed_bytes(self):
        self.assertEqual(len(SUPPORT_SNAPSHOT), 6)
        self.assertEqual(verify_handoff_snapshot(REPO_ROOT), [])
        self.assertEqual(verify_checked_in_handoff(REPO_ROOT), [])
        self.assertEqual(
            build_reviewer_handoff_contract()["source_lineage"][
                "m14a_base_commit"
            ],
            M14A_BASE_COMMIT,
        )

    def test_every_worksheet_decision_and_identity_field_is_empty(self):
        for role in REQUIRED_ROLES:
            worksheet = build_reviewer_worksheet(role).to_dict()
            self.assertEqual(worksheet["status"], WORKSHEET_STATUS)
            self.assertTrue(
                all(value is None for value in worksheet["reviewer_fields"].values())
            )
            self.assertTrue(
                all(item["answer"] is None for item in worksheet["question_fields"])
            )
            self.assertTrue(
                all(
                    item["finding_references"] == []
                    for item in worksheet["question_fields"]
                )
            )
            self.assertTrue(
                all(value is None for value in worksheet["review_fields"].values())
            )

    def test_worksheet_cannot_be_readdressed_after_identity_population(self):
        payload = build_reviewer_worksheet(REQUIRED_ROLES[0]).to_dict()
        payload["reviewer_fields"]["reviewer_id"] = "packet_preparer"

        with self.assertRaisesRegex(ContractViolation, "content address"):
            CareerReviewerWorksheet(payload)
        with self.assertRaisesRegex(ContractViolation, "were populated"):
            CareerReviewerWorksheet(readdress_worksheet(payload))

    def test_worksheet_cannot_be_readdressed_after_disposition_population(self):
        payload = build_reviewer_worksheet(REQUIRED_ROLES[1]).to_dict()
        payload["review_fields"]["disposition"] = "accept_exact_packet"

        with self.assertRaisesRegex(ContractViolation, "were populated"):
            CareerReviewerWorksheet(readdress_worksheet(payload))

    def test_worksheet_cannot_be_readdressed_after_answer_population(self):
        payload = build_reviewer_worksheet(REQUIRED_ROLES[0]).to_dict()
        payload["question_fields"][0]["answer"] = "accept"

        with self.assertRaisesRegex(ContractViolation, "questions"):
            CareerReviewerWorksheet(readdress_worksheet(payload))

    def test_governance_preserves_all_operational_holds(self):
        self.assertTrue(REQUIRED_GOVERNANCE["reviewer_handoff_only"])
        self.assertTrue(
            all(
                value is False
                for key, value in REQUIRED_GOVERNANCE.items()
                if key != "reviewer_handoff_only"
            )
        )
        contract = build_reviewer_handoff_contract()
        self.assertFalse(contract["next_gate"]["source_generation_authorized"])
        self.assertFalse(contract["next_gate"]["evaluation_access"])
        self.assertFalse(contract["next_gate"]["campaign_authorized"])

    def test_preflight_cli_verifies_handoff_without_writes(self):
        exit_code, payload, stderr = run_cli([
            "career-review-preflight",
            "--repo-root",
            str(REPO_ROOT),
        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["status"], HANDOFF_STATUS)
        self.assertEqual(payload["issues"], [])
        self.assertEqual(payload["files_created_or_modified"], 0)
        self.assertEqual(payload["RKA_writes"], 0)
        self.assertTrue(all(not value for value in payload["authorization"].values()))

    def test_single_receipt_cli_validates_but_does_not_approve(self):
        receipt = build_synthetic_review_receipt(
            REQUIRED_ROLES[0], "synthetic_cli_lineage"
        ).to_dict()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            exit_code, payload, stderr = run_cli([
                "career-review-receipt", "--receipt", str(path)
            ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            payload["status"], "VALID_RECEIPT_DECLARATION_NOT_APPROVED"
        )
        self.assertEqual(payload["checkpoint_status"],
                         "OPEN_REQUIRES_EXTERNAL_RESOLUTION")
        self.assertTrue(all(not value for value in payload["authorization"].values()))

    def test_two_synthetic_receipts_cli_reaches_no_authority_state(self):
        receipts = [
            build_synthetic_review_receipt(
                REQUIRED_ROLES[0], "synthetic_cli_lineage"
            ).to_dict(),
            build_synthetic_review_receipt(
                REQUIRED_ROLES[1], "synthetic_cli_domain"
            ).to_dict(),
        ]
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index, receipt in enumerate(receipts):
                path = Path(directory) / f"receipt_{index}.json"
                path.write_text(json.dumps(receipt), encoding="utf-8")
                paths.append(path)
            exit_code, payload, stderr = run_cli([
                "career-review-bundle",
                "--receipt",
                str(paths[0]),
                "--receipt",
                str(paths[1]),
            ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            payload["status"], "SYNTHETIC_MECHANICS_PASS_NO_AUTHORITY"
        )
        self.assertEqual(payload["files_created_or_modified"], 0)
        self.assertEqual(payload["RKA_writes"], 0)

    def test_incomplete_bundle_cli_fails_closed(self):
        receipt = build_synthetic_review_receipt(
            REQUIRED_ROLES[0], "synthetic_cli_lineage"
        ).to_dict()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            exit_code, payload, _ = run_cli([
                "career-review-bundle", "--receipt", str(path)
            ])

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "INCOMPLETE_NOT_APPROVED")

    def test_cli_exposes_no_review_create_or_finalize_command(self):
        choices = build_parser()._subparsers._group_actions[0].choices

        self.assertIn("career-review-preflight", choices)
        self.assertIn("career-review-receipt", choices)
        self.assertIn("career-review-bundle", choices)
        self.assertNotIn("career-review-create", choices)
        self.assertNotIn("career-review-finalize", choices)

    def test_contract_mutation_breaks_content_address(self):
        contract = build_reviewer_handoff_contract()
        mutated = deepcopy(contract)
        mutated["status"] = "APPROVED"

        self.assertNotEqual(mutated["handoff_id"], handoff_id_for(mutated))


if __name__ == "__main__":
    unittest.main()
