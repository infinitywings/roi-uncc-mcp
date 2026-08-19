# Grid Testbed Reference Manual

A comprehensive reference consolidating all documentation for the AI-assisted red teaming grid co-simulation testbed.

**Consolidated from:**
- `examples/2bus-13bus/GRID_DIAGRAM.md` — Detailed grid topology diagrams
- `examples/2bus-13bus/README.md` — System overview and EV station details
- `examples/2bus-13bus/QUICK_REFERENCE.txt` — Operational commands
- `docs/ai_red_team_framework_summary.md` — Research framework overview
- `docs/attack_vs_baseline_report.md` — Experimental comparison results
- `archive/ev_setpoint_mcp/README.md` — archived MCP server documentation
- `archive/ev_setpoint_mcp/ATTACK_STRATEGIES.md` — archived attack strategy catalog
- `archive/ev_setpoint_mcp/CONFIG_VALIDATION.md` — archived configuration validation
- `archive/ev_setpoint_mcp/DEPLOYMENT_ATTACK_MODE.md` — archived deployment guide
- `archive/ev_setpoint_mcp/CHANGES_FOR_ATTACK_MODE.md` — archived implementation changelog
- `archive/ev_setpoint_mcp/SUMMARY.md` — archived quick reference summary

---

## Table of Contents

