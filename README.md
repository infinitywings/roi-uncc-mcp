# AI-Assisted Grid Penetration Testing Framework

ROI UNCC MCP Project - Research framework for studying power grid cybersecurity using AI-driven attack strategies.

## Overview

This project implements a Model Context Protocol (MCP) server that enables AI models to conduct strategic penetration testing on simulated power grid systems. The framework demonstrates how AI-assisted attacks can be significantly more effective than random approaches, providing valuable insights for defensive cybersecurity research.

### Key Features

- **AI-Powered Strategic Planning**: AI analyzes grid state and plans coordinated attack sequences
- **Real Physics Simulation**: GridLAB-D + GridPACK co-simulation with actual electrical calculations
- **HELICS Integration**: Real-time federated simulation for authentic attack-defense scenarios
- **Comprehensive Attack Primitives**: Data spoofing, load injection, reconnaissance, command blocking
- **Threat Model Validation**: Safety constraints prevent simulation damage
- **Performance Comparison**: Quantitative analysis of AI vs random attack effectiveness

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AI Layer (LLM Models)                       │
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
└─────────────────────────────┘   └─────────────────────────────┘
```

## Prerequisites

### System Requirements
- **CPU**: Multi-core processor (4+ cores recommended)
- **Memory**: Minimum 16GB RAM (32GB+ recommended for AI models)
- **Storage**: 20GB+ free disk space
- **OS**: Linux (Ubuntu 20.04+ recommended) or macOS with Docker

### Software Requirements
- **Docker**: Version 20.10+ with docker-compose v2.0+
- **Git**: For repository management
- **Python**: 3.8+ (if running locally)

### AI Model Options
- **Local Models**: Ollama, LM Studio, or any OpenAI-compatible local server
- **Cloud APIs**: OpenAI GPT-4, Anthropic Claude, or other compatible APIs
- **Default**: Configured for local Qwen3 model

## Quick Start (Docker - Recommended)

### 1. Clone the Repository
```bash
git clone https://github.com/infinitywings/roi-uncc-mcp.git
cd roi-uncc-mcp
```

### 2. Build Docker Images
```bash
# Build the base image with HELICS, GridLAB-D, and GridPACK
cd containers/docker
docker build -t roi-uncc-img .
cd ../..

# Build the MCP server image
docker build -f docker/Dockerfile.mcp -t roi-uncc-mcp:latest .
```

### 3. Configure AI Model

**Option A: Use Pre-configured Examples**
```bash
# For OpenAI GPT-4
./run_demo.sh --config config/examples/openai_config.yaml

# For Anthropic Claude
./run_demo.sh --config config/examples/anthropic_config.yaml

# For local Ollama
./run_demo.sh --config config/examples/ollama_config.yaml

# For local Qwen3 (default)
./run_demo.sh --config config/examples/local_qwen_config.yaml
```

**Option B: Create Custom Configuration**
```bash
cp config/demo_config.yaml config/my_config.yaml
# Edit my_config.yaml with your AI provider settings
./run_demo.sh --config config/my_config.yaml
```

### 4. Run the Demo

**Basic Demo (AI vs Random Comparison)**
```bash
./run_demo.sh --mode comparison --iterations 3
```

**AI-Only Attack Demo**
```bash
./run_demo.sh --mode ai --duration 300
```

**Random Attack Demo**
```bash
./run_demo.sh --mode random --duration 300
```

### 5. Monitor Results

The demo will output:
- Real-time attack progress
- Grid state changes
- Performance metrics
- Comparison statistics (in comparison mode)

Results are saved to `demo_results/` directory with timestamps.

## Detailed Installation

### Using Docker Compose (Automated)

```bash
# Start all services
docker-compose -f docker/docker-compose.demo.yml up -d

# Run the demo
python demo.py --config config/demo_config.yaml

# Clean up
docker-compose -f docker/docker-compose.demo.yml down
```

### Manual Docker Setup

```bash
# 1. Build GridPACK federate (if not already built)
cd examples/2bus-13bus && ./build.sh && cd ../..

# 2. Start HELICS broker
docker run -d --name helics-broker --network host \
  roi-uncc-img helics_broker -f 3 --loglevel=debug --port=23406

# 3. Start GridPACK federate
docker run -d --name gridpack-federate --network host \
  -v $(pwd)/examples/2bus-13bus:/workspace \
  roi-uncc-img /workspace/build/gpk-left-fed.x

