# M12 CAREER clean-source freeze design report

Status: **PASS — design contract only**

Real-source status: **UNBUILT**

Contract ID:
`careersourcefreeze_648776649fcaa43a3ecce5fab19aced608c427646b086c0f6bc2128a611a61f3`

Decision:
`dec_01M1DN5GNS59V8GEP19E08T4PW`

## Result

M12 defines how clean candidate source packages for CAREER resources `S` and
`M` must be constructed, partitioned, content-addressed, reviewed, and frozen.
It repairs the design defects found by M11 without promoting the existing
exploratory files, assigning real data, selecting a model family, issuing a
review receipt, or choosing a scientific threshold.

The two resource profiles remain independent:

- `S` may add only validated process-relationship records for one EV
  aggregator's active charging setpoint and exposed bus-voltage response.
- `M` may add only validated scores and ranks over the exact three M9
  candidate IDs for the preregistered primary physical endpoint.

Neither profile changes raw observations, action authority, the M9 candidate
library, revision permission, budgets, or evaluation access. Neither profile
may depend on the other profile's derived resource.

## Partition registry

M12 defines eight future empirical roles:

| Role | Factor | Exclusive purpose |
|---|---|---|
| `S_source_derivation` | `S` | Derive the clean `S` source |
| `S_threshold_design` | `S` | Design future `S` thresholds |
| `S_independent_validation` | `S` | Test future action validity |
| `M_source_derivation` | `M` | Derive the clean `M` source |
| `M_threshold_design` | `M` | Design future `M` thresholds |
| `M_independent_validation` | `M` | Test future ranking validity |
| `ASM_factor_confirmation` | `A/S/M` | Estimate future factor effects |
| `evaluation_sealed` | Evaluation | Remain inaccessible |

The future sample identity is the joint
`factor_role_run_seed_operating_cell_episode_block`. Exact empirical blocks
must be pairwise disjoint, including across `S` and `M`. Static tracked code,
environment, feeder configuration, and M9 protocol definitions may be shared;
empirical blocks and derived resources may not.

All eight assignments remain `null` with status
`UNASSIGNED_DESIGN_ONLY`. M12 defines the order for a later assignment: freeze
the sample identity and role registry, assign blocks without outcome access,
verify disjointness, obtain independent partition review, and freeze the
assignment manifest before derivation.

## Clean `S` source profile

The `S` profile resolves the authority mismatch in the exploratory four-device
sensitivity artifact:

- authority is exactly one EV aggregator;
- the controlled variable is active charging setpoint;
- the response is exposed bus-voltage telemetry;
- development probes must be paired and symmetric;
- other-device authority is prohibited; and
- the reactive-power axis is explicitly outside the primary scope rather than
  represented by an unexplained all-zero matrix.

A future source package must bind the tracked generator commit and hash,
environment and feeder configuration, operating-cell and development-seed
registries, symmetric perturbation schedule, source partition, raw input
manifest, and derived relationship-resource bytes. Every corresponding M12
slot is `null`.

The future relationship records are limited to operating-cell ID, action ID,
signed active-setpoint delta, voltage-response statistic, qualitative response
direction, and source-block ID. Numerical precision and operating-cell coverage
must be frozen before source generation, and identical manifests must produce
identical bytes.

## Clean `M` source profile

The `M` profile binds the exact M9 candidate-library fingerprint
`sha256_0932044cd25b3c6e77e33086282246f82b67085286f90569cc1db04c3d584aec`
and its ordered three candidate IDs. It predicts only
`maximum_scaled_voltage_envelope_excess`; detector or alarm outcomes are not a
training label and remain a separate evidence channel.

M9 candidates are qualitative and non-executable. M12 therefore requires a
separate engineering-instantiation manifest that preserves the M9 candidate
IDs, plus a content-addressed endpoint definition. Both slots remain `null`.
This prevents a physical ranking from being claimed over uninstantiated tokens
and prevents engineering choices from silently changing the candidate library.

The future ranker must be tracked, deterministic, frozen, read-only, and
reproducible. It may condition only on context already visible under the active
`A` condition, so `M` cannot add raw observations or revision authority. The
algorithm family is deliberately unselected before source review, online update
is prohibited, and ties must follow the frozen M9 candidate order.

## Contamination controls

Both derivations reject:

- treatment-arm outcomes;
- detector or alarm outcomes;
- evaluation records;
- factor-confirmation outcomes;
- independent-validation outcomes during derivation;
- the other factor's derived resource;
- online feedback or updates; and
- untracked or unhashed source bytes.

This preserves the prospective order: clean source freeze, independent source
review, later threshold design, later independent validation, and only then a
possible resource-admission decision.

## Independent review protocol

M12 requires two distinct reviewers, and the source author cannot serve as a
reviewer:

1. an independent data-lineage reviewer checks source bytes and partition
   separation; and
2. an independent domain-method reviewer checks capability semantics and
   deterministic reproducibility.

Each future receipt must bind the M12 contract, profile, tracked code revision,
static input hashes, partition assignment, input manifest, and output manifest.
Threshold design cannot begin until both reviewers accept the exact same frozen
source package.

The receipt templates are intentionally unissued: reviewer IDs, profile IDs,
manifest hashes, decisions, and receipt IDs are empty or `null`. M12 does not
simulate independent approval.

## Machine artifacts

- `artifacts/career_source_freeze_design_m12.json` contains the canonical
  partition registry, two source profiles, empty empirical slots, unissued
  review templates, governance status, and M13 boundary.
- `career_source_freeze_design.schema.json` defines the interchange shape.
- `g7confirm/career_source_freeze_design.py` enforces content addressing,
  exact M9 lineage, null empirical slots, single-aggregator authority,
  partition separation, S/M independence, and review-order semantics.
- `tests/test_career_source_freeze_design.py` covers all design boundaries and
  rejects populated assignments, review decisions, candidate drift, governance
  relaxation, and unacknowledged mutation.

Fifteen M12 unit tests pass. Full-repository verification is reported at commit
time. External JSON Schema validation is not claimed when the optional
`jsonschema` package is unavailable; JSON parsing and the stricter Python
semantic validator remain mandatory.

## Claim boundary

Passing M12 establishes a reviewable source-freeze design. It does **not**
establish:

- a generated, reviewed, or frozen real source package;
- a real partition assignment;
- a valid relationship, predictive model, score, or rank;
- a scientific threshold or finalized estimator;
- physical consequence, stealth, or a factor effect;
- model, embedding, tool, simulator, or detector capability;
- evaluation access; or
- campaign authorization.

Both real resources remain on HOLD, every threshold remains unset, evaluation
remains sealed, and the campaign remains on HOLD.

## Next gate

M13 may implement an offline validator over synthetic positive and negative
source-package manifests. Its negative matrix should cover partition overlap,
untracked inputs, missing physical instantiation, candidate drift, additional
authority or observations, cross-factor resource dependency, online update,
outcome contamination, self-review, reviewer reuse, and receipt-binding drift.

M13 may not freeze a real source, assign a real partition, issue a real review
receipt, select a scientific threshold, or access a model, embedding service,
tool, simulator, detector, actuator, evaluation record, or campaign.
