# Deployment Guide: Attack Mode Operation

## Quick Start for AI-Driven Grid Attacks

This guide explains how to deploy the EV Setpoint MCP server as an adversarial interface for AI attackers while maintaining normal grid operation.

> **Note:** The original multi-container MCP server implementation has been archived under `archive/legacy_demo/`. References to `mcp-server/...` in this document now point to those legacy materials.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Environment                         │
│                                                               │
│  ┌───────────┐    ┌──────────────┐    ┌─────────────────┐  │
│  │  HELICS   │◄───┤   GridLAB-D  │◄───┤   GridPACK      │  │
│  │  Broker   │    │  (IEEE 123)  │    │   (IEEE 9-bus)  │  │
│  └─────▲─────┘    └──────▲───────┘    └─────────────────┘  │
│        │                 │                                    │
│        │         ┌───────┴────────┐                          │
│        │         │                 │                          │
│  ┌─────┴─────────┴────┐   ┌────────▼───────────┐            │
│  │ EV Controller       │   │ EV Attacker MCP    │            │
│  │ (Blue Team/Legit)   │   │ (Red Team/AI)      │            │
│  │ - Peak shaving      │   │ - Attack injection │            │
│  │ - Islanding control │   │ - Overload         │            │
│  └─────────────────────┘   └────────▲───────────┘            │
│                                      │                        │
└──────────────────────────────────────┼────────────────────────┘
                                       │
                            ┌──────────▼──────────┐
                            │   AI Attacker       │
                            │   (External/Host)   │
                            │   - Strategic       │
                            │   - Observes        │
                            │   - Attacks         │
                            └─────────────────────┘
```

---

## Prerequisites

- Docker Engine 20.10+ with Compose V2
- `roi-img:latest` base image built (contains HELICS, GridLAB-D, GridPACK)
- Repository checked out with `examples/2bus-13bus` available (submodule)

> The new `grid-attack-demo` compose service automatically builds the GridPACK federate (`cmake .. && make`) if the executable is missing, so no manual compilation steps are required.

---

## Step-by-Step Deployment

### Step 1: Launch the One-Container Demo

```bash
cd /home/cfu6/roi-uncc-mcp
docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build
```

- Builds the attacker image (extends `roi-img`) and mounts the simulation/attacker directories.
- Executes `run_grid_attack_demo.sh`, which:
  - compiles `build/gpk-left-fed.x` as needed,
  - launches broker + GridLAB-D ×2 + EV controller + GridPACK + EV attacker MCP,
  - triggers an AI-driven campaign that queries the local `openai/gpt-oss-120b` endpoint, then posts malicious setpoints via the `primitive` API.
- Keeps the Flask API available on `http://localhost:5100/` for manual testing.

Environment overrides before `docker compose up`:

| Variable | Default | Description |
| --- | --- | --- |
| `RUN_AI_CAMPAIGN` | `1` | Set to `0` to skip the automatic AI campaign |
| `AI_CAMPAIGN_STEPS` | `3` | Number of LLM-driven attack iterations |
| `AI_CAMPAIGN_INTERVAL` | `30` | Seconds to wait between iterations |
| `AI_CAMPAIGN_WAIT` | `60` | Readiness wait window in seconds |
| `LLM_API_BASE` | `http://ccil1s26m8hj6lws:8000/v1` | OpenAI-compatible endpoint used by the campaign |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Model identifier requested from the LLM service |

Use `-d` for detached mode, then follow with `docker compose ... logs -f` to stream output.

### Step 2: Confirm Startup

`docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml logs grid-attack-demo` should include:
- `HELICS federate ev_attacker_mcp entered execution mode`
- `Running on http://127.0.0.1:5100`

### Step 3: Inspect Telemetry & Logs

```bash
curl -s http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"get_grid_status","params":{}}' | jq
```

Log artefacts (under `examples/2bus-13bus/logs/`):

- `attacker.log` – MCP server / Flask output
- `gld1.log`, `gld2.log`, `controller.log`, `gridpack.log`
- `ai_campaign.log` – REST request/response trace for the automatic AI campaign
- `llm_interactions.jsonl` – LLM prompts/responses captured by `LocalLLMStrategist`

### Step 4: Inject a Benign Setpoint

```bash
curl -s http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{
    "method": "set_ev_capacity",
    "params": {
      "ev_id": "EV5",
      "real_power_kw": 180,
      "reactive_power_kvar": 0
    }
  }' | jq
```

The response should show `"attack_type": "normal"`, confirming that the safety checks still allow baseline operation.

### Step 6: Monitor Attack Logs

```bash
# Terminal 1: Follow container output (all services)
docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml logs -f grid-attack-demo

# Terminal 2: Follow LLM interaction log
tail -f examples/2bus-13bus/logs/llm_interactions.jsonl | jq

# Terminal 3: Watch legitimate controller logs
tail -f examples/2bus-13bus/logs/controller.log
```

---

## Attack Execution Examples

### Example 1: Simple Overload Attack

```bash
# Inject 2.5 MW on EV3 to stress grid
curl -s http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{
    "method": "set_ev_capacity",
    "params": {
      "ev_id": "EV3",
      "real_power_kw": 2500,
      "reactive_power_kvar": 0
    }
  }' | jq

# Observe:
# - MCP log: "ATTACK INJECTION: MALICIOUS | Type=overload_attack"
# - Controller log: May trigger islanding if total load > 4.2 MW
```

### Example 2: AI-Driven Attack Campaign

