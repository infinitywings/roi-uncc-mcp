# G3 OpenDER Physical-Loop Validation Report

Date: 2026-07-29

## Decision

**G3 passes at a selected 10-second coupling cadence**, bounded to the tested
single-device Feeder A physical loop. The 10-second cadence is the coarsest of
1, 5, 10, and 60 seconds that satisfies every declared local-interface,
paired-source-balance, and convergence gate for this pulse schedule. This does
not imply that every OpenDER function or disturbance converges at 10 seconds.

The canonical evidence is under `g3_canonical_r1/`. It contains eight
create-once 840-second arms (pulse and matched null at each cadence), the
convergence analysis, and a fresh selected-cadence pulse/null repeat.

## Frozen identity

- Canonical Feeder A GLM SHA-256:
  `553eb2c4a3082057bba78249340adbd9f1be9d9a639206aec242e793f54ef888`
- Canonical source HELICS config SHA-256:
  `b12a953b4182db0de97ca0d2a160919fcca642d68219d7ccd9fc5bdf718454f2`
- G3 runner SHA-256:
  `4e6e6f03ab6e0ccc43377449dcab83ac6daaac8c3df2462b9b425701c4d64a34`
- OpenDER: 2.2.0, commit
  `fe7877c664bc6c5eb3832499bf05e0f1dd1825c8`
- HELICS: 3.6.1
- Expected container image ID:
  `sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7`
- Device declaration SHA-256:
  `68865984820ef99c766cb44e8d3e3f9ccd1c8d43eeb953b7b08c575b2b366451`
- Convergence analyzer SHA-256:
  `edb468531643bea15acc7c6dd863bb3afd40b559fe55e8d2b52f5fec99d68006`
- Convergence JSON SHA-256:
  `d8872a781a55ca506074e1e7dcdde052d51d63a58ccbc0f501dab101c88f0712`

The repository was mounted into the pinned container, which ran with external
networking disabled, a read-only root filesystem, all capabilities dropped,
and `no-new-privileges`.

## Corrected topology and ownership

The declared device site is bus `l92`, phase C. The canonical topology is:

```text
feeder:       n91 --linobj9192--> l92
legacy load:  l92 --swEV4-------> EV4
OpenDER DER:  l92 ----------------> DER_EV4_BESS_COUPLING
```

An independent audit found that the first exploratory implementation parented
the coupling object to `EV4`. That incorrectly placed the DER behind the
legacy charger switch and created a second disconnect path outside OpenDER.
The canonical overlay instead parents the new signed-P/Q object directly to
`l92`, preserves the existing 200 kW EV4 charger load, and removes the complete
legacy EV4 storage owner tree (`swEV4_storage`, `storage_EV4`,
`battery_inv_EV4`, and `battery_EV4`).

Every canonical arm proves that:

- there is exactly one G3 coupling object and its parent is `l92`;
- the four legacy EV4 storage objects are absent;
- `swEV4` remains `CLOSED` at every sample under static runner ownership;
- HELICS has no `swEV4` target and no message endpoints; and
- only the OpenDER value publication owns the coupling object's complex power.

## Method

OpenDER advances internally at one second in every arm. GridLAB-D/HELICS
exchange cadence varies over 1, 5, 10, and 60 seconds. Each pulse arm applies:

- +10 kW injection from 60–180 seconds;
- -10 kW absorption from 240–360 seconds;
- +10 kvar injection from 420–540 seconds;
- -10 kvar absorption from 600–720 seconds; and
- zero-output baseline and recovery intervals.

Each cadence has a matched-null arm with the same feeder inputs and zero DER
commands. Positive OpenDER P/Q means injection, while positive GridLAB-D
constant power means consumption. The boundary converts exactly once:

```text
S_gridlabd_VA = -1000 * (P_openDER_kW + j Q_openDER_kvar)
```

Paired pulse-minus-null responses are evaluated at 120, 300, 480, 660, and
780 seconds. Limits were fixed at 0.1 VA local mapping error, 0.1 kW/kvar
device response error, 0.0001 pu voltage convergence, 2 kW/kvar source
convergence, and 2 kW/kvar paired source-balance residual.

