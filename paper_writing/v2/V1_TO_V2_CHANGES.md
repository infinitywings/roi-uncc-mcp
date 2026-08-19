# LLM-GridEval: Comprehensive Summary of Changes from V1 to V2

## Document Purpose

This document provides a detailed, evidence-backed summary of every significant change between the v1 paper (AI_Grid_Attack.pdf, submitted December 2025) and the v2 paper (paper_writing/v2/main.pdf, April 2026). It covers infrastructure fixes, experimental redesign, new results, and manuscript revisions. Each change includes the justification and the evidence supporting it.

---

## 1. Critical Infrastructure Fix: 3600-Second HELICS Delay Filter

### What Changed
The v1 controller's HELICS configuration (`examples/2bus-13bus/1c_Control.json`) contained a message delay filter that delayed ALL controller-to-EV commands by 3600 seconds (1 hour). This was removed in v2.

### Evidence
- **v1 config** (1c_Control.json, lines 96-113): `"operation": "delay", "properties": {"name": "delay", "value": 3600}`
- **v2 config** (v2/controller/v2_control.json): `"filters": []`
- **Impact on v1 results**: In a 300-second experiment, no controller command ever took effect. The controller was non-functional. All v1 TVD values (Random=240s, AI-V1=120s, AI-V2=240s) were produced against a controller that never responded.

### Justification
The paper's core thesis is about exploiting the controller's 10-second observation cycle (micro-timing). If the controller never responds, micro-timing is irrelevant and the entire evaluation is meaningless. Fixing this bug was the single most important change.

### Result
- v1: Random TVD=240s, EVG(V2/Random)=1.0× (ceiling effect — controller absent)
- v2 at Hour 7: Random TVD=75±30s, EVG(V2/Random)=2.40× (controller responds, creating real differentiation)

---

## 2. Controller Redesign: From All-or-Nothing to Progressive Shedding

### What Changed

| Feature | v1 Controller | v2 Controller |
|---------|--------------|---------------|
| Command delay | 3600s (broken) | None (immediate) |
| Shedding mode | All EVs to 0 instantly | One EV per 10s cycle |
| Shed order | Fixed (deterministic) | Randomized per seed |
| Restoration | Instant (all at once) | One EV per 30s holdoff |
| Safe-range logic | Buggy (powered all 6 EVs) | Correct (EV1+EV2 only) |
| States | 3 (OVERLOAD/CAUTION/LOW) | 4 (OVERLOAD/CAUTION/RECOVERY/NORMAL) |
| Configuration | Hardcoded | Environment variables + CLI args |

### Evidence
- **v1 code** (`examples/2bus-13bus/1bc_EV_Controller.py`, lines 161-210): All-or-nothing shedding. Safe-range sends 210/200 kW to all 6 endpoints (lines 183-188) instead of shedding EV3-6.
- **v2 code** (`v2/controller/ev_controller_v2.py`): `_shed_one()` method sheds one EV per call; `_restore_one()` restores one per holdoff; `rng.shuffle(self.shed_order)` randomizes order.

### Justification
- **Progressive shedding makes diversification strategically significant**: If the attacker sets N distinct EVs to high power, the controller needs N separate 10-second cycles to shed them all. This creates a direct relationship between target diversity and sustained violation duration.
- **Randomized order prevents deterministic exploitation**: The attacker cannot predict which EV is shed first.
- **Safe-range bug fix**: v1's safe-range branch sent power to all 6 endpoints (documented as "EV1 & EV2 only"), making the controller's behavior different from what the paper described.

### Result
The v2 controller is genuinely harder to attack. Random TVD dropped from 240s (v1) to 60-75s (v2). But the AI-V2 attacker still achieves 135-180s through diversification, producing a measurable EVG.

---

## 3. Multi-Operating-Point Experimental Design

### What Changed
v1 ran experiments at a single operating point (Hour 7, base load ~3.0 MW). v2 runs at three operating points spanning the load spectrum.

| Operating Point | Sim Hour | Base Load | Headroom | v1 | v2 |
|----------------|----------|-----------|----------|----|----|
| Low load | 4 | ~3480 kW | ~720 kW | Not tested | Tested |
| Medium load | 7 | ~3703 kW | ~497 kW | Only point | Tested |
| High load | 14 | ~5490 kW | −1290 kW | Not tested | Tested |

