# EV Setpoint Attack vs. Baseline Run

## Shared Configuration
- **Runtime stack** – launched via `docker compose -f ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build -d`, which mounts the `examples/2bus-13bus` workspace into the container and exposes the primitive API on port 5100 (`ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml:1-22`).
- **AI campaign parameters** – by default the container starts the helper with unlimited steps, a 5 s wall-clock interval, 600 s warm-up wait, 24 h target duration, and 0.1 s between successive actions (`ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml:14-21`).
- **Attacker HELICS settings** – the MCP federate advances HELICS time in 600 s quanta (`time_delta`/`period`) while polling every 10 s, and can target six EV endpoints capped at ±4 MW (`ev_setpoint_mcp/config/ev_mcp_local.yaml:6-80`).
- **Blue-team controller** – `examples/2bus-13bus/1bc_EV_Controller.py` runs a 24 h loop with 20-minute evaluation intervals, enforcing feeder limits of 2.6–4.2 MW (`examples/2bus-13bus/1bc_EV_Controller.py:75-84`).

## Run 1 – AI attacker enabled (2025‑11‑11 15:27 EST)
### Procedure
1. Cleared prior logs and launched the full stack with the default environment (AI campaign active).
2. Waited for the MCP helper to record its first telemetry snapshot (`examples/2bus-13bus/logs/ai_campaign.log:1-2`).
3. Observed the LLM’s first decision and resulting HELICS traffic through `ai_campaign.log`, `attacker.log`, and `gld1.log`.

### What happened
- **Initial telemetry** – the helper captured a 3.56 MW feeder load while all EV setpoints were at 0 kW (`examples/2bus-13bus/logs/ai_campaign.log:1-2`).
- **LLM action** – on step 1 the model requested a single 3 MW surge on EV3, which the MCP accepted and forwarded to GridLAB-D (`examples/2bus-13bus/logs/ai_campaign.log:3-4` and `examples/2bus-13bus/logs/attacker.log:16-20`).
- **Controller state** – the EV controller logged only its initial “SAFE RANGE” message (3.57 MW) before HELICS raised an error at 600 s, preventing any further blue-team action (`examples/2bus-13bus/logs/controller.log:12-22`).
- **Physical response** – the extra EV3 load immediately drove multiple primary lines and the substation transformer above 200 % of their emergency ratings (e.g., `linobj1491` at 210 %+) and GridLAB-D declared a convergence failure at 00:11 PST (`examples/2bus-13bus/logs/gld1.log:240-288`).
- **Aftermath** – with GridLAB-D halted, the MCP federate began reporting `[-101]` HELICS errors and the AI campaign stopped after the very first step (`examples/2bus-13bus/logs/attacker.log:20-30`).

### Key takeaway
A single 3 MW command issued at the first 600 s step destabilized the feeder faster than the protection workflow could react, so we never observed controller-driven islanding or switch operations in this run.

## Run 2 – Baseline (RUN_AI_CAMPAIGN=0)
### Procedure
1. Copied the attack logs aside and relaunched the compose stack with `RUN_AI_CAMPAIGN=0` so no LLM requests were generated.
2. Let the co-simulation advance for ~6 000 s of simulated time (≈100 minutes) to confirm stability, then collected the preserved logs from `examples/2bus-13bus/logs_baseline/`.

### What happened
- **Controller cadence** – with identical feeder limits, the controller advanced through multiple 20-minute intervals, each time reporting totals between 3.1–3.6 MW and reaffirming the SAFE RANGE action (EV1 & EV2 on, others off) at every checkpoint up to 6 000 s (`examples/2bus-13bus/logs_baseline/controller.log:12-29`).
- **Grid behavior** – GridLAB-D progressed past 01:30 PST without numerical issues. The log is dominated by inverter threshold warnings but no overloads or convergence errors (`examples/2bus-13bus/logs_baseline/gld1.log:200-260`).
- **Attack surface** – Because the MCP server never received `set_ev_capacity` primitives in this mode, EV setpoints stayed at their scheduled values and HELICS remained synchronized.

### Key takeaway
When the attacker is idle, the feeder cruises within the 4.2 MW upper bound, allowing the controller to cycle through its SAFE RANGE branch repeatedly without tripping switches or islanding storage. This establishes the “normal” trajectory for comparisons.

## Comparative Notes
- **Simulation progress** – Baseline run continued indefinitely, whereas the attack run halted at 600 s due to a GridLAB-D convergence failure. This highlights that the current attack configuration is too aggressive to showcase downstream protection effects.
- **Controller visibility** – In baseline mode the controller samples and logs every 20 minutes; under attack it only produced the first log entry before HELICS errored out. Showing a meaningful difference therefore requires either throttling the attack steps or hardening the feeder model so the controller can react.
- **Data for visualization** – Use `examples/2bus-13bus/logs_baseline/gld1.log` as the reference trace and `examples/2bus-13bus/logs/gld1.log` / `ai_campaign.log` for the attack case when plotting feeder load, line overloads, or campaign events side-by-side.

