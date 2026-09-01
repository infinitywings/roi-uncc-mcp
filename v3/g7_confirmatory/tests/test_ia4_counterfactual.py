from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from g7confirm.ia4_counterfactual import (
    M7_CONTRACT_SCHEMA_VERSION,
    M7_METRIC,
    M7_SMOKE_SCHEMA_VERSION,
    M7_TOOL_NAME,
    M7_TARGETS,
    build_default_m7_overlay,
    build_m7_contract_artifact,
    build_m7_model_request,
    perform_m7_counterfactual_model_smoke,
    run_matched_ia3_condition,
    validate_m7_contract_artifact,
)
from g7confirm.ia4_tool_loop import IAInteractiveSession
from g7confirm.model_client import ModelClientError
from g7confirm.orchestration_contract import (
    ContractViolation,
    OrchestrationRung,
    TypedObservation,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "qwen3.6-35b-a3b"
FROZEN_SPEC_SHA256 = (
    "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"
)


def make_overlay():
    return build_default_m7_overlay(
        model_id=MODEL_ID,
        development_seeds=(8103, 8104),
        timeout_s=120.0,
    )


def make_session(overlay=None):
    active = overlay or make_overlay()
    return IAInteractiveSession(
        protocol=active.protocol,
        profile=active.protocol.adapter.profile,
        observation=TypedObservation(
            0,
            0,
            {
                "context": "symmetric_counterfactual_fixture",
                "candidate_difference": "target_only",
            },
        ),
        history=(),
        decision_core_id=MODEL_ID,
    )


def tool_payload(session, condition):
    return {
        "schema_version": "grideval-g7-ia4-tool-request/v1",
        "protocol_id": session.protocol.protocol_id,
        "base_search_surface_id": (
            session.protocol.adapter.search_surface.search_surface_id
        ),
        "turn_index": 0,
        "decision": "tool_request",
        "call_id": condition.call_id,
        "tool_name": M7_TOOL_NAME,
        "arguments": {"metric": M7_METRIC, "target_ids": list(M7_TARGETS)},
        "rationale": "Request the declared read-only sensitivity fixture.",
    }


def terminal_payload(session, condition, *, candidate_id=None):
    selected = candidate_id or condition.to_dict(
        session.protocol.adapter
    )["expected_candidate_id"]
    return {
        "schema_version": "grideval-g7-ia4-fixture-response/v1",
        "search_surface_id": (
            session.protocol.adapter.search_surface.search_surface_id
        ),
        "decision": "plan",
        "candidate_id": selected,
        "rationale": "Select the target with the larger computed fixture score.",
        "used_tool_call_ids": [condition.call_id],
    }


def completion_body(content, *, index):
    return {
        "id": f"chatcmpl-m7-fixture-{index}",
        "object": "chat.completion",
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": json.dumps(content, separators=(",", ":")),
            },
        }],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "total_tokens": 1100,
        },
    }


