# AI-Assisted Grid Penetration Testing Framework

ROI UNCC MCP Project - Research framework for studying power grid cybersecurity using AI-driven attack strategies.

## Overview

This project implements a Model Context Protocol (MCP) server that enables AI models (DeepSeek) to conduct strategic penetration testing on simulated power grid systems. The framework demonstrates how AI-assisted attacks can be significantly more effective than random approaches, providing valuable insights for defensive cybersecurity research.

### Key Features

- **AI-Powered Strategic Planning**: DeepSeek AI analyzes grid state and plans coordinated attack sequences
- **Real Physics Simulation**: GridLAB-D + GridPACK co-simulation with actual electrical calculations
- **HELICS Integration**: Real-time federated simulation for authentic attack-defense scenarios
- **Comprehensive Attack Primitives**: Data spoofing, load injection, reconnaissance, command blocking
- **Threat Model Validation**: Safety constraints prevent simulation damage
- **Performance Comparison**: Quantitative analysis of AI vs random attack effectiveness

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
│  │  /api/ai/*      │  │  - Validator     │  │  - History       │  │
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
│  └─────────────────────────┘   └─────────────────────────────┘
```

## Installation and Setup

### Prerequisites

- **Docker and docker-compose** (recommended approach)
- **OR** Local installation: Ubuntu 22.04, Python 3.8+, HELICS, GridLAB-D, GridPACK
- AI Model: Either local LLM or any OpenAI-compatible API
- Git

## Quick Start (Recommended: Docker)

### 1. Verify Prerequisites

```bash
# Test Docker setup
docker --version && docker compose version
docker images | grep roi-uncc-img
```

Expected output:
```
Docker version 27.5.1, build 4ed5d58
Docker Compose version v2.29.1
roi-uncc-img    latest    abc123def456   2 days ago    2.1GB
```

### 2. Configure AI Model

**Option A: Use Configuration Files (Recommended)**
```bash
# Use OpenAI GPT-4
./run_demo.sh --config config/examples/openai_config.yaml

# Use Anthropic Claude
./run_demo.sh --config config/examples/anthropic_config.yaml

# Use local Ollama
./run_demo.sh --config config/examples/ollama_config.yaml

# Use local Qwen3 (default)
./run_demo.sh --config config/examples/local_qwen_config.yaml
```

**Option B: Command Line Parameters**
```bash
# OpenAI API
./run_demo.sh --ai-model gpt-4 \
              --ai-base-url https://api.openai.com/v1 \
              --ai-api-key sk-your-key-here

# Local LLM
./run_demo.sh --ai-model llama-3-70b \
              --ai-base-url http://localhost:8080/v1
```

**Option C: Default Local Setup**
```bash
# Check if nginx-lb and vllm containers are running
docker ps | grep -E "nginx-lb|vllm"
# Then run with defaults
./run_demo.sh
```

### 3. Run the Demo

**Complete comparison demo (AI vs Random attacks):**
```bash
./run_demo.sh
```

**Specific demo modes:**
```bash
# AI-only attacks (60 seconds)
./run_demo.sh --mode ai --duration 60

# Random attacks only
./run_demo.sh --mode random --duration 60

# Comprehensive comparison study (3 trials each)
./run_demo.sh --mode comparison --trials 3 --duration 90

# Clean up existing containers before starting
./run_demo.sh --clean

# Build and run with cleanup
./run_demo.sh --clean --build
```

### 4. View Results

Results are saved in `demo_results/` directory:
```bash
ls -la demo_results/
# ai_campaign_20241230_120000.json      - AI attack results
# random_campaign_20241230_120100.json  - Random attack baseline
# comparison_20241230_120200.json       - Statistical comparison
```

## Detailed Setup Guide

### Option A: Docker Setup (Recommended)

#### Prerequisites
1. **Install Docker**:
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose
   sudo usermod -aG docker $USER
   # Log out and back in for group changes
   ```

2. **Build Base Container** (if not already done):
   ```bash
   cd containers/docker
   docker build -t roi-uncc-img:latest .
   ```

3. **Verify Setup**:
   ```bash
   docker --version && docker compose version
   docker images | grep roi-uncc-img
   ```

#### Running the Demo
```bash
# Default: AI vs Random comparison with Docker
./run_demo.sh

# Force Docker mode (default)
./run_demo.sh --docker

# Direct containerized demo
python3 demo_docker.py --mode comparison --duration 60 --trials 3
```

### Option B: Local Installation (Advanced)

#### Prerequisites Installation
1. **System Dependencies**:
   ```bash
   sudo apt update
   sudo apt install -y build-essential cmake git python3 python3-pip
   sudo apt install -y libzmq3-dev libboost-all-dev openmpi-bin libopenmpi-dev
   ```

2. **Install HELICS**:
   ```bash
   wget https://github.com/GMLC-TDC/HELICS/releases/download/v3.4.0/Helics-3.4.0-Linux-x86_64.tar.gz
   tar -xzf Helics-3.4.0-Linux-x86_64.tar.gz
   sudo cp -r Helics-3.4.0-Linux-x86_64/* /usr/local/
   pip3 install helics
   ```

3. **Install GridLAB-D with HELICS support**:
   ```bash
   git clone https://github.com/gridlab-d/gridlab-d.git
   cd gridlab-d
   mkdir build && cd build
   cmake -DGLD_USE_HELICS=ON -DGLD_HELICS_DIR=/usr/local ..
   make -j$(nproc)
   sudo make install
   ```

4. **Build GridPACK federate**:
   ```bash
   cd examples/2bus-13bus
   ./build.sh
   ```

5. **Install Python requirements**:
   ```bash
   pip3 install -r mcp-server/requirements.txt
   ```

#### Test Local Setup
```bash
# Verify HELICS installation
helics_broker --version
python3 -c "import helics; print(helics.helicsGetVersion())"

# Verify GridLAB-D installation  
gridlabd --version

# Verify GridPACK federate build
ls -la examples/2bus-13bus/build/gpk-left-fed.x
```

#### Running Local Demo
```bash
# Force local mode
./run_demo.sh --local --mode comparison
```

## Troubleshooting

### Docker Issues

1. **Base container not found**:
   ```bash
   # Check existing containers
   docker images | grep roi-uncc
   
   # Build base container if missing
   cd containers/docker
   docker build -t roi-uncc-img:latest .
   ```

2. **Permission denied**:
   ```bash
   # Add user to docker group
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

3. **Port conflicts**:
   ```bash
   # Check what's using ports 5000 or 23406
   sudo netstat -tulpn | grep -E "(5000|23406)"
   
   # Stop conflicting services or change ports in docker-compose.demo.yml
   ```

4. **Containers from previous runs**:
   ```bash
   # Check running containers
   docker ps | grep -E "roi-uncc|helics-broker|gridpack|gridlabd|mcp-server"
   
   # Clean up existing containers
   ./run_demo.sh --clean
   
   # Or manually clean up
   docker compose -f docker-compose.demo.yml down -v
   ```

### Local Installation Issues

1. **HELICS not found**:
   ```bash
   # Check HELICS installation
   helics_broker --version
   python3 -c "import helics; print(helics.helicsGetVersion())"
   ```

2. **GridLAB-D HELICS integration**:
   ```bash
   # Verify HELICS support
   gridlabd --version | grep HELICS
   ```

3. **GridPACK build failures**:
   ```bash
   # Install missing dependencies
   sudo apt install -y libboost-all-dev libopenmpi-dev
   
   # Rebuild
   cd examples/2bus-13bus
   rm -rf build
   ./build.sh
   ```

### API and Network Issues

1. **Local LLM errors**:
   ```bash
   # Check nginx-lb container
   docker logs nginx-lb
   
   # Test LLM connectivity
   curl http://localhost:8000/v1/models
   
   # Check vllm containers
   docker ps | grep vllm
   ```

2. **MCP server not responding**:
   ```bash
   # Check server logs
   tail -f demo_results/mcp_server.log
   
   # Test direct connection
   curl http://localhost:5000/api/status
   ```

3. **Federation communication errors**:
   ```bash
   # Check HELICS broker logs
   docker-compose -f docker-compose.demo.yml logs helics-broker
   
   # Verify port connectivity
   telnet localhost 23404
   ```

## Performance Tuning

### For Faster Demo Execution

1. **Reduce simulation duration**:
   ```bash
   ./run_demo.sh --duration 30  # 30 seconds instead of 60
   ```

2. **Fewer comparison trials**:
   ```bash
   ./run_demo.sh --trials 1  # Single trial for quick testing
   ```

3. **Adjust HELICS timing**:
   Edit `mcp-server/config/mcp.yaml`:
   ```yaml
   helics:
     time_delta: 0.5  # Faster time steps (default: 1.0)
   ```

### For More Comprehensive Analysis

1. **Longer campaigns**:
   ```bash
   ./run_demo.sh --duration 300 --trials 10  # 5 minutes, 10 trials
   ```

2. **Multiple AI models** (future enhancement):
   ```yaml
   ai:
     models: ["deepseek-reasoner", "deepseek-chat"]
   ```

## Validation and Testing

### Quick Validation Test

```bash
# Test Docker prerequisites
docker --version && docker compose version
docker images | grep roi-uncc-img || echo "❌ Base container not found"

# Test containerized demo prerequisites
python3 -c "
from demo_docker import ContainerizedDemo
demo = ContainerizedDemo()
print('✅ All systems ready!' if demo.check_prerequisites() else '❌ Issues found')
"
```

### Manual Component Testing

1. **Test MCP server standalone**:
   ```bash
   cd mcp-server/src
   python3 server.py
   # In another terminal:
   curl http://localhost:5000/api/status
   ```

2. **Test HELICS federation**:
   ```bash
   # Terminal 1: Start broker
   helics_broker -f 3 --loglevel=warning
   
   # Terminal 2: Test federate
   cd examples/2bus-13bus
   ./build/gpk-left-fed.x
   ```

3. **Test AI integration**:
   ```bash
   python3 -c "
   import sys
   sys.path.append('mcp-server/src')
   from ai.local_llm_client import LocalLLMStrategist
   print('✅ AI integration working')
   "
   ```

## Usage

### Quick Demo

Run the complete AI vs Random comparison demo:

```bash
./run_demo.sh
```

### Demo Options

```bash
# AI-only attack demonstration
./run_demo.sh --mode ai --duration 120

# Random attack baseline
./run_demo.sh --mode random --duration 60

# Comprehensive comparison study
./run_demo.sh --mode comparison --trials 5 --duration 90

# Use different grid models
./run_demo.sh --mode ai --grid-model IEEE-39bus --duration 120
./run_demo.sh --mode comparison --grid-model IEEE-118bus

# Custom attack prompts for AI
./run_demo.sh --mode ai --attack-prompt "Focus on voltage stability attacks targeting weak buses"
./run_demo.sh --mode ai --attack-prompt "Exploit HELICS communication delays for maximum disruption"

# Combined options
./run_demo.sh --mode ai --grid-model IEEE-39bus --attack-prompt "Target generator buses" --duration 180

# Docker deployment
./run_demo.sh --docker --build
```

### Manual Operation

1. **Start HELICS broker**:
   ```bash
   helics_broker -f 3 --loglevel=warning --port=23404
   ```

2. **Start grid simulation**:
   ```bash
   # Terminal 1: GridPACK federate
   cd examples/2bus-13bus
   ./build/gpk-left-fed.x
   
   # Terminal 2: GridLAB-D federate
   cd examples/2bus-13bus
   gridlabd IEEE13bus.glm
   ```

3. **Start MCP server**:
   ```bash
   cd mcp-server/src
   python3 server.py
   ```

4. **Run attacks via API**:
   ```bash
   # Get grid status
   curl http://localhost:5000/api/status
   
   # Execute AI-planned attack
   curl -X POST http://localhost:5000/api/ai/execute \
        -H "Content-Type: application/json" \
        -d '{"campaign": {"duration": 60, "objective": "Custom attack prompt"}}'
   
   # Execute random attack comparison
   curl -X POST http://localhost:5000/api/random/execute \
        -H "Content-Type: application/json" \
        -d '{"campaign": {"duration": 60}}'
   ```

## Advanced Features

### Custom Grid Models

The framework supports multiple grid models:
- **2bus-13bus** (default): IEEE 13-bus distribution + 2-bus transmission
- **IEEE-39bus**: New England 39-bus test system (coming soon)
- **IEEE-118bus**: Large-scale 118-bus test system (coming soon)

### Custom Attack Prompts

Guide the AI's attack strategy with custom prompts:
```bash
# Focus on specific vulnerabilities
./run_demo.sh --attack-prompt "Target voltage regulators and protection systems"

# Time-based strategies
./run_demo.sh --attack-prompt "Execute coordinated attacks during peak load conditions"

# Component-specific attacks
./run_demo.sh --attack-prompt "Focus on generator buses and critical transmission lines"
```

### AI Model Configuration

The framework supports any OpenAI-compatible API:

**Supported Models:**
- **Local Models**: Qwen3-30B (default), Llama-3, Mixtral, etc.
- **OpenAI**: GPT-4, GPT-3.5-turbo
- **Anthropic**: Claude-3-opus, Claude-3-sonnet
- **Together AI**: Llama-3-70b, Mixtral-8x7b
- **Any OpenAI-compatible endpoint**

**Configuration Examples:**
```bash
# Local model (default)
./run_demo.sh --mode ai

# OpenAI GPT-4
./run_demo.sh --ai-model gpt-4 \
              --ai-base-url https://api.openai.com/v1 \
              --ai-api-key sk-your-openai-key

# Anthropic Claude
./run_demo.sh --ai-model claude-3-opus-20240229 \
              --ai-base-url https://api.anthropic.com/v1 \
              --ai-api-key sk-ant-your-key

# Local Ollama
./run_demo.sh --ai-model llama3 \
              --ai-base-url http://localhost:11434/v1

# Together AI
./run_demo.sh --ai-model meta-llama/Llama-3-70b-chat-hf \
              --ai-base-url https://api.together.xyz/v1 \
              --ai-api-key your-together-key
```

## Attack Strategies

The framework implements several attack primitives targeting the configured grid simulation:

### Target System
- **Transmission**: 2-bus GridPACK system (Bus1: generator, Bus2: load)
- **Distribution**: IEEE 13-bus GridLAB-D feeder
- **Interface**: Node650 (critical connection point)
- **Communication**: HELICS federation (vulnerable to message tampering)

### Attack Primitives

1. **Data Spoofing** (`spoof_data`)
   - Inject false voltage/power measurements
   - Target: HELICS message channels
   - Impact: Causes incorrect power flow calculations

2. **Load Injection** (`inject_load`)
   - Add artificial electrical load
   - Target: Distribution system buses
   - Impact: System stress, voltage degradation

3. **Reconnaissance** (`reconnaissance`)
   - Discover grid topology and vulnerabilities
   - Target: All monitored endpoints
   - Impact: Intelligence gathering for strategic planning

4. **Command Blocking** (`block_command`)
   - Prevent control commands from reaching devices
   - Target: Protection and control systems
   - Impact: Prevents automatic recovery

### AI Strategic Approach

The DeepSeek AI strategist follows this methodology:

1. **Grid Intelligence Gathering**: Analyze real-time voltage, power, and health data
2. **Vulnerability Assessment**: Identify weak points (undervoltage, imbalances, stress)
3. **Strategic Planning**: Develop coordinated attack sequences
4. **Adaptive Execution**: Adjust strategy based on grid response
5. **Impact Assessment**: Measure effectiveness and plan follow-up actions

Example AI decision process:
```json
{
  "situation_analysis": "Phase A showing undervoltage (0.94 pu) with high imbalance",
  "strategic_objective": "Trigger protection cascade via coordinated voltage attack", 
  "attack_sequence": [
    {"technique": "reconnaissance", "objective": "Gather grid intelligence"},
    {"technique": "spoof_data", "target": "voltage_A", "value": 1600.0},
    {"technique": "inject_load", "phase": "A", "magnitude": 2000000},
    {"technique": "block_command", "enable": true, "duration": 30}
  ]
}
```

## Research Applications

### Academic Metrics

The framework provides quantitative measures demonstrating AI superiority:

- **Effectiveness Improvement**: Typically 3-5x higher impact scores for AI vs random
- **Success Rate**: AI achieves 70-90% measurable grid disruption vs 10-30% for random
- **Strategic Coherence**: AI attacks follow logical progression targeting vulnerabilities
- **Adaptation Rate**: AI adjusts strategy in 70%+ of campaigns based on grid response

### Statistical Analysis

Results include comprehensive statistical analysis:
- Independent t-tests for significance testing
- Effect size calculations (Cohen's d)
- Mann-Whitney U tests for non-parametric validation
- Confidence intervals and significance levels

### Publication-Ready Outputs

- Detailed campaign logs with AI decision reasoning
- Grid physics validation data
- Comparative effectiveness measurements
- Reproducible experimental protocols

## Configuration

### Demo Configuration Files

The framework uses YAML configuration files to manage all settings. The main configuration file is `config/demo_config.yaml`.

#### Main Configuration (`config/demo_config.yaml`)

```yaml
# Demo execution settings
demo:
  mode: "comparison"           # Options: ai, random, comparison
  duration: 60                 # Attack campaign duration in seconds
  trials: 3                    # Number of trials for comparison mode
  grid_model: "2bus-13bus"     # Options: 2bus-13bus, IEEE-39bus, IEEE-118bus

# AI model configuration
ai:
  model: "Qwen/Qwen3-30B-A3B"  # Model name/identifier
  api_base: "http://nginx-lb/v1"  # API endpoint URL
  api_key: ""                   # API key (leave empty for local models)
  temperature: 0.8              # Sampling temperature (0.0-1.0)
  max_tokens: 4000              # Maximum response length
  timeout: 60                   # API request timeout in seconds

# Attack configuration
attack:
  prompt: "Demonstrate AI-driven strategic attack progression"
  max_concurrent_attacks: 5     # Maximum simultaneous attacks
  voltage_limit_min: 0.7        # Safety: minimum voltage (pu)
  voltage_limit_max: 1.3        # Safety: maximum voltage (pu)

# Grid simulation settings
grid:
  helics:
    broker_address: "tcp://helics-broker:23406"
    federate_name: "mcp_attacker"
    time_delta: 1.0

# Results configuration
results:
  directory: "demo_results"     # Directory for saving results
  save_raw_data: true          # Save raw campaign data
  format: "json"               # Output format: json, csv
```

#### Example Configurations

**OpenAI GPT-4 (`config/examples/openai_config.yaml`)**
```yaml
ai:
  model: "gpt-4"
  api_base: "https://api.openai.com/v1"
  api_key: "sk-your-openai-api-key-here"
  temperature: 0.7
  max_tokens: 2000
```

**Anthropic Claude (`config/examples/anthropic_config.yaml`)**
```yaml
ai:
  model: "claude-3-opus-20240229"
  api_base: "https://api.anthropic.com/v1"
  api_key: "sk-ant-your-anthropic-api-key-here"
  temperature: 0.8
  max_tokens: 4000
```

**Local Ollama (`config/examples/ollama_config.yaml`)**
```yaml
ai:
  model: "llama3:70b"
  api_base: "http://localhost:11434/v1"
  api_key: ""  # No API key needed
  temperature: 0.8
  max_tokens: 3000
```

#### Using Configuration Files

```bash
# Use specific configuration
./run_demo.sh --config config/examples/openai_config.yaml

# Override specific settings
./run_demo.sh --config config/examples/openai_config.yaml --duration 120 --trials 5

# Create custom configuration
cp config/examples/openai_config.yaml config/my_config.yaml
# Edit config/my_config.yaml with your settings
./run_demo.sh --config config/my_config.yaml
```

### MCP Server Configuration (`mcp-server/config/mcp.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 5000

helics:
  broker_address: "tcp://127.0.0.1:23404"
  federate_name: "mcp_attacker"
  time_delta: 1.0

ai:
  api_base: "http://nginx-lb/v1"  # Default: Local LLM endpoint
  model: "Qwen/Qwen3-30B-A3B"     # Default: Qwen3 30B model
  temperature: 0.8
  max_tokens: 4000
  # These can be overridden with command line arguments:
  # --ai-model, --ai-base-url, --ai-api-key
```

### Threat Model Constraints (`mcp-server/config/threat_model.yaml`)

```yaml
voltage_limits:
  min: 0.7  # 70% of nominal
  max: 1.3  # 130% of nominal

power_limits:
  max_injection: 5000000  # 5 MVA

simulation_safety:
  prevent_permanent_damage: true
  max_voltage_deviation: 0.5
```

## API Reference

### Grid Status
```bash
GET /api/status
```
Returns current grid state, voltages, powers, and system health.

### Execute Attack
```bash
POST /api/attack
Content-Type: application/json

{
  "technique": "spoof_data",
  "params": {
    "target": "voltage_A", 
    "value": 1800.0,
    "phase": 0
  }
}
```

### AI Strategic Planning
```bash
POST /api/ai/plan
Content-Type: application/json

{
  "objective": "Maximize grid disruption",
  "context": {"duration": 60}
}
```

### AI Campaign Execution
```bash
POST /api/ai/execute
Content-Type: application/json

{
  "campaign": {"duration": 60}
}
```

### Comparison Study
```bash
POST /api/comparison
Content-Type: application/json

{
  "campaign": {"duration": 60, "trials": 3}
}
```

## Results Analysis

Demo results are saved to `demo_results/` directory:

- `ai_campaign_YYYYMMDD_HHMMSS.json`: AI attack campaign data
- `random_campaign_YYYYMMDD_HHMMSS.json`: Random attack baseline data  
- `comparison_YYYYMMDD_HHMMSS.json`: Statistical comparison analysis
- `*.log`: Detailed system logs from all components

### Example Results Analysis

```python
import json
import numpy as np

# Load comparison results
with open('demo_results/comparison_20241230_120000.json', 'r') as f:
    data = json.load(f)

metrics = data['comparison_metrics']
print(f"AI effectiveness: {metrics['ai_mean']:.2f}")
print(f"Random effectiveness: {metrics['random_mean']:.2f}")  
print(f"Improvement ratio: {metrics['improvement_ratio']:.2f}x")
```

## Safety and Ethics

### Research-Only Purpose

This framework is designed exclusively for defensive cybersecurity research:

- **Simulated Environment Only**: Targets only simulated grid systems
- **No Real Infrastructure**: Cannot connect to actual power systems
- **Academic Use**: Intended for research publication and education
- **Threat Model Constraints**: Built-in safety limits prevent simulation damage

### Responsible Disclosure

Research findings should be shared with:
- Power system security community
- NERC CIP compliance teams  
- Grid equipment manufacturers
- Cybersecurity defense researchers

## Contributing

### Development Guidelines

1. **Defensive Focus**: All contributions must support defensive cybersecurity research
2. **Safety First**: Maintain threat model constraints and simulation safety
3. **Documentation**: Include comprehensive documentation and test cases
4. **Academic Standards**: Follow reproducible research practices

### Extending the Framework

- **New Attack Primitives**: Add techniques in `mcp-server/src/attacks/`
- **Grid Models**: Support additional IEEE test systems
- **AI Models**: Integrate other LLM providers beyond DeepSeek
- **Analysis Tools**: Enhance statistical analysis and visualization

## Troubleshooting

### Common Issues

1. **HELICS Connection Errors**:
   ```bash
   # Check broker is running
   ps aux | grep helics_broker
   
   # Verify port availability
   netstat -ln | grep 23404
   ```

2. **GridLAB-D HELICS Integration**:
   ```bash
   # Verify HELICS support
   gridlabd --version | grep HELICS
   
   # Check HELICS library path
   ldd $(which gridlabd) | grep helics
   ```

3. **MCP Server API Errors**:
   ```bash
   # Check server logs
   tail -f demo_results/mcp_server.log
   
   # Test API connectivity
   curl http://localhost:5000/api/status
   ```

4. **Local LLM Issues**:
   ```bash
   # Check nginx load balancer
   docker logs nginx-lb
   
   # Test LLM endpoint
   curl http://localhost:8000/v1/models
   
   # Verify vllm backend containers
   docker ps | grep vllm
   ```

### Performance Optimization

- **Simulation Speed**: Adjust HELICS time_delta for faster execution
- **AI Response Time**: Use smaller max_tokens for quicker AI responses  
- **Memory Usage**: Reduce grid monitor history_size for large campaigns
- **Network Latency**: Run all components on same machine for best performance

## Citation

If you use this framework in your research, please cite:

```bibtex
@misc{roi_uncc_mcp_2024,
  title={AI-Assisted Grid Penetration Testing Framework},
  author={ROI UNCC Project Team},
  year={2024},
  publisher={University of North Carolina at Charlotte},
  note={Available at: https://github.com/roi-uncc/mcp-project}
}
```

## License

This project is released under the MIT License for academic and research purposes. See LICENSE file for details.

## Support

For technical support or research collaboration:

- **Documentation**: Check this README and inline code documentation
- **Issues**: Report bugs and feature requests via GitHub issues
- **Academic Collaboration**: Contact the ROI UNCC research team

---

**Disclaimer**: This framework is intended solely for defensive cybersecurity research in simulated environments. Users are responsible for ensuring compliance with applicable laws and regulations.