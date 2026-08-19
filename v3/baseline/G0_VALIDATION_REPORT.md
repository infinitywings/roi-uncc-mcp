# G0 Baseline Validation Report

Date: 2026-07-29  
Status: **PASS WITH CARRIED LIMITATIONS — G1/G2 component proofs may begin;
attack comparison remains prohibited**

## Scope and decision

This gate asks whether the GridEval v2 campaign is a sufficiently valid,
immutable comparison baseline for the v3 NATIG and OpenDER experiments. The
audit is deliberately non-destructive: it reads the frozen v2 campaign and
writes only new v3 artifacts. It does not rerun the co-simulation or alter the
paper.

The 45 planned slots reconcile exactly as 37 completed results and 8 failed
runs. The corrected analysis confirms a large observed AI-V2 versus Random
TVD difference at Hours 4 and 7. However, G0 cannot close because the retained
controller configuration and source do not support the paper's claimed
10-second *physical* defender cadence. The configuration declares a 60-second
HELICS period, while the source executes 10-second logical loop iterations.
Under HELICS period semantics, multiple logical decisions can therefore occur
at one granted time and use unchanged physical inputs. No successful
controller grant/decision trace was retained to demonstrate otherwise.

The corrected instrumented baseline has now been run. GridEval v3 adopts the
measured 10-second internal-actuation / 20-second controller-visible-feedback
contract. NATIG and OpenDER component proofs may begin independently. The
current v2 result must not be described as validating fresh 10-second
physical feedback, and no attack comparison may begin before later benign
equivalence gates pass.

## Reproducibility and identity

- Frozen v2 campaign tree: 44 files,
  `666715d9c77550928bcfb02ffcc06cd3532277cb50cc09722dda1abff9f3053d`
- Parsed completed result files: 37 unique files with no validation issues.
- Failed slots reconstructed from the retained run logs: 8.
- Planned/completed/failed reconciliation: `45 = 37 + 8`.
- Analysis environment: Python 3.10.12, NumPy 2.2.6, SciPy 1.15.3.
- Bootstrap: 50,000 deterministic resamples per contrast.
- A second run in a fresh temporary directory produced byte-identical JSON
  and CSV outputs.
- The default output directory is create-once; the runner refuses to
  overwrite an existing result.

Canonical machine-readable evidence:

- `reanalysis_r4/v2_reanalysis.json`
- `reanalysis_r4/completion_matrix.csv`
- `reanalyze_v2.py`
- `cadence_probe_r1/cadence_probe.json`
- `run_helics_cadence_probe.py`
- `value_freshness_probe_r2/value_freshness_probe.json`
- `run_helics_value_freshness_probe.py`
- `v2_freeze_manifest.json`

The create-once `reanalysis/` result is retained but superseded: its
statistical and missingness results are correct, while its initial static
timing map treated a request for current time zero as a zero grant. The live
HELICS probe showed that request advances to the first permitted grant.
Revision `reanalysis_r2/` corrected the controller map. Revision
`reanalysis_r3/` additionally captured the GridLAB-D period and minimum
timestep constraints, but its narrative described Feeder B's parsed 120-second
minimum as 60 seconds. Revision `reanalysis_r4/` corrects that sentence and is
canonical.

## Corrected quantitative results

The run, rather than the timestep, is the experimental unit. Primary tests are
one-sided Welch tests (`equal_var=False`) and exact independent-label
permutation tests. The exact tests are emphasized because cell sizes are only
3–5 and some cells have zero variance. Holm adjustment covers the two
responsive operating-point H1 tests (Hours 4 and 7); Hour 14 is a prespecified
ceiling/negative-control condition.

| Operating point | AI-V2 TVD | Random TVD | Difference | EVG | Welch p | Exact p | Holm exact p |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hour 4 | 135 ± 30 s (N=4) | 60 ± 49 s (N=4) | 75 s | 2.25× | 0.02393 | 0.05714 | 0.05714 |
| Hour 7 | 180 ± 0 s (N=4) | 75 ± 30 s (N=4) | 105 s | 2.40× | 0.002993 | 0.01429 | 0.02857 |
| Hour 14 | 295 ± 0 s (N=3) | 295 ± 0 s (N=3) | 0 s | 1.00× | undefined/equal constants | 1.0 | excluded |

Interpretation:

- Hour 7 remains significant under exact inference with Holm correction.
- Hour 4 is significant under Welch/Holm but not under exact permutation
  inference (`p=0.05714`). It should be described as a large observed effect
  with limited exact-test evidence, not an unqualified replicated
  `p < 0.05` result.
- The manuscript labels its tests Welch, but
  `v2/analysis/analyze_v2.py` calls `scipy.stats.ttest_ind(a, b)` without
  `equal_var=False`; the published p-values are pooled-variance Student
  results.
- Hour 14 is saturated and cannot validate attacker discrimination.

## Failure and missingness audit

Failures are not exchangeable-looking:

- AI-V1 completed 15/15; Random completed 11/15; AI-V2 completed 11/15.
- Seed 2 completed 4/9 versus 33/36 for all other seeds
  (two-sided Fisher exact `p=0.00443`).
