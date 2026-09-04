# M26 live empirical decision-only qualification report

## Outcome

M26 passed on its first and only create-once attempt. The already-running
`qwen3.6-35b-a3b` service completed the exact two-turn M5 interaction, requested
the registered `observe_sensitivity` tool, consumed one actual M24 local
read-only adapter result, selected the preregistered M7 candidate for `DER_B`,
and passed the common terminal plan validator. The live IA4 choice matched the
deterministic IA3 choice over the byte-identical empirical payload.

The selected plan was validated but never executed. M26 did not start or
inspect Docker or a simulator, did not access the project embedding service,
detector, defense, actuator, final seeds, or evaluation records, and did not
restart the model service. The result is `PRELIMINARY_ONLY` protocol and
empirical-result-consumption evidence.

## Preregistered boundary

The create-once contract was written before transport and bound:

- attack-development turn seeds `8107` and `8108`;
- temperature `0` and at most `512` output tokens per turn;
- exactly one model-discovery request and at most two completions;
- at most one actual M24 adapter invocation and one M5 tool call;
- zero retries, outer rollouts, and simulation-time advance;
- the exact M18 authorization, experiment specification, M5 core, M7
  interface, M24 evidence, and M25 qualification bytes; and
- the deterministic IA3 target and candidate derived from the exact M25
  actor-visible payload.

The two M18 action requests passed before the online attempt. They identify the
existing model service, forbid service lifecycle actions and final-evaluation
access, require failure retention, and bind the final M26 harness bytes.

| Registered item | Identity or SHA-256 |
|---|---|
| Contract ID | `m26contract_4d47dae1999c8e5a97d282dd12ac682b7242fbb70c79d636ea33d251f579902f` |
| Contract file | `5bcefa5f03843f949446127aea4fe513f634a40523370e8825569c4c538b735a` |
| Seed 8107 action request | `b33e525257fcff08df24b8ad73eb11079f6e407b69e97b4cbb4015a565ae3919` |
| Seed 8108 action request | `4405fe893d572371624f957b5f5190e69dcb3deacaa1e104fdaea94ae22b5546` |
| M26 harness | `fceaa09d8cd4c633f62261dc61ea2c59fb2ee6132c93b4c08f8610ff6567d7dc` |
| M26 schema | `e3f24d1137d12ebb1e367381bca80e549645ff3bbd46b088ac6dee7eb8e24190` |

## Live transaction

Discovery returned the registered service identity:

- model: `qwen3.6-35b-a3b`;
- owner: `vllm`;
- root: `QuantTrio/Qwen3.6-35B-A3B-AWQ`; and
- maximum model length: `262144`.

Turn 0 emitted the exact registered request:

- tool: `observe_sensitivity`;
- call ID: `call_m26_real_adapter_0001`;
- metric: `voltage_stress_gain_pu_per_kw`; and
- targets: `DER_A`, `DER_B`.

Only after this request passed the common M5 parser did the harness invoke the
M24 adapter. The invocation read exactly the registered M23 source and its
independent audit, returned no side effect, consumed no rollout, and advanced
no simulation time. The result payload SHA-256 was
`c397c90c3240643c75323a166432ea67e1cae94648ec1dff2edbc9564c52d5e8`,
identical to the preregistered M25/IA3 payload.

The actor-visible tool-result event contained only the common M5 envelope and
the five-field sensitivity payload. It contained no source ID, source
classification, file list, audit binding, alias map, access boundary,
invocation ID, adapter contract, or result provenance. Those fields remain in
the terminal episode receipt for audit.

On turn 1, the model calculated the registered target scores:

- `DER_A`: `30 × 0.000031383136929719056 = 0.0009414941078915717`; and
- `DER_B`: `30 × 0.00011145940302068984 = 0.003343782090620695`.

It selected candidate `cand_bc73d19dea133043082f` for `DER_B`, matching the
preregistered IA3 control. The common validator accepted the unchanged
candidate as a structurally valid 30 kW, one-window plan with a calculated
budget of `0.08333333333333333 kVAh`. This validation did not deliver the
command to any runtime.

## Transport and accounting

The attempt used exactly three network requests: one discovery and two
completions. No retry was made.

| Turn | Prompt tokens | Completion tokens | Total tokens |
|---|---:|---:|---:|
| Tool request | 2,599 | 276 | 2,875 |
| Terminal plan | 3,007 | 354 | 3,361 |
| Total | 5,606 | 630 | 6,236 |

The session recorded two model turns, one real local adapter call, one tool
call, zero outer rollouts, and zero simulation-time advance. Its execution
states are explicit:

- `model_transport_used: true`;
- `real_local_read_only_adapter_executed: true`;
- `synthetic_fixture_injected: false`; and
- `external_tool_execution_used: false`.

All Docker, simulator, embedding, detector, defense, physical-actuator, and
evaluation flags are false. The final-seed access list is empty.

## Verification

The primary verifier and non-importing independent auditor both returned
`issues: []`. The independent auditor checks content addresses, source bytes,
M18 action requests, development seeds, transport and adapter caps, model
identity, M5/M7 identities, M24 invocation provenance, actor-facing
provenance separation, IA3 candidate agreement, resource seals, and the static
execution boundary.

| Evidence | Identity or SHA-256 |
|---|---|
| Receipt ID | `m26receipt_248240e0650b47d804d01c2cf1627375bc7fe03654c2966796ad70266362b8ea` |
| Receipt file | `b6e99edcff130ef05f70d077ec0e0bdff00bc326398292c9daf5790515655f04` |
| Independent audit ID | `m26audit_3db4d67655d09698dde61f047f74f37e2e3cdaea369c21f49f74c2be81c2a9bd` |
| Independent audit file | `cfafec448a0cfb5f772326bfbcc622c16ac40c6639e3255a9a24cd0f338c056c` |
| Independent auditor | `ee20f4a8e09ad253924540b2326d2a87cd5f097736227f47715dcd6bfe20618f` |

All 14 focused M26 tests and all 421 `g7_confirmatory` tests pass. Python
compilation, JSON parsing, primary verification, independent verification, and
`git diff --check` pass. The frozen inputs remain exact:

- roadmap report:
  `c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b`;
- experiment specification:
  `79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d`;
  and
- orchestration contract:
  `2bfb23ffb8e17aac9f4c2ec41755d7cf97b01b1c70fc93cef26a637544294d3b`.

Before the create-once attempt existed, 13 of the 14 focused tests passed; the
remaining test correctly required the absent attempt directory. After the one
registered online attempt and independent audit were retained, all 14 passed.

## Scientific interpretation

M26 closes one engineering gap: the current model can request and consume the
real local M24 result through the common M5 transaction and produce a valid
candidate consistent with the deterministic control. It does not demonstrate
that the LLM outperforms IA3. Both actors choose the same candidate because the
prompt supplies an explicit arithmetic rule and only one empirical payload is
available.

The M23 source is still based on one system-identification seed and one
operating point. M26 therefore does not establish sensitivity repeatability,
uncertainty, target-ranking stability, source admission, autonomous strategy
learning, interactive attack advantage, physical impact, detector evasion,
defense effectiveness, safety, statistical significance, or generalization.

The next research gate should address the remaining evidence bottleneck rather
than immediately expanding model authority. A separately registered M27 can
repeat the empirical system-identification procedure across multiple
development seeds and operating points, estimate uncertainty and target-rank
stability, and decide whether a versioned sensitivity resource is admissible
for bounded simulator-connected red-team trials. Final evaluation must remain
sealed throughout that development gate.
