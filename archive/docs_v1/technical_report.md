# Technical Report: AI-Assisted Red Teaming for Power Grid Co-Simulation

---

## 1. Motivation

The proliferation of networked Distributed Energy Resources (DERs)—particularly Electric Vehicle (EV) charging infrastructure—introduces new cyber-physical attack surfaces into distribution grids. While EV chargers provide grid flexibility through controllable active and reactive power setpoints, the same control interfaces that enable demand response can be exploited by adversaries to induce localized overloads, trigger protection systems, or destabilize feeder operations.

Existing research on grid cybersecurity predominantly employs either (i) abstract threat models without realistic physical validation, or (ii) proprietary testbeds that preclude reproducibility. Furthermore, the emerging capability of Large Language Models (LLMs) to act as autonomous agents—planning multi-step actions based on observations and tool use—has not been systematically evaluated in the context of power system attacks. This gap leaves grid operators without empirical understanding of how an intelligent, adaptive adversary might coordinate DER manipulations under realistic operational constraints.

This project addresses these gaps by constructing a transparent, containerized research sandbox that couples high-fidelity transmission–distribution co-simulation with an LLM-driven attack orchestration layer. The framework enables rigorous study of how AI agents can discover, time, and execute coordinated EV setpoint attacks, and how defensive controls and physical protection mechanisms respond under realistic rate limits and partial observability.

---

## 2. Problem Scope

### 2.1 System Boundary

The testbed comprises a coupled transmission–distribution power system model:

- **Transmission Layer:** IEEE 9-bus system simulated via GridPACK, representing bulk power generation and high-voltage interconnections.
- **Distribution Layer:** Two IEEE 123-node radial feeders simulated via GridLAB-D, each connected to the transmission network via step-down transformers at designated tie buses.
- **EV Infrastructure:** Six EV charging stations distributed across the primary feeder (three phases: A, B, C), with two stations (EV1, EV4) equipped with behind-the-meter battery storage and islanding switches.

### 2.2 Adversary Model

The attacker operates under the following constraints, reflecting realistic cyber-intrusion scenarios:

- **Access:** Read/write capability to EV setpoint endpoints (active and reactive power) via a compromised or malicious Model Context Protocol (MCP) interface; no direct access to breakers, topology reconfiguration, or protection relay settings.
- **Observability:** Partial telemetry including aggregate feeder power, individual EV setpoints, and switch states; no access to internal transmission-level state or protection thresholds.
- **Rate Limits:** Configurable cooldown periods (e.g., one attack attempt per 30 simulated minutes) and time-phased magnitude caps (e.g., 0.4 MW early, 2.5 MW late) to emulate detection-avoidance behavior and realistic intrusion pacing.

### 2.3 Defensive Elements

- **Feeder Controller:** A Python HELICS federate that samples aggregate feeder load at regular intervals (configurable from 1 to 20 minutes) and enforces real-power thresholds (lower: ~2.6 MW, upper: ~4.5 MW). Upon overload detection, the controller sheds EV loads and/or triggers islanding of storage-equipped stations.
- **Physical Constraints:** Inherent line/transformer thermal ratings, voltage limits, and power-flow solver stability (GridLAB-D Newton–Raphson convergence) provide implicit protection that must be navigated by both attacker and defender.

### 2.4 Research Questions

1. How effectively can an LLM-based agent, operating under partial observability and rate constraints, discover and exploit timing/phase/asset combinations to exceed feeder limits?
2. How do controller thresholds, attack magnitude caps, and cooldown intervals influence both attack impact and simulation stability?
3. What observable indicators (controller actions, line overload warnings, voltage deviations) best reveal attack presence and progression?

---

## 3. Technical Challenges

### 3.1 Nonlinear Multi-Domain Coupling

The testbed exhibits strong coupling between transmission voltages, distribution power flows, and localized EV injections. Even modest setpoint perturbations can propagate nonlinearly, causing:

- Voltage deviations at the transmission tie point
- Thermal overloads on distribution lines and transformers
- Power-flow solver divergence when operating near equipment limits