- Retained per-condition logs reconcile all eight wrapper failure markers and
  partial progress, but contain no exception or root-cause text. The campaign
  report's “HELICS timeout” classification cannot be independently recovered
  from those logs.

Worst-case sensitivity assigns every missing TVD only its physical bound
`[0, 300]` seconds:

| Operating point | AI-V2 mean bound | Random mean bound | V2−Random bound |
|---|---:|---:|---:|
| Hour 4 | 108–168 s | 48–108 s | 0–120 s |
| Hour 7 | 144–204 s | 60–120 s | 24–144 s |
| Hour 14 | 177–297 s | 177–297 s | −120–120 s |

Thus the Hour-7 direction survives the bounded missing-data stress test.
Hour 4 cannot exclude equality under the most adverse allowed completion
outcomes.

## Controller timing defect

The physical cadence claim is contradicted by the frozen implementation:

1. `v2/controller/v2_control.json` declares `"period": 60`.
2. `v2/controller/ev_controller_v2.py` iterates logical time in 10-second
   increments and requests time only while `granted_time < t`.
3. HELICS documents that period constrains valid grants to
   `n × period + offset`; an invalid or already-current request advances to
   the next valid grant.
4. In a live HELICS 3.6.1 probe, the frozen loop's initial request for logical
   `t=0` was granted at 60 seconds. Logical iterations 0, 10, 20, 30, 40, 50,
   and 60 therefore executed at that one grant. The same grouping repeated at
   120, 180, 240, and 300 seconds. HELICS itself emitted time-mismatch
   warnings for the requests at 70, 130, 190, and 250 seconds.
5. The attacker's cycle-position score is computed from the configured
   10-second schedule, not from an observed controller action or grant.
6. No successful campaign controller trace records granted time, decision
   time, input sample identity, or actuation time.

The observed TVD data remain valid descriptions of what this frozen
implementation produced. They do not validate statements that every AI attack
arrived “immediately after the controller acts,” that the defender physically
polled every 10 seconds, or that diversified attacks required one fresh
physical control cycle per 10 seconds.

