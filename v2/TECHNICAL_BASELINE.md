# Technical Baseline: Verified State of the Co-Simulation Stack

This document captures the verified technical details of every component, as of the deep dive on 2026-04-04. Use this as the ground truth when designing v2 experiments.

---

## 1. Base Docker Image (`roi-img:latest`)

**Dockerfile**: `archive/legacy_demo/containers/docker/Dockerfile`

| Component | Version | Notes |
|-----------|---------|-------|
| OS | Ubuntu 22.04 | |
| HELICS | Source build (3.x) | C++ shared lib + Python bindings |
| GridLAB-D | Source build from `gridlab-d/gridlab-d` | With HELICS support (`-DGLD_USE_HELICS=ON`) |
| GridPACK | Source build from `GridOPTICS/GridPACK` | Requires Boost 1.78, GA 5.8, PETSc 3.16.4 |
| Python | 3.x (Ubuntu default) | `python` symlinked to `python3` |
| MPI | OpenMPI | `OMPI_ALLOW_RUN_AS_ROOT=1` |
| Image size | ~9.7 GB | |

**Key env vars in image**:
```
PATH includes /usr/local/gridlabd/bin, /usr/local/GridPACK/bin, /usr/local/helics/bin
PETSC_DIR=/usr/local/petsc-3.16.4
LD_LIBRARY_PATH=/usr/local/petsc-3.16.4/lib
```

---

## 2. HELICS Federation Configuration

### File: `examples/2bus-13bus/gpk-gld-cosim-with-mcp.json`

**Broker**: `-f5 --port=23404 --local` (5 federates expected)

| # | Federate | Executable | Name | Working Dir |
|---|----------|-----------|------|-------------|
| 1 | GridLAB-D Feeder A | `gridlabd 1c_IEEE_123_feeder.glm` | `IEEE123bus_fed` | `.` |
| 2 | GridLAB-D Feeder B | `gridlabd 1c_IEEE_123_feeder_2.glm` | `IEEE123bus_fed_2` | `.` |
| 3 | EV Controller | `python 1bc_EV_Controller.py -c 1c` | `1c_Controller` | `.` |
| 4 | GridPACK | `./build/gpk-left-fed.x` | `gridpack` | `.` |
| 5 | Attacker MCP | `python -m llm_grid_eval.server` | `ev_attacker_mcp` | `/app/llm_grid_eval` |

All connect to broker at `tcp://localhost:23404`.

---

## 3. GridLAB-D Feeder A (`1c_IEEE_123_feeder.glm`)

### Simulation Parameters
- **Clock**: 2013-08-28 07:00:00 to 2013-08-29 00:00:00 PST8
- **Minimum timestep**: 60 seconds
- **Solver**: FBS (Forward-Backward Sweep)
- **Line limits**: FALSE (disabled)
- **Newton-Raphson**: Available but commented out

### HELICS Interface (`mainglm.json`)
- **Name**: `gld_hlc_conn`, parent: `Node650`
- **Core**: ZMQ, period: 60s
- **Publications**: `gld_hlc_conn/Sa`, `Sb`, `Sc` (complex VA from Node650)
- **Subscriptions**: `gridpack/Va`, `Vb`, `Vc` (complex V), `swEV1`, `swEV1_storage`, `swEV4`, `swEV4_storage` (string)
- **Endpoints**: `gld_hlc_conn/EV1` through `EV6` (bidirectional, destinations: `EV_Controller/EV{1-6}`)

### EV Station Definitions

| EV | Node | Phase | Load (kW) | Nominal V | Switch | Battery |
|----|------|-------|-----------|-----------|--------|---------|
| EV1 | l5 | CN | 200 | 2401.7771 | swEV1 (closed) | Yes: 205 kWh Li-ion, 50% SoC, 200 kW inverter |
| EV2 | l2 | BN | 200 | 2401.7771 | swEV2 (closed) | No |
| EV3 | l88 | AN | 200 | 2401.7771 | swEV3 (closed) | No |
| EV4 | l92 | CN | 200 | 2401.7771 | swEV4 (closed) | Yes: 205 kWh Li-ion, 50% SoC, 200 kW inverter |
| EV5 | l107 | BN | 200 | 2401.7771 | swEV5 (closed) | No |
| EV6 | l114 | AN | 210 | 2401.7771 | swEV6 (closed) | No |

### Battery/Inverter Config (EV1, EV4 only)
- Inverter type: FOUR_QUADRANT, mode: LOAD_FOLLOWING
- Rated power: 200 kW, efficiency: 95%
- Charge threshold ON/OFF: 200/700 kW
- Discharge threshold ON/OFF: 0/0 kW
- Max charge/discharge rate: 500 kW
- Battery: 205 kWh, 95% round-trip, 10% reserve SoC

### Storage Switches
- `swEV1_storage`: initially OPEN (battery disconnected)
- `swEV4_storage`: initially OPEN (battery disconnected)

---

## 4. GridLAB-D Feeder B (`1c_IEEE_123_feeder_2.glm`)

### Differences from Feeder A
- Minimum timestep: **120s** (vs 60s)
- HELICS name: `gld_hlc_conn_2`
- Voltage subscriptions: `gridpack/Va_2`, `Vb_2`, `Vc_2`
- **No EV endpoints** (Feeder B has no controllable EVs)
- **No switch subscriptions** (no swEV publications)
- Reduced loads (Load3 Phase A: 40 kW vs 190 kW in Feeder A)
- No generator module

---

## 5. GridPACK Transmission (`gpk-left-fed.cpp`)

