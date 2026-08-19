# G2 OpenDER Standalone Component Validation

Date: 2026-07-29  
Verdict: **PASS WITH WRAPPER LIMITATION**

## Scope

This gate validates OpenDER as a standalone behavioral PV/BESS model. It does
not connect OpenDER to GridLAB-D, NATIG, DNP3, or any attack logic.

The public source is pinned to commit
`fe7877c664bc6c5eb3832499bf05e0f1dd1825c8` (tree
`1579d6978e166d9a1b178f5fb5f59ff073986d4b`), package version 2.2.0.
It was installed in an isolated Python 3.10 environment from that checkout.

## Results

- The complete upstream suite passes: 565/565 tests.
- The official `main.py` dynamic trip/enter-service example exits zero under
  a headless plotting backend.
- Positive BESS power is discharge/injection; negative BESS power is
  charge/absorption.
- A 0.5 pu active-power limit clips a +100 kW demand to +50 kW and preserves
  a −50 kW charge command.
- Constant-Q produces ±44 kvar as configured.
- The volt-var/Q-priority case at 0.95 pu produces 97.55 kW and 22 kvar while
  respecting the 100 kVA limit.
- A 10-second BESS ramp setting at a 1-second step produces exactly
  10 kW/s.
- The severe-overvoltage case enters `Cease to Energize`, then reaches `Trip`
  and zero output after the configured 0.16-second OV2 delay.
- A discharge/charge trace moves SOC monotonically in the expected direction
  and remains within [0, 1].

Two independent create-once runs produced byte-identical canonical JSON:
`eb5fdcfc4e16ce7af9ab3cb8c525a5f598a3138baa12e8d4ace6e021b8f73ac2`.

## Required wrapper limitation

OpenDER 2.2.0's internal `NP_SET_EXE_TIME` path does not delay an in-place
settings change. With a configured 3-second delay, an active-power limit
becomes effective at the next 1-second model step. The held and current values
refer to the same mutable `DERCommonFileFormat` object.

The pinned dependency is not patched. `device.py` disables the internal delay
and queues immutable setting snapshots at the v3 boundary. Its reference
trace accepts a limit at t=1, schedules it for t=4, holds 100 kW at t=2 and
t=3, and applies 50 kW exactly at t=4. Both the upstream defect and wrapper
repair are asserted in every conformance run.

All downstream OpenDER settings must pass through this wrapper (or a
semantically equivalent, separately validated gateway queue). Direct
in-place setting mutation with nonzero `NP_SET_EXE_TIME` is prohibited.

## Exact public API frozen for the next gate

- PV input: `DER.update_der_input(...)`
- BESS input: `DER_BESS.update_der_input(...)`
- Model step: `DER.run()` / `DER_BESS.run()`
- P/Q output: `get_der_output(...)` or `p_out_kw`, `q_out_kvar`
- BESS state: read-only `bess_soc`
- Delayed remote settings: `ScheduledOpenDERBESS.schedule_settings(...)`

G2 permits the next one-device physical-loop gate. It does not establish DNP3
protocol behavior or authorize cyberattack experiments.

Canonical evidence:

- `conformance_r7/opender_component_conformance.json`
- `conformance_r8/opender_component_conformance.json`
- `run_component_conformance.py`
- `device.py`
- `g2_artifact_manifest.json`
