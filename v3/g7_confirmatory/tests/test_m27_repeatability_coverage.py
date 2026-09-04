from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from g7confirm.m27_independent_audit import audit, verify_receipt
from g7confirm.m27_profiles import (
    M27_CELLS,
    M27_RUNTIME_PROFILES,
    TARGET_IDS,
    build_runtime_profiles,
    cell_id,
    pair_id,
    treatment_definitions,
)
from g7confirm.m27_repeatability_coverage import (
    OPERATING_POINTS,
    _anchor_cell,
    _stats,
    build_action_requests,
    build_contract,
    verify_evidence,
)
from g7confirm.m27_runtime import validate_m27_args
from g7confirm.manifest import create_once_json
from g7confirm.preliminary_only_gate import validate_preliminary_action_request


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ATTEMPT_ROOT = PACKAGE_ROOT / "artifacts" / "m27_repeatability_coverage_attempt1"


class M27RepeatabilityCoverageTests(unittest.TestCase):
    def test_crossed_anchor_has_six_new_cells_and_two_identifiable_axes(self):
        observed = [(item["seed"], item["operating_point"]) for item in M27_CELLS]
        self.assertEqual(len(observed), 6)
        self.assertEqual(
            {seed for seed, point in observed if point == "responsive_night"},
            {6102, 6103},
        )
        self.assertEqual(
            {point for seed, point in observed if seed == 6102},
            set(OPERATING_POINTS),
        )
        self.assertNotIn((6101, "responsive_night"), observed)

    def test_each_profile_is_one_benign_plus_four_symmetric_probes(self):
        self.assertEqual(M27_RUNTIME_PROFILES, build_runtime_profiles())
        self.assertEqual(len(M27_RUNTIME_PROFILES), 6)
        for cell in M27_CELLS:
            seed = cell["seed"]
            point = cell["operating_point"]
            profile = M27_RUNTIME_PROFILES[pair_id(seed, point)]
            self.assertEqual(profile["seed"], seed)
            self.assertEqual(profile["operating_point"], point)
            self.assertEqual(profile["partition_role"], "system_identification")
            self.assertEqual(profile["windows"], 3)
            self.assertEqual(profile["window_seconds"], 10)
            treatments = treatment_definitions(seed, point)
            self.assertEqual(len(treatments), 5)
            for target in TARGET_IDS:
                self.assertIn(f"{target}:+30", profile["probe_action_ids"])
                self.assertIn(f"{target}:-30", profile["probe_action_ids"])

    def test_all_thirty_six_action_requests_pass_M18(self):
        requests = build_action_requests()
        flattened = [request for cell in requests.values() for request in cell.values()]
        self.assertEqual(len(flattened), 36)
        self.assertEqual(len({request["action_id"] for request in flattened}), 36)
        self.assertEqual(sum(request["action_type"] == "simulator_execution" for request in flattened), 30)
        self.assertEqual(sum(request["action_type"] == "source_generation" for request in flattened), 6)
        for request in flattened:
            self.assertEqual(validate_preliminary_action_request(request), [])
            self.assertIn(request["seed"], {6102, 6103})
            self.assertFalse(request["final_evaluation_data_accessed"])
            self.assertFalse(request["physical_field_actuator"])

    def test_contract_is_deterministic_and_retains_interaction_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requests = build_action_requests()
            for identifier, items in requests.items():
                request_root = root / "requests" / identifier
                request_root.mkdir(parents=True)
                for name, request in items.items():
                    create_once_json(request_root / name, request)
            first = build_contract(root)
            second = build_contract(root)
        self.assertEqual(first, second)
        self.assertTrue(first["contract_id"].startswith("m27contract_"))
        self.assertEqual(first["design"]["new_runtime_run_cap"], 30)
        self.assertEqual(first["design"]["retry_cap"], 0)
        self.assertFalse(first["design"]["seed_by_operating_point_interaction_estimable"])
        self.assertFalse(first["access_boundary"]["resource_admission"])
        self.assertFalse(first["access_boundary"]["final_evaluation"])

    def test_runtime_wrapper_rejects_seed_or_operating_point_drift(self):
        args = argparse.Namespace(
            pair_id=pair_id(6102, "responsive_night"),
            preliminary_role="system_identification",
            attacker_seed=6102,
            operating_point="responsive_night",
        )
        validate_m27_args(args)
        args.attacker_seed = 6103
        with self.assertRaisesRegex(ValueError, "seed differs"):
            validate_m27_args(args)
        args.attacker_seed = 6102
        args.operating_point = "responsive_morning"
        with self.assertRaisesRegex(ValueError, "operating point differs"):
            validate_m27_args(args)

    def test_M23_anchor_is_exact_and_not_reexecuted(self):
        anchor = _anchor_cell()
        self.assertEqual(anchor["seed"], 6101)
        self.assertEqual(anchor["operating_point"], "responsive_night")
        self.assertFalse(anchor["provenance"]["runtime_rerun"])
        self.assertEqual(anchor["rank"]["true"]["winner"], "DER_EV4_BESS")

    def test_small_n_statistics_are_explicit_and_descriptive(self):
        result = _stats([1.0, 2.0, 3.0])
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["mean"], 2.0)
        self.assertEqual(result["sample_sd"], 1.0)
        self.assertEqual(
            result["interval_interpretation"],
            "descriptive_small_n_not_population_certification",
        )

    def test_missing_attempt_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            issues = verify_evidence(Path(directory))
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].startswith("M27_evidence_unreadable_or_invalid:"))

    @unittest.skipUnless(ATTEMPT_ROOT.is_dir(), "M27 runtime attempt not generated yet")
    def test_checked_in_attempt_passes_primary_and_independent_audit(self):
        self.assertEqual(verify_evidence(ATTEMPT_ROOT), [])
        self.assertEqual(audit(ATTEMPT_ROOT), [])
        receipt = json.loads(
            (ATTEMPT_ROOT / "independent_audit_receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(verify_receipt(ATTEMPT_ROOT, receipt), [])


if __name__ == "__main__":
    unittest.main()
