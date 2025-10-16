# MCP Server Primitives

This document defines the Model Context Protocol primitives available for AI-driven power grid penetration testing.

## Overview

The MCP server exposes two categories of primitives:
1. **Observation Primitives**: For collecting grid status and reconnaissance
2. **Action Primitives**: For executing attacks and modifications

## Observation Primitives

### 1. get_grid_status

Retrieves current power grid operational status.

**Request:**
```json
{
  "method": "get_grid_status",
  "params": {
    "components": ["voltages", "currents", "power_flows"],
    "buses": ["all"] // or specific bus IDs
  }
}
```

**Response:**
```json
{
  "timestamp": 1234567890.123,
  "grid_state": {
    "voltages": {
      "bus_632": {
        "Va": {"magnitude": 2401.5, "angle": 0.0, "pu": 1.001},
        "Vb": {"magnitude": 2398.2, "angle": -120.1, "pu": 0.999},
        "Vc": {"magnitude": 2402.0, "angle": 119.9, "pu": 1.001}
      }
    },
    "currents": {...},
    "power_flows": {...}
  },
  "system_metrics": {
    "total_load": 3500000,
    "total_generation": 3600000,
    "losses": 100000,
    "voltage_imbalance": 0.003
  }
}
```

### 2. discover_topology

Performs reconnaissance to discover grid topology and components.

**Request:**
```json
{
  "method": "discover_topology",
  "params": {
    "scan_type": "full", // "basic", "full", "targeted"
    "include_vulnerabilities": true
  }
}
```

**Response:**
```json
{
  "topology": {
    "buses": [
      {
        "id": "632",
        "type": "distribution_hub",
        "criticality": "high",
        "connected_to": ["633", "645", "671"]
      }
    ],
    "lines": [...],
    "transformers": [...],
    "switches": [...]
  },
  "vulnerabilities": {
    "weak_points": ["bus_671", "line_632_645"],
    "protection_gaps": ["undervoltage_zone_2"],
    "attack_vectors": ["voltage_injection", "load_stress"]
  }
}
```

### 3. monitor_protection_systems

Monitors status of protection devices and control systems.

**Request:**
```json
{
  "method": "monitor_protection_systems",
  "params": {
    "systems": ["undervoltage", "overcurrent", "breakers"]
  }
}
```

**Response:**
```json
{
  "protection_status": {
    "undervoltage_relays": {
      "relay_632": {
        "armed": true,
        "threshold": 0.88,
        "current_value": 0.95,
        "margin": 0.07
      }
    },
    "breakers": {
      "breaker_671": {
        "status": "closed",
        "can_trip": true,
        "last_operation": "2024-01-20T10:30:00Z"
      }
    }
  }
}
```

### 4. analyze_power_flow

Analyzes current power flow patterns and constraints.

**Request:**
```json
{
  "method": "analyze_power_flow",
  "params": {
    "calculation_type": "full", // "simplified", "full"
    "include_sensitivities": true
  }
}
```

**Response:**
```json
{
  "power_flow": {
    "convergence": true,
    "iterations": 3,
    "mismatch": 0.0001,
    "line_flows": {...},
    "bus_injections": {...}
  },
  "sensitivities": {
    "voltage_sensitivity": {...},
    "power_transfer_factors": {...}
  },
  "constraints": {
    "line_limits": {...},
    "voltage_limits": {...},
    "thermal_limits": {...}
  }
}
```

## Action Primitives

### 5. inject_false_data

Spoofs measurements to deceive grid monitoring systems.

**Request:**
```json
{
  "method": "inject_false_data",
  "params": {
    "injection_type": "voltage",
    "target": "bus_632_phase_A",
    "value": {
      "magnitude": 1800.0,
      "angle": 0.0
    },
    "duration": 10.0 // seconds
  }
}
```

**Response:**
```json
{
  "status": "success",
  "injection_id": "inj_001",
  "expected_impact": {
    "protection_trigger_probability": 0.85,
    "affected_buses": ["632", "633", "634"],
    "severity": "high"
  }
}
```

### 6. manipulate_load

Injects artificial load to stress the grid.

**Request:**
```json
{
  "method": "manipulate_load",
  "params": {
    "action": "inject", // "inject", "remove", "modify"
    "location": "bus_634",
    "load_profile": {
      "P": 2000000, // Active power in Watts
      "Q": 1000000, // Reactive power in VAR
      "phases": ["A", "B", "C"]
    }
  }
}
```

**Response:**
```json
{
  "status": "success",
  "load_id": "load_attack_001",
  "grid_response": {
    "voltage_drop": 0.12,
    "overload_risk": "medium",
    "stability_margin": 0.15
  }
}
```

### 7. disrupt_communication

Blocks or delays control commands and protection signals.

**Request:**
```json
{
  "method": "disrupt_communication",
  "params": {
    "disruption_type": "block", // "block", "delay", "corrupt"
    "target_channel": "scada_to_breaker_671",
    "duration": 30.0,
    "pattern": "complete" // "complete", "intermittent", "selective"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "disruption_id": "comm_block_001",
  "impact": {
    "blocked_commands": ["open_breaker", "voltage_setpoint"],
    "control_degradation": "severe",
    "recovery_hindrance": "high"
  }
}
```

### 8. manipulate_device

Forces device operations (breakers, switches, tap changers).

