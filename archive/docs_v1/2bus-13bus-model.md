# 2bus-13bus Co-Simulation Model Reference

This document consolidates the full technical context for the 2bus-13bus transmission–distribution–EV co-simulation. Sources: [examples/2bus-13bus/README.md](examples/2bus-13bus/README.md), [examples/2bus-13bus/GRID_DIAGRAM.md](examples/2bus-13bus/GRID_DIAGRAM.md), [examples/2bus-13bus/QUICK_REFERENCE.txt](examples/2bus-13bus/QUICK_REFERENCE.txt), [examples/2bus-13bus/SYSTEM_DIAGRAM.txt](examples/2bus-13bus/SYSTEM_DIAGRAM.txt), [examples/2bus-13bus/1bc_EV_Controller.py](examples/2bus-13bus/1bc_EV_Controller.py), and [examples/2bus-13bus/1bc_EV_Controller_2.py](examples/2bus-13bus/1bc_EV_Controller_2.py).

## System Overview
- Transmission: IEEE 9-bus system modeled in GridPACK; connects to two distribution feeders at Bus2 and Bus3.
- Distribution A (Feeder A): IEEE 123-node feeder with six EV charging stations and two optional battery storage switches (EV1, EV4). Model file: [examples/2bus-13bus/1c_IEEE_123_feeder.glm](examples/2bus-13bus/1c_IEEE_123_feeder.glm).
- Distribution B (Feeder B): IEEE 123-node feeder used for load diversity without EV control. Model file: [examples/2bus-13bus/1c_IEEE_123_feeder_2.glm](examples/2bus-13bus/1c_IEEE_123_feeder_2.glm).
- HELICS federation: GridPACK (transmission), GridLAB-D feeder A, GridLAB-D feeder B, EV controller federate, optional attacker federate. Broker default port 23406. Primary config: [examples/2bus-13bus/gpk-gld-cosim.json](examples/2bus-13bus/gpk-gld-cosim.json) and [examples/2bus-13bus/mainglm.json](examples/2bus-13bus/mainglm.json).
- Platforms tested: Linux (Ubuntu) with HELICS 3.x, GridLAB-D 5.x, GridPACK built from source; Python 3.10+ with `helics` wheel and `matplotlib`, `pandas`, `numpy`.
- Minimal run-time services: broker is spawned implicitly by `helics run --path=gpk-gld-cosim.json`; no external broker needed unless orchestrating from another host.

## Repository Checkout (Required for Reproduction)
This project is intentionally split across:
- Main repo: `roi-uncc-mcp` (attack tooling, docs, MCP server, orchestration).
- Model repo: `Grid-Simulation-Models` (checked out into `examples/`).

Recommended checkout commands (fresh machine):

```bash
git clone https://github.com/eshoubak/roi-uncc.git roi-uncc-mcp
cd roi-uncc-mcp

# The model content is expected at ./examples
git clone https://github.com/infinitywings/Grid-Simulation-Models.git examples
```

Expected working directory for this document: `roi-uncc-mcp/`.

## Execution Clock and Powerflow Baseline (Feeder A GLM)
- Simulation window: 24 h, start `2013-08-28 00:00:00`, stop `2013-08-29 00:00:00`, timezone PST8; minimum timestep 60 s.
- Modules: powerflow (FBS solver, voltage error 1e-4, line limits on), climate, residential (implicit_enduses NONE), tape, generators, market.
- Swing bus definition: `meter Node650` with phases ABC, nominal 138 kV, recorder at 60 s interval for measured voltage/power to `gld_cosim_right.csv`.
- Transmission–distribution interface: `transformer substation_transformer` (WYE_WYE 138 kV → 2.401 kV, 77.4 MVA, Z=0.00033+0.0022j) from Node650 to n150.
- HELICS connection: `object helics_msg gld_hlc_conn` attached to Node650, configured by [examples/2bus-13bus/mainglm.json](examples/2bus-13bus/mainglm.json).
- Load shapes: players and schedules included from `include/schedules/*` and `include/players/load_shape_player.player` (looping 14,600 samples for 24 h profile).

