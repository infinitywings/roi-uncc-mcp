# LLM-GridEval: Complete Manuscript Blueprint for ACM EnergySP '26

**Self-contained reference: sentence-level outline + verified BibTeX + figure specs**

---

# PART I: DETAILED MANUSCRIPT OUTLINE

## Title

**LLM-GridEval: Measuring the Evaluation Validity Gap in Smart Grid Security with Adaptive LLM Attackers**

## Venue Constraints

ACM EnergySP '26. 4–6 pages body (9pt ACM double-column), unlimited references/appendices. Non-anonymous.

---

## Abstract (~150 words, 5 sentences)

**Sentence 1 (Context — attack surface):** Cloud-hosted EV management platforms expose programmatic control interfaces over charging fleets, creating API-level attack surfaces through which adversaries can coordinate load-altering attacks that propagate from distribution feeders into the bulk transmission system.

**Sentence 2 (Gap — evaluation problem):** Yet security evaluations for grid defenses overwhelmingly rely on static datasets or pre-scripted attack scenarios, producing an *evaluation validity gap* (EVG): a discrepancy between a defense's measured performance against static benchmarks and its actual robustness against adaptive, observation-driven adversaries.

**Sentence 3 (Method — our framework):** We introduce LLM-GridEval, a framework that embeds adaptive, tool-using large language model (LLM) attackers into a HELICS-based transmission–distribution co-simulation through a schema-constrained attack primitive interface, enabling direct comparison of static and adaptive attack processes under identical physical conditions and resource constraints.

