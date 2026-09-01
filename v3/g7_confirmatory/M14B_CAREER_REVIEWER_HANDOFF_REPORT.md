# M14B CAREER external reviewer handoff report

Status: **EXACT HANDOFF READY — NOT APPROVED**

Handoff ID:
`m14bhandoff_b860b6a66def594f90aee3cd5dc675e3e0ec182d873a021f8284f1566cf7b6a3`

Decision:
`dec_01M1DQQMY05E8KV19X5WHVHRC0`

Open checkpoint:
`chk_01M1DPSAD7H2MGY49QDJNYPK1M`

## Result

M14B packages the M14 packet and M14A receipt-intake boundary into an exact,
reviewer-facing offline handoff. It adds a six-file byte manifest, two
role-specific empty worksheets, and three read-only CLI validation commands.

M14B does not perform a review, assign a reviewer, issue or finalize a receipt,
or resolve the checkpoint. All worksheet identity, independence, answer,
comment, disposition, timestamp, and receipt fields are null. Every runtime and
scientific authorization remains false.

## Exact support snapshot

The handoff binds these six files at M14A base commit
`363cbb48a678d1ea6b123ad5bc6aadf5c7b7635a` by path, byte count, and SHA-256:

1. the M14 packet;
2. the M14 packet report;
3. the M14A external receipt schema;
4. the M14A intake contract;
5. the M14A intake report; and
6. the M14A semantic receipt validator.

The M14 packet separately binds the thirteen governing M8–M13 files. M14B does
not replace or widen that scientific snapshot. Any mismatch in the six support
files fails preflight; any mismatch in the thirteen packet files continues to
fail the M14 validator.

## Reviewer roles and separation

External governance must assign two distinct reviewers:

1. `independent_data_lineage_reviewer`; and
2. `independent_domain_method_reviewer`.

Neither reviewer may be the packet preparer or source generator. Their stable
identity references, organizational independence, and conflict declarations
must be established outside this software. The two roles cannot be satisfied by
one person or one receipt.

## Empty worksheets

The checked-in worksheets are:

- `artifacts/reviewer_handoff/data_lineage_worksheet_m14b.json`; and
- `artifacts/reviewer_handoff/domain_method_worksheet_m14b.json`.

They are immutable `EMPTY_UNISSUED_NOT_A_RECEIPT` artifacts. They bind the
packet and the six review-question hashes, but every reviewer and review field
is null. Populating and readdressing a checked-in worksheet is rejected by the
semantic validator. Reviewers may use the worksheet structure as a private
note-taking aid, but a completed worksheet is never evidence.

A reviewer must instead issue a separate receipt conforming to
`career_review_receipt.schema.json` and the stricter M14A semantic validator.
The external reviewer, not the packet preparer, owns that receipt's content,
identity evidence, comments, disposition, timestamp, and content address.

## Read-only workflow

From `v3/g7_confirmatory`, first verify the checked-in handoff:

```bash
python3 -m g7confirm.cli career-review-preflight \
  --repo-root /absolute/path/to/roi-uncc-mcp
```

The expected status is `EXACT_HANDOFF_READY_NOT_APPROVED`, with zero issues,
zero files created or modified, zero RKA writes, an open checkpoint, and all
authorization values false.

After an external reviewer independently creates a receipt, validate that one
declaration without modifying it:

```bash
python3 -m g7confirm.cli career-review-receipt \
  --receipt /path/to/external-receipt.json
```

The success status is `VALID_RECEIPT_DECLARATION_NOT_APPROVED`. This confirms
only semantic conformance. It does not establish that the named reviewer exists
or is independent.

After both external receipts are available, evaluate the bundle:

```bash
python3 -m g7confirm.cli career-review-bundle \
  --receipt /path/to/lineage-receipt.json \
  --receipt /path/to/domain-receipt.json
```

Only two mechanically valid external acceptance shapes can reach
`READY_FOR_EXTERNAL_GOVERNANCE_RESOLUTION_NOT_APPROVED`. The command never
resolves RKA, and the status remains explicitly not approved. A request for
changes, rejection, incomplete pair, duplicate identity, role error, or stale
binding fails the gate.

There is deliberately no `career-review-create` or `career-review-finalize`
command.

## Receipt issuance boundary

Receipt issuance must occur outside the preparing executor. An independent
implementation may compute the content address from canonical JSON, or the
reviewer may inspect the open M14A `receipt_id_for()` algorithm. In either case,
the receipt owner must construct the contents, remove the `receipt_id` field for
the hash preimage, serialize with sorted keys and compact separators, calculate
SHA-256 over UTF-8 bytes, and set the `m14reviewreceipt_<sha256>` identifier.

Using the published algorithm does not establish independence; identity and
separation evidence still require external verification. No real receipt is
stored in this repository by M14B.

## Verification evidence

Fifteen M14B tests pass. They verify the six exact support files, canonical
contract and worksheets, null-only worksheet state, rejection after attempted
identity/answer/disposition population, all three CLI paths, absence of any
create/finalize command, and the no-authorization invariant. The complete
offline harness passes all 284 tests, and `compileall` succeeds.

The direct preflight command reports zero issues, zero writes, an open M14
checkpoint, and all authorization values false. JSON parsing, English-only,
diff, frozen-hash, and exact M14 snapshot checks are part of commit-time
verification.

## Machine artifacts

- `artifacts/career_reviewer_handoff_m14b.json` is the content-addressed
  handoff contract.
- `artifacts/reviewer_handoff/*_worksheet_m14b.json` are the two empty
  non-receipt worksheets.
- `career_reviewer_handoff.schema.json` defines the handoff shape.
- `career_reviewer_worksheet.schema.json` defines the null-only worksheet
  shape.
- `g7confirm/career_reviewer_handoff.py` enforces exact bytes and worksheet
  semantics.
- `g7confirm/cli.py` exposes only the three read-only review commands.
- `tests/test_career_reviewer_handoff.py` provides offline conformance
  evidence.

## Claim boundary

M14B establishes that the intended review materials can be handed off and
validated without ambiguity. It does **not** establish:

- an assigned, verified, or independent reviewer;
- an answered review question;
- an issued or accepted receipt;
- external identity or conflict-of-interest verification;
- M14 checkpoint resolution;
- source generation, partition assignment, threshold selection, or resource
  admission; or
- model, embedding, tool, simulator, detector, actuator, evaluation, or
  campaign authorization.

## Next gate

M15 remains external post-review resolution. Two genuine, independently issued
acceptance receipts must pass the M14A validator, external governance must
verify reviewer identity and independence, and RKA checkpoint
`chk_01M1DPSAD7H2MGY49QDJNYPK1M` must be explicitly resolved. Even then, a
separate bounded development authorization is required before real source
generation.