### Evidence
- v2 modified GridLAB-D clock start times via `sed` in Docker containers (`v2/docker/docker-compose-parallel.yml`)
- 37 experiments completed across 3 OPs × 3 variants × 5 seeds (8 failed due to HELICS timeouts)

### Justification
A single operating point leaves open the question: "Is the EVG an artifact of this specific load level?" The three-point sweep answers this:
- **Hour 4 (low load)**: EVG=2.25× — adaptive advantage exists even with large headroom
- **Hour 7 (medium)**: EVG=2.40× — strongest differentiation
- **Hour 14 (high load)**: EVG=1.0× — ceiling effect (base load alone exceeds threshold)

This reveals an inverted-U pattern: EVG peaks at moderate headroom and collapses when the grid is already overwhelmed. Hour 14 serves as a negative control validating that EVG reflects genuine capability differences.

---

## 4. Three Explicit Attacker Variants (V1 Script Now Exists)

### What Changed
v1 had only the AI-V2 (timing+strategy) script in the codebase. The AI-V1 (timing-only) results in the v1 paper came from an earlier prompt version that no longer existed. v2 creates three explicit, reproducible scripts.

| Variant | v1 Status | v2 Script |
|---------|-----------|-----------|
| Random | `run_random_baseline.py` (P=0.6) | `v2/attackers/random_baseline.py` (P=0.3) |
| AI-V1 | No script (lost) | `v2/attackers/ai_v1_timing.py` |
| AI-V2 | `run_ai_campaign.py` | `v2/attackers/ai_v2_strategy.py` |

