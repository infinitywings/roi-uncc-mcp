from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from g7confirm.m23_system_identification import (
    PAIR_ID,
    TARGET_IDS,
    TREATMENTS,
    build_action_requests,
    build_contract,
    verify_source,
)
from g7confirm.m23_independent_audit import (
    audit_source,
    verify_audit_receipt,
)
from g7confirm.manifest import create_once_json
from g7confirm.preliminary_only_gate import validate_preliminary_action_request
from g7confirm.runtime import PRELIMINARY_RUNTIME_PROFILES


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ATTEMPT_ROOT = (
    PACKAGE_ROOT
    / "artifacts"
    / "m23_system_identification_seed6101_attempt1"
)


class M23SystemIdentificationTests(unittest.TestCase):
    def test_profile_is_one_benign_plus_four_symmetric_three_window_probes(self):
        profile = PRELIMINARY_RUNTIME_PROFILES[PAIR_ID]
        self.assertEqual(profile["partition_role"], "system_identification")
        self.assertEqual(profile["action_type"], "simulator_execution")
        self.assertEqual(profile["seed"], 6101)
        self.assertEqual(profile["windows"], 3)
        self.assertEqual(profile["window_seconds"], 10)
        self.assertEqual(profile["attack_window_cap"], 1)
        self.assertEqual(profile["attack_energy_cap_kvah"], 2.0)
        self.assertEqual(len(TREATMENTS), 5)
        self.assertEqual(TARGET_IDS, ("DER_EV1_BESS", "DER_EV4_BESS"))
        for target in TARGET_IDS:
            keys = set(profile["probe_action_ids"])
            self.assertIn(f"{target}:+30", keys)
            self.assertIn(f"{target}:-30", keys)

    def test_all_six_action_requests_pass_M18(self):
        requests = build_action_requests()
        self.assertEqual(len(requests), 6)
        types = [request["action_type"] for request in requests.values()]
        self.assertEqual(types.count("simulator_execution"), 5)
        self.assertEqual(types.count("source_generation"), 1)
        for request in requests.values():
            self.assertEqual(validate_preliminary_action_request(request), [])
            self.assertEqual(request["partition_role"], "system_identification")
            self.assertFalse(request["physical_field_actuator"])
            self.assertFalse(request["final_evaluation_data_accessed"])

    def test_contract_build_is_deterministic_and_non_confirmatory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, request in build_action_requests().items():
                create_once_json(root / name, request)
            first = build_contract(root)
            second = build_contract(root)
        self.assertEqual(first, second)
        self.assertTrue(first["contract_id"].startswith("m23contract_"))
        self.assertEqual(first["runtime"]["valid_post_actuation_time_s"], 30)
        self.assertFalse(first["confirmatory_claim_authorized"])
        self.assertFalse(first["access_boundary"]["resource_admission"])

    def test_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            issues = verify_source(Path(directory))
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].startswith("M23_source_unreadable_or_invalid:"))

    def test_generator_verifier_timestamp_failure_is_retained(self):
        self.assertEqual(
            verify_source(ATTEMPT_ROOT),
            ["M23_source_content_drift", "M23_source_id_drift"],
        )

    def test_checked_in_source_passes_independent_exact_byte_audit(self):
        self.assertEqual(audit_source(ATTEMPT_ROOT), [])
        receipt = json.loads(
            (ATTEMPT_ROOT / "independent_audit_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(verify_audit_receipt(ATTEMPT_ROOT, receipt), [])


if __name__ == "__main__":
    unittest.main()
