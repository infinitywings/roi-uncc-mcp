# G3 Selected-Cadence Repeatability

**Verdict: PASS.** Two independent repeat pairs at the selected 10-second coupling cadence were compared.

| Pair | Identity | Adapter structure/text | Adapter numeric | Physical structure/text | Physical numeric | Process/assertions |
|---|---:|---:|---:|---:|---:|---:|
| pulse coupling10 r2 vs r3 | PASS | PASS | PASS | PASS | PASS | PASS |
| null coupling10 r1 vs r2 | PASS | PASS | PASS | PASS | PASS | PASS |

## Numerical audit

The acceptance tolerance is `abs_tol=1e-12` and `rel_tol=1e-12`. Exact numerical equality is reported separately and is not weakened by the tolerance gate.

| Pair | Adapter values | Adapter nonexact | Adapter max abs diff | Physical values | Physical nonexact | Physical max abs diff |
|---|---:|---:|---:|---:|---:|---:|
| pulse coupling10 r2 vs r3 | 1176 | 0 | 0 | 1008 | 0 | 0 |
| null coupling10 r1 vs r2 | 1176 | 0 | 0 | 1008 | 0 | 0 |

## Identity policy

All identity fields must match exactly. The sole narrow exception is `effective_config_sha256`: a hash difference may pass only when the parsed HELICS configurations differ exclusively in `coreName`, `name`, or `logfile` and are identical after those execution labels are normalized. Publications, subscriptions, object/property bindings, units, periods, topology, and all other configuration content remain load-bearing.

- **pulse coupling10 r2 vs r3:** identity exact = `true`; execution-label exception used = `false`.
- **null coupling10 r1 vs r2:** identity exact = `true`; execution-label exception used = `false`.

## Process and assertion audit

- **pulse coupling10 r2 vs r3:** both processes successful = `true`; assertion sets/values exact = `true`; all assertions true = `true` (28 assertions per run).
- **null coupling10 r1 vs r2:** both processes successful = `true`; assertion sets/values exact = `true`; all assertions true = `true` (21 assertions per run).

## Scope

This gate establishes rerun repeatability for the recorded selected-cadence pulse and null arms. It does not establish correctness of the physical model, external validity, or repeatability at other coupling cadences/platforms.
