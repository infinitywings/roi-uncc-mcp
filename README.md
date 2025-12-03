# AI-Assisted Red-Teaming for Grid Co-Simulation

## Motivation
Critical power systems increasingly blend cyber control with distributed energy resources such as EV charging. Adversaries could manipulate setpoints to stress feeders, trigger protection, or island storage. We built a contained research sandbox to study how an AI agent (LLM + tool use) can plan, time, and execute such attacks, and how blue-team controls and protection respond. The goal is to illuminate attack surfaces, quantify resilience, and guide defensive design.

## Scope & Problem Statement
- Domain: Transmission–distribution co-simulation with EV chargers and limited storage (IEEE 9-bus transmission, dual IEEE 123-node feeders).
- Attack surface: EV capacity setpoints (active/reactive power) delivered via HELICS messages.
- Research questions: How effectively can an AI agent discover and exploit timing/phase/asset combinations to exceed feeder limits? How do rate limits, incomplete knowledge, and defensive controllers alter outcomes? What protection indicators and logs best reveal attack impact?

## Challenges
- **Coupled dynamics:** Transmission/feeder/EV interactions create nonlinear load flows and solver instability under heavy stress.
- **Timing alignment:** HELICS time steps, controller cadence, and attacker rate limits must align to observe realistic blue-team responses without crashing the solver.
- **Partial observability:** An attacker rarely knows full topology; the agent must infer vulnerability from limited telemetry.
- **Safety vs realism:** Overly aggressive setpoints crash the simulation before defenses act; too gentle hides meaningful effects.

## Main Scientific Contributions
- A modular, containerized MCP federate that exposes EV setpoint primitives and grid-status telemetry, ready for LLM tool use.
- An AI campaign loop that logs every prompt/decision/action with cooldowns, action caps, and history context to study planning under constraints.
- A co-simulation harness (HELICS + GridLAB-D + GridPACK) configured for EV overload/islanding scenarios with tunable limits and schedules.
- Experimental designs for comparing AI-driven, random, and no-attack baselines, focusing on feeder overload and controller/protection responses.

## System Description (Conceptual)
1. **Co-sim plant:** GridPACK 9-bus transmission federate publishes tie voltages; two GridLAB-D IEEE 123-node feeders subscribe and publish three-phase feeder power. EV1/EV4 include storage switches; others are chargers only.
2. **Controller:** A Python HELICS federate samples feeder power each minute, enforcing feeder limits (upper ~4.5 MW, lower ~2.6 MW) and toggling EVs (or islanding storage) based on load.
3. **Attacker MCP:** Flask + HELICS federate exposing `get_grid_status` and `set_ev_capacity` per EV (caps phased by sim time). Logs all actions and tool calls.
4. **AI loop:** OpenAI-compatible LLM endpoint; builds prompts from telemetry, recent actions, and a configurable cooldown (e.g., one attempt every 30 sim minutes). Actions are clamped by sim-time tiers to avoid early solver crashes.

## Experiment Design
- **Baselines:** (a) No attack (RUN_AI_CAMPAIGN=0), (b) random or naive attacks within the same caps/cooldowns, (c) AI-driven attacks.
- **Phases and limits:** Early cap 0.4 MW/EV (first 30 min), mid 1.2 MW, late 2.5 MW; controller upper limit 4.5 MW to allow overload without immediate divergence.
- **Schedules:** Softened EV profiles (tens to hundreds of kW peaks) to keep baseline near but below limits, enabling attacks to tip the system.
- **Metrics:** Feeder real power vs limits, controller actions (overload/safe/low-load branches), HELICS time progression, line/transformer overload warnings, solver stability.
- **Success criteria:** AI raises load above limits at meaningful times, triggers controller/protection responses without crashing the solver; random attacks less effective or blocked by cooldowns.

## Expected Evaluation & Results
- **Effectiveness:** Compare AI vs random in number of successful overloads, magnitude/duration above limit, and induced controller actions.
- **Robustness:** Track solver stability (no premature convergence failures) across full-day runs; measure how caps/cooldowns affect stability.
- **Stealth/efficiency:** Count attack attempts vs achieved impact under cooldowns; assess whether history-aware prompting improves timing/target selection.
- **Defender insights:** Use controller logs and feeder overload warnings to identify detection signals and potential automated mitigations.

## How to Run
- With attacker (default): `docker compose -f ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build -d`
- Without attacker: `RUN_AI_CAMPAIGN=0 docker compose -f ev_setpoint_mcp/docker/docker-compose.ev-mcp.yml up --build -d`
- Monitor logs: `examples/2bus-13bus/logs/{controller,gld1,gld2,ai_campaign,attacker,broker}.log`

## Notes & Future Work
- Fine-tune GLM line/transformer ratings and controller thresholds to balance realism and solver stability.
- Explore partial-topology prompts and noisy telemetry to harden the planning task.
- Add blue-team detection scoring and automated mitigations to study adaptive attacker–defender dynamics.
