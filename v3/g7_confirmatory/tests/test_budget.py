from __future__ import annotations

import unittest

from g7confirm.budget import (
    DualBudget,
    DualBudgetPolicyAdapter,
    RunnerOwnedDualBudgetPolicyAdapter,
)


class StubPolicy:
    def __init__(self, proposals):
        self.proposals = iter(proposals)
        self.spent = 0

    def decide(self, window, time_s, telemetry):
        return next(self.proposals)

    def note_spent(self, commands):
        if commands:
            self.spent += 1


class DualBudgetTests(unittest.TestCase):
    def test_benign_equivalent_command_costs_nothing(self):
        budget = DualBudget(window_cap=1, apparent_energy_cap_kvah=1.0, window_seconds=10)
        result = budget.try_admit({"pv": (80.0, 0.0)}, {"pv": (80.0, 0.0)})
        self.assertTrue(result.accepted)
        self.assertEqual(result.commands, {})
        self.assertEqual(budget.windows_spent, 0)
        self.assertEqual(budget.energy_spent_kvah, 0.0)

    def test_energy_is_command_deviation_from_benign(self):
        budget = DualBudget(window_cap=2, apparent_energy_cap_kvah=1.0, window_seconds=10)
        result = budget.try_admit({"bess": (100.0, 0.0), "pv": (0.0, 0.0)},
                                  {"bess": (0.0, 0.0), "pv": (80.0, 0.0)})
        expected = 180.0 * 10.0 / 3600.0
        self.assertTrue(result.accepted)
        self.assertAlmostEqual(result.apparent_energy_kvah, expected)
        self.assertAlmostEqual(budget.energy_spent_kvah, expected)

    def test_over_energy_rejection_is_atomic(self):
        budget = DualBudget(window_cap=3, apparent_energy_cap_kvah=0.1, window_seconds=10)
        first = budget.try_admit({"d": (10.0, 0.0)}, {"d": (0.0, 0.0)})
        self.assertTrue(first.accepted)
        before = (budget.windows_spent, budget.energy_spent_kvah)
        rejected = budget.try_admit({"d": (100.0, 0.0)}, {"d": (0.0, 0.0)})
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "apparent_energy_cap")
        self.assertEqual(rejected.commands, {})
        self.assertEqual((budget.windows_spent, budget.energy_spent_kvah), before)

    def test_over_window_rejection_is_atomic(self):
        budget = DualBudget(window_cap=1, apparent_energy_cap_kvah=10, window_seconds=10)
        self.assertTrue(budget.try_admit({"d": (1, 0)}, {"d": (0, 0)}).accepted)
        rejected = budget.try_admit({"d": (1, 0)}, {"d": (0, 0)})
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "perturbed_window_cap")
        self.assertEqual(budget.windows_spent, 1)

    def test_adapter_notes_inner_spend_only_after_acceptance(self):
        policy = StubPolicy([{"d": (1.0, 0.0)}, {"d": (100.0, 0.0)}])
        budget = DualBudget(window_cap=2, apparent_energy_cap_kvah=0.01, window_seconds=10)
        adapter = DualBudgetPolicyAdapter(policy, budget, {"d": (0.0, 0.0)})
        self.assertEqual(adapter.decide(0, 10, {}), {"d": (1.0, 0.0)})
        self.assertEqual(adapter.decide(1, 20, {}), {})
        self.assertEqual(policy.spent, 1)
        self.assertEqual(adapter.trace[-1]["reason"], "apparent_energy_cap")

    def test_unknown_device_fails_closed(self):
        budget = DualBudget(window_cap=1, apparent_energy_cap_kvah=1, window_seconds=10)
        with self.assertRaisesRegex(ValueError, "missing benign"):
            budget.try_admit({"unknown": (1, 0)}, {"known": (0, 0)})

    def test_runner_owned_adapter_accounts_exactly_once(self):
        policy = StubPolicy([{"d": (1.0, 0.0)}])
        dual = DualBudget(window_cap=1, apparent_energy_cap_kvah=1, window_seconds=10)
        adapter = RunnerOwnedDualBudgetPolicyAdapter(policy, dual, {"d": (0.0, 0.0)})
        admitted = adapter.decide(0, 10, {})
        self.assertEqual(policy.spent, 0)
        adapter.note_spent(admitted)
        self.assertEqual(policy.spent, 1)
        self.assertEqual(adapter.spent, 1)
        self.assertTrue(adapter.trace[-1]["runner_noted"])

    def test_runner_owned_adapter_rejection_never_reaches_delivery(self):
        policy = StubPolicy([{"d": (100.0, 0.0)}])
        dual = DualBudget(window_cap=1, apparent_energy_cap_kvah=0.01, window_seconds=10)
        adapter = RunnerOwnedDualBudgetPolicyAdapter(policy, dual, {"d": (0.0, 0.0)})
        admitted = adapter.decide(0, 10, {})
        self.assertEqual(admitted, {})
        adapter.note_spent(admitted)
        self.assertEqual(policy.spent, 0)
        self.assertEqual(adapter.trace[-1]["reason"], "apparent_energy_cap")

    def test_runner_owned_adapter_detects_runner_command_drift(self):
        policy = StubPolicy([{"d": (1.0, 0.0)}])
        dual = DualBudget(window_cap=1, apparent_energy_cap_kvah=1, window_seconds=10)
        adapter = RunnerOwnedDualBudgetPolicyAdapter(policy, dual, {"d": (0.0, 0.0)})
        adapter.decide(0, 10, {})
        with self.assertRaisesRegex(RuntimeError, "runner command drift"):
            adapter.note_spent({"d": (2.0, 0.0)})


if __name__ == "__main__":
    unittest.main()
