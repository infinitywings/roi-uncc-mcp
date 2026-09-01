# Grid-aware red-team design

Status: high-level design and Phase 0–1 requirements. Individual attack and
defense implementations require separate runtime gates.

## Why a grid red team is not a generic control-system benchmark

The result is governed by interacting electrical and cyber states:

- The feeder is radial, unbalanced, and phase-specific. The same command can be
  high-leverage at one node/phase and nearly invisible at another.
- Voltage sensitivity is operating-point dependent and P/Q coupled. A policy
  that wins at midday PV export can fail at the evening load peak.
- BESS and PV do not have symmetric authority. BESS can charge/discharge but is
  constrained by SOC; PV is irradiance-limited and generally curtail-only in P.
- Inverter limits, priority rules, ramping, saturation, ride-through, and mode
  transitions make the command-to-physics map nonlinear and stateful.
- The current OpenDER configuration has an approximately 15-second mode
  transition against a 10-second control window. Therefore commands have memory
  across windows; an i.i.d. point-attack abstraction is invalid.
- Local Volt-VAR changes the attack surface. In the current runner it overrides
  remote Q commands, so a red-team policy must contest it through P or attack
  the function/configuration itself.
- A legitimate but malicious command can be physically self-consistent. A WLS
  residual that trusts attested P/Q may explain the voltage response and remain
  blind to authority abuse.
- Benign variability, detector state, and protection state are path-dependent.
  False-alarm probability and time-to-alarm must be evaluated per trajectory,
  not as shuffled rows.

These properties make paired benign counterfactuals, strict timing, device
state, and cross-layer provenance mandatory.

## Do not use a single ambiguous "box" label

Each run should record a knowledge vector:

`K = (grid, detector, training_data, defense, feedback)`

Each component is one of `none`, `partial`, or `exact`. Human-readable labels
are derived from the vector:

| Label | Grid knowledge | Detector/defense knowledge | Feedback | Intended realism |
|---|---|---|---|---|
| Black-box | Public device interface and bounds only | None | Noisy local telemetry; no score | Compromised client/aggregator with query access |
| Gray-box | Device type, approximate topology or learned sensitivity | Detector family or binary alarm, not parameters | Telemetry plus bounded probe/alarm history | Skilled operator with partial documentation/reconnaissance |
| White-box | Exact topology, dynamics, limits, seeds, and sensitivity | Exact code, thresholds, state, and defense | Full internal state | Worst-case assurance and adaptive-evasion audit |

Two useful boundary conditions are also required: `zero_feedback` (open-loop)
and `delayed_feedback` (one or more windows late). These separate genuine model
knowledge from online query advantage.

## Attack surface and strategy library

### A. DER command-authority abuse (current G7 core)

- step/corner: simultaneous worst-envelope command;
- pulse/intermittent: alternating or sparse commands that excite transitions;
- ramp/drift: low-and-slow command movement;
- periodic/duty-cycle: amplitude-period schedules;
- event-synchronized: act during load/PV ramps, tap changes, or disturbances;
- riding-the-wave: shape the command in the direction of an existing benign
  excursion;
- P/Q coordinated: exploit cross-coupling, phase imbalance, or inverter
  priority/saturation;
- spatially sparse/coordinated: choose one vulnerable DER, a same-phase subset,
  or a cross-phase coalition;
- state-exhaustion: manipulate BESS SOC or PV curtailment headroom before the
  damaging phase; and
- adaptive detector-evasion: optimize harm subject to alarm-risk and both
  operational budgets.

### B. Telemetry and timing integrity

- additive bias, scaling, ramp, replay, freeze, packet loss, and delay;
- coherent multi-sensor false data that is AC/linearized-residual consistent;
- command/telemetry split view (operator sees a plausible response while the
  physical DER receives a different command);
- time-shift and reordering that exploits detector/inverter state; and
- compound command manipulation plus measurement concealment.

### C. Configuration and autonomous-function abuse

- malicious Volt-VAR/Volt-Watt curve or priority setting;
- disabling local autonomous modes or changing setpoint execution delay;
- unsafe but syntactically valid parameter combinations; and
- synchronized configuration changes across multiple inverters.

### D. Availability and cross-layer conditions

- denial/degradation of command or telemetry channels;
- stale-command hold, fail-open/fail-safe behavior, and recovery;
- topology/model mismatch; and
- benign physical faults occurring concurrently with a cyberattack.

The initial confirmatory experiment remains on category A. Categories B–D are
separate campaigns because they change the trust boundary and causal question.

## Grid effects to measure

The primary G7 metric remains paired pre-alarm voltage harm per attack kVAh,
but red-team guidance needs a vector of outcomes:

- maximum and integral voltage-envelope violation by node and phase;
- oscillation energy, rate of change, and persistence after the last command;
- source P/Q imbalance and feeder loss change;
- DER saturation, curtailment, SOC depletion, ride-through/trip, and recovery;
- spatial propagation and the ratio of remote-node to attacked-node harm;
- detector event recall, false alarms per benign trajectory, latency,
  localization accuracy, and score calibration;
- mitigation cost: curtailed energy, control effort, voltage-quality penalty,
  and recovery time; and
- worst-cell risk across operating point, topology, noise, latency, and model
  mismatch—not only the global average.

All attack metrics must be paired with the same operating point and stochastic
seed. Detection performance must report event-level and trajectory-level
statistics; row-level accuracy alone is misleading under class imbalance and
time dependence.

## Recommended staged design

1. **Physical map.** Verify P/Q sign, envelopes, saturation, transition memory,
   SOC, and local-control arbitration; build operating-point/phase sensitivity
   maps with bounded probes.
2. **Canonical library.** Run fixed step, pulse, ramp, periodic, riding-wave,
   spatial-subset, and configuration attacks under equal dual budgets. This
   creates a stable detector benchmark rather than training on one policy.
3. **Knowledge ladder.** Evaluate zero-feedback black-box, query black-box,
   gray-box system-ID, and white-box optimization. Match query and rollout
   budgets; never compare 5 LLM episodes with 12 classical episodes.
4. **Detector bake-off.** Freeze calibration data, thresholds, feature access,
   and compute budgets. Test clean, distribution-shift, adaptive-evasion, and
   fault-plus-attack partitions.
5. **Defense-in-depth.** Add command screening/local fallback, hybrid detection,
   then active challenge defenses. Measure security gain against operational
   cost and new failure modes.
6. **Adaptive red-team final.** Reveal one defense tier at a time to gray/white
   attackers, preserve an unseen attack-family holdout, and report the Pareto
   frontier of physical harm, stealth, query cost, and defender cost.

Use sequential screening rather than a full Cartesian product. Promote only
attack-detector pairs that expose a distinct mechanism or dominate a harm/
stealth frontier into the expensive replicated campaign.

## Minimum provenance per run

- exact attacker knowledge vector and feedback delay;
- target devices/nodes/phases and compromised channel;
- proposal/query transcript and all rejected actions;
- commands before/after clamping, delivered P/Q, voltage, SOC, mode, and limits;
- detector features/scores/state/alarm and defense actions;
- window and apparent-energy budgets before/after every decision;
- simulator, code, config, prompt, detector, model, and plan hashes; and
- paired benign run ID and seed lineage.

