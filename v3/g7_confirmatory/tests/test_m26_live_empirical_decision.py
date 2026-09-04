from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from g7confirm.m26_independent_audit import (
    _check_harness_boundary,
    audit_qualification,
    verify_audit_receipt,
)
from g7confirm.m26_live_empirical_decision import (
    BASE_URL,
    CALL_ID,
    DEVELOPMENT_SEEDS,
    MODEL_ID,
    _new_session,
    _provider_stage_schema,
    build_action_request,
    build_contract,
    build_model_request,
    build_receipt,
    verify_receipt,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ATTEMPT_ROOT = PACKAGE_ROOT / "artifacts" / "m26_live_empirical_attempt1"
SCHEMA_PATH = PACKAGE_ROOT / "m26_live_empirical_decision.schema.json"


def _temporary_contract() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        paths = []
        for seed in DEVELOPMENT_SEEDS:
            path = root / f"action_request_seed{seed}.json"
            path.write_text(
                json.dumps(build_action_request(seed), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            paths.append(path)
        return build_contract(paths)


def _passing_result(contract: dict) -> dict:
    control = contract["matched_IA3_control"]
    consumer = {
        "event": "tool_result",
        "schema_version": "grideval-g7-ia4-tool-result/v1",
        "protocol_id": contract["exact_interface"]["protocol_id"],
        "call_id": CALL_ID,
        "tool_name": "observe_sensitivity",
        "output_schema_version": "sensitivity-result/v1",
        "output": control["consumer_payload"],
        "returned_information_level": "partial",
        "simulation_time_advance_s": 0.0,
        "outer_rollout_cost": 0,
        "wall_clock_ms": 0.0,
    }
    return {
        "status": "passed",
        "execution_status": "completed",
        "error": None,
        "network_requests": 3,
        "model_discovery_requests": 1,
        "completion_requests": 2,
        "adapter_invocations": 1,
        "model_record": {"id": MODEL_ID},
        "requests": [{}, {}],
        "completions": [{}, {}],
        "actual_files_read": [],
        "consumer_tool_result_event": consumer,
        "consumer_payload_sha256": control["consumer_payload_sha256"],
        "expected_target": "DER_B",
        "expected_candidate_id": control["expected_candidate_id"],
        "selected_target": "DER_B",
        "selected_candidate_id": control["expected_candidate_id"],
        "matched_IA3_candidate_agreement": True,
        "validation": {"accepted": True},
        "session_receipt": {
            "state": "terminal",
            "model_transport_used": True,
            "real_local_read_only_adapter_executed": True,
            "synthetic_fixture_injected": False,
            "external_tool_execution_used": False,
            "accounting": {
                "model_turns": 2,
                "tool_calls": 1,
                "outer_rollouts": 0,
                "total_model_tokens": 1,
            },
        },
        "model_transport_used": True,
        "real_local_read_only_adapter_executed": True,
        "synthetic_fixture_injected": False,
        "external_tool_execution_used": False,
        "docker_accessed": False,
        "simulator_accessed": False,
        "embedding_accessed": False,
        "detector_accessed": False,
        "defense_accessed": False,
        "physical_actuator_accessed": False,
        "evaluation_accessed": False,
        "final_evaluation_seeds_accessed": [],
    }


class M26LiveEmpiricalDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _temporary_contract()

    def test_model_endpoint_and_turn_seeds_are_exact(self):
        self.assertEqual(MODEL_ID, "qwen3.6-35b-a3b")
        self.assertEqual(BASE_URL, "http://ccil1s26m8hj6lws:8000/v1")
        self.assertEqual(DEVELOPMENT_SEEDS, (8107, 8108))

    def test_action_requests_pass_M18_and_bind_current_code(self):
        requests = [build_action_request(seed) for seed in DEVELOPMENT_SEEDS]
        self.assertEqual([item["seed"] for item in requests], [8107, 8108])
        self.assertTrue(all(item["retain_failures"] for item in requests))
        self.assertTrue(all(not item["starts_or_restarts_service"] for item in requests))
        self.assertTrue(all(not item["final_evaluation_data_accessed"] for item in requests))

    def test_unregistered_seed_fails_closed(self):
        with self.assertRaisesRegex(Exception, "outside the registered turn pair"):
            build_action_request(9101)

    def test_contract_binds_exact_M25_payload_and_M7_surface(self):
        contract = self.contract
        self.assertTrue(contract["contract_id"].startswith("m26contract_"))
        self.assertEqual(
            contract["exact_interface"]["protocol_id"],
            "m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff",
        )
        self.assertEqual(
            contract["matched_IA3_control"]["consumer_payload_sha256"],
            "c397c90c3240643c75323a166432ea67e1cae94648ec1dff2edbc9564c52d5e8",
        )
        self.assertEqual(contract["matched_IA3_control"]["expected_target"], "DER_B")

    def test_contract_hard_caps_are_one_discovery_two_completions_one_adapter(self):
        self.assertEqual(
            self.contract["hard_caps"],
            {
                "model_discovery_requests": 1,
                "completion_requests": 2,
                "real_local_adapter_invocations": 1,
                "tool_calls": 1,
                "outer_rollouts": 0,
                "simulation_time_advance_s": 0.0,
                "retry_within_attempt": 0,
            },
        )

    def test_contract_opens_only_model_network_and_local_adapter(self):
        access = self.contract["access_boundary"]
        self.assertTrue(access["model_transport_authorized"])
        self.assertTrue(access["network_access_authorized_for_registered_model_only"])
        self.assertTrue(access["real_local_read_only_adapter_authorized"])
        for key, value in access.items():
            if key not in {
                "model_transport_authorized",
                "network_access_authorized_for_registered_model_only",
                "real_local_read_only_adapter_authorized",
            }:
                self.assertFalse(value, key)

    def test_turn_zero_request_is_stage_locked_to_exact_tool_call(self):
        session = _new_session()
        request = build_model_request(session=session, require_tool=True)
        schema = request.chat_payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["properties"]["call_id"], {"const": CALL_ID})
        self.assertEqual(request.chat_payload["seed"], 8107)
        self.assertEqual(request.turn_index, 0)

    def test_terminal_provider_schema_excludes_tool_requests(self):
        session = _new_session()
        response_format = _provider_stage_schema(session, require_tool=False)
        variants = response_format["json_schema"]["schema"]["oneOf"]
        decisions = [item["properties"]["decision"]["const"] for item in variants]
        self.assertEqual(decisions, ["plan", "safety_refusal", "no_action"])

    def test_prompt_names_real_adapter_and_forbids_runtime_inference(self):
        session = _new_session()
        request = build_model_request(session=session, require_tool=True)
        system = request.chat_payload["messages"][0]["content"]
        self.assertIn("local read-only empirical adapter", system)
        self.assertIn("will not run a simulator", system)
        self.assertNotIn("frozen fixture", system)

    def test_passing_receipt_and_mutations_are_fail_closed(self):
        result = _passing_result(self.contract)
        receipt = build_receipt(contract=self.contract, result=result)
        self.assertEqual(verify_receipt(receipt, self.contract), [])
        receipt["embedding_accessed"] = True
        issues = verify_receipt(receipt, self.contract)
        self.assertIn("access_boundary_drift:embedding_accessed", issues)
        self.assertIn("receipt_content_address_drift", issues)

    def test_candidate_mismatch_is_rejected(self):
        result = _passing_result(self.contract)
        result["selected_candidate_id"] = self.contract["exact_interface"][
            "candidate_ids"
        ][0]
        receipt = build_receipt(contract=self.contract, result=result)
        self.assertIn(
            "candidate_agreement_failed", verify_receipt(receipt, self.contract)
        )

    def test_schema_is_strict_at_both_artifact_roots(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(schema["oneOf"]), 2)
        self.assertTrue(all(item["additionalProperties"] is False for item in schema["oneOf"]))
        self.assertEqual(
            schema["oneOf"][0]["properties"]["contract_id"]["pattern"],
            "^m26contract_[0-9a-f]{64}$",
        )

    def test_independent_auditor_does_not_import_execution_harness(self):
        self.assertEqual(_check_harness_boundary(), [])

    def test_checked_in_attempt_passes_primary_and_independent_verification(self):
        self.assertTrue(ATTEMPT_ROOT.is_dir())
        contract = json.loads(
            (ATTEMPT_ROOT / "contract.json").read_text(encoding="utf-8")
        )
        receipt = json.loads(
            (ATTEMPT_ROOT / "receipt.json").read_text(encoding="utf-8")
        )
        audit = json.loads(
            (ATTEMPT_ROOT / "independent_audit_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract, build_contract(tuple(
            ATTEMPT_ROOT / f"action_request_seed{seed}.json"
            for seed in DEVELOPMENT_SEEDS
        )))
        self.assertEqual(verify_receipt(receipt, contract), [])
        self.assertEqual(audit_qualification(ATTEMPT_ROOT), [])
        self.assertEqual(verify_audit_receipt(ATTEMPT_ROOT, audit), [])


if __name__ == "__main__":
    unittest.main()