## Canonical arm results

All eight individual arms returned GridLAB-D code zero, completed without an
adapter exception, parsed all required physical recorders cleanly, and passed
their complete assertion sets.

| Coupling | Pulse/null adapter rows | Pulse assertions | Null assertions | Pulse max mapping residual | Null residual |
|---:|---:|---:|---:|---:|---:|
| 1 s | 840 / 840 | 29/29 | 22/22 | 0.004903374 VA | 0 VA |
| 5 s | 168 / 168 | 29/29 | 22/22 | 0.004715779 VA | 0 VA |
| 10 s | 84 / 84 | 29/29 | 22/22 | 0.004715779 VA | 0 VA |
| 60 s | 14 / 14 | 29/29 | 22/22 | 0.001300818 VA | 0 VA |

For every pulse arm, internal discharge and charge energy are each
0.33333333333333265 kWh. With 0.95 charge efficiency, expected final SOC is
0.4999186991869919 and observed SOC is 0.4999186991869915, an absolute
residual of `3.89e-16`. Null SOC remains 0.5 exactly.

## Coupling convergence

| Coupling | Pass | Voltage error vs 1 s | Source P/Q error vs 1 s | Paired P/Q balance residual |
|---:|:---:|---:|---:|---:|
| 1 s | yes | 0 pu | 0 W / 0 var | 1621.40 W / 1289.17 var |
| 5 s | yes | `1.13e-13` pu | `1.75e-08` W / `5.59e-07` var | 1621.40 W / 1289.17 var |
| 10 s | yes | `1.91e-11` pu | `9.20e-06` W / `7.95e-05` var | 1621.40 W / 1289.17 var |
| 60 s | **no** | 0.00398783 pu | 10481.52 W / 10976.45 var | 12102.92 W / 10949.91 var |

The 60-second arms pass their local mapping, sign, device-output, SOC, and
process gates. They fail voltage convergence, source P/Q convergence, and
paired P/Q balance because the command/effect sampling aliases a full feeder
step. It is therefore scientifically inadmissible for this schedule.

At the selected 10-second cadence, paired responses include:

- +10 kW device output at 120 seconds with -10.46 kW source-P change;
- -10 kW output at 300 seconds with +8.38 kW source-P change;
- +10 kvar output at 480 seconds with -10.03 kvar source-Q change; and
- -10 kvar output at 660 seconds with +10.07 kvar source-Q change.

The residuals include feeder losses and voltage-dependent load response; the
2 kW/kvar limits are acceptance bounds, not an assertion of lossless equality.

## Selected-cadence repeatability

The finalized canonical 10-second pulse/null pair was rerun after the
convergence tolerances were frozen. Both repeats passed with identical
identities, process outcomes, and assertion sets. Across each pair, 1,176
adapter numeric leaves and 1,008 physical numeric leaves were exactly equal;
no tolerance-only equality was needed. See `g3_canonical_r1/REPEATABILITY_V2.md`.

## Preserved failures and exclusions

- `physical_loop_coupling*_r*` used the superseded parent-`EV4` topology.
  These outputs remain exploratory and are excluded from the canonical gate.
- `physical_loop_coupling1_r1` exposed a runner deadlock: accumulated
  GridLAB-D warnings filled an unread stdout pipe. Direct log-file streaming
  fixed the runner; the truncated output remains preserved.
- `physical_loop_coupling60_r1` and `pulse_coupling10_r1` preserve evaluator
  failures caused by short/transition-contaminated analysis windows. They were
  not relabeled as physical failures or deleted.

## Scope and next gate

G3 establishes one OpenDER BESS physical adapter at one IEEE-123 site for the
tested deterministic schedule. It does **not** include NATIG, ns-3, DNP3, a
cyber gateway, GridPACK, a full two-feeder/controller federation, an attacker,
or a validated dynamic frequency source. It makes no attack-effect or
vendor-device-realism claim.

The next experiment is G4: freeze a typed DNP3 point map and gateway, route an
identical deterministic command trace through direct-reference and benign
NATIG paths, and require command lineage plus physical equivalence before any
impairment or attack screening.
