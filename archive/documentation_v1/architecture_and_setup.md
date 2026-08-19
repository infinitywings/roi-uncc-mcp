# Architecture and Setup Guide

This guide describes the code structure of the ROI UNCC MCP project and how to run the demonstration environment.

## Code Architecture
```text
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
│  - Distribution grid        │   │  - Transmission grid        │
│  - Load/generation models   │   │  - Stability analysis       │
└─────────────────────────────┘   └─────────────────────────────┘
```

## Getting Started

### Prerequisites
- Docker and Docker Compose (recommended)
- Or local installation: Ubuntu 22.04, Python 3.8+, HELICS, GridLAB-D, GridPACK
- An OpenAI-compatible LLM endpoint or local model

### Quick Start
```bash
# Verify Docker setup
docker --version && docker compose version

# Run demo with default local model
./run_demo.sh

# Use custom AI model configuration
./run_demo.sh --config config/examples/openai_config.yaml
```

The HELICS broker listens on `tcp://helics-broker:23406`; ensure this port is available before starting the demo.

