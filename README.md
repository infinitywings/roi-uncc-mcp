# ROI UNCC MCP

AI-assisted grid penetration testing sandbox combining HELICS co-simulation, EV setpoint manipulation, and LLM-driven attack orchestration.

## What’s in This Repo
- `ev_setpoint_mcp/` — active attacker container (Flask API, HELICS federate, AI tooling, Docker assets).
- `examples/2bus-13bus/` — transmission + distribution models, build artifacts, and runtime logs (see `GRID_DIAGRAM.md` for the full topology).
- `documentation/` — background material inherited from earlier phases.
- `archive/legacy_demo/` — retired multi-container MCP server workflow kept for reference only.

## Simulation Model Snapshot
- Transmission: IEEE 9-bus GridPACK federate publishes tie-line voltages (`gridpack/Va,Vb,Vc`).
- Distribution: Two IEEE 123-node feeders (GridLAB-D) subscribe to transmission voltages and publish feeder demand (`gld_hlc_conn/Sa,Sb,Sc`).
- EV Assets: Six chargers share phases; EV1 and EV4 include battery-backed islanding switches.
- For detailed node/phase/breaker layouts refer to `examples/2bus-13bus/GRID_DIAGRAM.md`.

## Quick Start
> Prerequisites: Docker with Compose v2, and the `roi-img:latest` base image (build instructions reside in `archive/legacy_demo/containers/docker/` if you need to rebuild it).

1. **Launch the demo**
   ```bash
   docker compose -f ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build
   ```
2. **Watch the co-simulation**
   ```bash
   tail -f examples/2bus-13bus/logs/{broker,gld1,gld2,gridpack,controller,attacker}.log
   tail -f examples/2bus-13bus/logs/ai_campaign.log
   ```
3. **Query the MCP API**
   ```bash
   curl -s http://localhost:5100/health | jq
   curl -s http://localhost:5100/primitive \
     -H "Content-Type: application/json" \
     -d '{"method":"get_grid_status","params":{}}' | jq
   ```
4. **Fire an attack manually (optional)**
   ```bash
   curl -s http://localhost:5100/primitive \
     -H "Content-Type: application/json" \
     -d '{"method":"set_ev_capacity","params":{"ev_id":"EV3","real_power_kw":2500,"reactive_power_kvar":0}}' | jq
   ```
5. **Run additional AI campaigns**
   ```bash
   docker exec -it grid-attack-demo \
     python /app/ev_setpoint_mcp/tools/run_ai_campaign.py \
       --server http://localhost:5100/primitive \
       --llm-base http://ccil1s26m8hj6lws:8000/v1 \
       --model openai/gpt-oss-120b
   ```
6. **Shut everything down**
   ```bash
   docker compose -f ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml down
   ```

## Where to Go Next
- **Design details** — see `DESIGN.md` for architecture, workflow, and API references.
- **Current status** — check `STATUS.md` for the latest run results, open issues, and quick-resume tips.
- **Topology reference** — consult `examples/2bus-13bus/GRID_DIAGRAM.md` while analysing logs or attacks.