### Load Shape Player (excerpt)
Source: [examples/2bus-13bus/include/players/load_shape_player.player](examples/2bus-13bus/include/players/load_shape_player.player). Values are per-minute multipliers applied to base loads; file loops for long runs.

```
2013-08-28 00:00:00, 0.241766
+1m, 0.243147
+1m, 0.244528
+1m, 0.245908
+1m, 0.247289
+1m, 0.248670
+1m, 0.245771
+1m, 0.242811
+1m, 0.239852
+1m, 0.236892
+1m, 0.233933
+1m, 0.235427
+1m, 0.237050
+1m, 0.238672
+1m, 0.240294
+1m, 0.241916
+1m, 0.241126
+1m, 0.240231
+1m, 0.239335
+1m, 0.238440
+1m, 0.237544
+1m, 0.236195
+1m, 0.234818
+1m, 0.233442
+1m, 0.232065
+1m, 0.230689
+1m, 0.231470
+1m, 0.232412
+1m, 0.233354
+1m, 0.234297
...
```

## Transmission Model (GridPACK)
- Network: 9-bus, three generators (Bus1, Bus2, Bus3) and tie lines to feeders at Bus2 and Bus3.
- Publications: `gridpack/Va`, `gridpack/Vb`, `gridpack/Vc` (complex voltages at tie buses).
- Subscriptions: `gld_hlc_conn/Sa`, `Sb`, `Sc` (aggregate complex power from feeders).
- Build artifacts: sources under [examples/2bus-13bus/gpk-left-fed.cpp](examples/2bus-13bus/gpk-left-fed.cpp), [examples/2bus-13bus/pf_app.cpp](examples/2bus-13bus/pf_app.cpp), CMake in [examples/2bus-13bus/CMakeLists.txt](examples/2bus-13bus/CMakeLists.txt).

## Distribution Model A (GridLAB-D, feeder with EVs)
- Swing bus: Node650 tied to transmission Bus2.
- EV attachment points (links to lateral nodes):
  - EV1: link l5, phase CN, switch `swEV1`, storage switch `swEV1_storage` (battery islanding capable).
  - EV2: link l2, phase BN, switch `swEV2`.
  - EV3: link l88, phase AN, switch `swEV3`.
  - EV4: link l92, phase CN, switch `swEV4`, storage switch `swEV4_storage` (battery islanding capable).
  - EV5: link l107, phase BN, switch `swEV5`.
  - EV6: link l114, phase AN, switch `swEV6`.
- Nominal EV ratings: EV1/EV4 220 kW; EV2/EV3/EV5/EV6 200 kW. Attack/abuse limits noted up to 4 MW per EV.
- Recorder outputs: `output/1c_IEEE_123_feeder_0_EV*.csv` for per-EV power.
- Islanding logic (model intent): when feeder load exceeds the upper limit, open `swEV1`/`swEV4`, close `swEV1_storage`/`swEV4_storage`, keep EV1/EV4 powered from local storage, disconnect others.

## Distribution Model B (GridLAB-D, feeder without EV control)
- Swing bus: Node650 tied to transmission Bus3.
- No EV-specific endpoints or controller actions; used for additional load diversity and stress propagation scenarios.

## HELICS Topology and Endpoints
- Federates: `gridpack` (transmission), `IEEE13bus_fed` (feeder A), `IEEE13bus_fed_2` (feeder B), `EVControllerSim` (legitimate controller), optional `ev_attacker_mcp` (attacker MCP).
- GridLAB-D feeder A publishes `gld_hlc_conn/Sa,Sb,Sc` (feeder power) and subscribes to transmission voltages `gridpack/Va,Vb,Vc`. EV load objects subscribe to `gld_hlc_conn/EV1-6` setpoint endpoints.
- Controller publishes setpoints to `EV_Controller/EV1-6` (mapped to `gld_hlc_conn/EV1-6`) and switch states `swEV1`, `swEV4`, `swEV1_storage`, `swEV4_storage`; subscribes to `gld_hlc_conn/Sa,Sb,Sc`.
- Attacker (if active) publishes `attacker/EV1-6` to the same EV endpoints and subscribes to feeder load and transmission voltages; last message on each endpoint wins.
- Feeder A endpoint wiring (from [examples/2bus-13bus/mainglm.json](examples/2bus-13bus/mainglm.json)): each `gld_hlc_conn/EVx` is global and maps to EVx constant_power_* property; Node650 power publications are complex VA per phase.
- Controller filter: `EVfilters` adds a 3600 s source delay on all `EV_Controller/EV1-6` endpoints (in [examples/2bus-13bus/1c_Control.json](examples/2bus-13bus/1c_Control.json)); attacker messages are not delayed by this filter and can preempt controller updates.
- Secondary feeder (B) uses parallel keys `gld_hlc_conn_2/*` with controller variant config [examples/2bus-13bus/1c_Control_2.json](examples/2bus-13bus/1c_Control_2.json) and endpoints `EV_Controller_2/EV1-6` (also filtered with 3600 s delay).

