# G7 bounded runtime-integration report

Date: 2026-08-31  
RKA mission: `mis_01M1AVRZ4A67VB07NTDG6KRRD6`  
Runtime decision: `dec_01M1AVQEK57WSBC25RSJNCCRFJ`  
Campaign authorization: **HOLD**

## Outcome

The bounded integration stage passed its code, model-contract, gen-only, and
single-window smoke checks. This closes three concrete implementation gaps:

1. `qwen3.6-35b-a3b` produced one strict-schema, candidate-valid proposal.
2. The frozen runner now has a derived dual-budget composition that follows
   its `decide` then `note_spent` lifecycle without double accounting.
3. Every operating-point label maps to a real GridLAB-D clock position and
   therefore to a different value in the feeder's one-minute load-shape player.

It does not close detector freeze, paired-baseline, seed-completeness,
held-out-partition, or campaign-throughput gates.

## Evidence ladder

| State | Result | Evidence |
|---|---|---|
| Code-valid | PASS | 33/33 tests |
| Model-contract-valid | PASS | `artifacts/model_smoke_attempt4_strict_schema_network.json` |
| Gen-only-valid | PASS | `artifacts/runtime_integration/gen_only_responsive_night/runtime_integration.json` |
| One-window-runtime-valid | PASS | `artifacts/runtime_integration/one_window_responsive_night/runtime_integration.json` |
| Campaign-ready | HOLD | detector, pairing, held-out, and independent freeze work remains |

## Frozen composition

The derived layer imports the frozen formal attack runner and frozen shared
base runner by absolute path. It adjusts only relocated path globals and
injects clock and policy-factory hooks in memory. Recomputed source hashes
after the smoke were unchanged:

- formal attack runner:
  `79fd8f821477dd6beab9b9ccb28cd65a2a5ddfb4f2d2b462e1e84b89d82f8c69`
- shared/base runner:
  `bdd5c661846e3f5364e273918a8d3ffb08c6d8898f43435bee94edce5336fdbb`
- preserved L5b schedule-search source:
  `748f284fe7b90b25b8aea1328cbc72626a0dd0cf1f266720081bc33cdcfba4fb`
- pinned `docker-cosim` image:
  `sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7`

No file outside `v3/g7_confirmatory/` was created or modified by the target
runner. Existing working-tree changes were preserved.

## Physical operating points

The five points use the frozen 2013-08-28 feeder load-shape player:

| Condition | Clock | Load-shape value | Role |
|---|---:|---:|---|
| `responsive_night` | 04:00 | 0.212061 | low-load responsive point |
| `responsive_morning` | 07:00 | 0.289390 | medium-load ramp |
| `responsive_midday` | 12:00 | 0.789762 | high-load rising shoulder |
| `responsive_evening` | 18:00 | 0.785509 | high-load falling shoulder |
| `voltage_ceiling` | 14:00 | 0.932920 | ceiling/falsification point |

Tests require five distinct generated GLM hashes and a load-shape span greater
than 0.7. The persisted gen-only and live artifacts both set
`responsive_night` to `04:00:00` through `04:00:10`; the actuated GLM hash is
`1c9e771fdbf6a4c48e6278e38c10c2e5c5042aba88f39d9e1ac1000e8942f399`.

## Single-window budget and physics trace

The corrected smoke used `scripted_max`, seed 8101, 0.2% measurement noise,
one perturbed-window cap, 2.0 kVAh apparent-command-energy cap, Volt-VAR off,
and exactly one 10-second window. GridLAB-D returned 0.

- proposed commands were canonicalized against each device's benign command;
- one benign-equivalent PV command was removed before admission;
- three changed commands were admitted and delivered;
- inner policy spend and dual-budget spend both equal 1;
- admitted and delivered command-deviation energy both equal
  `0.7777777777777778` kVAh;
- the four device traces each contain exactly one row, with finite terminal
  voltage and `Continuous Operation` status; and
- the two BESS outputs reached 100 kW, the curtailed PV reached 0 kW, and the
  unperturbed PV remained at its benign 80 kW command.

This is command-to-OpenDER-to-GridLAB-D smoke evidence, not an estimate of
attack harm or detector performance.

## Preserved anomalies

- `model_smoke_attempt3_strict_schema.json` failed before endpoint contact due
  to sandbox DNS. The separately named network-authorized attempt passed.
- The first Docker invocation inherited the image's
  `/app/v2/docker/entrypoint.sh`, which started an unrelated legacy federation.
  It was stopped, removed, and produced no target output. It is invalid
  evidence. The gated correction explicitly overrode the entrypoint with
  `/bin/bash`; no further live retry was used.
- The valid target smoke emitted HELICS unknown-route warnings during final
  teardown and GridLAB-D's pre-existing FBS switch warning. GridLAB-D still
  exited 0 and all one-window traces reconciled. These warnings must be
  re-examined in a paired multi-window pilot; they are not silently promoted to
  campaign safety.

## Remaining gates

Before any confirmatory campaign can be authorized:

1. Freeze detector implementations and calibrate them only on the calibration
   partition, then prove development/evaluation isolation.
2. Add paired benign lineage at every operating point and verify that all
   stochastic components consume declared seeds.
3. Exercise the black/gray/white-box attacker matrix against frozen detector
   and defense configurations without information leakage.
4. Run a bounded multi-window throughput/power pilot and resolve teardown
   warnings.
5. Freeze the final derived bytes and obtain an independent hash/evidence
   review before opening evaluation seeds.
