# M22 Current-Service Tool-Use Regression Report

## Outcome

M22 passed its preregistered current-service regression. The running
`qwen3.6-35b-a3b` service completed both mirrored M7 conditions, requested the
declared read-only interface before choosing a plan, selected the fixture
argmax in both conditions, and switched candidates when the target
sensitivity values were reversed.

The create-once contract and receipt are:

- `artifacts/m22_current_service_regression_attempt1/contract.json`
  (SHA-256
  `83b3dcd4ad1a2d4bbafd19c8b06e06bb16c9da1dad022ffa3b0449bcf4b7f0af`);
  and
- `artifacts/m22_current_service_regression_attempt1/receipt.json`
  (SHA-256
  `1235baa796414dc53b0ba2580c6c6b0fec8573ae96d6cd2d46e4ea690642f7e8`,
  receipt ID
  `m22receipt_a276ddad8803232047dd395209fa527e1e14279096b90da3591d63ed84baeb98`).

The receipt is classified `PRELIMINARY_ONLY`. Its verifier returned no issues.
This result qualifies the current model transport, structured two-turn
protocol, fixture use, and common plan-validation boundary. It does not
qualify an autonomous attacker or a physical-grid experiment.

## Preregistered boundary

M22 reused the exact M7 protocol, search surface, candidate library, and tool
schema. It was fixed before model transport as follows:

- attack-development seeds `8105` and `8106`;
- one model-discovery request and at most four completion requests;
- at most 512 output tokens per completion, temperature zero, and no retry;
- two target-only candidates with the same strategy and 30 kW magnitude;
- one harness-injected `observe_sensitivity` result per condition;
- matched IA3 and IA4 access to the same surface and information;
- no real tool execution, simulator, detector, defense, embedding access, or
  physical actuation; and
- no access to final evaluation data or seeds `9101` through `9112`.

M21 was used only as a downstream timing prerequisite. Its values were not
shown to the model. The contract binds the following governing evidence:

| Source | SHA-256 |
|---|---|
| Frozen experiment specification | `79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d` |
| M18 preliminary-only gate | `e31a49d758700a3d30e4d7e3d5469b831b3f52370954fa92238eac6aa4dc3e9d` |
| M7 interface implementation | `325b5ae4c94e420b213cb3a9036da8a2b49ec9a989bf2821c5ef37f2e617af57` |
| M7 original contract | `4cef8444c56c40ff493ed3add9847d43d9d12c72f9f1714597e7566109d26de2` |
| M21 timing artifact | `2aa7bbc10bcd20f964f9a7cbcad9a70b6058b8e652acbc68bdbea953bc7e022d` |

The executable M22 implementation is SHA-256
`3d9561f0d41aca5730c1c1a2d217e6839e619d7fffc70d42bdfaa47798f8f79e`.
Both M18 action requests bind this exact code hash, the frozen specification,
the existing model-service identity, and the M22 request budget.

## Current service and transport

The existing service was discovered, not started or restarted. It reported:

| Field | Value |
|---|---|
| Model ID | `qwen3.6-35b-a3b` |
| Runtime owner | `vllm` |
| Model root | `QuantTrio/Qwen3.6-35B-A3B-AWQ` |
| Maximum model length | 262,144 tokens |

The complete run used five network requests: one discovery request and four
completion requests. Token accounting across the four completions was 11,291
prompt tokens, 1,257 completion tokens, and 12,548 total tokens. No model or
service configuration was changed.

## Paired causal result

Both episodes reached a valid terminal state and used the exact declared
tool-call ID. The tool result was a frozen synthetic fixture injected by the
harness; the model did not contact a live tool.

| Condition | Sensitivity argmax | IA4 selection | Validated plan | Result |
|---|---|---|---|---|
| `pair_left` | `DER_A` | `cand_322228c6707998fea51c` / `DER_A` | 30 kW, 0.083333 kVAh | correct |
| `pair_right` | `DER_B` | `cand_bc73d19dea133043082f` / `DER_B` | 30 kW, 0.083333 kVAh | correct |

The primary endpoint therefore passed: directional accuracy was 2/2 and the
selected candidate changed under the mirrored intervention. Both terminal
plans passed the same schema, authority, and apparent-energy validator.

## Comparator interpretation

The matched deterministic IA3 argmax control also scored 2/2 on the same
fixtures. Consequently, M22 provides no evidence that IA4 is better than IA3.
That is the scientifically useful interpretation: the current LLM can follow
the structured protocol and condition its selection on an allowed observation,
but this toy rule remains fully expressible by a static policy.

The result also does not show that the model learned an attack strategy,
discovered a new strategy, combined tools over time, adapted to a detector,
or generated a subtler long-horizon bias attack. The candidate set, arithmetic
rule, and synthetic sensitivity values were supplied by the harness.

## Verification

The independent receipt check returned `issues: []`. The full confirmatory
harness suite passed 367 tests. The frozen roadmap and experiment
specification retained their expected SHA-256 values:

- roadmap report:
  `c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b`;
- experiment specification:
  `79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d`.

## Scientific boundary and next gate

M22 establishes only a current-service, synthetic-fixture tool-use regression.
It does not establish real-tool safety, simulator readiness, grid impact,
stealth, detector or defense effectiveness, IA4 superiority, statistical
significance, generalization, or confirmatory evidence.

The next bounded gate should replace the synthetic sensitivity fixture with a
content-addressed empirical system-identification source generated under the
M21 three-window timing rule. A separate adapter qualification should then
prove that the same read-only schema can expose only the registered empirical
fields, with no simulation-time advance or actuation. Only after those two
gates pass should an LLM-selected plan be connected to an ephemeral simulator.
This ordering distinguishes genuine evidence-guided interaction from prompt
compliance and preserves a matched IA3 comparator for later ablation.
