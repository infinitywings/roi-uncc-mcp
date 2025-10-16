# EV Setpoint MCP - Attack Mode Summary

## ✅ Configuration Complete

Your EV Setpoint MCP server is now configured as an **adversarial attack interface** for AI-driven grid penetration testing on the 2bus-13bus co-simulation.

> Historical references to `mcp-server/` or legacy demo scripts now point to `archive/legacy_demo/`. Use the materials here for the active deployment.

---

## What Was Fixed

### 🔧 Critical Issues Resolved

1. **HELICS Endpoint Conflict** ✅
   - **Problem**: MCP and legitimate controller competing for same endpoints
   - **Solution**: Intentional! Both send to `gld_hlc_conn/EV1-6`; last message wins
   - **Architecture**: Red Team (MCP) vs Blue Team (legitimate controller)

2. **Subscription Key Mismatch** ✅
   - **Problem**: Wrong format `IEEE13bus_fed/gld_hlc_conn/Sa`
   - **Solution**: Corrected to `gld_hlc_conn/Sa` (global keys, no federate prefix)

3. **Attack Limits Too Restrictive** ✅
   - **Problem**: Max 220 kW prevented meaningful attacks
   - **Solution**: Attack mode allows up to 4000 kW (4 MW) per EV

4. **No Attack Classification** ✅
   - **Problem**: No way to identify attack types
   - **Solution**: Added real-time classification (overload, reverse power, reactive power, etc.)

---

## Architecture Overview

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

## Attack Capabilities Enabled

### Observation (Reconnaissance)
- `get_grid_status`: Real-time voltage, power, EV state monitoring
- `discover_topology`: Grid structure and vulnerability mapping
- `monitor_protection_systems`: Feeder limits and protection status
- `analyze_power_flow`: Power flow patterns for attack planning

### Action (Attack Execution)
- `set_ev_capacity`: Inject malicious EV setpoints
  - **Normal**: 200-220 kW (benign operation)
  - **Attack**: Up to 4000 kW (4 MW) per EV
  - **Reverse Power**: Down to -1000 kW (injection attacks)

### Attack Types Auto-Classified
1. `normal` - Within normal operating range
2. `mild_overload` - 10-50% over normal
3. `overload_attack` - >50% over normal (2-4 MW)
4. `reverse_power_injection` - Negative setpoints
5. `reactive_power_attack` - Excessive reactive power

---

## Quick Start

- Spin up the one-container demo and run an AI campaign:
  ```bash
  cd /home/cfu6/roi-uncc-mcp
  docker compose -f ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build
  ```
  This:
  - Builds GridPACK if needed.
  - Launches broker + all five federates (GridLAB-D ×2, EV controller, GridPACK, attacker MCP).
  - Starts `run_ai_campaign.py`, which waits for the server then calls `/api/ai/execute` using the local `openai/gpt-oss-120b` model.
  - Streams logs to `examples/2bus-13bus/logs/`:
    - `attacker.log` – MCP server output.
    - `gld1.log`, `gld2.log`, `controller.log`, `gridpack.log`.
    - `ai_campaign.log` – REST campaign request/response.
    - `llm_interactions.jsonl` – every prompt/response exchanged with the LLM.

### 2. Test Observation Primitive

```bash
curl -s http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"get_grid_status","params":{}}' | jq
```

### 3. Execute Overload Attack

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
```

**Expected Impact**:
- Feeder load exceeds 4.2 MW protection threshold
- Legitimate controller triggers islanding for EV1/EV4
- Battery storage activated
- Grid stress increased

### 4. Monitor Attack Activity

```bash
# Watch MCP logs (attack classification)
docker logs -f ev-setpoint-mcp

# Watch interaction log (AI audit trail)
tail -f ev_setpoint_mcp/output/interaction_log.jsonl | jq

