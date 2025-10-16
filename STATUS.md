# ROI UNCC MCP – Status & Handoff

**Last updated:** 2025-10-15  
**Maintainer:** Codex session (AI assistant)  
**Environment:** Single-container EV attacker demo (`ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml`)

---

## 1. Current State
- ✅ `grid-attack-demo` container boots cleanly; HELICS broker and all five federates (2× GridLAB-D, GridPACK, blue-team controller, attacker MCP) enter execution.
- ✅ `/primitive` endpoint reachable at `http://localhost:5100/primitive` once the container is up.
- ✅ LLM integration pointed at `http://ccil1s26m8hj6lws:8000/v1` using model `openai/gpt-oss-120b`.
- ✅ AI campaign helper now receives HTTP 200 responses (<1 ms handler latency); `attack_executed` entries include `handler_latency_sec` and `helics_send_latency_sec` for every command.
- 📁 Runtime logs bind-mounted to `examples/2bus-13bus/logs/` (broker, gld1/gld2, gridpack, controller, attacker, ai_campaign, llm_interactions).

## 2. What Changed in This Session
- Archived legacy multi-container assets under `archive/legacy_demo/` to reduce clutter.
- Updated `ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml` to build from `ev_setpoint_mcp/docker/Dockerfile` (path fix after archival move).
- Reworked documentation into three concise files: `README.md`, `DESIGN.md`, `STATUS.md`.
- Adjusted AI helper defaults (`run_ai_campaign.py`) earlier to mitigate timeouts (90 s per request, 2 s delay).
- Instrumented `set_ev_capacity` path (ActionService + EV federate + Flask handler) so logs capture per-request latency, HELICS send time, and whether a refresh was queued.

## 3. Outstanding Items & Risks
1. **Monitor async state refresh**  
   - Poll loop now uses an event to refresh immediately after each attack; watch for `refresh_queued=true` and ensure telemetry snapshots reflect recent setpoints.

2. **Base image dependency**  
   - `roi-img:latest` must exist locally. If missing, rebuild via `archive/legacy_demo/containers/docker/Dockerfile`.

3. **LLM compliance evaluation**  
   - Logs now capture raw requests; analyse `llm_interactions.jsonl` to quantify how often the model respects ±4 MW limits.

## 4. Quick Resume Checklist
1. Ensure Docker daemon is running and `roi-img:latest` is built.
2. `docker compose -f ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build`.
3. Wait for the “[startup] All federates launched” message in container logs.
4. Hit `/health` and `/primitive` endpoints to confirm readiness.
5. Tail `examples/2bus-13bus/logs/ai_campaign.log` to monitor AI activity.
6. When testing is complete, `docker compose … down` and snapshot key logs if needed.

## 5. Reference Links
- High-level overview & quick start: `README.md`
- Architecture & workflow details: `DESIGN.md`
- Grid topology diagrams: `examples/2bus-13bus/GRID_DIAGRAM.md`
- Legacy workflow (archived): `archive/legacy_demo/`
