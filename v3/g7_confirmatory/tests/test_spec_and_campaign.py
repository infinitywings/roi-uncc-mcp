from __future__ import annotations

import copy
import unittest
from pathlib import Path

from g7confirm.campaign import expand_profile
from g7confirm.operating_points import OPERATING_POINTS
from g7confirm.spec import SpecError, load_spec, validate_spec


ROOT = Path(__file__).resolve().parents[1]


class SpecAndCampaignTests(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(ROOT / "experiment_spec.yaml")

    def test_checked_in_spec_is_valid_and_not_authorized(self):
        self.assertFalse(self.spec["campaign_authorized"])
        self.assertEqual(self.spec["search"]["outer_budget_k"], 12)

    def test_partition_overlap_fails_closed(self):
        bad = copy.deepcopy(self.spec)
        bad["partitions"]["evaluation"][0] = bad["partitions"]["development"][0]
        with self.assertRaisesRegex(SpecError, "overlap"):
            validate_spec(bad)

    def test_campaign_authorization_cannot_be_enabled_in_phase_one(self):
        bad = copy.deepcopy(self.spec)
        bad["campaign_authorized"] = True
        with self.assertRaisesRegex(SpecError, "campaign_authorized"):
            validate_spec(bad)

    def test_smoke_plan_has_equal_one_proposal_per_arm(self):
        plan = expand_profile(self.spec, "smoke")
        self.assertFalse(plan["executable"])
        self.assertFalse(plan["campaign_authorized"])
        self.assertEqual(len(plan["runs"]), len(self.spec["search"]["arms"]))
        self.assertEqual({run["proposal_index"] for run in plan["runs"]}, {0})
        self.assertEqual({run["seed"] for run in plan["runs"]}, {8101})
        llm = next(run for run in plan["runs"] if run["arm"] == "llm_clean_uninformed")
        self.assertIsNone(llm["proposal"])
        self.assertEqual(llm["status"], "requires_model_proposal")

    def test_plan_is_deterministic(self):
        first = expand_profile(self.spec, "smoke")
        second = expand_profile(self.spec, "smoke")
        self.assertEqual(first, second)

    def test_spec_operating_points_match_runtime_actuator(self):
        declared = {
            item["id"]: item["start_time"]
            for item in self.spec["conditions"]["operating_points"]
        }
        runtime = {key: value.start_time for key, value in OPERATING_POINTS.items()}
        self.assertEqual(declared, runtime)
        self.assertTrue(self.spec["runtime_integration"]["campaign_hold_preserved"])


if __name__ == "__main__":
    unittest.main()
