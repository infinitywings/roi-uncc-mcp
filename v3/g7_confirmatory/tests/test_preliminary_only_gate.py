from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from g7confirm.cli import build_parser, main
from g7confirm.orchestration_contract import ContractViolation
from g7confirm.preliminary_only_gate import (
    BOUND_ASSETS,
    EMBEDDING_SERVICE_IDENTITY,
    FINAL_SEALS,
    LLM_SERVICE_IDENTITY,
    PARTITION_REGISTRY,
    PRELIMINARY_GATE_SCHEMA_VERSION,
    PRELIMINARY_GATE_STATUS,
    PRELIMINARY_PERMISSIONS,
    PreliminaryOnlyGate,
    build_preliminary_only_gate,
    load_preliminary_only_gate,
    preliminary_gate_id_for,
    validate_preliminary_action_request,
    verify_bound_assets,
    verify_checked_in_preliminary_gate,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
ARTIFACT_PATH = PACKAGE_ROOT / "artifacts/preliminary_only_gate_m18.json"
SCHEMA_PATH = PACKAGE_ROOT / "preliminary_only_gate.schema.json"
EXPECTED_GATE_ID = (
    "m18preliminary_f8169459011b6d4dffa2b8dbd08f052dfe0a1323b5ed617199e1ff2eed6bd5c5"
)


def readdress(payload: dict) -> dict:
    payload["gate_id"] = preliminary_gate_id_for(payload)
    return payload


def request(**overrides: object) -> dict:
    payload = {
        "action_id": "prelim-action-0001",
        "action_type": "preliminary_runtime_evaluation",
        "partition_role": "runtime_qualification",
        "seed": 5101,
        "output_classification": "PRELIMINARY_ONLY",
        "create_once": True,
        "manifest_sha256": "a" * 64,
        "code_sha256": "b" * 64,
        "config_sha256": "c" * 64,
        "budget_id": "single-window-runtime-v1",
        "paired_benign_id": "prelim-benign-0001",
        "final_evaluation_data_accessed": False,
        "physical_field_actuator": False,
        "starts_or_restarts_service": False,
        "retain_failures": True,
        "local_service_identity": None,
    }
    payload.update(overrides)
    return payload


def run_cli(argv: list[str]) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv)
    payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
    return exit_code, payload, stderr.getvalue()


