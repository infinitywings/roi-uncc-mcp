# Configuration Validation - ev_mcp.yaml

## Summary

The `ev_mcp.yaml` configuration has been updated to match the **actual 2bus-13bus grid simulation** running in Docker. All HELICS subscription keys, timing parameters, and topology information now align with the real simulation.

---

## Key Changes Made

### 1. ✅ HELICS Subscriptions - CORRECTED

**Old (Incorrect)**:
```yaml
subscriptions:
  - name: gld_power_Sa
    key: IEEE13bus_fed/gld_hlc_conn/Sa  # ❌ Wrong: federate prefix
  - name: gld_voltage_Va
    key: gld_hlc_conn/Va  # ❌ Wrong: GridLAB-D doesn't publish voltages
```

**New (Correct)**:
```yaml
subscriptions:
  # Feeder load measurements from GridLAB-D (Node650 - swing bus)
  - name: feeder_power_A
    key: gld_hlc_conn/Sa  # ✅ Published by IEEE13bus_fed
  - name: feeder_power_B
    key: gld_hlc_conn/Sb
  - name: feeder_power_C
    key: gld_hlc_conn/Sc

  # Voltage measurements from GridPACK (transmission system)
  - name: transmission_voltage_A
    key: gridpack/Va  # ✅ Published by GridPACK federate
  - name: transmission_voltage_B
    key: gridpack/Vb
  - name: transmission_voltage_C
    key: gridpack/Vc

  # Switch status for EV islanding (published by legitimate controller)
  - name: switch_EV1_storage
    key: swEV1_storage
  - name: switch_EV1
    key: swEV1
  - name: switch_EV4_storage
    key: swEV4_storage
  - name: switch_EV4
    key: swEV4
```

**Why**:
- GridLAB-D **publishes** power measurements at Node650 (swing bus)
- GridLAB-D **subscribes** to voltages from GridPACK
- GridPACK **publishes** transmission voltages
- Switch subscriptions added to monitor legitimate controller's islanding actions

---

### 2. ✅ Timing Parameters - VALIDATED

```yaml
time_delta: 60.0  # Match GridLAB-D period (60s)
period: 60.0      # Same as GridLAB-D federate
poll_interval: 0.5  # Fast polling for attack responsiveness
```

**Validation**:
- ✅ GridLAB-D period = 60s (from mainglm.json line 6)
- ✅ Legitimate controller update_interval = 1200s (20 min, but total_interval=10 for short test)
- ✅ MCP poll_interval = 0.5s for responsive attack timing

---

### 3. ✅ Topology Information - ENHANCED

Added comprehensive topology metadata:

```yaml
observation:
  topology:
    transmission:
      model: IEEE 9-bus (GridPACK)
      federate_name: gridpack
      tie_buses: [bus2, bus3]
      voltage_publications: [gridpack/Va, gridpack/Vb, gridpack/Vc]

    distribution:
      feeders:
        - id: feeder_A
          federate_name: IEEE13bus_fed
          model: IEEE_123 (GridLAB-D)
          swing_node: Node650
          ev_stations:
            - {id: EV1, node: l5, phase: CN, storage: true, ...}
            - {id: EV2, node: l2, phase: BN, storage: false, ...}
            # ... all 6 EVs documented
          controller:
            name: 1bc_EV_Controller.py
            update_interval_s: 1200
            peak_hours: [15, 16, 17]
```

**Purpose**:
- AI attackers can query topology via `discover_topology` primitive
- Accurate EV station metadata (phase, storage, normal vs attack limits)
- Controller behavior documented for attack planning

---

### 4. ✅ EV Endpoints - CONFIRMED CORRECT

```yaml
ev_endpoints:
  - name: EV1
    key: attacker/EV1
    destination: gld_hlc_conn/EV1  # ✅ Same as legitimate controller
    phases: CN
    max_power_kw: 4000
```

**Validation against mainglm.json**:
- ✅ EV1: phase CN, constant_power_C (line 195-200)
- ✅ EV2: phase BN, constant_power_B (line 175-187)
- ✅ EV3: phase AN, constant_power_A (line 160-172)
- ✅ EV4: phase CN, constant_power_C (line 145-157)
- ✅ EV5: phase BN, constant_power_B (line 130-142)
- ✅ EV6: phase AN, constant_power_A (line 115-127)

**Attack Mechanism**:
- Both attacker MCP and legitimate controller send to **same destinations**
- HELICS delivers messages chronologically → **last message wins**
- Attacker can override controller setpoints by sending more frequently

---

## Validation Checklist

### ✅ HELICS Key Mapping

| Data Type | Source Federate | Publication Key | MCP Subscription | Type |
|-----------|----------------|-----------------|------------------|------|
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

### ✅ EV Endpoint Validation

