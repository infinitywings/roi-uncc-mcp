# M29-R offline complementarity report

## Verdict

**Provider-compatible execution qualification: PASS.** Attempt 2 completed all
96 registered cells. All 48 LLM calls returned model responses, the primary
receipt rebuilt with `issues=[]`, and the independent non-campaign auditor
also rebuilt with `issues=[]`.

**Core complementarity unlock: FAIL.** The registered `IA4-H` hybrid produced
zero conjunctive successes, zero correct mirrored pairs, and no witness cell
that both the optimizer-only and direct-LLM controls missed. M29-B remains
locked.

**Secondary scoped-retrieval rule: PASS within this battery.** `IA4-HR`
improved over `IA4-H` by four successes on the eight retrieval-required cells
and did not degrade on the eight non-retrieval cells. This result is useful for
the next offline design iteration, but the frozen contract explicitly forbids
it from substituting for the failed core unlock.

All evidence is `PRELIMINARY_ONLY`.

## Attempt history and retained provider failure

| Attempt | Execution contract | Infrastructure result | Scientific interpretation |
|---|---|---|---|
| 1 | `m29rexec_8567660baac6afe9bdfb7682c01fecdbef836e803ebe14d14448efddd1c626aa` | 48 deterministic cells completed; 48 LLM cells failed with HTTP 500 | Provider compatibility failure only; no LLM or hybrid estimate |
| 2 | `m29rexec_bff5fd77afe9896a06d7135ce0fe52fc6e8d9fe3ce5a4801219fe7c0185d1a72` | 96/96 cells completed; primary and independent audits passed | Core complementarity not demonstrated; secondary retrieval rule passed |

Attempt 1 was never overwritten. A five-request diagnostic isolated the
deployed vLLM structured-output compiler's rejection of `uniqueItems`.
Attempt 2 changed only the provider-facing schema projection, disabled Qwen
thinking, and fixed response cardinality to one. Local uniqueness validation,
evidence bytes, corpus bytes, conditions, arms, seeds, optimizer, independent
oracle, common validator, endpoints, and unlock thresholds remained unchanged.

The Attempt 2 primary receipt is
`m29rprimary_63ab632adc0929281a78ee9287f89515bfccb4ce9643a864632b11b3d47a0c6b`.
The independent audit is
`m29raudit_de37e91874e09cb4a1f8b75e9b0266e5c02ce15effd32164d335b2e1c2bdf08b`.

## Registered arm results

| Arm | Role | Successes | Correct pairs | Validity violations |
|---|---|---:|---:|---:|
| `IA3-O` | Neutral semantics plus deterministic optimizer | 0/16 | 0/8 | 16 |
| `IA3-SO` | Frozen symbolic compiler plus optimizer | 4/16 | 2/8 | 0 |
| `IA4-D` | Direct LLM plan without optimizer | 0/16 | 0/8 | 0 |
| `IA4-H` | LLM compiler plus deterministic optimizer | 0/16 | 0/8 | 1 |
| `IA4-HR` | Scoped retrieval, LLM compiler, and optimizer | 4/16 | 1/8 | 0 |
| `IA5-OC` | Independent oracle compiler plus optimizer | 16/16 | 8/8 | 0 |

The oracle ceiling confirms that all registered conditions are solvable. The
controls also behave as intended: the semantics-free optimizer cannot solve
the tasks, the narrow symbolic compiler succeeds only on four controlled
language cells, and the direct LLM does not reproduce the numerical optimum.

The decisive failure is semantic compilation. `IA4-H` frequently generated a
plan that exactly matched the oracle action sequence after optimization, but
its typed strategy program differed from the latent oracle semantics. Those
cells correctly remain failures because action coincidence cannot substitute
for strategy, constraint, and evidence-lineage correctness. The common
validator also retained one `IA4-H` plan-validity violation.

`IA4-HR` achieved four conjunctive successes: both delayed-evidence
conditions, resource-budget-left, and gradual-bias-horizon-right. Only the
delayed-evidence mirrored pair was correct on both sides. This asymmetry is a
diagnostic signal, not evidence of robust retrieval-assisted reasoning.

## Preregistered gates

