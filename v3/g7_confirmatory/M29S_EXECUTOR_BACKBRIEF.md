# M29-S Executor Backbrief

## Mission understanding

M29-S diagnoses the semantic-compilation bottleneck exposed by M29-R and
separates three candidate mechanisms: task-interface decomposition,
validator-guided agent revision, and scoped retrieval. The study is
compiler-only and `PRELIMINARY_ONLY`; it cannot optimize or execute attack
actions, advance simulator time, or reopen M29-B.

The original six-arm plan compared one-call single-pass arms with two-call
validator arms and therefore confounded validator information with an extra
model call. It also changed the interaction protocol and output interface at
the same time. PI directive `jrn_01M1PME90R32PV7GXQA9ZEEG93` and decision
`dec_01M1PMESQHHNCE5XK066EQB79X` approve an equal-call factorial refinement
before any live M29-S request.

## Causal questions

1. Does a staged `EvidenceLedger -> SemanticSlots -> StrategyProgram`
   interface improve exact semantic compilation under matched calls and
   visible evidence?
2. Does bounded validator feedback improve the second draft beyond an
   equal-cost neutral self-revision?
3. Does scoped retrieval improve compilation, and does its effect depend on
   the interface or feedback loop?
4. How much of any two-call improvement is explained by additional
   deliberation alone?

## Acceptance-criteria interpretation

1. **Disjointness.** M29-S uses 16 development and 16 held-out conditions.
   No condition ID, seed, latent tuple, semantic digest, rendered evidence
   bytes, or answer-bearing doctrine identifier may overlap M29-R.
2. **Independent truth.** Slot oracles are generated from latent
   specifications before rendering and are unavailable to tested arms.
3. **Equal-call causal matrix.** Every factorial LLM arm uses exactly two
   calls per cell. One-call arms are reference baselines only.
4. **Independent factors.** Interface, validator feedback, and retrieval are
   crossed independently. No unregistered factor may change between a
   contrast pair.
5. **Non-answer-revealing tools.** Validator results contain allowlisted error
   classes and affected slot names only. They cannot contain expected values,
   corrected programs, oracle fields, scores, or success labels.
6. **Field-level endpoints.** Evidence selection, authority, validity,
   doctrine, direction, topology, budgets, objective weights, cooldown, and
   lineage are scored separately. All-slot exactness remains conjunctive.
7. **Held-out decision rule.** A later end-to-end study may be proposed only
   if the staged validator-guided retrieval arm clears the frozen threshold
   and exceeds its matched interface, feedback, and deterministic controls.
8. **No downstream authorization.** A passing result cannot authorize M29-B,
   simulation, detector or defense interaction, physical actuation, or final
   evaluation.

## Registered arm ladder

### Non-LLM controls

| Arm | Compiler | Calls per cell | Purpose |
|---|---|---:|---|
| `IA3-SX` | Strong deterministic visible-evidence parser | 0 | Non-LLM semantic baseline |
| `IA5-OC` | Independent latent oracle compiler | 0 | Attainable ceiling, not an attacker |

### One-call reference arms

| Arm | Interface | Retrieval | Calls | Purpose |
|---|---|---:|---:|---|
| `IA4-C1` | Flat final program | No | 1 | One-shot deliberation and cost reference |
| `IA4-C1R` | Flat final program | Yes | 1 | One-shot retrieval reference |

These arms are not valid controls for the validator effect because they use
fewer calls than the causal factorial arms.

### Equal-call causal factorial

| Arm | Interface | Second-turn feedback | Retrieval | Calls |
|---|---|---|---:|---:|
| `IA4-FS` | Flat | Neutral self-review | No | 2 |
| `IA4-FSR` | Flat | Neutral self-review | Yes | 2 |
| `IA4-FV` | Flat | Validator diagnostics | No | 2 |
| `IA4-FVR` | Flat | Validator diagnostics | Yes | 2 |
| `IA4-SS` | Staged | Neutral self-review | No | 2 |
| `IA4-SSR` | Staged | Neutral self-review | Yes | 2 |
| `IA4-SV` | Staged | Validator diagnostics | No | 2 |
| `IA4-SVR` | Staged | Validator diagnostics | Yes | 2 |

Every two-call arm emits an initial draft and a final draft. Neutral
self-review receives only a fixed instruction to inspect the first draft and
return a final answer. Validator arms receive one deterministic diagnostic
object. If there are no findings, the second call must return a
content-identical confirmation.

## Staged task interface

The staged response contains three typed artifacts:

1. `EvidenceLedger`: active, superseded, expired, and unresolved evidence IDs,
   plus visible authority ordering.
