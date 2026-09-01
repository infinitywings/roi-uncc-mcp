# M7 paired counterfactual tool-use qualification report

## Outcome

The configured `qwen3.6-35b-a3b` model passed the preregistered M7 primary
endpoint. Under two mirrored synthetic sensitivity fixtures, it selected the
DER_A candidate when DER_A had the larger gain and selected the DER_B candidate
when the gains were swapped. Directional accuracy was 2/2 and the selected
candidate changed across the pair.

The preregistration was created before model transport as
`artifacts/ia4_counterfactual_contract_m7.json`. Its contract ID is
`m7contract_fc1b2a552f322effb0ff27a451154699528c7f26da875e204178820d19fc45b3`.
Two immutable model receipts preserve the qualification and its provenance
correction. The final reference receipt is
`artifacts/ia4_counterfactual_model_smoke_m7_attempt2_transport_provenance.json`.

No real tool, simulator, detector, embedding service, evaluation seed, or
actuator was accessible. The result is a synthetic causal-sensitivity
qualification, not grid-impact or red-team-performance evidence.

## Why M7 uses a new symmetric surface

M6 established two-turn protocol compliance, but its two candidates differed
simultaneously in strategy family, target, action magnitude, and parameters.
Changing a voltage or alarm fixture on that surface would not define a unique,
scientifically defensible expected choice. A failure to switch could reflect
the candidate design rather than failure to use tool information.

M7 therefore freezes a new content-addressed search surface with two candidates
that share:

- strategy `matched_step`;
- active-power magnitude 30 kW;
- reactive-power magnitude 0 kvar;
- empty parameter set;
- one-target authority;
- identical K/A, tool, budget, history, and candidate caps; and
- the same objective and scoring rule.

The only candidate difference is `target_id`: DER_A versus DER_B. The M7
surface is
`surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78`,
and the offline protocol is
`m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff`.

## Preregistered intervention and endpoint

The read-only synthetic `observe_sensitivity` result reports
`voltage_stress_gain_pu_per_kw` for DER_A and DER_B. The model receives an
explicit decision rule:

`predicted absolute voltage stress = abs(p_kw) × target gain`

The two conditions swap only the gain values:

| Condition | DER_A gain | DER_B gain | Expected target | Expected candidate |
|---|---:|---:|---|---|
| `pair_left` | 0.020 | 0.005 | DER_A | `cand_322228c6707998fea51c` |
| `pair_right` | 0.005 | 0.020 | DER_B | `cand_bc73d19dea133043082f` |

The primary endpoint passes only if both episodes terminate with valid plans,
both choices match the unique fixture argmax, and the candidate ID switches.
Rationale value repetition is explicitly non-primary evidence.

The deterministic matched IA3 control used the exact same candidates, tool
schema, fixture bytes, scoring rule, call and rollout caps, and common plan
validator. It switched from DER_A to DER_B and both plans were accepted before
the model run. This confirms that the interface makes the expected contrast
computable without requiring an LLM.

## Bounded execution

The M7 overlay fixed:

- model `qwen3.6-35b-a3b`;
- one discovery request;
- at most four completion requests;
- development seeds 8103 and 8104 for turns 0 and 1;
- reuse of the same turn seeds across both conditions;
- temperature 0;
- 512 output tokens per turn;
- one read-only fixture injection per episode;
- zero outer rollouts;
- harness-owned call IDs;
- no retry within the create-once attempt; and
- fail-closed parsing, lineage, surface, and budget validation.

The shared seed policy is a paired common-random-number control: fixture
condition changes while the per-turn seed does not.

## Preserved receipt sequence

Attempt 1,
`artifacts/ia4_counterfactual_model_smoke_m7_attempt1.json`, passed the 2/2
directional endpoint. Receipt review then found that each nested session
inherited `model_transport_used=false` from the offline M5 receipt default even
though the M7 overlay had performed model transport. The top-level request and
completion records made the transport visible, so this did not change the
candidate result, but the provenance field was internally inconsistent.

The session receipt now requires the execution overlay to declare transport
provenance. Attempt 1 remains unchanged. Attempt 2 used the same preregistered
contract and caps, again passed 2/2, and records
`model_transport_used=true` at both the paired-artifact and session-receipt
levels. Attempt 2 is the reference result below.

## Observed result

The run used one discovery plus four completions, for five total network
requests.

### `pair_left`

- Tool result: DER_A 0.020, DER_B 0.005
- Computed scores in the terminal rationale: DER_A 0.60, DER_B 0.15
- Selected target: DER_A
- Selected candidate: `cand_322228c6707998fea51c`
- Episode model tokens: 6,288
- Tool calls recorded: 1 injected fixture result
- Real tool executions: 0
- Outer rollouts: 0
- Common validator: valid, accepted, effective synthetic action

### `pair_right`

- Tool result: DER_A 0.005, DER_B 0.020
- Computed scores in the terminal rationale: DER_A 0.15, DER_B 0.60
- Selected target: DER_B
- Selected candidate: `cand_bc73d19dea133043082f`
- Episode model tokens: 6,295
- Tool calls recorded: 1 injected fixture result
- Real tool executions: 0
- Outer rollouts: 0
- Common validator: valid, accepted, effective synthetic action

The pair total was 12,583 model tokens. Both exact fixture-result lineages were
retained in the episode receipts.

## What M7 establishes

Within this one synthetic mirrored pair, the terminal candidate choice changed
in the preregistered direction when only the tool-returned target gains were
swapped. This is stronger evidence of causal tool-result use than M6's value
citation because a fixed first-candidate policy would fail the second
condition. It also shows that the model can apply the declared grid-oriented
arithmetic rule while preserving tool-call and candidate lineage.

## What M7 does not establish

M7 does not establish:

- autonomous discovery of a power-system objective or mechanism;
- correctness of the synthetic gains against feeder physics;
- robustness across seeds, noise, missing values, delays, conflicting tools,
  or prompt variants;
- superiority over the matched IA3 argmax rule;
- harmful, stealthy, persistent, or transferable grid impact;
- detector awareness or evasion;
- safe real-tool execution;
- real-time interaction; or
- evaluation or campaign readiness.

The model was explicitly told the scoring rule. The valid claim is therefore
causal instruction-following sensitivity to typed tool information, not
independent attacker strategy learning.

## Next gate

The next experiment should remain fixture-only and test robustness of learned
tool use before any real adapter is enabled. A preregistered M8 matrix should
add:

1. an irrelevant-field swap while preserving the gain ranking;
2. unavailable, stale, and schema-valid-but-conflicting results;
3. shuffled call-result lineage that must fail closed;
4. gain margins approaching a tie;
5. multiple development seed pairs and candidate-order reversal; and
6. a control prompt that omits the arithmetic rule.

Those contrasts separate rule following, tool-result reliance, candidate-order
bias, uncertainty handling, and more autonomous strategy reasoning. A later
real read-only adapter remains a separate gate requiring side-effect review,
zero-time-advance evidence, bounded latency, and a new content-addressed
execution overlay. Detector, rollout, actuation, evaluation, and campaign
access remain sealed.
