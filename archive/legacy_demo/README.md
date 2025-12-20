# Legacy MCP Server Assets

This folder preserves the original multi-container MCP server workflow. It contains:

- `config/` – legacy YAML configuration library (demo presets, AI provider examples, 2bus-13bus attack config).
- `demo_results/` – archived dashboards and CSV outputs from earlier comparison demos.
- `docker/` and `containers/` – Dockerfiles and compose bundles for the multi-service deployment.
- `mcp-server/` – the previous Flask-based MCP server implementation, including attack engine, monitor, and AI strategist.
- `scripts/`, `demo.py`, `run_demo.sh` – orchestration helpers for the legacy workflow.
- `API.txt`, `CLAUDE.md`, `PROJECT_STRUCTURE.md` – historical documentation notes.

The current (previous) single-container demo has been archived under `archive/ev_setpoint_mcp/`. The assets here are read-only references kept for posterity and should not be modified unless you are intentionally reviving the legacy workflow.
