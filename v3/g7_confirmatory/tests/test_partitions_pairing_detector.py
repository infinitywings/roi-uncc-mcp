from __future__ import annotations

import copy
import unittest
from pathlib import Path

from g7confirm.detector_freeze import (
    build_benign_calibration_plan,
    build_detector_provenance_audit,
)
from g7confirm.pairing import build_paired_development_plan, validate_pair
from g7confirm.partitions import (
    SeedGuardError,
    derive_component_seeds,
    gridlabd_random_seed,
    partition_for_seed,
    require_component_seeds,
    require_seed_partition,
)
from g7confirm.spec import SpecError, load_spec


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
HASHES = {
    "runner": "1" * 64,
    "source_glm": "2" * 64,
    "device_config": "3" * 64,
    "detector": "4" * 64,
    "sensitivity": "5" * 64,
}


class PartitionPairingDetectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_spec(ROOT / "experiment_spec.yaml")
        cls.simulator_seed = gridlabd_random_seed(
            REPO / "examples/2bus-13bus/1c_IEEE_123_feeder.glm"
        )

    def test_seed_partitions_are_classified_and_unknown_rejected(self):
        self.assertEqual(partition_for_seed(self.spec, 7101), "detector_calibration")
        self.assertEqual(partition_for_seed(self.spec, 8101), "development")
        self.assertEqual(partition_for_seed(self.spec, 9101), "evaluation")
        with self.assertRaisesRegex(SeedGuardError, "not declared"):
            partition_for_seed(self.spec, 1001)

    def test_evaluation_seed_is_sealed(self):
        with self.assertRaisesRegex(SeedGuardError, "evaluation seed 9101 is sealed"):
            require_seed_partition(
                self.spec, 9101, allowed=("development",), purpose="test"
            )

    def test_component_seed_derivation_matches_frozen_runner(self):
        assignment = derive_component_seeds(
            self.spec, 8101, gridlabd_random_seed=self.simulator_seed
        )
        self.assertEqual(assignment.measurement_noise_seed, 98101)
        self.assertEqual(assignment.gridlabd_random_seed, 10)
        with self.assertRaisesRegex(SeedGuardError, "noise seed drift"):
            require_component_seeds(
                self.spec,
                replicate_seed=8101,
                gridlabd_random_seed=10,
                explicit_noise_seed=7,
                allowed=("development",),
                purpose="test",
            )

    def test_paired_plan_is_non_executable_and_exactly_controlled(self):
        plan = build_paired_development_plan(
            self.spec,
            "smoke",
            dependency_hashes=HASHES,
            detector_package_id="g7det_test",
            gridlabd_seed=self.simulator_seed,
        )
        self.assertFalse(plan["evaluation_opened"])
        self.assertFalse(plan["executable"])
        self.assertEqual(plan["pair_count"], len(self.spec["search"]["arms"]))
        for pair in plan["pairs"]:
            validate_pair(pair, self.spec)
            self.assertEqual(
                pair["runs"][0]["controlled_lineage"],
                pair["runs"][1]["controlled_lineage"],
            )

    def test_pair_control_drift_fails_closed(self):
        plan = build_paired_development_plan(
            self.spec,
            "smoke",
            dependency_hashes=HASHES,
            detector_package_id="g7det_test",
            gridlabd_seed=self.simulator_seed,
        )
        bad = copy.deepcopy(plan["pairs"][0])
        bad["runs"][1]["controlled_lineage"]["volt_var"] = True
        with self.assertRaisesRegex(SpecError, "controlled-lineage drift"):
            validate_pair(bad, self.spec)

    def test_evaluation_seed_cannot_be_smuggled_into_pair(self):
        plan = build_paired_development_plan(
            self.spec,
            "smoke",
            dependency_hashes=HASHES,
            detector_package_id="g7det_test",
            gridlabd_seed=self.simulator_seed,
        )
        bad = copy.deepcopy(plan["pairs"][0])
        seeds = derive_component_seeds(
            self.spec, 9101, gridlabd_random_seed=self.simulator_seed
        ).as_dict()
        for run in bad["runs"]:
            run["controlled_lineage"]["replicate_seed"] = 9101
            run["controlled_lineage"]["component_seeds"] = seeds
            run["controlled_lineage"]["partition"] = "evaluation"
        with self.assertRaisesRegex(SeedGuardError, "evaluation seed 9101 is sealed"):
            validate_pair(bad, self.spec)

    def test_legacy_benign_is_preserved_but_not_admissible(self):
        audit = build_detector_provenance_audit(
            self.spec,
            repo_root=REPO,
            mission_id="mis_test",
            decision_id="dec_test",
        )
        self.assertFalse(audit["legacy_candidate"]["admissible_for_confirmatory_calibration"])
        self.assertFalse(audit["freeze_state"]["calibrated"])
        self.assertFalse(audit["freeze_state"]["evaluation_admissible"])
        checks = {item["name"]: item for item in audit["legacy_candidate"]["checks"]}
        self.assertFalse(checks["replicate_seed_in_detector_calibration_partition"]["passed"])
        self.assertFalse(checks["explicit_condition_and_noise_lineage"]["passed"])
        self.assertFalse(checks["sensitivity_sources_content_addressed"]["passed"])

    def test_calibration_plan_is_benign_only_and_partitioned(self):
        plan = build_benign_calibration_plan(
            self.spec,
            dependency_hashes=HASHES,
            gridlabd_seed=self.simulator_seed,
        )
        expected = (
            len(self.spec["conditions"]["operating_points"])
            * len(self.spec["conditions"]["volt_var"])
            * len(self.spec["partitions"]["detector_calibration"])
        )
        self.assertEqual(plan["run_count"], expected)
        self.assertFalse(plan["executable"])
        self.assertEqual({run["treatment"] for run in plan["runs"]}, {"benign"})
        self.assertEqual(
            {run["controlled_lineage"]["partition"] for run in plan["runs"]},
            {"detector_calibration"},
        )


if __name__ == "__main__":
    unittest.main()
