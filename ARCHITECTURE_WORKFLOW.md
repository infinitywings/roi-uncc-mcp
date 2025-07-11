# ROI UNCC MCP Architecture and Workflow Documentation

## Complete System Architecture and AI-Assisted Attack Workflow

This document traces the complete execution flow from running `run_demo.sh` through all system components during an AI-assisted grid attack demonstration.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Initialization Flow](#initialization-flow)
3. [Component Architecture](#component-architecture)
4. [AI Attack Workflow](#ai-attack-workflow)
5. [HELICS Integration Points](#helics-integration-points)
6. [LLM Integration](#llm-integration)
7. [Attack Primitives](#attack-primitives)
8. [Data Flow Diagram](#data-flow-diagram)

---

## 1. System Overview

The ROI UNCC MCP system consists of several interconnected components:

```
┌─────────────────────────────────────────────────────────────┐
│                    run_demo.sh                               │
│  (Entry point - orchestrates Docker containers)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   demo_docker.py                             │
│  (Python orchestrator - manages campaign execution)          │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
┌──────────────────┐                    ┌─────────────────────┐
│ Docker Compose   │                    │   MCP Server API    │
│ Infrastructure   │                    │  (Flask REST API)   │
└──────────────────┘                    └─────────────────────┘
        │                                           │
        ├── HELICS Broker                          ├── /api/ai/execute
        ├── GridPACK Federate                      ├── /api/status
        ├── GridLAB-D Federate                     └── /api/attack
        └── MCP Server Container
```

---

## 2. Initialization Flow

### Step 1: run_demo.sh Execution
```bash
./run_demo.sh --docker --build --mode ai --duration 300
```

**File**: `run_demo.sh`
**Actions**:
1. Parses command line arguments
2. Validates parameters (mode, duration, etc.)
3. Calls `demo_docker.py` with appropriate arguments

### Docker Files Usage

The system uses multiple Docker files for different purposes:

#### **Actually Used Docker Files:**
1. **`containers/docker/Dockerfile`** - Base container image (`roi-uncc-img:latest`)
   - Contains HELICS, GridLAB-D, GridPACK, and all dependencies
   - Built manually: `cd containers/docker && docker build -t roi-uncc-img:latest .`
   - Used by: helics-broker, gridpack-federate, gridlabd-federate containers

2. **`Dockerfile.mcp`** - MCP server container
   - Extends `roi-uncc-img:latest` with MCP server code
   - Built automatically by `demo_docker.py`
   - Used by: mcp-server container

3. **`docker-compose.demo.yml`** - Container orchestration
   - Defines all services and their relationships
   - Used by: `demo_docker.py` to start/stop services

#### **Cleaned Up:**
- **`Dockerfile`** (in root directory) - Legacy/standalone version, removed
- **`containers/docker/with-helics-2.2.2/`** - Older HELICS version, removed
- **`containers/apptainer/`** - Apptainer/Singularity files, removed

### Step 2: demo_docker.py Initialization

**File**: `demo_docker.py`
**Key Components**:

```python
class ContainerizedDemo:
    def __init__(self):
        self.compose_file = "docker-compose.demo.yml"
        self.mcp_url = "http://localhost:5000"
        self.containers = [
            'helics-broker',
            'gridpack-federate', 
            'gridlabd-federate',
            'mcp-server'
        ]
```

**Actions**:
1. Checks Docker prerequisites
2. Cleans up existing containers if `--clean` specified
3. Builds images if `--build` specified
4. Starts containers via `docker-compose up -d`
5. Waits for all services to be ready
6. Executes attack campaign via MCP API

### Step 3: Container Build Process

**Triggered by**: `--build` flag in `run_demo.sh`

1. **Base Container Check** (`demo_docker.py:check_prerequisites()`):
   ```python
   # Check if roi-uncc-img:latest exists
   result = subprocess.run(['docker', 'images', '-q', 'roi-uncc-img:latest'])
   if not result.stdout.strip():
       print("❌ Base container 'roi-uncc-img:latest' not found")
       print("   cd containers/docker && docker build -t roi-uncc-img:latest .")
   ```

2. **MCP Container Build** (`demo_docker.py:build_mcp_container()`):
   ```python
   # Build MCP server container
   cmd = ['docker', 'build', '-f', 'Dockerfile.mcp', '-t', 'roi-uncc-mcp:latest', '.']
   process = subprocess.run(cmd, cwd=self.demo_dir)
   ```

### Step 4: Container Startup Sequence

**File**: `docker-compose.demo.yml`

```yaml
services:
  helics-broker:      # Started first - communication hub
  gridpack-federate:  # Transmission grid simulator
  gridlabd-federate:  # Distribution grid simulator  
  mcp-server:         # Attack orchestrator - depends on others
```

**Container Dependencies**:
- `helics-broker` - No dependencies (starts first)
- `gridpack-federate` - depends_on: helics-broker
- `gridlabd-federate` - depends_on: helics-broker  
- `mcp-server` - depends_on: helics-broker, gridpack-federate, gridlabd-federate

**Container Images Used**:
- `helics-broker`: `roi-uncc-img:latest` (base image)
- `gridpack-federate`: `roi-uncc-img:latest` (base image)
- `gridlabd-federate`: `roi-uncc-img:latest` (base image)
- `mcp-server`: Built from `Dockerfile.mcp` (extends base image)

---

## 3. Component Architecture

### MCP Server Structure

```
mcp-server/
├── src/
│   ├── server.py           # Main Flask application
│   ├── federate.py         # HELICS federation interface
│   ├── attacks/
│   │   └── attack_engine.py # Attack primitive implementations
│   ├── ai/
│   │   └── local_llm_client.py # AI/LLM integration
│   ├── monitor/
│   │   └── grid_monitor.py # Real-time grid state monitoring
│   └── utils/
│       └── validation.py   # Threat model validation
└── config/
    └── mcp.yaml           # Server configuration
```

### Component Responsibilities

#### server.py - Main Flask Application
- **Purpose**: REST API server and orchestration hub
- **Key Endpoints**:
  - `/api/ai/execute` - Execute AI-planned attack campaign
  - `/api/status` - Get current grid and attack status
  - `/api/attack` - Execute single attack primitive
- **Initialization**:
  ```python
  # Key initialization in server.py
  federate = GridAttackFederate(config)
  attack_engine = AttackEngine(federate)
  grid_monitor = GridMonitor(federate, config)
  ai_strategist = LocalLLMStrategist(attack_engine, grid_monitor, config)
  ```

#### federate.py - HELICS Interface
- **Purpose**: Bridge between MCP server and grid simulators
- **HELICS Publications**:
  ```python
  self.pub_voltage_attacks = {
      'A': self.federate.register_publication("voltage_attack_A", "complex"),
      'B': self.federate.register_publication("voltage_attack_B", "complex"),
      'C': self.federate.register_publication("voltage_attack_C", "complex")
  }
  self.pub_power_attacks = {
      'A': self.federate.register_publication("power_attack_A", "complex"),
      'B': self.federate.register_publication("power_attack_B", "complex"),
      'C': self.federate.register_publication("power_attack_C", "complex")
  }
  self.pub_command_block = self.federate.register_publication("command_block", "boolean")
  ```
- **HELICS Subscriptions**:
  ```python
  # Subscribe to GridLAB-D measurements
  self.sub_gld_voltage = self.federate.register_subscription("gridlabd/voltage_650", "complex")
  self.sub_gld_power = self.federate.register_subscription("gridlabd/power_650", "complex")
  
  # Subscribe to GridPACK measurements
  self.sub_gpk_voltage_1 = self.federate.register_subscription("gpk_voltage_1", "complex")
  self.sub_gpk_voltage_2 = self.federate.register_subscription("gpk_voltage_2", "complex")
  ```

---

## 4. AI Attack Workflow

### Phase 1: Campaign Initialization

When `/api/ai/execute` is called:

```python
# In server.py
@app.route('/api/ai/execute', methods=['POST'])
def execute_ai_campaign():
    campaign_config = request.json.get('campaign', {})
    result = ai_strategist.execute_campaign(campaign_config)
```

### Phase 2: AI Strategic Planning

**File**: `ai/local_llm_client.py`

```python
class LocalLLMStrategist:
    def plan_attack(self, objective, context):
        # 1. Get current grid state
        grid_state = self.grid_monitor.get_comprehensive_analysis()
        
        # 2. Build prompt with context
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._build_planning_prompt(objective, grid_state)}
        ]
        
        # 3. Call LLM for strategic plan
        response = requests.post(
            f"{self.api_base}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature
            }
        )
        
        # 4. Parse AI response into attack plan
        return self._parse_attack_plan(ai_response)
```

**LLM Prompt Structure**:
```python
def _build_planning_prompt(self, objective, grid_state):
    return f"""
    Current Grid State:
    - Voltages: {grid_state['voltages']}
    - Power Flows: {grid_state['powers']}
    - System Health: {grid_state['system_health']}
    - Detected Anomalies: {grid_state['anomalies']}
    
    Objective: {objective}
    
    Available Attack Techniques:
    1. spoof_data - Manipulate voltage/power measurements
    2. inject_load - Add artificial electrical load
    3. reconnaissance - Gather grid intelligence
    4. block_command - Prevent control commands
    
    Plan a strategic attack sequence with timing and parameters.
    """
```

### Phase 3: Attack Execution Loop

**Execution Flow in `local_llm_client.py`**:

```python
def execute_campaign(self, config):
    attacks_executed = []
    
    while time.time() < end_time:
        # 1. Get fresh grid state
        grid_analysis = self.grid_monitor.get_comprehensive_analysis()
        
        # 2. AI decides next attack
        next_attack = self._decide_next_attack(grid_analysis, attacks_executed)
        
        # 3. Execute through attack engine
        result = self.attack_engine.execute_attack(
            next_attack['technique'],
            next_attack['params']
        )
        
        # 4. Record and analyze impact
        attacks_executed.append(result)
        
        # 5. Optional: Re-plan if needed
        if self._should_replan(result, grid_analysis):
            self.current_plan = self.plan_attack(objective, updated_context)
```

### Phase 4: Attack Primitive Execution

**File**: `attacks/attack_engine.py`

```python
class AttackEngine:
    def __init__(self, federate):
        self.techniques = {
            'spoof_data': self._spoof_data,
            'inject_load': self._inject_load,
            'reconnaissance': self._reconnaissance,
            'block_command': self._block_command
        }
    
    def execute_attack(self, technique, params):
        # 1. Get pre-attack state
        pre_attack_state = self.federate.get_current_state()
        
        # 2. Execute specific technique
        result = self.techniques[technique](params)
        
        # 3. Advance HELICS time
        self.federate.advance_time()
        
        # 4. Get post-attack state
        post_attack_state = self.federate.get_current_state()
        
        # 5. Calculate impact
        impact = self._calculate_impact(pre_attack_state, post_attack_state)
        
        return {
            'technique': technique,
            'params': params,
            'impact': impact,
            'pre_state': pre_attack_state,
            'post_state': post_attack_state
        }
```

**Attack Primitive Implementations**:

```python
def _spoof_data(self, params):
    """Inject false voltage/power measurements"""
    target = params.get('target', 'voltage_A')
    
    if 'voltage' in target:
        phase = target.split('_')[-1]
        voltage_mag = params.get('value', self._generate_strategic_voltage())
        angle = params.get('angle', 0)
        
        # Publish to HELICS
        self.federate.publish_voltage_attack(phase, voltage_mag, angle)
        
    elif 'power' in target:
        phase = params.get('phase', 'A')
        power_real = params.get('real', 0)
        power_reactive = params.get('reactive', 0)
        
        # Publish to HELICS
        self.federate.publish_power_attack(phase, power_real, power_reactive)

def _inject_load(self, params):
    """Add phantom electrical load"""
    phase = params.get('phase', 'A')
    magnitude = params.get('magnitude', 1000000)  # 1 MW default
    
    # Convert to complex power
    power_complex = complex(magnitude * 0.9, magnitude * 0.436)  # 0.9 PF
    
    # Publish as power injection
    self.federate.publish_power_attack(phase, power_complex.real, power_complex.imag)

def _block_command(self, params):
    """Block control commands"""
    enable = params.get('enable', True)
    duration = params.get('duration', 30)
    
    # Publish command block signal
    self.federate.publish_command_block(enable)
    
    # Store block duration for automatic release
    self.command_block_until = time.time() + duration
```

---

## 5. HELICS Integration Points

### HELICS Federation Setup (federate.py)

```python
def _initialize_helics(self):
    # Create federate info
    fedinfo = h.helicsFederateInfoCreate()
    h.helicsFederateInfoSetBroker(fedinfo, self.broker_address)
    h.helicsFederateInfoSetCoreType(fedinfo, h.HELICS_CORE_TYPE_ZMQ)
    
    # Create value federate
    self.federate = h.helicsCreateValueFederate(self.federate_name, fedinfo)
    
    # Register publications for attacks
    self._register_publications()
    
    # Register subscriptions for monitoring
    self._register_subscriptions()
    
    # Enter execution mode
    h.helicsFederateEnterExecutingMode(self.federate)
```

### Time Synchronization

```python
def advance_time(self, time_delta=None):
    """Advance simulation time"""
    if time_delta is None:
        time_delta = self.time_delta
        
    current_time = h.helicsFederateGetCurrentTime(self.federate)
    requested_time = current_time + time_delta
    
    # Request time advance (blocks until granted)
    granted_time = h.helicsFederateRequestTime(self.federate, requested_time)
    
    # Update cached state after time advance
    self._update_cached_state()
```

### Data Exchange

**Publishing Attacks**:
```python
def publish_voltage_attack(self, phase, magnitude, angle):
    """Publish voltage spoofing attack"""
    if phase in self.pub_voltage_attacks:
        # Convert to complex number
        complex_voltage = cmath.rect(magnitude, math.radians(angle))
        
        # Publish to HELICS
        h.helicsPublicationPublishComplex(
            self.pub_voltage_attacks[phase], 
            complex_voltage.real, 
            complex_voltage.imag
        )
        
        # Record in attack history
        self.attack_history.append({
            'type': 'voltage_attack',
            'phase': phase,
            'magnitude': magnitude,
            'angle': angle,
            'timestamp': h.helicsFederateGetCurrentTime(self.federate)
        })
```

**Reading Grid State**:
```python
def _update_cached_state(self):
    """Read current values from all subscriptions"""
    # GridLAB-D measurements
    if h.helicsInputIsUpdated(self.sub_gld_voltage):
        v_complex = h.helicsInputGetComplex(self.sub_gld_voltage)
        self.current_state['gridlabd']['voltage'] = {
            'magnitude': abs(complex(v_complex[0], v_complex[1])),
            'angle': cmath.phase(complex(v_complex[0], v_complex[1]))
        }
    
    # GridPACK measurements
    if h.helicsInputIsUpdated(self.sub_gpk_voltage_1):
        v1 = h.helicsInputGetComplex(self.sub_gpk_voltage_1)
        self.current_state['gridpack']['bus1_voltage'] = abs(complex(v1[0], v1[1]))
```

---

## 6. LLM Integration

### LLM Configuration

**Config Location**: `mcp-server/config/mcp.yaml`
```yaml
ai:
  api_base: "http://nginx-lb/v1"  # Local LLM endpoint
  model: "Qwen/Qwen3-30B-A3B"     # Model selection
  temperature: 0.8                 # Creativity level
  max_tokens: 4000                 # Response length limit
```

### LLM API Calls

**File**: `ai/local_llm_client.py`

**Strategic Planning Call**:
```python
def _call_llm(self, messages):
    """Make API call to LLM"""
    payload = {
        "model": self.model,
        "messages": messages,
        "temperature": self.temperature,
        "max_tokens": self.max_tokens,
        "response_format": {"type": "json_object"}  # Structured output
    }
    
    response = requests.post(
        f"{self.api_base}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
    )
    
    return response.json()['choices'][0]['message']['content']
```

### Prompt Engineering

**System Prompt** (Defensive Security Focus):
```python
self.system_prompt = """You are an AI assistant helping with defensive security research 
on power grid systems. You are analyzing vulnerabilities in a SIMULATED environment to 
help develop better defenses. 

Your task is to demonstrate sophisticated attack strategies that real adversaries might use, 
so that defensive measures can be developed and tested.

Available attack techniques:
- spoof_data: Inject false sensor readings
- inject_load: Add artificial electrical loads  
- reconnaissance: Map system topology
- block_command: Prevent control actions

Always explain your reasoning and consider cascading effects."""
```

**Dynamic Context Injection**:
```python
def _build_execution_prompt(self, grid_state, attack_history):
    return f"""
    Current Situation:
    - Time Elapsed: {self.elapsed_time}s
    - Attacks Executed: {len(attack_history)}
    - Current Grid Health: {grid_state['system_health']['overall_health']:.1%}
    
    Recent Attack Results:
    {self._format_recent_attacks(attack_history[-3:])}
    
    Grid Vulnerabilities Detected:
    {self._format_vulnerabilities(grid_state['vulnerabilities'])}
    
    What should be the next attack action? Consider timing, target, and parameters.
    Respond with JSON: {{"technique": "...", "params": {{...}}, "reasoning": "..."}}
    """
```

---

## 7. Attack Primitives

### Definition Location

**File**: `attacks/attack_engine.py`

### Available Primitives

1. **spoof_data**
   - **Purpose**: Inject false measurements to confuse control systems
   - **Parameters**: 
     - `target`: "voltage_A", "voltage_B", "voltage_C", "power_A", etc.
     - `value`: Magnitude for voltage (V) or power (W)
     - `angle`: Phase angle for voltage (degrees)
     - `phase`: Phase selection (A, B, or C)
   
2. **inject_load**
   - **Purpose**: Add phantom loads to stress the system
   - **Parameters**:
     - `phase`: Target phase (A, B, or C)
     - `magnitude`: Load size in VA
     - `power_factor`: Power factor (default 0.9)
   
3. **reconnaissance**
   - **Purpose**: Gather intelligence about grid state
   - **Parameters**: None (passive observation)
   - **Returns**: Detailed grid topology and state information
   
4. **block_command**
   - **Purpose**: Prevent control commands from executing
   - **Parameters**:
     - `enable`: True to block, False to unblock
     - `duration`: How long to maintain block (seconds)

### Impact Calculation

```python
def _calculate_impact(self, pre_state, post_state):
    """Calculate attack impact metrics"""
    impact = {
        'voltage_deviation': self._calc_voltage_deviation(pre_state, post_state),
        'power_disruption': self._calc_power_disruption(pre_state, post_state),
        'phase_imbalance': self._calc_phase_imbalance(post_state),
        'system_stress': self._calc_system_stress(post_state),
        'total_impact': 0.0
    }
    
    # Weighted total impact score
    weights = {'voltage_deviation': 0.3, 'power_disruption': 0.3, 
               'phase_imbalance': 0.2, 'system_stress': 0.2}
    
    impact['total_impact'] = sum(
        impact[key] * weights.get(key, 0) 
        for key in impact if key != 'total_impact'
    )
    
    return impact
```

---

## 8. Data Flow Diagram

```
┌─────────────────┐
│   run_demo.sh   │
└────────┬────────┘
         │ Executes with parameters
         ▼
┌─────────────────┐
│ demo_docker.py  │
└────────┬────────┘
         │ HTTP POST to /api/ai/execute
         ▼
┌─────────────────────────────────────────────────────┐
│                   MCP Server                         │
│  ┌────────────┐                                     │
│  │ server.py  │                                     │
│  └──────┬─────┘                                     │
│         │                                            │
│         ▼                                            │
│  ┌─────────────────┐     ┌──────────────────┐      │
│  │ LocalLLMStrategist │   │   GridMonitor    │      │
│  └────────┬────────┘     └────────┬─────────┘      │
│           │                        │                 │
│           │ Plans attacks          │ Monitors state │
│           ▼                        ▼                 │
│  ┌─────────────────┐     ┌──────────────────┐      │
│  │  AttackEngine   │────▶│ GridAttackFederate│      │
│  └─────────────────┘     └────────┬─────────┘      │
│                                   │                 │
└───────────────────────────────────┼─────────────────┘
                                    │ HELICS Messages
                          ┌─────────┴─────────┐
                          ▼                   ▼
                ┌──────────────────┐ ┌──────────────────┐
                │ GridLAB-D Fed    │ │  GridPACK Fed    │
                │ (Distribution)   │ │ (Transmission)   │
                └──────────────────┘ └──────────────────┘
```

### Message Flow Example

1. **AI Decision**: 
   ```
   LLM → "spoof_data on voltage_A with 1800V"
   ```

2. **Attack Execution**:
   ```
   AttackEngine → GridAttackFederate → HELICS Publication
   ```

3. **Grid Response**:
   ```
   GridLAB-D → HELICS → GridAttackFederate → GridMonitor
   ```

4. **Impact Analysis**:
   ```
   GridMonitor → LocalLLMStrategist → Next Attack Decision
   ```

---

## Summary

The ROI UNCC MCP architecture demonstrates a sophisticated integration of:

1. **Container Orchestration**: Docker Compose manages all components
2. **REST API**: Flask provides clean HTTP interface
3. **HELICS Federation**: Enables real-time co-simulation
4. **AI Integration**: LLM plans and adapts attack strategies
5. **Attack Engine**: Implements cyber attack primitives
6. **Grid Monitoring**: Continuous state observation and analysis

This architecture enables researchers to study how AI can coordinate complex cyber attacks on power grids, helping develop better defensive strategies.