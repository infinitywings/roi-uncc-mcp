from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from g7confirm.budget import DualBudget
from g7confirm.component_matrix import (
    REQUIRED_COMPONENTS,
    component_matrix_sha256,
    load_component_matrix,
    validate_component_matrix,
)
from g7confirm.orchestration_contract import (
    AuthorityProfile,
    CapabilityProfile,
    ContractViolation,
    ControllerDecision,
    DecisionKind,
    InformationLevel,
    KnowledgeAxis,
    KnowledgeProfile,
    NumericParameterSpec,
    OrchestrationRung,
    OutcomeRecord,
    OutcomeStatus,
    ParameterValue,
    PlanAction,
    PlanValidator,
    SideEffectClass,
    StrategyCard,
    StrategyLibrary,
    StrategyStep,
    ToolCallRecord,
    ToolContract,
    ToolSpec,
    TypedObservation,
    TypedPlan,
    assert_capability_parity,
    build_intent_trace,
    summarize_outcomes,
)
from g7confirm.orchestrators import (
    FixedMaximumPowerComparator,
    IA0StaticFrozen,
    IA1LibraryOpenLoop,
    IA2RuleInteractive,
    IA3UCBAdaptive,
    RoutingRule,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FROZEN_SPEC_SHA256 = (
    "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d"
)


def make_library() -> StrategyLibrary:
    scale = (NumericParameterSpec("scale", 0.0, 1.0, 0.3),)
    return StrategyLibrary([
        StrategyCard(
            strategy_id="S_step",
            family="step",
            description="Bounded active-power step.",
            default_actions=(PlanAction("pv1", 30.0, 0.0),),
            eligible_devices=frozenset({"pv1", "pv2"}),
            p_kw_bounds=(0.0, 100.0),
            q_kvar_bounds=(-50.0, 50.0),
            parameter_specs=scale,
        ),
        StrategyCard(
            strategy_id="S_pulse",
            family="pulse",
            description="Bounded active and reactive pulse.",
            default_actions=(PlanAction("pv2", 40.0, 10.0),),
            eligible_devices=frozenset({"pv1", "pv2"}),
            p_kw_bounds=(0.0, 100.0),
            q_kvar_bounds=(-50.0, 50.0),
            parameter_specs=(NumericParameterSpec("duration_windows", 1, 4, 1),),
        ),
        StrategyCard(
            strategy_id="B2a_fixed_maximum_power",
            family="fixed_maximum_power",
            description="Static maximum-power comparator.",
            default_actions=(PlanAction("pv1", 100.0, 0.0),),
            eligible_devices=frozenset({"pv1"}),
            p_kw_bounds=(100.0, 100.0),
            q_kvar_bounds=(0.0, 0.0),
            fixed_maximum_power=True,
        ),
    ])


def make_authority(*, allow_active_power: bool = True,
                   window_cap: int = 3,
                   energy_cap: float = 2.0) -> AuthorityProfile:
    return AuthorityProfile(
        allowed_devices=frozenset({"pv1", "pv2"}),
        allow_active_power=allow_active_power,
        allow_reactive_power=True,
        max_targets_per_plan=2,
        perturbed_window_cap=window_cap,
        apparent_energy_cap_kvah=energy_cap,
        feedback_delay_windows=1,
    )


def make_profile(rung: OrchestrationRung, *,
                 allowed_strategy_ids: frozenset[str] | None = None,
                 authority: AuthorityProfile | None = None,
                 tool_call_cap: int = 3,
                 rollout_cap: int = 1,
                 history_limit: int = 8,
                 candidate_count_cap: int = 64,
                 max_strategies: int = 2) -> CapabilityProfile:
    return CapabilityProfile(
        profile_id=f"profile_{rung.value}",
        rung=rung,
        knowledge=KnowledgeProfile(
            grid=InformationLevel.PARTIAL,
            detector=InformationLevel.NONE,
            training_data=InformationLevel.NONE,
            defense=InformationLevel.NONE,
            feedback=InformationLevel.PARTIAL,
        ),
        authority=authority or make_authority(),
        allowed_strategy_ids=(allowed_strategy_ids or frozenset({
            "S_step", "S_pulse", "B2a_fixed_maximum_power",
        })),
        allowed_tool_names=frozenset({
            "observe_state", "inspect_history", "bounded_rollout",
        }),
        tool_call_cap=tool_call_cap,
        outer_rollout_cap=rollout_cap,
        history_limit=history_limit,
        candidate_count_cap=candidate_count_cap,
        max_strategies_per_plan=max_strategies,
    )


def make_tools() -> ToolContract:
    return ToolContract([
        ToolSpec(
            name="observe_state",
            side_effect_class=SideEffectClass.READ_ONLY_NO_TIME_ADVANCE,
            information_axis=KnowledgeAxis.GRID,
            minimum_information_level=InformationLevel.PARTIAL,
        ),
        ToolSpec(
            name="inspect_history",
            side_effect_class=SideEffectClass.READ_ONLY_NO_TIME_ADVANCE,
            information_axis=KnowledgeAxis.FEEDBACK,
            minimum_information_level=InformationLevel.PARTIAL,
        ),
        ToolSpec(
            name="bounded_rollout",
            side_effect_class=SideEffectClass.OUTER_ROLLOUT_CONSUMING,
            information_axis=KnowledgeAxis.GRID,
            minimum_information_level=InformationLevel.PARTIAL,
        ),
    ])


def make_call(*, rung: OrchestrationRung = OrchestrationRung.IA3,
              name: str = "observe_state",
              side_effect: SideEffectClass = SideEffectClass.READ_ONLY_NO_TIME_ADVANCE,
              returned: InformationLevel = InformationLevel.PARTIAL,
              time_advance: float = 0.0,
              rollout_cost: int = 0,
              call_id: str = "call_1") -> ToolCallRecord:
    return ToolCallRecord(
        call_id=call_id,
        caller_rung=rung,
        tool_name=name,
        input_schema_version="input/v1",
        output_schema_version="output/v1",
        side_effect_class=side_effect,
        simulation_time_advance_s=time_advance,
        outer_rollout_cost=rollout_cost,
        wall_clock_ms=2.5,
        model_tokens=0,
        returned_information_level=returned,
        validation_result="accepted",
    )


def make_validator(profile: CapabilityProfile, *,
                   library: StrategyLibrary | None = None) -> PlanValidator:
    return PlanValidator(
        profile=profile,
        strategy_library=library or make_library(),
        tool_contract=make_tools(),
        dual_budget=DualBudget(
            window_cap=profile.authority.perturbed_window_cap,
            apparent_energy_cap_kvah=profile.authority.apparent_energy_cap_kvah,
            window_seconds=10,
        ),
    )


class ComponentMatrixTests(unittest.TestCase):
    def test_matrix_covers_components_comparators_and_frozen_spec(self):
        matrix = load_component_matrix(
            PACKAGE_ROOT / "artifacts" / "ai_v2_component_matrix.json"
        )
        self.assertEqual(
            {item["id"] for item in matrix["components"]}, REQUIRED_COMPONENTS
        )
        comparator_ids = {item["id"] for item in matrix["comparators"]}
        self.assertIn("B2a_fixed_maximum_power", comparator_ids)
        self.assertIn("IA3_nonllm_adaptive", comparator_ids)
        self.assertEqual(
            matrix["frozen_experiment_spec"]["sha256"], FROZEN_SPEC_SHA256
        )
        self.assertEqual(len(component_matrix_sha256(matrix)), 64)

    def test_matrix_fails_closed_when_a_component_is_removed(self):
        matrix = load_component_matrix(
            PACKAGE_ROOT / "artifacts" / "ai_v2_component_matrix.json"
        )
        invalid = copy.deepcopy(matrix)
        invalid["components"] = [
            item for item in invalid["components"]
            if item["id"] != "diversification_guidance"
        ]
        with self.assertRaisesRegex(ContractViolation, "diversification_guidance"):
            validate_component_matrix(invalid)


class CapabilityAndToolContractTests(unittest.TestCase):
    def test_ia3_and_ia4_parity_excludes_only_decision_core_identity(self):
        ia3 = make_profile(OrchestrationRung.IA3)
        ia4 = make_profile(OrchestrationRung.IA4)
        assert_capability_parity(ia3, ia4)
        self.assertEqual(ia3.parity_fingerprint(), ia4.parity_fingerprint())
        self.assertEqual(
            make_tools().schema_fingerprint(ia3.allowed_tool_names),
            make_tools().schema_fingerprint(ia4.allowed_tool_names),
        )

    def test_parity_fails_on_a_hidden_budget_upgrade(self):
        ia3 = make_profile(OrchestrationRung.IA3, rollout_cap=1)
        ia4 = make_profile(OrchestrationRung.IA4, rollout_cap=2)
        with self.assertRaisesRegex(ContractViolation, "capability parity mismatch"):
            assert_capability_parity(ia3, ia4)

    def test_tool_contract_rejects_hidden_information_and_side_effects(self):
        profile = make_profile(OrchestrationRung.IA3)
        tools = make_tools()
        cases = [
            make_call(name="hidden_tool"),
            make_call(returned=InformationLevel.EXACT),
            make_call(time_advance=1.0),
        ]
        for call in cases:
            with self.subTest(call=call):
                with self.assertRaises(ContractViolation):
                    tools.validate_calls(profile, [call])

    def test_tool_contract_rejects_outer_rollout_overrun(self):
        profile = make_profile(OrchestrationRung.IA3, rollout_cap=1)
        calls = [
            make_call(
                name="bounded_rollout",
                side_effect=SideEffectClass.OUTER_ROLLOUT_CONSUMING,
                rollout_cost=1,
                call_id=f"call_{index}",
            )
            for index in (1, 2)
        ]
        with self.assertRaisesRegex(ContractViolation, "outer_rollout_cap"):
            make_tools().validate_calls(profile, calls)

    def test_invalid_tools_are_rejected_even_when_controller_refuses(self):
        profile = make_profile(OrchestrationRung.IA3)
        outcome = make_validator(profile).evaluate(
            ControllerDecision.refuse("Controller safety refusal."),
            benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
            tool_calls=[make_call(name="hidden_tool")],
        )
        self.assertEqual(outcome.status, OutcomeStatus.CONTRACT_REJECTION)
        self.assertTrue(outcome.safety_refusal)


class PlanValidationTests(unittest.TestCase):
    def test_serialized_plan_matches_declared_schema_surface(self):
        schema = json.loads(
            (PACKAGE_ROOT / "orchestration_plan.schema.json").read_text(
                encoding="utf-8"
            )
        )
        plan = make_library().get("S_step").instantiate(
            OrchestrationRung.IA3, "Serialize the common plan contract."
        ).to_dict()
        self.assertEqual(
            plan["schema_version"],
            schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(set(plan), set(schema["required"]))
        self.assertEqual(
            set(plan["steps"][0]),
            set(schema["$defs"]["strategy_step"]["required"]),
        )

    def test_parameterized_composed_plan_uses_common_validator(self):
        library = make_library()
        profile = make_profile(OrchestrationRung.IA3, max_strategies=2)
        plan = TypedPlan(
            source_rung=OrchestrationRung.IA3,
            steps=(
                StrategyStep(
                    strategy_id="S_step",
                    parameters=(ParameterValue("scale", 0.5),),
                    actions=(PlanAction("pv1", 50.0, 0.0),),
                ),
                StrategyStep(
                    strategy_id="S_pulse",
                    parameters=(ParameterValue("duration_windows", 2),),
                    actions=(PlanAction("pv2", 40.0, 10.0),),
                ),
            ),
            rationale="Compose two bounded strategies.",
        )
        outcome = make_validator(profile, library=library).evaluate(
            ControllerDecision.submit(plan, "typed_strategy_plan"),
            benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
        )
        self.assertEqual(outcome.status, OutcomeStatus.ACCEPTED_EFFECTIVE)
        self.assertEqual(set(outcome.commands), {"pv1", "pv2"})

    def test_card_parameter_and_action_envelopes_fail_closed(self):
        profile = make_profile(OrchestrationRung.IA3)
        bad_parameter = TypedPlan(
            source_rung=OrchestrationRung.IA3,
            steps=(StrategyStep(
                strategy_id="S_step",
                parameters=(ParameterValue("scale", 1.5),),
                actions=(PlanAction("pv1", 50.0, 0.0),),
            ),),
            rationale="Out-of-envelope parameter.",
        )
        bad_action = TypedPlan(
            source_rung=OrchestrationRung.IA3,
            steps=(StrategyStep(
                strategy_id="S_step",
                parameters=(ParameterValue("scale", 0.5),),
                actions=(PlanAction("pv1", 150.0, 0.0),),
            ),),
            rationale="Out-of-envelope action.",
        )
        validator = make_validator(profile)
        benign = {"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)}
        for plan in (bad_parameter, bad_action):
            with self.subTest(plan=plan):
                outcome = validator.evaluate(
                    ControllerDecision.submit(plan, "typed_strategy_plan"),
                    benign=benign,
                )
                self.assertEqual(outcome.status, OutcomeStatus.CONTRACT_REJECTION)

    def test_strategy_composition_cap_is_enforced(self):
        profile = make_profile(OrchestrationRung.IA3, max_strategies=1)
        steps = (
            make_library().get("S_step").default_step(),
            make_library().get("S_pulse").default_step(),
        )
        plan = TypedPlan(
            source_rung=OrchestrationRung.IA3,
            steps=steps,
            rationale="Attempt an unauthorized composition.",
        )
        outcome = make_validator(profile).evaluate(
            ControllerDecision.submit(plan, "typed_strategy_plan"),
            benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
        )
        self.assertEqual(outcome.status, OutcomeStatus.CONTRACT_REJECTION)
        self.assertIn("max_strategies_per_plan", outcome.reason)

    def test_authority_rejection_does_not_spend_budget(self):
        authority = make_authority(allow_active_power=False)
        profile = make_profile(OrchestrationRung.IA3, authority=authority)
        validator = make_validator(profile)
        plan = make_library().get("S_step").instantiate(
            OrchestrationRung.IA3, "Try an unauthorized active-power action."
        )
        outcome = validator.evaluate(
            ControllerDecision.submit(plan, "typed_strategy_plan"),
            benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
        )
        self.assertEqual(outcome.status, OutcomeStatus.CONTRACT_REJECTION)
        self.assertEqual(validator.dual_budget.windows_spent, 0)
        self.assertEqual(validator.dual_budget.energy_spent_kvah, 0.0)

    def test_budget_rejection_is_atomic(self):
        authority = make_authority(window_cap=1, energy_cap=0.01)
        profile = make_profile(OrchestrationRung.IA3, authority=authority)
        validator = make_validator(profile)
        plan = make_library().get("S_step").instantiate(
            OrchestrationRung.IA3, "Exceed the energy cap."
        )
        outcome = validator.evaluate(
            ControllerDecision.submit(plan, "typed_strategy_plan"),
            benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
        )
        self.assertEqual(outcome.status, OutcomeStatus.BUDGET_REJECTION)
        self.assertEqual(validator.dual_budget.windows_spent, 0)
        self.assertEqual(validator.dual_budget.energy_spent_kvah, 0.0)

    def test_refusal_no_action_and_effective_action_are_not_conflated(self):
        profile = make_profile(OrchestrationRung.IA3)
        validator = make_validator(profile)
        benign = {"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)}
        effective_plan = make_library().get("S_step").instantiate(
            OrchestrationRung.IA3, "Effective action."
        )
        benign_plan = make_library().get("S_step").instantiate(
            OrchestrationRung.IA3,
            "Admitted plan equal to benign.",
            parameters=(ParameterValue("scale", 0.0),),
            actions=(PlanAction("pv1", 0.0, 0.0),),
        )
        outcomes = [
            validator.evaluate(
                ControllerDecision.submit(effective_plan, "typed_strategy_plan"),
                benign=benign,
            ),
            validator.evaluate(
                ControllerDecision.submit(benign_plan, "typed_strategy_plan"),
                benign=benign,
            ),
            validator.evaluate(ControllerDecision.refuse("Safety refusal."), benign=benign),
            validator.evaluate(ControllerDecision.no_action("No scheduled action."), benign=benign),
        ]
        metrics = summarize_outcomes(
            outcomes,
            tool_calls=[make_call()],
        )
        self.assertEqual(metrics["decisions"], 4)
        self.assertEqual(metrics["effective_actions"], 1)
        self.assertEqual(metrics["safety_refusals"], 1)
        self.assertEqual(metrics["accepted_decisions"], 3)
        self.assertEqual(metrics["target_diversity"], 1)
        self.assertEqual(metrics["tool_calls"], 1)
        self.assertAlmostEqual(metrics["safety_refusal_rate"], 0.25)
        self.assertAlmostEqual(metrics["effective_action_rate"], 0.25)

    def test_intent_trace_does_not_claim_unobserved_runtime_evidence(self):
        profile = make_profile(OrchestrationRung.IA3)
        decision = ControllerDecision.no_action("No scheduled action.")
        outcome = make_validator(profile).evaluate(
            decision, benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)}
        )
        offline = build_intent_trace(
            profile=profile,
            decision=decision,
            outcome=outcome,
            tool_calls=(),
        )
        runtime = build_intent_trace(
            profile=profile,
            decision=decision,
            outcome=outcome,
            tool_calls=(),
            delivered={},
        )
        self.assertFalse(offline["runtime_evidence"])
        self.assertTrue(runtime["runtime_evidence"])


class ReferenceOrchestratorTests(unittest.TestCase):
    def test_ia0_replays_schedule_without_feedback(self):
        controller = IA0StaticFrozen(
            profile=make_profile(OrchestrationRung.IA0),
            strategy_library=make_library(),
            schedule={2: "S_step"},
        )
        first = controller.decide(
            TypedObservation(2, 20, {"severity": 0.0}),
            [OutcomeRecord(1, "S_pulse", 100.0, OutcomeStatus.ACCEPTED_EFFECTIVE)],
        )
        second = controller.decide(
            TypedObservation(2, 20, {"severity": 1.0}),
            [],
        )
        self.assertEqual(first.plan, second.plan)
        self.assertEqual(
            controller.decide(TypedObservation(3, 30, {}), []).kind,
            DecisionKind.NO_ACTION,
        )

    def test_ia1_never_switches_and_fixed_maximum_is_explicit(self):
        library = make_library()
        profile = make_profile(OrchestrationRung.IA1)
        controller = IA1LibraryOpenLoop(
            profile=profile, strategy_library=library, strategy_id="S_step"
        )
        decisions = [
            controller.decide(TypedObservation(index, index * 10, {"severity": index}), [])
            for index in (0, 1)
        ]
        self.assertEqual({item.plan.strategy_id for item in decisions}, {"S_step"})
        fixed = FixedMaximumPowerComparator(
            profile=profile,
            strategy_library=library,
            strategy_id="B2a_fixed_maximum_power",
        )
        self.assertEqual(
            fixed.decide(TypedObservation(0, 0, {}), []).plan.strategy_id,
            "B2a_fixed_maximum_power",
        )
        with self.assertRaisesRegex(ContractViolation, "fixed maximum-power"):
            FixedMaximumPowerComparator(
                profile=profile, strategy_library=library, strategy_id="S_step"
            )

    def test_ia2_switches_only_through_frozen_rules(self):
        controller = IA2RuleInteractive(
            profile=make_profile(OrchestrationRung.IA2),
            strategy_library=make_library(),
            rules=(RoutingRule("severity", "gte", 0.5, "S_pulse"),),
            default_strategy_id="S_step",
        )
        low = controller.decide(TypedObservation(0, 0, {"severity": 0.4}), [])
        high = controller.decide(TypedObservation(1, 10, {"severity": 0.5}), [])
        self.assertEqual(low.plan.strategy_id, "S_step")
        self.assertEqual(high.plan.strategy_id, "S_pulse")

    def test_ia3_ucb_is_bounded_and_deterministic(self):
        allowed = frozenset({"S_step", "S_pulse"})
        controller = IA3UCBAdaptive(
            profile=make_profile(
                OrchestrationRung.IA3,
                allowed_strategy_ids=allowed,
                history_limit=4,
            ),
            strategy_library=make_library(),
            exploration_weight=0.0,
        )
        observation = TypedObservation(2, 20, {})
        partial = [
            OutcomeRecord(0, "S_pulse", 1.0, OutcomeStatus.ACCEPTED_EFFECTIVE)
        ]
        self.assertEqual(
            controller.decide(observation, partial).plan.strategy_id, "S_step"
        )
        complete = partial + [
            OutcomeRecord(1, "S_step", 0.0, OutcomeStatus.ACCEPTED_EFFECTIVE)
        ]
        first = controller.decide(observation, complete)
        second = controller.decide(observation, complete)
        self.assertEqual(first, second)
        self.assertEqual(first.plan.strategy_id, "S_pulse")

    def test_all_reference_rungs_emit_the_common_decision_type(self):
        library = make_library()
        observation = TypedObservation(0, 0, {"severity": 0.0})
        controllers = [
            IA0StaticFrozen(
                profile=make_profile(OrchestrationRung.IA0),
                strategy_library=library,
                schedule={0: "S_step"},
            ),
            IA1LibraryOpenLoop(
                profile=make_profile(OrchestrationRung.IA1),
                strategy_library=library,
                strategy_id="S_step",
            ),
            IA2RuleInteractive(
                profile=make_profile(OrchestrationRung.IA2),
                strategy_library=library,
                rules=(),
                default_strategy_id="S_step",
            ),
            IA3UCBAdaptive(
                profile=make_profile(OrchestrationRung.IA3),
                strategy_library=library,
            ),
        ]
        for controller in controllers:
            with self.subTest(controller=type(controller).__name__):
                self.assertIsInstance(controller.decide(observation, []), ControllerDecision)


class FreezeRegressionTests(unittest.TestCase):
    def test_frozen_experiment_spec_bytes_are_unchanged(self):
        digest = hashlib.sha256(
            (PACKAGE_ROOT / "experiment_spec.yaml").read_bytes()
        ).hexdigest()
        self.assertEqual(digest, FROZEN_SPEC_SHA256)


if __name__ == "__main__":
    unittest.main()
