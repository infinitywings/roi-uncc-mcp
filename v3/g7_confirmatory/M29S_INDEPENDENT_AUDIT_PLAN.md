# M29-S independent audit plan

## Independence boundary

The independent auditor must not import the M29-S generator, runner,
deterministic compiler, validator, retrieval adapter, response parser, or
primary verifier. It may use only Python's standard library and serialized
create-once artifacts. Its source hash is stored in every receipt.

## Inputs

The auditor receives the frozen factorial plan, strict schemas, design fixture,
development-freeze receipt, execution contract, visible evidence, corpus
manifest, embedding receipt, model requests and responses, tool transcripts,
initial drafts, final programs, and primary receipt. Latent specifications and
slot oracles are read only during endpoint recomputation and are never copied
into tested-arm requests or tool results.

## Required checks

### Split and source integrity

- Recompute every content ID and SHA-256 hash.
- Prove M29-R, M29-S development, and M29-S held-out disjointness across
  condition IDs, seeds, latent tuples, semantic digests, rendered bytes, and
  answer-bearing doctrine identifiers.
- Reject source drift, unregistered artifacts, overwrite, retry, missing cell,
  or held-out access before the development freeze.

### Factorial parity

- Reconstruct the 2 x 2 x 2 interface, feedback, and retrieval matrix.
- Require exactly two model calls for every causal factorial cell.
- Require exactly one call for one-shot references and exclude those arms from
  validator-effect estimates.
- Verify byte-identical initial visible evidence and model settings for every
  matched contrast; only registered factor fields may differ.
- Confirm that retrieval changes selected frozen-corpus passages only.

### Interface integrity

- Require flat arms to emit only a final-program draft.
- Require staged arms to emit `EvidenceLedger`, `SemanticSlots`, and the
  deterministic final-program projection.
- Recompute the projection and reject any substantive value introduced or
  repaired by deterministic code.
- Require every staged semantic slot to cite only visible evidence IDs.
- Canonicalize only fields registered as unordered sets.

### Validator-tool non-leakage

- Require every tool name, argument, result key, and diagnostic code to be in
  the frozen allowlist.
- Require diagnostic results to contain only code and affected-slot pairs,
  draft lineage, and visible-input lineage.
- Reject expected values, corrected programs, oracle fields, numeric scores,
  hidden labels, recommendations, or unregistered strings.
- Recompute call ordering: initial draft, one feedback phase, one revision,
  final submission, with no retry.
- Confirm that neutral self-review receives no validator-derived information.

### Endpoint and contrast recomputation

- Recompute exact accuracy for every ledger and semantic slot.
- Recompute evidence-lineage completeness, all-slot success, mirrored-pair
  success, initial correctness, repair conversion, repair regression,
  refusals, and invalid outputs.
- Recompute interface, validator, retrieval, deliberation, and registered
  interaction contrasts from paired cells.
- Exclude one-call references from equal-call causal contrasts.
- Recompute every held-out threshold without importing primary code.

### Accounting and seals

- Recompute model calls, tokens, embedding calls and items, tool calls,
  invalid drafts, refusals, revisions, and wall time.
- Enforce 288 calls per split, 576 additional calls, 677 conservative
  cumulative calls, and zero retries.
- Confirm zero simulator, Docker, HELICS, GridLAB-D, OpenDER, detector,
  defense, network-impairment, physical-actuator, final-evaluation, and RKA
  attacker-view access.
- Confirm that seeds 9101 through 9112 and all M29-R answer-bearing bytes are
  absent from tested requests.

## Verdicts

`status=passed` means only that artifacts are internally valid and endpoints
reproduce. Scientific disposition is separate:

- `mechanism_gate_passed`: all preregistered held-out criteria pass;
- `mechanism_gate_failed`: infrastructure passes but at least one scientific
  criterion fails; or
- `qualification_failed`: provenance, parity, completeness, accounting,
  non-leakage, source, or access checks fail.

No auditor verdict authorizes M29-B, simulator access, final evaluation, or a
physical, stealth, detector-evasion, defense-bypass, generalization, or
confirmatory claim.