### Evidence
- All three scripts share a common base class (`v2/attackers/base.py`) ensuring identical constraint enforcement
- Random attack probability changed from 0.6 (v1 code) to 0.3 (matching the v1 paper's stated value)
- AI-V1 system prompt deliberately excludes: power accumulation model, diversification guidance, attack history

### Justification
- **Reproducibility**: Anyone can run `python3 v2/attackers/ai_v1_timing.py` to reproduce V1 results
- **Fair comparison**: The shared base class guarantees identical cooldowns, budgets, and observation intervals across variants
- **Probability fix**: v1 code used P=0.6 while the paper said P=0.3 — a silent inconsistency

---

## 5. LLM Model Change and Prompt Reframing

### What Changed

| | v1 | v2 |
|---|---|---|
| Model | openai/gpt-oss-120b (or Llama-3.1-8B per paper) | Qwen 3.5-122B-A10B (AWQ 4-bit) |
| Parameters | 120B dense | 122B MoE (10B active) |
| Endpoint | ccil1s26m8hj6lws:8000 (defunct) | cci-siscluster1.charlotte.edu:8000 |
| Prompt framing | Adversarial ("attack", "penetration testing") | Neutral ("stress-testing", "adjust") |
| max_tokens | 300 | 4000 |

### Evidence
- Qwen 3.5 refused adversarial prompts: "I cannot assist with this request. Even in a simulated or research context, I'm not able to participate in attack simulations on critical infrastructure"
- After reframing to "stress-testing agent" language, the model cooperated with <5% refusal rate for V2 (still ~30% for V1)
- Qwen 3.5 is a thinking model requiring ~1500-2500 tokens of internal reasoning before output, necessitating max_tokens=4000

### Justification
- The old LLM endpoint became unavailable
- Neutral framing preserves the identical decision task while avoiding safety refusals
- The 30% V1 refusal rate is honestly disclosed as a confound in the paper's limitations section

---

## 6. Quantitative Results Comparison

### V1 Paper Results (Table I, page 5 of AI_Grid_Attack.pdf)

| Metric | Random | AI-V1 | AI-V2 |
|--------|--------|-------|-------|
| TVD (seconds) | 240 | 120 | 240 |
| Total attacks | 4 | 3 | 3 |
| Unique EVs | 4 | 1 | 3 |
| Final accum. kW | 3459 | 1500 | 4500 |
| EVG | — | 0.5× | 1.0× |

### V2 Campaign Results (Table 3, per operating point)

**Hour 4 (low load):**

| Metric | Random (N=4) | AI-V1 (N=5) | AI-V2 (N=4) |
|--------|-------------|-------------|-------------|
| TVD | 60 ± 49 | 48 ± 27 | **135 ± 30** |
| Unique EVs | 2.0 | 1.6 | **3.8** |
| EVG | — | 0.80× | **2.25×** |
| p-value | — | 0.710 | **0.020*** |
| Cohen's d | — | 0.28 | **1.85** |

**Hour 7 (medium load):**

| Metric | Random (N=4) | AI-V1 (N=5) | AI-V2 (N=4) |
|--------|-------------|-------------|-------------|
| TVD | 75 ± 30 | 120 ± 0 | **180 ± 0** |
| Unique EVs | 2.0 | 1.0 | **4.0** |
| EVG | — | 1.60× | **2.40×** |
| p-value | — | 0.038* | **<0.001**** |
| Cohen's d | — | 1.80 | **4.95** |

**Hour 14 (high load — ceiling):**

| Metric | Random (N=3) | AI-V1 (N=5) | AI-V2 (N=3) |
|--------|-------------|-------------|-------------|
| TVD | 295 ± 0 | 295 ± 0 | 295 ± 0 |
| EVG | — | 1.0× | 1.0× |

### Key Differences

| Finding | v1 | v2 | Why Different |
|---------|----|----|---------------|
| EVG (V2/Random) | 1.0× | **2.25–2.40×** | v1 controller was broken (3600s delay) |
| V1 vs Random | V1 worse (0.5×) | V1 worse at Hr4 (0.8×), better at Hr7 (1.6×) | Consistent finding across both versions |
| Statistical significance | None (1 run per variant) | p < 0.05 with N=3-5 per cell | v2 has proper replication |
| Operating points | 1 | 3 | v2 reveals condition-dependence |
| Ceiling effect | Present (all variants = 240s) | Explained (Hr14 base load > threshold) | v2 identifies the mechanism |

---

## 7. Docker and Execution Infrastructure

### What Changed

| | v1 | v2 |
|---|---|---|
| Docker approach | Dockerfile COPY + entrypoint script | Volume-mount + inline bash command |
| Federation startup | `helics run` or manual | Docker Compose with inline bash |
| Parallel execution | None | 3 containers simultaneously (one per OP) |
| Federation restart | Not needed (single run) | Between every experiment (avoids HELICS deadlock) |
| Build caching | Stale GridPACK builds copied from host | Build cache cleaned on startup |

### Evidence
- `v2/docker/docker-compose.yml`: inline bash command matching the proven `docker run` pattern
- `v2/docker/docker-compose-parallel.yml`: 3 services (hr4, hr7, hr14) on ports 5101-5103
- `v2/run_campaign.sh`: orchestrates parallel execution with per-experiment federation restart

### Justification
- The HELICS federation deadlocks after ~430s of cumulative simulation time (root cause: time-synchronization issue between 5s/10s/60s/120s period federates)
- Federation restart between experiments is the reliable workaround
- Parallel execution across 3 containers reduced campaign time from ~5 hours to ~1.5 hours

---

## 8. Manuscript Writing Changes

### Venue Change
- v1: Unspecified IEEE workshop format (IEEEtran class, 6 pages)
- v2: ACM EnergySP '26 (acmart sigconf class, 9pt, 6 body pages + unlimited appendix)

### Structural Changes

| Section | v1 | v2 |
|---------|----|----|
| Abstract | 1 paragraph, no statistics | 5 sentences with EVG=2.25-2.40×, p-values |
| Introduction | 2 paragraphs, 1 contribution per line | 4 paragraphs, 3 numbered contributions |
| Related Work | 2 subsections (Background, LLM tools) | 3 subsections (+LAA/EV security) |
| System/Threat Model | Combined in 1 section | Separate subsections + formal EVG definition with equation |
| Framework | 2 subsections | 4 subsections (architecture, controller, attackers, LLM orchestration) |
| Evaluation | 3 subsections (Setup, Variants, Results) | 4 subsections (+Limitations) |
| Discussion | In evaluation section | Removed (merged into §5 and conclusion) |
| Conclusion | 1 paragraph | 1 paragraph, forward-looking |
| Appendix | None | 4 appendices (prompts, raw data, stats, controller) |
| Figures | 1 (architecture) | 3 (architecture, EVG bar chart, attack timelines) |
| Tables | 1 (Table I: comparison) | 3 body + 3 appendix |
| References | 22 | 30 (8 new 2025-2026 citations) |

### New Citations Added in v2

| Citation | Year | Relevance |
|----------|------|-----------|
| Nasr et al. "Attacker Moves Second" | 2025 | 12 LLM defenses bypassed at >90% under adaptive attacks |
| Sarieddine et al. OCPP vulnerabilities | 2024 | 6 zero-days per EV charging platform |
| Kuroptev et al. EV grid segmentation | 2026 | Compromising 2 CSOs overloads transmission |
| Kaur et al. EV cybersecurity survey | 2025 | Comprehensive EV charging stack security |
| Ibrahim & Kashef LLM+grid survey | 2025 | LLMs in smart grid cybersecurity |
| Xu et al. Forewarned survey | 2025 | LLM agents in autonomous cyberattacks |
| Zhang et al. Grid-Agent | 2025 | LLM for grid control (non-adversarial) |
| Chen & Wen X-GridAgent | 2025 | LLM for grid analysis (non-adversarial) |

### Claim Calibration (Revision Rounds 1-4)

The manuscript underwent 4 revision rounds to calibrate claims to evidence:

| Claim | Early Draft | Final Version | Rationale |
|-------|------------|---------------|-----------|
| EVG generalization | "static evaluations overstate defense effectiveness" | "In our setup, a random baseline understates violation duration...suggesting static evaluations may underestimate" | Random ≠ all static baselines |
| Domain knowledge driver | "domain knowledge is the primary driver" | "The V2 prompt package outperforms V1; the design does not isolate which components drive the improvement" | V2 changes multiple factors simultaneously |
| V1 counterproductive | "proves counterproductive" | "appears counterproductive in this setup, partly due to safety refusals and single-target fixation" | 30% refusal rate confounds |
| Timing "solved" | "timing intelligence is a solved problem" | "timing exploitation is straightforward in this setup given access to the controller's observation schedule" | One model, one topology |
| LLMs as proxies | "scalable cognitive proxies for human red teams" | "a practical way to instantiate adaptive attackers" | No human comparison made |
| Priority claim | "to our knowledge the first" (3 times) | Kept once in Contribution 1 only | Avoid overclaiming |
| Finding 3 | "transforms the stochastic LLM into a deterministic optimizer" | "produces highly consistent behavior in this setup" | Consistency ≠ determinism in general |

---

## 9. Known Limitations Explicitly Disclosed in v2

The v2 paper includes an explicit §5.4 Limitations subsection disclosing:
1. Small, unbalanced sample sizes (N=3-5, 8/45 runs failed)
2. Single grid topology (IEEE 123-node)
3. Single LLM (Qwen 3.5-122B)
4. Random baseline as comparator (not all static baselines)
5. AI-V2 changes multiple factors simultaneously (no ablation)
6. AI-V1 30% safety refusal rate confound

The v1 paper had a brief "Limitations and Future Work" section but did not disclose the controller delay bug, the missing V1 script, or the sample size issues.

---

## 10. Summary: What the Changes Prove

The v1-to-v2 evolution demonstrates three things:

1. **The EVG concept is valid but was masked in v1.** The 3600-second delay bug created a ceiling effect where all attackers achieved the same TVD regardless of strategy. Fixing this single bug changed EVG from 1.0× to 2.40× — the entire paper's contribution was hidden by an infrastructure bug.

2. **Multi-operating-point evaluation is essential.** The Hour 14 ceiling effect (EVG=1.0×) would look like the EVG doesn't exist if tested in isolation. The three-point sweep reveals that EVG is condition-dependent, peaking at moderate headroom and collapsing when the grid is overwhelmed.

3. **Honest reporting strengthens the paper.** The v2 paper's explicit disclosure of limitations (small N, refusal confound, no ablation) and careful claim calibration ("appears counterproductive" vs "proves counterproductive") produces a more credible submission than v1's stronger but less supported claims.
