from __future__ import annotations

import unittest

from g7confirm.budget import DualBudget, RunnerOwnedDualBudgetPolicyAdapter
from g7confirm.partitions import SeedGuardError
from g7confirm.runtime import (
    build_parser,
    load_frozen_runtime,
    reconcile_delivery,
    run_bounded,
)


class StubPolicy:
    def __init__(self, proposals):
        self.proposals = iter(proposals)
        self.budget = 2
        self.spent = 0
        self.feedback = None
        self.detector = None

    def decide(self, window, time_s, telemetry):
        return next(self.proposals)

    def note_spent(self, commands):
        if commands:
            self.spent += 1


class RuntimeIntegrationTests(unittest.TestCase):
    def test_runtime_rejects_evaluation_seed_before_loading_composition(self):
        args = build_parser().parse_args([
            "--operating-point", "responsive_night",
            "--attacker-seed", "9101",
            "--output-dir", "/tmp/must-not-be-created-g7-evaluation",
            "--gen-only",
        ])
        with self.assertRaisesRegex(SeedGuardError, "evaluation seed 9101 is sealed"):
            run_bounded(args)

    def test_runtime_detector_is_held_without_parameter_artifact(self):
        args = build_parser().parse_args([
            "--operating-point", "responsive_night",
            "--attacker-seed", "8101",
            "--output-dir", "/tmp/must-not-be-created-g7-detector",
            "--detector",
            "--gen-only",
        ])
        with self.assertRaisesRegex(ValueError, "detector execution is held"):
            run_bounded(args)

    def test_frozen_runner_composes_with_frozen_base(self):
        base, attack, hashes = load_frozen_runtime()
        self.assertIs(attack.base, base)
        self.assertTrue(base.SOURCE_GLM.is_file())
        self.assertEqual(len(hashes["frozen_attack_runner_sha256"]), 64)
        self.assertEqual(len(hashes["frozen_base_runner_sha256"]), 64)

    def test_delivery_reconciliation_matches_runner_order(self):
        policy = StubPolicy([{"d": (10.0, 0.0)}, {"d": (100.0, 0.0)}])
        adapter = RunnerOwnedDualBudgetPolicyAdapter(
            policy,
            DualBudget(window_cap=2, apparent_energy_cap_kvah=0.05, window_seconds=10),
            {"d": (0.0, 0.0)},
        )
        first = adapter.decide(0, 10, {})
        adapter.note_spent(first)
        second = adapter.decide(1, 20, {})
        adapter.note_spent(second)
        self.assertEqual(first, {"d": (10.0, 0.0)})
        self.assertEqual(second, {})

        evidence = reconcile_delivery(
            adapter=adapter,
            attack_trace=[
                {"attack": {"d": [10.0, 0.0]}},
                {"attack": {}},
            ],
            device_traces={"d": [
                {"cmd_p_kw": 10.0, "cmd_q_kvar": 0.0, "perturbed": True},
                {"cmd_p_kw": 0.0, "cmd_q_kvar": 0.0, "perturbed": False},
            ]},
            benign_commands={"d": (0.0, 0.0)},
            window_seconds=10,
        )
        self.assertTrue(evidence["delivery_reconciled"])
        self.assertEqual(evidence["windows_spent"], 1)
        self.assertAlmostEqual(
            evidence["admitted_energy_kvah"],
            evidence["delivered_command_energy_kvah"],
        )

    def test_reconciliation_rejects_unadmitted_delivery(self):
        policy = StubPolicy([{"d": (100.0, 0.0)}])
        adapter = RunnerOwnedDualBudgetPolicyAdapter(
            policy,
            DualBudget(window_cap=1, apparent_energy_cap_kvah=0.01, window_seconds=10),
            {"d": (0.0, 0.0)},
        )
        admitted = adapter.decide(0, 10, {})
        adapter.note_spent(admitted)
        with self.assertRaisesRegex(RuntimeError, "admitted/runner attack drift"):
            reconcile_delivery(
                adapter=adapter,
                attack_trace=[{"attack": {"d": [100.0, 0.0]}}],
                device_traces={"d": [
                    {"cmd_p_kw": 100.0, "cmd_q_kvar": 0.0, "perturbed": True},
                ]},
                benign_commands={"d": (0.0, 0.0)},
                window_seconds=10,
            )


if __name__ == "__main__":
    unittest.main()
