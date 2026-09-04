# M29-S Executor Backbrief

## Mission understanding

M29-S will diagnose the semantic-compilation bottleneck exposed by M29-R and
test whether bounded, typed validator interaction can repair it. The study is
compiler-only and `PRELIMINARY_ONLY`: it will not optimize or execute attack
actions, advance simulator time, or reopen M29-B.

The central causal question is not whether a longer prompt raises aggregate
accuracy. It is whether an agent that can inspect visible evidence, retrieve a
scoped doctrine passage, validate a draft, and revise once can produce a more
accurate typed strategy program than both a matched single-pass LLM and a
strong deterministic semantic compiler on disjoint held-out conditions.

## Acceptance-criteria interpretation

1. **Disjointness.** M29-S will use 16 development and 16 held-out conditions.
   No condition ID, latent-parameter tuple, semantic digest, rendered evidence
   bytes, development seed, or held-out seed may overlap M29-R.
2. **Independent truth.** Each slot oracle will be generated from the latent
   specification before rendering. Tested arms will receive only the rendered
   evidence and their registered corpus view.
3. **Matched visibility.** The deterministic compiler and matched LLM arms will
   receive byte-identical evidence and corpus views for each condition. The
   retrieval factor may change selected passages only.
4. **Non-answer-revealing tools.** Validator feedback may identify schema,
   provenance, contradiction, authority, validity, or consistency error
   classes. It may not return an expected value, oracle field, corrected
   program, score, label, or plan.
5. **Field-level endpoints.** Doctrine, direction, authority, validity,
   topology, budget, objective weights, cooldown, and evidence lineage will be
   scored separately. All-slot exactness remains conjunctive.
6. **Held-out decision rule.** A renewed end-to-end complementarity study may
   be proposed only if the validator-guided agent clears the preregistered
   held-out threshold and exceeds both the single-pass LLM and strong
   deterministic compiler on paired cells.
7. **No downstream authorization.** Even a passing M29-S result cannot
   authorize M29-B, simulation, detector/defense interaction, physical
   actuation, or final evaluation.

## Proposed arm ladder

| Arm | Semantic compiler | Retrieval | Validator interaction | Model calls per cell |
|---|---|---:|---:|---:|
| `IA3-SX` | Strong deterministic evidence parser | Matched corpus view | Internal deterministic checks only | 0 |
| `IA4-C1` | Qwen single pass | No | No | 1 |
| `IA4-C1R` | Qwen single pass | Yes | No | 1 |
| `IA4-CR` | Qwen draft and one revision | No | One bounded diagnostic turn | 2 |
| `IA4-CRR` | Qwen draft and one revision | Yes | One bounded diagnostic turn | 2 |
| `IA5-OC` | Independent latent oracle compiler | Not applicable | Not applicable | 0 |

The two revise arms always receive exactly two model calls per cell. If the
initial draft has no validator findings, the second turn must return a
content-identical confirmation. This preserves request-count parity and avoids
conditioning cost on initial correctness.

## Scenario and split design

Each split contains eight mirrored pairs and covers:

- doctrine and effect-direction selection;
- authority and supersession resolution;
- temporal validity and expiry;
- topology and target-scope composition;
- resource-budget and action-count composition;
- objective-weight and cooldown composition;
- delayed evidence and evidence-lineage completeness; and
- retrieval-dependent doctrine selection.

Development and held-out splits will use different doctrine identifiers,
target permutations, authority orderings, temporal windows, budgets, numeric
values, paraphrase templates, distractor records, and corpus locations. The
same construct classes may appear in both splits, but no answer-bearing bytes
or parameter tuple may repeat.

## Tool boundary

The inspect-revise arms may use two local deterministic tools:

- `inspect_visible_records`: filter and order only the evidence records already
  present in the arm's input, returning source IDs and visible text without
  adding facts;
- `validate_strategy_draft`: return a set of bounded error codes and the
  affected slot names, without expected values or a corrected draft.