Primary semantics reference:
[HELICS timing configuration](https://docs.helics.org/en/latest/user-guide/fundamental_topics/timing_configuration.html).

## Live HELICS cadence experiment

The versioned probe compared three 300-second controller-loop conditions in
the local `docker-cosim` runtime, using HELICS 3.6.1:

| Condition | Requests | Distinct grants used | Maximum logical decisions at one grant | Result |
|---|---:|---:|---:|---|
| Frozen v2 loop, period 60 | 5 | 5 | 7 | Fails cadence invariant |
| Period changed to 10 only | 29 | 29 | 2 | Startup still grouped |
| Repaired loop, period 10 | 29 | 30 | 1 | Passes isolated grant invariant |

The repaired condition initializes its first decision at HELICS current time
zero, then explicitly requests every later 10-second decision time. Every
logical decision is aligned to exactly one grant. An independent fresh
container run produced byte-identical probe JSON.

This is a real HELICS timing experiment, but it deliberately isolates time
grants.

## Two-federate value-freshness experiment

A second live HELICS 3.6.1 experiment paired a 10-second synthetic plant
federate with the frozen or repaired controller loop. The plant published a
monotonically increasing sample ID, allowing stale input reuse to be measured
directly.

| Condition | Controller decisions | Distinct non-default samples observed | Adjacent repeated samples | Maximum decisions at one grant |
|---|---:|---:|---:|---:|
| Frozen v2 loop | 30 | 5 | 25 | 7 |
| Repaired period-10 loop | 30 | 29 | 0 | 1 |

The frozen observation sequence was
`5×7, 11×6, 17×6, 23×6, 29×5`: each HELICS input was reused for several
nominal 10-second logical decisions. The repaired sequence was one initial
default at time zero followed by samples `0…28`, exactly one fresh sample per
post-start decision. A fresh container rerun produced byte-identical JSON.

This establishes the grant and generic HELICS value-delivery repair. It does
not yet prove that the full GridLAB-D model publishes fresh feeder power or
that an EV command causes the expected physical effect every 10 seconds.
Those are now the remaining cadence-equivalence measurements.

## Physical plant cadence constraint

The full-federation configuration explains why controller-only repair is
insufficient:

- `examples/2bus-13bus/mainglm.json`: HELICS period 60 seconds.
- `examples/2bus-13bus/mainglm_2.json`: HELICS period 60 seconds.
- Feeder A GLM: `#set minimum_timestep=60`.
- Feeder B GLM: `#set minimum_timestep=120`.

GridLAB-D therefore cannot provide newly advanced physical state or accept and
resolve a physical EV effect at 10-second intervals under the frozen
configuration. A period-10 controller could make logical decisions at 10
seconds, but it would still operate over feeder plants advancing no faster
than 60 and 120 seconds. The paper describes the GridLAB-D solver at 60
seconds, yet one feeder is configured with a 120-second minimum timestep and
the causal micro-timing interpretation assumes a fresh defender
observation/action opportunity every 10 seconds.

G0 repair must choose and validate one coherent model:

1. **10-second physical control:** set the relevant GridLAB-D HELICS period
   and minimum timestep to 10 seconds, then establish numerical convergence,
   power balance, fresh input, and command-effect timing; or
2. **60-second physical plant:** retain the plant cadence, explicitly model
   controller actions between plant samples as queued/logical actions, and
   remove claims that each nominal 10-second decision observes a fresh
   physical response.

The first option is required if micro-timing remains the causal mechanism to
be compared through NATIG.

## Executed IEEE-123 physical cadence repair

The required Feeder A component comparison has now been executed using the
actual source IEEE-123 model and a v3-only temporary overlay. Both successful
arms and their independent repeats are byte-identical.

With an EV4 200→400→200 kW pulse:

- Frozen period-60 arm: command applies internally after 60 seconds and the
  feeder-power effect becomes visible to the controller after 120 seconds.
- Physical-10 arm: command applies internally after 10 seconds and becomes
  visible to the controller after 20 seconds.
- Pre-pulse feeder power agrees within 1 W on every phase.
- Phase-drift-adjusted high/restore effects agree within 0.88% and 0.006% of
  the 200 kW commanded step, passing the 2% component tolerance.

The physical-10 overlay therefore repairs command actuation cadence, but a
fresh closed-loop observation still takes 20 seconds under non-iterative
HELICS coupling. See `GRIDLABD_CADENCE_REPORT.md`.

An attempted 1.5 MW EV4 pulse produced a preserved FBS convergence failure at
t=120. The successful 400 kW pulse is a bounded diagnostic, not proof that
the isolated model tolerates campaign-scale attack commands.

## Full-coupling root cause and repair

The first full GridPACK plus two-feeder benign trace initially failed at
t=60 in both feeders. A fifth read-only 5-second federate revealed that the
retained GridPACK adapter cumulatively rotates phase B and C on every solve.
At the first feeder grant, all three published source phasors were
approximately +138 kV at zero degrees.

Causal replay confirmed the defect: a balanced boundary completed, while
changing only the t=55 boundary to the captured co-phasal values reproduced
the t=60 `meter:190` FBS failure. A v3-only adapter repair resets B/C
positive-sequence seeds before applying one phase rotation per solve. Two
repaired frozen-cadence benign full-federation runs then completed 240 seconds
with all five processes returning zero and structurally identical traces.

Clean no-command control and bounded EV4 pulse arms also completed at both
cadences:

| Arm | Internal actuation latency | Controller-visible latency | Pulse-control effect |
|---|---:|---:|---:|
| Frozen 60 s | 60 s | 120 s | 221,399.9 W |
| Physical 10 s | 10 s | 20 s | 221,517.2 W |

The effect difference is 117.3 W, or 0.0587% of the commanded 200 kW step,
inside the 2% tolerance. See `FULL_COUPLING_CADENCE_REPORT.md`.

## Configuration discrepancy

`v2/configs/experiment.yaml` declares `max_tokens: 300`, while the two
campaign attacker implementations hard-code `max_tokens=4000` and do not read
that YAML field. The effective campaign value is therefore 4000; the YAML is
stale and misleading, rather than evidence that campaign calls used 300.

## Required repair to close G0

Run a small, versioned controller-cadence equivalence campaign before the full
NATIG/OpenDER matrix:

Completed:

1. Controller and GridLAB-D period-10 overlay.
2. Internal EV4 and controller-visible power instrumentation.
3. Frozen-versus-10-second bounded pulse comparison and exact repeats.
4. Physical-effect magnitude and command-latency equivalence analysis.

Completed:

5. Full-coupling phase-boundary root cause isolated by read-only observation
   and causal replay.
6. V3-only GridPACK phase repair built and hashed.
7. Repaired full coupled no-attacker traces completed twice.
8. Full coupled clean control and bounded-pulse arms completed at frozen60
   and physical10.
9. V3 timing contract frozen at 10-second actuation / 20-second feedback.

Still required before attack comparison:

1. Keep campaign-scale commands disabled until the preserved 1.5 MW
   convergence limit is characterized and a safe bound is frozen.
2. Complete NATIG G1 and OpenDER G2 component proofs.
3. Complete one-device physical-loop and benign-network equivalence gates.
4. Freeze a new balanced Hour 4/7 screening protocol before estimating
   attacker effects.

If rerunning is infeasible, the alternative is to reclassify v2 as exploratory
evidence from a 60-second-coupled controller and remove the 10-second
micro-timing mechanism claims. That alternative does not provide the clean
comparison baseline needed for v3.

## Gate verdict

**G0 passes for entry into G1 NATIG and G2 OpenDER component proofs.** The
statistical reconstruction is reproducible, the frozen 10-second-feedback
mechanism is falsified and explicitly carried forward, the GridPACK phase
defect is causally identified and repaired in v3, and the repaired
full-coupling bounded effect is equivalent with 10-second internal actuation
and 20-second feedback.

This is not approval for attack comparison. The preserved 1.5 MW failure,
NATIG/OpenDER component validation, one-device physical loop, and benign
network equivalence remain hard downstream gates.
