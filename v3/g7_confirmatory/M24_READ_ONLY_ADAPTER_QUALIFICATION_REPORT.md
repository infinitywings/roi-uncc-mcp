# M24 empirical read-only adapter qualification report

## Outcome

M24 qualified one real local, read-only adapter that transforms the exact M23
empirical sensitivity source candidate into the unchanged M7
`observe_sensitivity` consumer payload. The adapter passed both its primary
verifier and a separately implemented independent audit. The independent audit
reported `issues: []`.

This is an offline interface and isolation result. The M23 source remains
`PRELIMINARY_ONLY` and unadmitted. M24 did not contact an LLM, embedding
service, detector, defense, network, Docker daemon, simulator, evaluation
record, or physical actuator, and it advanced zero simulation time.

## Registered design

The create-once contract is
`artifacts/m24_read_only_adapter_attempt1/contract.json` (SHA-256
`95965833d0d49cb021fe4af89e2cd830d4cd904a2de6f7d12aad2ecd33721ee3`,
contract ID
`m24contract_c92535c44ed39b2d8f42555fee19977aebcc764fd17841c7e8a0736d7b560575`).
It binds:

- adapter code SHA-256
  `8db0a84376d47cac9ef9d900b32aaa276f5175bde4eb1d611fe9bd9f85a577cb`;
- receipt-schema SHA-256
  `ca6cdb53b4e41d3a11f6d848b90a55db7e9ae0cd3e5658c6b86773e8893560d1`;
- M7 contract SHA-256
  `4cef8444c56c40ff493ed3add9847d43d9d12c72f9f1714597e7566109d26de2`;
- M7 protocol ID
  `m5proto_7b094847ba6550c0216b4471cde8a3aff783002177ba41a557882f3e90e1f2ff`;
- M7 search-surface ID
  `surface_585d7e0e77d464207579863cfdffbd420e439894eabdc2b5c6cd1b747c64ff78`;
- M23 source SHA-256
  `30d003e06d016b88d49e024857c9b74a9f9f34012a6f022b6f3a26511fc619c1`;
  and
- M23 independent-audit SHA-256
  `d0c3a539c20cc4dc3adb2910cd7bbba9c90a071a839ebc0fcde9d9e67f524030`.

The contract authorizes only a local read-only adapter. File writes, model,
embedding, detector, defense, network, Docker, simulator, physical-actuator,
and evaluation access are false. The side-effect contract fixes simulation
time advance and outer-rollout cost at zero.

## Exact M7 interface preservation

M24 keeps the M7 interface unchanged:

- tool name: `observe_sensitivity`;
- input schema version: `sensitivity-query/v1`;
- output schema version: `sensitivity-result/v1`;
- request metric: `voltage_stress_gain_pu_per_kw`;
- ordered consumer targets: `DER_A`, then `DER_B`;
- side-effect class: `read_only_no_time_advance`; and
- returned information level: `partial`.

The physical-to-consumer mapping is explicit and fixed:

| Consumer alias | M23 physical target |
|---|---|
| `DER_A` | `DER_EV1_BESS` |
| `DER_B` | `DER_EV4_BESS` |

This mapping is non-actuating. It preserves the existing candidate and tool
namespace for matched IA3/IA4 comparison while connecting each alias to only
one registered M23 scalar.

## Field-minimized result

The canonical consumer payload is:

```json
{
  "metric": "voltage_stress_gain_pu_per_kw",
  "schema_version": "sensitivity-result/v1",
  "time_s": 30,
  "values": {
    "DER_A": 0.000031383136929719056,
    "DER_B": 0.00011145940302068984
  },
  "window": 2
}
```

Its canonical SHA-256 is
`c397c90c3240643c75323a166432ea67e1cae94648ec1dff2edbc9564c52d5e8`.
The payload contains exactly five top-level fields and exactly two scalar
values. It does not expose the M23 source ID, audit ID, classification,
admission state, full four-node response vectors, one-sided estimates,
centered residuals, source-power responses, run records, manifest, warnings,
detector state, or defense state.

Those fields were not discarded or rewritten. Their exact M23 source bytes
remain unchanged and are referenced by hash in the separate invocation
receipt. Thus field minimization does not destroy the internal evidence needed
for later review.

