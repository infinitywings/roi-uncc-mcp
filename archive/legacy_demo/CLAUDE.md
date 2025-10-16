# ROI UNCC MCP Project - AI Assistant Memory

## Project Overview
**AI-Assisted Grid Penetration Testing Framework** for defensive cybersecurity research on power grid systems at University of North Carolina at Charlotte (UNCC).

## Purpose
This framework enables AI models to conduct strategic penetration testing on simulated power grid systems to:
- Identify vulnerabilities in grid cyber-defenses
- Develop defensive countermeasures
- Improve critical infrastructure protection
- Compare AI-assisted vs random attack effectiveness

## System Architecture

### Core Components
1. **MCP Server** (Model Context Protocol)
   - Flask REST API at port 5000
   - Bridge between AI models and grid simulation
   - Located in `/mcp-server/src/server.py`

2. **HELICS Federation**
   - Real-time co-simulation platform
   - Synchronizes GridLAB-D and GridPACK
   - Message-based communication

3. **Grid Simulators**
   - **GridLAB-D**: IEEE 13-bus distribution model
   - **GridPACK**: 2-bus transmission system
   - Real physics calculations

4. **Attack Engine**
   - Implements attack primitives
   - Located in `/mcp-server/src/attacks/attack_engine.py`
   - Techniques: spoof_data, inject_load, reconnaissance, block_command

5. **AI Integration**
   - Supports OpenAI, Anthropic, local models (Ollama)
   - Strategic attack planning
   - Located in `/mcp-server/src/ai/local_llm_client.py`

## Docker Setup
- **Base Image**: `roi-img:latest` (contains HELICS, GridLAB-D, GridPACK)
- **MCP Image**: `roi-uncc-mcp:latest` (MCP server)
- **Network**: host mode for HELICS communication
- **Status**: ✅ Image name issue fixed (was incorrectly referencing roi-uncc-img:latest)

## Key API Endpoints
- `GET /api/status` - Grid state and health
- `POST /api/attack` - Execute attack primitive
- `GET /api/reconnaissance` - Discover topology
- `POST /api/ai/plan` - AI attack planning
- `POST /api/ai/execute` - Execute AI campaign
- `POST /api/comparison` - Compare AI vs random

## Safety Features
- Threat model validation
- Parameter bounds checking
- Simulation-only environment
- Audit logging
- No real grid connection

## Current AI API Configuration
- **Model**: openai/gpt-oss-120b (120B parameter model)
- **Endpoint**: http://ccil1s26m8hj6lws:8000/v1
- **Provider**: vLLM local server
- **Context Length**: 131,072 tokens
- **API Key**: Not required (local deployment)

## Recent Code Review Fixes (2025-01-16)

### Critical Issues Fixed
1. **Missing GridMonitor Methods**
   - Added `get_current_state()` with monitoring metadata
   - Added `get_vulnerability_assessment()` with risk analysis
   - Implemented anomaly detection logic
   - Fixed runtime errors in AI strategist calls

2. **Configuration Path Issues**
   - Removed hardcoded `/app/mcp-server/config/` paths
   - Implemented auto-detection with fallback chain
   - Now works in both Docker and local environments

3. **YAML Import Handling**
   - Added proper import error handling
   - Graceful fallback to defaults
   - Warning messages for missing PyYAML

### Code Quality Assessment
**Strengths:**
- Well-structured modular design
- Good separation of concerns
- Comprehensive error handling
- Clear defensive research focus

**Areas for Improvement:**
- Add authentication mechanism
- Create unit test suite
- Add rate limiting
- Implement WebSocket for real-time updates

## Attack Primitives

### Available Techniques
1. **spoof_data**: Inject false voltage/power measurements
2. **inject_load**: Add artificial load to stress grid
3. **reconnaissance**: Discover grid topology and vulnerabilities
4. **block_command**: Prevent control commands

### Parameter Validation
- Voltage: 0.7-1.3 per unit
- Power: Max 5 MVA injection
- Timing: Min 1s between attacks
- Duration: Max 300s

## Configuration Files
- `/mcp-server/config/mcp.yaml` - Server configuration
- `/mcp-server/config/threat_model.yaml` - Safety constraints
- `/config/demo_config.yaml` - Main demo configuration
- `/config/2bus_13bus_attack_demo.yaml` - **NEW**: Optimized 2bus-13bus attack demo
- `/config/examples/` - Example configs for different AI providers

## Testing Recommendations
1. Unit tests for attack_engine, federate, monitor
2. Integration tests for HELICS federation
3. End-to-end attack simulation tests
4. AI strategist integration tests

## Deployment Notes
- **Current State**: Ready for development/research use
- **Production Readiness**: 70% - needs auth, tests, monitoring
- **Docker Deployment**: Fully containerized
- **Simulation Models**: IEEE 13-bus + 2-bus ready

## Important Files
- `/mcp-server/src/server.py` - Main REST API server
- `/mcp-server/src/federate.py` - HELICS federate implementation  
- `/mcp-server/src/attacks/attack_engine.py` - Attack execution
- `/mcp-server/src/ai/local_llm_client.py` - AI integration
- `/mcp-server/src/monitor/grid_monitor.py` - Grid state monitoring
- `/mcp-server/src/utils/validation.py` - Threat model validation

## Run Commands
```bash
# Start HELICS broker
docker run -d --name helics-broker --network host roi-img:latest helics_broker -f 3 --loglevel=debug --port=23406

# Start MCP server
docker run -d --name mcp-server --network host roi-uncc-mcp:latest

# Run standard demo
./run_demo.sh --mode comparison --iterations 3

# Run optimized 2bus-13bus attack demo (RECOMMENDED)
./run_demo.sh --config config/2bus_13bus_attack_demo.yaml --mode comparison --trials 5
```

## Security Context
This framework is explicitly designed for **DEFENSIVE CYBERSECURITY RESEARCH** in controlled simulation environments. All attack capabilities are intended to identify vulnerabilities that can be addressed to improve real grid security. The system includes multiple safety constraints to prevent misuse and ensure research integrity.

## Next Development Priorities
1. Add API authentication
2. Create comprehensive test suite
3. Document API with OpenAPI/Swagger
4. Add Prometheus metrics
5. Implement WebSocket for real-time monitoring
6. Performance optimization with asyncio

---
*Last Updated: 2025-01-16*
*Purpose: Defensive Cybersecurity Research*
*Environment: Simulated IEEE Test Systems Only*