from __future__ import annotations

import unittest
from pathlib import Path

from g7confirm.m19_qualification import (
    PAIR_ID,
    REPLICATE_SEED,
    verify_qualification,
)
from g7confirm.runtime import BenignPolicy, _preliminary_component_seeds
from g7confirm.spec import load_spec


class M19QualificationTests(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(Path(__file__).resolve().parents[1] / "experiment_spec.yaml")

    def test_runtime_qualification_seed_uses_m18_overlay(self):
        role, seeds = _preliminary_component_seeds(
            spec=self.spec,
            role="runtime_qualification",
            replicate_seed=REPLICATE_SEED,
            gridlabd_seed=42,
            explicit_noise_seed=95101,
        )
        self.assertEqual(role, "runtime_qualification")
        self.assertEqual(seeds.replicate_seed, REPLICATE_SEED)
        self.assertEqual(seeds.measurement_noise_seed, 95101)

    def test_final_evaluation_seed_is_rejected_by_overlay(self):
        with self.assertRaisesRegex(ValueError, "not registered"):
            _preliminary_component_seeds(
                spec=self.spec,
                role="runtime_qualification",
                replicate_seed=9101,
                gridlabd_seed=42,
                explicit_noise_seed=None,
            )

    def test_benign_policy_never_requests_a_command(self):
        policy = BenignPolicy()
        self.assertEqual(policy.decide(0, 10, {"DER_A": 1.0}), {})
        policy.note_spent({})
        self.assertEqual(policy.spent, 0)

    def test_pair_identifier_is_fixed_for_the_bounded_attempt(self):
        self.assertEqual(PAIR_ID, "m19_pair_runtime_qualification_seed5101")

    def test_checked_in_attempt_two_evidence_is_content_addressed(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "artifacts"
            / "m19_runtime_qualification_seed5101_attempt2"
        )
        self.assertEqual(verify_qualification(root), [])


if __name__ == "__main__":
    unittest.main()
