from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from g7confirm.ia4_model import (
    IA4_MODEL_REPLAY_SCHEMA_VERSION,
    IA4ModelReplay,
    IA4ModelRequest,
    OpenAICompletionRecord,
    extract_openai_completion,
    ia4_model_response_format,
    perform_bounded_model_smoke,
)
from g7confirm.ia4_smoke_fixture import build_m4_smoke_adapter
from g7confirm.model_client import ModelClientError
from g7confirm.orchestration_contract import (
    ContractViolation,
    OrchestrationRung,
    TypedObservation,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "qwen3.6-35b-a3b"
DEVELOPMENT_SEEDS = (8101, 8102)


def make_replay() -> IA4ModelReplay:
    return IA4ModelReplay(
        adapter=build_m4_smoke_adapter(),
        allowed_development_seeds=DEVELOPMENT_SEEDS,
    )


def make_request():
    return make_replay().build_request(
        observation=TypedObservation(
            0,
            0,
            {"context": "synthetic_interface_fixture", "voltage_pu": 1.0},
        ),
        history=(),
        model_id=MODEL_ID,
        temperature=0.0,
        max_tokens=512,
        seed=8101,
    )


def valid_payload() -> dict:
    adapter = build_m4_smoke_adapter()
    return {
        "schema_version": "grideval-g7-ia4-fixture-response/v1",
        "search_surface_id": adapter.search_surface.search_surface_id,
        "decision": "plan",
        "candidate_id": adapter.candidate_library.ids()[0],
        "rationale": "Select one unchanged candidate from the shared surface.",
        "used_tool_call_ids": [],
    }


def completion_body(*, content: str | None = None) -> dict:
    return {
        "id": "chatcmpl-m4-fixture",
        "object": "chat.completion",
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": content if content is not None else json.dumps(
                    valid_payload(), separators=(",", ":")
                ),
            },
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }


class IA4ModelRequestTests(unittest.TestCase):
    def test_smoke_fixture_preserves_ia3_ia4_surface_and_strategy_content(self):
        adapter = build_m4_smoke_adapter()
        surface = adapter.search_surface.to_dict()
        self.assertEqual(adapter.profile.rung, OrchestrationRung.IA4)
        self.assertEqual(surface["participant_rungs"], ["IA3", "IA4"])
        self.assertEqual(
            set(surface["candidate_library"]["ordered_candidate_ids"]),
            set(adapter.candidate_library.ids()),
        )
        self.assertEqual(
            {item["strategy_id"] for item in surface["strategy_library"]["cards"]},
            {"step_corner", "pulse_intermittent"},
        )

    def test_response_format_is_surface_bound_and_tool_free(self):
        adapter = build_m4_smoke_adapter()
        response_format = ia4_model_response_format(adapter)
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["json_schema"]["strict"])
        variants = response_format["json_schema"]["schema"]["oneOf"]
        plan = variants[0]
        self.assertEqual(
            plan["properties"]["search_surface_id"]["const"],
            adapter.search_surface.search_surface_id,
        )
        self.assertEqual(
            plan["properties"]["candidate_id"]["enum"],
            list(adapter.candidate_library.ids()),
        )
        for variant in variants:
            self.assertEqual(
                variant["properties"]["used_tool_call_ids"]["maxItems"], 0
            )
            self.assertFalse(variant["additionalProperties"])

    def test_model_request_is_deterministic_and_content_addressed(self):
        first = make_request()
        second = make_request()
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(len(first.request_sha256), 64)
        self.assertEqual(first.chat_payload["n"], 1)
        self.assertFalse(first.chat_payload["stream"])
        self.assertFalse(
            first.chat_payload["chat_template_kwargs"]["enable_thinking"]
        )
        self.assertIn(
            first.ia4_request["search_surface_id"],
            first.chat_payload["messages"][1]["content"],
        )
        self.assertTrue(first.ia4_request["task"]["proposal_is_non_actuating"])
        self.assertIn(
            "not your ability to select a candidate",
            first.chat_payload["messages"][0]["content"],
        )

    def test_request_rejects_evaluation_seed_and_unbounded_settings(self):
        replay = make_replay()
        base = {
            "observation": TypedObservation(0, 0, {}),
            "history": (),
            "model_id": MODEL_ID,
            "temperature": 0.0,
            "max_tokens": 512,
            "seed": 8101,
        }
        cases = [
            {"seed": 9101},
            {"temperature": 1.1},
            {"max_tokens": 1001},
        ]
        for change in cases:
            arguments = {**base, **change}
            with self.subTest(change=change):
                with self.assertRaises(ModelClientError):
                    replay.build_request(**arguments)


