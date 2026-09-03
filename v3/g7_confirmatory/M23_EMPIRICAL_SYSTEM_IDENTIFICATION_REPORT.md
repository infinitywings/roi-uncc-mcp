# M23 Empirical System-Identification Report

## Outcome

M23 generated and independently verified one bounded empirical sensitivity
source candidate for the two BESS targets used by the current GridEval runtime.
The source is based on one shared benign control and four target-isolated,
signed probes. All five network-isolated simulator runs completed exactly
three 10-second windows, exited zero, and were removed.

The create-once source is
`artifacts/m23_system_identification_seed6101_attempt1/m23_system_identification.json`
(SHA-256
`30d003e06d016b88d49e024857c9b74a9f9f34012a6f022b6f3a26511fc619c1`,
source ID
`m23source_300ed1e8d0d878cd5ce932e59fa8920d8a22edba3793a9cfc5d9044ca0dd9f50`).
Its status is `EMPIRICAL_SYSTEM_IDENTIFICATION_SOURCE_CANDIDATE` and its
classification is `PRELIMINARY_ONLY`. It is explicitly not an admitted or
final sensitivity resource.

## Registered design

The run was registered before simulator execution in
`artifacts/m23_system_identification_seed6101_attempt1/contract.json`
(SHA-256
`b870c6af3279f709bd096a3ed6c39f3b15f3c6428c5fd65cb0eb61e3e4b75e74`,
contract ID
`m23contract_1fe0006a3ed480a1ef6b7a084a7031aa8855c319f02c46bfbaea42a0c45ad859`).
Six M18 action requests bound the final runtime, source-builder,
configuration, and gate bytes: five `simulator_execution` actions and one
`source_generation` action, all on the `system_identification` partition.

The fixed runtime design was:

- replicate and attacker seed `6101`;
- measurement-noise seed `96101` and GridLAB-D seed `10`;
- `responsive_night` operating point;
- one shared benign treatment;
- `DER_EV1_BESS` at +30 kW and -30 kW in separate treatments;
- `DER_EV4_BESS` at +30 kW and -30 kW in separate treatments;
- one perturbed 10-second window and a 2 kVAh cap per probe;
- two later observations, with only runner `t=30` treated as post-actuation;
- detector held, Volt-VAR defense disabled, and no model or embedding call;
- image
  `sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7`;
- an ephemeral container per treatment with `--network none`; and
- final evaluation seeds `9101` through `9112` sealed.

This symmetric design estimates the local first-order column as
`(response(+30 kW) - response(-30 kW)) / 60 kW`. It also retains each
one-sided estimate and the centered residual
`(response(+30) + response(-30)) / 2 - response(0)` without selecting a
scientific linearity threshold.

## Command and timing qualification

Every probe requested, admitted, and delivered exactly one target command in
window 1. Each spent `0.0833333333 kVAh`; windows 2 and 3 delivered no probe
command. The benign treatment requested and spent nothing.

The target coupling recorder first exposed the command in row 3 at feeder
timestamp `04:00:20`: an OpenDER +30 kW generation command appeared as
-30,000 W received feeder power, while -30 kW appeared as +30,000 W. All
non-target coupling recorders retained zero command-power difference. This
confirms both the intended target isolation and the configured sign
conversion.

As in M21, runner `t=20` showed zero paired feeder response. Every signed probe
produced a finite nonzero voltage response at `t=30`; consequently, only the
third runner observation was used by the estimator.

## Empirical response columns

The central true-voltage gains, in p.u. per kW of OpenDER active-power
setpoint, are:

| Actuated target | EV1 voltage | EV3 voltage | EV4 voltage | EV5 voltage | Maximum absolute gain |
|---|---:|---:|---:|---:|---:|
| `DER_EV1_BESS` | +3.13831e-5 | -5.55264e-6 | +6.79172e-6 | +3.53093e-6 | 3.13831e-5 |
| `DER_EV4_BESS` | +7.82439e-6 | -7.71551e-5 | +1.11459e-4 | +3.24200e-5 | 1.11459e-4 |

At this one operating point, the scalar maximum-voltage gain for EV4 is
approximately 3.552 times the EV1 value. That ratio is useful for choosing a
target in a later interface smoke test, but it is not evidence of a stable
ranking across time, operating conditions, or seeds.