This coupling complicates both attack design (actions may have unintended global consequences) and evaluation (distinguishing intended impact from numerical artifacts).

### 3.2 Temporal Orchestration

Effective experimentation requires careful alignment of multiple time scales:

- **HELICS Co-Simulation Time:** Discrete time steps (configurable period and delta) govern message delivery and state synchronization across federates.
- **Controller Cadence:** The defensive controller samples and acts at a separate, potentially misaligned interval.
- **Attacker Pacing:** Rate limits and cooldowns must be enforced in simulated time, not wall-clock time, to reflect realistic adversary behavior.

Misalignment can cause attacks to "miss" controller observation windows, or conversely, trigger protection before the attack fully manifests.

### 3.3 Constrained Attacker Realism

Real-world intrusions face operational constraints: limited intrusion bandwidth, detection risk, and incomplete system knowledge. Emulating these conditions requires:

- Time-phased power caps (aggressive early attacks crash the solver before defenders react; overly gentle attacks produce no observable impact)
- History-aware prompting (the LLM must learn from prior action outcomes to improve targeting)
- Partial telemetry (the agent cannot directly observe protection thresholds or transmission-level state)

### 3.4 Measurement and Attribution

Rigorous evaluation demands:

- Coordinated logging of simulation time, observations, LLM decisions, executed/blocked actions, controller branches, and physical warnings
- Clear separation of intended overloads from numerical instability (solver crashes should not be scored as "successful" attacks unless they reflect genuine physical consequences)
- Reproducibility via containerization and fixed random seeds where applicable

---

## 4. Main Scientific Contributions

### 4.1 Constrained AI Attack Planner

We introduce a history- and cooldown-aware LLM orchestration loop that:

- Constructs prompts from current telemetry, recent action history (last 5 actions with outcomes), and remaining attack budget (next allowed simulation time)
- Requests structured JSON action outputs specifying target EV, active power (kW), and reactive power (kVAR)
- Clamps proposed actions to time-phased magnitude limits (0.4 MW in first 30 min, 1.2 MW through 2 h, 2.5 MW thereafter) before HELICS delivery
- Enforces simulation-time cooldowns, skipping execution if the quota is exhausted

This design enables study of planning under constraints—mirroring real intrusion dynamics where adversaries must pace actions to avoid detection.

### 4.2 Reusable EV MCP Federate

The EV Setpoint MCP Server provides a modular, containerized attack/defense interface:

- **Observation Primitives:** `get_grid_status` (feeder power, EV setpoints, switch states), `discover_topology`, `monitor_protection_systems`, `analyze_power_flow`
- **Action Primitive:** `set_ev_capacity` (per-EV active/reactive power setpoints with configurable attack bounds ±4 MW)
- **HELICS Integration:** Combination federate with subscriptions (voltages, powers) and endpoints (EV setpoints) enabling synchronized co-simulation participation
- **Audit Logging:** JSON-lines interaction log capturing every request, response, latency, and execution status for post-hoc analysis

The modular design allows reuse across grid models and attack/defense research beyond the immediate EV overload scenario.

### 4.3 Integrated Overload/Islanding Harness

The co-simulation workflow integrates:

- GridPACK 9-bus transmission federate publishing tie-line voltages
- Two GridLAB-D IEEE 123-node feeders subscribing to transmission voltages and publishing feeder demand
- Python-based EV controller enforcing tunable real-power limits and managing islanding for storage-equipped stations
- Competing attacker MCP federate sending setpoints to the same HELICS endpoints (last message wins)

This configuration enables systematic exploration of overload thresholds, controller reaction times, and islanding effectiveness under adversarial conditions.

### 4.4 Evaluation Protocol Under Constraints

We define a rigorous experimental protocol comprising:

