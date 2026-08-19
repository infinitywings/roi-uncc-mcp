# Repaired Full-Coupling Cadence Report

Date: 2026-07-29  
Verdict: **Bounded physical-cadence equivalence passes; feedback is 20 s**

## Defect and causal confirmation

The frozen GridPACK adapter repeatedly rotated phase B by −120 degrees and
phase C by +120 degrees at every 5-second transmission solve. A read-only
fifth federate measured a three-step phase cycle. At the feeders' first
60-second grant, all three source phasors were approximately +138 kV at zero
degrees.

The causal replay was decisive:

- a balanced source-voltage replay completed the isolated IEEE-123 Feeder A
  trace; and
- changing only the 55-second boundary value to the captured co-phasal set
  reproduced the `meter:190` FBS convergence failure at 60 seconds.

The v3-only repair resets the GridPACK B/C positive-sequence seeds before
applying one phase rotation per solve. It does not alter v2. Two repaired
frozen-cadence full-federation runs completed 240 seconds with all five
participants returning zero and structurally identical physical traces.

## Full-coupling cadence comparison

The repaired GridPACK transmission model, both IEEE-123 feeders, the
controller, and a 5-second read-only observer were then compared under clean
no-command controls and identical EV4 200→400→200 kW diagnostic pulses.

| Arm | Internal high applies | Internal latency | First visible effect | Feedback latency | Pulse-control effect |
|---|---:|---:|---:|---:|---:|
| Frozen 60 s | 120 s | 60 s | 180 s | 120 s | 221,399.9 W |
| Physical 10 s | 70 s | 10 s | 80 s | 20 s | 221,517.2 W |

The first visible effect differs by 117.3 W, or 0.0587% of the commanded
200 kW step, well inside the prespecified 2% component tolerance. All
GridPACK, GridLAB-D, observer, and controller processes returned zero in all
four clean comparison arms.

## Decision boundary

The full physical-10 repair is numerically viable and preserves the bounded
effect magnitude. It validates:

- a physical EV setting applying within 10 seconds; and
- a controller-visible feeder response within 20 seconds under
  non-iterative HELICS coupling.

It does **not** validate a fresh physical feedback cycle every 10 seconds.
Downstream NATIG/OpenDER experiments may proceed only under an explicitly
frozen 10-second actuation / 20-second feedback protocol, or after a separate
iterative-coupling experiment demonstrates true 10-second feedback.

Canonical evidence:

- `gridpack_adapter_repair_r2/build_manifest.json`
- `voltage_replay_balanced_r1/voltage_boundary_replay.json`
- `voltage_replay_captured_cophasal_r1/voltage_boundary_replay.json`
- `full_coupling_frozen60_repaired_gridpack_r9/full_coupling_cadence_arm.json`
- `full_coupling_frozen60_repaired_gridpack_r10/full_coupling_cadence_arm.json`
- `full_coupling_cadence_analysis_r1/full_coupling_cadence_analysis.json`