## IA3/IA4 parity

The qualification invoked the adapter independently for `IA3` and `IA4`.
Each invocation read exactly two regular, non-symlink files:

1. the M23 empirical source; and
2. the passing M23 independent-audit receipt.

Both invocations used canonical request SHA-256
`b1a25b28bfe57854ca016d07a388b835158ec36f1892c30e780586a5a793ed6e`
and canonical payload SHA-256
`c397c90c3240643c75323a166432ea67e1cae94648ec1dff2edbc9564c52d5e8`.
All seven registered parity assertions passed:

- identical canonical request bytes;
- identical request hashes;
- identical canonical payload bytes;
- identical payload hashes;
- identical payload objects;
- identical side-effect contracts; and
- identical exact two-file read sets.

The create-once qualification receipt is
`artifacts/m24_read_only_adapter_attempt1/qualification_receipt.json`
(SHA-256
`6201770ced6029cf1c54a1d61b9d7a73d3c05c19d8edb83e9339df4d62fa65b8`,
qualification ID
`m24qual_e2dada84a81f064527590dcef69ac29bed40767a32f8a6d8f387ce8f01aebdb`).

## Fail-closed boundary

The implementation rejects before releasing a payload when any of the
following changes:

- M23 source or audit file bytes;
- source, contract, or audit identity and self-address;
- source or audit schema;
- source status, classification, admission state, or final-seed seal;
- scalar target set, metric, time, window, value type, or scalar derivation;
- M7 contract, protocol, search surface, tool schema, ordered alias request, or
  side-effect declaration;
- M24 contract identity, self-address, governance flag, alias map, or payload
  allowlist;
- request fields, metric, target count, target order, or caller rung; or
- JSON validity, including duplicate keys and non-finite constants.

Direct symbolic mutation tests check these semantic gates separately from the
exact file-hash gate. The adapter also rejects symlink inputs and returns a
defensive payload copy.

## Independent audit

`g7confirm/m24_independent_audit.py` does not import the adapter module. It
independently reads the evidence, recalculates content addresses and canonical
hashes, derives both scalar aliases directly from the M23 source, inspects the
M7 tool definition, checks the receipt topology, and parses the adapter source
to reject external-service imports and call tokens.

Its create-once receipt is
`artifacts/m24_read_only_adapter_attempt1/independent_audit_receipt.json`
(SHA-256
`7149de87a983e96850676b335e89a58e3c9e1f0b0b804b07b8d74cf9df49a787`,
audit ID
`m24audit_f4869f93d8bc5f8d9dcac137a4ea9893fef30722445905ce9e10233b59526e7a`).
The audit passed ten independent check classes with zero issues.

## Verification and scientific boundary

The focused M24 suite passes 18 tests. The full `g7_confirmatory` suite passes
391 tests. Both the primary verifier and independent verifier return empty
issue lists. The frozen roadmap and experiment specification retain their
expected SHA-256 values:

- roadmap report:
  `c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b`;
- experiment specification:
  `79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d`.

During the documentation pass, an attempted append changed the exact bytes of
the frozen `ORCHESTRATION_CONTRACT.md`. Six upstream preflight tests rejected
that drift as designed. The append was removed, a zero-diff check confirmed
that the frozen file was restored exactly, and the complete 391-test suite was
then rerun successfully. This retained development failure is evidence that
the preflight boundary detects even documentation-only changes to frozen
inputs; it is not evidence about runtime behavior.

M24 establishes an exact empirical-source-to-consumer transformation, strict
field minimization, matched IA3/IA4 byte parity, and a local read-only access
boundary. It does not establish source admission, repeatability, uncertainty,
operating-point coverage, a stable target ranking, physical harm, strategy
quality, LLM advantage, detector or defense effectiveness, runtime safety,
statistical significance, generalization, or confirmatory evidence.

## Recommended next gate

M25 should remain offline. It should extend the M5 execution overlay with a
provenance-aware adapter-result type so that a matched IA3 policy and the
current LLM can consume this exact M24 payload through the same transactional
tool-result path. M25 must distinguish real local read-only adapter execution
from synthetic fixture injection, retain one-call and zero-rollout caps, and
make no simulator call. Only after that integration passes should a separately
registered bounded simulator action be considered.