## Federate Launch Orchestration (gpk-gld-cosim.json)
- Broker enabled; federates launched locally:
  - `gridlabd 1c_IEEE_123_feeder.glm` → `IEEE123bus_fed` (Feeder A).
  - `gridlabd 1c_IEEE_123_feeder_2.glm` → `IEEE123bus_fed_2` (Feeder B).
  - `python 1bc_EV_Controller.py -c 1c` → `1c_Controller` (legit EV control).
  - `./build/gpk-left-fed.x` → `gridpack` (transmission).
  - Attacker MCP runs separately via `archive/ev_setpoint_mcp` docker compose when used.
- Launch command (native):
  - `cd examples/2bus-13bus && helics run --path=gpk-gld-cosim.json`
- Docker orchestration note:
  - A previously used multi-container “demo stack” compose file is archived under [archive/legacy_demo/docker/docker-compose.demo.yml](archive/legacy_demo/docker/docker-compose.demo.yml).
  - The simplest Docker path is the single-container `grid-attack-demo` service in [archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml](archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml), which launches the broker + 2× GridLAB-D + controller + GridPACK + MCP server in one container (archived).
- Build prerequisites:
  - GridPACK: `mkdir build && cd build && cmake .. && make` in [examples/2bus-13bus](examples/2bus-13bus); produces `build/gpk-left-fed.x`.
  - Python deps: `pip install helics matplotlib pandas numpy` (use same interpreter as controller run).
  - HELICS CLI: install `helics` binaries (apt, conda, or source) ensuring `helics_broker` and `helics run` are on PATH.

## EV Controller Logic (1bc_EV_Controller.py)
- Federate config: [examples/2bus-13bus/1c_Control.json](examples/2bus-13bus/1c_Control.json).
- Time step: `CONTROLLER_INTERVAL_SEC` env var (default 60 s). Simulation length: 24 hours.
- Feeder limits (as coded): upper 4.8 MW, lower 2.6 MW.
- Message handling: pulls latest message on each EV endpoint per step; stores time series; writes CSV `1c_EV_Outputs.csv` and plot `output/1c_Feeder_and_EVs_subplot.png`.
- Actions:
  - Overload (`P >= 4.8 MW`): send `0+0j` to all EV endpoints (all EVs OFF).
  - Safe band (`2.6 < P < 4.8 MW`): sends 210 kW then 200 kW commands to all endpoints (intended EV1/EV2 priority; code currently writes repeated EV1/EV2 patterns to all six endpoints).
  - Low load (`P <= 2.6 MW`): turns all EVs ON with per-endpoint defaults `[210, 200, 200, 200, 200, 206] kW` (converted to watts as complex strings).
- Finalization: requests `HELICS_TIME_MAXTIME`, disconnects, destroys federate.

### Controller Config (1c_Control.json)
Key pieces of the HELICS federate definition for the legitimate controller. Full file: [examples/2bus-13bus/1c_Control.json](examples/2bus-13bus/1c_Control.json).

```
{
  "coreInit": "--federates=1",
  "coreName": "EVController Federate",
  "coreType": "zmq",
  "name": "EVControllerSim",
  "period": 30,
  "logfile": "output.log",
  "publications": [ "swEV1_storage", "swEV1", "swEV4_storage", "swEV4" ],
  "endpoints": [ "EV_Controller/EV1" ... "EV_Controller/EV6" → gld_hlc_conn/EVx ],
  "filters": [{ "name": "EVfilters", "operation": "delay", "properties": {"value": 3600} }],
  "subscriptions": [ "gld_hlc_conn/Sa", "Sb", "Sc" (complex) ]
}
```

