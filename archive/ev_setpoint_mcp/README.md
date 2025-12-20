# EV Setpoint MCP Server (Attack Mode)

This standalone MCP server operates as an **adversarial interface** for AI-driven grid penetration testing on the 2bus-13bus co-simulation. It enables an AI attacker to inject malicious EV charging setpoints while the legitimate grid controller continues normal operation.

## Architecture: Red Team vs Blue Team

**Blue Team (Legitimate Operation)**:
- `1bc_EV_Controller.py` maintains normal peak-shaving operation
- Monitors feeder load (limit: 4.2 MW upper, 2.6 MW lower)
- Controls EV1 and EV4 islanding with battery storage during overload

**Red Team (AI Attacker)**:
- This MCP server provides attack primitives for AI adversaries
- Injects competing setpoints to disrupt grid stability
- Attack strategies: overload, reverse power injection, phase imbalance, timing attacks

## Features

### Observation Primitives (Reconnaissance)
- `get_grid_status` - Monitor real-time voltages, powers, and EV states
- `discover_topology` - Map transmission/distribution topology and vulnerabilities
- `monitor_protection_systems` - Track feeder load limits and protection status
- `analyze_power_flow` - Understand power flow patterns for attack targeting

### Action Primitive (Attack Execution)
- `set_ev_capacity` – **Inject malicious EV setpoints** that compete with legitimate controller
  - Normal operation: 200-220 kW per EV
  - Attack mode: Up to 4000 kW (4 MW) per EV to trigger protection/cascading failures
  - Supports negative setpoints for reverse power injection attacks

## Attack Mode Operation

The MCP server sends setpoints to the **same HELICS endpoints** as the legitimate controller (`gld_hlc_conn/EV1-6`). Since HELICS delivers messages chronologically, the **last message wins**. Attack strategies:

1. **Overload Attack**: Send 2-4 MW setpoints to stress grid beyond protection thresholds
2. **Reverse Power Injection**: Negative setpoints to disrupt power flow direction
3. **Phase Imbalance**: Target specific phases (CN, BN, AN) to cause voltage issues
4. **Timing Attack**: Coordinate with peak demand (15:00-17:00) to maximize impact
5. **Storage Exploitation**: Attack EV1/EV4 during islanding mode to drain batteries

The implementation reuses the existing 2bus-13bus co-simulation running in Docker. All configuration, source code, and attack logs live inside this folder to keep the attacker infrastructure self-contained.

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_server.py --config config/ev_mcp.yaml
```

The server listens on the host/port specified in `config/ev_mcp.yaml` (defaults to `0.0.0.0:5100`).

### Docker Deployment
If the 2bus-13bus co-simulation is running inside Docker, you can launch the MCP server in the same network:

```bash
# Ensure the simulation stack (helics-broker, gridlabd, gridpack, controller) is running
docker compose -f docker/docker-compose.demo.yml up -d

# Build and start the EV MCP container, attaching to the shared grid-network
docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build -d
```

The compose file expects an external `grid-network` (created automatically by the main demo stack). Environment variables are provided to the container so it reaches the HELICS broker at `tcp://helics-broker:23406`. To override at runtime:

```bash
EV_MCP_SERVER_PORT=5200 HELICS_BROKER_ADDRESS=tcp://helics-broker:23406 \
  docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up -d
```

The container exposes the REST API on port `5100` by default for AI clients (or the port you override via `EV_MCP_SERVER_PORT`).

Inside the shared Docker network (e.g., from another service such as an AI orchestrator), target `http://ev-setpoint-mcp:5100/primitive`. From the host machine, use `http://localhost:5100/primitive` (or the mapped port).

## Primitive Usage

### Observation Example
Send JSON requests to `POST /primitive` with the structure:
```json
{
  "method": "get_grid_status",
  "params": {}
}
```

### Attack Examples

**Benign setpoint (normal operation)**:
```json
{
  "method": "set_ev_capacity",
  "params": {
    "ev_id": "EV5",
    "real_power_kw": 180,
    "reactive_power_kvar": 0,
    "duration_s": 60
  }
}
```

