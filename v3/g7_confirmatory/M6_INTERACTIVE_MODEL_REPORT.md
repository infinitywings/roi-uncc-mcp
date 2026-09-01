# M6 bounded interactive-model qualification report

## Outcome

The configured `qwen3.6-35b-a3b` endpoint completed the M5 protocol in two
model turns after two preserved fail-closed compatibility attempts. The model
requested the exact read-only `observe_state` interface on turn 0, received a
content-addressed fixture injected by the harness without tool execution, and
returned a terminal candidate plan on turn 1.

The successful create-once receipt is
`artifacts/ia4_interactive_model_smoke_m6_attempt3_fixed_call_id.json`. It is
governed by `ia4_interactive_model_smoke.schema.json` and binds overlay
`m6overlay_87f514f9a25a63a8a49793c70cd1b62f4bbdb0c859e2568e41ea2fd6e0217a9c`
to M5 protocol
`m5proto_d3de5a4295d510abbe1b4b20dd52dc2fd23de72f67a0da8e9d6b118085a39d49`.

This is model-interaction evidence, but not real-tool or grid evidence. No tool
executor, embedding service, simulator, detector, calibration input,
evaluation seed, or actuator was accessible.

## Frozen execution overlay

The M6 overlay authorizes only model transport and fixture injection. It fixes:

- one model discovery request;
- at most two completion requests;
- model `qwen3.6-35b-a3b`;
- development seeds 8101 and 8102 for turns 0 and 1;
- temperature 0;
- 512 output tokens per turn;
- the unchanged M5 protocol and M3/M4 search-surface IDs;
- exact call ID `call_observe_model_0001`;
- turn 0 as tool-request-only;
- one injected `observe_state` fixture;
- turn 1 as terminal-only; and
- no retry within an attempt.

The base offline M5 artifact remains transport-disabled. M6 is a separate,
content-addressed authority layer rather than a mutation of prior evidence.

## Preserved attempt sequence

### Attempt 1: provider-schema failure

Artifact: `artifacts/ia4_interactive_model_smoke_m6_attempt1.json`

Model discovery succeeded, but the first completion POST returned HTTP 500
before any completion record was produced. The provider-guided schema included
`uniqueItems`, which the endpoint's guided decoder did not accept. The exact
failed receipt remains immutable.

This attempt also exposed an accounting bug: the artifact counted the
successful discovery but not the attempted completion POST because counters
were incremented only after a response. The implementation now counts requests
before transport. The historical artifact is not rewritten and therefore
retains `network_requests=1` and `completion_requests=0`; its error and absence
of a completion make the attempted POST visible in the narrative evidence.

The compatibility fix removes `uniqueItems` only from the provider's guided
schema. The independent M5 strict validator still rejects duplicate requested
fields, so endpoint compatibility does not weaken the accepted protocol.

### Attempt 2: call-lineage mismatch

Artifact: `artifacts/ia4_interactive_model_smoke_m6_attempt2_compat.json`

The corrected provider schema produced one valid JSON tool request for the
right tool and fields. The model chose call ID `obs_001`; the M5 parser requires
the `call_...` lineage namespace. The episode failed closed before fixture
injection and made no second completion request.

This was a contract-design gap: the provider schema allowed an arbitrary
string while the independent parser enforced a narrower identifier. Call IDs
are harness lineage, not a useful model decision. M6 therefore freezes the
exact call ID in the execution overlay and guided schema.

### Attempt 3: complete interactive replay

Artifact:
`artifacts/ia4_interactive_model_smoke_m6_attempt3_fixed_call_id.json`

- Model discovery requests: 1
- Completion requests: 2
- Total network requests: 3
- Turn seeds: 8101, 8102
- Turn 0 prompt/completion/total tokens: 2756 / 260 / 3016
- Turn 1 prompt/completion/total tokens: 3169 / 287 / 3456
- Episode total model tokens: 6472
- Tool requests accepted: 1
- Outer rollouts: 0
- Real tools executed: 0
- Terminal state: `terminal`
- Terminal decision: `plan`
- Candidate: `cand_e203a116322e41264fda`

The model requested `prior_alarm` and `voltage_pu`. The injected fixture
returned `prior_alarm=false` and `voltage_pu=0.99`. The terminal response cited
both values, retained the exact tool-call ID, and selected the unchanged
`step_corner` candidate. Offline replay through the common `PlanValidator`
confirmed valid candidate lineage, K/A/tool parity, and dual-budget admission
for the synthetic 30 kW action.

## What M6 establishes

M6 supports the narrow statements that this model can:

- follow a stage-locked two-turn JSON protocol;
- request an enabled read-only tool with valid arguments;
- retain the exact call ID through a tool-result round trip;
- refer to injected typed values in a terminal rationale;
- select one unchanged content-addressed candidate; and
- remain inside the declared turn, token, tool, rollout, information, and
  physical-plan contracts in this synthetic fixture.

The two fail-closed attempts are part of the result. They identified a provider
schema compatibility constraint and a harness-owned lineage field that should
not have been left to free generation.

## What M6 does not establish

The observed rationale is not evidence of strong attacker reasoning. It
describes `voltage_pu=0.99` as stable and characterizes the selected action in
terms of safety or stability. The model may have selected the same first
candidate regardless of the tool result. Mentioning a value is not proof that
the value causally changed the decision.

M6 therefore does not establish:

- causal use of tool information;
- better candidate ranking than IA3;
- harmful or stealthy grid behavior;
- correct power-system mechanism reasoning;
- robustness to conflicting, missing, delayed, or noisy results;
- real tool execution or simulator integration;
- detector evasion; or
- evaluation or campaign readiness.

## Next experiment: counterfactual tool-use qualification

Before enabling a real tool, the next model experiment should freeze a paired
counterfactual fixture design over the same protocol and candidate surface.
At minimum it should compare:

1. low versus high `voltage_pu` with all other fields fixed;
2. `prior_alarm=false` versus `true` with voltage fixed;
3. an informative result versus an explicitly unavailable result;
4. a tool result versus a semantically equivalent value already present in the
   initial observation; and
5. true-history versus shuffled-result lineage.

The primary qualification outcome is not whether the rationale repeats a
number. It is whether candidate choice, refusal, or no-action changes in the
preregistered direction under paired counterfactual swaps, while the matched
IA3 controller receives the same fixtures and resource accounting. Tool-result
sensitivity, invalid-response rate, safety-refusal rate, decision entropy,
candidate switching, tokens, and latency should all be reported.

Only after that causal fixture gate passes should the project consider a real
read-only observation adapter. A real adapter requires a new execution overlay,
independent side-effect review, and a receipt proving zero simulation-time
advance. Rollout, detector, actuation, and evaluation access remain later and
separate gates.
