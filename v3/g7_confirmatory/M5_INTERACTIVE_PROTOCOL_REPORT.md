# M5 offline interactive-tool protocol report

## Outcome

M5 now provides a content-addressed, fail-closed protocol for comparing an IA4
decision core with an IA3 non-LLM control over the same candidate surface and
one exact read-only tool interface. The implementation is offline: both
episodes use recorded fixture decisions and a content-addressed tool-result
fixture. No model transport, tool executor, embedding service, simulator,
detector, calibration input, evaluation seed, or actuator is reachable.

The checked-in contract is
`artifacts/ia4_interactive_contract_m5.json`, governed by
`ia4_interactive_contract.schema.json`. Its protocol ID is
`m5proto_d3de5a4295d510abbe1b4b20dd52dc2fd23de72f67a0da8e9d6b118085a39d49`.
It layers on the unchanged M3/M4 search surface
`surface_e8b57b491d4439045a988a2288c6601703fbce4ee9eee06ce6ffed710ca50412`.

## Why the protocol is a separate layer

The M3 surface already content-addresses the candidate library, K/A/resource
payload, strategy cards, reward contract, and tool schema versions. Changing
that surface in place would invalidate the preserved M4 receipts. M5 therefore
adds a second content-addressed protocol layer that binds:

- the exact M3/M4 base-surface ID;
- complete JSON input and output schemas for each enabled tool;
- the permitted state transitions;
- per-turn and per-episode resource caps;
- tool-result lineage and information level;
- fail-closed and retry behavior; and
- the matched IA3 control requirements.

Any change to these fields produces a new M5 protocol ID while leaving prior
milestone evidence immutable.

## State machine

The session has four explicit states:

| State | Accepted input | Next state |
|---|---|---|
| `awaiting_model` | Valid tool request | `awaiting_tool_result` |
| `awaiting_tool_result` | Exact bound fixture result | `awaiting_model` |
| `awaiting_model` | Valid plan, refusal, or no action | `terminal` |
| Any nonterminal state | Presented invalid input | `failed_closed` |

Only one call can be outstanding. A terminal decision is immutable. A
presented invalid model turn consumes the turn before the session fails closed,
so malformed output cannot obtain free retries. An invalid tool result also
fails the episode; the protocol does not silently rerun a call or substitute a
different result.

The model-request receipt binds the protocol ID, base-surface ID, actor rung,
decision-core ID, turn index, remaining budgets, complete initial decision
context, transcript, and the exact next-response schema. Every accepted turn
records the request hash, decision payload, response hash, model identity, and
token accounting.

## Tool boundary

M5 enables only `observe_state`. Its input requires an explicit unique subset
of `prior_alarm` and `voltage_pu`; its output requires the schema version,
window, time, and both typed values. Both input and output reject additional
fields.

The tool is fixed as:

- side effect: `read_only_no_time_advance`;
- information axis: partial grid knowledge;
- simulation-time advance: 0 seconds;
- outer-rollout cost: 0; and
- runtime execution authorization: false.

`bounded_rollout` remains declared on the older shared search surface but is
not enabled by M5. This is intentional: the first interactive milestone tests
protocol correctness without a simulator or a hidden search-budget upgrade.
Requesting the disabled tool, detector information, an extra argument, a
non-finite output, a mismatched schema, time advancement, rollout consumption,
or information above K terminates the episode as failed closed.

## Episode budgets

The offline contract caps each episode at:

- three decision turns, with one reserved for a terminal decision;
- one tool call;
- zero outer rollouts;
- 512 completion tokens per accepted turn; and
- 8,192 total model tokens.

The two checked-in fixture episodes use two decision turns, one tool-result
fixture, zero rollouts, and zero model tokens. Zero tokens are appropriate only
because no model ran; they are not evidence of a compute-matched live model
comparison.

## Matched IA3 control

`MatchedIA3ObserveThenSelect` uses the exact same M5 protocol. It requests the
same fields, receives the same content-addressed result, applies a frozen
threshold rule, and returns one unchanged candidate from the same ordered
library. The fixture artifact verifies all of the following:

- identical protocol and base search-surface IDs;
- identical tool arguments and full tool result;
- identical fixture lineage;
- identical tool-call and rollout counts;
- identical terminal candidate in the deterministic interface fixture; and
- successful common `PlanValidator` admission for both rungs.

The separate IA4 fixture episode mirrors this interaction only to qualify the
state and schema boundary. It is not an LLM episode. A later live comparison
must account for actual model tokens, calls, wall-clock cost, and any matched
IA3 search compute rather than treating these zero-token fixture receipts as a
scientific compute match.

## Common validation

Both terminal fixture plans select
`cand_e203a116322e41264fda` (`step_corner`, `DER_A`, 30 kW). The common
validator checks candidate lineage, rung, strategy-card bounds, device and P/Q
authority, tool-call lineage, K, and the dual physical budget. Each synthetic
episode is admitted as one effective action consuming one perturbed window and
0.083333 kVAh relative to the synthetic benign command.

This validator result establishes interface compatibility only. There is no
delivery, device acceptance, realized P/Q, grid trajectory, alarm, or harm
measurement.

## Adversarial checks

The offline tests cover:

- request determinism and exact surface binding;
- exact tool JSON-schema validation;
- IA3/IA4 capability parity;
- valid tool-to-terminal lifecycles for both rungs;
- explicit safety-refusal and no-action terminal states;
- terminal immutability;
- wrong-state messages and multiple outstanding-call prevention;
- extra fields, invalid or reused call IDs, and disabled tools;
- K escape and hidden detector fields;
- request-hash, token-accounting, candidate, and tool-lineage drift;
- wrong result identity and fixture lineage;
- non-finite results, silent simulation-time advance, and rollout cost; and
- a second tool request above the protocol cap.

## Evidence boundary and next gate

M5 supports claims about protocol completeness, replayability, resource
accounting, matched-interface construction, and fail-closed behavior. It does
not support claims about model tool use, planning quality, physical harm,
detector evasion, IA4 advantage, or campaign readiness.

That two-turn model replay is now complete as M6 and is documented in
`M6_INTERACTIVE_MODEL_REPORT.md`. The next defensible gate is a paired
counterfactual fixture test that asks whether changing only the tool result
changes candidate choice or refusal in a preregistered direction. Enabling a
real tool, rollout, simulator, detector, or evaluation partition remains a
different and later gate.
