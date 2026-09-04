# M29-A hybrid qualification report

## Verdict

**M29-A infrastructure qualification: PASS.** The third registered,
create-once attempt completed every applicable cell, the primary verifier
returned `issues=[]`, and the independently implemented non-importing auditor
also returned `issues=[]`.

**Scientific Gate 2 recommendation: HOLD.** The result does not show hybrid
behavior beyond both the optimizer-only and direct-LLM controls. In particular,
`IA3-O` matched all 16 applicable fixture expectations, while `IA4-H` matched
13 of 16. On the 12 cells shared by `IA4-D` and `IA4-H`, both arms matched 9.
Adding the structured runtime state reduced matches from 13 of 16 for `IA4-H`
to 12 of 16 for `IA4-HG`. M29-B execution therefore remains unauthorized.

This report is `PRELIMINARY_ONLY`. It is a development qualification, not a
confirmatory result.

## Frozen design

M29-A compared five arms under a common candidate surface, validity boundary,
history, feedback, raw-information digest, and environment-query budget:

| Arm | Decision core | LLM | Optimizer | State representation |
|---|---|---:|---:|---|
| `IA2` | Frozen rules | No | No | Canonical typed state |
| `IA3-O` | Deterministic optimizer policy | No | Yes | Canonical typed state |
| `IA4-D` | Direct LLM decision | Yes | No | Flat text |
| `IA4-H` | LLM meta-controller | Yes | Yes | Flat text |
| `IA4-HG` | LLM meta-controller | Yes | Yes | Structured graph |

The contract registered eight mirrored intervention classes and 16 immutable
conditions: sensitivity reversal, operating-point change, validity hole,
budget change, delayed feedback, infeasible optimizer output, tool failure
class, and strategy-rule contradiction. The critic contrast remains registered
but deferred.

- Design contract:
  `m29contract_97d073f1ecbc03271346a6559dfc8367275a45a18519be13d38240da7bf423b0`
- Candidate surface:
  `m29surface_375078014f605fae2211b301f9ee54cfab6cecadf97f179e60fbe6a5ec9a220b`
- Attempt 3 execution contract:
  `m29exec_89382c9bd7af947e22f89c693e6bd838f1cffd30aa6ebe6ea45e521eb2290374`
- Optimizer/core source SHA-256:
  `a26f04bdb6aae29e7681a6f18c123a33cbec14f7a35e8dd0b2984673498d07e4`
- Runner source SHA-256:
  `c2082d2d96e9c6fd5b66a833edaadcc5a7951593a31296bfb2500185c9e01741`
- Independent auditor source SHA-256:
  `cc59e21996927639d4974ca97ae1c7c4409f9ad4adb08ce68a2104673f7bd4c7`

## Attempt history

All attempts are retained. No failed cell was overwritten or silently
retried.

| Attempt | Execution contract | Applicable completion | Primary | Independent audit | Interpretation |
|---|---|---:|---|---|---|
| 1 | `m29exec_b959c9c79059d6c98ccf93ff63a7088dab617a2af88e565a8f137d5589bd319c` | 28 completed, 44 failed closed | Legacy verifier incorrectly passed | Failed, 48 issues | Provider rejected the original mixed nullable response schema with HTTP 500; the primary completion check was also defective. Both defects were retained and corrected in new source bytes. |
| 2 | `m29exec_552630cc6d0dc99433047514afa3ccad449bdfa6b0fda9a1d12112f10624c5ca` | 69 completed, 3 failed closed | Failed, 3 issues | Failed, 9 issues | The explicit union schema restored provider compatibility, but three responses ended at the 512-token cap. The prompt response envelope was narrowed and one over-specified endpoint was corrected to its frozen partial order. |
| 3 | `m29exec_89382c9bd7af947e22f89c693e6bd838f1cffd30aa6ebe6ea45e521eb2290374` | 72 completed, 8 not applicable | Passed, 0 issues | Passed, 0 issues | Qualification attempt. Every applicable cell reached a terminal completed state. |

Attempt 3 primary receipt:
`m29primary_e85ae9996b3690aca1edc02ac3c3521adc19af064341f1fddbe4187166d14437`.
Independent audit receipt:
`m29audit_6866e1a4f56f17404c2273634c0d7e30b4c867e537cfee80f2c8df6fc1fb0cba`.

## Attempt 3 behavioral endpoints

| Arm | Applicable | Completed | Expectation matches | Oracle matches | Validity compliant |
|---|---:|---:|---:|---:|---:|
| `IA2` | 12 | 12 | 12 | 12 | 12 |
| `IA3-O` | 16 | 16 | 16 | 16 | 16 |
| `IA4-D` | 12 | 12 | 9 | 9 | 12 |
| `IA4-H` | 16 | 16 | 13 | 13 | 16 |
| `IA4-HG` | 16 | 16 | 12 | 12 | 16 |

