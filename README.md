# LLM-GridEval: AI-Assisted Red-Teaming for Grid Co-Simulation

Measuring the **Evaluation Validity Gap (EVG)** in smart-grid security with
adaptive, tool-using LLM attackers embedded in a HELICS transmission–distribution
co-simulation. UNC Charlotte · supported by the UNC System Research Opportunities
Initiative (ROI).

> **Contained research sandbox — simulated IEEE test systems only. No real grid
> is ever contacted.** Dual-use red-team code is for defensive security research.

## Published work

**LLM-GridEval: Measuring the Evaluation Validity Gap in Smart Grid Security with
Adaptive LLM Attackers.** Fu, Besati, Wang. *ACM Sustainability Week Companion
2026* (Banff). Compiled paper: [`main.pdf`](main.pdf); LaTeX source under
[`paper_writing/v2/`](paper_writing/v2/).

Headline result: a strategy-aware LLM attacker reaches **2.25–2.40× the threshold
violation duration** of a random baseline where the defender can respond
(*p* < 0.05, *d* = 1.85–4.95), collapsing to 1.0× at a saturated operating point —
i.e. static/random benchmarks can understate adaptive risk by ~2.4×. The gap is
driven by target **diversification**, not micro-timing.

## Two generations in this repo

| Area | Purpose |
|---|---|
| [`llm_grid_eval/`](llm_grid_eval/) | The framework: schema-constrained MCP attacker server + primitive interface (the paper's "LLM-GridEval"). |
| [`v2/`](v2/) | Verified **direct-path reference** federation and the workshop-paper campaign (GridPACK IEEE-9 + 2×GridLAB-D IEEE-123, progressive-shedding controller, Random/AI-V1/AI-V2 attacker policies). |
| [`v3/`](v3/) | **Current expansion** — rebasing onto an explicit **NATIG** ns-3/DNP3 cyber network and **OpenDER** (IEEE-1547) DER behavior. See [`v3/README.md`](v3/README.md). |
| [`examples/`](examples/) | Git submodule: shared IEEE-123 feeder / GridLAB-D + GridPACK models used by v2 and v3. |
| [`paper_writing/v2/`](paper_writing/v2/), [`results.md`](results.md) | Published manuscript and consolidated results. |
| [`archive/`](archive/) | Superseded v1-era material (EV-setpoint MCP demo, v1 paper draft, old docs). |

## v3: rebasing on NATIG + OpenDER

The expansion makes an explicit **DNP3-over-ns-3 network the mandatory substrate**:
every controller/attacker command and every telemetry reading becomes a HELICS
*message* (delayable / droppable / modifiable) through a NATIG-derived network
federate, with SELECT-before-OPERATE DNP3 semantics; only physical V/f/P/Q stay
as HELICS *values*. An ideal-setpoint EV is replaced by a pinned OpenDER BESS with
IEEE-1547 limits, ramping, ride-through/trip, and SOC. The v2 direct path is
retained as a labeled reference arm.

**Gate discipline (`v3/README.md`), current status:**

| | Gate | Status |
|---|---|---|
| G0 | Freeze/repair v2 baseline | ✅ (carried: 10 s actuation / 20 s feedback) |
| G1 | NATIG reproducible build | ◑ bounded component proof (locked-source rebuild owed) |
| G2 | OpenDER component proof | ✅ (2.2.0, 565/565 upstream tests) |
| G3 | One-device physical loop | ✅ (BESS at l92, 10 s coupling) |
| G4 | Benign network equivalence | ✅ single BESS (direct vs NATIG paired) |
| G5–G8 | Impairment → attack → coordination → confirmatory | ⏳ not started |

**No impairment or attack campaign has been run.** Benign equivalence must hold
before any attack inference.

## Reproducing v3

Upstream sources and build images are **not vendored** (they are ~13 GB and
regenerable). Pinned commits and a fetch script live in
[`v3/deps/`](v3/deps/README.md):

```bash
bash v3/deps/fetch_deps.sh          # clone NATIG@e163b35, OpenDER@fe7877c
# locked NATIG build recipe: v3/natig/locked_build/ (Dockerfile + patches)
```

## Layout notes

- `git`-tracked = source, configs, small gate-evidence manifests, and the paper.
- Build-image trees, timestamped run outputs, upstream clones, virtualenvs, and
  LaTeX intermediates are gitignored (see `.gitignore`); regenerate them locally.