2. `SemanticSlots`: one value and supporting-evidence list for each registered
   semantic field.
3. `StrategyProgram`: a deterministic projection of the submitted slot values;
   projection and canonicalization cannot repair or change substantive values.

The flat interface emits only `StrategyProgram`. Both interfaces receive
byte-identical evidence and corpus views within matched retrieval cells.

## Tool boundary

The agent state machine permits only:

- `inspect_visible_records`, which filters and orders records already present
  in the request without adding facts;
- `validate_strategy_draft`, which returns a content-addressed list of
  allowlisted error code and slot pairs; and
- `submit_final_program`, which freezes the second response with no retry.

Allowed diagnostic codes are `schema`, `evidence_unknown`,
`evidence_missing`, `authority_conflict`, `expired_record`,
`topology_inconsistent`, `budget_inconsistent`, `weights_inconsistent`, and
`cooldown_inconsistent`.

## Scenario and split design

Each split contains eight mirrored pairs covering doctrine and direction,
authority and supersession, temporal validity, topology, resource budget,
objective weights and cooldown, delayed evidence and lineage, and
retrieval-dependent doctrine selection.

Development and held-out splits use different doctrine identifiers, target
permutations, authority orders, temporal windows, budgets, numeric values,
paraphrase templates, distractors, corpus positions, and seeds. Held-out
answer-bearing artifacts remain sealed until the development prompt and
source freeze is complete.

## Call and resource budget

For each 16-condition split:

- eight two-call factorial arms: 256 calls;
- two one-call reference arms: 32 calls;
- deterministic and oracle arms: zero calls.

The exact maximum is 288 calls per split and 576 additional calls across both
splits. Conservative cumulative use is at most `101 + 576 = 677/1000`.
There are no retries. Model discovery is not a chat call. Retrieval may use
only the already-running project GPU embedding service under separately
counted create-once receipts.

## Primary endpoints and causal contrasts

Held-out endpoints include per-slot exact accuracy, evidence-lineage accuracy,
all-slot program accuracy, mirrored-pair correctness, invalid output,
refusals, repair conversion, repair regression, and call/token cost.

Registered causal contrasts are:

- staged versus flat interface under matched feedback and retrieval;
- validator feedback versus neutral self-review under matched interface and
  retrieval;
- retrieval versus no retrieval under matched interface and feedback;
- interface-by-validator and retrieval-by-validator interactions; and
- two-call neutral self-review versus one-call reference as a secondary
  deliberation estimate.

A proposal for a later end-to-end complementarity study requires all of:

- `IA4-SVR` all-slot success at least 12/16;
- at least 6/8 correct mirrored pairs;
- zero final schema, provenance, or admissibility violations;
- at least four more held-out successes than `IA4-SSR`;
- at least four more held-out successes than `IA4-FVR`;
- at least four more held-out successes than `IA3-SX`;
- validator repair conversion at least 50 percent among initially incorrect
  `IA4-SVR` drafts;
- no more than one repair regression among initially correct drafts;
- retrieval margin at least two successes on retrieval-required cells and no
  more than one non-retrieval degradation; and
- primary and independent auditors both returning `issues=[]`.

These thresholds authorize only a proposal for a new complementarity study.

## Risks and mitigations

- **Extra-call confounding:** controlled by equal two-call factorial arms and
  separate one-call references.
- **Interface-feedback confounding:** controlled by crossing flat/staged and
  neutral/validator factors independently.
- **Tool leakage:** mitigated by a frozen diagnostic vocabulary, value-free
  outputs, and an independent transcript scanner.
- **Deterministic-baseline leakage:** mitigated by constructing every tested
  view from serialized visible input and auditing field access.
- **Held-out overfitting:** mitigated by freezing prompts, sources, thresholds,
  and development results before unsealing held-out execution.
- **Retrieval confounding:** mitigated by one frozen corpus; retrieval changes
  selection only, never source authority or facts.
- **Exact-match brittleness:** mitigated by canonicalizing registered unordered
  sets only; substantive values remain exact.
- **False progress from action coincidence:** M29-S has no action or physical
  impact endpoint.

## Implementation and verification approach

1. Add the factorial plan, strict schemas, disjoint scenario generator,
   staged compiler contracts, and content-addressed design fixture.
2. Add primary and non-importing plan auditors for disjointness, factor parity,
   call accounting, tool leakage, source binding, and access seals.
3. Add positive and single-fault tests for every invariant.
4. Pass a new plan-validation gate before any model or embedding call.
5. Implement create-once development and held-out runners. Freeze development
   sources before held-out access.
6. Execute within the registered ceiling and issue slot-level, paired, and
   factorial verdicts without opening M29-B.