# 4. Start GridLAB-D federate
docker run -d --name gridlabd-federate --network host \
  -v $(pwd)/examples/2bus-13bus:/workspace \
  roi-uncc-img gridlabd -D USE_HELICS=1 /workspace/IEEE13bus.glm

# 5. Start MCP server
docker run -d --name mcp-server --network host \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/API.txt:/app/API.txt:ro \
  roi-uncc-mcp:latest

# 6. Run attack demo
python demo.py --mode comparison
```

## Configuration

### Main Configuration File (`config/demo_config.yaml`)

```yaml
# AI Model Configuration
ai:
  model: "Qwen/Qwen3-30B-A3B"
  api_base: "http://nginx-lb/v1"  # Or http://localhost:1234/v1 for local
  temperature: 0.8
  max_tokens: 4000

# OpenAI Settings (if using)
openai:
  api_key: "sk-..."  # Or use API.txt file
  model: "gpt-4"
  temperature: 0.7

# Attack Configuration
attack:
  max_iterations: 10
  time_per_iteration: 30
  safety_constraints:
    max_voltage_deviation: 0.15
    max_power_injection: 1000
    block_critical_nodes: true

# Simulation Settings
simulation:
  duration: 300
  timestep: 1
  broker_address: "tcp://127.0.0.1:23406"
```

### API Key Management

For cloud AI providers, store your API key in `API.txt`:
```bash
echo "your-api-key-here" > API.txt
chmod 600 API.txt
```

## API Endpoints

The MCP server exposes the following REST API endpoints:

### Grid Status
```bash
GET /api/status
```
Returns current grid state including voltages, power flows, and device status.

### Execute Attack
```bash
POST /api/attack
{
  "type": "spoof_data",
  "target": "meter_1",
  "parameters": {
    "voltage": 1.05,
    "duration": 10
  }
}
```

### AI-Planned Attack
```bash
POST /api/ai/execute
{
  "objective": "maximize_impact",
  "context": {
    "time_limit": 300,
    "stealth": true
  }
}
```

### Compare Strategies
```bash
POST /api/comparison
{
  "iterations": 5,
  "duration_per_iteration": 60
}
```

## Attack Primitives

### 1. Data Spoofing
Manipulate sensor readings to hide actual grid state
```python
attack = {
    "type": "spoof_data",
    "target": "voltage_sensor_1",
    "fake_value": 1.0,
    "duration": 30
}
```

### 2. Load Injection
Inject false load to cause imbalance
```python
attack = {
    "type": "inject_load",
    "bus": "bus_671",
    "power_kw": 500,
    "duration": 60
}
```

### 3. Command Blocking
Prevent legitimate control commands
```python
attack = {
    "type": "block_command",
    "device": "switch_1",
    "duration": 120
}
```

### 4. Reconnaissance
Discover grid topology and vulnerabilities
```python
attack = {
    "type": "reconnaissance",
    "scope": "full"
}
```

## Running Experiments

### Basic Attack Sequence
```bash
# 1. Start the simulation environment
./run_demo.sh --setup

# 2. Run AI-assisted attack
./run_demo.sh --mode ai --objective "cause_blackout" --duration 600

# 3. Analyze results
python analyze_results.py demo_results/latest/
```

### Comparative Analysis
```bash
# Run comparison experiment
./run_demo.sh --mode comparison --iterations 10 --save-results

# Generate report
python generate_report.py demo_results/comparison_*/
```

### Custom Attack Campaigns
```python
# demo_custom_attack.py
from demo_launcher import DemoLauncher

launcher = DemoLauncher(config_file="config/custom.yaml")
launcher.initialize()

# Define attack sequence
attacks = [
    {"type": "reconnaissance"},
    {"type": "spoof_data", "target": "critical_sensor"},
    {"type": "inject_load", "bus": "weakest_bus", "power": 1000},
    {"type": "block_command", "device": "protection_relay"}
]

results = launcher.execute_campaign(attacks)
launcher.save_results(results)
```

## Monitoring and Visualization

### Real-time Monitoring
```bash
# Watch grid state
docker exec mcp-server python -m mcp_server.monitor.grid_monitor

# View HELICS federation
docker exec helics-broker helics_broker_server --query federates

# Check server status
curl http://localhost:5000/api/status
```

### Visualization Dashboard
```bash
# Start visualization server (if available)
python -m mcp_server.visualization.dashboard

# Open browser to http://localhost:8050
```

## Troubleshooting

### Common Issues

#### Docker Connection Issues
```bash
# Check Docker daemon
docker ps

# Verify network
docker network ls

