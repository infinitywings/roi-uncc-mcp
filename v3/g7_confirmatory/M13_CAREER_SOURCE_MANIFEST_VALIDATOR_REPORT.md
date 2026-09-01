# M13 CAREER synthetic source-manifest validator report

Status: **PASS — synthetic validator structure only**

Matrix ID:
`m13matrix_4025c6e7342d20113eb56bfd0c75676f9160389db968456b88603f61156ae7a3`

Decision:
`dec_01M1DNSMSJG0PP22RA8GC40CXX`

## Result

M13 implements the M12 clean-source rules as a fail-closed validator. Two
positive synthetic manifests pass with verdict
`PASS_SYNTHETIC_STRUCTURE_ONLY`. Twelve single-fault synthetic manifests are
rejected with one exact reason code each.

All hashes, block IDs, source identities, model identities, and reviewer
identities are deterministic synthetic fixtures. A positive receipt leaves the
real source unbuilt, partitions unassigned, real reviews unissued, scientific
thresholds unset, both resources on HOLD, and evaluation sealed. The validator
refuses a non-synthetic envelope.

## Synthetic fixture matrix

| Fixture | Expected result | Exact reason code |
|---|---|---|
| `S_positive_structure` | Pass structure only | None |
| `M_positive_structure` | Pass structure only | None |
| `S_partition_overlap` | Reject | `partition_overlap_or_invalid_assignment` |
| `S_untracked_source` | Reject | `untracked_source` |
| `S_authority_expansion` | Reject | `S_authority_expansion` |
| `S_reactive_zero_imputation` | Reject | `S_reactive_axis_scope_drift` |
| `M_missing_physical_instantiation` | Reject | Missing engineering-instantiation content address |
| `M_candidate_drift` | Reject | `M_candidate_library_drift` |
| `M_new_observation` | Reject | `M_new_observation_grant` |
| `M_online_update` | Reject | `M_online_update_enabled` |
| `M_detector_outcome_contamination` | Reject | `prohibited_outcome_or_resource_access` |
| `M_cross_factor_dependency` | Reject | `M_cross_factor_resource_dependency` |
| `S_reviewer_reuse` | Reject | `reviewer_independence_violation` |
| `M_review_binding_drift` | Reject | `review_package_binding_mismatch` |

Every negative is generated from its factor's positive base envelope, mutated
once, and then content-readdressed. This distinguishes a semantic rejection
from a stale-hash rejection and keeps the matrix useful for auditing individual
controls.

## Enforced package boundary

Each source package must:

- identify the exact M12 profile;
- remain explicitly synthetic in M13;
- bind every M12 empirical slot to a syntactically valid synthetic SHA-256;
- declare tracked source bytes;
- preserve the factor's exact information grant, derivation contract, and
  output template; and
- carry its own content-addressed package ID.

For `S`, the validator separately checks one-device active-setpoint authority
and the explicit exclusion of the reactive axis. For `M`, it separately checks
the exact ordered M9 candidate IDs, no new raw observation, no online update,
and no dependency on the `S` resource. The synthetic M ranker identifier is not
a scientific model-family choice.

## Partition and contamination boundary

Each synthetic partition manifest covers all eight M12 roles with unique block
IDs, the frozen compound sample identity, no outcome access before assignment,
and an unchanged real-partition status. Duplicate blocks fail closed.

The source envelope separately accounts for treatment, detector/alarm,
evaluation, confirmation, independent-validation, cross-factor-resource,
online-feedback, and untracked-source access. Any prohibited access fails the
validator. Model, embedding, tool, simulator, detector, actuator, and evaluation
access counters must all remain zero.

## Review boundary

The validator requires the two M12 review stages in order. Reviewers must be
distinct from one another and from the source author. Both synthetic receipts
must bind the same content-addressed package and retain the real review status
`UNISSUED_DESIGN_ONLY`.

The synthetic decision token is `PASS_SYNTHETIC_STRUCTURE_ONLY`; it is not an
approval token for a real source. Reusing a reviewer or changing a package
binding fails closed after the review receipt is readdressed.

## Machine artifacts

- `artifacts/career_source_manifest_matrix_m13.json` stores the fourteen case
  specifications, fourteen receipts, seventeen gate checks, status, and next
  boundary.
- `career_source_manifest_matrix.schema.json` defines the matrix interchange
  shape.
- `g7confirm/career_source_manifest_validator.py` builds envelopes, applies
  declared mutations, validates packages, partitions, access, and reviews, and
  emits content-addressed receipts.
- `tests/test_career_source_manifest_validator.py` covers the canonical matrix,
  all single-fault results, content-address mutation, malformed nesting, real-
  envelope rejection, status preservation, and next-gate restrictions.

Sixteen M13 unit tests pass. Full-repository verification is reported at commit
time. External JSON Schema validation is not claimed when the optional
`jsonschema` package is unavailable; JSON parsing and the stricter Python
semantic validator remain mandatory.

## Claim boundary

Passing M13 establishes that the repository can reject the specified malformed
source manifests. It does **not** establish:

- a real source, partition assignment, source freeze, or review;
- a valid physical relationship, model, score, or ranking;
- a scientific threshold or admitted resource;
- physical consequence, stealth, or a factor effect;
- model, embedding, tool, simulator, or detector capability;
- evaluation access; or
- campaign authorization.

## Next gate

M14 is an independent source-generation prerequisite review boundary. It may
assemble a review packet over exact committed code, schemas, candidate bindings,
partition requirements, threat-model authority, contamination controls, abort
criteria, and the proposed bounded source-generation plan. It may not perform
the independent review itself, assign real blocks, generate a real source,
select thresholds, or access runtime or evaluation systems.