The hybrid controller handled delayed feedback and both registered tool-failure
classes, including fail-closed refusals. It nevertheless missed the right-side
budget change, right-side sensitivity reversal, and left-side validity-hole
conditions. `IA4-HG` missed four conditions: right-side delayed feedback,
right-side operating-point change, right-side sensitivity reversal, and the
left-side strategy-rule contradiction.

The important comparison is conditional rather than rhetorical:

1. `IA4-H - IA3-O`: no hybrid benefit was observed; expectation matches were
   13/16 versus 16/16.
2. `IA4-H - IA4-D`: no aggregate tool benefit was observed on their 12 shared
   applicable conditions; both were 9/12, although their error sets differed.
3. `IA4-HG - IA4-H`: no structured-state benefit was observed; matches were
   12/16 versus 13/16.
4. Critic value remains unestimated because `IA5-HG` was intentionally
   deferred.

Fixture regret is retained in the endpoint table but is not used as a simple
cross-arm performance ranking here. Some registered tool-failure and
infeasibility conditions intentionally require refusal, so raw regret totals
mix normal selections with fail-closed behavior.

## Resource and cost accounting

Attempt 3 used the already-running `qwen3.6-35b-a3b` endpoint. It did not start
or restart the model service.

| Quantity | Count |
|---|---:|
| Model calls | 44 |
| Prompt tokens | 71,695 |
| Completion tokens | 5,681 |
| Optimizer calls | 48 |
| Optimizer evaluations | 90 |
| Optimizer compute units | 90 |
| Accepted and effective decisions | 65 |
| Refusals | 7 |
| Invalid proposals | 0 |
| Read-only tool calls | 0 |
| Environment queries | 0 |

The primary and independent paths both verified that M29-A did not access
Docker, a simulator, HELICS, OpenDER, GridLAB-D, detectors, defenses, the
embedding service, physical actuators, final evaluation records, RKA from an
attacker arm, or evaluation seeds `9101` through `9112`.

## Verification record

- Focused M29 test suite: `15 passed`.
- Full G7 test suite: `454 passed`.
- Python byte-code compilation passed for all three M29 modules.
- All 15 M29 plan, contract, attempt, primary-receipt, and audit-receipt JSON
  files parsed successfully.
- Repository whitespace validation returned no errors.
- Primary verification and the independent audit both returned `issues=[]` on
  the immutable Attempt 3 bytes.

## Supported claims

The immutable development evidence supports the following bounded claims:

1. The five-arm offline protocol is executable with strict typed compilation,
   common validation, source binding, cost accounting, and create-once
   retention.
2. The current model can produce schema-valid direct decisions and typed
   optimizer requests within this small registered battery; all 44 Attempt 3
   model calls terminated without parse or schema failure.
3. The optimizer tool boundary can fail closed, and every effective decision
   can be required to pass the same validator.
4. Flat and structured attacker views can be capability-filtered and bound to
   the same semantic digest without exposing the RKA governance graph.
5. The LLM arms exhibit some evidence-conditioned switching and valid
   refusals, but this behavior is imperfect and representation-sensitive.

## Unsupported claims

M29-A does **not** support any claim of:

- LLM or hybrid superiority over the deterministic optimizer;
- benefit from graph-structured runtime state;
- physical impact, stealth, detector evasion, or defense bypass;
- long-horizon bias injection or interactive campaign effectiveness;
- robustness across models, prompts, operating points, or stochastic samples;
- generalization or confirmatory inference; or
- authorization to execute M29-B.

The battery is deliberately small, synthetic, offline, and evaluated on one
model-service snapshot without repeated stochastic sampling. The results are
therefore useful for design diagnosis, not effect-size estimation.

## Gate 2 disposition and next research action

M29-A itself satisfies its qualification contract. Gate 2 should nevertheless
remain `HOLD` because its scientific unlock condition requires valid hybrid
behavior beyond both `IA3-O` and `IA4-D`, which was not observed.

The next action should be a new offline design-refinement mission, not a larger
run of the same battery. It should isolate tasks where the optimizer cannot
resolve semantic strategy choice by itself and the LLM cannot reliably replace
numerical search by itself. The mission should:

1. factor each decision into semantic strategy/constraint synthesis and
   numerical candidate optimization;
2. add coupled multi-step counterfactuals with delayed evidence, expiring
   validity, and strategy-dependent tool selection while retaining no physical
   actuation;
3. use error-focused fixtures derived from the observed budget, sensitivity,
   validity, operating-point, and contradiction misses;
4. diagnose whether the graph representation helps only when memory retrieval
   or relational queries are genuinely required, rather than merely restating
   flat facts; and
5. define an unlock criterion based on paired complementarity, not raw success
   alone: the hybrid must solve registered cells that `IA3-O` cannot solve from
   numeric state and that `IA4-D` cannot solve without the shared optimizer.

Only a new, independently audited result meeting that criterion should reopen
the proposal for bounded simulator execution.