- **Three Baselines:** (a) No attack, (b) Random attacks obeying identical caps/cooldowns, (c) AI-driven attacks with history/cooldown awareness
- **Controlled Variables:** Feeder limits, attack caps, cooldown intervals, EV load schedules, controller sampling interval
- **Metrics:** Overload count/duration, peak feeder power, controller branch activations, solver stability, attack efficiency (impact per attempt under quota), phase imbalance indices
- **Reproducibility:** Containerized deployment via Docker Compose; fixed seeds; logged simulation parameters

---

## 5. Methodology / System Design

### 5.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI Strategy Layer (LLM)                      │
│   Constructs prompts, parses JSON actions, enforces cooldowns   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│               EV Setpoint MCP Container (Attacker)              │
│  Flask REST API │ HELICS Federate │ Observation/Action Services │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      HELICS Federation                          │
│  GridLAB-D Feeder A │ GridLAB-D Feeder B │ GridPACK Transmission│
│                     │ EV Controller (Blue Team)                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Physical Models & Logs (examples/2bus-13bus)       │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Co-Simulation Plant Model

- **Transmission (GridPACK):** Publishes complex voltages `gridpack/Va,Vb,Vc` at tie buses; subscribes to aggregated feeder demand `gld_hlc_conn/Sa,Sb,Sc`.
- **Distribution (GridLAB-D):** IEEE 123-node feeders with EV chargers as controllable loads; swing bus at Node650 connected to transmission.
- **EV Assets:** Six stations across three phases (A: EV3/EV6, B: EV2/EV5, C: EV1/EV4); EV1 and EV4 include battery storage with islanding switches.

### 5.3 Blue-Team Controller Logic

The defensive controller executes a state-machine control law:

1. **Overload (P ≥ upper limit):** Disconnect all EVs from grid; optionally island storage-equipped stations.
2. **Safe Range (lower < P < upper):** Maintain nominal EV operation (EV1, EV2 active; others off or reduced).
3. **Low Load (P ≤ lower limit):** Enable all EVs at full capacity.

Controller sampling interval and thresholds are configurable, enabling study of reaction-time effects.

### 5.4 Red-Team MCP Attack Interface

The attacker MCP provides:

- **Telemetry Access:** Real-time feeder power, EV setpoints, switch states via `get_grid_status`.
- **Attack Execution:** Per-EV setpoint injection via `set_ev_capacity` (active: −500 to +4000 kW; reactive: configurable).
- **HELICS Message Delivery:** Setpoints sent to `gld_hlc_conn/EV1-6` endpoints; chronologically later messages override controller commands.

### 5.5 AI Campaign Loop

The AI orchestration layer implements:

1. **Observation:** Fetch grid telemetry from MCP.
2. **Prompt Construction:** Include current state, recent action history (last 5 with outcomes), cooldown quota, and schema hint for structured JSON output.
3. **LLM Inference:** Query OpenAI-compatible endpoint (e.g., `gpt-oss-120b`) with configurable temperature and max tokens.
4. **Response Parsing:** Extract JSON actions; fall back to regex extraction if raw JSON fails.
5. **Action Clamping:** Apply time-phased magnitude caps before execution.
6. **Rate Limiting:** Skip execution if within cooldown window; log rate-limited events.
7. **Execution:** Send clamped actions to MCP; record outcomes.
8. **Loop:** Repeat at configurable wall-clock interval until simulation duration exhausted.

### 5.6 Logging and Observability

All components emit structured logs:

- **AI Campaign Log:** Observations, LLM decisions, clamped actions, execution results, rate-limit events.
- **LLM Interaction Log:** Full request/response payloads, latencies, interaction IDs for traceability.
- **Controller Log:** Feeder load samples, branch activations (overload/safe/low-load), switch commands.
- **Feeder Logs (GridLAB-D):** Line/transformer overload warnings, voltage violations, solver status.

Logs are keyed by simulation time, enabling post-hoc alignment and causality analysis.

---

## 6. Experimental Design

### 6.1 Baselines

