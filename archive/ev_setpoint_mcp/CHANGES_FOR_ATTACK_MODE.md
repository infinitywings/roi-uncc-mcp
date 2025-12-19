# Changes Made for Attack Mode Operation

## Summary

The EV Setpoint MCP server has been reconfigured from a normal operation mode to an **adversarial attack interface** that enables AI-driven penetration testing on the 2bus-13bus grid co-simulation.

**Date**: 2025-01-07
**Purpose**: Enable red team attacks while blue team (legitimate controller) continues operation

> Legacy assets referenced in this changelog (e.g., `mcp-server/…`, `run_demo.sh`) now live under `archive/legacy_demo/`. This implementation is archived under `archive/ev_setpoint_mcp/`.

---

## Configuration Changes

### 1. `config/ev_mcp.yaml` - Main Configuration

#### HELICS Configuration
**Before**:
```yaml
federate_name: ev_setpoint_mcp
time_delta: 1.0
period: 1.0
poll_interval: 1.0
```

**After**:
```yaml
federate_name: ev_attacker_mcp  # Renamed to reflect adversarial role
time_delta: 60.0  # Match controller timing
period: 60.0
poll_interval: 0.5  # Faster polling for responsive attacks
```

**Reason**: Renamed federate to clearly identify as attacker. Adjusted timing to coordinate with legitimate controller updates (20 min intervals = 1200s scaled).

#### Subscription Keys
**Before**:
```yaml
subscriptions:
  - name: gld_power_Sa
    key: IEEE13bus_fed/gld_hlc_conn/Sa  # ❌ Wrong: federate prefix
```

**After**:
```yaml
subscriptions:
  - name: gld_power_Sa
    key: gld_hlc_conn/Sa  # ✅ Correct: global key
```

**Reason**: HELICS global publications don't use federate prefixes. Fixed to match actual GridLAB-D publication keys.

#### EV Endpoints
**Before**:
```yaml
ev_endpoints:
  - name: EV1
    key: ev_setpoint/EV1
    destination: gld_hlc_conn/EV1
    phases: CN
```

**After**:
```yaml
ev_endpoints:
  - name: EV1
    key: attacker/EV1  # Renamed for clarity
    destination: gld_hlc_conn/EV1  # Same destination as legitimate controller
    phases: CN
    max_power_kw: 4000  # Added attack limit
```

**Reason**: Attack endpoints send to SAME destinations as legitimate controller, creating competing messages. Added metadata for attack validation.

#### Setpoint Constraints
**Before**:
```yaml
setpoint_constraints:
  default_max_kw: 200
  default_min_kw: 0
  ev_limits:
    EV1:
      max_kw: 220
      min_kw: 0
```

**After**:
```yaml
setpoint_constraints:
  default_max_kw: 4000  # Abnormal attack target
  default_min_kw: -1000  # Allow reverse power injection
  attack_mode: true  # Enable attack validation mode

  ev_limits:
    EV1:
      normal_max_kw: 220  # Legitimate operation
      attack_max_kw: 4000  # Overload attack
      min_kw: -500  # Reverse power injection
      phases: CN
      has_storage: true  # Attack surface metadata
```

**Reason**: Enable extreme setpoints (2-4 MW) for grid stress testing. Separate normal vs attack limits. Add phase and storage metadata for attack planning.

---

## Source Code Changes

### 2. `src/action_service.py` - Attack Validation Logic

#### Added Attack Classification
**New Functionality**:
- `attack_mode` flag to enable/disable attack validation
- `_classify_attack()` method to categorize attack types
- Attack type logging for audit trail
- Phase and storage metadata in responses

**Attack Types Detected**:
- `normal` - Within normal operating range
- `mild_overload` - 10-50% over normal limit
- `overload_attack` - >50% over normal limit
- `reverse_power_injection` - Negative setpoints
- `reactive_power_attack` - Excessive reactive power

**Example Log Output**:
```
WARNING - ATTACK INJECTION: MALICIOUS | EV=EV3 | P=2500 kW | Q=0 kvar | Type=overload_attack
```

**Validation Logic**:
```python
if self._attack_mode:
    min_kw = limits.get("min_kw", -1000)  # Allow negative
    max_kw = limits.get("attack_max_kw", 4000)  # Attack limit
else:
    min_kw = 0
    max_kw = limits.get("normal_max_kw", 200)  # Normal limit
```

---

## Documentation Changes

### 3. `README.md` - Updated for Attack Mode

**Key Changes**:
- Added "Architecture: Red Team vs Blue Team" section
- Clarified competing message mechanism
- Added attack examples (overload, reverse power, coordinated)
- Emphasized adversarial testing purpose

**New Sections**:
- Attack Mode Operation
- Attack Examples (benign, overload, reverse power, coordinated)
- Blue Team vs Red Team architecture diagram

### 4. `ATTACK_STRATEGIES.md` - NEW FILE

**Content**:
- 8 detailed attack strategies with examples
- Expected impact analysis for each attack
- Defense analysis framework
- Attack success metrics
- Ethical guidelines

**Attack Strategies Documented**:
1. Simple Overload Attack
2. Reverse Power Injection Attack
3. Phase Imbalance Attack
4. Timing-Based Attack (Peak Demand Exploitation)
5. Storage Exploitation Attack
6. Reactive Power Attack
7. Rapid Setpoint Fluctuation Attack
8. Coordinated Multi-Stage Attack Campaign

