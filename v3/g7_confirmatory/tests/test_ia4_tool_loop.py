from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path

from g7confirm.ia4_smoke_fixture import (
    build_m4_smoke_adapter,
    build_smoke_capability_profile,
)
from g7confirm.ia4_tool_loop import (
    IAInteractiveSession,
    InteractiveState,
    FixtureToolResult,
    M5InteractiveProtocol,
    M5_CONTRACT_ARTIFACT_SCHEMA_VERSION,
    M5_EPISODE_RECEIPT_SCHEMA_VERSION,
    M5_MODEL_REQUEST_SCHEMA_VERSION,
    M5_PROTOCOL_SCHEMA_VERSION,
    M5_TOOL_REQUEST_SCHEMA_VERSION,
    MatchedIA3ObserveThenSelect,
    build_m5_contract_artifact,
    build_m5_protocol,
    validate_strict_json_schema,
)
from g7confirm.orchestration_contract import (
    ContractViolation,
    OrchestrationRung,
    TypedObservation,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FROZEN_SPEC_SHA256 = (
    "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"
)


def zero_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def make_session(
        rung: OrchestrationRung = OrchestrationRung.IA4,
        *, protocol: M5InteractiveProtocol | None = None) -> IAInteractiveSession:
    active_protocol = protocol or build_m5_protocol(build_m4_smoke_adapter())
    return IAInteractiveSession(
        protocol=active_protocol,
        profile=build_smoke_capability_profile(rung),
        observation=TypedObservation(
            0,
            0,
            {"context": "synthetic_interface_fixture", "voltage_pu": 1.0},
        ),
        history=(),
        decision_core_id=f"fixture_{rung.value.lower()}",
    )


def valid_tool_payload(session: IAInteractiveSession) -> dict:
    return MatchedIA3ObserveThenSelect().tool_request(session)


def valid_tool_output() -> dict:
    return {
        "schema_version": "observation-result/v1",
        "window": 0,
        "time_s": 0,
        "values": {"prior_alarm": False, "voltage_pu": 0.99},
    }


def accept_tool_request(session: IAInteractiveSession) -> FixtureToolResult:
    request = session.next_request()
    session.accept_model_turn(
        request_sha256=request["request_sha256"],
        payload=valid_tool_payload(session),
        model_id=session.decision_core_id,
        usage=zero_usage(),
    )
    outstanding = session.outstanding_request
    assert outstanding is not None
    return FixtureToolResult.build(
        protocol=session.protocol,
        request=outstanding,
        output=valid_tool_output(),
    )


def advance_after_tool(session: IAInteractiveSession) -> None:
    session.submit_tool_result(accept_tool_request(session))


def valid_terminal_payload(session: IAInteractiveSession, *,
                           decision: str = "plan") -> dict:
    common = {
        "schema_version": "grideval-g7-ia4-fixture-response/v1",
        "search_surface_id": (
            session.protocol.adapter.search_surface.search_surface_id
        ),
        "decision": decision,
        "rationale": "Return a terminal fixture decision.",
        "used_tool_call_ids": [item.call_id for item in session.tool_calls],
    }
    if decision == "plan":
        common["candidate_id"] = (
            session.protocol.adapter.candidate_library.ids()[0]
        )
    return common


def accept_terminal(session: IAInteractiveSession, *,
                    decision: str = "plan") -> None:
    request = session.next_request()
    session.accept_model_turn(
        request_sha256=request["request_sha256"],
        payload=valid_terminal_payload(session, decision=decision),
        model_id=session.decision_core_id,
        usage=zero_usage(),
    )


class ProtocolManifestTests(unittest.TestCase):
    def test_protocol_is_content_addressed_and_preserves_the_m4_surface(self):
        adapter = build_m4_smoke_adapter()
        first = build_m5_protocol(adapter)
        second = build_m5_protocol(adapter)
        self.assertEqual(first.protocol_id, second.protocol_id)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            first.to_dict()["schema_version"], M5_PROTOCOL_SCHEMA_VERSION
        )
        self.assertEqual(
            first.to_dict()["base_search_surface_id"],
            adapter.search_surface.search_surface_id,
        )
        self.assertFalse(first.to_dict()["tool_execution_authorized"])
        self.assertFalse(first.to_dict()["model_transport_authorized"])
        self.assertTrue(first.to_dict()["evaluation_sealed"])

    def test_protocol_exposes_exact_read_only_schemas_and_caps(self):
        payload = build_m5_protocol(build_m4_smoke_adapter()).to_dict()
        self.assertEqual(len(payload["enabled_tools"]), 1)
        tool = payload["enabled_tools"][0]
        self.assertEqual(tool["name"], "observe_state")
        self.assertEqual(
            tool["side_effect_class"], "read_only_no_time_advance"
        )
        self.assertEqual(tool["simulation_time_advance_s"], 0.0)
        self.assertEqual(tool["outer_rollout_cost"], 0)
        self.assertFalse(tool["input_schema"]["additionalProperties"])
        self.assertFalse(tool["output_schema"]["additionalProperties"])
        self.assertEqual(payload["episode_caps"]["outer_rollouts"], 0)

    def test_protocol_rejects_a_cap_that_leaves_no_terminal_turn(self):
        base = build_m5_protocol(build_m4_smoke_adapter())
        with self.assertRaisesRegex(ContractViolation, "terminal model turn"):
            M5InteractiveProtocol(
                adapter=base.adapter,
                tool_definitions=base.tool_definitions,
                max_model_turns=1,
                max_tool_calls=1,
            )