class CompletionEnvelopeTests(unittest.TestCase):
    def test_exact_completion_envelope_is_replayable(self):
        record = extract_openai_completion(
            completion_body(), expected_model_id=MODEL_ID
        )
        self.assertEqual(record.model_id, MODEL_ID)
        self.assertEqual(record.finish_reason, "stop")
        self.assertEqual(record.usage["total_tokens"], 150)
        self.assertEqual(len(record.response_sha256), 64)

    def test_completion_envelope_rejects_model_choice_finish_and_role_drift(self):
        cases = []
        wrong_model = completion_body()
        wrong_model["model"] = "other-model"
        cases.append(wrong_model)
        multiple = completion_body()
        multiple["choices"].append(copy.deepcopy(multiple["choices"][0]))
        cases.append(multiple)
        wrong_index = completion_body()
        wrong_index["choices"][0]["index"] = 1
        cases.append(wrong_index)
        length = completion_body()
        length["choices"][0]["finish_reason"] = "length"
        cases.append(length)
        wrong_role = completion_body()
        wrong_role["choices"][0]["message"]["role"] = "tool"
        cases.append(wrong_role)
        for body in cases:
            with self.subTest(body=body):
                with self.assertRaises(ModelClientError):
                    extract_openai_completion(body, expected_model_id=MODEL_ID)

    def test_completion_rejects_tool_emission_and_invalid_usage(self):
        tool_call = completion_body()
        tool_call["choices"][0]["message"]["tool_calls"] = [{"id": "call_1"}]
        with self.assertRaisesRegex(ModelClientError, "unauthorized tool"):
            extract_openai_completion(tool_call, expected_model_id=MODEL_ID)
        refusal = completion_body()
        refusal["choices"][0]["message"]["refusal"] = "Cannot comply."
        with self.assertRaisesRegex(ModelClientError, "out-of-contract refusal"):
            extract_openai_completion(refusal, expected_model_id=MODEL_ID)
        invalid_usage = completion_body()
        invalid_usage["usage"]["total_tokens"] = -1
        with self.assertRaisesRegex(ModelClientError, "usage"):
            extract_openai_completion(invalid_usage, expected_model_id=MODEL_ID)


