# Phase 0–1 implementation report

Protocol: `g7-confirmatory-20260831-r1`

RKA mission: `mis_01M1ASETDXKSC8CDNNPE49ZW1D`

Plan-validation gate: `chk_01M1ASKZXKM4FC0VCDV8Z6SNY8` (`GO` for harness
only)

## Delivered

- Research protocol and explicit provenance correction for the legacy
  horizon-informed L5b result.
- Machine-readable spec, finite common candidate space, global `K=12`,
  disjoint calibration/development/evaluation seeds, and hard stops.
- Clean LLM prompt with fail-closed leakage checks for prior alarm horizons,
  empirical schedule rankings, outcome values, and evaluation-partition data.
- Atomic perturbed-window plus apparent-energy accounting relative to each
  DER's benign command, with a policy adapter matching the frozen policy API.
- Strict model discovery, response parsing, candidate validation, and
  create-once smoke artifacts.
- Deterministic, explicitly non-executable campaign planning with equal
  proposal counts across search arms.
- Grid-aware red-team strategy/metric design and a sourced detector/defense
  shortlist for black-, gray-, and white-box testing.

## Offline verification

The final offline suite contains 22 tests covering:

- spec invariants and seed-partition disjointness;
- equal outer budgets and deterministic planning;
- static prompt leakage and evaluation-history rejection;
- atomic window/energy rejection and benign-command normalization;
- adapter accounting, unknown-device rejection, and create-once outputs; and
- strict exact-contract/off-grid/extra-field/empty-rationale model parsing.

`python3 -m unittest discover -s tests -v` passes. Package/test bytecode
compilation and CLI spec validation pass.

## Bounded model smoke evidence

No co-simulation was started.

1. `artifacts/model_smoke.json`: model discovery succeeded, but the completion
   contained no final proposal content. The request failed closed.
2. `artifacts/model_smoke_attempt2.json`: after applying the documented Qwen/
   vLLM non-thinking request option, the model returned an exact-contract JSON
   object whose amplitude and period passed candidate validation. The response
   then failed the preregistered rationale constraint (not a non-empty string of
   at most 1000 characters) and was rejected.

Both artifacts are immutable and remain as evidence. There was no fallback
proposal, no action, and no third attempt.

## Current verdict

Phase 0–1 code and offline controls are ready. Model compatibility and live
co-simulation integration are **HOLD**, not pass. The full confirmatory campaign
is not authorized.

Before a runtime gate can pass:

- perform a newly authorized, uniquely named compatibility smoke that records
  safe response field types/lengths and uses a server-supported strict JSON
  schema or fixes the prompt contract without using experimental outcomes;
- wire `DualBudgetPolicyAdapter` into a derived runner and prove delivered
  command/energy accounting end-to-end;
- make operating points real simulator inputs and verify that they change the
  physical initial condition/load/PV state;
- freeze/calibrate detector variants using calibration only, then demonstrate
  evaluation-partition isolation;
- implement paired benign lineage and complete command-to-physics-to-detector
  provenance; and
- submit the derived runtime bytes to an evidence-review gate and independent
  hash audit.

## Interpretation boundary

Passing unit tests proves harness invariants, not physical validity, detector
performance, statistical power, or campaign readiness. Literature results are
design inputs only; every detector/defense must be recalibrated and attacked on
this feeder.

