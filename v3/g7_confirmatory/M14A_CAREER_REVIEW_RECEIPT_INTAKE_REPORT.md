# M14A CAREER independent-review receipt intake report

Status: **OFFLINE INTAKE READY — M14 CHECKPOINT OPEN**

Contract ID:
`m14aintake_a4f22ef8dd509e486adc32cdd7623c3682fc2148ff8a48831f606fc256553ba4`

Bound packet ID:
`m14reviewpacket_6efed441aebe881691b3596321ca7255edf67af8d24ef59412be923e12098b25`

Decision:
`dec_01M1DPZR2QH6DHAK0CET23Q9E4`

Open checkpoint:
`chk_01M1DPSAD7H2MGY49QDJNYPK1M`

## Result

M14A adds a fail-closed, fully offline intake contract for review receipts that
will eventually be issued outside the preparing executor. It makes the receipt
shape, exact M14 binding, reviewer-role separation, disposition vocabulary,
comment integrity, and two-receipt bundle rule mechanically testable.

M14A performs no independent review. No real receipt or reviewer identity is
checked in. The existing M14 checkpoint remains open, and every source,
partition, threshold, resource, runtime, evaluation, and campaign authorization
remains false.

## Exact packet binding

Every valid receipt must bind all of the following:

- packet ID
  `m14reviewpacket_6efed441aebe881691b3596321ca7255edf67af8d24ef59412be923e12098b25`;
- checked-in packet file SHA-256
  `fc4339b93b99b278e4d0392622778edf4b38a7949c0e2401a5f18b409fcba5b8`;
- checked-in packet size `14284` bytes;
- M13 base commit `cbccdaa069784adbb3c03d130a42c5d0027ce16d`;
- canonical snapshot-manifest SHA-256
  `1af4941f031344c1e5d1ea5bb238e6ab669e7f32702230d1ef7bb96e94f1e39c`;
  and
- canonical review-scope SHA-256
  `32f6d0c5ba48d3370a860ab12b0b24fe1908817ee61c35bee88c9191b39edde6`.

Changing any of these values invalidates the receipt even if its own content
address is recomputed.

## Receipt contract

A receipt is immutable and content-addressed as
`m14reviewreceipt_<sha256>`. It declares exactly one required role:

1. `independent_data_lineage_reviewer`; or
2. `independent_domain_method_reviewer`.

The reviewer must provide a stable reviewer identifier and an external identity
verification reference, attest that they are not the packet preparer or a
source generator, attest independence from the other required reviewer, and
declare no unresolved conflict. The receipt must answer all six M14 questions,
carry non-empty comments with an exact UTF-8 SHA-256, and use one disposition:
`accept_exact_packet`, `request_changes`, or `reject`.

Software validates these declarations and references. It does not establish a
person's identity or independence. Those remain external governance facts that
must be checked before checkpoint resolution.

## Bundle state machine

The intake evaluator returns one of six states:

- `INCOMPLETE_NOT_APPROVED` for fewer or more than two receipts;
- `INVALID_NOT_APPROVED` for malformed, stale, duplicated, role-incomplete, or
  mixed synthetic/external receipts;
- `CHANGES_REQUIRED_NOT_APPROVED` if either reviewer requests changes;
- `REJECTED_NOT_APPROVED` if either reviewer rejects;
- `SYNTHETIC_MECHANICS_PASS_NO_AUTHORITY` for the two explicit synthetic
  acceptance fixtures; or
- `READY_FOR_EXTERNAL_GOVERNANCE_RESOLUTION_NOT_APPROVED` for two mechanically
  conforming external receipt shapes.

The last state is deliberately not approval. It still reports the RKA
checkpoint as `OPEN_REQUIRES_EXTERNAL_RESOLUTION`, and every authorization flag
is false. No function in M14A writes to RKA or mutates the M14 packet.

## Conformance evidence

The canonical matrix contains sixteen fixture-only cases. It covers empty and
single-receipt bundles, a positive synthetic pair, duplicate identity, duplicate
role, stale packet bindings, self-review, comment-hash and receipt-address
mutation, change requests, rejection, mixed artifact classes, and a two-receipt
external-shape boundary.

Synthetic receipts use `synthetic_` reviewer IDs, `synthetic://` verification
references, and a fixed year-2000 timestamp. They cannot be relabeled as
external receipts without replacing the synthetic identity markers and
recomputing the content address. Even an external-shaped test pair reaches only
the not-approved ready state.

Seventeen M14A unit tests and all 269 offline harness tests pass. Exact Git
provenance is recorded in RKA after commit and push. The two JSON Schemas parse
successfully; optional external `jsonschema` package validation is not claimed
because that package is unavailable in the current environment. The stricter
Python semantic validator remains mandatory.

## Machine artifacts

- `artifacts/career_review_receipt_intake_m14a.json` contains the
  content-addressed intake contract and sixteen-case conformance matrix.
- `career_review_receipt.schema.json` defines the externally supplied receipt
  interchange shape.
- `career_review_receipt_intake.schema.json` defines the canonical M14A
  contract shape.
- `g7confirm/career_review_receipts.py` implements semantic validation,
  content addressing, synthetic fixture construction, and fail-closed bundle
  evaluation.
- `tests/test_career_review_receipts.py` exercises packet binding, integrity,
  role and identity separation, dispositions, state transitions, and the
  no-authorization invariant.

## Claim boundary

M14A establishes receipt-intake mechanics only. It does **not** establish:

- that either reviewer exists or is independent;
- that an independent review occurred;
- that a receipt was genuinely issued;
- that the packet was accepted;
- that the M14 checkpoint may be resolved;
- that source generation or partition assignment may begin;
- that a threshold or resource is scientifically admissible; or
- that runtime, model, embedding, tool, simulator, detector, actuator,
  evaluation, or campaign access is authorized.

## Next gate

M15 remains post-review resolution. Two genuine external receipts must be
delivered, their identity and independence evidence must be checked outside the
preparing executor, both must accept the exact packet, and the RKA checkpoint
must then be explicitly resolved. Even a valid M15 resolution would not by
itself authorize source generation; that requires a separate bounded
development gate.