| EV ID | Phase | GridLAB-D Property | HELICS Destination | Attacker Key | Has Storage |
|-------|-------|-------------------|-------------------|--------------|-------------|
| EV1 | CN | constant_power_C | gld_hlc_conn/EV1 | attacker/EV1 | ✅ Yes |
| EV2 | BN | constant_power_B | gld_hlc_conn/EV2 | attacker/EV2 | ❌ No |
| EV3 | AN | constant_power_A | gld_hlc_conn/EV3 | attacker/EV3 | ❌ No |
| EV4 | CN | constant_power_C | gld_hlc_conn/EV4 | attacker/EV4 | ✅ Yes |
| EV5 | BN | constant_power_B | gld_hlc_conn/EV5 | attacker/EV5 | ❌ No |
| EV6 | AN | constant_power_A | gld_hlc_conn/EV6 | attacker/EV6 | ❌ No |

### ✅ Timing Alignment

| Parameter | Value | Source | Purpose |
|-----------|-------|--------|---------|
| GridLAB-D period | 60s | mainglm.json:6 | Power flow timestep |
| MCP time_delta | 60s | ev_mcp.yaml | Match GridLAB-D |
| MCP period | 60s | ev_mcp.yaml | HELICS sync interval |
| Controller update | 1200s | 1bc_EV_Controller.py:60 | Legitimate control updates |
| MCP poll_interval | 0.5s | ev_mcp.yaml | Attack responsiveness |

---

## Testing the Configuration

### Test 1: Verify Subscriptions Receive Data

```bash
# Start simulation and MCP server
docker-compose -f docker/docker-compose.demo.yml up -d
docker-compose -f ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up -d

# Query grid status
curl -s http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"get_grid_status","params":{}}' | jq

# Expected: Non-zero values for:
# - grid_state.voltages.Node650_phaseA (from transmission_voltage_A)
# - grid_state.powers.Node650_phaseA (from feeder_power_A)
```

**Success Criteria**:
- ✅ Voltage magnitudes ~2400 V (not 0)
- ✅ Power values non-zero (feeder load)
- ✅ EV setpoints show attacker values (if injected)

### Test 2: Verify Topology Discovery

```bash
curl -s http://localhost:5100/primitive \
  -H "Content-Type: application/json" \
  -d '{"method":"discover_topology","params":{}}' | jq

# Expected: Full topology with 6 EV stations, phases, storage info
```

### Test 3: Verify Attack Endpoint Works

```bash
# Inject benign setpoint
curl -s http://localhost:5100/primitive \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV5","real_power_kw":180}}' | jq

# Expected:
# - status: "accepted"
# - attack_type: "normal"
# - phase: "BN"

# Check GridLAB-D log for message delivery
docker exec IEEE13bus_fed tail -f IEEE13bus-gld.log | grep "EV5"
```

---

## Common Issues and Fixes

### Issue 1: Subscriptions Return All Zeros

**Symptom**: `get_grid_status` returns 0 for all voltages/powers

**Diagnosis**:
```bash
# Check HELICS broker for actual publication keys
docker logs helics-broker | grep "registering publication"
```

**Fix**: Update subscription keys in `ev_mcp.yaml` to match actual publications

---

### Issue 2: Attacker Setpoints Ignored

**Symptom**: EV setpoints don't change in GridLAB-D

**Diagnosis**:
```bash
# Check if attacker endpoint is sending
docker logs ev-setpoint-mcp | grep "Dispatching EV capacity"

# Check if GridLAB-D is receiving
docker logs IEEE13bus_fed | grep "endpoint"
```

**Fix**: Verify `destination` in ev_endpoints matches GridLAB-D endpoint keys

---

### Issue 3: Timing Misalignment

**Symptom**: MCP federate can't sync with simulation

**Diagnosis**:
```bash
# Check HELICS time requests
docker logs ev-setpoint-mcp | grep "RequestTime"
```

**Fix**: Ensure `time_delta` and `period` match GridLAB-D configuration

---

## Summary of Corrections

| Configuration Item | Before | After | Status |
|-------------------|---------|--------|--------|
| Power subscriptions | ❌ Wrong keys | ✅ gld_hlc_conn/Sa,Sb,Sc | FIXED |
| Voltage subscriptions | ❌ From GridLAB-D | ✅ From GridPACK | FIXED |
| Subscription names | ❌ Generic | ✅ Descriptive | IMPROVED |
| Switch monitoring | ❌ Missing | ✅ Added 4 switches | ADDED |
| Timing | ❌ Generic | ✅ Validated against actual | FIXED |
| Topology metadata | ❌ Basic | ✅ Comprehensive | ENHANCED |
| EV phase info | ❌ Generic | ✅ From mainglm.json | VALIDATED |

---

## Configuration Files Reference

- **ev_mcp.yaml**: Main MCP configuration (THIS FILE UPDATED)
- **mainglm.json**: GridLAB-D HELICS configuration (SOURCE OF TRUTH)
- **1c_Control.json**: Legitimate controller config (COMPETITOR)
- **gpk-gld-cosim.json**: HELICS federation runner
- **1bc_EV_Controller.py**: Legitimate controller code (timing reference)

---

**Status**: ✅ Configuration validated and consistent with 2bus-13bus simulation

**Last Updated**: 2025-01-07

**Validated Against**:
- examples/2bus-13bus/mainglm.json (GridLAB-D config)
- examples/2bus-13bus/1c_Control.json (Controller config)
- examples/2bus-13bus/1bc_EV_Controller.py (Controller code)
- examples/2bus-13bus/README.md (System documentation)