**Sentence 4 (Result — quantitative finding):** In a 37-experiment campaign across three grid operating points, a strategy-aware LLM attacker achieves 2.25–2.40× the threshold violation duration of a random baseline (p < 0.05, Cohen's d = 1.85–4.95), while a timing-only LLM attacker proves insufficient and even counterproductive under low-load conditions.

**Sentence 5 (Implication):** These results demonstrate that static evaluations can overstate grid defense effectiveness by a factor of two or more, motivating the inclusion of adaptive adversary models in security evaluation methodologies for API-driven, EV/DER-rich grids.

---

## §1 Introduction (~0.75 pages, 4 paragraphs)

---

### ¶1 — The converging attack surface (5 sentences)

**S1 (Trend):** The digitalization of transportation and the electrification of distributed energy resources are converging to create a power grid increasingly managed through software interfaces—cloud-based EV fleet management platforms, SCADA systems, and programmatic APIs that schedule charging and DER setpoints across thousands of devices.

**S2 (Benefit → risk):** While this integration improves operational flexibility and observability, it simultaneously exposes logic-level attack surfaces: adversaries who compromise an EV or DER management platform gain programmatic control over aggregate load, enabling coordinated load-altering attacks that can propagate from distribution feeders into the transmission system.

**S3 (Evidence — EV vulns):** This threat is not hypothetical—Sarieddine et al. \cite{sarieddine2024ocpp} discovered six zero-day vulnerabilities in each of 16 live EV charging management systems through OCPP backend analysis, enabling man-in-the-middle attacks and grid-destabilizing switching commands.

**S4 (Evidence — DER vulns + grid impact):** In the DER domain, the Forescout SUN:DOWN report identified 129 CVEs across major solar inverter management platforms exposing over 1 TW of capacity to remote control, and Kuroptev et al. \cite{kuroptev2026evgrid} demonstrated using real German charging station data that compromising just two Charging Station Operators suffices to overload transmission grid branches beyond N-1 security margins.

**S5 (Transition):** As these programmatic attack surfaces proliferate, the question of how to evaluate grid defenses against adversaries who exploit them becomes increasingly urgent.

---

### ¶2 — The evaluation problem and EVG concept (5 sentences)

**S1 (Current practice):** The smart grid security community has developed a rich ecosystem of co-simulation frameworks and intrusion detection testbeds \cite{cintuglu2017testbeds, smadi2021testbeds}, but most evaluation methodologies still rely on static datasets—widely used traces such as SWaT \cite{goh2017swat}, WADI \cite{ahmed2017wadi}, EPIC \cite{adepu2019epic}, and HAI \cite{shin2020hai} capture fixed attack trajectories under specific operating conditions—or on a small number of pre-scripted attack scenarios as in GridAttackSim \cite{le2020gridattacksim}.

**S2 (Core problem):** Static traces and scripts cannot capture the action–reaction dynamics between adaptive attackers and responsive defenses: when a controller sheds load in response to an attack, a static attacker continues its pre-programmed sequence regardless, while an adaptive attacker can observe the defensive response and adjust its strategy in real time.

**S3 (Define EVG):** We term the resulting discrepancy the *evaluation validity gap* (EVG): the ratio of a defense's stress under an adaptive attacker to its stress under a comparable static attacker, where EVG > 1.0 indicates that static evaluations underestimate adversarial risk.

**S4 (Parallel from adversarial ML):** This phenomenon has been extensively documented in adversarial machine learning—Carlini et al. \cite{carlini2019evaluating} established best practices for adaptive evaluation, and Nasr et al. \cite{nasr2025attacker} recently demonstrated that 12 LLM defenses reporting near-zero attack success rates under static evaluation were bypassed at over 90\% success under adaptive attacks—but has not been formally studied or quantified in smart grid security evaluation.

**S5 (Research question):** This paper asks: does a measurable evaluation validity gap exist in smart grid security, and if so, what attacker capabilities drive it?

---

### ¶3 — Our approach: LLMs as adaptive attackers (4 sentences)

**S1 (Core idea):** To answer this question, we introduce LLM-GridEval, a framework that embeds tool-using LLM agents as adaptive attackers inside a HELICS-based transmission–distribution co-simulation \cite{hardy2024helics}, connecting them to the grid through a schema-constrained catalog of attack primitives that ensures all actions are physically realizable.

**S2 (Why LLMs):** We use LLMs as scalable cognitive proxies for human red teams: they can reason over grid state observations, assess timing opportunities, and select actions from the primitive catalog without requiring environment-specific training—unlike reinforcement learning approaches that demand scenario-specific reward shaping and state representations \cite{sahani2023mlids}.

**S3 (Key design insight):** A critical architectural choice is the schema-constrained primitive interface, which sidesteps the LLM code-generation reliability problem identified by Sen et al. \cite{sen2024aiattacker}, who found that current LLMs produce only "partially usable" attack code for grid systems; by constraining the LLM to *select* validated actions rather than *generate* arbitrary commands, we make LLM-driven grid attacks feasible and reproducible.

**S4 (Scope note):** We emphasize that LLMs are not proposed as optimal attackers but as a practical, explainable, and generalizable approach to adaptive adversary modeling that complements existing static and RL-based methods.

---

### ¶4 — Contributions (3 numbered items)

**Contribution 1 (Framework):** We present LLM-GridEval, to our knowledge the first framework coupling tool-using LLM agents with physics-accurate T\&D co-simulation via schema-constrained attack primitives for adversarial security evaluation. The framework's layered architecture enables controlled experimentation by allowing researchers to swap attacker implementations (scripted, RL-based, or LLM-based) while holding the co-simulation and tool interface fixed.

**Contribution 2 (Empirical results):** We conduct a 37-experiment campaign across three grid operating points (low, medium, and high base load) comparing three attacker variants—a random static baseline, an LLM attacker with timing intelligence only, and an LLM attacker with timing plus power-system domain knowledge—against a progressive-shedding controller. The strategy-aware attacker achieves EVG = 2.25–2.40× at operating points where the controller can respond (p < 0.05, d = 1.85–4.95), while EVG correctly collapses to 1.0× at a ceiling operating point where the controller is overwhelmed.

**Contribution 3 (Insight on attacker capabilities):** We demonstrate that domain knowledge—specifically understanding of power accumulation dynamics and target diversification—is the primary driver of the evaluation validity gap, while timing intelligence alone is insufficient and even counterproductive at low-load conditions (EVG = 0.80×), providing concrete guidance for both prompt engineering of CPS red-teaming agents and the design of adaptive-aware defense evaluations.

---

## §2 Related Work (~0.6 pages, 3 subsections)

---

### §2.1 Smart Grid Security Evaluation (~0.2 pages, 1 paragraph)

**S1 (Co-simulation foundation):** HELICS \cite{hardy2024helics} has emerged as the dominant open-source framework for multi-domain grid co-simulation, supporting time-coordinated interaction between transmission solvers, distribution simulators, and control applications.

**S2 (Static datasets):** Security evaluation in this space has traditionally relied on static attack datasets—SWaT \cite{goh2017swat}, WADI \cite{ahmed2017wadi}, EPIC \cite{adepu2019epic}, and HAI \cite{shin2020hai} provide recordings of scripted attack campaigns against industrial control and power systems, while survey work \cite{sahani2023mlids} highlights that evaluation results from such traces may not generalize to adaptive adversaries.

**S3 (Co-sim testbeds):** Security-focused co-simulation platforms such as GridAttackSim \cite{le2020gridattacksim} combine power system and network simulation but rely on predefined attack profiles fixed before execution, representing what we term Generation 1 evaluation tools with high-fidelity environments but adversary logic fixed in advance.

**S4 (Gap statement):** No existing framework couples *adaptive*, observation-driven adversary agents with physics-accurate T\&D co-simulation to study how defense performance changes under dynamic attack strategies.

---

### §2.2 LLM-Based Offensive Security and Grid AI (~0.2 pages, 1 paragraph)

**S1 (IT-focused LLM tools):** Recent advances in LLM-based offensive security have produced systems such as PentestGPT \cite{deng2024pentestgpt}, which orchestrates penetration testing through LLM reasoning over tool outputs, and AutoAttacker \cite{xu2024autoattacker}, which automates cyber-attack implementation; a comprehensive survey by Xu et al. \cite{xu2025forewarned} covers the rapidly expanding landscape of LLM agents in autonomous cyberattacks.

**S2 (ICS-specific):** In the industrial control domain, Ahmed \cite{ahmed2025attackllm} developed AttackLLM for generating ICS attack patterns, while Fang et al. \cite{fang2024llmexploit} demonstrated that LLM agents can autonomously exploit one-day vulnerabilities without human guidance, and Janjusevic et al. \cite{janjusevic2025mcp} showed that MCP-based LLM agents can achieve domain dominance on corporate networks in under an hour.

**S3 (LLMs for grid operations):** In the power systems domain, several recent systems—Grid-Agent \cite{zhang2025gridagent} for multi-agent grid control and X-GridAgent \cite{chen2025xgridagent} for grid analysis—demonstrate that LLM agents can be effectively coupled with grid simulators, but all focus on *operations and control* rather than adversarial security testing.

**S4 (Closest prior + differentiation):** The closest prior work is Sen et al. \cite{sen2024aiattacker}, who developed AI-based attacker models for multi-stage cyberattack simulations in smart grids using co-simulation but critically found that current LLMs produce unreliable attack code; LLM-GridEval's schema-constrained primitive interface addresses this limitation by constraining the LLM to validated action selection rather than open-ended code generation.

---

### §2.3 Load-Altering Attacks and EV Infrastructure Security (~0.2 pages, 1 paragraph)

**S1 (LAA taxonomy):** Maleki et al. \cite{maleki2025laa} provide a comprehensive taxonomy of load-altering attacks against power grids covering attack impact, detection, and mitigation, while Reda et al. \cite{reda2022fdia} survey false data injection attacks—both attack modalities that can exploit the programmatic interfaces of modern EV and DER management platforms.

**S2 (EV-specific vulns):** The EV charging ecosystem presents a particularly rich attack surface: Sarieddine et al. \cite{sarieddine2024ocpp} demonstrated OCPP backend vulnerabilities in live systems, Kaur et al. \cite{kaur2025evcsur} provide a comprehensive survey of cybersecurity challenges across the EV charging stack, and Kuroptev et al. \cite{kuroptev2026evgrid} quantified the transmission-level impact of EV charging attacks using real infrastructure data.

**S3 (LLMs + grid security):** Ibrahim and Kashef \cite{ibrahim2025llmgrid} survey the emerging intersection of LLMs and smart grid cybersecurity, identifying both offensive and defensive applications but noting the lack of frameworks that embed LLM agents directly into grid co-simulation for adversarial evaluation.

**S4 (Positioning):** To our knowledge, LLM-GridEval is the first framework that combines (i) tool-using LLM agents, (ii) physics-accurate T\&D co-simulation via HELICS, and (iii) schema-constrained attack primitives for adversarial security evaluation of smart grids.

---

## §3 System and Threat Model (~0.4 pages)

---

### §3.1 System Model (~0.2 pages, 1 paragraph + Table I)

**S1 (Grid model):** We model the smart grid as a discrete-time cyber-physical system comprising an IEEE 9-bus transmission network simulated by GridPACK \cite{palmer2016gridpack} and two IEEE 123-node distribution feeders \cite{schneider2018testfeeders} simulated by GridLAB-D \cite{chassin2014gridlabd}, integrated via the HELICS co-simulation framework \cite{hardy2024helics} with conservative time advancement.

**S2 (EV stations):** Feeder A hosts six EV charging stations (EV1–EV6) distributed across phases A, B, and C at different nodes, with nominal power of 200 kW each and a maximum attack-settable capacity of 1500 kW; EV1 and EV4 are co-located with 205 kWh lithium-ion battery storage systems.

**S3 (Feeder B):** Feeder B contains only uncontrollable background loads and provides demand diversity but no controllable EV stations.

**S4 (Timing):** The federation operates with a multi-rate timing hierarchy: GridPACK advances at 5-second intervals, the MCP attacker server at 5 seconds, the defensive controller at 10 seconds, and GridLAB-D's power flow solver at 60 seconds—creating a 2:1 attacker-to-controller observation ratio that forms the basis of the micro-timing exploit.

**S5 (Operating points):** To study condition-dependence, we evaluate at three operating points corresponding to different simulation clock start times, spanning from low base load (~3480 kW, ~720 kW headroom below the 4200 kW protection threshold) through medium load (~3703 kW, ~497 kW headroom) to high load (~5490 kW, already exceeding the threshold)—see Table~I.

**[Table I: Operating Points — exact content as in previous blueprint]**

---

### §3.2 Threat Model (~0.15 pages, 1 paragraph)

**S1 (Adversary position):** The adversary has compromised the EV Management and Control Platform (MCP) server that provides programmatic control over the EV charging fleet—a threat model grounded in the documented real-world vulnerabilities of OCPP-based backends \cite{sarieddine2024ocpp} and DER management platforms.

**S2 (Capabilities):** The adversary has read access to aggregate feeder measurements and individual EV setpoints via a \texttt{get\_grid\_status()} primitive, and write access to EV charging capacities within the range [500, 1500] kW via a \texttt{set\_ev\_capacity(ev\_id, P)} primitive.

**S3 (Limitations):** The adversary cannot directly observe transmission system internal states or protection relay settings, cannot modify relay configurations, and cannot exceed per-device capacity bounds.

**S4 (Resource constraints):** To ensure fair comparison across attacker variants, all attackers operate under identical resource constraints: a minimum 90-second cooldown between consecutive attacks (upper-bounding the rate to approximately 3–4 attacks per 300-second experiment), a power ramping rate limit of 100 kW/s to prevent solver instability, and a budget of 20 attacks per hour.

---

### §3.3 Evaluation Validity Gap Definition (~0.05 pages, inline)

**S1 (Formal definition):** For a defense M evaluated under stress metric $\mathcal{E}$ (where higher values indicate greater grid stress) and attack budget B, we define the Evaluation Validity Gap as $\text{EVG}(\mathcal{E}, M, B) = \mathcal{E}(M, \pi_{\text{adapt}}, B) / \mathcal{E}(M, \pi_{\text{static}}, B)$, where $\pi_{\text{adapt}}$ and $\pi_{\text{static}}$ denote adaptive and static attack policies respectively.

**S2 (Primary metric):** We instantiate $\mathcal{E}$ as Threshold Violation Duration (TVD): cumulative seconds during which feeder power exceeds the protection threshold $P_{\max}$ = 4200 kW, so that EVG > 1.0 indicates the adaptive attacker achieves longer violation durations than the static baseline under equal resource constraints.

---

## §4 LLM-GridEval Framework (~0.8 pages)

---

### §4.1 Framework Architecture (~0.25 pages, 1 paragraph + Figure 1)

**S1 (Overview):** LLM-GridEval integrates the system model into a unified evaluation environment through three layers (Fig.~1): a co-simulation layer, an interface and tool layer, and a cognitive layer.

**S2 (Co-sim layer):** The co-simulation layer implements the physical plant through a HELICS federation with five time-synchronized federates: a GridPACK transmission federate (IEEE 9-bus), two GridLAB-D distribution federates (IEEE 123-node feeders, with Feeder A containing EV loads), a feeder controller federate implementing the defensive policy, and an MCP attacker server federate that bridges the interface layer.

**S3 (Interface layer):** The interface and tool layer acts as a sandboxed API boundary between the co-simulation and the attacker, implemented as a FastAPI HTTP server wrapping a HELICS federate; each attack primitive is defined by a JSON schema specifying inputs, outputs, preconditions, and the mapping to HELICS operations, and the layer performs argument validation and constraint enforcement (capacity bounds, cooldown timers, ramping rate limits) before invoking HELICS calls, ensuring that all actions issued by any attacker—including a fully autonomous LLM—are physically realizable and auditable.

**S4 (Cognitive layer):** The cognitive layer hosts the attacker policy $\pi$ using a ReAct-style interaction loop: (1) observe grid state via \texttt{get\_grid\_status()}, (2) assess timing via macro and micro scoring, (3) query the LLM for an action specification, (4) validate the response against the primitive schema, (5) execute via the sandboxed interface, and (6) advance the simulation clock.

**S5 (Key design property):** This layered separation enables controlled experimentation: researchers can swap attacker implementations—scripted baselines, RL agents, or LLM-based policies—while keeping the co-simulation and tool interface fixed, isolating the impact of policy changes on measured outcomes.

→ **[Figure 1: Architecture diagram — see Part III for full specification]**

---

### §4.2 Progressive-Shedding Controller (Blue Team) (~0.15 pages, 1 paragraph)

**S1 (Overview):** The defender is a state-machine-based feeder controller (v2) that polls total feeder power at the swing node every 10 seconds and operates in three states.

**S2 (OVERLOAD):** In the OVERLOAD state ($P_{\text{feeder}} \geq$ 4200 kW), the controller sheds one active EV per 10-second observation cycle in a randomized order that varies per experiment seed, requiring N controller cycles to shed N simultaneously active EVs—a property that makes target diversification strategically significant for attackers.

**S3 (CAUTION + RECOVERY):** In the CAUTION state (2600 < $P$ < 4200 kW), the controller maintains EV1 and EV2 at nominal power while shedding EV3–EV6; in the RECOVERY state ($P \leq$ 2600 kW), it restores one previously shed EV per 30-second holdoff period.

**S4 (Design note):** This controller represents a realistic baseline congestion management mechanism; commands arrive immediately with no message delay (correcting a critical 3600-second delay bug in the v1 prototype that rendered the controller non-functional during experiments).

---

### §4.3 Attacker Variants (Red Team) (~0.2 pages, 1 paragraph + Table II)

**S1 (Design rationale):** We evaluate three attacker policies through the same MCP primitive interface, ensuring that observed differences in outcomes reflect policy quality rather than interface advantages.

**S2 (Random):** The random baseline ($\pi_{\text{static}}$) represents a static, non-adaptive policy: at each 5-second observation interval, if the 90-second cooldown has elapsed, it attacks with probability P = 0.3, selecting the target EV uniformly from \{EV1, …, EV6\} and power uniformly from [500, 1500] kW, with no awareness of grid state, controller timing, or attack history.

**S3 (AI-V1):** AI-V1 ($\pi_{\text{adapt}}^{(1)}$) uses Qwen 3.5-122B (a mixture-of-experts thinking model with 122B total and 10B active parameters) with a timing gate that pre-filters observations before LLM invocation: the LLM is called only when the micro-timing score exceeds 70 (indicating the controller just acted, leaving a ≥7-second window) and the cooldown has elapsed; the system prompt provides timing score interpretation but includes no information about the power accumulation model, no diversification guidance, and no attack history.

**S4 (AI-V2):** AI-V2 ($\pi_{\text{adapt}}^{(2)}$) extends V1 with explicit domain knowledge injected into the system prompt: an explanation that EV power contributions are additive across distinct targets but overwrite when the same EV is re-attacked, a priority instruction to attack unmodified EVs before repeating any target, and dynamic per-call context showing which EVs have been attacked and their current power levels—identical model, identical interface, identical constraints, different prompt content.

**S5 (Power accumulation):** This power accumulation model—where $P_{\text{total}} = P_{\text{base}} + \sum_{i=1}^{6} P_{EV_i}$ with overwrite semantics on same-EV re-attacks—means that three attacks on EV1 at 1500 kW contribute only 1500 kW total, while three attacks on EV1, EV2, and EV3 at 1500 kW each contribute 4500 kW, making target diversification essential for effective load accumulation.

**[Table II: Attacker Variant Comparison — 5 rows comparing Random, AI-V1, AI-V2]**

---

### §4.4 LLM Orchestration Details (~0.2 pages, 1 paragraph)

**S1 (Timing gate mechanics):** The timing gate reduces LLM invocations from approximately 60 per experiment (one per 5-second observation) to 5–14 (only when timing criteria are met), using a two-level scoring system: a macro-timing score (0–100) that assesses headroom between current load and the 4200 kW threshold, and a micro-timing score (0–100) that maps the attacker's position within the controller's 10-second observation cycle, where a score of 100 indicates the controller just acted and the attacker has a full 10-second window before the next defensive check.

**S2 (V2 strategic context):** In AI-V2, each LLM call receives a dynamic strategic context block showing the shrinking list of unattacked EVs (e.g., [EV2, EV3, EV4, EV5, EV6] after the first attack), the per-EV attack count and current power level, and an explicit instruction to target unmodified EVs first at maximum power (1500 kW); this context deterministically steers the LLM through a systematic target sweep.

**S3 (Model details):** All LLM-based experiments use Qwen 3.5-122B-A10B (AWQ 4-bit quantization) served via vLLM, with temperature 0.3 and max\_tokens 4000 to accommodate the model's internal chain-of-thought reasoning (which consumes ~1500–2500 tokens before producing the visible JSON output); prompts use neutral "stress-testing" framing to avoid safety refusals from the model's guardrails.

**S4 (Response format):** The LLM returns a JSON object specifying a reasoning string, a decision ("adjust" or "wait"), and—when adjusting—an action with the target EV identifier and power level in kW, which is validated against the primitive schema before execution.

---

## §5 Evaluation (~1.7 pages)

---

### §5.1 Experimental Setup (~0.2 pages, 1 paragraph)

**S1 (Matrix):** We conducted a campaign of 3 attacker variants × 3 operating points × 5 random seeds = 45 planned experiments, each running for 300 seconds (5 minutes) of simulation time with fresh federation restart between experiments to avoid HELICS time-synchronization deadlocks.

**S2 (Completion):** Of the 45 planned experiments, 37 completed successfully (82\%); 8 failed due to HELICS timeout errors, with seed 2 systematically failing across multiple variants (a reproducible interaction between specific random number sequences and HELICS federation timing), yielding final sample sizes of N = 5 for AI-V1 at all operating points, N = 3–4 for Random, and N = 3–4 for AI-V2.

**S3 (Infrastructure):** Three Docker containers ran in parallel (one per operating point), each hosting the full HELICS federation with GridPACK, two GridLAB-D instances, the v2 controller, and the MCP attacker server; attacker scripts ran on the host machine communicating with the MCP server via HTTP on port 5100.

**S4 (Metrics):** The primary metric is Threshold Violation Duration (TVD); secondary metrics include attack success rate (ASR, fraction of attacks after which $P_{\text{feeder}}$ exceeds $P_{\max}$), mean attack cycle position (MACP, average position in the controller's 10-second cycle when attacks occur, where 0.0 is optimal), unique EVs targeted (measuring diversification), and per-attack efficiency (TVD divided by total attacks).

---

### §5.2 Main Results (~0.4 pages, 2 paragraphs + Tables III and IV)

**¶1 — Table III walkthrough (5 sentences):**

**S1:** Table~III presents the complete results across all nine experimental cells.

**S2 (Hr4):** At Hour 4 (low load, ~720 kW headroom), AI-V2 achieves TVD = 135 ± 30 s compared to Random's 60 ± 49 s, while AI-V1 achieves only 48 ± 27 s—lower than random—due to its timing gate consuming attack opportunities while its single-target fixation (mean 1.6 unique EVs vs. V2's 3.8) limits cumulative load impact.

**S3 (Hr7):** At Hour 7 (medium load, ~497 kW headroom), the differentiation is sharpest: AI-V2 achieves TVD = 180 ± 0 s with perfect consistency across all seeds, AI-V1 achieves 120 ± 0 s with consistent but lower performance (targeting only 1.0 unique EVs), and Random achieves 75 ± 30 s.

**S4 (Hr14):** At Hour 14 (high load, base load exceeding threshold by 1290 kW), all three variants achieve identical TVD = 295 ± 0 s—the full experiment duration minus startup transients—because the controller cannot reduce feeder power below the threshold even with all EVs shed, rendering attacker strategy irrelevant.

**S5 (ASR note):** Attack success rates at Hour 14 are 0\% for all variants because the violations are caused by base load, not by attacks; the attacker's actions are superfluous in this regime, which serves as a negative control validating that the EVG metric reflects genuine attacker capability rather than measurement artifacts.

**[Table III: Main Results Across Operating Points]**

**¶2 — Table IV: EVG summary (3 sentences):**

**S1:** Table~IV summarizes the evaluation validity gap with statistical tests.

**S2:** AI-V2 achieves EVG = 2.25× at Hour 4 (p = 0.020, d = 1.85) and EVG = 2.40× at Hour 7 (p = 0.0002, d = 4.95), both statistically significant with large effect sizes; AI-V1 achieves EVG = 0.80× at Hour 4 (below random) and EVG = 1.60× at Hour 7.

**S3:** At Hour 14, EVG = 1.00× for both adaptive variants, confirming that the gap vanishes when the defender is overwhelmed and validating the metric's discriminant validity.

**[Table IV: EVG Summary with p-values and effect sizes]**

---

### §5.3 Analysis (~0.7 pages, 3 paragraphs corresponding to 3 findings)

---

**¶1 — Finding 1: The EVG is real, significant, and condition-dependent (5 sentences)**

**S1 (Headline):** The primary result is that the evaluation validity gap is real and statistically significant: at both operating points where the controller has capacity to respond (Hours 4 and 7), AI-V2 achieves 2.25–2.40× the violation duration of the random baseline, with large effect sizes (Cohen's d = 1.85–4.95) that indicate practically meaningful differences.

**S2 (Practical meaning):** In concrete terms, a security evaluation using only random or scripted attacks at Hour 7 would report the progressive-shedding controller as limiting violations to 75 seconds, while the same controller permits 180 seconds of violation against a strategy-aware adaptive attacker under identical resource constraints—an overestimation of defense effectiveness by a factor of 2.4.

**S3 (Condition-dependence):** The EVG varies systematically with grid headroom, following an inverted-U pattern: it is highest at Hour 7 (2.40×) where moderate headroom provides enough space for adaptive strategy to differentiate but enough stress for violations to occur, somewhat lower at Hour 4 (2.25×) where large headroom limits even V2's ability to trigger violations, and collapses to 1.0× at Hour 14 where no headroom remains.

**S4 (Negative control):** The Hour 14 result serves as a critical negative control: because base load alone exceeds the threshold, all attacker actions are superfluous and the EVG correctly reports no adaptive advantage, demonstrating that the metric is not inflated by confounds inherent to the co-simulation.

**S5 (Parallel):** This condition-dependence mirrors Nasr et al.'s \cite{nasr2025attacker} finding in LLM security that the gap between static and adaptive evaluation varies with defense difficulty—a pattern that appears to generalize across security domains.

---

**¶2 — Finding 2: Domain knowledge is the primary driver; timing alone is counterproductive (6 sentences)**

**S1 (Timing equivalence):** Both AI variants achieve identical, perfect micro-timing at all operating points: cycle position 0.00 and micro-timing score 100, meaning every LLM-issued attack arrives immediately after the controller acts, exploiting the full 10-second observation window; timing intelligence is therefore a solved problem for both variants.

**S2 (Diversification gap):** The entire V2-vs-V1 performance gap is driven by strategic knowledge—specifically target diversification: V2 consistently targets 3.8–4.0 unique EVs across all operating points while V1 targets 1.0–1.6, with enormous effect sizes (d = 4.1–7.3, p < 0.001) on the unique-EVs metric.

**S3 (Why diversification matters):** This dominance arises from the interaction between the additive power accumulation model and the progressive-shedding controller: the controller must shed each attacked EV in a separate 10-second cycle, so N diversified attacks create a violation that requires N controller cycles (10N seconds) to resolve, whereas N attacks on the same EV create a violation resolvable in a single cycle.

**S4 (V1 counterproductivity):** The sharpest result is V1's underperformance at Hour 4 (EVG = 0.80×, below the random baseline), where V1's timing gate causes it to wait for high micro-timing scores rather than attacking immediately, consuming scarce time within the 300-second window; combined with its persistent single-target fixation (attacking EV1 exclusively in most seeds), V1 executes fewer effective attacks than the random baseline, which at least achieves accidental diversification (mean 2.0 unique EVs).

**S5 (Implication for LLM agents):** This demonstrates that timing optimization without domain context represents locally optimal but globally suboptimal decision-making—a failure mode characteristic of LLMs operating with insufficient physical grounding—and suggests that prompt engineering for CPS red-teaming must encode system dynamics (power accumulation, controller response patterns), not merely protocol-level timing information.

**S6 (For defenders):** For defenders, this implies that attacks requiring multi-step physical reasoning (accumulating load across diverse targets) are qualitatively different from timing exploits and may require different detection strategies.

---

**¶3 — Finding 3: Strategic prompting produces deterministic, reproducible behavior (4 sentences)**

**S1 (V2 consistency):** AI-V2 exhibits zero TVD variance ($\sigma$ = 0) at Hour 7 and low variance ($\sigma$ = 30 s) at Hour 4 across all seeds, following a near-identical attack sequence everywhere: EV1 → EV2 → EV3 → EV4, each at 1500 kW, each at cycle position 0.00—the strategic prompt transforms the stochastic LLM into a deterministic optimizer.

**S2 (V1 variance):** In contrast, AI-V1 exhibits high variance ($\sigma$ = 27 s at Hour 4, range 48–240 s at Hour 7 across seeds): in some seeds it fixates on EV1 exclusively while in others (notably seed 2 at Hour 7) it spontaneously diversifies to EV3 without explicit instruction—a behavioral pattern that is unreliable and unreproducible.

**S3 (Practical impact):** This consistency distinction has direct implications for security evaluation: V1's stochasticity means a single experiment could produce EVG anywhere from 0.5× to 3.2× depending on the seed, while V2 consistently produces EVG = 2.40× at Hour 7, enabling reliable risk estimation.

**S4 (Anchoring mechanism):** The mechanism is the dynamic strategic context in V2's prompt—the shrinking unattacked-EV list and explicit diversification instruction anchor the LLM's target selection, overriding the model's tendency toward default or habitual choices (EV1 fixation) that dominate V1's behavior.

→ **[Figure 2: EVG bar chart — see Part III]**
→ **[Figure 3: Attack timelines — see Part III]**

---

## §6 Discussion and Limitations (~0.5 pages)

---

### §6.1 Implications for Practice (~0.2 pages, 1 paragraph with 3 sub-points)

**S1 (For defense evaluation):** These results suggest that grid security benchmarks should complement static dataset evaluations with adaptive adversary testing and report the EVG alongside traditional metrics; an EVG of 2.4× at a given operating point means the defense is 2.4× less effective against adaptive threats than its static benchmark suggests, providing a quantitative basis for assessing evaluation adequacy.

**S2 (For CPS red teaming):** The schema-constrained primitive interface pattern—where LLMs *select* actions from a validated catalog rather than *generate* arbitrary commands—is applicable beyond EV scenarios to any CPS with a programmable API (SCADA systems, building management, industrial IoT) and addresses the core LLM reliability concern identified by Sen et al. \cite{sen2024aiattacker}.

**S3 (For attacker modeling):** The V1 counterproductivity result demonstrates that naive LLM agent design—providing "intelligence" without physical grounding—can produce *worse* outcomes than random, cautioning against uncritical deployment of LLM-based red-teaming tools in CPS domains where physical dynamics couple actions across time and space.

---

### §6.2 Limitations (~0.3 pages, 1 paragraph listing 6 items, then 2-sentence future work)

**S1 (Sample size):** The sample sizes (N = 3–5 per cell) are adequate for the observed large effect sizes (d > 1.8) but preclude precise confidence interval estimation; the systematic seed-2 failure pattern reduces some cells to N = 3.

**S2 (Scope):** All experiments use a single grid topology (IEEE 123-node feeder), a single LLM (Qwen 3.5-122B), and a single defense mechanism (threshold-based progressive shedding); different configurations may yield different EVG magnitudes.

**S3 (Attack surface):** The current primitive catalog is limited to two primitives (observe and set capacity), capturing only one attack modality; real adversaries may combine load manipulation with measurement spoofing, firmware compromise, or V2G discharge exploitation.

**S4 (Defender sophistication):** The threshold-based controller lacks anomaly detection capabilities; a more sophisticated defender incorporating ML-based intrusion detection would likely *increase* the EVG by reducing the random attacker's success rate more than the adaptive attacker's.

**S5 (V1 confound):** AI-V1 experienced approximately 30\% safety refusal rate from Qwen 3.5's guardrails, reducing its effective attack rate; V1's lower TVD is partly an artifact of missed attack opportunities, though its single-target fixation is visible even in successful attacks.

**S6 (Power model):** The additive per-EV power model is a simplification of real OCPP hierarchical profile stacking with per-site power caps; the model correctly captures the relative advantage of diversification but may overestimate individual attack impact.

**S7 (Future work):** Ongoing work extends the evaluation with an RL-based attacker baseline for comparison against the dominant adaptive paradigm, an ML-based anomaly-detecting defender to study how EVG scales with defender sophistication, a richer attack primitive catalog including false data injection, and longer campaigns to test sustained attack resource management.

---

## §7 Conclusion (~0.15 pages, 4 sentences)

**S1:** We introduced LLM-GridEval, to our knowledge the first framework coupling adaptive, tool-using LLM attackers with physics-accurate grid co-simulation through schema-constrained attack primitives for adversarial security evaluation.

**S2:** A 37-experiment campaign across three grid operating points demonstrated a statistically significant evaluation validity gap of 2.25–2.40× (p < 0.05, d = 1.85–4.95): adaptive LLM attackers achieve over twice the violation duration of random baselines where the defender can respond, while the gap correctly vanishes at a ceiling operating point where the defender is overwhelmed.

**S3:** Domain knowledge—specifically understanding of power accumulation dynamics and target diversification—is the primary driver of this gap, with timing intelligence alone proving insufficient and counterproductive at low-load conditions (EVG = 0.80×).

**S4:** These results demonstrate that static security evaluations materially underestimate adversarial risk in API-driven, EV/DER-rich grids, motivating the routine inclusion of adaptive adversary models in defense evaluation methodology.

---

## Appendices (Unlimited Pages)

### Appendix A: Complete LLM Prompts

Full verbatim text of:
- AI-V1 system prompt (timing intelligence only, ~15 lines)
- AI-V2 system prompt additions (power accumulation model, diversification strategy, ~20 lines)
- Example AI-V2 dynamic user prompt with grid state, timing scores, and strategic context
- Example LLM JSON response with reasoning field

### Appendix B: Per-Experiment Raw Data

- Complete attack action sequences for all 37 experiments (target, power, timestamp)
- Per-seed timing metrics table (micro score, cycle position, macro score)
- Full experiment manifest showing completed and failed runs with failure modes

### Appendix C: Statistical Tests

- Full hypothesis test results for all operating points (V2>Random, V2>V1, unique EVs comparisons)
- Per-OP t-statistics, p-values, and effect sizes (Cohen's d)

### Appendix D: Controller v2 Design

- State machine specification and comparison with v1
- Description of the 3600-second delay bug and its impact on v1 results
- Controller configuration parameters (YAML)

---
---

# PART II: VERIFIED BIBTEX FILE

All entries verified against publisher websites (IEEE Xplore, ACM DL, Springer, USENIX, MDPI, Wiley, Elsevier, Frontiers) and arXiv. No fabricated content.

```bibtex
% ============================================================
% GROUP 1: Grid co-simulation and testbed infrastructure
% ============================================================

@article{hardy2024helics,
  author    = {Trevor D. Hardy and Bryan Palmintier and Philip L. Top
               and Dheepak Krishnamurthy and Jason C. Fuller},
  title     = {{HELICS}: A Co-Simulation Framework for Scalable
               Multi-Domain Modeling and Analysis},
  journal   = {IEEE Access},
  volume    = {12},
  pages     = {24325--24347},
  year      = {2024},
  doi       = {10.1109/ACCESS.2024.3363615},
}

@article{chassin2014gridlabd,
  author    = {David P. Chassin and Jason C. Fuller and Ned Djilali},
  title     = {{GridLAB-D}: An Agent-Based Simulation Framework
               for Smart Grids},
  journal   = {Journal of Applied Mathematics},
  volume    = {2014},
  pages     = {1--12},
  year      = {2014},
  doi       = {10.1155/2014/492320},
  note      = {Article ID 492320},
}

@article{palmer2016gridpack,
  author    = {Bruce J. Palmer and William A. Perkins and Yousu Chen
               and Shuangshuang Jin and David Callahan
               and Kevin A. Glass and Ruisheng Diao and Mark J. Rice
               and Stephen T. Elbert and Mallikarjuna R. Vallem
               and Zhenyu Huang},
  title     = {{GridPACK}\texttrademark: A Framework for Developing
               Power Grid Simulations on High-Performance Computing
               Platforms},
  journal   = {International Journal of High Performance Computing
               Applications},
  volume    = {30},
  number    = {2},
  pages     = {223--240},
  year      = {2016},
  doi       = {10.1177/1094342015607609},
}

@article{schneider2018testfeeders,
  author    = {Kevin P. Schneider and B. A. Mather and
               B. C. Pal and C.-W. Ten and G. J. Shirek and
               H. Zhu and J. C. Fuller and J. L. R. Pereira and
               L. F. Ochoa and L. R. de Araujo and
               R. C. Dugan and S. Matthias and S. Paudyal and
               T. E. McDermott and W. Kersting},
  title     = {Analytic Considerations and Design Basis for the
               {IEEE} Distribution Test Feeders},
  journal   = {IEEE Transactions on Power Systems},
  volume    = {33},
  number    = {3},
  pages     = {3181--3188},
  year      = {2018},
  doi       = {10.1109/TPWRS.2017.2760011},
}

% ============================================================
% GROUP 2: ICS/CPS security datasets
% ============================================================

@inproceedings{goh2017swat,
  author    = {Jonathan Goh and Sridhar Adepu and
               Khurum Nazir Junejo and Aditya Mathur},
  title     = {A Dataset to Support Research in the Design of
               Secure Water Treatment Systems},
  booktitle = {Critical Information Infrastructures Security
               (CRITIS 2016)},
  series    = {LNCS},
  volume    = {10242},
  pages     = {88--99},
  publisher = {Springer},
  year      = {2017},
  doi       = {10.1007/978-3-319-71368-7_8},
}

@inproceedings{ahmed2017wadi,
  author    = {Chuadhry Mujeeb Ahmed and
               Venkata Reddy Palleti and Aditya P. Mathur},
  title     = {{WADI}: A Water Distribution Testbed for Research
               in the Design of Secure Cyber Physical Systems},
  booktitle = {Proceedings of the 3rd International Workshop on
               Cyber-Physical Systems for Smart Water Networks
               (CySWATER '17)},
  pages     = {25--28},
  publisher = {ACM},
  year      = {2017},
  doi       = {10.1145/3055366.3055375},
}

@inproceedings{adepu2019epic,
  author    = {Sridhar Adepu and Nandha Kumar Kandasamy
               and Aditya Mathur},
  title     = {{EPIC}: An Electric Power Testbed for Research and
               Training in Cyber Physical Systems Security},
  booktitle = {Computer Security -- ESORICS 2018 Workshops
               (CyberICPS/SECPRE 2018)},
  series    = {LNCS},
  volume    = {11387},
  pages     = {37--52},
  publisher = {Springer},
  year      = {2019},
  doi       = {10.1007/978-3-030-12786-2_3},
}

@inproceedings{shin2020hai,
  author    = {Hyeok-Ki Shin and Woomyo Lee and
               Jeong-Han Yun and HyoungChun Kim},
  title     = {{HAI} 1.0: {HIL}-based Augmented {ICS} Security
               Dataset},
  booktitle = {13th USENIX Workshop on Cyber Security
               Experimentation and Test (CSET '20)},
  publisher = {USENIX Association},
  year      = {2020},
  url       = {https://www.usenix.org/conference/cset20/presentation/shin},
}

@article{le2020gridattacksim,
  author    = {Tan Duy Le and Adnan Anwar and Seng W. Loke
               and Razvan Beuran and Yasuo Tan},
  title     = {{GridAttackSim}: A Cyber Attack Simulation Framework
               for Smart Grids},
  journal   = {Electronics},
  volume    = {9},
  number    = {8},
  pages     = {1218},
  year      = {2020},
  doi       = {10.3390/electronics9081218},
  publisher = {MDPI},
}

% ============================================================
% GROUP 3: Smart grid security surveys
% ============================================================

@article{sahani2023mlids,
  author    = {Nitasha Sahani and Ruoxi Zhu and
               Jin-Hee Cho and Chen-Ching Liu},
  title     = {Machine Learning-based Intrusion Detection for
               Smart Grid Computing: A Survey},
  journal   = {ACM Transactions on Cyber-Physical Systems},
  volume    = {7},
  number    = {2},
  pages     = {1--31},
  year      = {2023},
  doi       = {10.1145/3578366},
  note      = {Article 11},
}

@article{maleki2025laa,
  author    = {Sajjad Maleki and Shijie Pan and
               Subhash Lakshminarayana and
               Charalambos Konstantinou},
  title     = {Survey of Load-Altering Attacks Against Power Grids:
               Attack Impact, Detection, and Mitigation},
  journal   = {IEEE Open Access Journal of Power and Energy},
  volume    = {12},
  pages     = {220--234},
  year      = {2025},
  doi       = {10.1109/OAJPE.2025.3562052},
}

@article{reda2022fdia,
  author    = {Haftu Tasew Reda and Adnan Anwar and
               Abdun Mahmood},
  title     = {Comprehensive Survey and Taxonomies of False Data
               Injection Attacks in Smart Grids: Attack Models,
               Targets, and Impacts},
  journal   = {Renewable and Sustainable Energy Reviews},
  volume    = {163},
  pages     = {112423},
  year      = {2022},
  doi       = {10.1016/j.rser.2022.112423},
}

@article{cintuglu2017testbeds,
  author    = {Mehmet H. Cintuglu and Osama A. Mohammed
               and Kemal Akkaya and A. Selcuk Uluagac},
  title     = {A Survey on Smart Grid Cyber-Physical System
               Testbeds},
  journal   = {IEEE Communications Surveys \& Tutorials},
  volume    = {19},
  number    = {1},
  pages     = {446--464},
  year      = {2017},
  doi       = {10.1109/COMST.2016.2627399},
}

@article{smadi2021testbeds,
  author    = {Abdallah A. Smadi and Babatunde Tobi Ajao
               and Brian K. Johnson and Hangtian Lei
               and Yacine Chakhchoukh
               and Qutaiba Abu Al-Haija},
  title     = {A Comprehensive Survey on Cyber-Physical Smart Grid
               Testbed Architectures: Requirements and Challenges},
  journal   = {Electronics},
  volume    = {10},
  number    = {9},
  pages     = {1043},
  year      = {2021},
  doi       = {10.3390/electronics10091043},
  publisher = {MDPI},
}

% ============================================================
% GROUP 4: LLM-based offensive security tools
% ============================================================

@inproceedings{deng2024pentestgpt,
  author    = {Gelei Deng and Yi Liu and
               V{\'\i}ctor Mayoral-Vilches and Peng Liu and
               Yuekang Li and Yuan Xu and Tianwei Zhang and
               Yang Liu and Martin Pinzger and Stefan Rass},
  title     = {{PentestGPT}: Evaluating and Harnessing Large
               Language Models for Automated Penetration Testing},
  booktitle = {33rd USENIX Security Symposium
               (USENIX Security '24)},
  pages     = {847--864},
  publisher = {USENIX Association},
  year      = {2024},
  url       = {https://www.usenix.org/conference/usenixsecurity24/presentation/deng},
}

@article{xu2024autoattacker,
  author    = {Jiacen Xu and Jack W. Stokes and Geoff McDonald
               and Xuesong Bai and David Marshall and Siyue Wang
               and Adith Swaminathan and Zhou Li},
  title     = {{AutoAttacker}: A Large Language Model Guided System
               to Implement Automatic Cyber-attacks},
  journal   = {arXiv preprint arXiv:2403.01038},
  year      = {2024},
  doi       = {10.48550/arXiv.2403.01038},
}

@article{ahmed2025attackllm,
  author    = {Chuadhry Mujeeb Ahmed},
  title     = {{AttackLLM}: {LLM}-based Attack Pattern Generation
               for an Industrial Control System},
  journal   = {arXiv preprint arXiv:2504.04187},
  year      = {2025},
  doi       = {10.48550/arXiv.2504.04187},
}

@article{fang2024llmexploit,
  author    = {Richard Fang and Rohan Bindu and Akul Gupta
               and Daniel Kang},
  title     = {{LLM} Agents can Autonomously Exploit One-day
               Vulnerabilities},
  journal   = {arXiv preprint arXiv:2404.08144},
  year      = {2024},
  doi       = {10.48550/arXiv.2404.08144},
}

% ============================================================
% GROUP 5: New references from literature review
% ============================================================

@article{nasr2025attacker,
  author    = {Milad Nasr and Nicholas Carlini and
               Chawin Sitawarin and Sander V. Schulhoff and
               Jamie Hayes and Michael Ilie and Juliette Pluto
               and Shuang Song and Harsh Chaudhari and
               Ilia Shumailov and Abhradeep Thakurta and
               Kai Yuanqing Xiao and Andreas Terzis and
               Florian Tram\`{e}r},
  title     = {The Attacker Moves Second: Stronger Adaptive Attacks
               Bypass Defenses Against {LLM} Jailbreaks and Prompt
               Injections},
  journal   = {arXiv preprint arXiv:2510.09023},
  year      = {2025},
  doi       = {10.48550/arXiv.2510.09023},
}

@article{sen2024aiattacker,
  author    = {Omer Sen and Christoph Pohl and Immanuel Hacker
               and Markus Stroot and Andreas Ulbig},
  title     = {{AI}-based Attacker Models for Enhancing Multi-Stage
               Cyberattack Simulations in Smart Grids Using
               Co-Simulation Environments},
  journal   = {arXiv preprint arXiv:2412.03979},
  year      = {2024},
  doi       = {10.48550/arXiv.2412.03979},
}

@inproceedings{sarieddine2024ocpp,
  author    = {Khaled Sarieddine and Mohammad Ali Sayed and
               Sadegh Torabi and Ribal Attallah and
               Danial Jafarigiv and Chadi Assi and
               Mourad Debbabi},
  title     = {Uncovering Covert Attacks on {EV} Charging
               Infrastructure: How {OCPP} Backend Vulnerabilities
               Could Compromise Your System},
  booktitle = {Proceedings of the 19th ACM Asia Conference on
               Computer and Communications Security
               (ASIA CCS '24)},
  pages     = {977--989},
  publisher = {ACM},
  year      = {2024},
  doi       = {10.1145/3634737.3644999},
}

@article{zhang2025gridagent,
  author    = {Yan Zhang and Ahmad Mohammad Saber and
               Amr Youssef and Deepa Kundur},
  title     = {{Grid-Agent}: An {LLM}-Powered Multi-Agent System
               for Power Grid Control},
  journal   = {arXiv preprint arXiv:2508.05702},
  year      = {2025},
  doi       = {10.48550/arXiv.2508.05702},
}

@article{chen2025xgridagent,
  author    = {Xin Chen and Yihan Wen},
  title     = {{X-GridAgent}: An {LLM}-Powered Agentic {AI} System
               for Assisting Power Grid Analysis},
  journal   = {arXiv preprint arXiv:2512.20789},
  year      = {2025},
  doi       = {10.48550/arXiv.2512.20789},
}

@article{janjusevic2025mcp,
  author    = {Strahinja Janjusevic and Anna Baron Garcia
               and Sohrob Kazerounian},
  title     = {Hiding in the {AI} Traffic: Abusing {MCP} for
               {LLM}-Powered Agentic Red Teaming},
  journal   = {arXiv preprint arXiv:2511.15998},
  year      = {2025},
  doi       = {10.48550/arXiv.2511.15998},
}

@article{kuroptev2026evgrid,
  author    = {Kirill Kuroptev and Florian Steinke and
               Efthymios Karangelos},
  title     = {Defending the Power Grid by Segmenting the {EV}
               Charging Cyber Infrastructure},
  journal   = {arXiv preprint arXiv:2603.17640},
  year      = {2026},
  doi       = {10.48550/arXiv.2603.17640},
}

@article{kaur2025evcsur,
  author    = {Amanjot Kaur and Nima Valizadeh and
               Devki Nandan Jha and Tomasz Szydlo and
               James R. K. Rajasekaran and Vijay Kumar and
               Mutaz Barika and Jun Liang and Rajiv Ranjan
               and Omer Rana},
  title     = {Cybersecurity Challenges in the {EV} Charging
               Ecosystem},
  journal   = {ACM Computing Surveys},
  volume    = {58},
  number    = {1},
  pages     = {1--32},
  year      = {2025},
  doi       = {10.1145/3735662},
}

@article{xu2025forewarned,
  author    = {Minrui Xu and Jiani Fan and Xinyu Huang and
               Conghao Zhou and Jiawen Kang and Dusit Niyato
               and Shiwen Mao and Zhu Han and
               Xuemin Shen and Kwok-Yan Lam},
  title     = {Forewarned is Forearmed: A Survey on Large Language
               Model-based Agents in Autonomous Cyberattacks},
  journal   = {arXiv preprint arXiv:2505.12786},
  year      = {2025},
  doi       = {10.48550/arXiv.2505.12786},
}

@article{ibrahim2025llmgrid,
  author    = {Nourhan Ibrahim and Rasha Kashef},
  title     = {Exploring the Emerging Role of Large Language Models
               in Smart Grid Cybersecurity: A Survey of Attacks,
               Detection Mechanisms, and Mitigation Strategies},
  journal   = {Frontiers in Energy Research},
  volume    = {13},
  pages     = {1531655},
  year      = {2025},
  doi       = {10.3389/fenrg.2025.1531655},
}

% ============================================================
% GROUP 6: Adversarial evaluation methodology
% ============================================================

@article{carlini2019evaluating,
  author    = {Nicholas Carlini and Anish Athalye and
               Nicolas Papernot and Wieland Brendel and
               Jonas Rauber and Dimitris Tsipras and
               Ian Goodfellow and Aleksander Madry and
               Alexey Kurakin},
  title     = {On Evaluating Adversarial Robustness},
  journal   = {arXiv preprint arXiv:1902.06705},
  year      = {2019},
  doi       = {10.48550/arXiv.1902.06705},
}

@inproceedings{morris2013icsattacks,
  author    = {Thomas H. Morris and Wei Gao},
  title     = {Industrial Control System Cyber Attacks},
  booktitle = {1st International Symposium for ICS \& SCADA
               Cyber Security Research (ICS-CSR 2013)},
  pages     = {22--29},
  publisher = {BCS Learning and Development Ltd.},
  year      = {2013},
  doi       = {10.14236/ewic/ICSCSR2013.3},
}
```

---
---

# PART III: FIGURE AND TABLE SPECIFICATIONS

---

## Figure 1: LLM-GridEval Framework Architecture

### Purpose
Communicate the three-layer architecture and how the LLM attacker connects to the physics simulation through the sandboxed MCP interface. The reader should immediately grasp: LLM reasons at the top, constrained API in the middle, physics at the bottom.

### Layout and Topology
- **Orientation:** Landscape-filling, spanning full ACM single-column width (3.33 in / 84.5 mm). Height: ~2.5 in.
- **Structure:** Three horizontal bands stacked vertically, connected by labeled vertical arrows. An annotation column on the far right provides a one-word role label per layer.

### Detailed Elements

**Top band — Cognitive Layer (fill: #E8F0FE light blue, height ~22%):**
- Central rounded rectangle: **"LLM-based Attacker"** with subtitle "Policy π with RAG over K" in 7pt italic.
- To its left, inside a dashed outline labeled "Swappable Policies": three small boxes side-by-side reading "Random", "AI-V1", "AI-V2" in 6pt font. Dashed border communicates that these are interchangeable.
- Two vertical arrows exit downward from the central box: left arrow labeled **"Tool calls (JSON)"** in 6pt, right arrow entering from below labeled **"Observations / results"**.
- Right annotation column: **"Reasoning & Planning"** in 7pt bold, vertically centered alongside the band.

**Middle band — Interface and Tool Layer (fill: #FFF8E1 light yellow, height ~28%):**
- Central rounded rectangle: **"MCP HTTP Server (FastAPI)"**.
- Inside it, two tool boxes side-by-side:
  - Left tool box: `get_grid_status()` with subtitle "read feeder state" in 6pt.
  - Right tool box: `set_ev_capacity(ev_id, P)` with subtitle "write EV power" in 6pt.
- To the right of the tools, a separate box: **"Validation & Constraints"** listing "bounds · cooldown · ramping" in 6pt.
- Downward arrows from bottom of this band: **"HELICS API calls"**. Upward arrows entering from below: **"Measurements, setpoints"**.
- Right annotation: **"Typed, Constrained Interface"**.

**Bottom band — Co-simulation Layer (fill: #E8F5E9 light green, height ~35%):**
- Four rectangles arranged horizontally, equal width:
  1. **"GridPACK"** / "IEEE 9-bus" / "Transmission" / "(5 s)" — stacked text, 6–7pt.
  2. **"GridLAB-D"** / "Feeder A" / "123-node + EVs" / "(60 s)".
  3. **"GridLAB-D"** / "Feeder B" / "123-node" / "(120 s)".
  4. **"EV Controller v2"** / "(Defense M)" / "(10 s)".
- A horizontal bar spanning all four, beneath them: **"HELICS value exchange (voltages, powers)"** with small bidirectional arrows connecting each federate to the bar.
- Right annotation: **"Physics & Control"**.

### Visual Style
- Flat design. No 3D, no gradients, no drop shadows.
- Font: sans-serif (Helvetica or matching ACM template font). 7–8pt for box labels, 6pt for subtitles.
- Layer fills are very light pastels printable in grayscale (light → medium → dark).
- Arrows: solid black, 0.75pt, filled arrowheads.
- Box borders: 0.5pt dark gray (#555555), 3px corner radius.
- Band borders: none (distinguished by fill color only).

### Production
- Create in TikZ, Inkscape, or draw.io. Export to PDF.
- Exact width: 3.33 in (full ACM column). Height: ~2.5 in.

---

## Figure 2: Evaluation Validity Gap Across Operating Points

### Purpose
Visual centerpiece. Show at a glance that EVG is significant at Hr4 and Hr7 but collapses to 1.0× at Hr14.

### Chart Type
Grouped bar chart. 3 groups (operating points) × 3 bars (attacker variants).

### Axes
- **X-axis:** Three groups labeled "Hour 4\n(Low Load)", "Hour 7\n(Medium Load)", "Hour 14\n(High Load)". 8pt font.
- **Y-axis:** "TVD (seconds)", range 0 to 320 in increments of 50. 8pt font. Tick labels 7pt.

### Bars (left to right within each group)
- **Random:** medium gray (#9E9E9E), no hatch.
- **AI-V1 (Timing):** blue (#4285F4), diagonal line hatch (for grayscale fallback).
- **AI-V2 (Strategy):** red-orange (#EA4335), crosshatch (for grayscale fallback).
- Bar width: ~0.18 in. Gap between bars within group: 0.02 in. Gap between groups: 0.15 in.

### Data Points (bar heights)

| Group    | Random | AI-V1 | AI-V2 |
|----------|--------|-------|-------|
| Hour 4   | 60     | 48    | 135   |
| Hour 7   | 75     | 120   | 180   |
| Hour 14  | 295    | 295   | 295   |

### Error Bars
Black, cap-ended, ±1 standard deviation:
- Hr4: Random ±49, V1 ±27, V2 ±30.
- Hr7: Random ±30, V1 ±0, V2 ±0.
- Hr14: all ±0.

### Annotations
- **EVG labels** above each AI-V2 bar: "2.25×", "2.40×", "1.0×" in 7pt bold.
- **Significance brackets** between Random and AI-V2 bars:
  - Hr4: bracket with "*" (p < 0.05).
  - Hr7: bracket with "***" (p < 0.001).
  - Hr14: no bracket (n.s.).
- **Horizontal dashed line** at y = 295 labeled "Experiment ceiling" in 6pt italic, dark gray.

### Legend
Upper-left corner. Three colored squares with labels: "Random", "AI-V1 (Timing)", "AI-V2 (Strategy)". 7pt font.

### Visual Style
White background. Horizontal gridlines only, very light gray (#E0E0E0). No vertical gridlines. No box around plot area.

### Production
Create with matplotlib or R ggplot2. Export to PDF. Width: 3.33 in. Height: ~2.0 in.

---

## Figure 3: Attack Timeline Comparison at Hour 7

### Purpose
Make the abstract EVG concrete by showing action–reaction dynamics. The reader should see: Random has brief, scattered violations; V1 has repeated single-EV spikes; V2 has sustained staircase overloads.

### Layout
Three vertically stacked time-series panels sharing a common x-axis. Each panel is one attacker variant at Hour 7. Use a single representative seed per variant (Random seed 1, V1 seed 1, V2 seed 1).

### Dimensions
Full column width (3.33 in). Per-panel height: ~0.6 in. Total figure height: ~2.2 in (including shared x-axis label and panel labels).

### Shared X-axis (bottom panel only)
"Time (seconds)", range 0 to 300, major ticks at 0, 60, 120, 180, 240, 300. 7pt tick labels.

### Y-axis (each panel)
"Feeder Power (kW)", range 2500 to 6000. Major ticks at 3000, 4000, 5000. 6pt tick labels. Axis label on leftmost panel only; other panels share the scale visually.

### Elements Per Panel

**Common to all panels:**
- **Power trace:** Solid black line, 1pt, showing total feeder real power over 300 seconds.
- **Threshold line:** Horizontal dashed red line at 4200 kW, 0.75pt. Label "4200 kW" in 5pt red on right edge of the first panel only.
- **Violation shading:** Semi-transparent red fill (#EA433530) between the power trace and the threshold line wherever power ≥ 4200 kW.
- **Attack markers:** Small red upward-pointing triangles (▲) at the x-position of each attack, placed at the bottom of the panel. Each labeled with "EV*n*" in 5pt red text above the triangle.
- **Controller shed markers:** Small blue downward-pointing triangles (▼) at the x-position of each controller shed action, placed at the top of the panel.
- **Panel label:** Upper-left corner, 7pt bold. E.g., "(a) Random (TVD = 75 s)".

**Panel (a) — Random (seed 1):**
- Power trace shows irregular, brief spikes after random attacks at ~t=0, 110, 220.
- Violation shading: narrow red bands, few and short-lived.
- Attack labels: "EV1@755", "EV1@1393", "EV2@1091".
- Pattern: controller quickly sheds each attacked EV.

**Panel (b) — AI-V1 Timing (seed 1):**
- Power trace shows repeated spikes all from EV1 (same EV re-attacked at t≈30, 130, 290).
- Violations somewhat wider than Random but still single-cycle resolution.
- Attack labels: "EV1@1500", "EV1@1500", "EV1@1500".
- Pattern: each spike reaches the same height because it's the same EV being overwritten, not accumulated.

**Panel (c) — AI-V2 Strategy (seed 1):**
- Power trace shows a staircase pattern: each new EV adds ~1500 kW.
- Violation shading: wide, sustained red bands because the controller needs 4 sequential shed cycles (40 seconds) to remove 4 distinct attacked EVs.
- Attack labels: "EV1@1500", "EV2@1500", "EV3@1500", "EV4@1500".
- Pattern: staircase accumulation → sustained overload → slow progressive shedding → next attack re-establishes overload.

### Visual Style
- Minimal chrome. No plot borders. Light gray horizontal gridlines only.
- Power trace: 1pt solid black.
- Threshold: 0.75pt dashed red.
- Violation fill: semi-transparent red.
- Attack triangles: 4pt, red (#EA4335).
- Shed triangles: 4pt, blue (#4285F4).
- Panel separation: thin light gray horizontal rule (0.25pt).
- All text: sans-serif, 5–7pt.

### Production
Requires actual simulation time-series from `v2/results/campaign/hr7/` JSON files. Create with matplotlib (3 subplots, `sharex=True`). Export to PDF. Width: 3.33 in. Height: ~2.2 in.

---

## Appendix Figure A1: Controller v2 State Machine

### Purpose
Clearly show the three-state defensive logic for readers who want implementation detail.

### Type
State-transition diagram with 3 states and labeled directed edges.

### Elements
- **Three circles (states):**
  - OVERLOAD: red fill (#FFCDD2), labeled "OVERLOAD\nShed 1 EV/cycle\n(randomized order)".
  - CAUTION: yellow fill (#FFF9C4), labeled "CAUTION\nKeep EV1+EV2\nShed EV3–EV6".
  - RECOVERY: green fill (#C8E6C9), labeled "RECOVERY\nRestore 1 EV/30 s".
- **Arrangement:** Triangle layout. OVERLOAD top-center, CAUTION bottom-left, RECOVERY bottom-right.
- **Directed edges (curved arrows with labels):**
  - OVERLOAD → CAUTION: "P < 4200 kW"
  - CAUTION → OVERLOAD: "P ≥ 4200 kW"
  - CAUTION → RECOVERY: "P ≤ 2600 kW"
  - RECOVERY → CAUTION: "P > 2600 kW"
  - Self-loop on OVERLOAD: "P ≥ 4200 kW\n(shed next EV)"
  - Self-loop on RECOVERY: "P ≤ 2600 kW\n(restore next EV)"

### Style
Clean, minimal. Circle diameter ~0.8 in. 6pt text inside circles. Edge labels 5pt. Black arrows, 0.75pt.

### Production
TikZ or draw.io. Width: ~3 in. Height: ~2 in.

---

## Appendix Figure A2: Timing Gate Flowchart

### Purpose
Show the decision logic that filters observations before invoking the LLM.

### Type
Standard flowchart with diamond decisions and rectangular processes.

### Flow
```
[Start: New observation] → ◇ Cooldown elapsed? → No → [Wait]
                                    ↓ Yes
                           ◇ Micro score ≥ 70? → No → [Wait]
                                    ↓ Yes
                           ◇ Recommendation = ATTACK_NOW
                             or ATTACK_POSSIBLE? → No → [Wait]
                                    ↓ Yes
                           [Call LLM with prompt]
                                    ↓
                           [Parse JSON response]
                                    ↓
                           ◇ Valid action? → No → [Wait]
                                    ↓ Yes
                           [Execute via MCP server]
```

### Style
- Diamonds: light yellow fill. Rectangles: light blue fill. Terminal states: rounded rectangles, light gray.
- 6pt text. Black arrows 0.75pt.
- Left-to-right "No" branches; top-to-bottom "Yes" flow.

### Production
TikZ or draw.io. Width: ~3 in. Height: ~2.5 in.

---

# PART IV: REFERENCE MAP

Quick lookup for which `\cite{}` key to use at each point in the manuscript.

| Location | Cite Keys |
|----------|-----------|
| §1 ¶1 S3 (EV vulns) | `sarieddine2024ocpp` |
| §1 ¶1 S4 (DER + grid impact) | `kuroptev2026evgrid` |
| §1 ¶2 S1 (testbed surveys) | `cintuglu2017testbeds, smadi2021testbeds` |
| §1 ¶2 S1 (static datasets) | `goh2017swat, ahmed2017wadi, adepu2019epic, shin2020hai` |
| §1 ¶2 S1 (GridAttackSim) | `le2020gridattacksim` |
| §1 ¶2 S4 (adaptive eval parallel) | `carlini2019evaluating, nasr2025attacker` |
| §1 ¶3 S1 (HELICS) | `hardy2024helics` |
| §1 ¶3 S2 (ML-IDS survey) | `sahani2023mlids` |
| §1 ¶3 S3 (Sen et al. reliability) | `sen2024aiattacker` |
| §2.1 S1 (HELICS) | `hardy2024helics` |
| §2.1 S2 (datasets) | `goh2017swat, ahmed2017wadi, adepu2019epic, shin2020hai, sahani2023mlids` |
| §2.1 S3 (GridAttackSim) | `le2020gridattacksim` |
| §2.2 S1 (LLM tools) | `deng2024pentestgpt, xu2024autoattacker, xu2025forewarned` |
| §2.2 S2 (ICS + MCP) | `ahmed2025attackllm, fang2024llmexploit, janjusevic2025mcp` |
| §2.2 S3 (Grid LLMs) | `zhang2025gridagent, chen2025xgridagent` |
| §2.2 S4 (closest prior) | `sen2024aiattacker` |
| §2.3 S1 (LAA + FDIA) | `maleki2025laa, reda2022fdia` |
| §2.3 S2 (EV ecosystem) | `sarieddine2024ocpp, kaur2025evcsur, kuroptev2026evgrid` |
| §2.3 S3 (LLM + grid survey) | `ibrahim2025llmgrid` |
| §3.1 S1 (grid components) | `palmer2016gridpack, schneider2018testfeeders, chassin2014gridlabd, hardy2024helics` |
| §3.2 S1 (threat grounding) | `sarieddine2024ocpp` |
| §5.3 ¶1 S5 (parallel) | `nasr2025attacker` |
| §6.1 S2 (schema pattern) | `sen2024aiattacker` |

**Total unique references: 25**