# Check container logs
docker logs mcp-server
docker logs helics-broker
```

#### HELICS Federation Errors
```bash
# Verify broker is running
docker exec helics-broker helics_broker_server --query isconnected

# Check federate registration
docker exec helics-broker helics_broker_server --query federates

# Review HELICS logs
docker logs helics-broker | grep ERROR
```

#### AI Model Connection Issues
```bash
# Test AI endpoint
curl http://localhost:1234/v1/models

# For OpenAI/Anthropic
python -c "import openai; openai.api_key='your-key'; print(openai.Model.list())"

# Check Ollama
ollama list
```

#### GridLAB-D/GridPACK Issues
```bash
# Verify GridLAB-D model
docker exec gridlabd-federate gridlabd --validate IEEE13bus.glm

# Check GridPACK build
docker exec gridpack-federate /workspace/build/gpk-left-fed.x --help

# Monitor federation timing
docker exec helics-broker helics_broker_server --query current_time
```

### Debug Mode

Enable detailed logging:
```bash
# Set debug environment variables
export HELICS_LOG_LEVEL=debug
export MCP_DEBUG=true

# Run with verbose output
./run_demo.sh --debug --verbose

# Check detailed logs
tail -f demo_results/latest/debug.log
```

### Performance Optimization

1. **Reduce simulation fidelity** for faster experiments:
```yaml
simulation:
  timestep: 10  # Increase from 1
  fast_mode: true
```

2. **Use smaller AI models** for quicker response:
```yaml
local_llm:
  model: "qwen3-7b"  # Instead of 30b
```

3. **Limit attack complexity**:
```yaml
attack:
  max_primitives_per_iteration: 3
  simple_mode: true
```

## Project Structure

```
roi-uncc-mcp/
├── mcp-server/           # MCP server implementation
│   ├── src/
│   │   ├── server.py     # Flask REST API
│   │   ├── federate.py   # HELICS federate
│   │   ├── attacks/      # Attack primitives
│   │   ├── ai/          # AI integration
│   │   └── monitor/     # Grid monitoring
│   └── config/
├── scripts/             # Demo and utility scripts
│   ├── demo_docker.py   # Docker demo launcher
│   ├── demo_launcher.py # Native demo launcher
│   └── demo_attack_scenario.py
├── docker/              # Docker configuration
│   ├── Dockerfile.mcp
│   ├── docker-compose.demo.yml
│   └── docker-compose.yml
├── documentation/       # Project documentation
│   ├── architecture_and_setup.md
│   ├── research_overview.md
│   └── PROJECT_STATUS.md
├── examples/            # Simulation models
│   └── 2bus-13bus/     # GridLAB-D and GridPACK models
├── config/             # Configuration files
│   ├── demo_config.yaml
│   └── examples/       # Pre-configured examples
├── containers/         # Base Docker images
│   └── docker/
├── demo_results/       # Experiment outputs
├── archive/            # Deprecated/old files
├── run_demo.sh        # Main demo launcher
├── demo.py            # Simple wrapper script
└── README.md
```

## Safety and Ethics

**IMPORTANT**: This framework is designed for defensive cybersecurity research only.

- All attacks are simulated in isolated environments
- Safety constraints prevent damage to real systems
- Threat model validation ensures realistic but safe scenarios
- Results should be used to improve grid defense mechanisms

## Contributing

We welcome contributions to improve the framework:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-attack-primitive`)
3. Commit your changes (`git commit -m 'Add new attack primitive'`)
4. Push to the branch (`git push origin feature/new-attack-primitive`)
5. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone git@github.com:YOUR_USERNAME/roi-uncc-mcp.git
cd roi-uncc-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/
```

## Citation

If you use this framework in your research, please cite:

```bibtex
@misc{roi_uncc_mcp_2024,
  title={AI-Assisted Grid Penetration Testing Framework},
  author={ROI UNCC Project Team},
  year={2024},
  publisher={University of North Carolina at Charlotte},
  url={https://github.com/infinitywings/roi-uncc-mcp}
}
```

## License

This project is released under the MIT License for academic and research purposes. See the LICENSE file for details.

## Support

- **Documentation**: Consult files in this repository
- **Issues**: Report bugs via [GitHub Issues](https://github.com/infinitywings/roi-uncc-mcp/issues)
- **Academic Collaboration**: Contact the ROI UNCC research team

---

**Disclaimer**: This framework is intended solely for defensive cybersecurity research in simulated environments. Users are responsible for ensuring compliance with applicable laws and regulations. Never use these tools against real infrastructure or without explicit permission.