from __future__ import annotations

import copy
import unittest
from pathlib import Path

from g7confirm.prompt_audit import (
    PromptAuditError,
    audit_static_prompt,
    load_prompt,
    render_messages,
)


ROOT = Path(__file__).resolve().parents[1]


class PromptAuditTests(unittest.TestCase):
    def setUp(self):
        self.prompt = load_prompt(ROOT / "prompts/clean_uninformed_v1.json")

    def test_clean_prompt_renders_exact_contract(self):
        messages = render_messages(
            self.prompt,
            amplitudes=[0.05, 0.15],
            periods=[2, 4],
            window_cap=8,
            energy_cap=2.0,
        )
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertIn('"amplitude_fraction"', messages[1]["content"])
        self.assertIn("No proposals have been evaluated", messages[1]["content"])

    def test_legacy_alarm_horizon_is_rejected(self):
        bad = copy.deepcopy(self.prompt)
        bad["system"] += " Benign self-alarm is near window 68."
        with self.assertRaisesRegex(PromptAuditError, "alarm"):
            audit_static_prompt(bad)

    def test_legacy_ranked_alpha_is_rejected(self):
        bad = copy.deepcopy(self.prompt)
        bad["system"] += " The best alpha is 0.05."
        with self.assertRaisesRegex(PromptAuditError, "alpha"):
            audit_static_prompt(bad)

    def test_evaluation_history_is_rejected(self):
        with self.assertRaisesRegex(PromptAuditError, "development-partition"):
            render_messages(
                self.prompt,
                amplitudes=[0.1],
                periods=[2],
                window_cap=8,
                energy_cap=2.0,
                history=[{
                    "partition": "evaluation",
                    "proposal_index": 0,
                    "amplitude_fraction": 0.1,
                    "period_windows": 2,
                    "paired_harm_before_alarm": 1.0,
                    "first_alarm_window": 10,
                    "status": "complete",
                }],
            )

    def test_unknown_history_field_is_rejected(self):
        with self.assertRaisesRegex(PromptAuditError, "unapproved fields"):
            render_messages(
                self.prompt,
                amplitudes=[0.1], periods=[2], window_cap=8, energy_cap=2.0,
                history=[{"partition": "development", "secret_threshold": 3.0}],
            )


if __name__ == "__main__":
    unittest.main()