# Watch legitimate controller response
docker logs -f 1c_Controller
```

---

## Documentation

### 📚 Complete Documentation Created

1. **README.md** - Main documentation (updated for attack mode)
   - Architecture overview
   - Attack examples
   - Quick start guide

2. **ATTACK_STRATEGIES.md** - 8 Detailed Attack Strategies
   - Simple Overload Attack
   - Reverse Power Injection
   - Phase Imbalance Attack
   - Timing-Based Attack (peak demand exploitation)
   - Storage Exploitation Attack
   - Reactive Power Attack
   - Rapid Setpoint Fluctuation
   - Coordinated Multi-Stage Campaigns

3. **DEPLOYMENT_ATTACK_MODE.md** - Step-by-Step Deployment
   - Prerequisites and verification
   - Docker vs local deployment
   - Attack execution examples
   - Monitoring and analysis
   - Troubleshooting guide

4. **CHANGES_FOR_ATTACK_MODE.md** - Complete Change Log
   - Configuration changes explained
   - Source code modifications
   - Testing checklist
   - Known limitations

5. **SUMMARY.md** - This File
   - Quick reference
   - What was fixed
   - How to use

---

## Testing Checklist

Before production attack testing:

- [ ] **HELICS Connectivity**
  ```bash
  docker logs ev-setpoint-mcp | grep "federate.*entered execution"
  ```

- [ ] **Subscriptions Working**
  ```bash
  # Should return non-zero voltage/power values
  curl -s http://localhost:5100/primitive \
    -d '{"method":"get_grid_status","params":{}}' | jq .grid_state.voltages
  ```

- [ ] **Benign Setpoint Works**
  ```bash
  # Attack type should be "normal"
  curl -s http://localhost:5100/primitive \
    -d '{"method":"set_ev_capacity","params":{"ev_id":"EV5","real_power_kw":180}}' | \
    jq .attack_type
  ```

- [ ] **Attack Setpoint Works**
  ```bash
  # Attack type should be "overload_attack"
  curl -s http://localhost:5100/primitive \
    -d '{"method":"set_ev_capacity","params":{"ev_id":"EV3","real_power_kw":2500}}' | \
    jq .attack_type
  ```

- [ ] **Competing with Legitimate Controller**
  ```bash
  # Both controllers should be running
  docker ps | grep -E "ev-setpoint-mcp|1c_Controller"
  ```

- [ ] **Attack Logging Active**
  ```bash
  # Should show attack warnings
  docker logs ev-setpoint-mcp | grep "ATTACK INJECTION"
  ```

---

## Attack Impact Metrics

Monitor these to evaluate attack effectiveness:

1. **Feeder Load Threshold**: Load > 4.2 MW (upper) or < 2.6 MW (lower)
2. **Protection Activations**: Count switch operations in controller log
3. **Voltage Deviations**: Voltages outside 0.95-1.05 pu range
4. **Storage Depletion**: Battery discharge during islanding
5. **Recovery Time**: Time to restore normal operation

---

## Known Limitations

1. **Timing Granularity**: 60-second time steps (period=60.0)
2. **Single Feeder**: Only Feeder A confirmed controllable
3. **No Switch Control**: Cannot directly force switch open/close (yet)
4. **No Authentication**: API is open (acceptable for isolated research)
5. **Subscription Verification Needed**: Check that voltage/power values are not all zeros

---

## Next Steps

### Immediate Testing
1. Verify HELICS subscriptions return real data (not zeros)
2. Test benign setpoint → should classify as "normal"
3. Test overload attack → should classify as "overload_attack"
4. Monitor legitimate controller response to attacks

### AI Integration
1. Use observation primitives for grid reconnaissance
2. Implement attack timing based on feeder load monitoring
3. Develop multi-stage attack campaigns
4. Evaluate attack success metrics

### Defense Development
1. Analyze attack logs in `interaction_log.jsonl`
2. Identify attack detection signatures
3. Design defensive countermeasures
4. Test defense effectiveness against AI attacks

---

## Security Reminder

**⚠️ IMPORTANT: This is a defensive research tool**

**Acceptable Use**:
- ✅ Simulated grid testing only
- ✅ Defensive cybersecurity research
- ✅ Vulnerability assessment
- ✅ Defense mechanism development

**Prohibited Use**:
- ❌ Real grid infrastructure
- ❌ Unauthorized testing
- ❌ Malicious attacks

All attacks are logged to `output/interaction_log.jsonl` for audit purposes.

---

## Troubleshooting

### Issue: Subscriptions Return All Zeros

**Check**:
```bash
# Verify GridLAB-D is publishing
docker logs IEEE123bus_fed | grep "publication"
```

**Fix**: Update subscription keys in `config/ev_mcp.yaml` to match actual publications

### Issue: Attacks Have No Effect

**Check**:
```bash
# Verify endpoint destinations
grep "destination" config/ev_mcp.yaml
```

**Fix**: Ensure destinations match `gld_hlc_conn/EV1-6`

### Issue: MCP Won't Connect to HELICS

**Check**:
```bash
# Verify broker is running
docker ps | grep helics-broker
netstat -an | grep 23406
```

**Fix**: Ensure broker address is `tcp://helics-broker:23406` (Docker) or `tcp://localhost:23406` (local)

---

## Support

For issues or questions:
1. Check `DEPLOYMENT_ATTACK_MODE.md` for detailed troubleshooting
2. Review `ATTACK_STRATEGIES.md` for attack examples
3. Examine `CHANGES_FOR_ATTACK_MODE.md` for configuration details
4. Check Docker logs: `docker logs ev-setpoint-mcp`
5. Review interaction log: `tail -f output/interaction_log.jsonl`

---

## Success Criteria

Your attack MCP is working correctly when:

✅ MCP federate connects to HELICS broker
✅ Subscriptions return non-zero voltage/power values
✅ Benign setpoints classified as "normal"
✅ Attack setpoints classified correctly (overload_attack, etc.)
✅ Legitimate controller continues operating (doesn't crash)
✅ Grid responds to injected setpoints
✅ All attacks logged to `interaction_log.jsonl`
✅ Attack warnings appear in MCP server logs

---

**Status**: ✅ Configuration Complete - Ready for Attack Testing

**Next Action**: Deploy MCP server and verify HELICS connectivity