1. [Research Framework](#1-research-framework)
2. [System Overview](#2-system-overview)
3. [Transmission System](#3-transmission-system-ieee-9-bus)
4. [Distribution System A](#4-distribution-system-a-ieee-123-node)
5. [Distribution System B](#5-distribution-system-b)
6. [HELICS Communication Architecture](#6-helics-communication-architecture)
7. [Protection Limits](#7-protection-limits)
8. [EV Setpoint MCP Server](#8-ev-setpoint-mcp-server)
9. [Attack Surface Map](#9-attack-surface-map)
10. [Attack Strategies Catalog](#10-attack-strategies-catalog)
11. [Operational Flows](#11-operational-flows)
12. [Deployment Guide](#12-deployment-guide)
13. [Configuration Reference](#13-configuration-reference)
14. [API Reference](#14-api-reference)
15. [Experimental Results](#15-experimental-results)
16. [Troubleshooting](#16-troubleshooting)
17. [Key Files Reference](#17-key-files-reference)
18. [Summary Statistics](#18-summary-statistics)

---

## 1. Research Framework

### Motivation

Modern electric grids are increasingly software-defined and interconnected, which means that subtle weaknesses in control logic or communications can translate rapidly into physical risk. Traditional security testing still relies heavily on scripted fault scenarios, leaving planners without a reliable way to gauge how their defences hold up against adaptive adversaries.

The proposed evaluation framework closes this gap by connecting an AI-assisted attacker to a high-fidelity co-simulation environment so that the grid can be stressed with dynamically generated campaigns rather than predetermined playbooks.

### Design Pillars

1. **Modular Co-Simulation**: Grid models, communication overlays, and controller configurations can be swapped in and out for different scenarios.

2. **Governed Tool Registry**: The attacker operates through a governed tool registry that advertises legitimate primitives and enforces safety constraints.

3. **Full Instrumentation**: Protection states, DER responses, communication delays, and disruption scores are captured continuously for quantitative comparison.

### Expected Outcome

A reusable playbook for resilience assessment where stakeholders can run repeatable, fully instrumented campaigns in which an AI adversary adapts to their defences, reveals residual weaknesses, and validates remediation steps before deployment on real infrastructure.

---

## 2. System Overview

The testbed integrates transmission and distribution systems with EV charging infrastructure for AI-driven cybersecurity research.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    T&D Co-Simulation Architecture                            │
│                                                                               │
│  Transmission (GridPACK)          Distribution (GridLAB-D)                   │
│  IEEE 9-bus System                IEEE 123-node Feeders                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Technology | Model | Notes |
|-----------|------------|-------|-------|
| Transmission | GridPACK | IEEE 9-bus | 69 kV, 3 generators |
| Distribution A | GridLAB-D | IEEE 123-node | 4.16 kV, 6 EVs, controllable |
| Distribution B | GridLAB-D | IEEE 123-node | 4.16 kV, no EV control |
| Blue-Team Controller | Python/HELICS | Custom | Peak-shaving, islanding |
| Red-Team MCP | Flask/HELICS | Custom | AI-driven setpoint injection |

### Red Team vs Blue Team Architecture

```
Grid Simulation (Docker)
│
├─ HELICS Broker (port 23406)
│   │
│   ├─ GridLAB-D (IEEE 123-bus distribution)
│   ├─ GridPACK (IEEE 9-bus transmission)
│   │
│   ├─ Blue Team: 1bc_EV_Controller.py (legitimate)
│   │    └─ Publishes to: gld_hlc_conn/EV1-6
│   │    └─ Function: Peak shaving, islanding control
│   │
│   └─ Red Team: EV Attacker MCP (this server)
│        └─ Publishes to: gld_hlc_conn/EV1-6 (SAME!)
│        └─ Function: Malicious setpoint injection
│
└─ AI Attacker (external)
     └─ Uses MCP REST API to attack grid
```

**Competition Mechanism**: Both controllers send messages to the same endpoints. HELICS delivers chronologically, so **the last message received wins**.

---

## 3. Transmission System (IEEE 9-bus)

**Federate**: `gridpack`  
**Source**: `gpk-left-fed.cpp`

```
                    GridPACK Federate: "gridpack"

    ┌────────┐                                    ┌────────┐
    │  Gen1  │                                    │  Gen2  │
    └───┬────┘                                    └────┬───┘
        │                                              │
        │ Bus1                                    Bus2 │
        ○──────────────Line 1-4────────────────────────○ ← Tie to Feeder A
        │                                              │   (Node650)
        │                                              │
    Bus4○                                         Bus5 ○
        │                                              │
        │                                              │
    Bus7○──────────────Line 7-8──────────────○ Bus8   │
        │                                     │        │
        │                                     │        │
    Bus9○                                     │    Bus6○
        │                                     │        │
        └─────────────Line 9-6─────────────────────────┘
                                              │
                                         Bus3 ○ ← Tie to Feeder B
                                              │   (Node650)
                                         ┌────┴────┐
                                         │  Gen3   │
                                         └─────────┘
```

### HELICS Interface

| Direction | Topic | Description |
|-----------|-------|-------------|
| Publishes | `gridpack/Va`, `Vb`, `Vc` | Complex voltage at tie buses |
| Subscribes | `gld_hlc_conn/Sa`, `Sb`, `Sc` | Power demand from feeders |

---

## 4. Distribution System A (IEEE 123-node)

**Federate**: `IEEE13bus_fed`  
**Config**: `1c_IEEE_123_feeder.glm`  
**Swing Bus**: `Node650` (connected to Transmission Bus2)

### Main Feeder Topology

```
                        From Transmission Bus2
                               ↓
                          [Node650] ← Swing Bus (3-phase)
                               │    Publications: gld_hlc_conn/Sa,Sb,Sc
                               │    Subscriptions: gridpack/Va,Vb,Vc
                               │
                          [Regulator]
                               │
                         ┌─────┴─────┐
                         │           │
                    [Primary  ]  [Laterals...]
                      Feeder
                         │
                    ┌────┴────┬──────┬──────┬──────┬──────┐
                    │         │      │      │      │      │
                   l5        l2    l88    l92   l107   l114
                    │         │      │      │      │      │
                [swEV1]   [swEV2] [swEV3][swEV4][swEV5][swEV6]
                    │         │      │      │      │      │
                  [EV1]     [EV2]  [EV3]  [EV4]  [EV5]  [EV6]
                    │                        │
              [swEV1_storage]          [swEV4_storage]
                    │                        │
              [EV1_STORAGE]            [EV4_STORAGE]
               (Battery)                (Battery)
```

### EV Charging Station Configuration

| EV | Link | Phase | Switch | Storage | Normal Power | Attack Max | Power Property |
|----|------|-------|--------|---------|--------------|------------|----------------|
| EV1 | l5 | CN | swEV1 + storage | ✓ Yes | 220 kW | 4 MW | constant_power_C |
| EV2 | l2 | BN | swEV2 | ✗ No | 200 kW | 4 MW | constant_power_B |
| EV3 | l88 | AN | swEV3 | ✗ No | 200 kW | 4 MW | constant_power_A |
| EV4 | l92 | CN | swEV4 + storage | ✓ Yes | 220 kW | 4 MW | constant_power_C |
| EV5 | l107 | BN | swEV5 | ✗ No | 200 kW | 4 MW | constant_power_B |
| EV6 | l114 | AN | swEV6 | ✗ No | 200 kW | 4 MW | constant_power_A |

### Phase Distribution

- **Phase A (AN):** EV3, EV6
- **Phase B (BN):** EV2, EV5
- **Phase C (CN):** EV1, EV4 (both have battery storage)

### Islanding Capability (EV1 and EV4)

```
Normal Operation:                     Islanded Operation (Overload):

Grid ──[swEV1]──○──[EV1]             Grid  [swEV1]    ○──[EV1]
        CLOSED   │                           OPEN      │
                 │                                     │
    [swEV1_storage]                         [swEV1_storage]
        OPEN     │                             CLOSED  │
                 │                                     │
            [Battery]                             [Battery]
                                                  (powers EV1)
```

**Trigger:** Total feeder load > 4.2 MW  
**Action:** Controller opens grid switch, closes storage switch  
**Result:** EV1/EV4 powered by local battery, isolated from grid

---

## 5. Distribution System B

**Federate**: `IEEE13bus_fed_2`  
**Config**: `1c_IEEE_123_feeder_2.glm`  
**Swing Bus**: `Node650` (connected to Transmission Bus3)

```
                        From Transmission Bus3
                               ↓
                          [Node650] ← Swing Bus (3-phase)
                               │
                          [Regulator]
                               │
                         [IEEE 123-node]
                          Distribution
                           Network

    ⚠️  No EV control configured for Feeder B
    ⚠️  Used for load diversity / system testing
```

---

## 6. HELICS Communication Architecture

### Federate Topology

```
                         ┌─────────────────┐
                         │  HELICS Broker  │
                         │  Port: 23406    │
                         └────────┬────────┘
                                  │
              ┌───────────────────┼───────────────────┬───────────────┐
              │                   │                   │               │
    ┌─────────▼──────┐  ┌────────▼────────┐  ┌──────▼──────┐  ┌────▼────────┐
    │   gridpack     │  │ IEEE13bus_fed   │  │IEEE13bus_   │  │EVController │
    │                │  │                 │  │   fed_2     │  │    Sim      │
    │ Transmission   │  │ Distribution A  │  │Distribution │  │             │
    │ IEEE 9-bus     │  │ IEEE 123-node   │  │     B       │  │ Blue Team   │
    │                │  │ + 6 EVs         │  │ IEEE 123    │  │ Controller  │
    └────────────────┘  └─────────────────┘  └─────────────┘  └─────────────┘
```

### Publication/Subscription Matrix

| Federate | Publishes | Subscribes |
|----------|-----------|------------|
| **gridpack** | `gridpack/Va,Vb,Vc` | `gld_hlc_conn/Sa,Sb,Sc` |
| **IEEE13bus_fed** | `gld_hlc_conn/Sa,Sb,Sc` | `gridpack/Va,Vb,Vc`, `swEV1,swEV4` (switches) |
| **EVControllerSim** | `swEV1,swEV4,swEV1_storage,swEV4_storage`, `EV_Controller/EV1-6` | `gld_hlc_conn/Sa,Sb,Sc` |
| **ev_attacker_mcp** | `attacker/EV1-6` | `gld_hlc_conn/Sa,Sb,Sc`, `gridpack/Va,Vb,Vc`, switches |

### HELICS Key Mapping (Validated)

| Data Type | Source Federate | Publication Key | MCP Subscription | Type |
|-----------|-----------------|-----------------|------------------|------|
| **Powers** | IEEE13bus_fed | gld_hlc_conn/Sa | feeder_power_A | complex (VA) |
| | IEEE13bus_fed | gld_hlc_conn/Sb | feeder_power_B | complex (VA) |
| | IEEE13bus_fed | gld_hlc_conn/Sc | feeder_power_C | complex (VA) |
| **Voltages** | gridpack | gridpack/Va | transmission_voltage_A | complex (V) |
| | gridpack | gridpack/Vb | transmission_voltage_B | complex (V) |
| | gridpack | gridpack/Vc | transmission_voltage_C | complex (V) |
| **Switches** | EVControllerSim | swEV1_storage | switch_EV1_storage | string |
| | EVControllerSim | swEV1 | switch_EV1 | string |
| | EVControllerSim | swEV4_storage | switch_EV4_storage | string |
| | EVControllerSim | swEV4 | switch_EV4 | string |

### Competing Controllers (Red vs Blue Team)

```
┌─────────────────┐                    ┌─────────────────┐
│ EVControllerSim │                    │ ev_attacker_mcp │
│   (Blue Team)   │                    │   (Red Team)    │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │ EV_Controller/EV1-6                  │ attacker/EV1-6
         │                                      │
         └──────────────┬───────────────────────┘
                        │
                        ▼
              ┌────────────────────┐
              │ gld_hlc_conn/EV1-6 │ ← GridLAB-D endpoint
              └────────────────────┘
                        │
                        │ LAST MESSAGE WINS!
                        ▼
              ┌────────────────────┐
              │ EV1-6 Load Objects │
              │   in GridLAB-D     │
              └────────────────────┘
```

---

## 7. Protection Limits

| Parameter | Value | Description |
|-----------|-------|-------------|
| Feeder Upper Limit | 4.2 MW | Triggers islanding |
| Feeder Lower Limit | 2.6 MW | All EVs enabled |
| Voltage Range | 0.95–1.05 pu | Per-unit limits |
| Nominal Voltage | 2401.7771 V | Line-to-neutral |

---

## 8. EV Setpoint MCP Server

The EV Setpoint MCP Server operates as an **adversarial interface** for AI-driven grid penetration testing on the 2bus-13bus co-simulation.

### Observation Primitives (Reconnaissance)

| Primitive | Description |
|-----------|-------------|
| `get_grid_status` | Monitor real-time voltages, powers, and EV states |
| `discover_topology` | Map transmission/distribution topology and vulnerabilities |
| `monitor_protection_systems` | Track feeder load limits and protection status |
| `analyze_power_flow` | Understand power flow patterns for attack targeting |

### Action Primitive (Attack Execution)

| Primitive | Description |
|-----------|-------------|
| `set_ev_capacity` | Inject malicious EV setpoints that compete with legitimate controller |

**Setpoint Ranges:**
- Normal operation: 200–220 kW per EV
- Attack mode: Up to 4000 kW (4 MW) per EV
- Reverse power injection: Down to −1000 kW

### Attack Type Classification

The MCP server automatically classifies attack types:

| Attack Type | Description | Setpoint Range |
|-------------|-------------|----------------|
| `normal` | Within normal operating range | 0–220 kW |
| `mild_overload` | 10–50% over normal limit | 220–330 kW |
| `overload_attack` | >50% over normal limit | 330–4000 kW |
| `reverse_power_injection` | Negative setpoints | −1000 to 0 kW |
| `reactive_power_attack` | Excessive reactive power | High Q values |

---

## 9. Attack Surface Map

### Layer 1: EV Charging Stations

**Target:** `gld_hlc_conn/EV1-6` endpoints  
**Method:** Inject malicious setpoints via attacker MCP  
**Impact:** Overload, phase imbalance, reverse power injection

```
  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │  EV3/6  │  │  EV2/5  │  │  EV1/4  │  │ Storage │
  │ Phase A │  │ Phase B │  │ Phase C │  │ Systems │
  └─────────┘  └─────────┘  └─────────┘  └─────────┘

Attack Vectors:
  • Overload (2–4 MW per EV)
  • Phase imbalance (heavy on one phase)
  • Reverse power injection (−500 kW)
  • Storage depletion during islanding
```

### Layer 2: Distribution Feeder

**Critical Point:** Node650 (swing bus)  
**Protection:** Feeder load limits (2.6–4.2 MW)  
**Vulnerability:** Cumulative EV overload

| Load Type | Value |
|-----------|-------|
| Normal Load | ~3.0 MW |
| EV Load (normal) | ~1.2 MW (6 × 200 kW) |
| Attack Load (max) | 24 MW (6 × 4 MW) |

**Attack Goal:** Total > 4.2 MW → Trigger protection

### Layer 3: Transmission Tie

**Weak Point:** Bus2 ↔ Node650 tie  
**Impact:** Cascading to transmission system  
**Detection:** Voltage deviation at `gridpack/Va,Vb,Vc`

---

## 10. Attack Strategies Catalog

### Strategy 1: Simple Overload Attack

**Objective:** Exceed feeder load limits to trigger protection systems

```bash
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV3","real_power_kw":2500}}'
```

**Expected Impact:**
- Feeder load exceeds 4.2 MW threshold
- Controller triggers islanding for EV1/EV4
- Battery storage activated

### Strategy 2: Reverse Power Injection

**Objective:** Disrupt power flow direction to cause protection misoperation

```bash
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV1","real_power_kw":-500}}'
```

**Expected Impact:**
- Reverse power flow on distribution feeder
- Voltage rise at EV connection point
- Protection relay confusion

### Strategy 3: Phase Imbalance Attack

**Objective:** Create voltage imbalance across three phases

```bash
# Heavy load on Phase C (EV1 + EV4)
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV1","real_power_kw":3500}}'
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV4","real_power_kw":3500}}'
```

**Expected Impact:**
- Severe voltage imbalance across phases
- Phase C voltage drop significantly
- Neutral current increase

### Strategy 4: Timing-Based Attack (Peak Demand)

**Objective:** Attack during peak hours (15:00–17:00) when grid is stressed

**Approach:**
1. Monitor feeder load via `get_grid_status`
2. Wait until legitimate load approaches 3.5–4.0 MW
3. Inject additional load to push over 4.2 MW limit

### Strategy 5: Storage Exploitation

**Objective:** Drain battery storage during islanding

**Steps:**
1. Trigger overload to force EV1/EV4 islanding with storage
2. Once islanded, inject maximum load on EV1 and EV4
3. Deplete batteries so they can't support future events

### Strategy 6: Reactive Power Attack

**Objective:** Cause voltage issues through excessive reactive power injection

```bash
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV6","real_power_kw":500,"reactive_power_kvar":800}}'
```

### Strategy 7: Rapid Setpoint Fluctuation

**Objective:** Create instability through rapid load changes

- Send setpoint commands every 1–5 seconds
- Alternate between high and low setpoints
- Causes continuous power flow oscillations

### Strategy 8: Coordinated Multi-Stage Campaign

**Stages:**
1. **Reconnaissance** (0–60s): Monitor grid state via observation primitives
2. **Preparation** (60–120s): Identify vulnerable EVs and timing
3. **Initial Strike** (120–180s): Trigger overload to force islanding
4. **Exploitation** (180–300s): Attack storage systems during islanding
5. **Cascading** (300–360s): Rapid fluctuations to prevent recovery

---

## 11. Operational Flows

### Normal Operation (Blue Team)

| Time | Load | Controller Action |
|------|------|-------------------|
| 0s | 3.0 MW | Monitor, normal operation |
| 1200s | 3.5 MW | Mild EV adjustment |
| 2400s | 4.3 MW | **ISLANDING TRIGGERED** |

**Islanding Actions:**
- Open `swEV1`, `swEV4` (disconnect from grid)
- Close `swEV1_storage`, `swEV4_storage`
- EV1, EV4 → battery powered (200 kW)
- EV2, 3, 5, 6 → disconnected (0 kW)

### Attack Operation (Red Team)

| Time | Observation | Attacker Action | Result |
|------|-------------|-----------------|--------|
| 0s | 3.0 MW | Wait for peak | — |
| 900s | 3.8 MW | EV3 → 2500 kW, EV5 → 2000 kW | 8.3 MW (OVERLOAD!) |
| 920s | Controller responds | Drain batteries: EV1,4 → 220 kW | Batteries depleting |
| 1800s | — | — | Batteries exhausted |

---

## 12. Deployment Guide

### One-Container Demo (Recommended)

```bash
cd /home/cfu6/roi-uncc-mcp
docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build
```

This:
- Builds GridPACK if needed
- Launches broker + all five federates (GridLAB-D ×2, EV controller, GridPACK, attacker MCP)
- Starts `run_ai_campaign.py` with the local LLM endpoint
- Streams logs to `examples/2bus-13bus/logs/`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUN_AI_CAMPAIGN` | `1` | Set to `0` to skip automatic AI campaign |
| `AI_CAMPAIGN_STEPS` | `3` | Number of LLM-driven attack iterations |
| `AI_CAMPAIGN_INTERVAL` | `30` | Seconds to wait between iterations |
| `AI_CAMPAIGN_WAIT` | `60` | Readiness wait window in seconds |
| `LLM_API_BASE` | `http://ccil1s26m8hj6lws:8000/v1` | OpenAI-compatible endpoint |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Model identifier |

### Verify Startup

```bash
docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml logs grid-attack-demo
```

Should show:
- `HELICS federate ev_attacker_mcp entered execution mode`
- `Running on http://127.0.0.1:5100`

### Log Files

| Log | Location | Content |
|-----|----------|---------|
| Attacker | `examples/2bus-13bus/logs/attacker.log` | MCP server output |
| GridLAB-D 1 | `examples/2bus-13bus/logs/gld1.log` | Feeder A simulation |
| GridLAB-D 2 | `examples/2bus-13bus/logs/gld2.log` | Feeder B simulation |
| Controller | `examples/2bus-13bus/logs/controller.log` | Blue-team actions |
| AI Campaign | `examples/2bus-13bus/logs/ai_campaign.log` | REST request/response |
| LLM | `examples/2bus-13bus/logs/llm_interactions.jsonl` | Full LLM prompts/responses |

---

## 13. Configuration Reference

### Timing Parameters

| Parameter | Value | Source | Purpose |
|-----------|-------|--------|---------|
| GridLAB-D period | 60s | mainglm.json | Power flow timestep |
| MCP time_delta | 60s | ev_mcp.yaml | Match GridLAB-D |
| MCP period | 60s | ev_mcp.yaml | HELICS sync interval |
| Controller update | 1200s | 1bc_EV_Controller.py | Legitimate control updates |
| MCP poll_interval | 0.5s | ev_mcp.yaml | Attack responsiveness |

### Setpoint Constraints

```yaml
setpoint_constraints:
  default_max_kw: 4000      # Attack target
  default_min_kw: -1000     # Reverse power injection
  attack_mode: true

  ev_limits:
    EV1:
      normal_max_kw: 220    # Legitimate operation
      attack_max_kw: 4000   # Overload attack
      min_kw: -500          # Reverse power injection
      phases: CN
      has_storage: true
```

---

## 14. API Reference

### Observe Grid Status

```bash
curl http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"get_grid_status","params":{}}'
```

### Discover Topology

```bash
curl http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"discover_topology","params":{}}'
```

### Execute Attack (Overload)

```bash
curl http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV3","real_power_kw":2500}}'
```

### Monitor Protection

```bash
curl http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"monitor_protection_systems","params":{}}'
```

---

## 15. Experimental Results

### Attack vs Baseline Comparison

**Shared Configuration:**
- Runtime: Docker Compose stack
- AI parameters: Unlimited steps, 5s interval, 600s warm-up, 24h target
- Attacker HELICS: 600s time quanta, 6 EV endpoints capped at ±4 MW
- Blue-team: 20-minute intervals, 2.6–4.2 MW limits

### Run 1: AI Attacker Enabled

**What Happened:**
- Initial telemetry: 3.56 MW feeder load, all EVs at 0 kW
- LLM action: Step 1 requested 3 MW surge on EV3
- Result: Multiple primary lines exceeded 200% emergency ratings
- GridLAB-D declared convergence failure at 00:11 PST
- Simulation halted after first attack step

**Key Takeaway:** A single 3 MW command destabilized the feeder faster than protection could react.

### Run 2: Baseline (No Attack)

**What Happened:**
- Controller advanced through multiple 20-minute intervals
- Feeder load stayed between 3.1–3.6 MW
- Controller affirmed SAFE RANGE action at every checkpoint
- GridLAB-D progressed past 01:30 PST without issues

**Key Takeaway:** Without attacks, feeder cruises within 4.2 MW bound; controller cycles through SAFE RANGE branch normally.

### Comparative Notes

| Metric | Attack Run | Baseline Run |
|--------|------------|--------------|
| Simulation Progress | 600s (halted) | 6000s+ (continuing) |
| Controller Logs | 1 entry | Multiple entries |
| Grid Stability | Convergence failure | Stable |
| Line Overloads | 210%+ on multiple lines | None |

---

## 16. Troubleshooting

### Issue: Subscriptions Return All Zeros

**Symptom:** `get_grid_status` returns 0 for all voltages/powers

**Check:**
```bash
docker logs helics-broker | grep "registering publication"
```

**Fix:** Update subscription keys in `ev_mcp.yaml`:
- Wrong: `IEEE13bus_fed/gld_hlc_conn/Sa`
- Right: `gld_hlc_conn/Sa`

### Issue: Attack Setpoints Have No Effect

**Possible Causes:**
1. HELICS endpoint mismatch
2. Message timing (controller sending more frequently)
3. Simulation time scaling

**Debug:**
```bash
docker logs ev-setpoint-mcp | grep "Dispatching EV capacity"
docker logs IEEE13bus_fed | grep "endpoint"
```

### Issue: MCP Can't Connect to HELICS

**Check:**
```bash
docker ps | grep helics-broker
netstat -an | grep 23406
```

**Fix:** Ensure broker address is `tcp://helics-broker:23406` (Docker) or `tcp://localhost:23406` (local)

### Issue: Timing Misalignment

**Symptom:** MCP federate can't sync with simulation

**Fix:** Ensure `time_delta` and `period` match GridLAB-D configuration (60s)

---

## 17. Key Files Reference

| Purpose | Path |
|---------|------|
| Grid Model | `examples/2bus-13bus/1c_IEEE_123_feeder.glm` |
| HELICS Config | `examples/2bus-13bus/mainglm.json` |
| Blue-Team Controller | `examples/2bus-13bus/1bc_EV_Controller.py` |
| Simulation Runner | `examples/2bus-13bus/gpk-gld-cosim.json` |
| MCP Config | `archive/ev_setpoint_mcp/config/ev_mcp.yaml` |
| AI Campaign | `archive/ev_setpoint_mcp/tools/run_ai_campaign.py` |
| Docker Compose | `archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml` |
| Attack Strategies | `archive/ev_setpoint_mcp/ATTACK_STRATEGIES.md` |

---

## 18. Summary Statistics

| Metric | Value |
|--------|-------|
| Transmission Buses | 9 (IEEE 9-bus) |
| Distribution Nodes (A) | 123 (IEEE 123-node) |
| Distribution Nodes (B) | 123 (IEEE 123-node) |
| EV Charging Stations | 6 (Feeder A only) |
| Battery Storage Systems | 2 (EV1, EV4) |
| HELICS Federates | 5 (includes attacker MCP) |
| Attack Endpoints | 6 (`gld_hlc_conn/EV1-6`) |
| Protection Range | 2.6–4.2 MW |
| Normal Peak Load | ~4.0 MW |
| Maximum Attack Load | 24 MW (6 × 4 MW) |

---

## Appendix: Symbols and Legend

```
Symbols:
  ○ ═ ─    Electrical connections
  [ ]      Equipment/component
  ↔ ↕ →    Power/data flow
  ┌ ┐ └ ┘  Diagram structure

Components:
  Node     - Bus bar (voltage node)
  Link     - Distribution line segment
  Transformer - Voltage conversion
  Switch   - Controllable breaker
  Load     - Power consumption point

HELICS:
  Publication   - Data sent to HELICS bus
  Subscription  - Data received from HELICS bus
  Endpoint      - Bidirectional message channel

Protection:
  Relay    - Automatic protection device
  Limit    - Threshold for protection activation
  Margin   - Distance from protection threshold
```

---

*Document Version: 2.0*  
*Last Updated: December 2025*  
*Purpose: Comprehensive reference for AI-assisted grid cybersecurity research testbed*
