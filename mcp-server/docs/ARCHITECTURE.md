# MCP (Model Context Protocol) Architecture

## Overview

The Model Context Protocol (MCP) server serves as a bridge between AI models (e.g., DeepSeek) and the simulated power grid environment, enabling AI-driven penetration testing of power grid systems. The MCP provides a comprehensive set of primitives for monitoring grid status and executing cyber attacks in a controlled research environment, following the Model Context Protocol specification for standardized AI-tool interactions.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AI Layer (DeepSeek)                         │
│  - Strategic Planning    - Attack Sequencing    - Impact Analysis   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MCP Server (Python/Flask)                        │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   REST API      │  │  Attack Engine   │  │  Grid Monitor    │  │
│  │  /api/status    │  │  - Primitives    │  │  - State Cache   │  │
│  │  /api/attack    │  │  - Sequencer     │  │  - Analytics     │  │
│  │  /api/recon     │  │  - Validator     │  │  - History       │  │
│  └─────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    HELICS Federation Layer                          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  MCP Federate   │  │   Publications   │  │  Subscriptions   │  │
│  │  - Time Sync    │  │  - Attack Cmds   │  │  - Grid State   │  │
│  │  - Messaging    │  │  - Injections    │  │  - Measurements │  │
│  └─────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                           ┌────────┴────────┐
                           ▼                 ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│    GridLAB-D Federate       │   │    GridPACK Federate        │
│  - IEEE 13-bus model        │   │  - Power flow solver        │
│  - Distribution grid         │   │  - Transmission grid        │
│  - Load/generation models   │   │  - Stability analysis       │
└─────────────────────────────┘   └─────────────────────────────┘
```

## Core Components

### 1. MCP Server

The main server application that:
- Hosts REST API for AI interaction
- Manages HELICS federate lifecycle
- Coordinates attack execution
- Maintains grid state cache

### 2. Attack Engine

Implements attack primitives:
- **Data Spoofing**: Inject false measurements
- **Load Injection**: Add artificial loads
- **Command Blocking**: Prevent control actions
- **Device Control**: Force equipment operations
- **Reconnaissance**: Discover grid topology

### 3. Grid Monitor

Tracks simulation state:
- Real-time voltage/current measurements
- Power flow analysis
- Protection system status
- Attack impact assessment

### 4. HELICS Integration

Manages co-simulation communication:
- Federate registration and initialization
- Time synchronization
- Publication/subscription management
- Message routing

## Data Flow

### Attack Execution Flow

```
1. AI Request → MCP REST API
   POST /api/attack
   {
     "technique": "spoof_data",
     "params": {
       "target": "voltage_A",
       "value": 1800.0,
       "phase": 0
     }
   }

2. MCP → Attack Engine
   - Validate parameters
   - Check threat model constraints
   - Prepare HELICS publications

3. Attack Engine → HELICS
   - Publish attack data
   - Request time advancement
   - Wait for federation sync

4. HELICS → Grid Simulators
   - GridLAB-D receives spoofed data
   - Power flow recalculation
   - Protection system response

5. Grid Simulators → HELICS → MCP
   - Updated grid state
   - Impact measurements
   - System response data

6. MCP → AI Response
   {
     "status": "success",
     "impact": {
       "voltage_deviation": 0.25,
       "protection_triggered": true,
       "affected_buses": ["632", "633", "634"]
     }
   }
```

### Monitoring Flow

```
1. Grid Simulators → HELICS
   - Continuous state publications
   - Voltage, current, power measurements
   - Equipment status updates

2. HELICS → MCP Monitor
   - Subscribe to grid topics
   - Cache latest values
   - Detect anomalies

3. MCP Monitor → State Cache
   - Update internal grid model
   - Calculate derived metrics
   - Maintain history

4. AI Query → MCP API → State Cache
   GET /api/status
   → Current grid state response
