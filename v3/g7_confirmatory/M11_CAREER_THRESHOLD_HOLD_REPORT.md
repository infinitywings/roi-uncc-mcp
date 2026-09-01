# M11 CAREER source-lineage and threshold HOLD report

Status: **HOLD — threshold prerequisites are not met**

Contract ID:
`careerthresholdhold_4ff524e10e76cc36a68aec92ac6fcddda99802cf0699e419f930ad1f03588468`

Decision:
`dec_01M1DMKWJ9BM6YV2E0MNDJZRDJ`

## Result

M11 audited the available candidate sources for the CAREER process-
relationship resource `S` and predictive-ranking resource `M`. Neither source
is eligible for scientific threshold selection or real-resource admission.
Both are preserved as exploratory lineage, and every scientific threshold in
the canonical artifact remains `null` with status
`UNSET_NOT_SCIENTIFICALLY_JUSTIFIED`.

This is a positive governance result, not a scientific validation failure.
The M10 validator correctly requires evidence and threshold ordering that the
current workspace cannot support. M11 therefore records the exact source bytes,
the bounded audit findings, draft estimator skeletons, and the repairs required
before threshold design may begin. It does not invent convenient values from
the M10 synthetic fixtures or from prior treatment outcomes.

## Bounded audit scope

The read-only source audit covered targeted filenames, content, JSON structure,
hashes, byte counts, Git status, numerical consistency, and RKA retrieval in:

- `v3/opender_federate`;
- `v3/g7_condition_freeze/20260830_r1`;
- `v3/g7_confirmatory`; and
- RKA project `prj_01KYMPK10PE9YH1TJ84PAVB9Z6`.

The negative source finding is explicitly bounded to these roots and methods.
It does not claim that a suitable source can never exist elsewhere.

## Candidate `S` audit

The inspected exploratory artifact is
`v3/opender_federate/sensitivity_g7.json`:

| Property | Observed value |
|---|---|
| Bytes | `16497` |
| SHA-256 | `05d486024b5106dec266c512d008294ff41c6485011093baf67a9737293bf8f8` |
| Git tracked | No |
| Freeze copy byte-identical | Yes |
| Declared probe-based | Yes |
| `Sp` / `Sq` shapes | `4 x 4` / `4 x 4` |
| Nonzero `Sq` entries | `0` |
| Reference rows | `84` |

The artifact cannot be promoted to the primary CAREER `S` resource because:

1. Its seven declared `source_runs` omit the exact baseline whose `v_ref`,
   `p_ref`, and `q_ref` arrays it contains. That baseline trace has SHA-256
   `3945f0bc0bbe638c255d6284e6116661a116a415e93d45ee56cbd703cae5ab14`.
2. Four probe traces exist, but their paths or hashes are not bound by the
   artifact's source manifest.
3. No deterministic generator for the sensitivity artifact was found in the
   declared scan scope.
4. Seed and operating-condition lineage is incomplete.
5. The four-device authority does not match the primary single-EV-aggregator
   intervention.
6. The all-zero reactive-power channel has not been validated as an intentional
   scope restriction.
7. The source bytes are untracked.

The four observed probe-trace hashes are retained in the machine artifact so a
future repair can bind exact bytes rather than rely on directory names.
Historical exploratory L2 results remain historical evidence; M11 only rejects
their promotion into a CAREER admission resource.

## Candidate `M` audit

The inspected exploratory trace is
`v3/opender_federate/g7_l5b_search_trace.json`:

| Property | Observed value |
|---|---|
| Bytes | `1729` |
| SHA-256 | `f41f40c610336b00bbc815d34d68831aa65f85e70508cb2df71ac1d57691a670` |
| Episodes | `5` |
| Git tracked | No |
| Exact M9 candidate ranking | No |
| Treatment/detector outcomes used | Yes |

Its associated untracked script has SHA-256
`748f284fe7b90b25b8aea1328cbc72626a0dd0cf1f266720081bc33cdcfba4fb`.
The trace is not an admissible `M` resource because it uses treatment and
detector outcomes during search, does not rank the exact M9 candidate library,
has no independent ranking-validation partition, and is not a frozen read-only
ranking artifact. It remains useful only for exploratory L5b lineage.

## Threshold-preregistration boundary

M11 preserves the M10 metric families but does not finalize estimators:

| Factor | Draft metric families |
|---|---|
| `S` | Directional response agreement, normalized response error, operating-envelope coverage |
| `M` | Pairwise order accuracy, top-k candidate recall, normalized simple regret |

The sample unit is provisionally an independent validation block, not a window.
The uncertainty method remains unselected beyond requiring a cluster-aware
interval over independent blocks. Threshold-design and validation partitions
are both unset. Missing or invalid blocks fail admission completeness.

Before any threshold can be proposed, the next design must freeze disjoint
development partitions, exact estimators, engineering normalization, the
uncertainty method, and independent review order. Exploratory, treatment,
detector, or evaluation outcomes cannot select these choices.

## Required source repairs

For `S`, M12 must design a tracked deterministic source scoped to one EV
aggregator setpoint, with content-addressed input/output manifests, explicit
development seeds and operating conditions, disjoint design and validation
partitions, and no treatment, detector, or evaluation outcomes.

For `M`, M12 must design a tracked frozen read-only ranker over the exact M9
candidate library, with a content-addressed derivation manifest, disjoint design
and validation partitions, no online update, and no treatment, detector, or
evaluation outcomes.

The two factors remain independent. Repairing one does not admit the other, and
a failed factor reduces the factorial prospectively instead of triggering a
post-outcome replacement.

## Machine artifacts

- `artifacts/career_threshold_hold_m11.json` contains the content-addressed
  source audit, threshold nulls, draft estimator skeletons, repairs, status, and
  next-gate declaration.
- `career_threshold_hold.schema.json` defines the interchange shape.
- `g7confirm/career_threshold_hold.py` enforces exact source findings,
  content addressing, null thresholds, HOLD semantics, and governance limits.
- `tests/test_career_threshold_hold.py` covers source preservation, threshold
  invention, hash drift, governance mutation, and bounded absence claims.

Twelve M11 unit tests pass. Full-repository verification is reported at commit
time. External JSON Schema validation is not claimed when the optional
`jsonschema` package is unavailable; JSON parsing and the stricter Python
semantic validator remain mandatory.

## Claim boundary

M11 does **not** establish:

- a valid real `S` or `M` resource;
- a scientific threshold or finalized estimator;
- physical consequence, stealth, ranking quality, or a treatment effect;
- LLM, tool-use, detector, or embedding capability;
- runtime readiness; or
- evaluation or campaign authorization.

Evaluation remains sealed, both resources remain on HOLD, and no model,
embedding service, real tool, simulator, detector, actuator, or evaluation
record was accessed by the M11 contract.

## Next gate

M12 is an offline clean-candidate source-freeze design. It may define source
manifest schemas, partition roles, deterministic derivation requirements, and
independent-review receipts. It may not create scientific threshold values,
read validation or treatment outcomes, execute a simulator or detector, call a
model or embedding service, admit a real resource, or open evaluation.
