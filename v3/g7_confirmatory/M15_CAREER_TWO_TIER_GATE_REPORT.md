# M15 CAREER Two-Tier Gate Report

## Result

M15 replaces the single M14 development blocker with a fail-closed two-tier
gate. Pure offline engineering and local advisory review may proceed. External
review is deferred, not completed, accepted, or waived. Every data-dependent,
scientific, simulation, evaluation, and campaign action remains sealed.

The canonical artifact is
`artifacts/career_two_tier_gate_m15.json`, governed by
`career_two_tier_gate.schema.json` and verified by
`g7confirm.career_two_tier_gate`.

## PI and RKA provenance

The gate revision binds the following RKA records:

- confirmation brief: `jrn_01M1M8VE9XHW8NC9APWFAVXFS7`;
- PI confirmation: `jrn_01M1M9594BX7M4JPQK0SMPXAQ8`;
- governing two-tier decision: `dec_01M1M95MNV67RVB4BZJDG4CGVX`;
- M14 checkpoint resolved as deferred, not approved:
  `chk_01M1DPSAD7H2MGY49QDJNYPK1M`; and
- replacement non-blocking offline/deferred external checkpoint:
  `chk_01M1M97DN5EWDKSM4T1CMT76J6`.

The decision is deliberately narrower than experiment approval. It changes
which offline implementation work may proceed but does not change the
scientific evidence requirements.

## Tier 1: permitted offline work

The contract permits only the following classes of work:

- contract and schema authoring;
- implementation and unit testing;
- synthetic fixture generation;
- internal advisory review;
- use of the local LLM on synthetic or non-evaluation inputs;
- use of the already-running embedding service on synthetic or
  non-evaluation inputs; and
- RKA provenance writes.

Starting or restarting either model service is not authorized by this gate.
Local advisory work must disclose the service and session identity. It is not
independent external review and cannot create or finalize an external receipt,
resolve the deferred checkpoint, or confer scientific approval.

## Tier 2: sealed work

The following actions remain explicitly false in the machine contract:

- real source generation or modification;
- partition assignment;
- resource admission;
- numeric threshold selection or fitting;
- detector calibration;
- simulator or actuator execution;
- runtime evaluation or evaluation-record access;
- campaign execution; and
- external-receipt issuance or gate resolution by a local advisor.

Any attempted mutation that enables one of these actions fails either the
content-address check or the semantic validator, including after a malicious
caller recomputes the content address.

## Preservation of M14 review evidence

M15 does not delete or rewrite the external-review path. It binds thirteen
M14, M14A, and M14B files by path, byte count, and SHA-256 digest, including:

- the source-review packet and report;
- the receipt schema, intake contract, intake report, and receipt validator;
- the reviewer handoff contract and report;
- both handoff schemas;
- both empty role-specific worksheets; and
- the handoff verifier.

The frozen roadmap report and experiment specification are separately bound by
exact bytes. Therefore an M15 preflight fails closed if either the historical
review machinery or a frozen project artifact drifts.

## Deferred external gate

The replacement checkpoint remains open and is non-blocking only for the
narrow offline work above. Before any sealed action, the project still needs:

1. two genuine receipts from distinct external reviewer identities;
2. external identity, independence, and conflict-of-interest governance;
3. exact binding to the preserved M14 packet and review scope; and
4. explicit RKA resolution of the deferred checkpoint.

Internal review findings may improve the design but cannot be counted toward
these requirements.

## Read-only preflight

From `v3/g7_confirmatory`:

```bash
python3 -m g7confirm.cli career-development-gate \
  --repo-root /home/cfu6/roi-uncc-mcp
```

The command reads the canonical artifact and all bound files. It creates or
modifies no file, performs no RKA write, contacts no model or embedding
service, and exposes no unseal operation.

## Validation scope

`tests/test_career_two_tier_gate.py` covers the canonical artifact, closed
schema, exact-byte preservation, offline permissions, all sealed actions,
deferred external-review state, advisory limitations, read-only CLI behavior,
and readdressed adversarial mutations. The targeted M14B/M15 run passed 30
tests, and the complete `v3/g7_confirmatory` suite passed 299 tests. The
read-only M15 CLI preflight also returned zero issues. Passing these checks
demonstrates the software boundary only. It does not demonstrate external
review, source fitness, calibrated detection, physical validity, or campaign
readiness.

## Next safe milestone

M16 may conduct an internal advisory offline design review using synthetic or
non-evaluation inputs. Its output must remain advisory, identify the local
model/service/session provenance, and propose engineering changes without
changing any sealed-action flag. The external-review gate remains a hard
precondition for later source, threshold, calibration, runtime, and campaign
work.
