# M21 Three-Window Causal-Timing Report

## Outcome

M21 qualified the minimum observation schedule needed by the current
GridEval runtime. A command delivered in runner window 1 is not visible in the
runner's window-2 feeder observation. It first appears in the third completed
GridLAB-D coupling-recorder row at feeder timestamp
`2013-08-28 04:00:20 PST`, and the first nonzero paired feeder response appears
in runner window 3 at `t=30`.

The create-once evidence is
`artifacts/m21_three_window_timing_seed5103_attempt1/m21_three_window_timing.json`
(SHA-256
`2aa7bbc10bcd20f964f9a7cbcad9a70b6058b8e652acbc68bdbea953bc7e022d`).
Its status is `THREE_WINDOW_CAUSAL_TIMING_QUALIFIED` and its classification is
`PRELIMINARY_ONLY`.

This result qualifies the causal observation index for subsequent bounded
runtime experiments. It does not estimate an attack-effect distribution or
authorize a larger trial.

## Registered boundary

M21 was created only after M20 was closed without modification and its timing
checkpoint was resolved. The new pair was fixed as follows:

- operating point: `responsive_night`;
- matched benign and `scripted_max` treatments;
- replicate and attacker seed: `5103`;
- measurement-noise seed: `95103`;
- GridLAB-D seed: `10`;
- exactly three 10-second windows per treatment;
- attack intervention in window 1 only;
- attack apparent-energy cap: `2 kVAh`;
- detector held, Volt-VAR defense disabled, and no model inference;
- separate ephemeral containers using `--network none`; and
- final evaluation seeds `9101` through `9112` sealed.

The runtime rejects a fourth M21 window before component startup and still
rejects a third M20 window. Both action requests passed the M18 validator and
were bound to runtime SHA-256
`8e5da9768c0788fa7f297d472ebda10a8c20f7db3351fdc4e9ee3c1bd1eed696`.

## Command and budget lineage

The attack requested four commands in window 1. The benign-equivalent
`DER_EV5_PV = (80, 0)` request was removed before admission. The other three
commands were admitted and delivered without drift:

| Device | Requested P/Q (kW/kvar) | Admitted and delivered P/Q |
|---|---:|---:|
| `DER_EV1_BESS` | `(100, 0)` | `(100, 0)` |
| `DER_EV3_PV` | `(0, 0)` | `(0, 0)` |
| `DER_EV4_BESS` | `(100, 0)` | `(100, 0)` |
| `DER_EV5_PV` | `(80, 0)` | benign-equivalent, removed |

The attack spent exactly one perturbation window and reconciled
`0.7777777778 kVAh` of both admitted and delivered command-deviation energy.
Windows 2 and 3 contained no requested, admitted, or delivered attack command.
The benign treatment spent zero budget.

## Causal timing result

The pre-intervention true voltage, measured voltage, source power, operating
point, dependency hashes, and component seeds were exactly equal across the
pair.

GridLAB-D received-power differences were zero in recorder rows 1 and 2. In
row 3, at feeder timestamp `04:00:20`, the paired active-power differences
became:

| Coupling recorder | Attack minus benign P (W) | Q (var) |
|---|---:|---:|
| `DER_EV1_BESS` | -100,000 | 0 |
| `DER_EV3_PV` | +80,000 | 0 |
| `DER_EV4_BESS` | -100,000 | 0 |
| `DER_EV5_PV` | 0 | 0 |

The runner observation at `t=20` remained exactly equal across treatments.
The observation at `t=30` produced the first nonzero paired feeder response:

| Endpoint | Attack minus benign |
|---|---:|
| `DER_EV1_BESS` voltage | +0.0036503379 p.u. |
| `DER_EV3_PV` voltage | -0.0160541112 p.u. |
| `DER_EV4_BESS` voltage | +0.0082066252 p.u. |
| `DER_EV5_PV` voltage | +0.0081576454 p.u. |
| Source P | -204,398.0613 W |
| Source Q | -13,200.7360 var |

Therefore, later experiments using this composition must treat the third
runner observation as the first valid post-actuation outcome for a command
issued in the first runner window. Scoring the second observation would
silently classify an unobserved command as a zero-effect action.

## Runtime identity and anomalies

Both containers exited zero and were absent from `docker ps -a` after
completion. They used image
`sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7`,
GridLAB-D `5.3.0-20236`, HELICS `3.6.1-main-ge437060a1`, Python `3.10.12`,
and vendored OpenDER `2.2.0`.

Three warning classes remain retained:

1. the benign run emitted a HELICS unknown-route/no-broker message at final
   time 30, while the attack run did not;
2. both runs emitted the `helicsFederateFinalize` deprecation warning; and
3. both GridLAB-D runs emitted the existing FBS switch-behavior warning.

The treatment-asymmetric teardown message did not alter the completed traces
or exit codes, but it remains an operational anomaly and is not evidence of
physical validity.

## Scientific boundary and next gate

M21 establishes the first recorder-visible command index, the first finite
nonzero paired feeder-response index, and three-window command/budget lineage
for one deterministic pair. It does not establish attack-harm distribution,
detector or defense effectiveness, stealth or long-horizon behavior,
LLM-attacker advantage, statistical significance, generalization, or
confirmatory evidence.

The next bounded gate may connect the existing LLM to the already defined
same-surface attacker interface, but it must preserve the three-window timing
schedule established here. The first live comparison should remain a tiny
matched smoke test between a deterministic strategy rung and the LLM tool-use
rung, with the same candidate surface, observation payload, budget, seed
lineage, and post-actuation scoring index. Detector and defense experiments
remain separate later gates.