| Check | Required | Observed | Result |
|---|---:|---:|---|
| Oracle ceiling | at least 16 successes | 16 | PASS |
| `IA4-H` successes | at least 12 | 0 | FAIL |
| `IA4-H` correct pairs | at least 6 | 0 | FAIL |
| `IA4-H` validity violations | at most 0 | 1 | FAIL |
| `IA4-H - IA3-O` margin | at least 6 | 0 | FAIL |
| `IA4-H - IA4-D` margin | at least 4 | 0 | FAIL |
| Hybrid-only witness cells | at least 4 | 0 | FAIL |
| Retrieval-subset margin | at least 2 | 4 | PASS |
| Non-retrieval degradation | at most 1 | 0 | PASS |

The primary gate is conjunctive. Passing only the oracle and secondary
retrieval checks cannot make the attempt eligible for an M29-B proposal.

## Resource and access accounting

| Quantity | Count |
|---|---:|
| Prior read-only chat requests | 53 |
| Attempt 2 model calls | 48 |
| Cumulative read-only chat requests | 101/1000 |
| Prompt tokens | 168,896 |
| Completion tokens | 12,921 |
| Optimizer calls | 52 |
| Optimizer evaluations | 1,485,172 |
| Embedding HTTP calls, including prior preflight | 4 |
| Retrieved passages | 64 |
| Invalid proposals | 7 |
| Refusals | 14 |

The campaign used the already-running embedding service and did not start,
restart, replace, or reconfigure either model. It did not access Docker,
HELICS, GridLAB-D, OpenDER, a simulator, detector, defense, network impairment,
physical actuation, RKA governance from an attacker arm, final evaluation, or
seeds 9101--9112.

## Verification record

- The focused M29-R suite passed 39 tests.
- The complete G7 suite passed 493 tests.
- Python byte-code compilation passed for the post-hoc analysis module.
- Every Attempt 2 and failure-analysis JSON file parsed as strict JSON.
- Primary verification returned `issues=[]`.
- Independent audit verification returned `issues=[]`.
- Failure-analysis receipt
  `m29ranalysis_c31e36033d92c95c2342934652690ff205e0564666d0ad32164e241ce12ae1eb`
  rebuilt with `issues=[]`.

## Supported claims

The immutable development evidence supports only these bounded claims:

1. The provider-only compatibility projection eliminated the retained
   `uniqueItems` HTTP 500 failure while preserving the registered scientific
   contract.
2. The six-arm M29-R protocol is executable, create-once, content-addressed,
   and independently reproducible on the current service snapshot.
3. The current LLM-plus-optimizer composition did not demonstrate the
   preregistered semantic and numerical complementarity mechanism.
4. Scoped retrieval improved conjunctive success on four retrieval-required
   cells and met its preregistered secondary rule without non-retrieval
   degradation.
5. The perfect oracle ceiling separates model/compiler failure from fixture
   infeasibility.

## Unsupported claims

M29-R does not support claims of general LLM, hybrid, optimizer, or retrieval
superiority; robust long-horizon bias injection; physical impact; stealth;
detector evasion; defense bypass; cross-model or cross-prompt generalization;
or confirmatory inference. It does not authorize M29-B or any simulator run.

## Next research action

Do not rerun or tune against the registered M29-R cells. Open a new offline
mission with a disjoint development namespace that treats semantic compilation
as the measured bottleneck. The next design should:

1. decompose strategy compilation into independently scored doctrine,
   authority, temporal-validity, topology, budget, and evidence-lineage slots;
2. compare single-pass compilation with a typed inspect-revise workflow that
   may query a deterministic validator but cannot see the latent oracle;
3. retain the same deterministic optimizer across relevant arms so that
   compilation repair cannot be mistaken for numerical-search improvement;
4. isolate retrieval selection quality from post-retrieval instruction
   following, including mirrored counterfactuals and asymmetric-error checks;
5. add a stronger deterministic semantic baseline instead of treating the
   intentionally narrow `IA3-SO` parser as the only non-LLM compiler; and
6. require held-out semantic-slot accuracy before considering another
   end-to-end complementarity or simulator gate.

This changes the research question from "does the current hybrid already win?"
to "which semantic operations fail, and can validator-guided tool use repair
them without leaking the answer?" That is the narrowest next experiment
supported by Attempt 2.