class CounterfactualSurfaceTests(unittest.TestCase):
    def test_candidates_are_symmetric_except_for_target(self):
        adapter = make_overlay().protocol.adapter
        left, right = adapter.candidate_library.candidates
        self.assertNotEqual(left.candidate_id, right.candidate_id)
        self.assertEqual(left.strategy_ids, right.strategy_ids)
        self.assertEqual(left.steps[0].parameters, right.steps[0].parameters)
        self.assertEqual(left.steps[0].actions[0].p_kw, 30.0)
        self.assertEqual(right.steps[0].actions[0].p_kw, 30.0)
        self.assertEqual(left.target_ids, ("DER_A",))
        self.assertEqual(right.target_ids, ("DER_B",))

    def test_protocol_exposes_one_read_only_zero_rollout_tool(self):
        protocol = make_overlay().protocol
        payload = protocol.to_dict()
        self.assertEqual(payload["episode_caps"]["model_turns"], 3)
        self.assertEqual(payload["episode_caps"]["tool_calls"], 1)
        self.assertEqual(payload["episode_caps"]["outer_rollouts"], 0)
        self.assertEqual(len(payload["enabled_tools"]), 1)
        self.assertEqual(payload["enabled_tools"][0]["name"], M7_TOOL_NAME)
        self.assertEqual(
            payload["enabled_tools"][0]["side_effect_class"],
            "read_only_no_time_advance",
        )

    def test_preregistration_binds_mirrored_pair_and_matched_ia3_switch(self):
        overlay = make_overlay()
        artifact = build_m7_contract_artifact(
            overlay=overlay,
            spec_file_sha256=FROZEN_SPEC_SHA256,
        )
        self.assertEqual(artifact["schema_version"], M7_CONTRACT_SCHEMA_VERSION)
        self.assertTrue(artifact["contract_id"].startswith("m7contract_"))
        self.assertEqual(
            [item["selected_target"] for item in artifact["matched_ia3_controls"]],
            ["DER_A", "DER_B"],
        )
        self.assertTrue(all(
            item["validation"]["accepted"]
            for item in artifact["matched_ia3_controls"]
        ))
        validate_m7_contract_artifact(
            artifact=artifact,
            overlay=overlay,
            spec_file_sha256=FROZEN_SPEC_SHA256,
        )
        artifact["conditions"][0]["expected_target"] = "DER_B"
        with self.assertRaises(ContractViolation):
            validate_m7_contract_artifact(
                artifact=artifact,
                overlay=overlay,
                spec_file_sha256=FROZEN_SPEC_SHA256,
            )

    def test_matched_ia3_control_switches_under_fixture_swap(self):
        overlay = make_overlay()
        results = [
            run_matched_ia3_condition(
                protocol=overlay.protocol,
                condition=condition,
            )
            for condition in overlay.conditions
        ]
        self.assertEqual(
            [item["selected_target"] for item in results],
            ["DER_A", "DER_B"],
        )

    def test_condition_gains_cannot_mutate_after_content_addressing(self):
        condition = make_overlay().conditions[0]
        with self.assertRaises(TypeError):
            condition.gains["DER_A"] = 0.0


class CounterfactualRequestTests(unittest.TestCase):
    def test_overlay_reuses_same_two_turn_seeds_across_both_conditions(self):
        overlay = make_overlay()
        payload = overlay.to_dict()
        self.assertEqual(payload["development_seeds"], [8103, 8104])
        self.assertEqual(payload["network_request_cap"], 5)
        self.assertEqual(payload["completion_request_cap"], 4)
        self.assertEqual(
            payload["paired_seed_policy"],
            "reuse_same_turn_seeds_across_conditions",
        )
        self.assertFalse(payload["tool_execution_authorized"])
        self.assertFalse(payload["embedding_access_authorized"])

    def test_turn_zero_is_tool_only_and_call_id_is_harness_owned(self):
        overlay = make_overlay()
        condition = overlay.conditions[0]
        request = build_m7_model_request(
            overlay=overlay,
            condition=condition,
            session=make_session(overlay),
            require_tool=True,
        )
        schema = request.chat_payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["properties"]["decision"]["const"], "tool_request")
        self.assertEqual(
            schema["properties"]["call_id"]["const"], condition.call_id
        )
        self.assertEqual(request.chat_payload["seed"], 8103)


