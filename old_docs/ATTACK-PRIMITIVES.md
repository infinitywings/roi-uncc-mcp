# ⚔️ Attack Primitives Reference

Technical documentation for all attack techniques available in the MCP server.

## 🎯 **Attack Technique Overview**

| Technique | Target | Impact | MITRE ATT&CK |
|-----------|--------|---------|--------------|
| `spoof_data` | Voltage measurements | Protection system triggering | T0832 - Manipulation of Control |
| `inject_load` | Grid capacity | Voltage drop, overload | T0836 - Modify Parameter |
| `reconnaissance` | System topology | Intelligence gathering | T0840 - Network Connection Enumeration |
| `block_command` | Control channels | Response prevention | T0814 - Denial of Service |
| `toggle_device` | Circuit breakers | Service interruption | T0835 - Manipulate I/O Image |

## 🔧 **Attack Technique Details**

### **1. Voltage Data Spoofing (`spoof_data`)**

**Purpose**: Inject false voltage readings directly into GridLAB-D simulation

**HELICS Mechanism**: 
- Creates publication: `mcp/attack_voltage_A/B/C`
- GridLAB-D subscribes to these topics
- Injected values override normal voltage calculations

**Parameters:**
```json
{
  "technique": "spoof_data",
  "params": {
    "target": "voltage_A",     // "voltage_A", "voltage_B", "voltage_C"
    "value": 1800.0,           // Magnitude in volts
    "phase": 0                 // Phase angle in degrees
  }
}
```

**Implementation:**
```python
@technique("spoof_data")
def _spoof_data(fed: h.HelicsFederate, params: Dict[str, Any]) -> Dict[str, Any]:
    target = params.get("target", "voltage_A")
    magnitude = float(params.get("value", 2400.0))
    phase_deg = float(params.get("phase", 0.0))
    
    # Convert to complex representation
    import math
    phase_rad = math.radians(phase_deg)
    real_part = magnitude * math.cos(phase_rad)
    imag_part = magnitude * math.sin(phase_rad)
    
    # Create publication to GridLAB-D
    topic = f"mcp/attack_{target}"
    pub = h.helicsFederateRegisterPublication(fed, topic, h.HELICS_DATA_TYPE_COMPLEX, "V")
    h.helicsPublicationPublishComplex(pub, real_part, imag_part)
```

**Expected Impact:**
- **Undervoltage** (< 1900V): Triggers protection systems
- **Overvoltage** (> 2600V): Triggers overvoltage protection
- **Phase imbalance**: Creates system instability

### **2. Load Injection (`inject_load`)**

**Purpose**: Add artificial load to stress the grid system

**HELICS Mechanism**: 
- Creates publication: `mcp/load_injection_A/B/C`
- Simulates additional power demand
- Causes voltage drops and equipment stress

**Parameters:**
```json
{
  "technique": "inject_load",
  "params": {
    "magnitude": 2000000,      // Load in VA (2 MVA)
    "target": "A",             // Phase "A", "B", or "C"
    "phase_deg": 30            // Power factor angle
  }
}
```

**Implementation:**
```python
@technique("inject_load")
def _inject_load(fed: h.HelicsFederate, params: Dict[str, Any]) -> Dict[str, Any]:
    magnitude = float(params.get("magnitude", 1000000))  # 1 MVA default
    phase_deg = float(params.get("phase_deg", 0.0))
    target = params.get("target", "A")
    
    # Convert to complex power
    import math
    phase_rad = math.radians(phase_deg)
    real_part = magnitude * math.cos(phase_rad)  # Active power
    imag_part = magnitude * math.sin(phase_rad)  # Reactive power
    
    # Inject artificial load
    topic = f"mcp/load_injection_{target}"
    pub = h.helicsFederateRegisterPublication(fed, topic, h.HELICS_DATA_TYPE_COMPLEX, "VA")
    h.helicsPublicationPublishComplex(pub, real_part, imag_part)
```

**Expected Impact:**
- **Voltage sag**: Reduces system voltage levels
- **Equipment overload**: Stresses transformers and lines
- **Protection triggering**: May cause overcurrent protection

### **3. Grid Reconnaissance (`reconnaissance`)**

**Purpose**: Discover grid topology and operational vulnerabilities

**HELICS Mechanism**: 
- Queries available HELICS subscriptions
- Analyzes current grid measurements
- Returns intelligence for strategic planning

**Parameters:**
```json
{
  "technique": "reconnaissance",
  "params": {
    "scan_type": "operational"  // "topology", "operational", "full"
  }
}
```