Allowed validator codes include `schema`, `evidence_unknown`,
`evidence_missing`, `authority_conflict`, `expired_record`,
`topology_inconsistent`, `budget_inconsistent`, `weights_inconsistent`, and
`cooldown_inconsistent`. Tool transcripts are content-addressed and included
in the cell receipt. The independent auditor will scan every tool result for
oracle values, expected-output keys, hidden labels, and unregistered fields.

## Call and resource budget

For each 16-condition split:

- `IA4-C1`: 16 calls;
- `IA4-C1R`: 16 calls;
- `IA4-CR`: 32 calls;
- `IA4-CRR`: 32 calls.

The exact maximum is 96 calls for development and 96 calls for held-out,
giving 192 additional read-only chat calls. Conservative cumulative usage
would be 293/1000 after both registered attempts. There are no retries. A
model-discovery GET is not a chat call. Existing embedding receipts may be
reused only after identity verification; a new retrieval index may call only
the already-running GPU embedding service under a separately counted,
create-once preflight.

## Primary endpoints and proposed thresholds

Held-out endpoints will include per-slot exact accuracy, evidence-lineage
accuracy, all-slot program accuracy, mirrored-pair correctness, invalid output,
validator-tool findings, repair conversion, repair regression, retrieval
margin, and call/token cost.

A proposal for a later end-to-end study requires all of the following:

- `IA4-CRR` all-slot success at least 12/16;
- at least 6/8 correct mirrored pairs;
- zero schema, provenance, or admissibility violations in final drafts;
- at least four more paired-cell successes than `IA4-C1R`;
- at least four more paired-cell successes than `IA3-SX`;
- at least 50% repair conversion among initially incorrect `IA4-CRR` drafts;
- no more than one repair regression among initially correct drafts;
- retrieval margin at least two successes on retrieval-required cells with no
  more than one non-retrieval degradation; and
- primary and independent auditors both returning `issues=[]`.

These thresholds authorize only a proposal for a new complementarity study.

## Assumptions

1. Construct coverage can be preserved while making all M29-S answer-bearing
   bytes and latent parameters disjoint from M29-R.
2. Field-name and error-class feedback is useful without disclosing correct
   values.
3. A deterministic compiler built only from visible records is a meaningful
   stronger baseline rather than a disguised oracle.
4. The current qwen endpoint and existing GPU embedding service remain
   available with their registered identities.
5. A 16-condition held-out split is adequate for a strict qualification gate,
   but not for population-level effect estimation.

## Risks and mitigations

- **Tool leakage:** error messages could reveal answers indirectly. Mitigation:
  freeze a finite code vocabulary, prohibit values in results, and run an
  independent transcript scanner.
- **Deterministic-baseline leakage:** structured parsing could consume hidden
  latent fields. Mitigation: construct each arm from serialized visible input
  and audit field access.
- **Development overfitting:** prompt or tool changes could follow held-out
  observations. Mitigation: freeze all execution sources and thresholds after
  the development receipt and before held-out registration.
- **Retrieval confounding:** retrieved passages could add authoritative facts.
  Mitigation: bind one common frozen corpus and treat retrieval as selection,
  never source creation.
- **Exact-match brittleness:** harmless ordering differences could count as
  errors. Mitigation: canonicalize only registered unordered sets; preserve
  semantic value equality for all substantive fields.
- **False progress from action coincidence:** M29-R showed exact plans under
  wrong semantics. Mitigation: M29-S has no action-level success endpoint.

## Implementation and verification approach

1. Add an M29-S design module, schemas, corpus, prompt contracts, and a
   content-addressed design fixture.
2. Add separate development and held-out runners with create-once roots and
   explicit cumulative authorization accounting.
3. Add a primary verifier and a non-importing independent auditor that rebuild
   all endpoints from serialized evidence.
4. Add focused positive and single-fault tests for disjointness, tool leakage,
   parity, response parsing, revision accounting, threshold logic, and access
   seals.
5. Run the complete offline suite, create a plan-validation gate, and execute
   no live call until that gate is GO.

The three mission-guard warnings concern superseded M24/G4 runtime findings.
M29-S neither depends on nor asserts those findings, so they do not alter this
offline compiler plan.
