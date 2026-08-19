# v2 Baseline Freeze

`v2_freeze_manifest.json` is an identity snapshot of the current comparison
evidence. It records canonical file hashes, every campaign file hash, the
campaign tree digest, working-tree state, available tool versions, run counts,
and unresolved audit flags.

The manifest does not certify the scientific claims. In particular, it keeps
the statistics, timeout missingness, timing cadence, token-limit discrepancy,
and Hour 14 ceiling issues visible. A later corrected analysis must be written
as a new artifact and must not overwrite the frozen source results.

Regeneration intentionally refuses to overwrite:

```bash
python3 v3/tools/capture_v2_baseline.py
```

## G0 reanalysis

The create-once G0 runner reconstructs the 45-slot campaign, corrects the
statistical tests, audits informative missingness, and checks the controller
timing and token-limit configuration:

```bash
python3 v3/baseline/reanalyze_v2.py
```

The canonical outputs are:

- `G0_VALIDATION_REPORT.md` — decision-oriented audit and gate verdict.
- `reanalysis_r4/v2_reanalysis.json` — complete machine-readable evidence.
- `reanalysis_r4/completion_matrix.csv` — all 45 planned slots.
- `cadence_probe_r1/cadence_probe.json` — measured HELICS 3.6.1 grant
  behavior for the frozen, period-only, and repaired loops.
- `value_freshness_probe_r2/value_freshness_probe.json` — two-federate
  synthetic-plant evidence of stale input reuse and the repaired behavior.
- `GRIDLABD_CADENCE_REPORT.md` — actual IEEE-123 frozen-versus-10-second
  physical cadence experiment.
- `FULL_COUPLING_BLOCKER_REPORT.md` — repeated benign failure, captured
  phase-boundary defect, and causal replay.
- `FULL_COUPLING_CADENCE_REPORT.md` — repaired GridPACK plus two-feeder
  control/pulse comparison and timing contract.
- `gridlabd_cadence_analysis_r3/gridlabd_cadence_analysis.json` — canonical
  machine-readable physical comparison.

`reanalysis/`, `reanalysis_r2/`, and `reanalysis_r3/` are retained as
superseded create-once revisions; see their `SUPERSEDED.md` files. No result
was overwritten.

The current verdict is **G0 pass with carried limitations** for independent
G1 NATIG and G2 OpenDER component proofs. The frozen controller's 60-second
HELICS period does not validate the paper's claimed fresh 10-second physical
feedback; v3 instead freezes the measured 10-second internal-actuation /
20-second controller-visible-feedback contract.

The isolated HELICS cadence experiment has already established that the
frozen loop executes up to seven logical decisions at one grant, while the
proposed period-10/current-time repair executes one decision per grant. The
two-federate value experiment further measured 25 repeated adjacent inputs in
the frozen loop versus zero after repair. A full GridLAB-D power/actuation
trace remains the next gate. Both GridLAB-D federates use 60-second HELICS
periods; their minimum timesteps are 60 and 120 seconds. The physical
cadence—not only the controller—must be changed and convergence-validated.

The full GridPACK-coupled comparison is also complete for a bounded 400 kW EV4
pulse. A cumulative phase-rotation defect in the retained GridPACK adapter was
identified by observation and causal replay, repaired only in v3, and followed
by two successful benign repetitions plus clean control/pulse arms at both
cadences. Attack work remains prohibited until later benign-equivalence gates,
and the preserved 1.5 MW FBS failure keeps campaign-scale commands disabled.
