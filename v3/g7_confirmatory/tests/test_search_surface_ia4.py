from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from g7confirm.budget import DualBudget
from g7confirm.candidates import (
    CandidateLibrary,
    CandidateRewardSpec,
    CandidateTemplate,
)
from g7confirm.ia4_adapter import (
    IA4FixtureAdapter,
    IA4_REQUEST_SCHEMA_VERSION,
    IA4_RESPONSE_SCHEMA_VERSION,
)
from g7confirm.orchestration_contract import (
    OBSERVATION_SCHEMA_VERSION,
    OUTCOME_SCHEMA_VERSION,
    AuthorityProfile,
    CapabilityProfile,
    ContractViolation,
    InformationLevel,
    KnowledgeAxis,
    KnowledgeProfile,
    NumericParameterSpec,
    OrchestrationRung,
    OutcomeRecord,
    OutcomeStatus,
    PlanAction,
    PlanValidator,
    SideEffectClass,
    StrategyCard,
    StrategyLibrary,
    ToolCallRecord,
    ToolContract,
    ToolSpec,
    TypedObservation,
    build_intent_trace,
)
from g7confirm.orchestrators import IA3CandidateUCBAdaptive
from g7confirm.search_surface import (
    SEARCH_SURFACE_SCHEMA_VERSION,
    SearchSurfaceManifest,
    assert_search_surface_parity,
    build_search_surface,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
FROZEN_SPEC_SHA256 = (
    "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"
)


def make_library() -> StrategyLibrary:
    return StrategyLibrary([
        StrategyCard(
            strategy_id="S_step",
            family="step",
            description="Bounded step strategy.",
            default_actions=(PlanAction("pv1", 30.0, 0.0),),
            eligible_devices=frozenset({"pv1", "pv2"}),
            p_kw_bounds=(0.0, 100.0),
            q_kvar_bounds=(0.0, 0.0),
            parameter_specs=(NumericParameterSpec("scale", 0.0, 1.0, 0.5),),
        ),
        StrategyCard(
            strategy_id="S_pulse",
            family="pulse",
            description="Bounded pulse strategy.",
            default_actions=(PlanAction("pv2", 50.0, 0.0),),
            eligible_devices=frozenset({"pv1", "pv2"}),
            p_kw_bounds=(0.0, 100.0),
            q_kvar_bounds=(0.0, 0.0),
            parameter_specs=(
                NumericParameterSpec("duration_windows", 1.0, 2.0, 1.0),
            ),
        ),
    ])


def make_candidates() -> CandidateLibrary:
    library = make_library()
    return CandidateLibrary([
        CandidateTemplate(
            steps=(library.get("S_step").default_step(),),
            origins=frozenset({"fixture"}),
        ),
        CandidateTemplate(
            steps=(library.get("S_pulse").default_step(),),
            origins=frozenset({"fixture"}),
        ),
    ])


def make_profile(rung: OrchestrationRung, *, candidate_cap: int = 2,
                 history_limit: int = 2,
                 rollout_cap: int = 1) -> CapabilityProfile:
    return CapabilityProfile(
        profile_id=f"surface_{rung.value}",
        rung=rung,
        knowledge=KnowledgeProfile(
            grid=InformationLevel.PARTIAL,
            feedback=InformationLevel.PARTIAL,
        ),
        authority=AuthorityProfile(
            allowed_devices=frozenset({"pv1", "pv2"}),
            allow_active_power=True,
            allow_reactive_power=False,
            max_targets_per_plan=2,
            perturbed_window_cap=4,
            apparent_energy_cap_kvah=2.0,
            feedback_delay_windows=1,
        ),
        allowed_strategy_ids=frozenset({"S_step", "S_pulse"}),
        allowed_tool_names=frozenset({"observe_state", "bounded_rollout"}),
        tool_call_cap=2,
        outer_rollout_cap=rollout_cap,
        history_limit=history_limit,
        candidate_count_cap=candidate_cap,
        max_strategies_per_plan=1,
    )


def make_tools(*, observation_output: str = "observation-result/v1") -> ToolContract:
    return ToolContract([
        ToolSpec(
            name="observe_state",
            side_effect_class=SideEffectClass.READ_ONLY_NO_TIME_ADVANCE,
            information_axis=KnowledgeAxis.GRID,
            minimum_information_level=InformationLevel.PARTIAL,
            input_schema_version="observation-query/v1",
            output_schema_version=observation_output,
        ),
        ToolSpec(
            name="bounded_rollout",
            side_effect_class=SideEffectClass.OUTER_ROLLOUT_CONSUMING,
            information_axis=KnowledgeAxis.GRID,
            minimum_information_level=InformationLevel.PARTIAL,
            input_schema_version="rollout-query/v1",
            output_schema_version="rollout-result/v1",
        ),
    ])


def make_reward(*, direction: str = "maximize") -> CandidateRewardSpec:
    return CandidateRewardSpec(
        metric_name="paired_pre_alarm_harm",
        minimum=0.0,
        maximum=2.0,
        direction=direction,
    )


def make_surface(rung: OrchestrationRung = OrchestrationRung.IA4, **kwargs):
    return build_search_surface(
        profile=kwargs.get("profile", make_profile(rung)),
        strategy_library=kwargs.get("strategy_library", make_library()),
        candidate_library=kwargs.get("candidate_library", make_candidates()),
        reward_spec=kwargs.get("reward_spec", make_reward()),
        tool_contract=kwargs.get("tool_contract", make_tools()),
    )


def make_adapter() -> IA4FixtureAdapter:
    return IA4FixtureAdapter(
        profile=make_profile(OrchestrationRung.IA4),
        strategy_library=make_library(),
        candidate_library=make_candidates(),
        reward_spec=make_reward(),
        tool_contract=make_tools(),
        search_surface=make_surface(OrchestrationRung.IA3),
    )


def make_call(**overrides) -> ToolCallRecord:
    values = {
        "call_id": "call_observe_1",
        "caller_rung": OrchestrationRung.IA4,
        "tool_name": "observe_state",
        "input_schema_version": "observation-query/v1",
        "output_schema_version": "observation-result/v1",
        "side_effect_class": SideEffectClass.READ_ONLY_NO_TIME_ADVANCE,
        "simulation_time_advance_s": 0.0,
        "outer_rollout_cost": 0,
        "wall_clock_ms": 1.0,
        "model_tokens": 0,
        "returned_information_level": InformationLevel.PARTIAL,
        "validation_result": "accepted",
    }
    values.update(overrides)
    return ToolCallRecord(**values)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class SearchSurfaceTests(unittest.TestCase):
    def test_ia3_and_ia4_share_one_content_addressed_surface(self):
        ia3 = make_surface(OrchestrationRung.IA3)
        ia4 = make_surface(OrchestrationRung.IA4)
        assert_search_surface_parity(ia3, ia4)
        self.assertEqual(ia3.to_dict(), ia4.to_dict())
        self.assertEqual(
            ia3.search_surface_id,
            "surface_0d0fefaf0d4f178e4c8bf30a3c5907b2cf714cad5c45748edc2dde9e28671946",
        )
        self.assertEqual(ia3.to_dict()["participant_rungs"], ["IA3", "IA4"])

    def test_surface_rejects_candidate_order_and_capability_drift(self):
        baseline = make_surface()
        reordered = make_surface(
            candidate_library=CandidateLibrary(reversed(make_candidates().candidates))
        )
        changed_cap = make_surface(
            profile=make_profile(OrchestrationRung.IA4, candidate_cap=3)
        )
        for changed in (reordered, changed_cap):
            with self.subTest(changed=changed.search_surface_id):
                with self.assertRaisesRegex(ContractViolation, "parity mismatch"):
                    assert_search_surface_parity(baseline, changed)

    def test_surface_rejects_reward_and_tool_schema_drift(self):
        baseline = make_surface()
        changed_reward = make_surface(reward_spec=make_reward(direction="minimize"))
        changed_tools = make_surface(
            tool_contract=make_tools(observation_output="observation-result/v2")
        )
        for changed in (changed_reward, changed_tools):
            with self.subTest(changed=changed.search_surface_id):
                with self.assertRaisesRegex(ContractViolation, "parity mismatch"):
                    assert_search_surface_parity(baseline, changed)

    def test_surface_is_immutable_from_caller_mutation(self):
        content = make_surface().content_dict()
        manifest = SearchSurfaceManifest(content)
        original_id = manifest.search_surface_id
        content["capability"]["payload"]["tool_call_cap"] = 999
        self.assertEqual(manifest.search_surface_id, original_id)
        self.assertNotEqual(
            manifest.content_dict()["capability"]["payload"]["tool_call_cap"],
            999,
        )

    def test_checked_in_contract_and_schema_keep_the_phase_sealed(self):
        artifact = json.loads(
            (PACKAGE_ROOT / "artifacts" / "ia3_ia4_search_surface_contract.json")
            .read_text(encoding="utf-8")
        )
        schema = json.loads(
            (PACKAGE_ROOT / "search_surface.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(artifact["executable"])
        self.assertFalse(artifact["campaign_authorized"])
        self.assertTrue(artifact["evaluation_sealed"])
        self.assertEqual(
            artifact["frozen_experiment_spec"]["sha256"], FROZEN_SPEC_SHA256
        )
        serialized = make_surface().to_dict()
        self.assertEqual(set(serialized), set(schema["required"]))
        self.assertEqual(
            serialized["schema_version"],
            schema["properties"]["schema_version"]["const"],
        )


class IA4FixtureAdapterTests(unittest.TestCase):
    def test_request_is_deterministic_bounded_and_feedback_delayed(self):
        adapter = make_adapter()
        first_id, second_id = make_candidates().ids()
        history = [
            OutcomeRecord(0, "S_step", 0.2, OutcomeStatus.ACCEPTED_EFFECTIVE,
                          first_id),
            OutcomeRecord(1, "S_pulse", 0.4, OutcomeStatus.ACCEPTED_EFFECTIVE,
                          second_id),
            OutcomeRecord(2, "S_step", 0.6, OutcomeStatus.ACCEPTED_EFFECTIVE,
                          first_id),
            OutcomeRecord(3, "S_pulse", 0.8, OutcomeStatus.ACCEPTED_EFFECTIVE,
                          second_id),
        ]
        observation = TypedObservation(3, 30, {"voltage_pu": 0.98})
        first = adapter.build_request(observation, history)
        second = adapter.build_request(observation, history)
        self.assertEqual(first, second)
        self.assertEqual([item["window"] for item in first["visible_history"]], [1, 2])
        self.assertEqual(
            first["search_surface"]["candidate_library"]["ordered_candidate_ids"],
            list(make_candidates().ids()),
        )
        self.assertEqual(
            [item["name"] for item in first["search_surface"]["tools"]["specs"]],
            ["bounded_rollout", "observe_state"],
        )
        self.assertNotIn("model", first)
        self.assertNotIn("endpoint", first)

    def test_request_rejects_reordered_or_forged_history(self):
        adapter = make_adapter()
        first_id, second_id = make_candidates().ids()
        reordered = [
            OutcomeRecord(1, "S_pulse", 0.2, OutcomeStatus.ACCEPTED_EFFECTIVE,
                          second_id),
            OutcomeRecord(0, "S_step", 0.2, OutcomeStatus.ACCEPTED_EFFECTIVE,
                          first_id),
        ]
        with self.assertRaisesRegex(ContractViolation, "non-decreasing"):
            adapter.build_request(TypedObservation(3, 30, {}), reordered)
        forged = [OutcomeRecord(
            0, "S_pulse", 0.2, OutcomeStatus.ACCEPTED_EFFECTIVE, first_id
        )]
        with self.assertRaisesRegex(ContractViolation, "strategy_id"):
            adapter.build_request(TypedObservation(3, 30, {}), forged)

    def test_plan_fixture_survives_common_validation_and_trace(self):
        adapter = make_adapter()
        call = make_call()
        result = adapter.parse_fixture_response(
            load_fixture("ia4_plan_response.json"), tool_calls=(call,)
        )
        self.assertEqual(result.decision.plan.source_rung, OrchestrationRung.IA4)
        self.assertEqual(
            result.decision.candidate_id, "cand_e44f7c76d885ef0b23ee"
        )
        validator = PlanValidator(
            profile=adapter.profile,
            strategy_library=make_library(),
            tool_contract=make_tools(),
            dual_budget=DualBudget(
                window_cap=4,
                apparent_energy_cap_kvah=2.0,
                window_seconds=10,
            ),
        )
        outcome = validator.evaluate(
            result.decision,
            benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
            tool_calls=result.validated_tool_calls,
        )
        trace = build_intent_trace(
            profile=adapter.profile,
            decision=result.decision,
            outcome=outcome,
            tool_calls=result.validated_tool_calls,
        )
        self.assertEqual(outcome.status, OutcomeStatus.ACCEPTED_EFFECTIVE)
        self.assertEqual(trace["candidate_id"], result.decision.candidate_id)
        self.assertFalse(trace["runtime_evidence"])
        self.assertEqual(len(result.response_fingerprint), 64)

    def test_refusal_and_no_action_remain_distinct(self):
        adapter = make_adapter()
        refusal = adapter.parse_fixture_response(
            load_fixture("ia4_refusal_response.json")
        )
        no_action = adapter.parse_fixture_response(
            load_fixture("ia4_no_action_response.json")
        )
        self.assertEqual(refusal.decision.kind.value, "safety_refusal")
        self.assertEqual(no_action.decision.kind.value, "no_action")
        self.assertIsNone(refusal.decision.plan)
        self.assertIsNone(no_action.decision.candidate_id)

    def test_response_rejects_extra_fields_wrong_surface_and_blank_rationale(self):
        adapter = make_adapter()
        baseline = load_fixture("ia4_no_action_response.json")
        cases = []
        extra = copy.deepcopy(baseline)
        extra["hidden"] = True
        cases.append(extra)
        wrong_surface = copy.deepcopy(baseline)
        wrong_surface["search_surface_id"] = "surface_" + "0" * 64
        cases.append(wrong_surface)
        blank = copy.deepcopy(baseline)
        blank["rationale"] = "   "
        cases.append(blank)
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ContractViolation):
                    adapter.parse_fixture_response(payload)

    def test_response_rejects_unknown_candidate_and_wrong_schema(self):
        adapter = make_adapter()
        payload = load_fixture("ia4_plan_response.json")
        payload["candidate_id"] = "cand_00000000000000000000"
        with self.assertRaisesRegex(ContractViolation, "unknown candidate"):
            adapter.parse_fixture_response(payload, tool_calls=(make_call(),))
        payload = load_fixture("ia4_no_action_response.json")
        payload["schema_version"] = "grideval-g7-ia4-fixture-response/v2"
        with self.assertRaisesRegex(ContractViolation, "schema_version"):
            adapter.parse_fixture_response(payload)

    def test_response_binds_exact_ordered_tool_call_lineage(self):
        adapter = make_adapter()
        payload = load_fixture("ia4_plan_response.json")
        payload["used_tool_call_ids"] = ["other_call"]
        with self.assertRaisesRegex(ContractViolation, "do not match"):
            adapter.parse_fixture_response(payload, tool_calls=(make_call(),))
        payload["used_tool_call_ids"] = ["call_observe_1", "call_observe_1"]
        with self.assertRaisesRegex(ContractViolation, "duplicates"):
            adapter.parse_fixture_response(payload, tool_calls=(make_call(),))
        payload["used_tool_call_ids"] = ["call_observe_1"]
        rejected = make_call(validation_result="rejected")
        with self.assertRaisesRegex(ContractViolation, "non-accepted"):
            adapter.parse_fixture_response(payload, tool_calls=(rejected,))

    def test_response_rejects_every_tool_capability_escape(self):
        adapter = make_adapter()
        payload = load_fixture("ia4_plan_response.json")
        cases = [
            make_call(tool_name="hidden_tool"),
            make_call(caller_rung=OrchestrationRung.IA3),
            make_call(input_schema_version="observation-query/v2"),
            make_call(returned_information_level=InformationLevel.EXACT),
            make_call(simulation_time_advance_s=1.0),
            make_call(
                tool_name="bounded_rollout",
                input_schema_version="rollout-query/v1",
                output_schema_version="rollout-result/v1",
                side_effect_class=SideEffectClass.OUTER_ROLLOUT_CONSUMING,
                outer_rollout_cost=2,
            ),
        ]
        for call in cases:
            with self.subTest(call=call):
                with self.assertRaises(ContractViolation):
                    adapter.parse_fixture_response(payload, tool_calls=(call,))

    def test_adapter_rejects_non_ia4_or_surface_drift(self):
        arguments = {
            "strategy_library": make_library(),
            "candidate_library": make_candidates(),
            "reward_spec": make_reward(),
            "tool_contract": make_tools(),
            "search_surface": make_surface(OrchestrationRung.IA3),
        }
        with self.assertRaisesRegex(ContractViolation, "requires an IA4"):
            IA4FixtureAdapter(
                profile=make_profile(OrchestrationRung.IA3), **arguments
            )
        with self.assertRaisesRegex(ContractViolation, "parity mismatch"):
            IA4FixtureAdapter(
                profile=make_profile(OrchestrationRung.IA4, candidate_cap=3),
                **arguments,
            )

    def test_request_and_response_schema_versions_are_checked_in(self):
        request_schema = json.loads(
            (PACKAGE_ROOT / "ia4_request.schema.json").read_text(encoding="utf-8")
        )
        response_schema = json.loads(
            (PACKAGE_ROOT / "ia4_fixture_response.schema.json").read_text(
                encoding="utf-8"
            )
        )
        request = make_adapter().build_request(TypedObservation(0, 0, {}), [])
        self.assertEqual(set(request), set(request_schema["required"]))
        self.assertEqual(
            request_schema["properties"]["schema_version"]["const"],
            IA4_REQUEST_SCHEMA_VERSION,
        )
        self.assertEqual(
            response_schema["$defs"]["common"]["properties"]
            ["schema_version"]["const"],
            IA4_RESPONSE_SCHEMA_VERSION,
        )


class SharedHistoryAndSerializationTests(unittest.TestCase):
    def test_observation_and_outcome_have_versioned_deterministic_payloads(self):
        observation = TypedObservation(2, 20, {"z": 1.0, "a": True})
        outcome = OutcomeRecord(
            1,
            "S_step",
            0.5,
            OutcomeStatus.ACCEPTED_EFFECTIVE,
            make_candidates().ids()[0],
        )
        self.assertEqual(observation.to_dict()["schema_version"], OBSERVATION_SCHEMA_VERSION)
        self.assertEqual(outcome.to_dict()["schema_version"], OUTCOME_SCHEMA_VERSION)
        self.assertEqual(list(observation.to_dict()["values"]), ["a", "z"])

    def test_ia3_applies_the_same_feedback_delay(self):
        candidates = make_candidates()
        controller = IA3CandidateUCBAdaptive(
            profile=make_profile(OrchestrationRung.IA3),
            strategy_library=make_library(),
            candidate_library=candidates,
            reward_spec=make_reward(),
            exploration_weight=0.0,
        )
        first_id, second_id = candidates.ids()
        history = [
            OutcomeRecord(0, "S_step", 2.0, OutcomeStatus.ACCEPTED_EFFECTIVE,
                          first_id),
            OutcomeRecord(2, "S_pulse", 0.0, OutcomeStatus.ACCEPTED_EFFECTIVE,
                          second_id),
        ]
        selected = controller.decide(TypedObservation(2, 20, {}), history)
        self.assertEqual(selected.candidate_id, second_id)

    def test_frozen_spec_bytes_remain_unchanged(self):
        digest = hashlib.sha256(
            (PACKAGE_ROOT / "experiment_spec.yaml").read_bytes()
        ).hexdigest()
        self.assertEqual(digest, FROZEN_SPEC_SHA256)