**Implementation:**
```python
@technique("reconnaissance")
def _reconnaissance(fed: h.HelicsFederate, params: Dict[str, Any]) -> Dict[str, Any]:
    scan_type = params.get("scan_type", "operational")
    
    if scan_type == "topology":
        return {
            "status": "ok",
            "action": "reconnaissance",
            "discovered": {
                "grid_model": "IEEE 13-bus distribution feeder",
                "critical_buses": {
                    "650": "Main feeder connection (substation)",
                    "632": "Primary distribution hub",
                    "671": "Transformer and switch location"
                },
                "attack_targets": ["voltage_A", "voltage_B", "voltage_C"]
            }
        }
    else:
        # Operational intelligence
        return {
            "status": "ok",
            "operational_data": {
                "nominal_voltage": 2400.0,
                "attack_surface": {
                    "voltage_injection_points": ["mcp/attack_voltage_A", "mcp/attack_voltage_B", "mcp/attack_voltage_C"],
                    "load_injection_points": ["mcp/load_injection_A", "mcp/load_injection_B", "mcp/load_injection_C"]
                },
                "vulnerability_assessment": {
                    "voltage_stability": "Monitor for under/overvoltage conditions",
                    "protection_systems": "Undervoltage and overvoltage protection active"
                }
            }
        }
```

**Intelligence Gathered:**
- **Grid topology**: Bus connections and critical nodes
- **Operational state**: Current voltage/power levels
- **Attack surface**: Available injection points
- **Vulnerabilities**: System weak points

### **4. Command Blocking (`block_command`)**

**Purpose**: Prevent control commands from reaching devices

**HELICS Mechanism**: 
- Simulates communication disruption
- Blocks automatic control responses
- Extends attack persistence

**Parameters:**
```json
{
  "technique": "block_command",
  "params": {
    "src": "controller/commands"  // Source to block
  }
}
```

**Implementation:**
```python
@technique("block_command")
def _block_command(fed: h.HelicsFederate, params: Dict[str, Any]) -> Dict[str, Any]:
    src = params.get("src", "controller/commands")
    
    # In full implementation, would create HELICS message filter
    # For demonstration, logs the blocking action
    logger.warning("Blocking commands from %s (demo placeholder).", src)
    
    return {
        "status": "ok", 
        "action": "block_command", 
        "src": src,
        "impact": "Control commands blocked - prevents automatic recovery"
    }
```

**Expected Impact:**
- **Recovery prevention**: Stops automatic voltage regulation
- **Protection disabling**: Blocks protective device commands
- **Persistence**: Extends duration of other attacks

### **5. Device Control (`toggle_device`)**

**Purpose**: Force circuit breaker or switch operations

**HELICS Mechanism**: 
- Publishes device control commands
- Simulates unauthorized device operation
- Creates unplanned service interruptions

**Parameters:**
```json
{
  "technique": "toggle_device",
  "params": {
    "device_topic": "grid/breaker/671_switch",  // Device control topic
    "state": 0                                  // 0=open, 1=closed
  }
}
```

**Implementation:**
```python
@technique("toggle_device")
def _toggle_device(fed: h.HelicsFederate, params: Dict[str, Any]) -> Dict[str, Any]:
    device_topic = params.get("device_topic", "grid/device/breaker1/cmd")
    state = int(params.get("state", 0))

    # Send device control command
    pub = h.helicsFederateRegisterPublication(fed, device_topic, h.HELICS_DATA_TYPE_STRING, "")
    h.helicsPublicationPublishString(pub, json.dumps({"state": state}))
    
    # Advance simulation time
    current_time = h.helicsFederateGetCurrentTime(fed)
    h.helicsFederateRequestTime(fed, current_time + 1.0)
    
    return {
        "status": "ok", 
        "action": "toggle_device", 
        "device": device_topic, 
        "state": "open" if state == 0 else "closed"
    }
```

**Expected Impact:**
- **Service interruption**: Opens breakers to create outages
- **Load redistribution**: Forces power flow changes
- **Protection confusion**: May cause coordination issues

## 🔄 **Attack Coordination**

### **Multi-Phase Attack Example**

```python
# Phase 1: Reconnaissance
attack_1 = {
    "technique": "reconnaissance",
    "params": {"scan_type": "operational"}
}

# Phase 2: Voltage manipulation (based on recon)
attack_2 = {
    "technique": "spoof_data", 
    "params": {"target": "voltage_A", "value": 1700, "phase": 0}
}

# Phase 3: Load stress (amplify impact)
attack_3 = {
    "technique": "inject_load",
    "params": {"magnitude": 3000000, "target": "A", "phase_deg": 30}
}

# Phase 4: Block recovery
attack_4 = {
    "technique": "block_command",
    "params": {"src": "voltage_regulator/commands"}
}
```

