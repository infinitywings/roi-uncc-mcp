# ROI UNCC MCP – Design Notes

## 1. Architecture Overview
```
┌────────────────────────────────────────────────────────────────────┐
│                       AI Strategy Layer (LLM)                      │
│   - Plans malicious EV setpoints via /primitive REST calls         │
└────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────┐
│                EV Setpoint MCP Container (grid-attack-demo)        │
│                                                                    │
│  Flask API  ─┐   Observation Service   ─┐   Action Service         │
│              │                         │                            │
│  /health     │→ HELICS Federate ←──────┘→ Publishes EV setpoints   │
│  /primitive  │                         │   Subscribes feeder data  │
└──────────────┴─────────────────────────┴────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────┐
│                         HELICS Federation                          │
│  - GridLAB-D Feeder A (IEEE 123-node)                              │
│  - GridLAB-D Feeder B (IEEE 123-node)                              │
│  - GridPACK Transmission (IEEE 9-bus)                              │
│  - Legitimate EV Controller (blue team)                            │
│  - Attacker EV MCP (red team)                                      │
└────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Physical Models & Logs (examples/2bus-13bus)    │
└────────────────────────────────────────────────────────────────────┘

## 2. Simulation Model & Topology
- **Transmission (GridPACK)**: Publishes tie-line voltages `gridpack/V{a,b,c}` at the two feeder connection buses. Subscribes to aggregated feeder demand `gld_hlc_conn/S{a,b,c}`.
- **Distribution Feeders (GridLAB-D)**: Two copies of the IEEE 123-node system. EV chargers map to switches `swEV1`…`swEV6`; EV1 & EV4 include storage switches for islanding. Publish feeder load, subscribe to voltage setpoints.
- **Reference**: Full feeder/phase diagrams live in `examples/2bus-13bus/GRID_DIAGRAM.md`.

## 3. Container Workflow
1. `docker-compose.ev-mcp.yml` builds the image from `ev_setpoint_mcp/docker/Dockerfile` (base `roi-img:latest`).
2. `CMD` executes `docker/run_grid_attack_demo.sh`, which:
   - Builds GridPACK artifacts on first run (`cmake && make`).
   - Starts a local HELICS broker on `tcp://localhost:23404`.
   - Launches both GridLAB-D feeders, the blue-team EV controller, the GridPACK federate, and the attacker MCP.
   - Optionally runs `tools/run_ai_campaign.py` to drive the LLM loop.
3. All stdout/stderr streams land in `examples/2bus-13bus/logs/`.

## 4. EV Setpoint MCP Internals
- **Configuration**: `config/ev_mcp.yaml` (or `_local.yaml` in the container) defines broker address, timing, attack limits, logging paths, and AI defaults.
- **Observation Service**: Exposes `get_grid_status`, `discover_topology`, `monitor_protection_systems`, `analyze_power_flow`.
- **Action Service**: Currently supports `set_ev_capacity`, enforcing ±4 MW (−0.5 MW) attack bounds plus reactive-power limits.
- **Interaction Log**: JSON lines written to `logs/llm_interactions.jsonl` when logging is enabled.

## 5. AI Campaign Flow
1. Fetch grid telemetry via `/primitive` → `get_grid_status`.
2. Craft prompt (schema hint + operating limits) for `openai/gpt-oss-120b` hosted at `http://ccil1s26m8hj6lws:8000/v1`.
3. Parse JSON response (`{"actions":[...]}`).
4. POST each action back to `/primitive` → `set_ev_capacity`.
5. Record successes/failures in `ai_campaign.log`.
   - Default client timeout: 90 s per action.
   - 2 s delay between sequential actions to avoid overlapping HELICS updates.

## 6. API Surface
- `GET /health` → container heartbeat (`{"status":"ok","federate_running":true}`).
- `POST /primitive` with payload:
  ```json
  {
    "method": "get_grid_status",
    "params": {}
  }
  ```
  or
  ```json
  {
    "method": "set_ev_capacity",
    "params": {
      "ev_id": "EV3",
      "real_power_kw": 2500,
      "reactive_power_kvar": 0
    }
  }
  ```
- Responses include `"status": "success"` or `"error"` plus method-specific data.

## 7. Environment & Overrides
- `HELICS_BROKER_ADDRESS` — override broker in `load_config`.
- `EV_MCP_SERVER_HOST`, `EV_MCP_SERVER_PORT` — change bind address/port.
- `RUN_AI_CAMPAIGN`, `AI_CAMPAIGN_STEPS`, `AI_CAMPAIGN_INTERVAL`, `AI_CAMPAIGN_WAIT` — control automatic LLM loop from the startup script.
- Base image `roi-img:latest` bundles HELICS, GridLAB-D, GridPACK, and Python dependencies used by the MCP.

## 8. Observability & Artefacts
- `examples/2bus-13bus/logs/` — broker, federate, controller, attacker, and AI campaign logs.
- `ev_setpoint_mcp/output/interaction_log.jsonl` — per-request audit trail when enabled.
- `examples/2bus-13bus/build/` — GridPACK executable (`gpk-left-fed.x`).
- Use `docker logs grid-attack-demo` for aggregate view if needed.
