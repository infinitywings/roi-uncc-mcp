# M18 Bounded Online Development Gate Report

## Result

M18 replaces the contract-only interpretation of the preliminary gate with a
PI-authorized bounded online-development boundary. Once the read-only preflight
and per-action validator pass, later milestones may exercise the real local
GridEval development flow: existing model services, ephemeral simulator and
network components, simulated DER actuation, detector and defense logic,
paired result collection, and provenance packaging.

The canonical artifact is `artifacts/preliminary_only_gate_m18.json`, governed
by `preliminary_only_gate.schema.json` and validated by
`g7confirm.preliminary_only_gate`.

M18 is an authorization artifact, not a run receipt. It starts no process,
calls no model, reads no experiment record, and creates no empirical result.
M19 is the first authorized online execution milestone.

## PI and RKA provenance

The active boundary is based on:

- PI online-testing directive: `jrn_01M1MEHG231KP7VRA9THV14KTD`;
- bounded-online Confirmation Brief: `jrn_01M1MEJ2HR5CV1EM0F66KGYN2R`;
- exact PI confirmation: `jrn_01M1MENKG6DHRRTSDW6WSJXBFS`;
- active online-development decision: `dec_01M1MEP2VK98XN9KD935WDH39N`;
- superseded contract-only decision: `dec_01M1ME2CJ9WN5XBPY56C3AB714`;
- M18 Executor Backbrief: `jrn_01M1ME2TJXAE96SB65P851DY1B`;
- Brain Gate 1 approval: `jrn_01M1ME3433FM04A4T65RRMVAH2`; and
- M17 implementation evidence: `jrn_01M1ME102EMBDERJ6ZRM09XR98`.

The active decision permits online development but explicitly preserves final
evaluation. The previous decision is retained as superseded provenance rather
than silently rewritten.

## Authorized online-development actions

After M18 preflight and per-action validation, a later milestone may perform:

- create-once preliminary source generation;
- provisional, revocable resource admission;
- preliminary-only numeric threshold selection and fitting;
- preliminary detector calibration;
- simulator and simulated-actuator execution;
- bounded preliminary runtime evaluation and trial batches;
- calls to the already-running local `qwen3.6-35b-a3b` service;
- calls to the already-running project embedding service; and
- startup and teardown of ephemeral local runtime components needed by the
  registered GridEval flow.

These permissions are conditional. Every action requires an exact registered
purpose, seed, budget identifier, code/config/input hashes, create-once output,
failure retention, and `PRELIMINARY_ONLY` classification. Runtime trials also
require a paired benign lineage.

## Purpose-specific partition registry

M18 reserves seven disjoint seed namespaces:

| Purpose | Seeds | Access | Design use |
|---|---|---|---|
| Runtime qualification | 5101-5104 | Preliminary | May influence integration design |
| System identification | 6101-6112 | Preliminary | May influence design |
| Detector calibration | 7101-7112 | Preliminary | May influence detector parameters |
| Detector audit | 7201-7212 | Preliminary | May influence detector selection |
| Attack development | 8101-8112 | Preliminary | May influence strategy and orchestrator design |
| Preliminary holdout | 8201-8212 | One-time preliminary | Must not tune design |
| Final evaluation | 9101-9112 | Sealed | Must not be read or used |

The final partition remains present in the registry so that accidental use is
detectable. It is classified `FINAL_SEALED`, has `may_read=false`, and cannot
support design or preliminary claims.

## Service and actuation boundary

The LLM identity is fixed as
`qwen3.6-35b-a3b@http://ccil1s26m8hj6lws:8000/v1`. The project must reuse the
existing embedding service and record its live identity for each action. M18
does not permit starting, restarting, or substituting either model service.

Ephemeral local GridLAB-D, HELICS, network, adapter, detector, and defense
processes may be started for registered preliminary work. Their process and
version identities plus teardown status must be recorded. Physical field-device
connections and actuation remain prohibited.

## Per-action fail-closed validator

`validate_preliminary_action_request` validates a closed request containing:

- action and partition purpose;
- registered seed;
- output classification and create-once policy;
- manifest, code, and configuration SHA-256 values;
- budget and paired-benign identifiers;
- final-data, physical-actuator, service-start, and failure-retention flags;
  and
- model or embedding service identity where applicable.

The validator rejects final seeds, cross-purpose seeds, action/partition
mismatches, missing paired controls, malformed hashes, output overwrite,
failure filtering, final-data access, physical actuation, model-service restart,
and undeclared service identity. Recomputing the M18 content address cannot
turn a rejected governance mutation into an accepted contract.

## Final seals

M18 cannot authorize any of the following:

- access to final evaluation partitions or seeds;
- final resource admission or final detector/threshold locking;
- confirmatory campaign execution or confirmatory statistical inference;
- generalization or publication-grade defense-effectiveness claims;
- physical field-device actuation; or
- starting or restarting the LLM or embedding service.

Preliminary results may guide development, except that the preliminary holdout
is one-time and outcome-ineligible for subsequent tuning. All results must
report their preliminary status, negative results, failed runs, refusals,
timeouts, aborts, and known limitations.

## Read-only preflight

From `v3/g7_confirmatory`:

```bash
python3 -m g7confirm.cli preliminary-only-preflight \
  --repo-root /home/cfu6/roi-uncc-mcp
```

The command verifies the full M17 chain, six exact-byte M18 inputs, partition
disjointness, online permissions, service boundaries, final seals, and the
canonical content address. It exposes no run or final-unseal command.

## Validation scope

`tests/test_preliminary_only_gate.py` passed 19 tests. The complete
`v3/g7_confirmatory` suite passed 350 tests, and the read-only M18 preflight
returned zero issues. This establishes software authorization semantics only;
it is not evidence that the online workflow runs correctly or that any attack,
detector, or defense is effective.

## Next action

M19 will first perform a live read-only service and component preflight. If
that succeeds, it will execute one benign trace and one matched single-window
attack trace on the `runtime_qualification` partition, record complete
requested-to-realized P/Q and detector/defense lineage, and verify teardown.
Only a successful M19 flow may unlock broader preliminary batches.