### 5. `DEPLOYMENT_ATTACK_MODE.md` - NEW FILE

**Content**:
- Step-by-step deployment guide
- Architecture diagram
- Attack execution examples
- Monitoring and analysis procedures
- Troubleshooting common issues
- Security considerations

**Key Sections**:
- Prerequisites and verification
- Docker vs local deployment
- Real-time monitoring commands
- Attack log analysis
- Simple AI attacker example code

---

## What Was NOT Changed

### Kept Intact
1. **GridLAB-D Configuration**: No changes to `examples/2bus-13bus/1c_IEEE_123_feeder.glm`
2. **Legitimate Controller**: `1bc_EV_Controller.py` continues operating unchanged
3. **HELICS Broker**: No broker configuration changes needed
4. **Observation Service**: `src/observation_service.py` remains unchanged
5. **EV Federate Core**: `src/ev_federate.py` unchanged (already supported endpoint injection)

### Why This Works
The attack mode operates by **competing for the same HELICS endpoints** as the legitimate controller:
- Both send messages to `gld_hlc_conn/EV1-6`
- HELICS delivers messages in chronological order
- **Last message received wins** (most recent setpoint applied)
- No changes needed to GridLAB-D or other components

---

## Testing Required

### 1. HELICS Connectivity
- [ ] Verify MCP federate connects to broker
- [ ] Confirm subscription keys receive data (not all zeros)
- [ ] Test endpoint message delivery to GridLAB-D

### 2. Attack Primitive Validation
- [ ] Benign setpoint (180 kW) -> attack_type = "normal"
- [ ] Overload setpoint (2500 kW) -> attack_type = "overload_attack"
- [ ] Negative setpoint (-500 kW) -> attack_type = "reverse_power_injection"
- [ ] Validate phase assignments match (EV1=CN, EV2=BN, etc.)

### 3. Competition with Legitimate Controller
- [ ] Both controllers running simultaneously
- [ ] Attacker messages override controller messages
- [ ] Controller continues operating (doesn't crash)
- [ ] Grid responds to attacker setpoints

### 4. Attack Impact Verification
- [ ] Overload attack triggers feeder limit (> 4.2 MW)
- [ ] Controller activates islanding when overload detected
- [ ] Storage systems respond during islanding
- [ ] Voltage/power measurements reflect attack

### 5. Logging and Audit
- [ ] All attacks logged to `interaction_log.jsonl`
- [ ] Attack types correctly classified
- [ ] Timestamps accurate
- [ ] MCP server logs show attack warnings

---

## Deployment Checklist

Before production attack testing:

1. ✅ Configuration updated (`ev_mcp.yaml`)
2. ✅ Action service updated with attack validation
3. ✅ Documentation updated (README, strategies, deployment guide)
4. ⚠️ HELICS keys need verification (check broker logs)
5. ⚠️ Test benign setpoint first
6. ⚠️ Monitor legitimate controller behavior
7. ⚠️ Verify attack logging is working
8. ⚠️ Ensure Docker network isolation

---

## Known Limitations

1. **No Switch Control**: Currently only EV setpoints. Cannot directly control switches (swEV1, swEV4, etc.)
2. **Single Feeder**: Only Feeder A (1c_IEEE_123_feeder.glm) has confirmed EV control. Feeder B status unknown.
3. **No Authentication**: API endpoints are open (acceptable for isolated research)
4. **Timing Granularity**: Limited by HELICS time steps (60s period)
5. **No Feedback Loop**: Attacker doesn't get immediate confirmation of grid response (must observe via next status query)

---

## Future Enhancements

1. **Switch Attack Primitive**: Add ability to force open/close switches
2. **Storage Control**: Direct battery setpoint manipulation during islanding
3. **Coordinated Attack Scheduler**: Built-in multi-stage attack campaigns
4. **Real-Time Feedback**: WebSocket for instant attack impact visibility
5. **AI Integration**: Direct OpenAI API calls for autonomous attack planning
6. **Defense Evaluation**: Metrics to score defense effectiveness

---

## Rollback Procedure

If attack mode needs to be disabled:

```bash
# Restore original config
git checkout config/ev_mcp.yaml

# Or manually edit:
# - attack_mode: false
# - default_max_kw: 200
# - Remove attack_max_kw, use normal_max_kw only
```

---

## Security Audit

**Classification**: Red Team Penetration Testing Tool
**Risk Level**: High (capable of disrupting simulated grid)
**Mitigations**:
- Docker network isolation
- Comprehensive audit logging
- No real grid connectivity
- Ethical use guidelines enforced

**Acceptable Use**:
- ✅ Defensive cybersecurity research
- ✅ Grid vulnerability assessment
- ✅ AI attack algorithm development
- ✅ Defense mechanism testing

**Prohibited Use**:
- ❌ Real grid infrastructure
- ❌ Unauthorized testing
- ❌ Malicious attacks
- ❌ Uncontrolled environments

---

*Changes implemented by: AI Assistant (Claude)*
*Date: 2025-01-07*
*Purpose: Enable adversarial grid testing for defensive research*
