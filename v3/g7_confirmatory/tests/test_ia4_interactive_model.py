from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from g7confirm.ia4_interactive_model import (
    M6_OVERLAY_SCHEMA_VERSION,
    M6_REQUEST_SCHEMA_VERSION,
    M6_SMOKE_SCHEMA_VERSION,
    M6ModelOverlay,
    build_default_m6_overlay,
    build_m6_model_request,
    perform_bounded_interactive_model_smoke,
    validate_m6_terminal_receipt,
)
from g7confirm.ia4_smoke_fixture import build_smoke_capability_profile
from g7confirm.ia4_tool_loop import (
    FixtureToolResult,
    IAInteractiveSession,
    InteractiveState,
    M5_TOOL_REQUEST_SCHEMA_VERSION,
)
from g7confirm.model_client import ModelClientError
from g7confirm.orchestration_contract import OrchestrationRung, TypedObservation


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "qwen3.6-35b-a3b"
FROZEN_SPEC_SHA256 = (
    "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"
)


def make_overlay() -> M6ModelOverlay:
    return build_default_m6_overlay(
        model_id=MODEL_ID,
        development_seeds=(8101, 8102),
        timeout_s=120.0,
    )


def make_session(overlay: M6ModelOverlay | None = None) -> IAInteractiveSession:
    active = overlay or make_overlay()
    return IAInteractiveSession(
        protocol=active.protocol,
        profile=build_smoke_capability_profile(OrchestrationRung.IA4),
        observation=TypedObservation(
            0,
            0,
            {
                "context": "synthetic_interface_fixture",
                "prior_alarm": False,
                "voltage_pu": 1.0,
            },
        ),
        history=(),
        decision_core_id=MODEL_ID,
    )


def tool_payload(session: IAInteractiveSession) -> dict:
    return {
        "schema_version": M5_TOOL_REQUEST_SCHEMA_VERSION,
        "protocol_id": session.protocol.protocol_id,
        "base_search_surface_id": (
            session.protocol.adapter.search_surface.search_surface_id
        ),
        "turn_index": 0,
        "decision": "tool_request",
        "call_id": "call_observe_model_0001",
        "tool_name": "observe_state",
        "arguments": {"fields": ["prior_alarm", "voltage_pu"]},
        "rationale": "Request the declared read-only observation.",
    }


def terminal_payload(session: IAInteractiveSession) -> dict:
    return {
        "schema_version": "grideval-g7-ia4-fixture-response/v1",
        "search_surface_id": (
            session.protocol.adapter.search_surface.search_surface_id
        ),
        "decision": "plan",
        "candidate_id": session.protocol.adapter.candidate_library.ids()[0],
        "rationale": "Use the fixture and select one unchanged candidate.",
        "used_tool_call_ids": ["call_observe_model_0001"],
    }


def completion_body(content: str | dict, *, turn: int) -> dict:
    encoded = content if isinstance(content, str) else json.dumps(
        content, separators=(",", ":")
    )
    return {
        "id": f"chatcmpl-m6-fixture-{turn}",
        "object": "chat.completion",
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": encoded},
        }],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "total_tokens": 1100,
        },
    }


