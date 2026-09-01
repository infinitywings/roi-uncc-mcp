from __future__ import annotations

import json
import unittest
from pathlib import Path

from g7confirm.budget import DualBudget
from g7confirm.candidates import (
    CandidateGenerationSpec,
    CandidateLibrary,
    CandidateRewardSpec,
    CandidateTemplate,
    assert_candidate_library_parity,
    assert_reward_spec_parity,
    generate_candidate_library,
)
from g7confirm.orchestration_contract import (
    AuthorityProfile,
    CapabilityProfile,
    ContractViolation,
    InformationLevel,
    KnowledgeProfile,
    NumericParameterSpec,
    OrchestrationRung,
    OutcomeRecord,
    OutcomeStatus,
    ControllerDecision,
    PlanAction,
    PlanValidator,
    StrategyCard,
    StrategyLibrary,
    ToolContract,
    TypedObservation,
    build_intent_trace,
)
from g7confirm.orchestrators import IA3CandidateUCBAdaptive


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


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


def make_profile(rung: OrchestrationRung, *, candidate_cap: int,
                 allow_active_power: bool = True,
                 history_limit: int = 32,
                 max_strategies: int = 2) -> CapabilityProfile:
    return CapabilityProfile(
        profile_id=f"candidate_{rung.value}",
        rung=rung,
        knowledge=KnowledgeProfile(
            grid=InformationLevel.PARTIAL,
            feedback=InformationLevel.PARTIAL,
        ),
        authority=AuthorityProfile(
            allowed_devices=frozenset({"pv1", "pv2"}),
            allow_active_power=allow_active_power,
            allow_reactive_power=False,
            max_targets_per_plan=2,
            perturbed_window_cap=4,
            apparent_energy_cap_kvah=2.0,
        ),
        allowed_strategy_ids=frozenset({"S_step", "S_pulse"}),
        allowed_tool_names=frozenset(),
        tool_call_cap=0,
        outer_rollout_cap=0,
        history_limit=history_limit,
        candidate_count_cap=candidate_cap,
        max_strategies_per_plan=max_strategies,
    )


def make_spec(candidate_cap: int, *, enumeration_cap: int = 1000,
              composition_orders: tuple[int, ...] = (1, 2),
              selection_seed: str = "candidate-test-v1") -> CandidateGenerationSpec:
    return CandidateGenerationSpec(
        candidate_cap=candidate_cap,
        enumeration_cap=enumeration_cap,
        parameter_fractions=(0.0, 1.0),
        action_fractions=(0.0, 1.0),
        composition_orders=composition_orders,
        selection_seed=selection_seed,
    )


def make_manual_candidates() -> CandidateLibrary:
    library = make_library()
    return CandidateLibrary([
        CandidateTemplate(
            steps=(library.get("S_step").default_step(),),
            origins=frozenset({"test_fixture"}),
        ),
        CandidateTemplate(
            steps=(library.get("S_pulse").default_step(),),
            origins=frozenset({"test_fixture"}),
        ),
    ])


def make_reward_spec() -> CandidateRewardSpec:
    return CandidateRewardSpec(
        metric_name="paired_pre_alarm_harm",
        minimum=0.0,
        maximum=2.0,
        direction="maximize",
    )


