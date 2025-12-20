# LLM-GridEval: Experiment Design Report

## Evaluating Adaptive AI Attackers Against Smart Grid Defenses

**Project:** LLM-GridEval  
**Institution:** University of North Carolina at Charlotte  
**Target Venue:** IEEE/ACM Workshop on AI and Security  
**Document Version:** 1.0  
**Date:** December 2024

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Research Questions and Hypotheses](#2-research-questions-and-hypotheses)
3. [Theoretical Framework](#3-theoretical-framework)
4. [Experimental Design](#4-experimental-design)
5. [System and Threat Model](#5-system-and-threat-model)
6. [Metrics and Measurements](#6-metrics-and-measurements)
7. [Statistical Analysis Plan](#7-statistical-analysis-plan)
8. [Expected Results](#8-expected-results)
9. [Timeline and Resources](#9-timeline-and-resources)
10. [Validity and Limitations](#10-validity-and-limitations)

---

## 1. Executive Summary

### 1.1 Research Problem

Current smart grid security evaluations predominantly rely on static datasets or pre-scripted attack scenarios. This creates an **Evaluation Validity Gap (EVG)**: defenses that appear robust against static benchmarks may be significantly less effective against adaptive, feedback-driven adversaries.

### 1.2 Research Objective

This experiment aims to quantify the EVG by comparing the effectiveness of:
- **Random attacks**: No timing intelligence, decisions based on fixed probability
- **AI-adaptive attacks**: LLM-based attacker exploiting two-level timing intelligence

### 1.3 Core Thesis

> Adaptive LLM-based attackers achieve 2-3× higher effectiveness (measured by Threshold Violation Duration) than random baselines by exploiting macro-timing (load patterns) and micro-timing (controller cycle gaps), demonstrating that conventional evaluations significantly underestimate adversarial capability.

### 1.4 Key Innovation: Two-Level Timing Intelligence

| Level | What It Exploits | How It's Measured |
|-------|------------------|-------------------|
| **Macro-timing** | High-load periods with low headroom to threshold | Peak Hour Attack Ratio (PHAR) |
| **Micro-timing** | Gaps in defender observation/action cycles | Attack Cycle Position (lower = better) |

---

## 2. Research Questions and Hypotheses

### 2.1 Research Questions

| ID | Research Question |
|----|-------------------|
| **RQ1** | How effectively can LLM-based attackers exploit temporal patterns in grid operations compared to random attackers? |
| **RQ2** | Does two-level timing intelligence (macro + micro) significantly improve attack success rates? |
| **RQ3** | How does defender response time (controller interval) affect the relative advantage of intelligent attackers? |
| **RQ4** | What is the magnitude of the Evaluation Validity Gap for AI vs. static attack evaluations? |

### 2.2 Hypotheses

| ID | Hypothesis | Statistical Test | α |
|----|------------|------------------|---|
| **H1** | AI attackers achieve significantly higher TVD than random attackers under identical constraints | One-tailed independent t-test | 0.05 |
| **H2** | AI attackers concentrate attacks during peak load hours (PHAR > 50%) while random attackers show uniform distribution (PHAR ≈ 33%) | One-sample t-test against 33% | 0.05 |
| **H3** | AI attackers exploit micro-timing by attacking early in controller cycles (avg cycle position < 0.3) while random attackers show uniform distribution (≈ 0.5) | One-sample t-test | 0.05 |
| **H4** | The Evaluation Validity Gap (EVG = AI_TVD / Random_TVD) is significantly greater than 1.5× | One-sample t-test | 0.05 |
| **H5** | AI attackers at faster controller intervals (60s) match or exceed random attacker performance at slower intervals (120s) | Cross-condition comparison | 0.05 |

### 2.3 Null Hypotheses

| ID | Null Hypothesis |
|----|-----------------|
| **H0-1** | There is no significant difference in TVD between AI and random attackers |
| **H0-2** | AI attackers do not preferentially attack during peak hours |
| **H0-3** | AI attackers do not exploit controller cycle timing |
| **H0-4** | EVG ≤ 1.0 (AI performs equal or worse than random) |

---

## 3. Theoretical Framework

### 3.1 Evaluation Validity Gap Formalization

Let $E(M, A)$ denote an evaluation functional that maps a defense mechanism $M$ and attack process $A$ to performance metrics.

**Definition (Evaluation Validity Gap):**
$$\Delta E(M) = E(M, A_{adaptive}) - E(M, A_{static})$$

Where:
- $A_{static}$: Attack process with fixed/random policy $\pi_{static}$
- $A_{adaptive}$: Attack process with adaptive policy $\pi_{adaptive}$ that reacts to observations

A positive $\Delta E(M)$ indicates the defense appears more effective under adaptive evaluation than static, quantifying how much static evaluations underestimate true adversarial capability.

### 3.2 Two-Level Timing Intelligence Model

#### Macro-Timing Function

$$\text{MacroScore}(t) = f(\text{headroom}(t), \text{is\_peak}(t))$$

Where:
- $\text{headroom}(t) = \text{threshold} - \text{load}(t)$
- $\text{is\_peak}(t) = \mathbb{1}[\text{hour}(t) \in \text{PeakHours}]$

**Scoring Logic:**
```
headroom ≤ 0      → score = 100 (already in violation)
headroom < 500    → score = 90  (critical)
headroom < 1000   → score = 75  (favorable)
headroom < 1500   → score = 55  (moderate)
headroom < 2000   → score = 35  (limited)
headroom ≥ 2000   → score = 15  (poor)
+ 15 bonus if is_peak = true
```

#### Micro-Timing Function

$$\text{MicroScore}(t) = (1 - \text{CyclePosition}(t)) \times 100$$

Where:
$$\text{CyclePosition}(t) = \frac{(t - t_{last\_controller}) \mod T_{controller}}{T_{controller}}$$

- $\text{CyclePosition} = 0$: Controller just acted (BEST for attacker)
- $\text{CyclePosition} = 1$: Controller about to act (WORST for attacker)

#### Combined Decision Function

$$\text{CombinedScore} = 0.6 \times \text{MacroScore} + 0.4 \times \text{MicroScore}$$

**Decision Matrix:**

| Condition | Recommendation |
|-----------|----------------|
| MacroScore ≥ 50 AND MicroScore ≥ 70 | ATTACK_NOW |
| CombinedScore ≥ 50 | ATTACK_POSSIBLE |
| MicroScore ≥ 70 AND MacroScore < 50 | WAIT_FOR_LOAD |
| Otherwise | WAIT |

### 3.3 Fair Comparison Framework

To ensure valid comparison, both attackers operate under **identical constraints**:

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Observation interval | 5 seconds | Both can observe at same frequency |
| Attack cooldown | 30 seconds | Prevents rapid-fire attacks |
| Hourly budget | 60 attacks | Limits total attack volume |
| Power range | 1500-3500 kW | Same manipulation capability |
| Valid targets | EV1-EV6 | Same attack surface |

**The ONLY difference is decision logic:**
- Random: $P(\text{attack}) = 0.3$ per eligible observation
- AI: Attack when timing intelligence recommends AND LLM confirms

---

## 4. Experimental Design

### 4.1 Design Type

**2 × 2 × 3 Mixed Factorial Design**

| Factor | Type | Levels | Values |
|--------|------|--------|--------|
| **Attacker Type** | Between-subjects | 2 | Random, AI |
| **Controller Interval** | Within-subjects | 2 | 60s, 120s |
| **Replicate** | Blocking | 3 | Seeds 1, 2, 3 |

Plus **Baseline** condition (no attacks) for reference.

### 4.2 Experimental Matrix

| Run ID | Attacker | Interval | Seed | Duration |
|--------|----------|----------|------|----------|
| baseline_60s_r1 | None | 60s | 1 | 7200s |
| baseline_60s_r2 | None | 60s | 2 | 7200s |
| baseline_60s_r3 | None | 60s | 3 | 7200s |
| baseline_120s_r1 | None | 120s | 1 | 7200s |
| baseline_120s_r2 | None | 120s | 2 | 7200s |
| baseline_120s_r3 | None | 120s | 3 | 7200s |
| random_60s_r1 | Random | 60s | 1 | 7200s |
| random_60s_r2 | Random | 60s | 2 | 7200s |
| random_60s_r3 | Random | 60s | 3 | 7200s |
| random_120s_r1 | Random | 120s | 1 | 7200s |
| random_120s_r2 | Random | 120s | 2 | 7200s |
| random_120s_r3 | Random | 120s | 3 | 7200s |
| ai_60s_r1 | AI | 60s | 1 | 7200s |
| ai_60s_r2 | AI | 60s | 2 | 7200s |
| ai_60s_r3 | AI | 60s | 3 | 7200s |
| ai_120s_r1 | AI | 120s | 1 | 7200s |
| ai_120s_r2 | AI | 120s | 2 | 7200s |
| ai_120s_r3 | AI | 120s | 3 | 7200s |

**Total: 18 experimental runs**

### 4.3 Independent Variables

| Variable | Type | Levels | Operationalization |
|----------|------|--------|-------------------|
| **Attacker Type** | Categorical | {None, Random, AI} | Decision algorithm used |
| **Controller Interval** | Continuous (discretized) | {60s, 120s} | `CONTROLLER_INTERVAL_SEC` environment variable |
| **Random Seed** | Blocking | {1, 2, 3} | Seeds for load profiles and random decisions |

### 4.4 Dependent Variables

| Variable | Symbol | Unit | Measurement Method |
|----------|--------|------|-------------------|
| **Threshold Violation Duration** | TVD | seconds | Cumulative time where load > 4200 kW |
| **Attack Success Rate** | ASR | % | (Attacks causing violation / Total attacks) × 100 |
| **Peak Hour Attack Ratio** | PHAR | % | (Attacks during peak hours / Total attacks) × 100 |
| **Mean Attack Cycle Position** | MACP | 0-1 | Average cycle_position at attack time |
| **Evaluation Validity Gap** | EVG | ratio | AI_TVD / Random_TVD |

### 4.5 Control Variables

| Variable | Controlled Value | Rationale |
|----------|------------------|-----------|
| Grid topology | IEEE 9-bus + 123-node | Standardized test system |
| Protection threshold | 4200 kW | Fixed defense trigger point |
| Simulation duration | 7200s (2 hours) | Sufficient for statistical significance |
| Attack constraints | See §4.1 | Ensure fair comparison |
| LLM model | gpt-oss-120b | Consistent AI capability |
| LLM temperature | 0.3 | Balanced exploration/exploitation |

---

## 5. System and Threat Model

### 5.1 Grid System Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                     HELICS Co-Simulation Federation                  │
│                                                                      │
│  ┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐    │
│  │  GridPACK    │   │   GridLAB-D      │   │   GridLAB-D      │    │
│  │  Transmission│◄─►│   Feeder A       │   │   Feeder B       │    │
│  │  IEEE 9-bus  │   │   123-node + EVs │   │   123-node       │    │
│  └──────────────┘   └────────┬─────────┘   └──────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│                    ┌─────────────────────┐                          │
│                    │   EV Controller     │  ◄── Defense (Blue Team) │
│                    │   (Threshold-based) │                          │
│                    └─────────────────────┘                          │
│                              ▲                                       │
│                              │ Competes for EV setpoints            │
│                              │                                       │
│                    ┌─────────────────────┐                          │
│                    │   MCP Server        │  ◄── Attacker Interface  │
│                    │   (Attack API)      │                          │
│                    └─────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 EV Charging Infrastructure

| EV ID | Phase | Location | Normal kW | Max Attack kW | Storage |
|-------|-------|----------|-----------|---------------|---------|
| EV1 | C | Link l5 | 220 | 4000 | Yes |
| EV2 | B | Link l2 | 200 | 4000 | No |
| EV3 | A | Link l88 | 200 | 4000 | No |
| EV4 | C | Link l92 | 220 | 4000 | Yes |
| EV5 | B | Link l107 | 200 | 4000 | No |
| EV6 | A | Link l114 | 200 | 4000 | No |

**Total normal load**: ~1.2 MW  
**Total attack capacity**: ~24 MW (if all at max)

### 5.3 Defense Mechanism (Blue Team)

The EV Controller implements threshold-based demand response:

```python
THRESHOLD_UPPER = 4200 kW  # Protection trigger
THRESHOLD_LOWER = 2600 kW  # Recovery threshold

def controller_action(feeder_power):
    if feeder_power >= THRESHOLD_UPPER:
        # OVERLOAD: Disconnect all EVs
        for ev in ALL_EVS:
            set_power(ev, 0)
    elif feeder_power <= THRESHOLD_LOWER:
        # LOW LOAD: Enable all EVs
        for ev in ALL_EVS:
            set_power(ev, normal_power[ev])
    else:
        # SAFE BAND: Partial operation
        set_power(EV1, 210)
        set_power(EV2, 200)
        for ev in [EV3, EV4, EV5, EV6]:
            set_power(ev, 0)
```

**Controller Interval**: Configurable (60s or 120s for experiments)

### 5.4 Threat Model

#### Adversary Capabilities
- **Read Access**: Aggregate feeder power, EV setpoints via `get_grid_status()`
- **Write Access**: EV charging capacities via `set_ev_capacity(ev_id, P)`
- **Computational Resources**: Access to LLM for decision-making

#### Adversary Limitations
- Cannot access transmission system internals
- Cannot modify protection relay settings
- Subject to attack constraints (cooldown, budget)
- Actions visible to defender (no stealth requirement)

#### Adversary Goal
Maximize Threshold Violation Duration (TVD) - time the feeder spends in overload condition (>4200 kW).

### 5.5 Attack Primitives

| Primitive | Parameters | Effect |
|-----------|------------|--------|
| `observe()` | include_history | Returns current grid state |
| `analyze()` | controller_interval | Returns timing intelligence |
| `attack(ev_id, real_kw)` | ev_id ∈ {EV1..EV6}, real_kw ∈ [1500, 3500] | Sets EV power |
| `get_metrics()` | - | Returns experiment statistics |

---

## 6. Metrics and Measurements

### 6.1 Primary Metrics

#### 6.1.1 Threshold Violation Duration (TVD)

**Definition**: Cumulative time the feeder power exceeds the protection threshold.

$$\text{TVD} = \sum_{t} \Delta t \cdot \mathbb{1}[\text{load}(t) > 4200]$$

**Measurement**: Computed from continuous feeder power monitoring at 5-second intervals.

**Interpretation**:
- TVD = 0: Defense successful (no violations)
- Higher TVD: More time in overload = more attack success

#### 6.1.2 Attack Success Rate (ASR)

**Definition**: Percentage of attacks that caused or maintained a threshold violation.

$$\text{ASR} = \frac{\text{Attacks causing violation}}{\text{Total attacks}} \times 100\%$$

**Measurement**: Each attack logged with pre/post load and violation status.

#### 6.1.3 Evaluation Validity Gap (EVG)

**Definition**: Ratio of AI attacker effectiveness to random attacker effectiveness.

$$\text{EVG} = \frac{\text{TVD}_{AI}}{\text{TVD}_{Random}}$$

**Interpretation**:
- EVG = 1.0: No advantage from timing intelligence
- EVG = 2.0: AI achieves 2× the violation duration
- EVG = 3.0: AI achieves 3× the violation duration

### 6.2 Timing Intelligence Metrics

#### 6.2.1 Peak Hour Attack Ratio (PHAR)

**Definition**: Percentage of attacks occurring during peak load hours.

$$\text{PHAR} = \frac{|\{a : \text{hour}(a) \in \text{PeakHours}\}|}{|\text{All attacks}|} \times 100\%$$

**Peak Hours**: {15, 16, 17, 18, 19, 20} (3 PM - 8 PM)

**Expected Values**:
- Random: ~33% (6 peak hours / 18 waking hours)
- AI: >50% (intelligent targeting)

#### 6.2.2 Mean Attack Cycle Position (MACP)

**Definition**: Average position in controller cycle when attacks occur.

$$\text{MACP} = \frac{1}{n}\sum_{i=1}^{n} \text{CyclePosition}(t_i)$$

Where $t_i$ is the time of attack $i$.

**Expected Values**:
- Random: ~0.5 (uniform distribution)
- AI: <0.3 (attacks early in cycle when window is largest)

#### 6.2.3 Average Micro Score at Attack

**Definition**: Mean micro-timing score when attacks are executed.

$$\bar{S}_{micro} = \frac{1}{n}\sum_{i=1}^{n} \text{MicroScore}(t_i)$$

**Expected Values**:
- Random: ~50 (uniform)
- AI: >70 (waits for favorable timing)

### 6.3 Constraint Compliance Metrics

| Metric | Definition | Expected |
|--------|------------|----------|
| Total Attacks | Number of attack commands executed | Similar for AI and Random |
| Attacks Blocked (Cooldown) | Attacks prevented by 30s cooldown | Low (constraints respected) |
| Attacks Blocked (Budget) | Attacks prevented by hourly budget | Low (budget not exhausted) |

---

## 7. Statistical Analysis Plan

### 7.1 Descriptive Statistics

For each condition, compute:
- Mean, standard deviation, and 95% confidence interval
- Median and interquartile range
- Min/max values

### 7.2 Hypothesis Tests

#### H1: AI TVD > Random TVD

**Test**: Independent samples t-test (one-tailed)

```python
from scipy import stats

ai_tvd = [ai_60s_r1.tvd, ai_60s_r2.tvd, ai_60s_r3.tvd, 
          ai_120s_r1.tvd, ai_120s_r2.tvd, ai_120s_r3.tvd]
random_tvd = [random_60s_r1.tvd, ..., random_120s_r3.tvd]

t_stat, p_value = stats.ttest_ind(ai_tvd, random_tvd, alternative='greater')
```

**Decision Rule**: Reject H0-1 if p < 0.05

#### H2: AI PHAR > 33%

**Test**: One-sample t-test against expected value

```python
ai_phar = [ai_run.phar for ai_run in ai_runs]
t_stat, p_value = stats.ttest_1samp(ai_phar, 33.33)
p_one_tailed = p_value / 2 if t_stat > 0 else 1 - p_value / 2
```

**Decision Rule**: Reject H0-2 if p < 0.05 and mean > 33%

#### H3: AI MACP < 0.5

**Test**: One-sample t-test against expected value

```python
ai_macp = [ai_run.macp for ai_run in ai_runs]
t_stat, p_value = stats.ttest_1samp(ai_macp, 0.5)
p_one_tailed = p_value / 2 if t_stat < 0 else 1 - p_value / 2
```

**Decision Rule**: Reject H0-3 if p < 0.05 and mean < 0.5

#### H4: EVG > 1.5

**Test**: One-sample t-test

```python
evg_values = [ai_tvd[i] / random_tvd[i] for i in range(len(ai_tvd))]
t_stat, p_value = stats.ttest_1samp(evg_values, 1.5)
```

**Decision Rule**: Reject H0-4 if p < 0.05 and mean > 1.5

### 7.3 Effect Size

**Cohen's d** for comparing AI vs. Random:

$$d = \frac{\bar{X}_{AI} - \bar{X}_{Random}}{s_{pooled}}$$

Where:
$$s_{pooled} = \sqrt{\frac{(n_1-1)s_1^2 + (n_2-1)s_2^2}{n_1+n_2-2}}$$

**Interpretation**:
- d = 0.2: Small effect
- d = 0.5: Medium effect
- d = 0.8: Large effect

### 7.4 Two-Way ANOVA

To examine interaction effects:

**Factors**: Attacker Type (Random, AI) × Controller Interval (60s, 120s)

**Model**: TVD ~ Attacker + Interval + Attacker × Interval

```python
import statsmodels.api as sm
from statsmodels.formula.api import ols

model = ols('TVD ~ C(Attacker) * C(Interval)', data=df).fit()
anova_table = sm.stats.anova_lm(model, typ=2)
```

### 7.5 Multiple Comparison Correction

For multiple hypotheses, apply **Bonferroni correction**:

$$\alpha_{adjusted} = \frac{\alpha}{k} = \frac{0.05}{5} = 0.01$$

Where k = 5 (number of hypotheses tested).

---

## 8. Expected Results

### 8.1 Primary Metric Predictions

| Condition | TVD (s) | ASR (%) | PHAR (%) | MACP |
|-----------|---------|---------|----------|------|
| baseline_60s | 0 | N/A | N/A | N/A |
| baseline_120s | 0 | N/A | N/A | N/A |
| random_60s | 120 ± 50 | 25 ± 10 | 33 ± 5 | 0.50 ± 0.05 |
| random_120s | 250 ± 80 | 35 ± 12 | 33 ± 5 | 0.50 ± 0.05 |
| **ai_60s** | **300 ± 70** | **55 ± 15** | **65 ± 10** | **0.25 ± 0.08** |
| **ai_120s** | **500 ± 100** | **65 ± 15** | **70 ± 12** | **0.22 ± 0.07** |

### 8.2 Expected EVG Values

| Controller Interval | EVG (AI/Random) | Interpretation |
|--------------------|-----------------|----------------|
| 60s | **2.5×** | AI achieves 2.5× more violation time |
| 120s | **2.0×** | AI advantage persists but diminishes with slower defense |

### 8.3 Expected Statistical Outcomes

| Hypothesis | Expected Result | Expected p-value | Effect Size |
|------------|-----------------|------------------|-------------|
| H1 (AI TVD > Random TVD) | **Reject H0** | p < 0.01 | d > 1.0 (large) |
| H2 (AI PHAR > 33%) | **Reject H0** | p < 0.01 | d > 1.5 (large) |
| H3 (AI MACP < 0.5) | **Reject H0** | p < 0.01 | d > 1.2 (large) |
| H4 (EVG > 1.5) | **Reject H0** | p < 0.05 | - |
| H5 (AI@60s ≈ Random@120s) | **Support** | Non-significant difference | d < 0.3 |

### 8.4 Visualization Plan

#### Figure 1: TVD by Condition
Bar chart with error bars showing TVD for each (Attacker × Interval) combination.

#### Figure 2: Evaluation Validity Gap
Bar chart showing EVG by controller interval with horizontal line at EVG=1.0.

#### Figure 3: Timing Intelligence Exploitation
Dual panel:
- (a) PHAR distribution: AI vs Random vs Expected 33%
- (b) Attack cycle position distribution: Histogram comparing AI (clustered at 0-0.3) vs Random (uniform)

#### Figure 4: Attack Timeline
Time series showing attacks (vertical lines) overlaid on feeder power, with controller intervals marked.

---

## 9. Timeline and Resources

### 9.1 Three-Day Execution Plan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DAY 1: VALIDATION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ 0:00-2:00  │ Environment setup, LLM connectivity test                       │
│ 2:00-4:00  │ Parameter alignment, code review                               │
│ 4:00-6:00  │ Short validation runs (30 min each)                            │
│ 6:00-8:00  │ Debug, verify AI TVD > Random TVD                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                           DAY 2: EXPERIMENTS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 0:00-12:00 │ Run 18 experiments (automated, ~40 min each)                   │
│ 12:00-14:00│ Verify completeness, re-run failures                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                           DAY 3: ANALYSIS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 0:00-2:00  │ Run statistical analysis script                                │
│ 2:00-4:00  │ Generate figures and tables                                    │
│ 4:00-6:00  │ Interpret results, write findings                              │
│ 6:00-8:00  │ Draft results section for paper                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Computational Resources

| Resource | Specification | Purpose |
|----------|---------------|---------|
| Simulation Server | 64-core CPU, 512 GB RAM | HELICS co-simulation |
| LLM Server | gpt-oss-120b @ http://ccil1s26m8hj6lws:8000 | AI attack decisions |
| Storage | ~50 GB | Logs, results, traces |

### 9.3 Time Estimates

| Phase | Estimated Time |
|-------|----------------|
| Single experiment run | ~40 minutes |
| All 18 experiments | ~12 hours |
| Analysis and figures | ~2 hours |
| **Total execution** | **~15 hours** |

---

## 10. Validity and Limitations

### 10.1 Internal Validity

| Threat | Mitigation |
|--------|------------|
| **Confounding variables** | Identical constraints for AI and Random |
| **Selection bias** | Random seed blocking across conditions |
| **Instrumentation** | Same MCP server and metrics collection for all runs |
| **History effects** | Simulation reset between runs |

### 10.2 External Validity

| Limitation | Impact | Future Work |
|------------|--------|-------------|
| Single grid topology | May not generalize to other networks | Test on IEEE 37, 123 variants |
| Simplified defense | Real controllers more sophisticated | Test against MPC, ML-based defenses |
| LLM-specific | Results may vary with different LLMs | Compare GPT-4, Claude, Llama |
| 2-hour duration | May miss long-term patterns | Extend to 24-hour simulations |

### 10.3 Construct Validity

| Metric | Validity Concern | Justification |
|--------|------------------|---------------|
| TVD | Measures physical impact | Directly relates to grid stress duration |
| PHAR | Assumes peak hours known | Reflects realistic load patterns |
| MACP | Assumes observable cycles | Controller timing detectable via load changes |

### 10.4 Known Limitations

1. **Simplified Threat Model**: Attacker has perfect observation of feeder load; real attacks may have partial observability.

2. **No Stealth Requirement**: Attacker actions are visible; adding IDS could change dynamics.

3. **Single Defense Type**: Only threshold-based controller tested; results may differ with advanced defenses.

4. **LLM Variability**: AI decisions may vary across runs even with same prompt; temperature=0.3 provides some consistency.

5. **Simulation vs. Reality**: HELICS co-simulation abstracts real-world communication delays and measurement errors.

---

## Appendix A: Experiment Checklist

### Pre-Experiment

- [ ] LLM endpoint responding: `curl http://ccil1s26m8hj6lws:8000/v1/models`
- [ ] Docker images built: `roi-img:latest`
- [ ] Grid simulation starts: All HELICS federates connect
- [ ] MCP server health check: `curl http://localhost:5100/health`
- [ ] Threshold aligned: Controller uses 4200 kW (not 4.8 MW)
- [ ] Constraints verified: Both attackers use same config

### During Experiment

- [ ] Log files generated for each run
- [ ] No simulation crashes or deadlocks
- [ ] LLM responses parsing correctly
- [ ] Metrics being recorded

### Post-Experiment

- [ ] All 18 JSON result files present
- [ ] Baseline TVD = 0 (sanity check)
- [ ] AI TVD > Random TVD (main result)
- [ ] Statistical tests run
- [ ] Figures generated

---

## Appendix B: LaTeX Table Template

```latex
\begin{table}[t]
\centering
\caption{Attack Effectiveness and Evaluation Validity Gap}
\label{tab:results}
\begin{tabular}{llrrrr}
\toprule
\textbf{Attacker} & \textbf{Interval} & \textbf{TVD (s)} & \textbf{ASR (\%)} & \textbf{PHAR (\%)} & \textbf{EVG} \\
\midrule
Baseline & 60s  & 0 & -- & -- & -- \\
Baseline & 120s & 0 & -- & -- & -- \\
\midrule
Random   & 60s  & 120$\pm$50  & 25$\pm$10 & 33$\pm$5 & -- \\
Random   & 120s & 250$\pm$80  & 35$\pm$12 & 33$\pm$5 & -- \\
\midrule
AI       & 60s  & 300$\pm$70  & 55$\pm$15 & 65$\pm$10 & \textbf{2.5$\times$} \\
AI       & 120s & 500$\pm$100 & 65$\pm$15 & 70$\pm$12 & \textbf{2.0$\times$} \\
\bottomrule
\end{tabular}
\end{table}
```

---

*End of Experiment Design Report*