class PreliminaryOnlyGateTests(unittest.TestCase):
    def test_checked_in_artifact_matches_canonical_builder(self):
        stored = load_preliminary_only_gate(ARTIFACT_PATH)
        built = build_preliminary_only_gate()

        self.assertEqual(stored.to_dict(), built.to_dict())
        self.assertEqual(stored.gate_id, EXPECTED_GATE_ID)
        self.assertEqual(stored.gate_id, preliminary_gate_id_for(stored.to_dict()))
        self.assertEqual(stored.to_dict()["status"], PRELIMINARY_GATE_STATUS)

    def test_schema_is_closed_and_names_contract_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            PRELIMINARY_GATE_SCHEMA_VERSION,
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(
            schema["properties"]["final_seals"]["additionalProperties"]
        )

    def test_bound_assets_and_upstream_M17_are_exact(self):
        self.assertEqual(len(BOUND_ASSETS), 6)
        self.assertEqual(verify_bound_assets(REPO_ROOT), [])
        self.assertEqual(verify_checked_in_preliminary_gate(REPO_ROOT), [])

    def test_partition_registry_is_disjoint_and_purpose_specific(self):
        owners: dict[int, str] = {}
        for partition in PARTITION_REGISTRY:
            for seed in partition["seeds"]:
                self.assertNotIn(seed, owners)
                owners[seed] = partition["role"]

        self.assertEqual(owners[7101], "detector_calibration")
        self.assertEqual(owners[8101], "attack_development")
        self.assertEqual(owners[9101], "final_evaluation_reserved")

    def test_final_evaluation_partition_is_reserved_and_unreadable(self):
        final = build_preliminary_only_gate().to_dict()["partition_registry"][-1]

        self.assertEqual(final["role"], "final_evaluation_reserved")
        self.assertEqual(final["classification"], "FINAL_SEALED")
        self.assertFalse(final["may_read"])
        self.assertFalse(final["may_influence_design"])
        self.assertFalse(final["may_support_confirmatory_claims"])

    def test_preliminary_permissions_do_not_weaken_final_seals(self):
        gate = build_preliminary_only_gate().to_dict()

        self.assertEqual(gate["preliminary_permissions"], PRELIMINARY_PERMISSIONS)
        self.assertTrue(all(PRELIMINARY_PERMISSIONS.values()))
        self.assertEqual(gate["final_seals"], FINAL_SEALS)
        self.assertTrue(all(value is False for value in FINAL_SEALS.values()))
        self.assertFalse(gate["executes_actions"])

    def test_services_must_already_be_running(self):
        boundary = build_preliminary_only_gate().to_dict()["service_boundary"]

        self.assertEqual(boundary["LLM"]["identity"], LLM_SERVICE_IDENTITY)
        self.assertTrue(boundary["LLM"]["must_already_be_running"])
        self.assertFalse(boundary["LLM"]["start_or_restart_allowed"])
        self.assertEqual(
            boundary["embedding"]["identity"], EMBEDDING_SERVICE_IDENTITY
        )
        self.assertTrue(
            boundary["embedding"]["must_use_existing_project_service"]
        )
        self.assertFalse(boundary["embedding"]["start_or_restart_allowed"])
        self.assertTrue(
            boundary["runtime_components"]
            ["may_start_ephemeral_local_components"]
        )
        self.assertTrue(
            boundary["runtime_components"]["must_record_teardown_status"]
        )
        self.assertFalse(
            boundary["runtime_components"]["physical_field_connection_allowed"]
        )

    def test_valid_runtime_request_is_admitted(self):
        self.assertEqual(validate_preliminary_action_request(request()), [])

    def test_evaluation_seed_and_partition_are_rejected(self):
        issues = validate_preliminary_action_request(request(
            partition_role="final_evaluation_reserved",
            seed=9101,
        ))

        self.assertIn("action_partition_purpose_mismatch", issues)
        self.assertIn("partition_is_sealed", issues)
        self.assertIn("partition_not_preliminary_only", issues)

    def test_seed_must_belong_to_declared_partition(self):
        issues = validate_preliminary_action_request(request(seed=8101))

        self.assertEqual(issues, ["seed_not_registered_for_partition"])

    def test_action_must_match_partition_purpose(self):
        issues = validate_preliminary_action_request(request(
            action_type="threshold_fitting",
            partition_role="attack_development",
            seed=8101,
            paired_benign_id=None,
        ))

        self.assertEqual(issues, ["action_partition_purpose_mismatch"])

    def test_runtime_action_requires_paired_benign_lineage(self):
        issues = validate_preliminary_action_request(request(paired_benign_id=None))

        self.assertEqual(issues, ["paired_benign_lineage_required"])

    def test_output_label_overwrite_and_failure_filtering_are_rejected(self):
        issues = validate_preliminary_action_request(request(
            output_classification="FINAL",
            create_once=False,
            retain_failures=False,
        ))

        self.assertIn("output_not_preliminary_only", issues)
        self.assertIn("output_not_create_once", issues)
        self.assertIn("failure_retention_not_enabled", issues)

    def test_final_access_physical_actuation_and_service_restart_are_rejected(self):
        issues = validate_preliminary_action_request(request(
            final_evaluation_data_accessed=True,
            physical_field_actuator=True,
            starts_or_restarts_service=True,
        ))

        self.assertIn("final_evaluation_access_requested", issues)
        self.assertIn("physical_field_actuation_requested", issues)
        self.assertIn("service_start_or_restart_requested", issues)

    def test_model_and_embedding_requests_bind_existing_service_identity(self):
        llm_request = request(
            action_type="local_LLM_inference",
            partition_role="attack_development",
            seed=8101,
            paired_benign_id=None,
            local_service_identity=LLM_SERVICE_IDENTITY,
        )
        embedding_request = request(
            action_type="embedding_inference",
            partition_role="detector_audit",
            seed=7201,
            paired_benign_id=None,
            local_service_identity=f"{EMBEDDING_SERVICE_IDENTITY}:live-id",
        )

        self.assertEqual(validate_preliminary_action_request(llm_request), [])
        self.assertEqual(
            validate_preliminary_action_request(embedding_request), []
        )
        self.assertIn(
            "LLM_service_identity_mismatch",
            validate_preliminary_action_request(
                {**llm_request, "local_service_identity": "another-model"}
            ),
        )

    def test_hashes_and_closed_request_shape_fail_closed(self):
        self.assertEqual(
            validate_preliminary_action_request(
                {**request(), "manifest_sha256": "bad"}
            ),
            ["invalid_manifest_sha256"],
        )
        extra = request()
        extra["unexpected"] = True
        self.assertEqual(
            validate_preliminary_action_request(extra),
            ["action_request_fields_drift"],
        )

    def test_unaddressed_permission_mutation_breaks_content_address(self):
        payload = build_preliminary_only_gate().to_dict()
        payload["final_seals"]["confirmatory_campaign_execution"] = True

        with self.assertRaisesRegex(ContractViolation, "content address"):
            PreliminaryOnlyGate(payload)

    def test_readdressed_final_unseal_and_partition_overlap_are_rejected(self):
        unsealed = build_preliminary_only_gate().to_dict()
        unsealed["final_seals"]["confirmatory_campaign_execution"] = True
        with self.assertRaisesRegex(ContractViolation, "final_seals"):
            PreliminaryOnlyGate(readdress(unsealed))

        overlap = copy.deepcopy(build_preliminary_only_gate().to_dict())
        overlap["partition_registry"][0]["seeds"][0] = 6101
        with self.assertRaisesRegex(ContractViolation, "partition_registry"):
            PreliminaryOnlyGate(readdress(overlap))

    def test_preflight_is_read_only_and_exposes_no_final_unseal(self):
        exit_code, payload, stderr = run_cli([
            "preliminary-only-preflight",
            "--repo-root",
            str(REPO_ROOT),
        ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["status"], PRELIMINARY_GATE_STATUS)
        self.assertFalse(payload["executes_actions"])
        self.assertEqual(payload["sealed_partition"], "final_evaluation_reserved")
        self.assertTrue(all(value is False for value in payload["final_seals"].values()))
        self.assertEqual(payload["issues"], [])
        self.assertEqual(payload["files_created_or_modified"], 0)
        self.assertEqual(payload["RKA_writes"], 0)

        choices = build_parser()._subparsers._group_actions[0].choices
        self.assertIn("preliminary-only-preflight", choices)
        self.assertNotIn("final-evaluation-unseal", choices)
        self.assertNotIn("confirmatory-campaign-run", choices)


if __name__ == "__main__":
    unittest.main()
