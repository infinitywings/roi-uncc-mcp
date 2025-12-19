# LLM-GridEval

LLM-GridEval is an adaptive attacker evaluation framework for the `examples/2bus-13bus` HELICS co-simulation.

It provides:
- An HTTP “MCP-style” attacker server exposing `/tools/observe`, `/tools/analyze`, `/tools/attack`, and `/tools/metrics`
- Two campaign drivers with identical constraints:
  - `scripts/run_random_baseline.py`
  - `scripts/run_ai_campaign.py` (timing-aware, observe-decide-wait)

This implementation follows `new_design.md` at the repo root.

## Quick start (server)

1. Start the HELICS co-simulation (broker + federates) separately (see `examples/2bus-13bus/README.md`).
2. In another terminal, start the attacker server:

```bash
python llm_grid_eval/run_server.py --config llm_grid_eval/config/default.yaml
```

Then hit:

```bash
curl -s http://localhost:5100/health | jq
curl -s http://localhost:5100/tools/analyze -H 'Content-Type: application/json' -d '{}' | jq
```

## Campaigns

```bash
python llm_grid_eval/scripts/run_random_baseline.py --mcp-url http://localhost:5100 --duration 1800 --experiment-name random_30m
python llm_grid_eval/scripts/run_ai_campaign.py --mcp-url http://localhost:5100 --duration 1800 --experiment-name ai_30m
```