class StrictSchemaTests(unittest.TestCase):
    def test_small_schema_validator_accepts_exact_tool_arguments(self):
        definition = build_m5_protocol(
            build_m4_smoke_adapter()
        ).tool("observe_state")
        validate_strict_json_schema(
            {"fields": ["prior_alarm", "voltage_pu"]},
            definition.input_schema,
        )

    def test_small_schema_validator_rejects_extra_duplicate_and_nonfinite(self):
        definition = build_m5_protocol(
            build_m4_smoke_adapter()
        ).tool("observe_state")
        bad = [
            {"fields": ["voltage_pu"], "extra": True},
            {"fields": ["voltage_pu", "voltage_pu"]},
            {"fields": ["detector_threshold"]},
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ContractViolation):
                    validate_strict_json_schema(value, definition.input_schema)
        output = valid_tool_output()
        output["values"]["voltage_pu"] = float("nan")
        with self.assertRaises(ContractViolation):
            validate_strict_json_schema(output, definition.output_schema)

    def test_small_schema_validator_rejects_unknown_keywords(self):
        with self.assertRaisesRegex(ContractViolation, "unsupported"):
            validate_strict_json_schema("x", {"type": "string", "format": "x"})


class InteractiveLifecycleTests(unittest.TestCase):
    def test_receipt_transport_provenance_is_overlay_supplied(self):
        session = make_session()
        advance_after_tool(session)
        accept_terminal(session)
        self.assertFalse(session.receipt()["model_transport_used"])
        self.assertTrue(
            session.receipt(model_transport_used=True)["model_transport_used"]
        )
        with self.assertRaises(ContractViolation):
            session.receipt(model_transport_used=1)

    def test_request_is_deterministic_surface_bound_and_rung_explicit(self):
        session = make_session()
        first = session.next_request()
        second = session.next_request()
        self.assertEqual(first, second)
        self.assertEqual(
            first["schema_version"], M5_MODEL_REQUEST_SCHEMA_VERSION
        )
        self.assertEqual(first["actor_rung"], "IA4")
        self.assertEqual(
            first["request_sha256"],
            hashlib.sha256(
                json.dumps(
                    {key: value for key, value in first.items()
                     if key != "request_sha256"},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )
        variants = first["response_schema"]["oneOf"]
        self.assertEqual(variants[0]["properties"]["decision"]["const"],
                         "tool_request")

    def test_valid_tool_then_plan_reaches_terminal_with_complete_lineage(self):
        session = make_session()
        advance_after_tool(session)
        self.assertEqual(session.state, InteractiveState.AWAITING_MODEL)
        accept_terminal(session)
        self.assertEqual(session.state, InteractiveState.TERMINAL)
        receipt = session.receipt()
        self.assertEqual(
            receipt["schema_version"], M5_EPISODE_RECEIPT_SCHEMA_VERSION
        )
        self.assertEqual(receipt["accounting"]["model_turns"], 2)
        self.assertEqual(receipt["accounting"]["tool_calls"], 1)
        self.assertEqual(receipt["accounting"]["outer_rollouts"], 0)
        self.assertEqual(receipt["terminal_decision"]["kind"], "plan")
        self.assertFalse(receipt["tool_execution_used"])

    def test_same_lifecycle_is_valid_for_matched_ia3(self):
        session = make_session(OrchestrationRung.IA3)
        advance_after_tool(session)
        accept_terminal(session)
        self.assertEqual(
            session.terminal_decision.plan.source_rung,
            OrchestrationRung.IA3,
        )
        self.assertEqual(session.tool_calls[0].caller_rung, OrchestrationRung.IA3)

    def test_safety_refusal_and_no_action_are_terminal(self):
        for decision in ("safety_refusal", "no_action"):
            with self.subTest(decision=decision):
                session = make_session()
                accept_terminal(session, decision=decision)
                self.assertEqual(session.state, InteractiveState.TERMINAL)
                self.assertEqual(
                    session.terminal_decision.kind.value,
                    decision,
                )

    def test_terminal_state_is_immutable(self):
        session = make_session()
        accept_terminal(session)
        with self.assertRaisesRegex(ContractViolation, "session state"):
            session.next_request()
        with self.assertRaisesRegex(ContractViolation, "session state"):
            session.accept_model_turn(
                request_sha256="0" * 64,
                payload={},
                model_id="fixture",
                usage=zero_usage(),
            )
        self.assertEqual(session.state, InteractiveState.TERMINAL)

    def test_tool_result_before_request_fails_closed(self):
        session = make_session()
        other = make_session()
        result = accept_tool_request(other)
        with self.assertRaisesRegex(ContractViolation, "session state"):
            session.submit_tool_result(result)
        self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)


class FailClosedTests(unittest.TestCase):
    def assert_failed_model_payload(self, change) -> IAInteractiveSession:
        session = make_session()
        request = session.next_request()
        payload = valid_tool_payload(session)
        change(payload)
        with self.assertRaises(ContractViolation):
            session.accept_model_turn(
                request_sha256=request["request_sha256"],
                payload=payload,
                model_id="fixture",
                usage=zero_usage(),
            )
        self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)
        self.assertEqual(session.model_turn_count, 1)
        return session

    def test_extra_field_and_invalid_call_id_fail_closed(self):
        self.assert_failed_model_payload(lambda payload: payload.update(extra=True))
        self.assert_failed_model_payload(
            lambda payload: payload.update(call_id="bad-call-id")
        )

    def test_unknown_tool_and_excess_information_request_fail_closed(self):
        self.assert_failed_model_payload(
            lambda payload: payload.update(tool_name="bounded_rollout")
        )
        self.assert_failed_model_payload(
            lambda payload: payload["arguments"].update(extra="detector")
        )

    def test_wrong_request_hash_and_invalid_usage_fail_closed(self):
        session = make_session()
        with self.assertRaisesRegex(ContractViolation, "request_sha256"):
            session.accept_model_turn(
                request_sha256="0" * 64,
                payload=valid_tool_payload(session),
                model_id="fixture",
                usage=zero_usage(),
            )
        self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)

        session = make_session()
        request = session.next_request()
        with self.assertRaisesRegex(ContractViolation, "inconsistent"):
            session.accept_model_turn(
                request_sha256=request["request_sha256"],
                payload=valid_tool_payload(session),
                model_id="fixture",
                usage={"prompt_tokens": 2, "completion_tokens": 2,
                       "total_tokens": 5},
            )
        self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)

    def test_wrong_tool_result_identity_and_lineage_fail_closed(self):
        session = make_session()
        result = accept_tool_request(session)
        with self.assertRaisesRegex(ContractViolation, "call_id"):
            session.submit_tool_result(replace(result, call_id="call_other"))
        self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)

        session = make_session()
        result = accept_tool_request(session)
        with self.assertRaisesRegex(ContractViolation, "lineage"):
            session.submit_tool_result(
                replace(result, source_fixture_id="fixture_00000000000000000000")
            )
        self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)

    def test_tool_result_cannot_advance_time_or_consume_rollout(self):
        for field, value, message in (
            ("simulation_time_advance_s", 1.0, "advanced simulation time"),
            ("outer_rollout_cost", 1, "outer rollout"),
        ):
            with self.subTest(field=field):
                session = make_session()
                result = accept_tool_request(session)
                with self.assertRaisesRegex(ContractViolation, message):
                    session.submit_tool_result(replace(result, **{field: value}))
                self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)

    def test_terminal_response_requires_exact_tool_lineage_and_candidate(self):
        session = make_session()
        advance_after_tool(session)
        request = session.next_request()
        payload = valid_terminal_payload(session)
        payload["used_tool_call_ids"] = []
        with self.assertRaisesRegex(ContractViolation, "lineage"):
            session.accept_model_turn(
                request_sha256=request["request_sha256"],
                payload=payload,
                model_id="fixture",
                usage=zero_usage(),
            )
        self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)

        session = make_session()
        request = session.next_request()
        payload = valid_terminal_payload(session)
        payload["candidate_id"] = "cand_00000000000000000000"
        with self.assertRaisesRegex(ContractViolation, "unknown candidate"):
            session.accept_model_turn(
                request_sha256=request["request_sha256"],
                payload=payload,
                model_id="fixture",
                usage=zero_usage(),
            )

    def test_second_tool_request_exceeds_the_protocol_cap(self):
        session = make_session()
        advance_after_tool(session)
        request = session.next_request()
        payload = valid_tool_payload(session)
        payload["call_id"] = "call_observe_0002"
        with self.assertRaisesRegex(ContractViolation, "tool call cap"):
            session.accept_model_turn(
                request_sha256=request["request_sha256"],
                payload=payload,
                model_id="fixture",
                usage=zero_usage(),
            )
        self.assertEqual(session.state, InteractiveState.FAILED_CLOSED)


