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

## Status: network-impairment arm DEFERRED (NATIG stack limitation)

The tooling above is sound and the impairment overlay/preflight work, but the
**measurement is blocked by a defect in the NATIG DNP3 co-simulation stack**, and
the arm is deferred to future work behind a hardened transport.

### What we established (reproducible)
On the immutable r24 runtime, seed 777, single OpenDER BESS at l92:

| channel | OPERATEs applied / 18 |
|---|---|
| nominal (jitter 0, 60 Mb/s) | **18** |
| any delay 1 ms–1 s | 10 |
| bounded jitter [0,100] ms | 10 |
| bandwidth 1–8 kb/s (jitter 0) | 10 |

Delivery is **bimodal**: the DNP3/ns-3 path delivers all 18 remote-DER OPERATEs
only at the *exact* nominal channel; under **any** modeled non-ideality it
deterministically drops the same 8 (the ao0/active-power OPERATE in windows 2–9),
with a measurable physical control error (max ΔP = 10 kW over 24/84 steps). The
controller originates all 18 commands and all 18 DNP3 SELECTs reach the gateway;
the OPERATEs are lost inside the ns-3/DNP3 transport.

### Why it is deferred, not fixed
- **Not a 5 s SBO timeout** (1 ms triggers it; falsified).
- **Not the two-OPERATE-per-window race**: a split-schedule controller emitting
  P and Q in separate poll cycles made it *worse* (1/18 at 200 ms), falsifying it.
- **The true mechanism** is a subtler per-command interaction between the periodic
  DNP3 poll and the control SELECT/OPERATE in the NATIG master under any
  non-instant channel — needs source-level instrumentation to resolve.
- **The NATIG build system blocks the fix**: edited `dnplib` sources
  (`master.cpp`/`outstation.cpp`/`station.cpp`) do **not** recompile into the
  runtime `libns3.35-dnp3-optimized.so` — incremental `waf` skips them and even
  `waf clean` produced a `.so` without the instrumentation strings. Fixing this
  is dedicated ns-3 build-system engineering.

### To resume
1. Fix the NATIG build so edited `dnplib` sources actually rebuild into the
   runtime `.so` (untangle the prebuilt-lib / install path).
2. Instrument `Station::changeState` + the master poll/control paths, trace one
   dropped command, and identify the poll/control interleave.
3. Fix it, re-verify 18/18 at nominal + *graceful* delay-dependent degradation,
   then run the delay/loss/jitter/DDoS arms through `run_live_g5_impairment.py`.

Until then the expanded paper relies on the **direct-path EVG**, the **G4 benign
network equivalence** (the DNP3/ns-3 path is faithful at the nominal channel),
and **OpenDER IEEE-1547 device behavior** — not on impairment magnitudes.
