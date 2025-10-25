## Modular Agent Architecture

The new attacker agent is designed as a composable control loop that mirrors the
research phases described in `archive/old_docs/AI-INTEGRATION.md` and the
experimental discipline captured in `archive/old_docs/RESEARCH-GUIDE.md`.

### Runtime Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `MCPAgent` | `ev_setpoint_mcp/agent/agent.py` | Orchestrates observation, LLM planning, and tool execution |
| `ToolRegistry` | `ev_setpoint_mcp/agent/tooling.py` | Registers/executes MCP primitives as reusable tools |
| `MemoryBuffer` | `ev_setpoint_mcp/agent/memory.py` | Stores recent observations, plans, and tool outcomes for prompt context |
| `PromptBuilder` | `ev_setpoint_mcp/agent/prompts.py` | Generates system/user messages with configurable templates |
| `run_agent.py` | `ev_setpoint_mcp/tools/run_agent.py` | CLI entry that wires configuration, logging, and LLM settings |

Tools are declared as simple dataclasses (`Tool`) describing a MCP method,
validation schema, and executor. Additional primitives can be introduced by
registering new `Tool` instances or by extending `ToolRegistry`.

### Event-Driven Agent Loop

1. **Monitor** – A background thread polls the MCP server on a configurable
   cadence and pushes new grid snapshots (or telemetry deltas) into an internal
   event queue. Topology is refreshed opportunistically according to the
   `topology_refresh_seconds` setting.
2. **Reason** – Whenever the planner receives a fresh observation and the
   decision cool-down has expired it assembles a prompt from the memory summary,
   a Harmony formatted history tail, the latest grid status, and the advertised
   tool catalogue (mirroring the intelligence-gathering and vulnerability
   assessment steps in `AI-INTEGRATION.md`).
3. **Act** – The LLM returns a structured `actions` array. For each entry the
   registry validates parameters and invokes the corresponding primitive
   (`discover_topology`, `monitor_protection_systems`, `set_ev_capacity`, etc.).
   Outcomes are appended to memory and written to the Harmony log so research
   metrics from `RESEARCH-GUIDE.md` can be computed post-run.
4. **Evaluate** – Cool-down timers, max-step limits, and simulated duration
   checks determine whether further planning is warranted; otherwise the agent
   awaits the next observation event.

All campaign events, Harmony transcript entries, and raw LLM exchanges are
persisted to JSONL files. This satisfies the reproducibility and statistical
analysis requirements outlined in `RESEARCH-GUIDE.md`, while also enabling
mid-campaign hand-offs to other agents or operators.

All campaign events and raw LLM exchanges are persisted to JSONL files so that
experimental runs can be reproduced and statistically analysed (see the
disruption score methodology in `RESEARCH-GUIDE.md`).

### Dockerised Deployment

`docker-compose.ev-mcp.yml` now separates the runtime into three reusable
services:

- `grid-sim` runs the HELICS broker, GridLAB-D feeders, GridPACK, and EV
  controller via `run_grid_stack.sh`.
- `ev-mcp` hosts the MCP observation/action server (`run_mcp_server.sh`) and
  exposes the primitive API on port 5100.
- `attack-agent` executes the modular agent (`run_modular_agent.sh`) and
  communicates with the MCP server over HTTP.

This modular layout makes it easy to swap in alternative controllers,
instruments, or agent behaviour while keeping the simulation model isolated in
its own container.

### Customisation Points

- **Tools/Primitives** – Add or remove entries in `ToolRegistry`; constrain the
  advertised list via the `--tools` CLI flag or environment variable
  `AI_AGENT_TOOLS`.
- **Prompt Template** – Supply bespoke instructions with
  `--instructions/--instructions-file` so that different strategies, assets, or
  evaluation criteria can be layered on top of the base system prompt.
- **Context Providers** – Extend `MCPAgent` to register additional cacheable
  context (e.g., schedule data, past disruption metrics) or implement specialised
  memory summaries aligned with specific research campaigns.
- **Harmony Transcript** – Point `--harmony-log` (or `AI_AGENT_HARMONY_LOG`) at a
  desired location to capture the full conversation history in Harmony format for
  later replay or debugging.

By aligning the implementation with the conceptual flow documented in the legacy
`archive/old_docs` manuals, the attacker stack is now modular enough to support
rapid experimentation and targeted debugging.