### Controller Logic (core loop excerpt)
Source: [examples/2bus-13bus/1bc_EV_Controller.py](examples/2bus-13bus/1bc_EV_Controller.py). Shows endpoint reads, load aggregation, and three-way action.

```
for t in range(0, total_interval, update_interval):
  while grantedtime < t:
    grantedtime = h.helicsFederateRequestTime(fed, t)

  rload_total = 0.0
  iload_total = 0.0
  for i in range(subkeys_count):
    demand = h.helicsInputGetComplex(subid[f"m{i}"])
    rload_total += demand.real
    iload_total += demand.imag

  # keep only last message per endpoint
  current_ev_values = {name: np.nan for name in ev_names}
  for i in range(endpoint_count):
    ep = endid[f"m{i}"]
    while h.helicsEndpointHasMessage(ep):
      msg = h.helicsEndpointGetMessage(ep)
    if msg:
      try:
        latest = complex(h.helicsMessageGetString(msg)).real / 1000.0
        current_ev_values[ev_names[i]] = latest
      except Exception:
        pass

  P = rload_total
  if P >= feeder_limit_upper:
    for i in range(endpoint_count):
      h.helicsEndpointSendBytes(endid[f"m{i}"], '0.0+0.0j')
  elif feeder_limit_lower < P < feeder_limit_upper:
    h.helicsEndpointSendBytes(endid["m0"], '210000+0.0j')
    h.helicsEndpointSendBytes(endid["m1"], '200000+0.0j')
    h.helicsEndpointSendBytes(endid["m2"], '210000+0.0j')
    h.helicsEndpointSendBytes(endid["m3"], '200000+0.0j')
    h.helicsEndpointSendBytes(endid["m4"], '210000+0.0j')
    h.helicsEndpointSendBytes(endid["m5"], '200000+0.0j')
  else:
    powers = ['210000+0.0j','200000+0.0j','200000+0.0j','200000+0.0j','200000+0.0j','206000+0.0j']
    for i in range(endpoint_count):
      h.helicsEndpointSendBytes(endid[f"m{i}"], powers[i] if i < len(powers) else '200000+0.0j')
```

    ### Controller Parameters (practical defaults)
    - `CONTROLLER_INTERVAL_SEC`: 60 (env override). Use 1200 to mirror 20-minute narrative cycle.
    - `feeder_limit_upper`: 4.8e6 W (align to 4.2e6 W if matching documentation/protection study).
    - `feeder_limit_lower`: 2.6e6 W.
    - Endpoint delay filter: 3600 s (consider removing for responsive control).
    - Output artifacts: `1c_EV_Outputs.csv` and `output/1c_Feeder_and_EVs_subplot.png`.

### Controller Communications Detail
- Endpoints (global): `EV_Controller/EV1-6` → destinations `gld_hlc_conn/EV1-6` (string payloads parsed as complex power W+jVAR).
- Switch publications: `swEV1`, `swEV4`, `swEV1_storage`, `swEV4_storage` as string status; GridLAB-D subscribes to these keys and sets switch statuses directly.
- Subscriptions: complex feeder power `gld_hlc_conn/Sa,Sb,Sc` read each step; defaults set to 0+0j to avoid nulls.
- Delay filter: 3600 s on controller endpoints means intentional latency; if disabled, update responsiveness increases and attacker race dynamics change.

## Alternate Controller Variant (1bc_EV_Controller_2.py)
- Federate config: [examples/2bus-13bus/1c_Control_2.json](examples/2bus-13bus/1c_Control_2.json).
- Time step: 60 s; loop currently set to a single interval (`total_interval = 1`), suitable for quick tests.
- Feeder limits: upper 4.2 MW, lower 2.6 MW.
- Actions:
  - Overload: all EVs OFF.
  - Safe band: first two endpoints receive 210 kW; others unchanged.
  - Low load: all endpoints set to 200 kW.