### **Timing Strategies**

**Sequential Attacks:**
```python
# Execute attacks with coordination delay
for attack in attack_sequence:
    execute_attack(attack)
    time.sleep(15)  # Allow grid response
```

**Coordinated Multi-Phase:**
```python
# Simultaneous voltage and load attacks
execute_parallel([voltage_attack, load_attack])
time.sleep(30)
execute_attack(block_recovery)
```

## 📊 **Attack Effectiveness Metrics**

### **Impact Scoring**

```python
def calculate_attack_impact(before_state, after_state):
    impact_score = 0
    
    # Voltage deviation scoring (0-100 points)
    for phase in ["Va", "Vb", "Vc"]:
        before_pu = before_state.get("voltages", {}).get(phase, {}).get("pu", 1.0)
        after_pu = after_state.get("voltages", {}).get(phase, {}).get("pu", 1.0)
        deviation = abs(after_pu - before_pu)
        
        if after_pu < 0.9 or after_pu > 1.1:
            impact_score += 50  # Critical voltage
        elif after_pu < 0.95 or after_pu > 1.05:
            impact_score += 25  # Warning voltage
        
        impact_score += deviation * 100  # Deviation magnitude
    
    # Power disruption scoring
    power_change = calculate_power_disruption(before_state, after_state)
    impact_score += power_change * 10
    
    return min(impact_score, 1000)  # Cap at 1000 points
```

### **Success Criteria**

| Metric | Threshold | Impact Level |
|--------|-----------|--------------|
| Voltage deviation | > 5% | Minor |
| Voltage deviation | > 10% | Major |
| Protection triggering | Any trip | Critical |
| Power disruption | > 20% | Major |
| Cascading failures | > 2 buses | Critical |

## 🛡️ **Detection and Mitigation**

### **Attack Signatures**

**Voltage Spoofing Detection:**
- Sudden voltage changes without load correlation
- Phase angle inconsistencies
- Impossible voltage magnitudes

**Load Injection Detection:**
- Power flow mismatches
- Unexplained voltage drops
- Load pattern anomalies

### **Defensive Countermeasures**

```python
def detect_attack_patterns(grid_measurements):
    """Detect potential cyber attacks from grid measurements"""
    anomalies = []
    
    # Voltage anomaly detection
    for phase, voltage in grid_measurements.get("voltages", {}).items():
        if voltage.get("pu", 1.0) < 0.85 or voltage.get("pu", 1.0) > 1.15:
            anomalies.append(f"Extreme voltage on {phase}: {voltage.get('pu')}")
    
    # Rate of change detection
    voltage_rate = calculate_voltage_rate_of_change(grid_measurements)
    if voltage_rate > 0.1:  # > 10% per second
        anomalies.append(f"Rapid voltage change: {voltage_rate:.2f}/s")
    
    return anomalies
```

## 🔧 **Implementation Notes**

### **HELICS Integration**

All attacks use HELICS publications to inject malicious data:

```python
# Common HELICS pattern
def execute_attack(technique, params, federate):
    # 1. Register publication
    pub = h.helicsFederateRegisterPublication(
        federate, 
        attack_topic, 
        data_type, 
        units
    )
    
    # 2. Publish attack data
    h.helicsPublicationPublishComplex(pub, real_value, imag_value)
    
    # 3. Advance simulation time
    current_time = h.helicsFederateGetCurrentTime(federate)
    h.helicsFederateRequestTime(federate, current_time + 0.1)
```

### **Error Handling**

```python
try:
    result = execute_technique(technique_name, params, federate)
    log_attack_success(result)
except Exception as e:
    log_attack_failure(technique_name, str(e))
    return {"status": "error", "message": str(e)}
```

### **Registry Pattern**

```python
# Decorator-based technique registration
_TECHNIQUES = {}

def technique(name: str):
    def _wrapper(func):
        _TECHNIQUES[name] = func
        return func
    return _wrapper

@technique("spoof_data")
def _spoof_data(fed, params):
    # Implementation
    pass
```

---

**Next Steps:** See [RESEARCH-GUIDE.md](RESEARCH-GUIDE.md) for academic usage methodology or [DEPLOYMENT.md](DEPLOYMENT.md) for setup instructions.