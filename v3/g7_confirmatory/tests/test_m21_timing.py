from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from g7confirm.m21_timing import verify_timing_qualification
from g7confirm.runtime import PRELIMINARY_RUNTIME_PROFILES, build_parser, run_bounded


class M21TimingTests(unittest.TestCase):
    def test_M21_profile_is_exactly_three_windows_and_one_intervention(self):
        profile = PRELIMINARY_RUNTIME_PROFILES[
            "m21_pair_runtime_qualification_seed5103"
        ]
        self.assertEqual(profile["seed"], 5103)
        self.assertEqual(profile["windows"], 3)
        self.assertEqual(profile["window_seconds"], 10)
        self.assertEqual(profile["attack_window_cap"], 1)
        self.assertEqual(profile["attack_energy_cap_kvah"], 2.0)

    def test_M21_profile_rejects_a_fourth_window_before_execution(self):
        args = build_parser().parse_args([
            "--preliminary-role", "runtime_qualification",
            "--pair-id", "m21_pair_runtime_qualification_seed5103",
            "--operating-point", "responsive_night",
            "--attacker-seed", "5103",
            "--windows", "4",
            "--output-dir", "/tmp/m21-must-not-run",
        ])
        with self.assertRaisesRegex(ValueError, "profile drift for windows"):
            run_bounded(args)

    def test_M20_profile_still_rejects_a_third_window(self):
        args = build_parser().parse_args([
            "--preliminary-role", "runtime_qualification",
            "--pair-id", "m20_pair_runtime_qualification_seed5102",
            "--operating-point", "responsive_night",
            "--attacker-seed", "5102",
            "--windows", "3",
            "--output-dir", "/tmp/m20-must-not-run-from-m21",
        ])
        with self.assertRaisesRegex(ValueError, "profile drift for windows"):
            run_bounded(args)

    def test_missing_M21_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            issues = verify_timing_qualification(Path(directory))
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].startswith("qualification_unreadable:"))

    def test_checked_in_M21_result_is_content_addressed(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "artifacts"
            / "m21_three_window_timing_seed5103_attempt1"
        )
        self.assertEqual(verify_timing_qualification(root), [])


if __name__ == "__main__":
    unittest.main()
