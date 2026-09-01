from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from g7confirm.career_threshold_hold import (
    BASELINE_TRACE_SHA256,
    EXPLORATORY_ONLY,
    L5B_TRACE_SHA256,
    M11_VERDICT,
    PROBE_TRACE_HASHES,
    SENSITIVITY_SHA256,
    THRESHOLD_HOLD_SCHEMA_VERSION,
    THRESHOLD_STATUS,
    CareerThresholdHold,
    build_career_threshold_hold,
    contract_id_for,
    load_career_threshold_hold,
)
from g7confirm.orchestration_contract import ContractViolation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PACKAGE_ROOT / "artifacts" / "career_threshold_hold_m11.json"
SCHEMA_PATH = PACKAGE_ROOT / "career_threshold_hold.schema.json"
EXPECTED_CONTRACT_ID = (
    "careerthresholdhold_4ff524e10e76cc36a68aec92ac6fcddda99802cf0699e419f930ad1f03588468"
)


def readdress(payload: dict) -> dict:
    payload["contract_id"] = contract_id_for(payload)
    return payload


class CareerThresholdHoldTests(unittest.TestCase):
    def test_checked_in_artifact_matches_canonical_builder(self):
        built = build_career_threshold_hold()
        stored = load_career_threshold_hold(ARTIFACT_PATH)

        self.assertEqual(stored.to_dict(), built.to_dict())
        self.assertEqual(stored.contract_id, EXPECTED_CONTRACT_ID)
        self.assertEqual(stored.to_dict()["verdict"], M11_VERDICT)

    def test_schema_is_parseable_and_names_contract_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"],
                         "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema_version"]["const"],
                         THRESHOLD_HOLD_SCHEMA_VERSION)
        self.assertFalse(schema["additionalProperties"])

    def test_every_scientific_threshold_is_null_and_unset(self):
        payload = build_career_threshold_hold().to_dict()

        for factor in ("S", "M"):
            for metric in payload["threshold_preregistration"][factor][
                    "metrics"].values():
                self.assertIsNone(metric["scientific_threshold"])
                self.assertEqual(metric["threshold_status"], THRESHOLD_STATUS)

    def test_readdressed_non_null_threshold_is_rejected(self):
        payload = build_career_threshold_hold().to_dict()
        metric = payload["threshold_preregistration"]["S"]["metrics"][
            "normalized_response_error"
        ]
        metric["scientific_threshold"] = 0.20

        with self.assertRaisesRegex(ContractViolation, "threshold was invented"):
            CareerThresholdHold(readdress(payload))

    def test_S_source_is_preserved_as_exploratory_only(self):
        audit = build_career_threshold_hold().to_dict()[
            "candidate_source_audit"]["S"]

        self.assertEqual(audit["candidate_status"], EXPLORATORY_ONLY)
        self.assertEqual(audit["artifact"]["sha256"], SENSITIVITY_SHA256)
        self.assertEqual(
            audit["observed_lineage"]["unlisted_baseline_sha256"],
            BASELINE_TRACE_SHA256,
        )
        self.assertEqual(
            audit["observed_lineage"]["probe_trace_hashes"],
            PROBE_TRACE_HASHES,
        )
        self.assertFalse(
            audit["observed_lineage"]["probe_paths_named_in_source_runs"]
        )

    def test_M_trace_is_treatment_informed_and_not_M9_ranking(self):
        audit = build_career_threshold_hold().to_dict()[
            "candidate_source_audit"]["M"]

        self.assertEqual(audit["candidate_status"], EXPLORATORY_ONLY)
        self.assertFalse(audit["eligible_candidate_found_in_scope"])
        self.assertEqual(audit["exploratory_trace"]["sha256"], L5B_TRACE_SHA256)
        self.assertTrue(
            audit["exploratory_trace"]
            ["contains_detector_informed_treatment_outcomes"]
        )
        self.assertFalse(
            audit["exploratory_trace"]["ranks_exact_M9_candidate_library"]
        )

    def test_source_absence_claim_is_bounded(self):
        scope = build_career_threshold_hold().to_dict()["audit_scope"]

        self.assertEqual(scope["absence_claim"],
                         "bounded_to_declared_scan_scope")
        self.assertFalse(scope["writes_performed"])
        self.assertIn("RKA_targeted_retrieval", scope["methods"])

    def test_real_resources_thresholds_evaluation_and_campaign_remain_held(self):
        status = build_career_threshold_hold().to_dict()["canonical_status"]

        self.assertTrue(status["S_real_resource"].startswith("HOLD_"))
        self.assertTrue(status["M_real_resource"].startswith("HOLD_"))
        self.assertEqual(status["S_scientific_threshold"], THRESHOLD_STATUS)
        self.assertEqual(status["M_scientific_threshold"], THRESHOLD_STATUS)
        self.assertEqual(status["evaluation"], "SEALED")
        self.assertEqual(status["campaign"], "HOLD")

    def test_S_and_M_repairs_keep_core_scope_and_remain_separate(self):
        repairs = build_career_threshold_hold().to_dict()["required_repairs"]

        self.assertIn("single_ev_aggregator_setpoint", repairs["S"])
        self.assertIn("exact_M9_candidate_library", repairs["M"])
        self.assertNotEqual(repairs["S"], repairs["M"])
        self.assertIn("no_online_update", repairs["M"])

    def test_governance_cannot_enable_threshold_freeze(self):
        payload = build_career_threshold_hold().to_dict()
        payload["governance"]["scientific_threshold_freeze_authorized"] = True

        with self.assertRaisesRegex(ContractViolation, "governance"):
            CareerThresholdHold(readdress(payload))

    def test_content_address_rejects_unacknowledged_source_hash_mutation(self):
        payload = build_career_threshold_hold().to_dict()
        payload["candidate_source_audit"]["S"]["artifact"]["sha256"] = (
            "0" * 64
        )

        with self.assertRaisesRegex(ContractViolation, "contract_id mismatch"):
            CareerThresholdHold(payload)

    def test_readdressed_source_hash_mutation_still_fails_semantics(self):
        payload = copy.deepcopy(build_career_threshold_hold().to_dict())
        payload["candidate_source_audit"]["M"]["exploratory_trace"][
            "sha256"] = "0" * 64

        with self.assertRaisesRegex(ContractViolation, "trace audit"):
            CareerThresholdHold(readdress(payload))


if __name__ == "__main__":
    unittest.main()