```

## Security Considerations

### Research Environment Isolation

- MCP operates ONLY on simulated grids
- No connection to real power systems
- Containerized deployment for isolation
- Clear research-only documentation

### Attack Validation

- Threat model enforcement
- Parameter bounds checking
- Physics-based constraints
- Audit logging

### Access Control

- API authentication tokens
- Rate limiting
- Request validation
- Activity monitoring

## Scalability Design

### Horizontal Scaling

- Stateless MCP server instances
- Shared Redis cache for grid state
- Load-balanced API endpoints
- Distributed HELICS federates

### Performance Optimization

- Asynchronous attack execution
- Batch state updates
- Efficient HELICS messaging
- Caching strategies

## Extension Points

### New Attack Primitives

```python
@attack_technique("new_attack")
def execute_new_attack(federate, params):
    # Custom implementation
    pass
```

### Additional Grid Models

- Support for different IEEE test systems
- Custom grid topologies
- Multi-area simulations
- Transmission-distribution interfaces

### AI Model Integration

- OpenAI API compatibility
- Custom model endpoints
- Batch attack planning
- Multi-agent coordination

## Configuration

### MCP Configuration

```yaml
# config/mcp.yaml
server:
  host: "0.0.0.0"
  port: 5000
  debug: false

helics:
  broker_address: "tcp://127.0.0.1:23404"
  federate_name: "mcp_attacker"
  time_delta: 1.0

attacks:
  max_concurrent: 5
  timeout: 30.0
  validation: strict

monitoring:
  update_interval: 0.1
  history_size: 1000
  anomaly_detection: true
```

### Threat Model Configuration

```yaml
# config/threat_model.yaml
constraints:
  voltage_limits:
    min: 0.7  # 70% of nominal
    max: 1.3  # 130% of nominal
  
  load_injection:
    max_magnitude: 5000000  # 5 MVA
    
  timing:
    min_interval: 1.0  # seconds between attacks
    
allowed_techniques:
  - spoof_data
  - inject_load
  - reconnaissance
  - block_command
  
restricted_targets:
  - critical_infrastructure
  - safety_systems
```

## Development Guidelines

### Code Organization

```
mcp-server/
├── src/
│   ├── __init__.py
│   ├── server.py          # Flask application
│   ├── federate.py        # HELICS integration
│   ├── attacks/           # Attack primitives
│   │   ├── __init__.py
│   │   ├── spoof.py
│   │   ├── inject.py
│   │   └── recon.py
│   ├── monitor/           # Grid monitoring
│   │   ├── __init__.py
│   │   ├── state.py
│   │   └── analytics.py
│   └── utils/             # Utilities
│       ├── __init__.py
│       └── validation.py
├── config/                # Configuration files
├── tests/                 # Test suite
└── docs/                  # Documentation
```

### API Design Principles

1. **RESTful conventions**: Standard HTTP methods and status codes
2. **Consistent responses**: Uniform JSON structure
3. **Comprehensive errors**: Detailed error messages
4. **Version control**: API versioning support
5. **Documentation**: OpenAPI/Swagger specs

### Testing Strategy

- Unit tests for each attack primitive
- Integration tests with mock HELICS
- End-to-end tests with simulators
- Performance benchmarks
- Security validation

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "src/server.py"]
```

### Docker Compose Integration

```yaml
services:
  mcp-server:
    build: ./mcp-server
    ports:
      - "5000:5000"
    environment:
      - HELICS_BROKER=helics-broker:23404
    depends_on:
      - helics-broker
      - gridlabd
```

## Future Enhancements

1. **Advanced Attack Patterns**
   - Multi-stage attack campaigns
   - Coordinated distributed attacks
   - Stealthy/persistent threats

2. **Machine Learning Integration**
   - Attack pattern learning
   - Automated vulnerability discovery
   - Defensive AI capabilities

3. **Visualization Dashboard**
   - Real-time grid visualization
   - Attack timeline display
   - Impact heat maps

4. **Extended Grid Support**
   - More IEEE test systems
   - European grid models
   - Microgrids and DER integration