class ArtifactTests(unittest.TestCase):
    def test_artifact_has_matched_ia3_and_ia4_fixture_receipts(self):
        artifact = build_m5_contract_artifact(
            adapter=build_m4_smoke_adapter(),
            spec_file_sha256=FROZEN_SPEC_SHA256,
        )
        self.assertEqual(
            artifact["schema_version"], M5_CONTRACT_ARTIFACT_SCHEMA_VERSION
        )
        self.assertEqual(artifact["status"], "passed")
        self.assertTrue(all(artifact["parity_assertions"].values()))
        self.assertFalse(artifact["model_transport_used"])
        self.assertFalse(artifact["tool_execution_used"])
        self.assertTrue(artifact["evaluation_sealed"])
        for episode in artifact["episodes"].values():
            self.assertTrue(episode["plan_validation"]["accepted"])
            self.assertTrue(episode["plan_validation"]["effective_action"])

    def test_checked_in_artifact_matches_the_frozen_schema_and_spec(self):
        schema = json.loads(
            (PACKAGE_ROOT / "ia4_interactive_contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        artifact = json.loads(
            (PACKAGE_ROOT / "artifacts" / "ia4_interactive_contract_m5.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(set(artifact), set(schema["required"]))
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            M5_CONTRACT_ARTIFACT_SCHEMA_VERSION,
        )
        self.assertEqual(artifact["spec_file_sha256"], FROZEN_SPEC_SHA256)
        self.assertTrue(all(artifact["parity_assertions"].values()))
        self.assertFalse(artifact["campaign_authorized"])
        self.assertTrue(artifact["evaluation_sealed"])


if __name__ == "__main__":
    unittest.main()
