# GridEval v3 Implementation Plan

## Critical path

```text
v2 baseline freeze
        |
        +--> NATIG public-build proof --------+
        |                                     |
        +--> OpenDER standalone proof --------+--> one-device physical loop
                                                     |
                                                     v
                                            benign DNP3 equivalence
                                                     |
                                                     v
                                          impairment/attack screening
                                                     |
                                                     v
                                           confirmatory campaign
```

The NATIG and OpenDER component proofs can proceed independently, but no attack
campaign starts before both converge in the benign equivalence build.

## WP0 — Freeze the comparison baseline

### Inputs

- `v2/results/campaign/**`
- `v2/results/CAMPAIGN_REPORT.md`
- `v2/analysis/analyze_v2.py`
- `v2/configs/experiment.yaml`
- the v2 federation, controller, attacker, GridLAB-D, and GridPACK configs

### Tasks

1. Record repository state, dirty patch, config hashes, container identity, and
   simulator versions for every retained v2 run.
2. Resolve the current mismatch between the manuscript’s Welch-test claim and
   the pooled-variance `ttest_ind` implementation.
3. Preserve 8 HELICS timeouts as explicit failures and test sensitivity to
   informative missingness.
4. Resolve the effective controller cadence: 10 s logic request versus 60 s
   HELICS period.
5. Freeze Hour 4 and Hour 7 as responsive starting blocks; label Hour 14 a
   ceiling/negative-control block.

### Exit artifact

`v3/baseline/v2_freeze_manifest.json` plus regenerated analysis and a signed
validation report. No v2 data files are modified.

## WP1 — NATIG feasibility spike

### Tasks

1. Clone the pinned NATIG commit into an isolated dependency workspace or
   vendor only an auditable patch set.
2. Inventory the exact GridLAB-D, HELICS, ns-3, OpenDNP3/DNP3, compiler,
   Python, and container dependencies.
3. Resolve whether every referenced development branch or private Stash
   component has a public equivalent in the pinned repository.
4. Build a locked container from public inputs.
5. Run NATIG’s native IEEE 123 benign example twice with the same seed.
6. Capture DNP3 command/telemetry logs, PCAP, network metrics, and output hashes.
7. Run one bounded payload-modification example solely inside the isolated
   simulated network.

### Pass

- clean public build;
- all expected federates enter and finalize;
- same-seed discrete event logs and PCAP-derived counts agree;
- DNP3 point changes cause the documented GridLAB-D setpoint change.

### Fail/fallback

If private or abandoned dependencies are essential, retain NATIG as the design
reference but implement the `cyber_message` interface using maintained public
HELICS/ns-3 components. Record the deviation; do not label the fallback NATIG.

## WP2 — OpenDER feasibility spike

### Tasks

1. Install the pinned OpenDER release in an isolated environment with a locked
   dependency file.
2. Execute the official dynamic trip/enter-service example.
3. Create deterministic tests for:
   - nominal P/Q output;
   - active-power limit;
   - constant-Q and volt-var behavior;
   - ramping and setting execution delay;
   - voltage trip and re-entry;
   - BESS charge/discharge and SOC bounds;
   - apparent-power capability priority.
4. Record the exact public API used to update voltage, frequency, available or
   demand power, timestep, and settings and to read P/Q/state.
5. Generate frozen reference traces and tolerances.

### Pass

Every enabled v3 device function has a reference test at the chosen model step.
Untested functions remain disabled in `der_devices.yaml`.

## WP3 — GridLAB-D/OpenDER physical adapter

### Proposed files

```text
v3/opender_federate/
  federate.py
  device.py
  config.py
  helics.json
  point_map.yaml
  tests/
v3/gridlabd/
  ieee123_v3.glm
  feeder_a_v3.json
```

### Tasks

1. Copy the canonical feeder model to a versioned v3 file; never edit the v2
   baseline in place.
2. Add terminal-voltage and frequency publications for EV4/l92.
3. Add a signed P/Q coupling object controlled only by OpenDER values.
4. Ensure the legacy EV4 battery/inverter is inactive.
5. Implement the OpenDER stepping wrapper and append-only event/physical logs.
6. Run positive and negative 10 kW/10 kvar pulse tests.
7. Check power balance and convergence at 1, 5, 10, and 60 s coupling steps.
8. Select the coarsest timestep meeting component and feeder tolerances.

## WP4 — Cyber gateway and NATIG adapter

### Proposed files

```text
v3/cyber_gateway/
  gateway.py
  arbitration.py
  dnp3_point_map.yaml
  helics.json
  tests/
v3/natig_adapter/
  README.md
  patches/
  configs/
  container/
```

### Tasks

1. Validate all ingress against `cyber_message.schema.json`.
2. Freeze DNP3 point indices, scales, ranges, quality flags, and
   select-before-operate behavior.
3. Map accepted remote points to OpenDER settings.
4. Map OpenDER telemetry/state back to DNP3 analog/binary points.
5. Preserve message lineage during modification and replay.
6. Reject stale, unauthorized, out-of-range, or unknown commands with an
   explicit reason.
7. Add an endpoint-graph test that fails on controller/attacker direct paths.

## WP5 — Benign equivalence

Replay an identical deterministic command trace in:

1. direct reference;
2. NATIG benign network.

Compare:

- source and accepted command sequences;
- P/Q setting and realized-output traces;
- terminal voltage;
- energy;
- command-to-effect latency;
- final state and SOC.

Any unexplained physical difference blocks attack testing.

## WP6 — Screening campaign

1. Generate a balanced manifest for the sparse Phase B contrasts.
2. Use paired controller, attacker, OpenDER, network, and load seeds.
3. Execute small batches with automatic preflight/postflight validation.
4. Analyze mechanism, variance, failures, and practical effects.
5. Select confirmatory contrasts and perform simulation-based power analysis.

## WP7 — Confirmatory and two-device campaigns

1. Freeze protocol, manifest, analysis code, and exclusions.
2. Run the powered confirmatory campaign.
3. Audit hashes, balance, missingness, and capability equality.
4. Only then enable EV1/l5 and test coordinated attacks under equal aggregate
   budgets.

## Immediate executable sequence

1. Run `python3 v3/tools/validate_design.py`.
2. Use the same checker on the v2 controller and attacker HELICS configs to
   demonstrate that the bypass detector rejects the old direct topology.
3. Complete WP0’s immutable baseline manifest.
4. Complete WP1 and WP2 as two component feasibility spikes.
5. Implement WP3 before modifying attacker behavior.

## Execution status — 2026-07-29

- WP0/G0: complete with the documented 1.5 MW command-limit carryover.
- WP2/G2: complete for the pinned OpenDER component surface and reference
  traces.
- WP1/G1: bounded NATIG component execution complete; locked construction,
  exact numerical reproducibility, clean auxiliary HELICS endpoints, and PCAP
  evidence remain open.
- WP3/G3: complete for one OpenDER BESS at l92; 10 seconds selected, while
  60 seconds fails paired physical convergence.
- WP4/G4: active. The minimal typed point map, object codec, endpoint graph,
  deterministic DNP3-to-semantic bridge, real OpenDER gateway lifecycle, and
  repeated 840-second offline adapter conformance are complete. Live benign
  direct-reference versus NATIG equivalence remains gated by the locked-build,
  endpoint, and stock callback/codec debt recorded in G1.
- WP5–WP7: not started; attack-effect experiments remain blocked by benign
  equivalence.
