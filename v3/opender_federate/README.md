# G3 OpenDER physical-loop experiment

`run_physical_loop.py` runs inside the pinned local `docker-cosim` image. It
creates a temporary v3-only Feeder A overlay, removes the complete legacy EV4
storage block, inserts one `DER_EV4_BESS_COUPLING` constant-power object at
`l92`, and exchanges voltage and signed P/Q with pinned OpenDER through HELICS.

The experiment uses 1-second OpenDER internal steps and independently varies
the GridLAB-D/HELICS coupling step over 1, 5, 10, and 60 seconds. The schedule
contains no attacker behavior: +10 kW injection, -10 kW absorption, +10 kvar
injection, -10 kvar absorption, and recovery.

Positive OpenDER P/Q means injection. Positive GridLAB-D constant power means
consumption/absorption, so the boundary applies exactly one conversion:

```text
S_gridlabd_VA = -1000 * (P_openDER_kW + j Q_openDER_kvar)
```

Every output directory is create-once. The runner captures the generated
model/configuration, raw GridLAB-D recorders and log, device/HELICS trace,
source identities, assertions, and artifact hashes.

## G3 result

The finalized canonical matrix is in `g3_canonical_r1/`. Pulse and matched-null
arms completed at 1, 5, 10, and 60 seconds with a fixed one-second OpenDER
internal step. The paired convergence gate selects 10 seconds; 60 seconds
fails voltage, source P/Q, and paired source-balance convergence. A fresh
10-second repeat is exactly equal across all compared adapter and physical
numeric leaves.

See `G3_VALIDATION_REPORT.md`, `g3_canonical_r1/CONVERGENCE.md`, and
`g3_canonical_r1/REPEATABILITY_V2.md`. These results do not include NATIG,
DNP3, a cyber impairment, or an attacker.