class CounterfactualTransportTests(unittest.TestCase):
    @patch("g7confirm.ia4_counterfactual.request_json")
    @patch("g7confirm.ia4_counterfactual.discover_model")
    def test_correct_mirrored_choices_pass_primary_gate(self, discover, request):
        overlay = make_overlay()
        sessions = [make_session(overlay), make_session(overlay)]
        discover.return_value = {"id": MODEL_ID, "owned_by": "vllm"}
        request.side_effect = [
            completion_body(tool_payload(sessions[0], overlay.conditions[0]), index=0),
            completion_body(terminal_payload(sessions[0], overlay.conditions[0]), index=1),
            completion_body(tool_payload(sessions[1], overlay.conditions[1]), index=2),
            completion_body(terminal_payload(sessions[1], overlay.conditions[1]), index=3),
        ]
        result = perform_m7_counterfactual_model_smoke(
            base_url="http://model.local/v1",
            overlay=overlay,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["network_requests"], 5)
        self.assertEqual(result["completion_requests"], 4)
        self.assertEqual(result["qualification"]["directional_accuracy"], 1.0)
        self.assertTrue(result["qualification"]["candidate_switched"])
        self.assertTrue(result["model_transport_used"])
        self.assertTrue(all(
            item["session_receipt"]["model_transport_used"]
            for item in result["episodes"]
        ))
        self.assertFalse(result["tool_execution_used"])
        self.assertFalse(result["evaluation_accessed"])

    @patch("g7confirm.ia4_counterfactual.request_json")
    @patch("g7confirm.ia4_counterfactual.discover_model")
    def test_first_candidate_bias_completes_but_fails_qualification(
            self, discover, request):
        overlay = make_overlay()
        sessions = [make_session(overlay), make_session(overlay)]
        first_id = overlay.protocol.adapter.candidate_library.ids()[0]
        discover.return_value = {"id": MODEL_ID}
        request.side_effect = [
            completion_body(tool_payload(sessions[0], overlay.conditions[0]), index=0),
            completion_body(terminal_payload(
                sessions[0], overlay.conditions[0], candidate_id=first_id
            ), index=1),
            completion_body(tool_payload(sessions[1], overlay.conditions[1]), index=2),
            completion_body(terminal_payload(
                sessions[1], overlay.conditions[1], candidate_id=first_id
            ), index=3),
        ]
        result = perform_m7_counterfactual_model_smoke(
            base_url="http://model.local/v1",
            overlay=overlay,
        )
        self.assertEqual(result["status"], "failed_qualification")
        self.assertEqual(result["qualification"]["directional_accuracy"], 0.5)
        self.assertFalse(result["qualification"]["candidate_switched"])
        self.assertEqual(request.call_count, 4)

    @patch("g7confirm.ia4_counterfactual.discover_model")
    def test_discovery_failure_sends_no_completion(self, discover):
        discover.side_effect = ModelClientError("model unavailable")
        result = perform_m7_counterfactual_model_smoke(
            base_url="http://model.local/v1",
            overlay=make_overlay(),
        )
        self.assertEqual(result["status"], "failed_closed")
        self.assertEqual(result["network_requests"], 1)
        self.assertEqual(result["completion_requests"], 0)


class CheckedInM7EvidenceTests(unittest.TestCase):
    def test_checked_in_contract_and_smoke_are_bound_and_non_actuating(self):
        contract_path = PACKAGE_ROOT / "artifacts" / "ia4_counterfactual_contract_m7.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        smoke_paths = [
            PACKAGE_ROOT / "artifacts" /
            "ia4_counterfactual_model_smoke_m7_attempt1.json",
            PACKAGE_ROOT / "artifacts" /
            "ia4_counterfactual_model_smoke_m7_attempt2_transport_provenance.json",
        ]
        attempts = [
            json.loads(path.read_text(encoding="utf-8")) for path in smoke_paths
        ]
        contract_schema = json.loads(
            (PACKAGE_ROOT / "ia4_counterfactual_contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        smoke_schema = json.loads(
            (PACKAGE_ROOT / "ia4_counterfactual_model_smoke.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(contract), set(contract_schema["required"]))
        self.assertEqual(contract["schema_version"], M7_CONTRACT_SCHEMA_VERSION)
        self.assertEqual(set(attempts[0]), set(smoke_schema["required"]))
        self.assertEqual(
            set(attempts[1]),
            set(smoke_schema["required"]) | {"model_transport_used"},
        )
        for smoke in attempts:
            self.assertEqual(smoke["schema_version"], M7_SMOKE_SCHEMA_VERSION)
            self.assertEqual(smoke["contract_id"], contract["contract_id"])
            self.assertEqual(smoke["spec_file_sha256"], FROZEN_SPEC_SHA256)
            self.assertEqual(smoke["status"], "passed")
            self.assertEqual(smoke["qualification"]["verdict"], "pass")
            self.assertEqual(
                smoke["qualification"]["directional_accuracy"], 1.0
            )
            self.assertTrue(smoke["qualification"]["candidate_switched"])
            self.assertFalse(smoke["tool_execution_used"])
            self.assertFalse(smoke["simulator_accessed"])
            self.assertFalse(smoke["detector_accessed"])
            self.assertFalse(smoke["embedding_accessed"])
            self.assertFalse(smoke["evaluation_accessed"])
        self.assertNotIn("model_transport_used", attempts[0])
        self.assertEqual(
            [item["session_receipt"]["model_transport_used"]
             for item in attempts[0]["episodes"]],
            [False, False],
        )
        self.assertTrue(attempts[1]["model_transport_used"])
        self.assertEqual(
            [item["session_receipt"]["model_transport_used"]
             for item in attempts[1]["episodes"]],
            [True, True],
        )


if __name__ == "__main__":
    unittest.main()