class IA4ModelReplayTests(unittest.TestCase):
    def test_valid_model_content_reaches_the_common_adapter(self):
        replay = make_replay()
        result = replay.replay(make_request(), completion_body())
        self.assertEqual(result.schema_version, IA4_MODEL_REPLAY_SCHEMA_VERSION)
        self.assertEqual(
            result.adapter_result.decision.reason,
            "ia4_model_replay_candidate_selection",
        )
        self.assertEqual(
            result.adapter_result.decision.candidate_id,
            build_m4_smoke_adapter().candidate_library.ids()[0],
        )
        self.assertFalse(result.to_dict()["tool_execution_authorized"])

    def test_replay_requires_one_bare_json_object(self):
        replay = make_replay()
        encoded = json.dumps(valid_payload())
        cases = [
            "analysis\n" + encoded,
            "```json\n" + encoded + "\n```",
            "[]",
            "",
        ]
        for content in cases:
            with self.subTest(content=content):
                with self.assertRaises(ModelClientError):
                    replay.replay(make_request(), completion_body(content=content))

    def test_replay_rejects_duplicate_fields_and_request_mutation(self):
        replay = make_replay()
        encoded = json.dumps(valid_payload(), separators=(",", ":"))
        duplicate = encoded.replace(
            '"decision":"plan"',
            '"decision":"no_action","decision":"plan"',
        )
        with self.assertRaisesRegex(ModelClientError, "duplicate field"):
            replay.replay(
                make_request(), completion_body(content=duplicate)
            )
        request = make_request()
        request.chat_payload["seed"] = 8102
        with self.assertRaisesRegex(ModelClientError, "changed"):
            replay.replay(request, completion_body())

    def test_replay_rejects_tool_ids_and_unknown_candidates(self):
        replay = make_replay()
        with_tool = valid_payload()
        with_tool["used_tool_call_ids"] = ["call_1"]
        with self.assertRaisesRegex(ContractViolation, "does not authorize"):
            replay.replay(
                make_request(), completion_body(content=json.dumps(with_tool))
            )
        unknown = valid_payload()
        unknown["candidate_id"] = "cand_00000000000000000000"
        with self.assertRaisesRegex(ContractViolation, "unknown candidate"):
            replay.replay(
                make_request(), completion_body(content=json.dumps(unknown))
            )

    @patch("g7confirm.ia4_model.request_json")
    @patch("g7confirm.ia4_model.discover_model")
    def test_bounded_transport_performs_one_completion(
            self, discover, request_json):
        discover.return_value = {
            "id": MODEL_ID,
            "owned_by": "vllm",
            "root": "fixture/model",
            "max_model_len": 262144,
        }
        request_json.return_value = completion_body()
        result = perform_bounded_model_smoke(
            make_replay(),
            base_url="http://model.local/v1",
            model_id=MODEL_ID,
            observation=TypedObservation(0, 0, {}),
            history=(),
            temperature=0.0,
            max_tokens=512,
            timeout_s=30.0,
            seed=8101,
        )
        self.assertEqual(result["network_requests"], 2)
        self.assertEqual(result["completion_requests"], 1)
        discover.assert_called_once()
        request_json.assert_called_once()
        self.assertTrue(
            request_json.call_args.args[0].endswith("/chat/completions")
        )

    def test_transport_timeout_is_hard_bounded(self):
        with self.assertRaisesRegex(ModelClientError, "timeout_s"):
            perform_bounded_model_smoke(
                make_replay(),
                base_url="http://model.local/v1",
                model_id=MODEL_ID,
                observation=TypedObservation(0, 0, {}),
                history=(),
                temperature=0.0,
                max_tokens=512,
                timeout_s=181.0,
                seed=8101,
            )

    def test_replay_schema_and_contract_artifact_are_sealed(self):
        schema = json.loads(
            (PACKAGE_ROOT / "ia4_model_replay.schema.json").read_text(
                encoding="utf-8"
            )
        )
        artifact = json.loads(
            (PACKAGE_ROOT / "artifacts" / "ia4_model_parsing_contract.json")
            .read_text(encoding="utf-8")
        )
        serialized = make_replay().replay(
            make_request(), completion_body()
        ).to_dict()
        self.assertEqual(set(serialized), set(schema["required"]))
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            IA4_MODEL_REPLAY_SCHEMA_VERSION,
        )
        self.assertFalse(artifact["campaign_authorized"])
        self.assertTrue(artifact["evaluation_sealed"])
        self.assertEqual(artifact["completion_request_cap"], 1)
        self.assertFalse(artifact["tool_execution_authorized"])

    def test_checked_in_smoke_preserves_the_refusal_anomaly(self):
        schema = json.loads(
            (PACKAGE_ROOT / "ia4_model_smoke.schema.json").read_text(
                encoding="utf-8"
            )
        )
        artifact = json.loads(
            (PACKAGE_ROOT / "artifacts" / "ia4_model_smoke_m4_attempt1.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(set(artifact), set(schema["required"]))
        self.assertEqual(artifact["status"], "passed")
        self.assertEqual(artifact["completion_requests"], 1)
        self.assertEqual(
            artifact["replay"]["adapter_result"]["decision"]["kind"],
            "safety_refusal",
        )
        self.assertEqual(
            artifact["spec_file_sha256"],
            "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d",
        )
        request = IA4ModelRequest(**artifact["request"])
        completion = OpenAICompletionRecord(**artifact["replay"]["completion"])
        replayed = make_replay().replay_record(request, completion)
        self.assertEqual(
            replayed.adapter_result.decision.kind.value,
            "safety_refusal",
        )


if __name__ == "__main__":
    unittest.main()
