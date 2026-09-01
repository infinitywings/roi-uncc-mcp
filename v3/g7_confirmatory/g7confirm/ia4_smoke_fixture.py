"""Synthetic two-candidate surface for the M4 model-parsing smoke only."""

from __future__ import annotations

from .candidates import CandidateLibrary, CandidateRewardSpec, CandidateTemplate
from .ia4_adapter import IA4FixtureAdapter
from .orchestration_contract import (
    AuthorityProfile,
    CapabilityProfile,
    InformationLevel,
    KnowledgeAxis,
    KnowledgeProfile,
    NumericParameterSpec,
    OrchestrationRung,
    PlanAction,
    SideEffectClass,
    StrategyCard,
    StrategyLibrary,
    ToolContract,
    ToolSpec,
)
from .search_surface import build_search_surface


def _strategy_library() -> StrategyLibrary:
    return StrategyLibrary([
        StrategyCard(
            strategy_id="step_corner",
            family="step",
            description=(
                "Apply one bounded active-power step to a single declared DER."
            ),
            default_actions=(PlanAction("DER_A", 30.0, 0.0),),
            eligible_devices=frozenset({"DER_A", "DER_B"}),
            p_kw_bounds=(0.0, 100.0),
            q_kvar_bounds=(0.0, 0.0),
            parameter_specs=(
                NumericParameterSpec("scale", 0.0, 1.0, 0.3),
            ),
        ),
        StrategyCard(
            strategy_id="pulse_intermittent",
            family="pulse",
            description=(
                "Apply one bounded intermittent active-power pulse to a "
                "single declared DER."
            ),
            default_actions=(PlanAction("DER_B", 40.0, 0.0),),
            eligible_devices=frozenset({"DER_A", "DER_B"}),
            p_kw_bounds=(0.0, 100.0),
            q_kvar_bounds=(0.0, 0.0),
            parameter_specs=(
                NumericParameterSpec("duration_windows", 1.0, 4.0, 1.0),
            ),
        ),
    ])


def _candidate_library(library: StrategyLibrary) -> CandidateLibrary:
    return CandidateLibrary([
        CandidateTemplate(
            steps=(library.get("step_corner").default_step(),),
            origins=frozenset({"m4_synthetic_interface_fixture"}),
        ),
        CandidateTemplate(
            steps=(library.get("pulse_intermittent").default_step(),),
            origins=frozenset({"m4_synthetic_interface_fixture"}),
        ),
    ])


def _profile(rung: OrchestrationRung) -> CapabilityProfile:
    return CapabilityProfile(
        profile_id=f"m4_smoke_{rung.value}",
        rung=rung,
        knowledge=KnowledgeProfile(
            grid=InformationLevel.PARTIAL,
            feedback=InformationLevel.PARTIAL,
        ),
        authority=AuthorityProfile(
            allowed_devices=frozenset({"DER_A", "DER_B"}),
            allow_active_power=True,
            allow_reactive_power=False,
            max_targets_per_plan=1,
            perturbed_window_cap=4,
            apparent_energy_cap_kvah=2.0,
            feedback_delay_windows=1,
        ),
        allowed_strategy_ids=frozenset({
            "step_corner", "pulse_intermittent",
        }),
        allowed_tool_names=frozenset({
            "observe_state", "bounded_rollout",
        }),
        tool_call_cap=2,
        outer_rollout_cap=1,
        history_limit=4,
        candidate_count_cap=2,
        max_strategies_per_plan=1,
    )


def _tool_contract() -> ToolContract:
    return ToolContract([
        ToolSpec(
            name="observe_state",
            side_effect_class=SideEffectClass.READ_ONLY_NO_TIME_ADVANCE,
            information_axis=KnowledgeAxis.GRID,
            minimum_information_level=InformationLevel.PARTIAL,
            input_schema_version="observation-query/v1",
            output_schema_version="observation-result/v1",
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


def build_m4_smoke_adapter() -> IA4FixtureAdapter:
    """Build the fixed synthetic surface used only for parser qualification."""

    library = _strategy_library()
    candidates = _candidate_library(library)
    tools = _tool_contract()
    reward = CandidateRewardSpec(
        metric_name="synthetic_paired_pre_alarm_harm",
        minimum=0.0,
        maximum=2.0,
        direction="maximize",
    )
    ia3_surface = build_search_surface(
        profile=_profile(OrchestrationRung.IA3),
        strategy_library=library,
        candidate_library=candidates,
        reward_spec=reward,
        tool_contract=tools,
    )
    return IA4FixtureAdapter(
        profile=_profile(OrchestrationRung.IA4),
        strategy_library=library,
        candidate_library=candidates,
        reward_spec=reward,
        tool_contract=tools,
        search_surface=ia3_surface,
    )
