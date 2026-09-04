# M27 Empirical Repeatability and Operating-Point Coverage Report

## Outcome

M27 completed its first and only create-once attempt. Thirty new
network-isolated simulator runs covered six preregistered system-identification
cells. Combined with the immutable M23 anchor, the result is a seven-cell
crossed-anchor sensitivity package spanning three seeds at
`responsive_night` and all five registered operating points at seed `6102`.

Every new container exited zero, was removed, and reported zero runtime issues.
Primary verification and the independent non-importing audit both returned
`issues: []`. The exact package is under
`artifacts/m27_repeatability_coverage_attempt1/`.

The evidence status remains `EMPIRICAL_REPEATABILITY_COVERAGE_CANDIDATE` and
the classification remains `PRELIMINARY_ONLY`. M27 does not itself admit a
sensitivity resource or authorize model-selected simulation.

## Registered design

The create-once contract is `contract.json` (SHA-256
`32571ba4737c0fa7d674e332fa34fab2ded34557fd5c58e9e20ca9fad0a274cb`,
contract ID
`m27contract_9f523653a0b78b9e3934d4bc5e95153f084eec84add9e9caca66bd12d9b70fe4`).
It was generated after the final M27 executor, runtime wrapper, source builder,
and independent auditor bytes existed and before any M27 simulator run.

The design deliberately avoids a 3-by-5 full factorial. It uses two
identifiable axes joined at seed `6102`, `responsive_night`:

- fixed-night seed axis: immutable M23 seed `6101`, plus new seeds `6102` and
  `6103`;
- fixed-seed operating-point axis: seed `6102` at `responsive_morning`,
  `responsive_midday`, `responsive_evening`, `responsive_night`, and
  `voltage_ceiling`.

Each new cell contains one shared benign control and four target-isolated
probes: +30 kW and -30 kW applied separately to `DER_EV1_BESS` and
`DER_EV4_BESS`. Every treatment uses three 10-second windows, exactly one
perturbed first window, and the M21-qualified `t=30` response index. The
design has a hard cap of 30 new runtime runs and zero retries.

The 36 M18 requests comprise 30 `simulator_execution` requests and six
`source_generation` requests. They use only system-identification seeds `6102`
and `6103`. LLM, embedding, detector, defense, external network, physical
actuator, and final-evaluation access remain false.

## Runtime result

`runtime_execution.json` has SHA-256
`18c3045cb2055576e111923f43e80a0b7eb7618825a43ffa5387e0e2112f958c`.
All 30 containers used image
`sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7`,
`--network none`, an unprivileged host-matching UID/GID, an ephemeral
`--rm` lifecycle, and no retry. Every run recorded:

- exact action-request, component-seed, pairing, and operating-point lineage;
- proposed, admitted, and delivered command traces;
- true and measured four-device voltage vectors;
- source P/Q traces and all target-coupling recorder rows;
- GridLAB-D and process logs plus raw stdout/stderr; and
- per-container exit code and exact teardown query.

All four probes in every cell delivered only their registered target in the
first window, spent `0.0833333333` kVAh, produced no feeder response through
runner `t=20`, and produced a finite nonzero response at `t=30`. The benign
runs delivered no command and spent no budget.

The runner also emitted 1,170 broken compatibility symlinks, 39 per run, whose
targets existed only under the container path `/work/examples/...`. They were
not evidence files and were excluded from the preregistered regular-file
manifest. Only those confirmed-broken links were removed after audit; all 974
regular manifest files and hashes remained unchanged.

## Seed repeatability at responsive night

The primary scalar is each target column's maximum absolute true-voltage gain
in p.u. per kW. The three fixed-night values were byte-identical across seeds
`6101`, `6102`, and `6103`:

| Target | Values at seeds 6101/6102/6103 | Mean | Sample SD | Descriptive 95% t interval, df=2 |
|---|---:|---:|---:|---:|
| `DER_EV1_BESS` | 3.13831369e-5, 3.13831369e-5, 3.13831369e-5 | 3.13831369e-5 | 0 | [3.13831369e-5, 3.13831369e-5] |
| `DER_EV4_BESS` | 1.11459403e-4, 1.11459403e-4, 1.11459403e-4 | 1.11459403e-4 | 0 | [1.11459403e-4, 1.11459403e-4] |

This is exact deterministic repeatability under the current composition, not
evidence of zero population uncertainty. The replicate seed changes the
measurement-noise seed, but the symmetric treatments use matched common random
numbers. Their central differences therefore cancel the injected measurement
noise. Across all cells and targets, the largest difference between the
measured and true primary gains was only `1.85670e-18` p.u./kW. M27 consequently
does not estimate sensitivity under unmatched measurement noise, topology
variation, parameter uncertainty, or solver variation.

## Operating-point coverage at seed 6102