| Condition | Description |
|-----------|-------------|
| **B0: No Attack** | AI campaign disabled (`RUN_AI_CAMPAIGN=0`); only controller and scheduled EV profiles operate. |
| **B1: Random Attack** | Attacker issues uniformly random EV setpoints (within same caps/cooldowns) without LLM reasoning. |
| **B2: AI Attack** | Full LLM-driven campaign with history/cooldown awareness and time-phased caps. |

### 6.2 Controlled Variables

| Variable | Range/Options |
|----------|---------------|
| Feeder Upper Limit | 4.0, 4.2, 4.5 MW |
| Feeder Lower Limit | 2.6 MW (fixed) |
| Attack Cap (early/mid/late) | 0.4/1.2/2.5 MW |
| Cooldown Interval | 15, 30, 60 sim-minutes |
| Controller Sampling Interval | 1, 5, 20 minutes |
| EV Load Schedules | Baseline (tens kW), Peak (hundreds kW) |
| Simulation Duration | 24 hours simulated time |

### 6.3 Metrics

| Metric | Definition |
|--------|------------|
| **Overload Count** | Number of intervals where P ≥ upper limit |
| **Overload Duration** | Cumulative simulated time above upper limit |
| **Peak Feeder Power** | Maximum observed P during run |
| **Controller Activations** | Count of overload/safe/low-load branch executions |
| **Solver Stability** | Binary: did simulation complete without convergence failure? |
| **Attack Efficiency** | (Overload Count) / (Attack Attempts) under rate quota |
| **Phase Imbalance Index** | Max |P_phase - P_avg| / P_avg across phases |

### 6.4 Procedure

1. Initialize co-simulation stack with specified parameters.
2. Launch AI campaign (or random/no-attack baseline).
3. Run for 24 h simulated time or until solver failure.
4. Collect logs: AI campaign, LLM interactions, controller, feeder.
5. Parse logs to extract metrics; annotate with simulation time.
6. Repeat for each baseline and parameter combination (minimum 3 replicates for variance estimation).

### 6.5 Expected Outcomes

- **AI vs. Random:** The constrained AI should achieve higher overload counts and durations per attempt by timing multi-EV actions near natural load peaks, exploiting phase imbalance, and learning from prior outcomes.
- **Stability Trade-offs:** Aggressive caps increase impact but risk solver divergence; conservative caps maintain stability but reduce observable impact. The optimal trade-off will be characterized.
- **Defender Insights:** Controller logs and feeder warnings should reveal detection signatures (e.g., sudden load jumps, repeated overload triggers) that could inform automated mitigation strategies.
- **Reproducibility:** Containerized deployment and logged parameters enable independent replication and extension.

---

## 7. Discussion and Future Work

### 7.1 Limitations

- The current adversary model assumes compromised DER endpoints; alternative attack vectors (e.g., false data injection at sensors) are not modeled.
- GridLAB-D's Newton–Raphson solver may diverge under extreme perturbations, conflating attack success with numerical instability.
- LLM behavior is stochastic; results require aggregation across multiple runs.

### 7.2 Extensions

- **Partial Topology Prompts:** Withhold or noise EV/phase information to study learning under uncertainty.
- **Adaptive Defense:** Implement automated anomaly detection and mitigation in the controller.
- **Multi-Agent Scenarios:** Introduce competing attackers or defender agents for game-theoretic analysis.
- **Transfer to Real-Time Simulators:** Port scenarios to OPAL-RT or RTDS for hardware-in-the-loop validation.

---

## 8. References

- IEEE Test Feeder Working Group. *IEEE 123 Node Test Feeder.* 2010.
- HELICS Team. *HELICS: Hierarchical Engine for Large-scale Infrastructure Co-Simulation.* 2018.
- GridLAB-D Team. *GridLAB-D: An Open-Source Simulation and Analysis Tool for Distribution Systems.* 2007.
- GridPACK Team. *GridPACK: A Framework for Developing Parallel Routines for Power Grid Simulation.* 2016.

---

*Document Version: 2.0*  
*Last Updated: December 2025*  
*Purpose: Technical foundation for academic publication on AI-assisted grid cybersecurity research.*