```python
#!/usr/bin/env python3
"""Simple AI attacker that monitors and attacks the grid."""

import requests
import time
import random

API = "http://localhost:5100/primitive"

def observe_grid():
    """Get current grid state."""
    resp = requests.post(API, json={"method": "get_grid_status", "params": {}})
    return resp.json()

def attack_ev(ev_id, power_kw):
    """Inject malicious setpoint."""
    resp = requests.post(API, json={
        "method": "set_ev_capacity",
        "params": {
            "ev_id": ev_id,
            "real_power_kw": power_kw,
            "reactive_power_kvar": 0
        }
    })
    return resp.json()

def calculate_total_load(grid_state):
    """Calculate total feeder load from three phases."""
    powers = grid_state.get("grid_state", {}).get("powers", {})
    total = 0
    for phase in ["gld_power_Sa", "gld_power_Sb", "gld_power_Sc"]:
        if phase in powers:
            total += powers[phase].get("real_kw", 0)
    return total

def main():
    """Simple AI attack logic."""
    print("AI Attacker initialized...")

    for iteration in range(100):  # Run for 100 cycles
        print(f"\n--- Iteration {iteration} ---")

        # Observe
        grid = observe_grid()
        total_load = calculate_total_load(grid)
        print(f"Current feeder load: {total_load:.1f} kW")

        # Decide: If load < 3000 kW, inject overload attack
        if total_load < 3000:
            target_ev = random.choice(["EV3", "EV5", "EV6"])
            attack_power = random.randint(2000, 3500)

            print(f"ATTACKING: {target_ev} with {attack_power} kW")
            result = attack_ev(target_ev, attack_power)
            print(f"Attack result: {result.get('status')} - {result.get('attack_type')}")

        # Wait before next cycle
        time.sleep(30)

if __name__ == "__main__":
    main()
```

Save as `simple_ai_attacker.py` and run:
```bash
python simple_ai_attacker.py
```

---

## Monitoring and Analysis

### Real-Time Monitoring

```bash
# Watch all attack activity
watch -n 5 'curl -s http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d "{\"method\":\"get_grid_status\",\"params\":{}}" | \
  jq ".grid_state.powers"'
```

### Attack Log Analysis

```bash
# Count attack types
jq -r '.attack_type' archive/ev_setpoint_mcp/output/interaction_log.jsonl | sort | uniq -c

# Find overload attacks
jq 'select(.attack_type == "overload_attack")' \
  archive/ev_setpoint_mcp/output/interaction_log.jsonl

# Calculate attack success rate
# (attacks that triggered protection / total attacks)
```

### Grid Impact Assessment

1. **Feeder Load Violations**: Count how many times load > 4.2 MW
2. **Voltage Deviations**: Track voltage outside 0.95-1.05 pu range
3. **Protection Activations**: Count switch operations in controller log
4. **Storage Depletion**: Monitor EV1/EV4 storage discharge rates

---

## Troubleshooting

> **Note:** The commands below were originally written for the multi-container deployment. When using the `grid-attack-demo` compose service, replace container names such as `grid-simulation` or `ev-setpoint-mcp` with `grid-attack-demo` and inspect logs via `docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml logs -f`.

### Issue: MCP Server Can't Connect to HELICS

**Symptom**: Server logs show "Failed to connect to broker"

**Solution**:
```bash
# Check broker is running
docker ps | grep helics-broker

# Check broker is on correct port
docker logs helics-broker | grep "listening on port"

# Verify network connectivity
docker network inspect grid-network | grep ev-setpoint-mcp
```

### Issue: Attack Setpoints Have No Effect

**Symptom**: Setpoints accepted but no grid impact observed

**Possible Causes**:
1. **HELICS endpoint mismatch**: Check that destinations match GridLAB-D endpoints
2. **Message timing**: Legitimate controller may be sending more frequently
3. **Simulation time scaling**: Check `time_delta` and `period` in config

**Debug**:
```bash
# Check HELICS message delivery
docker exec -it ev-setpoint-mcp helics_app query --target ev_attacker_mcp subscriptions

# Verify endpoint destinations
docker exec -it ev-setpoint-mcp helics_app query --target ev_attacker_mcp endpoints
```

### Issue: Subscription Values are All Zeros

**Symptom**: `get_grid_status` returns zero for all measurements

**Solution**:
```bash
# Check GridLAB-D is publishing to correct keys
docker logs IEEE123bus_fed | grep "publication"

# Update config/ev_mcp.yaml subscription keys to match
# Common fix: Remove federate prefix from keys
# Wrong: IEEE13bus_fed/gld_hlc_conn/Sa
# Right: gld_hlc_conn/Sa
```

---

## Cleanup and Shutdown

```bash
# Stop attack MCP server
docker-compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml down

# Stop entire simulation
docker-compose -f docker/docker-compose.demo.yml down

# Clean up logs and outputs
rm -rf archive/ev_setpoint_mcp/output/*.jsonl
```

---

## Security Considerations

**IMPORTANT**: This is a red team / penetration testing tool:

1. **Network Isolation**: Ensure Docker environment is NOT connected to real grids
2. **Audit Logging**: All attacks logged to `interaction_log.jsonl`
3. **Ethical Use**: Only for defensive research and security improvement
4. **Responsible Disclosure**: Report findings to grid operators

---

## Next Steps

After successful deployment:

1. **Test attack strategies** from `ATTACK_STRATEGIES.md`
2. **Develop AI attack algorithms** using observation primitives
3. **Measure attack effectiveness** with metrics
4. **Design defensive countermeasures** based on findings
5. **Document vulnerabilities discovered** for grid operators

---

For advanced AI integration, see the main MCP server documentation at `/mcp-server/docs/MCP_PRIMITIVES.md`.
