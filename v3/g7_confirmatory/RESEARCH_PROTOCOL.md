# G7 confirmatory research protocol

Protocol ID: `g7-confirmatory-20260831-r1`

Status: Phase 0–1 harness approved; confirmatory campaign not yet authorized.

## Research question

After equalizing attacker information, DER authority, perturbed-window and
apparent-energy budgets, outer proposal budget, detector calibration, and
held-out evaluation, does an LLM-guided schedule search outperform a
non-LLM schedule search on paired harm accumulated before the first alarm?

## Primary estimand

For each held-out seed and operating condition, compute attacker-minus-benign
rectified voltage-departure harm integrated only through the window before the
first detector alarm. Normalize the paired difference by injected apparent
energy (kVAh). The primary comparison is the paired difference between the
selected LLM schedule and the selected non-LLM schedule after the same outer
proposal budget `K`.

The alarm-window convention, zero-energy handling, aggregation across DERs,
and schedule-selection rule must be frozen before evaluation labels are
opened.

## Information conditions

The confirmatory LLM receives only:

- the public action space and operational budgets;
- a qualitative statement that detection is path-dependent;
- its own earlier proposals and development-partition outcomes; and
- the strict JSON response contract.

It does not receive empirical detector thresholds, previously successful
schedules, the benign self-alarm horizon, ranked exploratory outcomes, or
post-result strategy heuristics. The non-LLM search arms receive the same
candidate space, budgets, and development outcomes.

The preserved 20260830 L5b run is classified as `horizon_informed_exploratory`
and is excluded from confirmatory inference.

## Arms and equal search budget

- `fixed_grid`: deterministic preregistered schedule ordering.
- `random_search`: seeded sampling without replacement from the same space.
- `llm_clean_uninformed`: clean-prompt adaptive proposal from the same space.

Every search arm receives exactly `K=12` evaluated proposals per search cell.
The L3 mechanic policy and benign run are interpretation controls, not search
arms, and are reported separately.

The first confirmatory comparison is one slice of the larger red-team design in
`RED_TEAM_DESIGN.md`. Later campaigns must encode attacker knowledge as a
five-component vector rather than relying on an ambiguous black/gray/white
label. Detector and defense candidates are screened in
`DETECTOR_DEFENSE_REVIEW.md`.

## Operational budgets

Every evaluated proposal is bounded by both:

- at most 8 perturbed 10-second windows; and
- at most 2.0 kVAh cumulative apparent command deviation relative to the
  benign per-DER command.

For a candidate action, energy is
`sum_der sqrt(delta_p_kw^2 + delta_q_kvar^2) * 10 / 3600` kVAh. The action is
accepted atomically only when both prospective totals remain within their
caps. Rejected actions become benign windows and are provenance-logged.

The 2.0 kVAh cap is a preregistered engineering choice for the primary design,
not a claim that it is power-optimal. Budget sensitivities are descriptive.

## Partitions and leakage control

Detector-calibration, development, and evaluation seed sets are pairwise
disjoint. Evaluation outcomes cannot enter prompts, search histories,
schedule selection, or detector tuning. A frozen detector artifact and a
frozen selected schedule for each arm are prerequisites to opening the
evaluation partition.

Seed labels are intended to drive every stochastic component that the runtime
actually exposes. Runtime integration must demonstrate seed control and must
not overstate repeatability if a component remains unseeded.

## Design grid

The confirmatory target contains four responsive operating points plus one
ceiling/falsification point, Volt-VAR off/on, a primary measurement-noise
condition of 0.2% and descriptive 0.1%/0.5% sensitivities. The primary budget
is 8 windows; 0/2/4/16-window values are sensitivity or control conditions.
At least 10 clean held-out stochastic replicates are required per primary
cell. The machine spec plans 12 so up to two preregistered technical failures
can be reported without silently shrinking the target.

## Hard stops

Stop and open an RKA checkpoint if any of the following occurs:

- prompt audit fails or evaluation information reaches a search arm;
- proposal counts, candidate spaces, authority, or budgets differ by arm;
- a manifest/output path already exists;
- the detector or selected schedules are not frozen before evaluation;
- fewer than 10 valid held-out replicates remain in a primary cell;
- runtime hashes differ from the reviewed manifest;
- operating-point parameterization is not proven to affect the simulator;
- the model ID differs from the preregistered ID; or
- a co-simulation/model failure would require an unplanned fallback.

## Gates

1. Phase 0–1 plan validation: protocol, leakage audit, budgets, manifests,
   tests, and one bounded proposal smoke.
2. Runtime integration review: operating points, detector freeze, seed wiring,
   paired baseline execution, and provenance completeness.
3. Bounded throughput/power pilot: no confirmatory inference.
4. Campaign authorization: frozen bytes and independent audit.
5. Evidence review and synthesis validation.

## Literature boundary

State-of-the-art papers motivate candidate mechanisms; their published metrics
are not imported as expected performance. Every detector and defense must be
recalibrated and stress-tested on this unbalanced distribution feeder, its
OpenDER dynamics, and the same held-out attack suite.
