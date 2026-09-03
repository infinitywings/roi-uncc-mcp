from __future__ import annotations

import unittest
from pathlib import Path

from g7confirm.m20_timing import verify_timing_qualification
from g7confirm.runtime import PRELIMINARY_RUNTIME_PROFILES, build_parser, run_bounded


class M20TimingTests(unittest.TestCase):
    def test_M20_profile_is_exactly_two_windows_and_one_intervention(self):
        profile = PRELIMINARY_RUNTIME_PROFILES[
            "m20_pair_runtime_qualification_seed5102"
        ]
        self.assertEqual(profile["seed"], 5102)
        self.assertEqual(profile["windows"], 2)
        self.assertEqual(profile["window_seconds"], 10)
        self.assertEqual(profile["attack_window_cap"], 1)
        self.assertEqual(profile["attack_energy_cap_kvah"], 2.0)

    def test_M20_profile_rejects_a_third_window_before_execution(self):
        args = build_parser().parse_args([
            "--preliminary-role", "runtime_qualification",
            "--pair-id", "m20_pair_runtime_qualification_seed5102",
            "--operating-point", "responsive_night",
            "--attacker-seed", "5102",
            "--windows", "3",
            "--output-dir", "/tmp/m20-must-not-run",
        ])
        with self.assertRaisesRegex(ValueError, "profile drift for windows"):
            run_bounded(args)

    def test_legacy_runtime_remains_one_window_capped(self):
        args = build_parser().parse_args([
            "--operating-point", "responsive_night",
            "--attacker-seed", "8101",
            "--windows", "2",
            "--output-dir", "/tmp/legacy-must-not-run",
        ])
        with self.assertRaisesRegex(ValueError, "hard-capped at one window"):
            run_bounded(args)

    def test_checked_in_M20_negative_result_is_content_addressed(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "artifacts"
            / "m20_two_window_timing_seed5102_attempt1"
        )
        self.assertEqual(verify_timing_qualification(root), [])


if __name__ == "__main__":
    unittest.main()