| Operating point | EV1 max gain (p.u./kW) | EV4 max gain (p.u./kW) | EV4/EV1 rank margin |
|---|---:|---:|---:|
| `responsive_night` | 3.13831369e-5 | 1.11459403e-4 | 3.55157x |
| `responsive_morning` | 3.14181619e-5 | 1.12369594e-4 | 3.57658x |
| `responsive_midday` | 3.16325293e-5 | 1.17834208e-4 | 3.72510x |
| `responsive_evening` | 3.16307912e-5 | 1.17791554e-4 | 3.72395x |
| `voltage_ceiling` | 3.16909065e-5 | 1.19242788e-4 | 3.76268x |

The EV1 maximum gain spans a 1.00981 max/min ratio across the five operating
points. The EV4 maximum gain spans a 1.06983 ratio. Thus the scalar magnitudes
are condition-dependent, especially for EV4, even though the target ordering
does not change.

`DER_EV4_BESS` ranks first in all seven cells for both true and measured
central-difference metrics. The true EV4/EV1 margin ranges from 3.55157x to
3.76268x, with no ties. This supports a bounded target-ordering result for the
registered feeder, devices, probe, and operating points. It does not justify
treating the responsive-night scalar values as operating-point-invariant
quantities.

## Local asymmetry diagnostics

M27 retained the complete plus and minus one-sided columns and centered
residual vectors. Relative to the 30 kW first-order excursion, the largest
centered true-voltage residual ranges were:

- EV1: 0.1664% to 0.2503%;
- EV4: 0.9162% to 0.9327%.

These are descriptive local asymmetry measures. No scientific linearity
threshold was preregistered or selected, so M27 makes no formal linearity
acceptance claim.

## Warning evidence

The six new cells retained 139 matched warning lines in raw evidence:

- 60 HELICS Python deprecation lines, two per run;
- 30 GridLAB-D FBS switch-behavior warnings;
- 30 GridLAB-D repeated-warning summaries; and
- 19 HELICS final-time unknown-route lines affecting 15 of 30 runs.

The unknown-route incidence is treatment- and operating-point-asymmetric. It
appears after the retained `t=30` records and all processes exit zero, but M27
does not treat those facts as proof that the warning is harmless. The M23
anchor retains its previously audited warning summary; its original raw
console streams were not part of the M23 package, so M27 does not invent them.

## Independent audit and verification

The aggregate evidence is `m27_repeatability_coverage.json` (SHA-256
`043fbb972c8693c15c8a2c9a57a6478ce68d8980a03bb115dc243f81eb94d521`,
evidence ID
`m27evidence_8dea05cfdea4801ca55f3ae046eefba73effd22d921cf6aa34a3a34850069a15`).
Its manifest covers 974 files and 7,786,201 bytes.

The independent audit receipt is `independent_audit_receipt.json` (SHA-256
`2512f17434b8a5d830a101d3ecd6d85af90c75d67d4aa39864f258318165ac0e`,
audit ID
`m27audit_f8f1ba046848d602368697c0dd84c16efc37d0ce802e8ae67df45ea88e07c712`).
It imports no M27 builder and independently checks contract self-addressing,
all final-code bindings, 36 requests, 30 runtime records, command and timing
structure, estimator arithmetic, the immutable M23 anchor, seed statistics,
rank stability, every raw manifest size/hash, and all authority seals.

Verification results:

- primary M27 verifier: `issues: []`;
- independent M27 audit: `issues: []`;
- focused M27 tests: 9/9 passed;
- full `g7_confirmatory` suite: 430/430 passed; and
- M23 anchor audit recheck: `issues: []`.

The experiment specification and frozen roadmap were not modified.

## Scientific boundary and admission recommendation

M27 establishes bounded deterministic repeatability at one operating point,
bounded fixed-seed coverage across five operating points, and unanimous target
ordering within the registered two-target, one-feeder setting. It does not
estimate seed-by-operating-point interaction because only seed `6102` covers
non-night conditions. It also does not estimate population uncertainty,
topology or device-parameter uncertainty, unmatched measurement-noise effects,
general sensitivity, attacker advantage, detector/defense effectiveness, or
confirmatory evidence.

The evidence supports admitting the exact M23 scalar only as a
`responsive_night`, development-only sensitivity and supports the EV4-over-EV1
ordering as a five-operating-point preliminary observation. It does not support
admitting the M23 scalar as an operating-point-invariant resource. A separate
Brain decision must apply this scope before any simulator-connected LLM smoke.

The smallest useful next step is a decision-to-action wiring smoke at
`responsive_night` with the point-specific empirical payload, matched IA3/IA4
authority, one preselected bounded candidate, no optimization loop, and final
evaluation still sealed. Any broader multi-operating-point attacker study
should first expose an operating-point-indexed sensitivity payload rather than
silently reusing the night scalar.
