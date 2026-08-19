# v2 Experiment Plan

## Prerequisites (Must Resolve Before Any Experiments)

### P1: Verify or fix the controller delay filter
- [ ] Read `1c_Control.json` filter section
- [ ] Run a no-attack baseline for 5 minutes
- [ ] Check `1c_Controller.log` to see if controller commands actually change EV power
- [ ] If the 3600s delay is real and blocking: remove or reduce the filter
- [ ] Re-run baseline, confirm controller response within 10s

### P2: Verify controller safe-range logic
- [ ] Read `1bc_EV_Controller.py` safe-range branch
- [ ] Confirm what power values are sent to which EVs in each state
- [ ] Fix documentation to match actual behavior

### P3: Confirm LLM endpoint availability and response quality
- [ ] Test `curl http://ccil1s26m8hj6lws:8000/v1/models`
- [ ] Send 10 test prompts matching the attack scenario
- [ ] Measure JSON parse success rate (must be >90%)
- [ ] Document which model is actually being used

### P4: Decide on Feeder B
- [ ] Test if federation runs with only Feeder A (4 federates instead of 5)
- [ ] If not feasible, keep Feeder B but document it doesn't participate in attack/defense

---

## Experiment Matrix

### Phase 1: Baseline Validation (no attacks)

| Run | Duration | Controller | Purpose |
|-----|----------|-----------|---------|
| baseline_5m | 300s | 10s interval | Confirm TVD=0, controller works |
| baseline_1h | 3600s | 10s interval | Confirm sustained stability |

### Phase 2: Short Comparison (5 min × 3 seeds × 3 variants = 9 runs)

| Run | Variant | Seed | Duration |
|-----|---------|------|----------|
| random_5m_s1 | Random | 1 | 300s |
| random_5m_s2 | Random | 2 | 300s |
| random_5m_s3 | Random | 3 | 300s |
| ai_v1_5m_s1 | AI-V1 (timing only) | 1 | 300s |
| ai_v1_5m_s2 | AI-V1 (timing only) | 2 | 300s |
| ai_v1_5m_s3 | AI-V1 (timing only) | 3 | 300s |
| ai_v2_5m_s1 | AI-V2 (timing+strategy) | 1 | 300s |
| ai_v2_5m_s2 | AI-V2 (timing+strategy) | 2 | 300s |
| ai_v2_5m_s3 | AI-V2 (timing+strategy) | 3 | 300s |

**Success criteria**:
- V2 TVD >= Random TVD (V2 matches or exceeds)
- V1 TVD < Random TVD (V1 underperforms, confirming paper finding)
- V2 unique EVs >= 3 (diversification working)
- V1 unique EVs <= 2 (single-target confirmed)

### Phase 3: Extended Comparison (1 hour × 3 seeds × 3 variants = 9 runs)

Same matrix as Phase 2 but with `duration=3600s`.

**Success criteria**:
- V2 EVG > 1.0 (V2 outperforms random over longer horizon)
- V2 PHAR > 33% (AI concentrates on peak hours)
- V2 MACP < 0.3 (AI exploits controller cycles)
- Budget management: neither variant exhausts attack budget prematurely

### Phase 4 (optional): Controller Interval Sweep

Test at 10s, 30s, 60s controller intervals with V2 and Random only:
- 6 additional runs (2 variants × 3 intervals), 1 hour each
- Measure how micro-timing advantage scales with controller speed

---

## Shared Constraints (all variants)

```yaml
# v2/configs/constraints.yaml
observation:
  interval_sec: 5.0

action:
  min_cooldown_sec: 90.0
  max_attacks_per_hour: 20

power:
  min_kw: 500.0
  max_kw: 1500.0

targets:
  valid_ev_ids: ["EV1", "EV2", "EV3", "EV4", "EV5", "EV6"]

grid:
  threshold_kw: 4200.0
```

---

## Attacker Variant Specifications

### Random Baseline
- Attack probability: 0.3 per eligible observation (matches paper)
- Target: uniform random from valid EVs
- Power: uniform random from [500, 1500] kW
- No timing intelligence, no strategic planning

### AI-V1 (Timing Only)
- Micro-timing gate: attack only when micro_score >= 70
- Macro-timing gate: attack only when recommendation is ATTACK_NOW or ATTACK_POSSIBLE
- LLM prompt: timing scores + grid state only
- NO power accumulation model in prompt
- NO attack history or strategic context
- NO diversification guidance

### AI-V2 (Timing + Strategy)
- Same timing gates as V1
- LLM prompt includes:
  - Power accumulation model (additive across EVs, overwrite on same EV)
  - Attack history per EV (which EVs attacked, how many times, current power)
  - Diversification priority (unattacked EVs first)
  - Recommended targets list

---

## Metrics

### Primary
- **TVD** (seconds): Cumulative time feeder load > 4.2 MW
- **EVG** (ratio): AI_TVD / Random_TVD

### Timing Intelligence
- **PHAR** (%): Attacks during peak hours / total attacks
- **MACP** (0-1): Average cycle position at attack time
- **Avg micro score at attack**
- **Avg macro score at attack**

### Strategic
- **Unique EVs targeted**
- **Final accumulated EV setpoint** (sum of all EV target powers)
- **Per-attack efficiency** (TVD / total_attacks)

### Constraint Compliance
- Attacks blocked by cooldown
- Attacks blocked by budget
- LLM parse failure rate (AI variants only)

---

## Statistical Analysis

With 3 seeds per condition:
- Report mean ± standard deviation for all metrics
- Paired comparisons: Welch's t-test or Mann-Whitney U (small samples)
- Effect sizes: Cohen's d
- Bonferroni correction for multiple comparisons

For Phase 3 (1-hour runs), also compute:
- Time series of cumulative TVD
- Attack timeline plots overlaid on feeder power
- EVG as a function of elapsed time (does advantage grow?)

---

## Output Structure

```
v2/results/
├── phase1/
│   ├── baseline_5m.json
│   └── baseline_1h.json
├── phase2/
│   ├── random_5m_s1.json
│   ├── random_5m_s2.json
│   ├── ...
│   └── ai_v2_5m_s3.json
├── phase3/
│   ├── random_1h_s1.json
│   ├── ...
│   └── ai_v2_1h_s3.json
└── analysis/
    ├── phase2_summary.csv
    ├── phase3_summary.csv
    ├── statistical_tests.json
    └── figures/
        ├── tvd_comparison.png
        ├── evg_by_duration.png
        ├── timing_distributions.png
        └── attack_timeline.png
```