class OverlayAndRequestTests(unittest.TestCase):
    def test_overlay_is_content_addressed_and_keeps_every_external_gate_closed(self):
        first = make_overlay()
        second = make_overlay()
        self.assertEqual(first.overlay_id, second.overlay_id)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            first.to_dict()["schema_version"], M6_OVERLAY_SCHEMA_VERSION
        )
        self.assertEqual(first.to_dict()["network_request_cap"], 3)
        self.assertEqual(first.to_dict()["completion_request_cap"], 2)
        self.assertEqual(
            first.to_dict()["tool_call_id"], "call_observe_model_0001"
        )
        self.assertTrue(first.to_dict()["overlay_model_transport_authorized"])
        self.assertFalse(first.to_dict()["tool_execution_authorized"])
        self.assertFalse(first.to_dict()["simulator_access_authorized"])
        self.assertTrue(first.to_dict()["evaluation_sealed"])

    def test_overlay_requires_two_unique_development_seeds(self):
        base = make_overlay()
        for seeds in ((8101,), (8101, 8101)):
            with self.subTest(seeds=seeds):
                with self.assertRaises(ModelClientError):
                    M6ModelOverlay(
                        protocol=base.protocol,
                        model_id=MODEL_ID,
                        development_seeds=seeds,
                    )

    def test_turn_zero_is_tool_only_and_uses_first_seed(self):
        overlay = make_overlay()
        request = build_m6_model_request(
            overlay=overlay,
            session=make_session(overlay),
            require_tool=True,
        )
        self.assertEqual(
            request.to_dict()["schema_version"], M6_REQUEST_SCHEMA_VERSION
        )
        self.assertEqual(request.chat_payload["seed"], 8101)
        self.assertFalse(request.chat_payload["stream"])
        self.assertEqual(request.chat_payload["n"], 1)
        guided = request.chat_payload["response_format"]["json_schema"][
            "schema"
        ]
        variants = guided.get("oneOf", [guided])
        self.assertTrue(variants)
        self.assertEqual(
            {item["properties"]["decision"]["const"] for item in variants},
            {"tool_request"},
        )
        self.assertNotIn(
            "uniqueItems",
            variants[0]["properties"]["arguments"]["properties"]["fields"],
        )
        self.assertEqual(
            variants[0]["properties"]["call_id"]["const"],
            "call_observe_model_0001",
        )

    def test_turn_one_is_terminal_only_and_uses_second_seed(self):
        overlay = make_overlay()
        session = make_session(overlay)
        first = session.next_request()
        session.accept_model_turn(
            request_sha256=first["request_sha256"],
            payload=tool_payload(session),
            model_id=MODEL_ID,
            usage={"prompt_tokens": 0, "completion_tokens": 0,
                   "total_tokens": 0},
        )
        outstanding = session.outstanding_request
        assert outstanding is not None
        session.submit_tool_result(FixtureToolResult.build(
            protocol=overlay.protocol,
            request=outstanding,
            output={
                "schema_version": "observation-result/v1",
                "window": 0,
                "time_s": 0,
                "values": {"prior_alarm": False, "voltage_pu": 0.99},
            },
        ))
        request = build_m6_model_request(
            overlay=overlay,
            session=session,
            require_tool=False,
        )
        self.assertEqual(request.chat_payload["seed"], 8102)
        guided = request.chat_payload["response_format"]["json_schema"][
            "schema"
        ]
        variants = guided.get("oneOf", [guided])
        self.assertEqual(
            {item["properties"]["decision"]["const"] for item in variants},
            {"plan", "safety_refusal", "no_action"},
        )


