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

### Agent Loop

1. **Observe** – `MCPAgent` gathers the latest grid snapshot (and optionally
   caches topology) while recording the event in the shared memory buffer.
2. **Reason** – A prompt is assembled from the recent memory summary,
   observation payload, and tool catalogue. The LLM response must return a JSON
   `actions` array, enabling the ReAct-style planning highlighted in
   `AI-INTEGRATION.md`.
3. **Act** – `ToolRegistry` invokes each requested primitive (e.g.
   `discover_topology`, `monitor_protection_systems`, `set_ev_capacity`). Results
   and errors are appended to memory, supporting iterative refinement and the
   quantitative logging required by `RESEARCH-GUIDE.md`.
4. **Evaluate** – The loop sleeps for the configured interval, optionally
   refreshes topology, and records the next observation.

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

By aligning the implementation with the conceptual flow documented in the legacy
`archive/old_docs` manuals, the attacker stack is now modular enough to support
rapid experimentation and targeted debugging.
