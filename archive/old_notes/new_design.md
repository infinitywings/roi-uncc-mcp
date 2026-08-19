# AI Attacker Strategy Flaw Analysis

## Executive Summary

Validation testing of the scarce attack budget (Option A) revealed a critical flaw in the AI attacker's strategy: **the AI optimizes for timing but neglects target diversification**, resulting in significantly worse performance than a random baseline despite superior micro-timing scores.

---

## 1. Experimental Setup

### 1.1 Scarce Attack Budget Configuration

To force strategic timing decisions, we implemented Option A constraints:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `min_cooldown_sec` | 90s | 1.5× controller interval (60s) |
| `max_attacks_per_hour` | 20 | ~1 attack per 3 minutes |
| `controller_interval_sec` | 60s | Window for timing discrimination |

With these constraints:
- Attacker gets approximately **0.67 attacks per controller cycle** (60s cycle / 90s cooldown)
- Each attack decision becomes strategically significant
- Poor timing wastes scarce attack opportunities

### 1.2 Test Configuration

- **Duration**: 300 seconds (5 minutes)
- **Available EVs**: EV1, EV2, EV3, EV4 (4 charging stations)
- **Power Range**: 500-1500 kW per EV
- **Threshold**: 4.2 MW feeder limit
- **Base Load**: ~3.2 MW at simulation start

---

## 2. Experimental Results

### 2.1 Random Baseline Results

```
Experiment: scarce_random
Total Attacks: 4
Total TVD: 240 seconds

Attack Log:
  #1: t=5s    EV3 @ 745kW   micro=75  cycle_pos=0.25
  #2: t=95s   EV1 @ 1177kW  micro=25  cycle_pos=0.75
  #3: t=190s  EV4 @ 532kW   micro=66  cycle_pos=0.33
  #4: t=280s  EV2 @ 1005kW  micro=16  cycle_pos=0.83

Timing Metrics:
  Average Micro Score: 45.5
  Average Cycle Position: 0.54 (mid-cycle, suboptimal)

Target Distribution:
  EV1: 1 attack (1177 kW)
  EV2: 1 attack (1005 kW)
  EV3: 1 attack (745 kW)
  EV4: 1 attack (532 kW)

Total Accumulated Power: 3,459 kW across 4 EVs
```

### 2.2 AI Attacker Results

```
Experiment: scarce_ai
Total Attacks: 3
Total TVD: 120 seconds

Attack Log:
  #1: t=0s    EV1 @ 700kW   micro=83  cycle_pos=0.17
  #2: t=110s  EV1 @ 1200kW  micro=100 cycle_pos=0.00
  #3: t=235s  EV1 @ 1500kW  micro=91  cycle_pos=0.08

Timing Metrics:
  Average Micro Score: 91.33
  Average Cycle Position: 0.08 (near cycle start, optimal)

Target Distribution:
  EV1: 3 attacks (700 → 1200 → 1500 kW)
  EV2: 0 attacks
  EV3: 0 attacks
  EV4: 0 attacks

Effective Power Contribution: 1,500 kW (only final EV1 target)
```

### 2.3 Comparative Analysis

| Metric | Random | AI | Delta | Better |
|--------|--------|-----|-------|--------|
| **TVD (primary)** | 240s | 120s | -120s | Random |
| Total Attacks | 4 | 3 | -1 | AI (efficiency) |
| Avg Micro Score | 45.5 | 91.33 | +45.8 | AI (+101%) |
| Avg Cycle Position | 0.54 | 0.08 | -0.46 | AI |
| Unique EVs Targeted | 4 | 1 | -3 | Random |
| Cumulative Power | 3,459 kW | 1,500 kW | -1,959 kW | Random |

**EVG (Effectiveness vs Gain) = AI_TVD / Random_TVD = 120 / 240 = 0.50**

The AI achieved only **50% of random's effectiveness** despite having **2× better timing scores**.

---

## 3. Root Cause Analysis

### 3.1 The Target Diversity Problem

The fundamental issue is that the AI repeatedly attacked the **same EV** (EV1) while ignoring the other three charging stations.

**Why this matters:**

With rate-limited power ramping enabled, each EV independently ramps toward its target setpoint:

```
EV Power Ramping Model:
  - Ramp rate: 100 kW/s
  - Each EV maintains its own target and current power
  - Attacking the SAME EV overwrites its target (no accumulation)
  - Attacking DIFFERENT EVs accumulates their contributions
```

**Visual illustration:**

