from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from g7confirm.career_two_tier_gate import (
    DEFERRED_EXTERNAL_CHECKPOINT_ID,
    FROZEN_ASSETS,
    HISTORICAL_REVIEW_ASSETS,
    OFFLINE_PERMISSIONS,
    SEALED_ACTIONS,
    TWO_TIER_GATE_SCHEMA_VERSION,
    TWO_TIER_GATE_STATUS,
    CareerTwoTierGate,
    build_career_two_tier_gate,
    gate_id_for,
    load_career_two_tier_gate,
    verify_checked_in_two_tier_gate,
    verify_preserved_assets,
)
from g7confirm.cli import build_parser, main
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
ARTIFACT_PATH = PACKAGE_ROOT / "artifacts/career_two_tier_gate_m15.json"
SCHEMA_PATH = PACKAGE_ROOT / "career_two_tier_gate.schema.json"
EXPECTED_GATE_ID = (
    "m15twotier_af8cf66768ddeb85f535be40d76bf327b826c088a337d42cd7b15df5cb037d65"
)


def readdress(payload: dict) -> dict:
    payload["gate_id"] = gate_id_for(payload)
    return payload


def run_cli(argv: list[str]) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv)
    payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    return exit_code, payload, stderr.getvalue()


class CareerTwoTierGateTests(unittest.TestCase):
    def test_checked_in_artifact_matches_canonical_builder(self):
        stored = load_career_two_tier_gate(ARTIFACT_PATH)
        built = build_career_two_tier_gate()

        self.assertEqual(stored.to_dict(), built.to_dict())
        self.assertEqual(stored.gate_id, EXPECTED_GATE_ID)
        self.assertEqual(stored.gate_id, gate_id_for(stored.to_dict()))
        self.assertEqual(stored.to_dict()["status"], TWO_TIER_GATE_STATUS)

    def test_schema_is_closed_and_names_contract_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            TWO_TIER_GATE_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(
            schema["properties"]["sealed_actions"]["additionalProperties"]
        )

    def test_all_frozen_and_historical_review_assets_match_exact_bytes(self):
        self.assertEqual(len(FROZEN_ASSETS), 2)
        self.assertEqual(len(HISTORICAL_REVIEW_ASSETS), 13)
        self.assertEqual(verify_preserved_assets(REPO_ROOT), [])
        self.assertEqual(verify_checked_in_two_tier_gate(REPO_ROOT), [])

    def test_only_narrow_offline_permissions_are_enabled(self):
        gate = build_career_two_tier_gate().to_dict()

        self.assertEqual(gate["offline_permissions"], OFFLINE_PERMISSIONS)
        self.assertTrue(gate["offline_permissions"]["implementation_and_unit_testing"])
        self.assertTrue(gate["offline_permissions"]["internal_advisory_review"])
        self.assertTrue(
            gate["offline_permissions"]
            ["existing_embedding_service_on_synthetic_or_non_evaluation_inputs"]
        )
        self.assertFalse(
            gate["offline_permissions"]
            ["start_or_restart_model_or_embedding_service"]
        )

    def test_every_substantive_experiment_action_remains_sealed(self):
        sealed = build_career_two_tier_gate().to_dict()["sealed_actions"]

        self.assertEqual(sealed, SEALED_ACTIONS)
        self.assertTrue(all(value is False for value in sealed.values()))

    def test_external_review_is_deferred_not_completed_or_waived(self):
        gate = build_career_two_tier_gate().to_dict()
        deferred = gate["deferred_external_gate"]

        self.assertEqual(deferred["checkpoint_id"], DEFERRED_EXTERNAL_CHECKPOINT_ID)
        self.assertFalse(deferred["external_review_complete"])
        self.assertEqual(deferred["accepted_receipt_count"], 0)
        self.assertEqual(deferred["required_receipt_count"], 2)
        self.assertTrue(deferred["required_before_every_sealed_action"])
        self.assertIn("no_external_review_completed_or_waived", gate["limitations"])

    def test_internal_advisor_cannot_claim_external_authority(self):
        boundary = build_career_two_tier_gate().to_dict()[
            "internal_advisory_boundary"
        ]

        self.assertTrue(boundary["advisory_only"])
        self.assertTrue(boundary["may_not_claim_external_independence"])
        self.assertTrue(boundary["may_not_issue_or_finalize_external_receipts"])
        self.assertTrue(boundary["may_not_resolve_the_deferred_external_gate"])
        self.assertTrue(boundary["advisory_findings_are_not_scientific_approval"])

    def test_unaddressed_permission_mutation_breaks_content_address(self):
        payload = build_career_two_tier_gate().to_dict()
        payload["sealed_actions"]["detector_calibration"] = True

        with self.assertRaisesRegex(ContractViolation, "content address"):
            CareerTwoTierGate(payload)

    def test_readdressed_detector_calibration_permission_is_rejected(self):
        payload = build_career_two_tier_gate().to_dict()
        payload["sealed_actions"]["detector_calibration"] = True

        with self.assertRaisesRegex(ContractViolation, "sealed action"):
            CareerTwoTierGate(readdress(payload))

    def test_readdressed_service_restart_permission_is_rejected(self):
        payload = build_career_two_tier_gate().to_dict()
        payload["offline_permissions"][
            "start_or_restart_model_or_embedding_service"
        ] = True

        with self.assertRaisesRegex(ContractViolation, "offline permission"):
            CareerTwoTierGate(readdress(payload))

    def test_readdressed_external_completion_claim_is_rejected(self):
        payload = build_career_two_tier_gate().to_dict()
        payload["deferred_external_gate"]["external_review_complete"] = True
        payload["deferred_external_gate"]["accepted_receipt_count"] = 2

        with self.assertRaisesRegex(ContractViolation, "deferred external"):
            CareerTwoTierGate(readdress(payload))

    def test_readdressed_local_receipt_authority_is_rejected(self):
        payload = build_career_two_tier_gate().to_dict()
        payload["sealed_actions"][
            "external_receipt_issuance_by_local_advisor"
        ] = True

        with self.assertRaisesRegex(ContractViolation, "sealed action"):
            CareerTwoTierGate(readdress(payload))

    def test_readdressed_historical_review_hash_mutation_is_rejected(self):
        payload = copy.deepcopy(build_career_two_tier_gate().to_dict())
        payload["historical_review_assets"][0]["sha256"] = "0" * 64

        with self.assertRaisesRegex(ContractViolation, "historical review"):
            CareerTwoTierGate(readdress(payload))

    def test_development_gate_cli_is_read_only_and_reports_both_tiers(self):
        exit_code, payload, stderr = run_cli([
            "career-development-gate",
            "--repo-root",
            str(REPO_ROOT),
        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["status"], TWO_TIER_GATE_STATUS)
        self.assertEqual(payload["issues"], [])
        self.assertFalse(payload["external_review_complete"])
        self.assertTrue(payload["offline_permissions"]["implementation_and_unit_testing"])
        self.assertTrue(all(value is False for value in payload["sealed_actions"].values()))
        self.assertEqual(payload["files_created_or_modified"], 0)
        self.assertEqual(payload["RKA_writes"], 0)

    def test_cli_exposes_development_preflight_but_no_unseal_command(self):
        choices = build_parser()._subparsers._group_actions[0].choices

        self.assertIn("career-development-gate", choices)
        self.assertNotIn("career-development-unseal", choices)
        self.assertNotIn("career-external-review-waive", choices)


if __name__ == "__main__":
    unittest.main()