**Overload attack (2 MW injection)**:
```json
{
  "method": "set_ev_capacity",
  "params": {
    "ev_id": "EV3",
    "real_power_kw": 2000,
    "reactive_power_kvar": 500,
    "duration_s": 300
  }
}
```

**Reverse power injection attack**:
```json
{
  "method": "set_ev_capacity",
  "params": {
    "ev_id": "EV1",
    "real_power_kw": -500,
    "reactive_power_kvar": 0,
    "duration_s": 120
  }
}
```

**Coordinated multi-EV attack (trigger cascading failure)**:
```bash
# Attack multiple EVs simultaneously to exceed feeder limit (4.2 MW)
curl -s http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV3","real_power_kw":3000,"reactive_power_kvar":0}}' &
curl -s http://localhost:5100/primitive -H "Content-Type: application/json" \
  -d '{"method":"set_ev_capacity","params":{"ev_id":"EV5","real_power_kw":2500,"reactive_power_kvar":0}}' &
wait
```

For sample responses and attack impact analysis, see `output/sample_responses.json` and `output/interaction_log.jsonl`.

## Folder Layout
- `config/ev_mcp.yaml` – server, HELICS, topology, and protection settings.
- `src/` – complete Python source for the server, federate wrapper, and primitive handlers.
- `output/` – example JSON responses.
- `run_server.py` – CLI entry point that loads configuration and starts the Flask service.
- `output/interaction_log.jsonl` – JSONL log capturing every primitive request/response for auditing AI activity.

## Requirements
- Python 3.9+
- HELICS 3.x runtime available in the environment.

The server assumes the 2bus-13bus co-simulation is running (e.g. via `helics run --path examples/2bus-13bus/gpk-gld-cosim.json`).

### AI Configuration & Logging
- The `ai` block in `config/ev_mcp.yaml` points to the local model endpoint `http://ccil1s26m8hj6lws:8000/v1` and specifies the `openai/gpt-oss-120b` model along with a system prompt emphasizing the educational and research context. You can adjust these values to match other deployments.
- Every call to `/primitive` is appended to `output/interaction_log.jsonl` with the timestamp, method, parameters, status, and resulting payload so you can trace the AI’s observations and decisions.

## End-to-End Demo Procedure
Follow these steps after cloning the repository to run the complete demonstration with Dockerized simulation and the EV MCP server:

1. **Rebuild the GridPACK executable inside the ROI base image** (needed whenever the C++ federate sources change):
   ```bash
   docker compose -f docker/docker-compose.demo.yml run --rm helics-federation \
     bash -lc "cd /workspace/examples && rm -rf build && mkdir build && cd build && cmake .. && make -j\$(nproc)"
   ```

2. **Start the core co-simulation stack** (HELICS broker, GridLAB-D, GridPACK, EV controller). The modified timing stretches the run to roughly five real minutes so the AI has time to act:
   ```bash
   docker compose -f docker/docker-compose.demo.yml up --build -d
   ```

3. **Launch the EV MCP server container** on the same network:
   ```bash
   docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build -d
   ```

4. **Verify connectivity** by issuing observation primitives from the host (replace `localhost` with the appropriate host/IP if running remotely):
   ```bash
   curl -s http://localhost:5100/primitive \
     -H "Content-Type: application/json" \
     -d '{"method":"get_grid_status","params":{}}' | jq
   ```

5. **Trigger an EV capacity change** to demonstrate the single action primitive:
   ```bash
   curl -s http://localhost:5100/primitive \
     -H "Content-Type: application/json" \
     -d '{"method":"set_ev_capacity","params":{"ev_id":"EV5","real_power_kw":180,"reactive_power_kvar":0,"duration_s":120}}' | jq
   ```

6. **Monitor AI activity** by tailing the interaction log and container output:
   ```bash
   tail -f archive/ev_setpoint_mcp/output/interaction_log.jsonl
   docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml logs -f
   ```

7. **Shut everything down** once the campaign completes (~5 minutes):
   ```bash
   docker compose -f archive/ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml down
   docker compose -f docker/docker-compose.demo.yml down
   ```

This sequence rebuilds the model, launches the simulation, exposes the MCP interface for AI experimentation, and captures a full audit trail of every primitive call.
