# Experiment Plan: AI vs Random vs No-Attack in EV Setpoint Co-Simulation

## Objectives
- Quantify the advantage of a constrained, history-aware AI attacker over (a) random attacks obeying the same limits and (b) no-attack baseline.
- Demonstrate meaningful physical/operational effects (feeder overloads, controller responses, potential islanding) without frequent solver crashes.
- Assess robustness to rate limits, phased power caps, and partial observability.

## Scenarios
1. **No Attack (Baseline):** AI loop disabled; controller and plant run for 24 h with softened EV schedules.
2. **Random Attack:** Actions drawn uniformly within allowed caps/cooldowns and EV set; no timing/phase reasoning.
3. **AI Attack:** LLM-driven with history/cooldown awareness; same caps/cooldowns and observability as random.

## Model & Constraints (initial default)
- **Feeder limits:** Lower ~2.6 MW, upper ~4.5 MW (controller toggles EVs/islanding).
- **Phased attack caps (per EV):** 0–30 min: 0.4 MW; 30 min–2 h: 1.2 MW; >2 h: 2.5 MW.
- **Cooldown:** ≥30 minutes simulated between attack attempts.
- **EV schedules:** Softened peaks (tens to low hundreds of kW) to keep baseline near but below upper limit.
- **Timing:** HELICS time_delta ~600 s; controller interval 60 s to allow defensive reaction; adjust if instability persists.
- **Attacker observability:** Aggregate feeder power, per-EV setpoints, recent EV commands, limited switch states; no full topology.

## Parameter Settings (default and sweeps)
- **Simulation timing**
  - HELICS `time_delta`/`period`: 600 s (sweep 300–900 s if controller misses events or solver unstable).
  - Controller interval: 60 s (sweep 60–300 s to test defensive agility).
  - Simulation duration: 86 400 s (24 h) to cover full daily profiles.
- **Attacker limits**
  - Caps by phase: early 0.4 MW/EV; mid 1.2 MW/EV; late 2.5 MW/EV (sweep ±20%).
  - Cooldown: 30 min sim between attempts (sweep 15/30/60 min).
  - Action budget: optionally cap to N=10–20/day for stealth tests.
  - Compromise scope: default all six EVs; variant with only 2–3 EVs controllable.
- **Baselines**
  - Random: uniform EV selection within allowed set; uniform power within caps; same cooldown/budget; fixed seed.
  - No-attack: AI loop off; same schedules/limits.
- **Feeder limits/schedules**
  - Upper limit: 4.5 MW (sweep 4.2–4.8 MW to trade impact vs stability).
  - EV schedules: softened `.player` files yielding baseline ~3.5–3.9 MW; can restore higher peaks to increase headroom challenge.
- **Prompting/LLM**
  - Inject last 5 actions, cooldown reminder, current telemetry; JSON-only schema; partial observability maintained.

## Metrics
- **Impact:** Peak feeder real power; number/duration of overload intervals above upper limit; phase imbalances if available.
- **Defender response:** Counts of controller branch activations (overload/safe/low); any islanding events; switch states for storage EVs.
- **Stability:** Presence/absence of convergence failures; total simulated time achieved.
- **Efficiency/stealth:** Attacks executed vs skipped/rate-limited; impact per allowed attempt; time-to-first-overload.
- **Comparative:** AI vs random vs baseline across identical seeds/configs.

## Procedure
1. **Config freeze:** Fix caps, cooldown, EV schedules, feeder limits for a run set.
2. **Run campaigns:**
   - Baseline (no attack), 24 h simulated.
   - Random attack, 24 h, same caps/cooldown; seed fixed for reproducibility.
   - AI attack, 24 h, same caps/cooldown.
3. **Logging:** Collect `ai_campaign.log`, `llm_interactions.jsonl` (for attack runs), `controller.log`, `gld1.log/gld2.log`, `attacker.log`.
4. **Post-process:** Extract metrics (overload counts/durations, controller actions, stability flags, attack counts). Plot feeder power vs limits and mark attack/response events.
5. **Sensitivity sweeps (optional):** Vary cooldown (15/30/60 min) and caps (±20%) to map stability vs impact and to test AI robustness.

## Expected Outcomes
- Baseline stays under limits; no overload actions.
- Random attacks trigger few or poorly timed overloads; may waste quota; limited controller responses.
- AI attacks concentrate attempts near natural peaks/phase combinations to exceed limits more often and earlier, eliciting clear controller/protection responses while staying within caps/cooldowns and maintaining solver stability.