```
Random Strategy (Diversified):
Timeline:  |----5s----|----95s----|---190s----|---280s----|

EV1:       [          ][ 1177 kW ================================]
EV2:       [                                   ][ 1005 kW =======]
EV3:       [ 745 kW =============================================]
EV4:       [                      ][ 532 kW =====================]
           ─────────────────────────────────────────────────────────
Total:              745    1922        2454         3459 kW (cumulative)


AI Strategy (Single Target):
Timeline:  |----0s----|---110s----|---235s----|

EV1:       [ 700 kW ==][ 1200 kW ==][ 1500 kW ==================]
EV2:       [          (never attacked)                          ]
EV3:       [          (never attacked)                          ]
EV4:       [          (never attacked)                          ]
           ─────────────────────────────────────────────────────────
Total:         700        1200         1500 kW (overwrites, not cumulative)
```

### 3.2 Load Accumulation Evidence

The feeder load is the sum of base load plus all EV contributions:

```
Feeder Load = Base Load + Σ(EV_i power)

Random at t=280s:
  Feeder = 3200 + 1177 + 1005 + 745 + 532 = 6,659 kW
  Exceeds 4,200 kW threshold by: 2,459 kW

AI at t=235s:
  Feeder = 3200 + 1500 + 0 + 0 + 0 = 4,700 kW
  Exceeds 4,200 kW threshold by: 500 kW
```

The random attacker created a **4.9× larger margin** above the threshold, leading to more sustained violations.

### 3.3 Why the AI Made This Mistake

Examining the AI's decision-making context:

1. **Timing Optimization Focus**: The AI prompt emphasizes micro-timing scores and cycle position, not target diversity

2. **Missing Context**: The AI doesn't receive information about:
   - Current power level of each EV
   - Which EVs have already been attacked
   - Cumulative load contribution model

3. **Local Optimization**: The AI sees "EV1 available, good timing → attack EV1" without considering the global strategy of load accumulation

4. **First Attack Too Weak**: The AI started with only 700 kW (conservative) while random started with 745 kW and quickly escalated across targets

### 3.4 Controller Interaction Evidence

From the controller logs (`1c_Controller.log`):

```
Random Run (more severe overload):
t=120s: Total Feeder Load is 4693.62 kW
        OVERLOAD: P = 4.69 MW >= 4.20 MW, turning OFF all EV stations.

AI Run (milder overload):
t=120s: Total Feeder Load is 4421.83 kW
        OVERLOAD: P = 4.42 MW >= 4.20 MW, turning OFF all EV stations.
```

Both triggered controller response, but random created a **271 kW larger overload**, making recovery slower and extending TVD.

---

## 4. Theoretical Framework

### 4.1 Attack Effectiveness Model

Let's define attack effectiveness mathematically:

```
E(attack) = Power_contribution × Duration_factor × Timing_factor

Where:
  Power_contribution = Δ load added to feeder
  Duration_factor = time until controller can respond
  Timing_factor = (1 - cycle_position) for micro-timing benefit
```

For the AI's single-target strategy:
```
E_ai = 1500 kW × D × 0.92 = 1380D
```

For random's diversified strategy:
```
E_random = 3459 kW × D × 0.46 = 1591D
```

Even with **half the timing score**, random achieves **15% higher effectiveness** due to superior power accumulation.

### 4.2 Optimal Strategy

The optimal attacker should:

1. **Diversify targets first**: Attack each EV once before repeating
2. **Maximize power**: Use maximum power (1500 kW) for each attack
3. **Time attacks optimally**: Execute at cycle_position ≈ 0.0

Expected performance with optimal strategy:
```
4 attacks × 1500 kW × excellent timing = 6000 kW contribution
vs. Random's 3459 kW or AI's 1500 kW
```

---

## 5. Design Recommendations

### 5.1 Immediate Fixes

**Option A: Update AI System Prompt**

Add explicit guidance about target diversification:

```python
ATTACK_STRATEGY_GUIDANCE = """
CRITICAL: Attack different EVs to maximize cumulative load.
- Each EV's power ADDS to total feeder load
- Attacking the same EV repeatedly OVERWRITES (doesn't accumulate)
- Optimal: Attack EV1, then EV2, then EV3, then EV4
- Only repeat an EV after all others have been attacked

PRIORITY ORDER:
1. Target diversity (attack unattacked EVs first)
2. Power level (prefer maximum 1500 kW)
3. Timing (execute at cycle_position < 0.2)
"""
```

**Option B: Add EV State to Context**

Provide the AI with current power levels:

```json
{
  "ev_states": {
    "EV1": {"current_kw": 1200, "attacked": true, "attack_count": 2},
    "EV2": {"current_kw": 0, "attacked": false, "attack_count": 0},
    "EV3": {"current_kw": 0, "attacked": false, "attack_count": 0},
    "EV4": {"current_kw": 0, "attacked": false, "attack_count": 0}
  },
  "recommendation": "Attack EV2, EV3, or EV4 (unattacked)"
}
```

### 5.2 Metric Refinements

Add target diversity to the scoring system:

```python
def compute_attack_score(state, action, history):
    micro_score = compute_micro_timing(state)
    macro_score = compute_macro_timing(state)

    # NEW: Diversity bonus
    previously_attacked = [a['ev_id'] for a in history]
    if action['ev_id'] not in previously_attacked:
        diversity_bonus = 25  # Bonus for new target
    else:
        diversity_bonus = -10  # Penalty for repeat target

    return 0.4 * macro_score + 0.4 * micro_score + 0.2 * diversity_bonus
```

### 5.3 Architecture Changes

Consider adding a **strategic layer** above the tactical LLM:

```
┌─────────────────────────────────────────────┐
│           Strategic Planner                  │
│  - Tracks attack history per EV              │
│  - Computes cumulative load model            │
│  - Selects next target (diversification)     │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│           Tactical LLM                       │
│  - Given target EV, decides timing           │
│  - Selects power level                       │
│  - Outputs attack action                     │
└─────────────────────────────────────────────┘
```

---

## 6. Conclusions

### 6.1 Key Findings

1. **Timing ≠ Effectiveness**: Superior micro-timing (91 vs 45) did not translate to better outcomes

2. **Diversity Matters**: Target diversification is more important than timing optimization under scarce budgets

3. **Cumulative Model**: The power ramping model requires understanding that same-target attacks overwrite rather than accumulate

4. **Random Advantage**: Random's lack of preference accidentally discovers optimal strategy (diversification)

### 6.2 Implications for Research

This finding has important implications for LLM-based attacker evaluation:

1. **Prompt Engineering**: LLMs need explicit strategic guidance, not just tactical optimization criteria

2. **Context Design**: The information provided to the LLM must include state relevant to strategic decisions

3. **Baseline Validity**: A random baseline can outperform a "smart" attacker if the smart attacker optimizes wrong objectives

4. **Metric Design**: TVD alone is insufficient; need composite metrics that reward both timing AND strategic diversity

### 6.3 Next Steps

1. Implement prompt/context updates to address diversity
2. Re-run validation with updated AI
3. Extend to longer experiments (1-2 hours) to validate sustained performance
4. Consider Option B (power decay) which amplifies diversity importance

---

## Appendix: Raw Data

### A.1 Random Baseline Full Results

```json
{
  "experiment_name": "scarce_random",
  "duration_sec": 300,
  "config": {
    "min_attack_cooldown_sec": 90.0,
    "max_attacks_per_hour": 20,
    "attack_probability": 0.6
  },
  "attack_log": [
    {"elapsed": 5, "ev_id": "EV3", "real_kw": 745, "micro_score": 75, "cycle_position": 0.25},
    {"elapsed": 95, "ev_id": "EV1", "real_kw": 1177, "micro_score": 25, "cycle_position": 0.75},
    {"elapsed": 190, "ev_id": "EV4", "real_kw": 532, "micro_score": 66, "cycle_position": 0.33},
    {"elapsed": 280, "ev_id": "EV2", "real_kw": 1005, "micro_score": 16, "cycle_position": 0.83}
  ],
  "final_metrics": {
    "primary_metrics": {"tvd_sec": 240.0, "total_attacks": 4},
    "timing_metrics": {"avg_micro_score_at_attack": 45.5, "avg_cycle_position_at_attack": 0.54}
  }
}
```

### A.2 AI Attacker Full Results

```json
{
  "experiment_name": "scarce_ai",
  "duration_sec": 300,
  "config": {
    "min_attack_cooldown_sec": 90.0,
    "max_attacks_per_hour": 20,
    "micro_score_threshold": 70
  },
  "attack_log": [
    {"elapsed": 0, "ev_id": "EV1", "real_kw": 700, "micro_score": 83, "cycle_position": 0.17},
    {"elapsed": 110, "ev_id": "EV1", "real_kw": 1200, "micro_score": 100, "cycle_position": 0.00},
    {"elapsed": 235, "ev_id": "EV1", "real_kw": 1500, "micro_score": 91, "cycle_position": 0.08}
  ],
  "final_metrics": {
    "primary_metrics": {"tvd_sec": 120.0, "total_attacks": 3},
    "timing_metrics": {"avg_micro_score_at_attack": 91.33, "avg_cycle_position_at_attack": 0.08}
  }
}
```
