# M20 Two-Window Observation-Latency Report

## Outcome

M20 completed one bounded, matched benign/attack pair at preliminary seed
`5102`, but it did **not** qualify a post-actuation feeder response. The attack
command was admitted, delivered, and realized by OpenDER in the first runner
window. At the second runner observation, however, all four true-voltage
deltas and both source-power deltas were exactly zero. The completed GridLAB-D
coupling recorders contained only `t=0` and `t=10` rows and reported zero
received DER power in both rows.

The create-once result is
`artifacts/m20_two_window_timing_seed5102_attempt1/m20_two_window_timing.json`
(SHA-256
`7d4a90f389d8b305903aeb084cf24a8a4f1ab80a6496bd1ff2def4cf5b354a47`).
Its status is `TWO_WINDOW_OBSERVATION_LATENCY_GAP` and its classification is
`PRELIMINARY_ONLY`.

This is a useful negative timing result. It is not evidence that the admitted
attack has no physical effect. Under the present HELICS/GridLAB-D exchange and
recorder timing, two 10-second runner windows do not expose that effect in a
completed feeder record.

## Registered boundary

The M20 pair was fixed before execution:

- operating point: `responsive_night`;
- matched benign and `scripted_max` treatments;
- replicate and attacker seed: `5102`;
- measurement-noise seed: `95102`;
- GridLAB-D seed: `10`;
- exactly two 10-second runner windows per treatment;
- no benign perturbation and at most one attack perturbation window;
- attack apparent-energy cap: `2 kVAh`;
- detector held, Volt-VAR defense disabled, and no model call;
- separate ephemeral containers using `--network none`; and
- final evaluation seeds `9101` through `9112` sealed.

The runtime rejects a third M20 window before component startup. The checked-in
M18 preflight returned zero issues before the run, and both per-treatment action
requests were bound to the exact gate, runtime, configuration, pair, seed, and
budget identities.

## Matched execution evidence

Both containers exited zero and were absent from `docker ps -a` after teardown.
They used image
`sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7`,
GridLAB-D `5.3.0-20236`, HELICS `3.6.1-main-ge437060a1`, Python `3.10.12`,
and vendored OpenDER `2.2.0`.

The pre-intervention observations were byte-for-byte equivalent across the
pair. The attack treatment admitted and delivered three effective commands in
window 1, spent exactly one perturbation window, and reconciled
`0.7777777778 kVAh` of both admitted and delivered command-deviation energy.
Window 2 admitted and delivered no attack command.

| Endpoint at runner `t=20` | Benign | Attack | Attack minus benign |
|---|---:|---:|---:|
| `DER_EV1_BESS` voltage (p.u.) | 1.0133328888640245 | 1.0133328888640245 | 0 |
| `DER_EV3_PV` voltage (p.u.) | 0.9966358049031769 | 0.9966358049031769 | 0 |
| `DER_EV4_BESS` voltage (p.u.) | 1.0015190825823614 | 1.0015190825823614 | 0 |
| `DER_EV5_PV` voltage (p.u.) | 1.0230939710482552 | 1.0230939710482552 | 0 |
| Source P (W) | 956550.3790956459 | 956550.3790956459 | 0 |
| Source Q (var) | 264987.8411453542 | 264987.8411453542 | 0 |

The exact equality is consistent with the recorder evidence: every attack-side
`multi_der_*_coupling.csv` contains received complex power `(0, 0)` at both
completed timestamps. It therefore cannot be interpreted as a measured null
physical response to the nonzero command.

## Operational observations

The one-window M19 HELICS unknown-route message did not recur in either M20
run. Two warning classes remain preserved rather than dismissed:

1. the Python HELICS binding deprecates `helicsFederateFinalize` in favor of
   `helicsFederateDisconnect`; and
2. GridLAB-D emits its existing FBS switch-behavior warning.

Zero process exit codes establish clean process completion, not physical-model
validity.

## Scientific boundary

M20 establishes:

- deterministic two-window command admission, delivery, reset, and budget
  lineage;
- exact matched pre-intervention observations; and
- an observation-latency gap in the current two-window co-simulation schedule.

M20 does not establish attack harm, a null physical effect, detector or defense
effectiveness, stealth, long-horizon behavior, LLM-attacker advantage,
statistical significance, generalization, or confirmatory evidence. No LLM,
embedding model, detector, or defense was used to choose or score the action.

## Next gate

No automatic retry or duration expansion was performed. A separately
registered three-window timing test should retain the same one-window
intervention and matched benign control while observing two subsequent
exchange steps. That test must first prove where the admitted DER power becomes
visible in GridLAB-D and then bind the first valid post-actuation response
index. Only after this causal timing prerequisite passes should the same
strategy/tool surface be exposed to the LLM-attacker rung.

Detector calibration, defense comparisons, larger batches, final seeds, and
publication-grade claims remain outside this milestone.
