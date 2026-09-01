# M10 CAREER S/M resource-admission report

Status: **PASS — admission-validator structure only**

Real resource status:
`HOLD_PENDING_PREREGISTERED_THRESHOLDS_AND_INDEPENDENT_EVIDENCE`

Contract ID:
`careerresource_f3b0033341368b5eca92d350d4f06906eb969dffd5855f5829e26a0f5a97c2ca`

Synthetic fixture matrix ID:
`m10matrix_407d4406d6fa06ec18df691364e49a17b873054c6279d116e0ec998c52f0b6f7`

## Result

M10 creates separate fail-closed admission profiles for the two CAREER
resources that are allowed to vary independently of revision permission:

- `S` is a frozen, read-only set of validated process relationships;
- `M` is a frozen, read-only predictive ranking over the unchanged candidate
  library.

The validator distinguishes structural completeness from scientific validity.
Two positive synthetic envelopes demonstrate that a complete `S` or `M`
package can pass the state and lineage checks. Six negative envelopes verify
that partition overlap, thresholds chosen after evidence, parity expansion,
candidate-library drift, online updates, and treatment-outcome leakage are
rejected. Every receipt keeps the corresponding real resource on HOLD.

No real process relationship, predictive model, model output, or validation
dataset was supplied or admitted. The numerical values inside the positive
fixtures are synthetic test inputs with the explicit basis
`synthetic_fixture_only_not_scientific_threshold`. They are not proposed
scientific thresholds and cannot be reused by M11.

## Why `S` and `M` remain separate

The primary CAREER factorial is interpretable only if each resource changes one
declared information capability:

| Factor | Allowed resource | Independent validation role |
|---|---|---|
| `S` | Process-relationship identifiers, action family, qualitative response direction, and an operating-envelope reference | Held-out action-validity evidence |
| `M` | Candidate identifiers, read-only predicted scores and ranks, and a frozen model-version identifier | Held-out candidate-ranking evidence |

`S` may help a controller reason about validated process relationships, but it
does not provide a candidate score. `M` may rank the frozen candidates, but it
does not add new raw observations or action authority. The information grants
are non-substitutable, and each profile has its own metric set.

### `S` metric profile

- directional response agreement;
- normalized response error; and
- operating-envelope coverage.

### `M` metric profile

- pairwise ordering accuracy;
- top-k candidate recall; and
- normalized simple regret.

M10 names the metric families and tests higher- or lower-is-better mechanics in
synthetic fixtures; it does not yet define scientific estimators, uncertainty
procedures, or threshold values. M11 must preregister those definitions and
their development-only derivation before independent validation evidence is
examined.

## Shared admission rules

Every candidate resource must satisfy all of the following:

1. Thresholds are frozen before validation evidence is attached.
2. Resource derivation and validation partitions are disjoint.
3. Validation and later `A` confirmation partitions are disjoint.
4. Treatment outcomes cannot select thresholds or resources.
5. Evaluation records remain sealed.
6. The resource is frozen and read-only with no online update.
7. Metric profiles cannot be substituted after evidence is observed.
8. A failed resource reduces the factorial prospectively; it is not replaced
   opportunistically after seeing treatment outcomes.
9. Structural success makes a package eligible for independent review only;
   the validator does not automatically admit a real resource.

The state machine contains `draft`, `thresholds_frozen`, `evidence_attached`,
`eligible_for_independent_review`, and `rejected_fail_closed`. It deliberately
has no real-resource `admitted` terminal state in M10.

## M9 parity anchor

Both resource profiles bind the M9 contract
`careertwoint_6d57736587a6a6ad2474392a0413b784fa9633ecfa94af572798b7419b1e73a5`,
parity fingerprint
`sha256_6776210404947b827931f192f6c3a60edf58e91c586f53440287a147aaa9f671`,
and candidate-library fingerprint
`sha256_0932044cd25b3c6e77e33086282246f82b67085286f90569cc1db04c3d584aec`.

Adding `S` or `M` cannot change:

- raw observation interface;
- action authority;
- candidate library;
- budgets;
- revision permission;
- safety shield;
- independent-confirmation rule; or
- evaluation partition.

This preserves `A`, `S`, and `M` as distinct factors rather than capability
bundles.

## Synthetic fixture evidence

| Fixture | Expected result | Observed reason |
|---|---|---|
| `S_positive_structure` | Structural pass only | No structural violations |
| `M_positive_structure` | Structural pass only | No structural violations |
| `S_partition_overlap` | Reject | Validation partition is not independent |
| `M_post_evidence_threshold_freeze` | Reject | Threshold was not frozen before evidence |
| `S_parity_expansion` | Reject | Observation/parity assertion changed |
| `M_candidate_library_drift` | Reject | Candidate-library fingerprint changed |
| `M_online_update` | Reject | Resource mutation or online update enabled |
| `S_treatment_outcome_leak` | Reject | Treatment outcome was accessed |

All eleven preregistered matrix checks passed. Each envelope and receipt is
content-addressed, and each receipt records zero model, tool, simulator,
detector, embedding, actuator, and evaluation-record access.

Additional unit tests reject real-resource auto-admission, metric-profile
substitution, a failed synthetic metric, an enlarged information grant,
evaluation-partition leakage, governance mutation, and content-address drift.

## Claim boundary

Passing M10 establishes that the repository can represent and enforce the
admission workflow. It does **not** establish:

- validity of any real process relationship;
- predictive usefulness of any real model;
- an admissible scientific threshold;
- physical consequence or stealth;
- an `A`, `S`, or `M` treatment effect;
- LLM or tool-use capability;
- runtime readiness; or
- evaluation or campaign authorization.

Detector calibration remains a separate hold. A predictive ranking resource is
not a detector, and this contract does not read detector data or relax the
detector-provenance requirements.

## Machine artifacts

- `artifacts/career_resource_admission_m10.json` contains the contract, eight
  synthetic envelopes, eight receipts, and eleven gate checks.
- `career_resource_admission.schema.json` defines the interchange shape.
- `g7confirm/career_resource_admission.py` enforces profiles, lineage,
  partitions, threshold order, metric direction, parity, content addresses,
  and HOLD semantics.
- `tests/test_career_resource_admission.py` covers positive, negative, mutation,
  governance, partition, leakage, and offline boundaries.

The M10 RKA design decision is `dec_01M1DKWNJPFEM5FZDSGMAMS9GB` under mission
`mis_01KYMRDZHYN4QXC1XFTGP54E36`.

## Next gate

M11 is a development-only threshold-preregistration gate. Before any real
resource can be reviewed, it must:

1. identify candidate source bytes and derivation lineage without importing
   evaluation or treatment outcomes;
2. define the validation population, partitions, sample unit, metric
   estimators, uncertainty method, missing-data handling, and failure policy;
3. justify and freeze scientific threshold values before validation evidence;
4. retain separate `S` and `M` plans and permit either factor to be dropped;
5. receive independent review before any real evidence is attached; and
6. remain offline unless a later, separately authorized bounded validation run
   is explicitly opened.

M11 does not authorize model transport, embedding, real tool execution,
simulator or detector access, evaluation records, or campaign execution.