The central source-power responses were:

| Actuated target | Source P gain (W/kW) | Source Q gain (var/kW) |
|---|---:|---:|
| `DER_EV1_BESS` | -1,014.3163 | -29.6858 |
| `DER_EV4_BESS` | -1,047.3670 | -122.0334 |

The maximum centered voltage residual was `1.56691e-6 p.u.` for the EV1 pair
and `3.06373e-5 p.u.` for the EV4 pair. Relative to each column's 30 kW
first-order excursion, these are approximately 0.166% and 0.916%. They are
reported as local asymmetry diagnostics only; M23 preregistered no numerical
acceptance threshold and therefore makes no formal linearity claim.

The candidate future read-only payload exposes only the two scalar maximum
gains while the source preserves the complete four-node voltage vectors,
one-sided estimates, centered residuals, source-power responses, command
lineage, and raw hashes.

## Retained verifier failure and independent audit

The first generator-integrated verifier returned
`M23_source_content_drift` and `M23_source_id_drift`. A recursive comparison
located the cause: it rebuilt the manifest and therefore produced a new
`created_at_utc` value before comparing whole-source bytes. The stored source
and empirical calculations were not changed.

The failure was retained under RKA checkpoint
`chk_01M1MR10KGAJT84EJC0WT2YB4T`. Brain approved a separate read-only audit
instead of overwriting the source or rerunning the five treatments. The audit
directly checked the source and contract self-addresses, all 153 manifest
entries (1,196,592 bytes), exact generator/runtime bindings, six M18 requests,
access seals, five-run structure, center and one-sided arithmetic, scalar
payload derivation, network isolation, and teardown.

The create-once receipt is
`artifacts/m23_system_identification_seed6101_attempt1/independent_audit_receipt.json`
(SHA-256
`d0c3a539c20cc4dc3adb2910cd7bbba9c90a071a839ebc0fcde9d9e67f524030`,
audit ID
`m23audit_f424d5ca61a12125f837a4513f6b47424b62729096c9d61a0fa50e50379a532c`).
The independent audit passed with zero issues. Its receipt records both the
original verifier failure and that no source overwrite or runtime rerun
occurred.

## Runtime anomalies

All containers exited zero and `docker ps -a --filter name=g7-m23` returned no
rows after execution. The following warnings remain evidence, not exclusions:

1. the HELICS unknown-route/no-broker warning at final time 30 appeared in the
   benign and both EV1 console streams, but not in either EV4 stream;
2. all runs emitted the deprecated `helicsFederateFinalize` warning; and
3. every GridLAB-D log emitted the existing FBS switch-behavior warning.

The first warning is treatment-asymmetric and remains an operational defect.
It occurred after the completed t=30 records and did not change an exit code,
but M23 does not interpret that fact as proof of physical validity.

The runner also created 195 broken compatibility links targeting container
paths under `/work`. Only those confirmed-broken, newly generated links were
removed. All regular JSON, CSV, GLM, and log evidence was retained.

## Verification and scientific boundary

The independent audit returned `issues: []`, and the full confirmatory harness
passed 373 tests. The frozen roadmap and experiment specification retained
their expected SHA-256 values:

- roadmap report:
  `c4fc1168708c0d47d1162754296d3f731c51028650aaeab739aca42fb3aa827b`;
- experiment specification:
  `79e48fb57f01d680e3f1eef4c1273bc0895010f5eb7ab87fd85e0d4217be581d`.

M23 establishes one-seed, one-operating-point empirical source mechanics and
two target-isolated local response columns. It does not establish
repeatability, uncertainty, operating-point coverage, a final sensitivity,
linearity, source admission, real-adapter safety, stealth, attacker or LLM
advantage, detector or defense effectiveness, statistical significance,
generalization, or confirmatory evidence.

The next gate should be offline and non-actuating: qualify a field-minimized
read-only adapter that transforms this exact source into the declared
`sensitivity-result/v1` payload, rejects unregistered fields or source drift,
advances no simulation time, and exposes the identical payload to matched IA3
and IA4 consumers. Additional system-identification seeds and operating points
remain a later coverage gate, not an implicit expansion of M23.
