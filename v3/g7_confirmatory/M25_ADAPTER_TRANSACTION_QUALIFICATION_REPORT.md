# M25 empirical adapter transaction qualification report

## Outcome

M25 passed the exact M24 empirical sensitivity result through the common M5
transactional tool-result transition for matched offline IA3 and IA4 sessions.
Both sessions made one actual local read-only adapter invocation, entered and
left the same `awaiting_tool_result` state atomically, emitted byte-identical
actor-facing tool requests and result events, selected the same M7 candidate,
and consumed zero outer rollouts and zero simulation time.

This is an offline plumbing, provenance-separation, and parity result. The IA4
actor was a deterministic replay, not a live LLM. M25 did not access a model,
embedding service, network, Docker daemon, simulator, detector, defense,
physical actuator, final seed, or evaluation record. The M23 empirical source
remains `PRELIMINARY_ONLY` and unadmitted.

## Common M5 result path

`g7confirm/ia4_tool_loop.py` now defines `RealAdapterToolResult` alongside the
existing `FixtureToolResult`. The new type validates the full M24 invocation
receipt, including:

- the exact outstanding request and returned payload bytes;
- request and payload SHA-256 values;
- the self-addressed invocation identity;
- caller rung, tool name, and schema versions;
- M23 source and passing audit bindings;
- the exact two-file read record;
- zero-cost, non-actuating side effects; and
- the closed no-external-access boundary.

`IAInteractiveSession.submit_tool_result` accepts either type through the same
identity, schema, information-level, cost, `ToolCallRecord`, tool-contract, and
state-transition checks. Invalid real results fail closed before the session
advances. The session stores a rebuilt defensive copy after acceptance so a
caller cannot later mutate retained provenance.

Historical fixture behavior remains unchanged. The exact pre-M25 anchors are:

- fixture result SHA-256:
  `0a0d364173120eb25f3b7892a989e76ba897270a728e68e72ceacca0ca6629e2`;
- fixture episode receipt SHA-256:
  `5a7af50c3b56e45238b8f96f93cbefd72813a8dc9b81faa7e1a28465ae314ff9`;
- M7 protocol ID:
  `m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff`;
  and
- M7 search-surface ID:
  `surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78`.

## Provenance separation

Each terminal episode receipt contains a fully provenance-aware real result
with its M24 invocation receipt. The next actor turn receives only this common
M5 envelope:

```json
{
  "call_id": "call_m25_real_adapter_0001",
  "event": "tool_result",
  "outer_rollout_cost": 0,
  "output": {
    "metric": "voltage_stress_gain_pu_per_kw",
    "schema_version": "sensitivity-result/v1",
    "time_s": 30,
    "values": {
      "DER_A": 0.000031383136929719056,
      "DER_B": 0.00011145940302068984
    },
    "window": 2
  },
  "output_schema_version": "sensitivity-result/v1",
  "protocol_id": "m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff",
  "returned_information_level": "partial",
  "schema_version": "grideval-g7-ia4-tool-result/v1",
  "simulation_time_advance_s": 0.0,
  "tool_name": "observe_sensitivity",
  "wall_clock_ms": 0.0
}
```

The actor-facing event contains no adapter contract, source, audit, alias map,
file-read record, access boundary, invocation ID, result kind, or provenance
receipt. Its canonical SHA-256 is
`a545c991c29de2a2ee3bd791fbacf1f00375d520e9615da944d6c6d6ef17be04`.
The underlying M24 payload SHA-256 remains
`c397c90c3240643c75323a166432ea67e1cae94648ec1dff2edbc9564c52d5e8`.

This separation prevents provenance fields from becoming an IA4-only
information advantage while retaining exact evidence for later audit.

## Matched IA3/IA4 replay

The create-once qualification executes one independent session per rung. Both
use canonical tool-request SHA-256
`690084ad8b17dcb65aeaf61b23335c47537596af763a20dd82b8f14df1d95040`,
one real local adapter call, the same two exact file reads, one M5 tool call,
two zero-token local replay turns, zero outer rollouts, and zero time advance.

All nine registered parity assertions passed:

- identical tool-request bytes and hashes;
- identical M24 request canonical bytes;
- identical M24 payload canonical bytes and hashes;
- identical actor-facing tool-result event bytes;
- identical exact file reads;
- identical selected target and candidate; and
- identical zero-cost accounting.

Both sessions selected `DER_B` and M7 candidate
`cand_bc73d19dea133043082f`, because the registered M23 scalar for
`DER_EV4_BESS` is greater than the scalar for `DER_EV1_BESS`. This is a
deterministic transformation of one preliminary source, not evidence that the
ranking is stable across seeds or operating points.

The full real-result fingerprints differ as designed because the retained
provenance names the caller rung and its self-addressed M24 invocation:

| Rung | M24 invocation ID | Real-result fingerprint |
|---|---|---|
| IA3 | `m24invoke_c3c689d4286387d245b823e0c5b151d5363f9c00b1d21a21158486ec8ec40277` | `e0004f4a0fe5c98fba2b15a796b129d37674a6ea4fb0484b814f115aa8c946c5` |
| IA4 | `m24invoke_f7cc17ce0eb2599cb7dab5f7f9390e122b1b5cafdeed6ea056dfc336a88822c1` | `85ffc51011957bf71ecb97b4e407a0ecbbb209601cbf00fca1584306abda13b5` |

## Execution-state distinction

M25 removes an ambiguity that would otherwise weaken later experiments. A
real-adapter episode now records all three states explicitly:

- `real_local_read_only_adapter_executed: true`;
- `synthetic_fixture_injected: false`; and
- `external_tool_execution_used: false`.

The legacy aggregate `tool_execution_used` is true for this real local tool
path and remains false for historical fixture injection. Model transport and
all external-resource flags remain false.

## Registered evidence

The create-once directory is
`artifacts/m25_adapter_transaction_attempt1/`.

| Artifact | Content ID | File SHA-256 |
|---|---|---|
| Contract | `m25contract_00400d7db95cdb2a0e30e8e66100dccc00742f6b9d4d8ddfa71334bc65615d27` | `43fe76b9396fb5511902632085b6645e2d0af522026959449ddcc2960958785b` |
| Qualification | `m25qual_1d3ffc1e3d2adc6fd442286a9c9f48326cf49bea8f3dc67232ae34f628be1b6c` | `e0fa95cfeaaae1dbe576844f6a7dd7f44af0d5f3251cbc14adf2d6ecba2c837e` |
| Independent audit | `m25audit_d6f3b79e83de9834d2d8b4e123b4ebe18f5d1b1e80e9b31cc410a1cb70578398` | `ff07cf12ec365a54b50b0d16d0d5501a194aec63961df3dae55469aff0a178bc` |

The registered implementation hashes are:

- M5 transaction core:
  `1292c635a97550cd0246bcce9955ab5e2538e9657a1c823b86cbca643f1df6f6`;
- M25 transaction harness:
  `f75b411311adbe2e1c14d5e353d61b59edebf9681c029b2b69a59612ca5c0a0a`;
- independent auditor:
  `1326ebffb112e78f4a4c1003c9c8181c85b599e24906c6de327eee5201423f12`;
  and
- qualification schema:
  `62e10524b9cd3247cd4b31a747859b85c917f04c7c7e182b2bdc93541960878d`.

The independent auditor does not import the M25 harness or M24 adapter. It
derives the consumer scalars directly from the M23 source, validates all
content addresses and exact file bindings, checks transaction and invocation
lineage, confirms the actor-facing provenance exclusion, and scans the M25
code boundary for external-service imports. It passed ten check classes with
`issues: []`.

## Verification and retained observations

The focused M25 suite passes 16 tests. The full `g7_confirmatory` suite passes
407 tests. Both primary and independent verification return empty issue lists;
Python compilation and JSON parsing pass. The frozen inputs retain their exact
SHA-256 values:

- roadmap report:
  `c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b`;
- experiment specification:
  `79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d`;
  and
- orchestration contract:
  `2bfb23ffb8e17aac9f4c2ec41755d7cf97b01b1c70fc93cef26a637544294d3b`.

Before create-once generation, the new focused suite passed 15 of 16 tests;
the remaining check rejected the intentionally absent checked-in artifact.
After attempt 1 was generated once, all 16 tests passed without overwrite.

During M25 provenance intake, a transcription mismatch was found between the
M24 report and the exact M24 qualification artifact. The artifact ID is
`m24qual_e2dada84a81f064527590dcef69ac29bed40767a32f8a295048251257879de41`.
The report-only error was corrected and pushed at commit `b0adb93` before the
M25 contract was registered. No M24 artifact bytes or verification results
changed.

## Scientific boundary and next gate

M25 establishes that the exact M24 result can traverse the common M5
transaction with strict provenance validation, matched actor-visible bytes,
legacy compatibility, and explicit execution-state accounting. It does not
establish M23 source admission, sensitivity repeatability, uncertainty,
operating-point coverage, a stable target ranking, current-LLM behavior, LLM
advantage, attacker effectiveness, physical harm, detector or defense
effectiveness, runtime safety, statistical significance, generalization, or
confirmatory evidence.

M26 may be a separately registered bounded online decision-only regression
against the already-running current LLM. It should use the exact M25 contract,
one real read-only adapter call, no simulator action, development-only seeds,
and a matched IA3 decision over the same payload. A successful M26 would
qualify current-model transport and tool-result consumption only; empirical
source admission and any physical action must remain later, independent gates.