- Writes `1c_EV_Outputs_2.csv`; optional live matplotlib subplots per EV and feeder load.

### Variant Communications Detail
- Endpoints (global): `EV_Controller_2/EV1-6` → `gld_hlc_conn_2/EV1-6` with same string complex power format.
- Subscriptions: `gld_hlc_conn_2/Sa,Sb,Sc` complex feeder power.
- Filter: same 3600 s delay applied to all variant endpoints.
- Runtime knobs: `period` 60 s, `update_interval` 60 s, limits 4.2/2.6 MW baked in code. Outputs CSV `1c_EV_Outputs_2.csv`.

## Run Instructions

### Option A (Recommended): One-Container Docker Reproduction
This is the most reproducible path because it avoids local installs of HELICS/GridLAB-D/GridPACK.

1) Build the simulation base image (required exactly once per machine)

The active attacker container extends `roi-img:latest`. Build it from:
[archive/legacy_demo/containers/docker/Dockerfile](archive/legacy_demo/containers/docker/Dockerfile)

```bash
cd archive/legacy_demo/containers/docker
docker build -t roi-img:latest .
```

Notes:
- This build pulls and compiles upstream source dependencies (HELICS, GridLAB-D, GridPACK) and can take a long time.
- Versions are partially pinned in the Dockerfile (e.g., PETSc v3.16.4, GA 5.8, Boost 1.78.0); HELICS/GridLAB-D are cloned from their repos and may drift over time.

2) Run the full co-sim + attacker MCP in one container

```bash
cd /path/to/roi-uncc-mcp
docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build
```

What this does (via [archive/ev_setpoint_mcp/docker/run_grid_attack_demo.sh](archive/ev_setpoint_mcp/docker/run_grid_attack_demo.sh)):
- Ensures `examples/2bus-13bus/build/gpk-left-fed.x` exists; runs `cmake .. && make` if missing or stale.
- Starts a local HELICS broker on `tcp://localhost:23404` (inside the container).
- Launches:
  - `gridlabd 1c_IEEE_123_feeder.glm` → logs `examples/2bus-13bus/logs/gld1.log`
  - `gridlabd 1c_IEEE_123_feeder_2.glm` → logs `examples/2bus-13bus/logs/gld2.log`
  - `python 1bc_EV_Controller.py -c 1c` → logs `examples/2bus-13bus/logs/controller.log`
  - `./build/gpk-left-fed.x` → logs `examples/2bus-13bus/logs/gridpack.log`
  - `python run_server.py --config config/ev_mcp_local.yaml` → logs `examples/2bus-13bus/logs/attacker.log`

Useful environment overrides (set before `docker compose up`):
- `RUN_AI_CAMPAIGN=0` to disable the automated LLM campaign.
- `AI_CAMPAIGN_STEPS`, `AI_CAMPAIGN_INTERVAL`, `AI_CAMPAIGN_WAIT`, `AI_CAMPAIGN_DURATION`, `AI_CAMPAIGN_ACTION_DELAY` to tune the campaign.
- `LLM_API_BASE` and `LLM_MODEL` to point at your OpenAI-compatible endpoint.
- `GRIDPACK_PERIOD_SEC` and `GRIDPACK_DURATION_SEC` to adjust GridPACK stepping.

Sanity check from host:

```bash
curl -s http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"get_grid_status","params":{}}'
```

### Option B (Advanced): Native Build + HELICS Runner
Use this path only if you need to run everything without Docker.

1) Install prerequisites
- HELICS (runtime and CLI)
- GridLAB-D built with HELICS support
- GridPACK and its dependencies
- Python 3.10+ with `helics`, `numpy`, `pandas`, `matplotlib`

2) Build the GridPACK federate executable

```bash
cd examples/2bus-13bus
rm -rf build
mkdir build
cd build
cmake ..
make -j"$(nproc)"
```

3) Run the federation using HELICS runner

```bash
cd examples/2bus-13bus
helics run --path=gpk-gld-cosim.json
```

If you want the attacker interface in native mode, run the MCP server separately:

```bash
cd archive/ev_setpoint_mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_server.py --config config/ev_mcp_local.yaml
```

