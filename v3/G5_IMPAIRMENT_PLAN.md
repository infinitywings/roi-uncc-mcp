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

## First result — impairment screen (reproducible; stack-sensitivity found)

All runs `rc=0` on image `sha256:85b09515` (grideval/g4-derived-runtime:base-r24-r1),
seed 777, 840 s, single OpenDER BESS at l92, analyzed with
[`analyze_g5_impairment.py`](natig_adapter/analyze_g5_impairment.py).

| arm | 0 ms *(control)* | delay 1–1000 ms | jitter [0,100] ms | bandwidth 1–8 kb/s |
|---|---|---|---|---|
| OPERATEs applied / 18 | **18** | 10 | 10 | 10 |

- **Control valid & bimodal:** the exact nominal channel applies 18/18 (== benign);
  **any** modeled non-ideality — delay as small as 1 ms, bounded jitter, or a few
  kb/s bandwidth — drops the **same** 8 OPERATEs to 10/18. Threshold-near-zero,
  saturating, reproducible.
- **Where the loss is:** the controller originates all 18 commands and all 18 DNP3
  **SELECTs** reach the gateway in every arm, but 8 **OPERATEs** never reach the
  gateway (no gateway reject reason) — they are lost inside the compiled NATIG
  ns-3/DNP3 transport (`grideval-natig-g4`).
- **Physical consequence (nominal vs perturbed):** 24/84 coupling steps diverge;
  max |ΔP| = 10 kW (full command magnitude); integrated |ΔP| = 2400 kW·s. Dropped
  OPERATEs are predominantly the P-axis; Q-axis survives.

**Corrected interpretation (supersedes an earlier SBO-timeout reading).** A 1 ms
delay cannot exhaust the 5 s SELECT-before-OPERATE window, and bandwidth-only arms
(jitter = 0) drop the identical 8 — so the loss is **not** a physical timing
effect. It is a **sensitivity of the NATIG DNP3 master's SELECT/OPERATE scheduling
to any departure from the default channel** — an implementation characteristic of
the co-simulation stack, not a fundamental grid property. It must be root-caused at
the ns-3 source level (instrument/rebuild the DNP3 master) before impairment
magnitudes — or the delay/loss/jitter/bandwidth contrast the campaign needs — can
be trusted. It also compounds the open G1 numeric-non-repeatability debt.

**G5 status.** Impairment is measurable and reproducible (gate criterion met in the
trivial sense), but the arms are currently indistinguishable because the transport
is not robust to any perturbation; separating the availability factors is a
precondition before H2 magnitudes or any attacker (G6) inference.

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
