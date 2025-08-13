# Project Structure

## Overview
This document describes the organization of the ROI UNCC MCP project repository.

## Directory Structure

```
roi-uncc-mcp/
│
├── mcp-server/                 # Core MCP server implementation
│   ├── src/                    # Source code
│   │   ├── server.py           # Flask REST API server
│   │   ├── federate.py         # HELICS federate implementation
│   │   ├── attacks/            # Attack primitive implementations
│   │   │   └── attack_engine.py
│   │   ├── ai/                 # AI model integration
│   │   │   └── local_llm_client.py
│   │   ├── monitor/            # Grid monitoring utilities
│   │   │   └── grid_monitor.py
│   │   └── utils/              # Utility functions
│   │       └── validation.py
│   ├── config/                 # MCP server configuration
│   │   ├── mcp.yaml
│   │   └── threat_model.yaml
│   └── requirements.txt        # Python dependencies
│
├── scripts/                    # Executable scripts
│   ├── demo_docker.py          # Docker-based demo launcher
│   ├── demo_launcher.py        # Native installation demo
│   └── demo_attack_scenario.py # Attack scenario demonstrations
│
├── docker/                     # Docker configuration files
│   ├── Dockerfile.mcp          # MCP server container
│   ├── docker-compose.demo.yml # Full demo orchestration
│   └── docker-compose.yml      # Basic service setup
│
├── config/                     # Demo configuration files
│   ├── demo_config.yaml        # Main demo configuration
│   └── examples/               # Pre-configured examples
│       ├── openai_config.yaml
│       ├── anthropic_config.yaml
│       ├── ollama_config.yaml
│       └── local_qwen_config.yaml
│
├── containers/                 # Base container definitions
│   └── docker/
│       └── Dockerfile          # Base image with HELICS, GridLAB-D, GridPACK
│
├── examples/                   # Simulation examples and models
│   ├── 2bus-13bus/            # Main demo grid model
│   ├── simple-cosim/          # Simple co-simulation example
│   ├── pf-cosim/              # Power flow co-simulation
│   └── lc-tank/               # LC tank circuit demo
│
├── documentation/              # Project documentation
│   ├── architecture_and_setup.md
│   ├── research_overview.md
│   ├── PROJECT_STATUS.md
│   ├── ARCHITECTURE_WORKFLOW.md
│   ├── ATTACK_SCENARIO_DEMO.md
│   └── DOCKER_FILES_USAGE.md
│
├── demo_results/               # Generated results (gitignored)
│
├── archive/                    # Deprecated/old files
│   └── old_docs/
│
├── run_demo.sh                 # Main entry point script
├── demo.py                     # Simple Python wrapper
├── README.md                   # Project documentation
├── API.txt                     # API keys (gitignored)
└── .gitignore                  # Git ignore rules
```

## Key Files

### Entry Points
- `run_demo.sh` - Main bash script for running demos with various options
- `demo.py` - Simple Python wrapper for the demo scripts

### Core Components
- `mcp-server/src/server.py` - REST API server for attack orchestration
- `mcp-server/src/federate.py` - HELICS federate for grid interaction
- `mcp-server/src/attacks/attack_engine.py` - Attack primitive implementations

### Configuration
- `config/demo_config.yaml` - Main configuration with all options
- `config/examples/` - Pre-configured examples for different AI providers

### Docker
- `docker/Dockerfile.mcp` - Builds MCP server container
- `docker/docker-compose.demo.yml` - Orchestrates full demo environment
- `containers/docker/Dockerfile` - Base image with simulation tools

## Usage

### Quick Start
```bash
# Run with default configuration
./run_demo.sh

# Or use Python wrapper
python demo.py --mode comparison
```

### Docker Operations
```bash
# Build images
docker build -f containers/docker/Dockerfile -t roi-uncc-img .
docker build -f docker/Dockerfile.mcp -t roi-uncc-mcp .

# Run with docker-compose
docker-compose -f docker/docker-compose.demo.yml up
```

### Development
- Add new attack primitives in `mcp-server/src/attacks/`
- Configure AI models in `config/examples/`
- Add documentation in `documentation/`
- Place deprecated files in `archive/`