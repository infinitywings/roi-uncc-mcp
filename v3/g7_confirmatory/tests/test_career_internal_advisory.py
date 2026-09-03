from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from g7confirm.career_internal_advisory import (
    EXPECTED_REVIEW_SHA256,
    INPUT_MANIFEST,
    INTERNAL_ADVISORY_SCHEMA_VERSION,
    INTERNAL_ADVISORY_STATUS,
    CareerInternalAdvisory,
    advisory_id_for,
    load_career_internal_advisory,
    review_sha256_for,
    verify_advisory_inputs,
    verify_checked_in_internal_advisory,
)
from g7confirm.career_two_tier_gate import SEALED_ACTIONS
from g7confirm.cli import build_parser, main
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
ARTIFACT_PATH = PACKAGE_ROOT / "artifacts/career_internal_advisory_m16.json"
SCHEMA_PATH = PACKAGE_ROOT / "career_internal_advisory.schema.json"
EXPECTED_ADVISORY_ID = (
    "m16advisory_97522999d4087e7533495df9dac996815a4a49cb33874acf93b1508caf651b4a"
)


def readdress(payload: dict) -> dict:
    payload["advisory_id"] = advisory_id_for(payload)
    return payload


def run_cli(argv: list[str]) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv)
    payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    return exit_code, payload, stderr.getvalue()


class CareerInternalAdvisoryTests(unittest.TestCase):
    def test_checked_in_advisory_is_content_addressed_and_valid(self):
        advisory = load_career_internal_advisory(ARTIFACT_PATH)

        self.assertEqual(advisory.advisory_id, EXPECTED_ADVISORY_ID)
        self.assertEqual(advisory.advisory_id, advisory_id_for(advisory.to_dict()))
        self.assertEqual(advisory.to_dict()["status"], INTERNAL_ADVISORY_STATUS)

    def test_schema_is_closed_and_names_contract_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            INTERNAL_ADVISORY_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["governance"]["additionalProperties"])

    def test_all_thirteen_design_inputs_and_m15_gate_match_exact_bytes(self):
        self.assertEqual(len(INPUT_MANIFEST), 13)
        self.assertEqual(verify_advisory_inputs(REPO_ROOT), [])
        self.assertEqual(verify_checked_in_internal_advisory(REPO_ROOT), [])

    def test_accepted_model_output_is_digest_bound(self):
        payload = load_career_internal_advisory(ARTIFACT_PATH).to_dict()

        self.assertEqual(payload["review_sha256"], EXPECTED_REVIEW_SHA256)
        self.assertEqual(payload["review_sha256"], review_sha256_for(payload["review"]))

    def test_transport_preserves_two_failures_and_one_accepted_completion(self):
        transport = load_career_internal_advisory(ARTIFACT_PATH).to_dict()[
            "transport"
        ]

        self.assertEqual(transport["model_record"]["id"], "qwen3.6-35b-a3b")
        self.assertEqual(transport["model_completions_attempted"], 3)
        self.assertEqual(transport["accepted_completions"], 1)
        self.assertEqual(
            [item["accepted"] for item in transport["attempts"]],
            [False, False, True],
        )

    def test_transport_access_boundary_is_explicit(self):
        transport = load_career_internal_advisory(ARTIFACT_PATH).to_dict()[
            "transport"
        ]

        self.assertFalse(transport["embedding_service_used"])
        self.assertFalse(transport["model_or_embedding_service_started_or_restarted"])
        self.assertFalse(transport["simulator_detector_or_actuator_accessed"])
        self.assertFalse(transport["evaluation_records_accessed"])

    def test_brain_rejects_threshold_setting_recommendation(self):
        adjudication = load_career_internal_advisory(ARTIFACT_PATH).to_dict()[
            "brain_adjudication"
        ]

        disposition = adjudication["F50"]["disposition"]
        self.assertEqual(disposition, "REJECT_GOVERNANCE_CONFLICT")
        self.assertIn("threshold", adjudication["F50"]["reason"])

    def test_brain_corrects_stale_model_access_claim(self):
        F60 = load_career_internal_advisory(ARTIFACT_PATH).to_dict()[
            "brain_adjudication"
        ]["F60"]

        self.assertEqual(F60["disposition"], "ACCEPT_WITH_CORRECTION")
        self.assertIn("local model", F60["reason"])
        self.assertFalse(F60["may_change_sealed_actions"])

    def test_every_adjudication_preserves_sealed_actions(self):
        adjudication = load_career_internal_advisory(ARTIFACT_PATH).to_dict()[
            "brain_adjudication"
        ]

        self.assertEqual(set(adjudication), {"F10", "F20", "F30", "F40", "F50", "F60", "F70"})
        self.assertTrue(
            all(item["may_change_sealed_actions"] is False
                for item in adjudication.values())
        )

    def test_all_M15_sealed_actions_remain_false(self):
        governance = load_career_internal_advisory(ARTIFACT_PATH).to_dict()[
            "governance"
        ]

        self.assertTrue(all(governance[key] is False for key in SEALED_ACTIONS))
        self.assertFalse(governance["external_review_completed"])
        self.assertFalse(governance["scientific_approval_granted"])

    def test_unaddressed_review_mutation_breaks_content_address(self):
        payload = load_career_internal_advisory(ARTIFACT_PATH).to_dict()
        payload["review"]["executive_assessment"] += " Mutated."

        with self.assertRaisesRegex(ContractViolation, "content address"):
            CareerInternalAdvisory(payload)

    def test_readdressed_review_mutation_breaks_frozen_review_digest(self):
        payload = load_career_internal_advisory(ARTIFACT_PATH).to_dict()
        payload["review"]["executive_assessment"] += " Mutated."
        payload["review_sha256"] = review_sha256_for(payload["review"])

        with self.assertRaisesRegex(ContractViolation, "accepted review bytes"):
            CareerInternalAdvisory(readdress(payload))

    def test_readdressed_governance_mutation_is_rejected(self):
        payload = load_career_internal_advisory(ARTIFACT_PATH).to_dict()
        payload["governance"]["detector_calibration"] = True

        with self.assertRaisesRegex(ContractViolation, "governance"):
            CareerInternalAdvisory(readdress(payload))

    def test_readdressed_adjudication_mutation_is_rejected(self):
        payload = load_career_internal_advisory(ARTIFACT_PATH).to_dict()
        payload["brain_adjudication"]["F50"]["disposition"] = (
            "ACCEPT_FOR_OFFLINE_DESIGN"
        )

        with self.assertRaisesRegex(ContractViolation, "Brain adjudication"):
            CareerInternalAdvisory(readdress(payload))

    def test_advisory_preflight_cli_is_read_only_and_fail_closed(self):
        exit_code, payload, stderr = run_cli([
            "career-advisory-preflight",
            "--repo-root",
            str(REPO_ROOT),
        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["status"], INTERNAL_ADVISORY_STATUS)
        self.assertEqual(payload["issues"], [])
        self.assertFalse(payload["external_review_complete"])
        self.assertTrue(all(value is False for value in payload["sealed_actions"].values()))
        self.assertEqual(payload["files_created_or_modified"], 0)
        self.assertEqual(payload["RKA_writes"], 0)

    def test_cli_exposes_no_advisory_approval_or_unseal_command(self):
        choices = build_parser()._subparsers._group_actions[0].choices

        self.assertIn("career-advisory-preflight", choices)
        self.assertNotIn("career-advisory-approve", choices)
        self.assertNotIn("career-advisory-unseal", choices)


if __name__ == "__main__":
    unittest.main()