## Key Files and Outputs
- Models: [examples/2bus-13bus/1c_IEEE_123_feeder.glm](examples/2bus-13bus/1c_IEEE_123_feeder.glm), [examples/2bus-13bus/1c_IEEE_123_feeder_2.glm](examples/2bus-13bus/1c_IEEE_123_feeder_2.glm), [examples/2bus-13bus/gridlabd.xml](examples/2bus-13bus/gridlabd.xml).
- HELICS configs: [examples/2bus-13bus/gpk-gld-cosim.json](examples/2bus-13bus/gpk-gld-cosim.json), [examples/2bus-13bus/mainglm.json](examples/2bus-13bus/mainglm.json), [examples/2bus-13bus/1c_Control.json](examples/2bus-13bus/1c_Control.json), [examples/2bus-13bus/1c_Control_2.json](examples/2bus-13bus/1c_Control_2.json).
- Controller code: [examples/2bus-13bus/1bc_EV_Controller.py](examples/2bus-13bus/1bc_EV_Controller.py), [examples/2bus-13bus/1bc_EV_Controller_2.py](examples/2bus-13bus/1bc_EV_Controller_2.py).
- Diagrams and quick guides: [examples/2bus-13bus/GRID_DIAGRAM.md](examples/2bus-13bus/GRID_DIAGRAM.md), [examples/2bus-13bus/QUICK_REFERENCE.txt](examples/2bus-13bus/QUICK_REFERENCE.txt), [examples/2bus-13bus/SYSTEM_DIAGRAM.txt](examples/2bus-13bus/SYSTEM_DIAGRAM.txt), topology image [examples/2bus-13bus/2bus-13bus-topology.png](examples/2bus-13bus/2bus-13bus-topology.png).
- Logs and outputs: controller CSVs and plots in [examples/2bus-13bus/output](examples/2bus-13bus/output), runtime logs under [examples/2bus-13bus/logs](examples/2bus-13bus/logs).

## Reproduction Checklist (No Guesswork)
- `examples/2bus-13bus` exists and contains the model files (cloned from `Grid-Simulation-Models`).
- Docker path:
  - `roi-img:latest` exists locally (`docker images | grep roi-img`).
  - `docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build` runs to completion.
  - `http://localhost:5100/primitive` responds.
  - `examples/2bus-13bus/logs/` contains `broker.log`, `gld1.log`, `gld2.log`, `controller.log`, `gridpack.log`, `attacker.log`.
- Native path:
  - `helics run` and `helics_broker` are on PATH.
  - `gridlabd` is on PATH.
  - `examples/2bus-13bus/build/gpk-left-fed.x` exists and is executable.
  - `helics run --path=gpk-gld-cosim.json` starts all federates.

## Notable Behaviors and Caveats
- Endpoint arbitration is last-writer-wins; an attacker or faster publisher can override the legitimate controller on `gld_hlc_conn/EV1-6`.
- In `1bc_EV_Controller.py`, the safe-range branch currently writes EV1/EV2 commands to all six endpoints; adjust if per-EV differentiation is required.
- Default update interval (60 s) is much faster than the narrative 20-minute cycle; tune `CONTROLLER_INTERVAL_SEC` to match desired cadence.
- Feeder upper-limit values differ across artifacts (4.2 MW in documentation vs 4.8 MW in `1bc_EV_Controller.py`); align thresholds before experiments to avoid mismatched protection behavior.
- Controller filter delays (3600 s) dramatically slow legitimate updates; if left enabled, attacker messages will dominate during the first hour unless controller is started well before attack or filter is removed.
- Storage inverters (from gridlabd.xml): rated_power 200 kVA with max charge/discharge 500 kW, 480 V DC bus, four-quadrant load-following mode tied to `storage_EV1`/`storage_EV4`; trip settings include IEEE 1547 thresholds and reconnection delay 300 s—attacks that island storage should consider SOC and trip logic.
- To replicate end-to-end: build GridPACK binary, ensure HELICS CLI present, install Python deps, run `helics run --path gpk-gld-cosim.json` from examples/2bus-13bus, optionally start attacker MCP via docker compose, and monitor outputs in `logs/` and `output/`.