class BoundedTransportTests(unittest.TestCase):
    @patch("g7confirm.ia4_interactive_model.request_json")
    @patch("g7confirm.ia4_interactive_model.discover_model")
    def test_transport_uses_one_discovery_two_completions_and_one_fixture(
            self, discover, request):
        overlay = make_overlay()
        payload_session = make_session(overlay)
        discover.return_value = {
            "id": MODEL_ID,
            "owned_by": "vllm",
            "root": "fixture/model",
            "max_model_len": 262144,
        }
        request.side_effect = [
            completion_body(tool_payload(payload_session), turn=0),
            completion_body(terminal_payload(payload_session), turn=1),
        ]
        result = perform_bounded_interactive_model_smoke(
            base_url="http://model.local/v1",
            overlay=overlay,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["network_requests"], 3)
        self.assertEqual(result["completion_requests"], 2)
        self.assertEqual(discover.call_count, 1)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result["session_receipt"]["state"], "terminal")
        self.assertEqual(
            result["session_receipt"]["terminal_decision"]["kind"], "plan"
        )
        self.assertIsNotNone(result["injected_tool_result"])
        self.assertFalse(result["tool_execution_used"])
        self.assertFalse(result["simulator_accessed"])

    @patch("g7confirm.ia4_interactive_model.request_json")
    @patch("g7confirm.ia4_interactive_model.discover_model")
    def test_immediate_plan_on_turn_zero_fails_without_a_second_completion(
            self, discover, request):
        overlay = make_overlay()
        session = make_session(overlay)
        discover.return_value = {"id": MODEL_ID}
        immediate = terminal_payload(session)
        immediate["used_tool_call_ids"] = []
        request.return_value = completion_body(immediate, turn=0)
        result = perform_bounded_interactive_model_smoke(
            base_url="http://model.local/v1",
            overlay=overlay,
        )
        self.assertEqual(result["status"], "failed_closed")
        self.assertEqual(result["completion_requests"], 1)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result["session_receipt"]["state"], "failed_closed")
        self.assertIn("turn 0", result["error"])

    @patch("g7confirm.ia4_interactive_model.request_json")
    @patch("g7confirm.ia4_interactive_model.discover_model")
    def test_duplicate_json_on_terminal_turn_is_preserved_as_failed_closed(
            self, discover, request):
        overlay = make_overlay()
        session = make_session(overlay)
        discover.return_value = {"id": MODEL_ID}
        valid = json.dumps(terminal_payload(session), separators=(",", ":"))
        duplicate = valid.replace(
            '"decision":"plan"',
            '"decision":"no_action","decision":"plan"',
        )
        request.side_effect = [
            completion_body(tool_payload(session), turn=0),
            completion_body(duplicate, turn=1),
        ]
        result = perform_bounded_interactive_model_smoke(
            base_url="http://model.local/v1",
            overlay=overlay,
        )
        self.assertEqual(result["status"], "failed_closed")
        self.assertEqual(result["completion_requests"], 2)
        self.assertEqual(len(result["completions"]), 2)
        self.assertIn("duplicate field", result["error"])
        self.assertEqual(result["session_receipt"]["state"], "failed_closed")

    @patch("g7confirm.ia4_interactive_model.discover_model")
    def test_discovery_failure_never_sends_a_completion(self, discover):
        discover.side_effect = ModelClientError("model unavailable")
        result = perform_bounded_interactive_model_smoke(
            base_url="http://model.local/v1",
            overlay=make_overlay(),
        )
        self.assertEqual(result["status"], "failed_closed")
        self.assertEqual(result["network_requests"], 1)
        self.assertEqual(result["completion_requests"], 0)
        self.assertEqual(result["session_receipt"]["state"], "failed_closed")


class CheckedInSmokeTests(unittest.TestCase):
    def test_checked_in_m6_attempts_preserve_failures_and_success(self):
        schema = json.loads(
            (PACKAGE_ROOT / "ia4_interactive_model_smoke.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            M6_SMOKE_SCHEMA_VERSION,
        )
        names = [
            "ia4_interactive_model_smoke_m6_attempt1.json",
            "ia4_interactive_model_smoke_m6_attempt2_compat.json",
            "ia4_interactive_model_smoke_m6_attempt3_fixed_call_id.json",
        ]
        attempts = []
        for name in names:
            artifact = json.loads(
                (PACKAGE_ROOT / "artifacts" / name).read_text(encoding="utf-8")
            )
            self.assertEqual(set(artifact), set(schema["required"]))
            self.assertEqual(artifact["spec_file_sha256"], FROZEN_SPEC_SHA256)
            self.assertFalse(artifact["tool_execution_used"])
            self.assertFalse(artifact["simulator_accessed"])
            self.assertFalse(artifact["detector_accessed"])
            self.assertFalse(artifact["embedding_accessed"])
            attempts.append(artifact)

        self.assertEqual(attempts[0]["status"], "failed_closed")
        self.assertEqual(attempts[0]["completion_requests"], 0)
        self.assertIn("HTTP Error 500", attempts[0]["error"])
        self.assertEqual(attempts[1]["status"], "failed_closed")
        self.assertEqual(attempts[1]["completion_requests"], 1)
        self.assertIn("call_id", attempts[1]["error"])
        passed = attempts[2]
        self.assertEqual(passed["status"], "passed")
        self.assertEqual(passed["network_requests"], 3)
        self.assertEqual(passed["completion_requests"], 2)
        self.assertEqual(passed["session_receipt"]["state"], "terminal")
        self.assertEqual(
            passed["overlay"]["tool_call_id"], "call_observe_model_0001"
        )
        validation = validate_m6_terminal_receipt(
            overlay=make_overlay(),
            receipt=passed["session_receipt"],
        )
        self.assertTrue(validation["valid_plan"])
        self.assertTrue(validation["accepted"])
        self.assertTrue(validation["effective_action"])


if __name__ == "__main__":
    unittest.main()