- IEEE 9-bus system (from `Tr2bus.raw`)
- HELICS ZMQ core, 5s period
- **Publications**: `gridpack/Va`, `Vb`, `Vc` (for Feeder A), `Va_2`, `Vb_2`, `Vc_2` (for Feeder B)
- **Subscriptions**: `gld_hlc_conn/Sa`, `Sb`, `Sc` (from Feeder A), `gld_hlc_conn_2/Sa`, `Sb`, `Sc` (from Feeder B)
- Config: `input.xml` -- network `Tr2bus.raw`, connection node 2, subsystem node 3, load amplifier 15x

---

## 6. EV Controller (`1bc_EV_Controller.py`)

### HELICS Config (`1c_Control.json`)
- Name: `1c_Controller`
- Core: ZMQ, period: 60s
- **Subscriptions**: `gld_hlc_conn/Sa`, `Sb`, `Sc` (complex VA)
- **Endpoints**: `EV_Controller/EV1` through `EV6` → `gld_hlc_conn/EV1` through `EV6`
- **Publications**: `swEV1`, `swEV1_storage`, `swEV4`, `swEV4_storage`

### ⚠️ CRITICAL: Message Delay Filter
```json
"filters": [{
  "name": "EVfilters",
  "sourcetargets": ["EV_Controller/EV1", ..., "EV_Controller/EV6"],
  "mode": "source",
  "operation": "delay",
  "properties": {"name": "delay", "value": 3600}
}]
```
**ALL controller-to-EV commands are delayed by 3600 seconds (1 hour).**

### Controller Python Logic
- **Update interval**: 10 seconds (inner loop)
- **HELICS period**: 60 seconds
- **Simulation duration**: 86400 seconds (24 hours)
- **Total iterations**: 8640

### Three-State Decision Logic
```
IF P_feeder >= 4,200,000 W:
    → All 6 endpoints: '0.0+0.0j'  (shed all EVs)

ELIF 2,600,000 < P_feeder < 4,200,000 W:
    → Endpoints m0-m5: alternating '210000+0.0j' / '200000+0.0j'
    (NOTE: sends to ALL 6, not just EV1/EV2 as paper claims)

ELSE (P_feeder <= 2,600,000 W):
    → EV1: 210kW, EV2-5: 200kW, EV6: 206kW
```

### Second Controller (`1bc_EV_Controller_2.py`)
- 1200s update interval, 1 iteration, simplified logic
- Controls Feeder B endpoints (`EV_Controller_2/EV{1-6}`)
- Minimal test configuration

---

## 7. Attacker MCP Server (`llm_grid_eval/`)

### Server: FastAPI on port 5100
- HELICS federate: `ev_attacker_mcp`, ZMQ core, 5s period
- **Subscriptions**: Same as controller (Sa, Sb, Sc, Va, Vb, Vc, switches)
- **Endpoints**: `attacker/EV{1-6}` → `gld_hlc_conn/EV{1-6}`

### ⚠️ No Delay Filter on Attacker Endpoints
The attacker's messages arrive immediately. Combined with the 3600s delay on controller messages, the attacker has a massive timing advantage that is NOT about micro-timing -- it's about the controller being completely non-functional.

### Tool Endpoints
| Endpoint | Method | Effect |
|----------|--------|--------|
| `/tools/observe` | POST | Advance sim time + return GridState |
| `/tools/analyze` | POST | Advance sim time + compute timing assessment |
| `/tools/attack` | POST | Validate constraints + set EV target (ramped) |
| `/tools/metrics` | GET/POST | Return experiment metrics |
| `/experiment/start` | POST | Reset state for new experiment |
| `/experiment/end` | POST | Finalize metrics |
| `/health` | GET | Health check |
| `/constraints` | GET | Return active constraints |

### Ramp Controller
- Rate: 100 kW/s, 5s update interval → max 500 kW/step
- Default initial powers: EV1=220, EV2-5=200, EV4=220, EV6=200 kW
- Targets set by attack; ramped in `update()` called every timestep

---

## 8. HELICS Time Flow

```
GridPACK (5s) ──┐
                 ├──► Broker (port 23404) ──► time synchronization
Feeder A  (60s) ─┤
Feeder B (120s) ─┤
Controller (60s) ┤   (but inner loop: 10s via helicsFederateRequestTime)
Attacker   (5s) ─┘
```

The attacker and GridPACK request time every 5s. Feeder A requests every 60s. The broker coordinates so all federates advance together, but slower federates effectively gate the faster ones until they catch up.

---

## 9. Message Protocol

EV setpoint commands are sent as complex number strings in Watts:
```
'210000+0.0j'     → 210 kW real, 0 kVAR reactive
'1500000.0+0.0j'  → 1500 kW real, 0 kVAR reactive
'0.0+0.0j'        → 0 kW (shed)
```

Both controller and attacker use this format. Both send to `gld_hlc_conn/EV{n}` endpoints. GridLAB-D processes the most recent message per timestep.

---

## 10. Open Questions for v2

1. **Does the delay filter apply to attacker messages too?** The filter targets `EV_Controller/EV{n}` source endpoints. The attacker uses `attacker/EV{n}` endpoints with the same destination. Need to verify whether GridLAB-D's endpoint receives both and if the filter affects only controller-sourced messages.

2. **How do batteries on EV1/EV4 interact with attack setpoints?** The LOAD_FOLLOWING inverter mode charges when power > 200 kW and discharges when power < 0. If the attacker sets EV1 to 1500 kW, the inverter may try to charge, potentially amplifying or damping the attack effect.

3. **What happens when both controller and attacker send to the same EV endpoint?** HELICS endpoint message model: all messages queue. GridLAB-D processes them in order. If both arrive in the same timestep, the last one wins.

4. **Does Feeder B actually affect Feeder A load?** Through GridPACK coupling, yes -- both feeders are loads on the transmission system. Changes in Feeder B affect transmission voltages which feed back to Feeder A. But the effect may be negligible.