class CandidateGenerationTests(unittest.TestCase):
    def test_checked_in_candidate_contract_is_non_executable_and_sealed(self):
        contract = json.loads(
            (PACKAGE_ROOT / "artifacts" / "ia3_candidate_space_contract.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(contract["executable"])
        self.assertFalse(contract["campaign_authorized"])
        self.assertTrue(contract["evaluation_sealed"])
        self.assertEqual(
            contract["reference_generation_spec"]["candidate_cap"], 64
        )
        self.assertEqual(
            contract["frozen_experiment_spec"]["sha256"],
            "79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d",
        )

    def test_generation_is_bounded_deterministic_and_stratified(self):
        profile = make_profile(OrchestrationRung.IA3, candidate_cap=12)
        arguments = {
            "profile": profile,
            "strategy_library": make_library(),
            "benign_commands": {"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
            "spec": make_spec(12),
        }
        first, first_receipt = generate_candidate_library(**arguments)
        second, second_receipt = generate_candidate_library(**arguments)
        self.assertEqual(first.ids(), second.ids())
        self.assertEqual(first.fingerprint(), second.fingerprint())
        self.assertEqual(first_receipt.to_dict(), second_receipt.to_dict())
        self.assertEqual(len(first.candidates), 12)
        self.assertGreater(first_receipt.raw_candidate_count, 12)
        self.assertTrue(first_receipt.to_dict()["truncated"])
        self.assertEqual(
            set(first_receipt.coverage["composition_orders"]), {1, 2}
        )
        self.assertEqual(
            set(first_receipt.coverage["strategy_ids"]), {"S_step", "S_pulse"}
        )
        self.assertEqual(
            set(first_receipt.coverage["target_ids"]), {"pv1", "pv2"}
        )
        self.assertTrue(
            set(first_receipt.required_default_ids).issubset(first.ids())
        )
        self.assertTrue(any(
            len(step.actions) == 2
            for candidate in first.candidates
            for step in candidate.steps
        ))

    def test_ia3_and_ia4_share_the_exact_candidate_fingerprint(self):
        benign = {"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)}
        ia3, _ = generate_candidate_library(
            profile=make_profile(OrchestrationRung.IA3, candidate_cap=12),
            strategy_library=make_library(),
            benign_commands=benign,
            spec=make_spec(12),
        )
        ia4, _ = generate_candidate_library(
            profile=make_profile(OrchestrationRung.IA4, candidate_cap=12),
            strategy_library=make_library(),
            benign_commands=benign,
            spec=make_spec(12),
        )
        assert_candidate_library_parity(ia3, ia4)
        self.assertEqual(ia3.fingerprint(), ia4.fingerprint())
        with self.assertRaisesRegex(ContractViolation, "parity mismatch"):
            assert_candidate_library_parity(
                ia3, CandidateLibrary(reversed(ia4.candidates))
            )

    def test_candidate_ids_are_rung_independent_content_addresses(self):
        candidate = make_manual_candidates().candidates[0]
        ia3_plan = candidate.instantiate(OrchestrationRung.IA3, "IA3 plan.")
        ia4_plan = candidate.instantiate(OrchestrationRung.IA4, "IA4 plan.")
        self.assertEqual(candidate.candidate_id, candidate.candidate_id)
        self.assertEqual(ia3_plan.steps, ia4_plan.steps)
        self.assertNotEqual(ia3_plan.plan_id, ia4_plan.plan_id)

    def test_disabled_power_axis_is_pinned_to_benign(self):
        profile = make_profile(
            OrchestrationRung.IA3,
            candidate_cap=6,
            allow_active_power=False,
        )
        candidates, _ = generate_candidate_library(
            profile=profile,
            strategy_library=make_library(),
            benign_commands={"pv1": (7.0, 0.0), "pv2": (9.0, 0.0)},
            spec=make_spec(6, composition_orders=(1,)),
        )
        for candidate in candidates.candidates:
            for step in candidate.steps:
                for action in step.actions:
                    expected = 7.0 if action.device_id == "pv1" else 9.0
                    self.assertEqual(action.p_kw, expected)

    def test_generation_fails_on_missing_benign_or_enumeration_overflow(self):
        profile = make_profile(OrchestrationRung.IA3, candidate_cap=4)
        with self.assertRaisesRegex(ContractViolation, "missing benign"):
            generate_candidate_library(
                profile=profile,
                strategy_library=make_library(),
                benign_commands={"pv1": (0.0, 0.0)},
                spec=make_spec(4, composition_orders=(1,)),
            )
        with self.assertRaisesRegex(ContractViolation, "enumeration_cap"):
            generate_candidate_library(
                profile=profile,
                strategy_library=make_library(),
                benign_commands={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
                spec=make_spec(
                    4, enumeration_cap=4, composition_orders=(1,)
                ),
            )

    def test_generation_refuses_to_silently_drop_a_coverage_group(self):
        profile = make_profile(OrchestrationRung.IA3, candidate_cap=2)
        with self.assertRaisesRegex(ContractViolation, "coverage group"):
            generate_candidate_library(
                profile=profile,
                strategy_library=make_library(),
                benign_commands={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
                spec=make_spec(2),
            )

    def test_generation_rejects_impossible_composition_order(self):
        profile = make_profile(
            OrchestrationRung.IA3,
            candidate_cap=6,
            max_strategies=3,
        )
        with self.assertRaisesRegex(ContractViolation, "distinct strategy count"):
            generate_candidate_library(
                profile=profile,
                strategy_library=make_library(),
                benign_commands={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
                spec=make_spec(6, composition_orders=(1, 3)),
            )

    def test_receipt_matches_machine_readable_schema_surface(self):
        schema = json.loads(
            (PACKAGE_ROOT / "candidate_space_receipt.schema.json").read_text(
                encoding="utf-8"
            )
        )
        _, receipt = generate_candidate_library(
            profile=make_profile(OrchestrationRung.IA3, candidate_cap=6),
            strategy_library=make_library(),
            benign_commands={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
            spec=make_spec(6, composition_orders=(1,)),
        )
        serialized = receipt.to_dict()
        self.assertEqual(set(serialized), set(schema["required"]))
        self.assertEqual(
            serialized["schema_version"],
            schema["properties"]["schema_version"]["const"],
        )
        self.assertFalse(serialized["campaign_authorized"])
        self.assertTrue(serialized["evaluation_sealed"])


class CandidateAdaptiveControllerTests(unittest.TestCase):
    def test_reward_contract_is_bounded_directional_and_parity_checked(self):
        maximize = make_reward_spec()
        minimize = CandidateRewardSpec(
            metric_name="paired_pre_alarm_harm",
            minimum=0.0,
            maximum=2.0,
            direction="minimize",
        )
        self.assertEqual(maximize.objective_value(0.5), 0.25)
        self.assertEqual(minimize.objective_value(0.5), 0.75)
        assert_reward_spec_parity(maximize, make_reward_spec())
        with self.assertRaisesRegex(ContractViolation, "reward parity"):
            assert_reward_spec_parity(maximize, minimize)
        with self.assertRaisesRegex(ContractViolation, "preregistered bounds"):
            maximize.objective_value(2.1)

    def test_candidate_ucb_assigns_credit_to_full_candidates(self):
        candidate_library = make_manual_candidates()
        controller = IA3CandidateUCBAdaptive(
            profile=make_profile(OrchestrationRung.IA3, candidate_cap=2),
            strategy_library=make_library(),
            candidate_library=candidate_library,
            reward_spec=make_reward_spec(),
            exploration_weight=0.0,
        )
        observation = TypedObservation(2, 20, {})
        first_id, second_id = candidate_library.ids()
        initial = controller.decide(observation, [])
        self.assertEqual(initial.candidate_id, first_id)
        partial = [OutcomeRecord(
            0,
            candidate_library.get(first_id).strategy_ids[0],
            1.0,
            OutcomeStatus.ACCEPTED_EFFECTIVE,
            candidate_id=first_id,
        )]
        self.assertEqual(
            controller.decide(observation, partial).candidate_id, second_id
        )
        complete = partial + [OutcomeRecord(
            1,
            candidate_library.get(second_id).strategy_ids[0],
            0.0,
            OutcomeStatus.ACCEPTED_EFFECTIVE,
            candidate_id=second_id,
        )]
        selected = controller.decide(observation, complete)
        self.assertEqual(selected.candidate_id, first_id)
        self.assertEqual(selected.reason, "typed_candidate_plan")

    def test_candidate_lineage_survives_validation_and_trace(self):
        profile = make_profile(OrchestrationRung.IA3, candidate_cap=2)
        candidate_library = make_manual_candidates()
        controller = IA3CandidateUCBAdaptive(
            profile=profile,
            strategy_library=make_library(),
            candidate_library=candidate_library,
            reward_spec=make_reward_spec(),
        )
        decision = controller.decide(TypedObservation(0, 0, {}), [])
        validator = PlanValidator(
            profile=profile,
            strategy_library=make_library(),
            tool_contract=ToolContract(()),
            dual_budget=DualBudget(
                window_cap=4,
                apparent_energy_cap_kvah=2.0,
                window_seconds=10,
            ),
        )
        outcome = validator.evaluate(
            decision,
            benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
        )
        trace = build_intent_trace(
            profile=profile,
            decision=decision,
            outcome=outcome,
            tool_calls=(),
        )
        self.assertEqual(outcome.candidate_id, decision.candidate_id)
        self.assertEqual(trace["candidate_id"], decision.candidate_id)
        self.assertEqual(
            trace["validation"]["candidate_id"], decision.candidate_id
        )

    def test_validator_rejects_forged_candidate_lineage_atomically(self):
        profile = make_profile(OrchestrationRung.IA3, candidate_cap=2)
        candidate = make_manual_candidates().candidates[0]
        decision = ControllerDecision.submit(
            candidate.instantiate(OrchestrationRung.IA3, "Forged lineage."),
            "typed_candidate_plan",
            candidate_id="cand_00000000000000000000",
        )
        validator = PlanValidator(
            profile=profile,
            strategy_library=make_library(),
            tool_contract=ToolContract(()),
            dual_budget=DualBudget(
                window_cap=4,
                apparent_energy_cap_kvah=2.0,
                window_seconds=10,
            ),
        )
        outcome = validator.evaluate(
            decision,
            benign={"pv1": (0.0, 0.0), "pv2": (0.0, 0.0)},
        )
        self.assertEqual(outcome.status, OutcomeStatus.CONTRACT_REJECTION)
        self.assertIn("candidate_id", outcome.reason)
        self.assertEqual(validator.dual_budget.windows_spent, 0)

    def test_rewarded_history_requires_known_candidate_lineage(self):
        controller = IA3CandidateUCBAdaptive(
            profile=make_profile(OrchestrationRung.IA3, candidate_cap=2),
            strategy_library=make_library(),
            candidate_library=make_manual_candidates(),
            reward_spec=make_reward_spec(),
        )
        observation = TypedObservation(1, 10, {})
        without_id = [OutcomeRecord(
            0, "S_step", 1.0, OutcomeStatus.ACCEPTED_EFFECTIVE
        )]
        with self.assertRaisesRegex(ContractViolation, "requires candidate_id"):
            controller.decide(observation, without_id)
        unknown = [OutcomeRecord(
            0,
            "S_step",
            1.0,
            OutcomeStatus.ACCEPTED_EFFECTIVE,
            candidate_id="cand_00000000000000000000",
        )]
        with self.assertRaisesRegex(ContractViolation, "unknown candidate"):
            controller.decide(observation, unknown)
        first_id = controller.candidate_library.ids()[0]
        mismatch = [OutcomeRecord(
            0,
            "S_pulse",
            1.0,
            OutcomeStatus.ACCEPTED_EFFECTIVE,
            candidate_id=first_id,
        )]
        with self.assertRaisesRegex(ContractViolation, "strategy_id"):
            controller.decide(observation, mismatch)

    def test_controller_rejects_candidate_library_above_profile_cap(self):
        profile = make_profile(OrchestrationRung.IA3, candidate_cap=1)
        with self.assertRaisesRegex(ContractViolation, "candidate_count_cap"):
            IA3CandidateUCBAdaptive(
                profile=profile,
                strategy_library=make_library(),
                candidate_library=make_manual_candidates(),
                reward_spec=make_reward_spec(),
            )

    def test_controller_rejects_history_too_short_for_candidate_credit(self):
        profile = make_profile(
            OrchestrationRung.IA3,
            candidate_cap=2,
            history_limit=1,
        )
        with self.assertRaisesRegex(ContractViolation, "history_limit"):
            IA3CandidateUCBAdaptive(
                profile=profile,
                strategy_library=make_library(),
                candidate_library=make_manual_candidates(),
                reward_spec=make_reward_spec(),
            )


if __name__ == "__main__":
    unittest.main()
