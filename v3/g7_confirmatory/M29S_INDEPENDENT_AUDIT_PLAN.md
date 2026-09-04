# M29-S independent audit plan

## Independence boundary

The independent auditor must not import the M29-S generator, runner,
deterministic compiler, validator, retrieval adapter, response parser, or
primary verifier. It may use only Python's standard library and serialized
create-once artifacts. Its own source hash is stored in every audit receipt.

## Inputs

The auditor receives the frozen design contract, development-freeze receipt,
execution contract, serialized visible evidence, corpus manifest, embedding
receipt, model request and response records, tool transcripts, emitted drafts,
final programs, and primary receipt. Latent specifications and independent
slot oracles are read only from the sealed design fixture during endpoint
recomputation; they are never copied into tested-arm requests or tool results.

## Required checks

### Split and source integrity

- Recompute content IDs and SHA-256 hashes for every source and artifact.
- Prove M29-R, M29-S development, and M29-S held-out disjointness across
  condition IDs, seeds, latent tuples, semantic digests, and rendered bytes.
- Reject any source drift, extra artifact, overwrite, retry, or missing cell.

### Arm parity and information flow

- Reconstruct each arm's visible input and verify byte equality wherever the
  factorial contract holds a factor constant.
- Confirm that retrieval changes only selected passage IDs and their visible
  text, not the frozen corpus or evidence bundle.
- Confirm that the deterministic compiler reads no latent or oracle field.
- Confirm that model requests contain no oracle program, expected value,
  endpoint, success label, hidden classification, or RKA governance record.

### Validator-tool non-leakage

- Require every tool name, argument, result key, and error code to be in the
  frozen allowlist.
- Require tool results to contain no numeric/string value copied from a hidden
  oracle field unless that value already appears in the arm's visible input.
- Reject corrected programs, recommended values, scalar scores, success
  booleans, or expected-output fields in tool results.
- Recompute call ordering and enforce one initial draft, one tool phase, and
  one revision for every inspect-revise cell.

### Endpoint recomputation

- Recompute exact accuracy for every registered semantic slot.
- Recompute evidence-lineage completeness and unknown-evidence errors.
- Recompute all-slot success, mirrored-pair success, initial correctness,
  repair conversion, repair regression, and asymmetry.
- Recompute retrieval and non-retrieval margins.
- Recompute every threshold without importing primary evaluation code.

### Accounting and seals

- Recompute model calls, tokens, embedding calls/items, tool calls, invalid
  drafts, refusals, revisions, and wall time from cell records.
- Enforce the registered 96-call ceiling per split and 1000-call cumulative PI
  ceiling.
- Confirm zero simulator, Docker, HELICS, GridLAB-D, OpenDER, detector,
  defense, network-impairment, physical-actuator, final-evaluation, and RKA
  attacker-view access.
- Confirm that seeds 9101--9112 never appear in request or evidence bytes.

## Verdicts

`status=passed` means only that the artifacts are internally valid and the
endpoints reproduce. The scientific disposition is reported separately:

- `repair_gate_passed`: every preregistered held-out criterion passes;
- `repair_gate_failed`: infrastructure passes but at least one scientific
  criterion fails; or
- `qualification_failed`: provenance, parity, completeness, accounting,
  non-leakage, source, or access checks fail.

No auditor verdict authorizes M29-B or any simulator or final-evaluation step.
