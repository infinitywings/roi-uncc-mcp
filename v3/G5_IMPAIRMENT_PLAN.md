# G5 — Network-Impairment Screening (no attacker)

**Gate exit criterion (v3/README.md):** *"Delay, loss, jitter, and outage effects
are measurable and reproducible without an attacker."* G5 follows G4 (benign
network equivalence) and precedes G6 (attacker campaign). It establishes that
controlled impairments produce measurable, reproducible changes in command
delivery and physical impact **before** any adversary is introduced (RQ5,
dec_01KYNH6GXPZVFZ42RH8K9CAR4A).

## Injection mechanism

Impairment is a **declared, bounded, environmental** network condition — never an
attacker. The lever is the ns-3 application-layer DNP3 delay in
`topology.json Channel[0].jitterMin/jitterMax` (nanoseconds), which is the only
delay knob wired in the current star topology, sits on the `dnp3_over_ns3`
no-bypass path, is seeded/reproducible (`--RngRun=1` / `StaticSeed=1` /
`RandomSeed=777`), and starts **zero** attacker processes.

Runner: [`run_live_g5_impairment.py`](natig_adapter/run_live_g5_impairment.py).
It builds a G5 overlay that is byte-identical to the frozen G4 benign contract
except the injected jitter, a `natig.json.network_impairment` declaration, a
`security_condition.network_impairments[]` entry (empty `attacker_processes`),
the `scope` string, and the two re-hashed source-locks (`topology.json`,
`natig.json`). A G5-aware preflight (a) re-runs the **original** benign validator
on pristine `live_benign/` to prove the G4 base is intact, (b) re-verifies all 19
source-locks, and (c) asserts only the permitted fields changed. It then reuses
`run_live_benign.stage_overlay` / `execute_container` unchanged, so the frozen G4
runner and its evidence are never modified. `normalize_natig_live_reference.py`
gained an **opt-in** `--allow-declared-impairment` flag (default preserves G4
strict-benign behavior byte-for-byte).

Negative control: injecting an `attacker_process` is rejected pre-flight.

```bash
# dry-run preflight (no Docker)
PYTHONPATH=. python3 v3/natig_adapter/run_live_g5_impairment.py \
  --delay-ms 100 --label delay100ms --output-dir v3/natig_adapter/g5_impairment_delay100ms_dry
# live execution on the r24 derived runtime
PYTHONPATH=. python3 v3/natig_adapter/run_live_g5_impairment.py \
  --delay-ms 200 --label delay200ms_r1 \
  --output-dir v3/natig_adapter/g5_impairment_delay200ms_r1 \
  --execute --image-manifest v3/natig_adapter/locked_runtime_result_base_r24_r1/live_image_manifest.json
```

## First result — delay arm (screening, reproducible)

All runs `rc=0` on image `sha256:85b09515` (grideval/g4-derived-runtime:base-r24-r1),
seed 777, 840 s, single OpenDER BESS at l92.

| delay (ms) | 0 (control) | 50 | 100 | 200 | 500 | 1000 |
|---|---|---|---|---|---|---|
| OPERATEs applied / 18 | **18** | 10 | 10 | 10 | 10 | 10 |

- **Control valid:** 0 ms reproduces benign exactly (18/18) → the G5 harness is
  neutral; drops are caused by the delay, not the wrapper.
- **Reproducible & threshold-shaped:** any delay ≥ 50 ms drops the same 8
  commands (flat 50–1000 ms; 200 ms r1==r2).
- **Mechanism (SELECT-before-OPERATE timeout):** every arm accepts all 18 DNP3
  SELECTs, but ≥ 50 ms transport delay makes 8 OPERATEs arrive after their 5 s
  SELECT window (`select_expires_at_s = receive + 5 s`) → rejected → not actuated.
- **Physical consequence (0 ms vs 200 ms):** 24/84 coupling steps diverge;
  max |ΔP| = 10 kW (full command magnitude); integrated |ΔP| = 2400 kW·s. The
  BESS holds stale setpoints because fresh commands never apply. Dropped OPERATEs
  are predominantly the P-axis (AO0); Q-axis (AO1) survives (deterministic
  intra-window ordering).

This establishes **H2 (network mediation measurably degrades command delivery and
physical control)** at the screening tier.

## Caveats

- Magnitude is conditioned on the current 5 s SBO timeout + 10 s poll/coupling
  cadence — a realistic but specific configuration.
- Only the **delay** lever has been run. Remaining impairment factors:
  bounded jitter (`min < max`), bandwidth (`Channel.P2PRate`), packet loss
  (requires a `Node[]`/`UseCSMA` `RateErrorModel` topology restructure), link
  outage, and bounded-DDoS congestion (declared environmental, not an attacker).
- This is **pilot/screening** evidence, not the preregistered confirmatory
  campaign. Phase C requires ≥ 5 paired reps per contrast and a frozen analysis
  plan (primary outcome VVI, monitored nodes, seeds, exclusions) before any
  confirmatory or attacker-effect (G6) claim.

## Next steps

1. Bounded-jitter and bandwidth arms (config-only, same runner).
2. A `Node[]` topology variant to enable packet-loss and link-outage arms.
3. A G5 metric extractor (cyber latency + command-lifecycle counts + physical
   control-error/VVI) replacing the ad-hoc trace diff, per protocol §8.
4. Characterize which 8 commands drop per window and whether an adaptive
   attacker could time OPERATEs to survive the SBO window (feeds the G6 EVG-under-
   -mediation question).