**Request:**
```json
{
  "method": "manipulate_device",
  "params": {
    "device_type": "breaker",
    "device_id": "breaker_671",
    "action": "open", // "open", "close", "toggle"
    "force": true // Override interlocks
  }
}
```

**Response:**
```json
{
  "status": "success",
  "device_state": {
    "previous": "closed",
    "current": "open",
    "timestamp": 1234567890.456
  },
  "cascading_effects": {
    "power_rerouted": true,
    "overloads_created": ["line_632_633"],
    "islands_formed": 0
  }
}
```

### 9. coordinate_attack

Executes multi-stage coordinated attack campaigns.

**Request:**
```json
{
  "method": "coordinate_attack",
  "params": {
    "campaign_id": "campaign_001",
    "stages": [
      {
        "time_offset": 0,
        "primitive": "discover_topology",
        "params": {"scan_type": "targeted"}
      },
      {
        "time_offset": 5,
        "primitive": "inject_false_data",
        "params": {
          "injection_type": "voltage",
          "target": "bus_632_phase_A",
          "value": {"magnitude": 1900.0, "angle": 0.0}
        }
      },
      {
        "time_offset": 15,
        "primitive": "manipulate_load",
        "params": {
          "action": "inject",
          "location": "bus_634",
          "load_profile": {"P": 3000000, "Q": 1500000}
        }
      },
      {
        "time_offset": 20,
        "primitive": "disrupt_communication",
        "params": {
          "disruption_type": "block",
          "target_channel": "voltage_regulator_commands"
        }
      }
    ]
  }
}
```

**Response:**
```json
{
  "campaign_status": "executing",
  "campaign_id": "campaign_001",
  "stages_completed": 0,
  "stages_total": 4,
  "real_time_updates": "ws://mcp-server:5001/campaigns/campaign_001"
}
```

### 10. trigger_cascade

Attempts to trigger cascading failures through strategic targeting.

**Request:**
```json
{
  "method": "trigger_cascade",
  "params": {
    "strategy": "n-1-1", // N-1-1 contingency exploitation
    "initial_targets": ["line_632_645", "transformer_633"],
    "propagation_goal": "maximum_load_shed"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "cascade_analysis": {
    "initial_outages": 2,
    "cascaded_outages": 5,
    "total_load_shed": 2500000,
    "affected_customers": 1200,
    "propagation_path": [
      {"time": 0, "event": "line_632_645 tripped"},
      {"time": 2, "event": "overload on line_632_633"},
      {"time": 5, "event": "undervoltage at bus_634"},
      {"time": 8, "event": "protection cascade started"}
    ]
  }
}
```

## Primitive Categories

### Intelligence Gathering
- `get_grid_status`
- `discover_topology`
- `monitor_protection_systems`
- `analyze_power_flow`

### Direct Attacks
- `inject_false_data`
- `manipulate_load`
- `manipulate_device`

### Indirect Attacks
- `disrupt_communication`
- `trigger_cascade`

### Campaign Coordination
- `coordinate_attack`

## Usage Guidelines

### Sequential Execution
```python
# Example: Reconnaissance followed by targeted attack
topology = mcp.discover_topology(scan_type="full")
vulnerabilities = topology["vulnerabilities"]["weak_points"]
target = vulnerabilities[0]  # Select most vulnerable

result = mcp.inject_false_data(
    injection_type="voltage",
    target=f"{target}_phase_A",
    value={"magnitude": 1700.0, "angle": 0.0}
)
```

### Parallel Execution
```python
# Example: Simultaneous multi-point attack
import asyncio

async def multi_point_attack():
    tasks = [
        mcp.inject_false_data(target="bus_632_phase_A", value=1800),
        mcp.inject_false_data(target="bus_671_phase_B", value=1850),
        mcp.manipulate_load(location="bus_634", load_profile={"P": 3000000})
    ]
    results = await asyncio.gather(*tasks)
    return results
```

### Adaptive Campaigns
```python
# Example: AI-driven adaptive attack
while campaign_active:
    # Observe current state
    grid_state = mcp.get_grid_status()
    
    # AI decides next action based on state
    next_action = ai_model.plan_attack(grid_state)
    
    # Execute attack
    result = mcp.execute_primitive(next_action)
    
    # Assess impact
    if result["impact"]["severity"] == "critical":
        # Exploit the vulnerability
        mcp.disrupt_communication(target_channel="protection_systems")
```

## Security Constraints

All primitives enforce the following constraints:

1. **Operational Limits**: Prevent physically impossible values
2. **Safety Boundaries**: No permanent damage to simulated equipment
3. **Research Ethics**: Clear logging and attribution of all actions
4. **Threat Model Compliance**: Actions must align with defined threat model

## Error Handling

All primitives return standardized error responses:

```json
{
  "status": "error",
  "error_code": "INVALID_TARGET",
  "message": "Target bus_999 does not exist in current topology",
  "details": {
    "valid_targets": ["bus_632", "bus_633", "bus_634", ...]
  }
}
```

## Performance Considerations

- **Latency**: Most primitives complete within 100ms
- **Concurrency**: Up to 10 simultaneous primitive executions
- **Rate Limiting**: 100 requests per second per client
- **Resource Usage**: Memory-efficient caching of grid state

## Extension Mechanism

New primitives can be added through the plugin system:

```python
@mcp_primitive("custom_attack")
def custom_attack_handler(params):
    # Implementation
    return {"status": "success", "result": ...}
```