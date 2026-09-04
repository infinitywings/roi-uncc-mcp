# M29-A executor backbrief

## Mission interpretation

M29-A is a development-only, offline qualification of strategy-to-optimization
compilation and evidence-conditioned tool use. It compares five arms under a
frozen knowledge, authority, feedback, candidate, and accounting boundary:

- `IA2`: frozen rule-based switching;
- `IA3-O`: deterministic optimizer-only control;
- `IA4-D`: direct LLM decision without optimizer access;
- `IA4-H`: LLM meta-controller using the exact `IA3-O` optimizer; and
- `IA4-HG`: `IA4-H` with a structured runtime attack-state representation.

The target is conditional complementarity among semantic orchestration,
deterministic numerical search, and scoped structured memory. M29-A does not
measure physical harm, stealth, detector evasion, or final-evaluation
performance.

## Task-to-verification map

| Mission task | Implementation | Verification |
|---|---|---|
| Freeze arms and contrasts | Content-addressed design contract, arm-factor matrix, and explicit estimability labels | Recompute every source hash and reject unregistered factors |
| Define optimizer boundary | Strict `OptimizationRequest` and `OptimizerResult` schemas; one pure deterministic optimizer entry point; one common plan validator | Schema round-trips, negative fixtures, optimizer source hash and parity assertions |
| Define runtime attack state | Canonical facts, K-filtered views, validity/evidence/failure/lineage fields, separate from RKA | Content-address recomputation, forbidden-field scan, semantic-equivalence digest |
| Register eight counterfactuals | Sixteen immutable condition IDs with fixture-only oracle or partial-order expectations | Exact class/count checks and expectation recomputation without simulator data |
| Execute five arms | Deterministic `IA2`/`IA3-O`; bounded create-once `IA4-D`/`IA4-H`/`IA4-HG` after Gate 1 | Attempt limits, terminal failure retention, validator admission, separated costs |
| Audit and report | Primary verifier, non-importing independent JSON auditor, immutable receipts, `PRELIMINARY_ONLY` report | `issues=[]` from both paths and byte-identical endpoint tables |

## Primary contrasts

The four protocol-level contrasts remain frozen:

1. `IA4-H - IA3-O`: semantic meta-orchestration over a shared optimizer.
2. `IA4-H - IA4-D`: value of the optimizer tool to an LLM controller.
3. `IA4-HG - IA4-H`: value of structured scoped runtime state.
4. `IA5-HG - compute-matched IA4-HG`: critic value, registered now but not
   estimable in M29-A.

`IA2` is a calibration arm. No post-result contrast will be promoted to
primary status.

## Assumptions

1. M28 remains the qualified actor-blind action boundary and its artifacts are
   immutable inputs, not M29 edit targets.
2. M5-M7 state-machine and M24-M26 adapter concepts can be extended in new M29
   modules without mutating prior evidence.
3. One canonical fact list can render flat text and structured state with the
   same semantic digest.
4. Each mirrored fixture can define an oracle or partial order without
   simulator outcomes.
5. `IA3-O` and `IA4-H` can invoke one byte-identical optimizer implementation
   with identical surfaces, constraints, histories, feedback, and query caps.
6. The already-running `qwen3.6-35b-a3b` service can be probed after Gate 1
   without restart; a failed attempt will be retained and not retried silently.
7. `IA4-HG` changes representation only; raw facts and all capability fields
   remain fixed relative to `IA4-H`.
8. Unrelated dirty-worktree changes can be preserved by using new M29 files and
   scoped commits.
9. Superseded or retracted low-relevance G4/M24 guard notes are not operative
   inputs; current M22-M28 code/reports and the M29 protocol are authoritative.

## Fail-closed boundaries

- No Docker, simulator, HELICS, OpenDER, GridLAB-D, detector, defense, network
  impairment, physical actuator, embedding service, final record, or evaluation
  seed is accessed in M29-A.
- The RKA governance graph is never serialized into an attacker-facing state.
- The M23 point-specific sensitivity scalar is not treated as invariant.
- All LLM outputs are parsed into a typed direct decision, optimizer request,
  refusal, or terminal failure. They cannot directly reach an actuator.
- Every candidate passes the common `PlanValidator` path.
- Provider, parsing, schema, validation, tool, and lineage failures are retained
  as distinct terminal outcomes. There is no overwrite or silent retry.
- M29-B remains locked until a separate Gate 2 verdict.

## Planned files

- `m29_hybrid_plan.json`
- `m29_optimization_request.schema.json`
- `m29_optimizer_result.schema.json`
- `m29_attack_state.schema.json`
- `m29_counterfactual_contract.schema.json`
- `M29A_INDEPENDENT_AUDIT_PLAN.md`
- `artifacts/m29_hybrid_contract/contract.json`
- `g7confirm/m29_hybrid_contract.py`
- `g7confirm/m29_counterfactual.py`
- `g7confirm/m29_independent_audit.py`
- `tests/test_m29_hybrid.py`
- immutable attempt/audit receipts and `M29A_HYBRID_QUALIFICATION_REPORT.md`

This backbrief authorizes no live-model call by itself. The design contract and
its source-hash manifest must exist and the RKA plan-validation gate must be
`GO` first.
