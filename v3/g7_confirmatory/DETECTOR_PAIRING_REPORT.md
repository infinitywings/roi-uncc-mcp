# G7 detector freeze, pairing, and seed-isolation report

Protocol: `g7-confirmatory-20260831-r1`  
Mission: `mis_01M1AX9Z8V40TDNQK6ZH9RZ2YM`  
Decision: `dec_01M1AX97BM3KVBA0DV9KCX72BJ`  
Plan gate: `chk_01M1AXE8YN38FAJT8D1R7HMVBV` (`GO`, offline controls only)

## Outcome

The source/interface inventory, seed guard, and paired-lineage schema are
implemented and pass offline validation. The detector is **not calibrated**,
the evaluation partition remains sealed, no paired runtime pilot was run, and
the campaign remains on **HOLD**.

These readiness states are deliberately independent:

| Readiness layer | Verdict | Evidence |
|---|---:|---|
| Detector source/interface inventory | PASS | Exact source and dependency hashes recorded in a create-once audit |
| Legacy benign calibration lineage | FAIL CLOSED | Seed and condition lineage do not satisfy the current protocol |
| Detector parameter/threshold freeze | HOLD | No admissible calibration inputs and no serialized parameter artifact |
| Paired development schema | PASS | Three non-executable smoke pairs validate exact controlled-lineage equality |
| Paired runtime pilot | NOT RUN | Outside this gate |
| Evaluation | SEALED | Evaluation seeds are rejected before runtime composition loads |
| Campaign | HOLD | `campaign_authorized=false` |

## Independent audit of the legacy inputs

The preserved `g7_pilot_b0` run remains useful historical evidence, but it
cannot be silently promoted into confirmatory detector calibration:

- its recorded seed is `1001`, which belongs to none of the current
  detector-calibration, development, or evaluation partitions;
- its summary does not explicitly record operating-point ID, Volt-VAR state,
  measurement-noise level, or measurement-noise seed;
- its GLM contains `randomseed=10` and a 07:00 clock, but inferred values are
  not accepted as substitutes for run-level lineage;
- `sensitivity_g7.json` names seven exploratory source runs but supplies no
  content-addressed source manifests, seeds, or operating-condition lineage;
  and
- the legacy `WindowDetector.fit` interface defaults its internal RNG to seed
  `7`, which is outside every current partition.

The exact legacy bytes were preserved. Nothing under
`v3/g7_condition_freeze/20260830_r1/` was modified.

## Controls added

### Seed and evaluation isolation

`g7confirm.partitions` now treats the replicate seed as the only partition
key and records every stochastic component exposed by the composition:

- attacker-policy seed = replicate seed;
- measurement-noise seed = replicate seed + `90000`, matching the frozen
  runner;
- GridLAB-D seed = the single `#set randomseed` parsed from the exact source
  GLM bytes.

Unknown seeds fail closed. Evaluation seeds fail closed in this phase. An
explicit measurement-noise seed must equal the deterministic derivation. The
bounded runtime performs these checks before loading the frozen composition;
it also rejects detector-enabled execution until a reviewed, create-once
parameter artifact exists.

### Paired benign/attack lineage

Each pair contains exactly one benign and one attack record. Both records must
have byte-for-byte equal controlled lineage for:

- protocol and spec hash;
- partition and replicate/component seeds;
- operating point and Volt-VAR state;
- measurement noise;
- window length, total windows, and duration;
- detector package identity; and
- exact dependency hashes.

Only the intervention differs. The benign intervention has zero perturbation
and zero apparent-energy allowance; the attack intervention carries the
preregistered arm and dual budget. Any controlled-field drift is rejected.

### Benign-only detector calibration design

The generated calibration inventory contains `5 operating points × 2
Volt-VAR states × 12 calibration seeds = 120` benign-only inputs at the
primary 0.002 pu measurement-noise condition. It uses fit seed `7101` from the
calibration partition and is explicitly non-executable. Its fit stage remains
blocked until every run has a complete create-once manifest and a new,
content-addressed sensitivity lineage has been reviewed.

This 120-row artifact is a completeness plan, not permission to launch 120
runs. A future gate should first authorize only a one-condition, two-seed
lineage pilot; those pilot outputs must not be used as final thresholds.

## Create-once artifacts

- `artifacts/detector_pairing/detector_provenance_audit.json`
  - detector package ID: `g7det_57ee48fcf6887a010437`
  - SHA-256: `5631d32d74ac0e7098a3207f298de117024eef5b78fe01289931635b63c52dd6`
- `artifacts/detector_pairing/benign_calibration_plan.json`
  - 120 non-executable benign inputs
  - SHA-256: `e66e25b8f4d7502e33a28c8b67030aadacdd627ff23c6b7c18604e1d6244a0ae`
- `artifacts/detector_pairing/paired_development_smoke_plan.json`
  - three pairs, one per search arm, development seed `8101`
  - SHA-256: `c074bcef2523dfa8048d0fe7aae7048b50b7e6db6966190ff20f056daf678db8`

A deliberate second write to the paired-plan path returned exit code `2` with
`OutputExistsError`; the existing bytes were not replaced.

## Validation

- `python3 -m unittest discover -s tests -v`: **43/43 passed**.
- `python3 -m g7confirm.cli validate-spec --spec experiment_spec.yaml`: PASS.
- JSON schema syntax and Python bytecode compilation: PASS.
- Artifact checks: evaluation unopened, campaign unauthorized, all smoke-pair
  controls equal, and all 12 calibration seeds represented across 10
  operating-condition cells.

No model request, embedding request, Docker/HELICS/GridLAB-D run, GPU change,
service restart, evaluation access, or campaign execution occurred in this
mission.

## Next gate

The next safe step is a bounded calibration-lineage pilot, not detector
fitting and not campaign execution. It should generate one operating point ×
one Volt-VAR state × two calibration seeds, prove all run-level fields and
hashes are emitted directly by the runtime, and produce a separately reviewed
sensitivity-provenance design. Final detector calibration stays on HOLD until
that pilot passes and the full benign-only calibration inputs are authorized.
