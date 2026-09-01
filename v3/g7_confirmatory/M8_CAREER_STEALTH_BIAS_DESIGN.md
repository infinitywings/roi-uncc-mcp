# M8 CAREER-aligned subtle setpoint-bias design

Status: offline design contract complete; no model, tool, simulator, detector,
calibration, embedding, evaluation, or campaign access.

Contract ID:
`careerstealth_3091a0e686e43b483906a37733f26dfb4cef9fd90d2ae56226e47003b3cdd394`

## Outcome

The requested subtle and long-duration attack design is now aligned with the
governing CAREER project description. The primary experiment is not a broad
contest among unrestricted autonomous attackers. It is a matched estimate of
one capability effect:

> Does permission to revise the remaining action once, after one scheduled
> midpoint response, change independently confirmed physical consequence under
> the same alarm-exposure criterion and budget?

The primary threat model controls one EV charging aggregator setpoint, observes
only the exposed bus-voltage telemetry, and cannot alter sensors, protection,
interlocks, the detector, or another device. Within this surface, a subtle bias
is a bounded deviation from the benign charging setpoint. It is not false
measurement injection.

The governing source was read in full from the local, intentionally ignored
`archive/CAREER_Project_Description_Draft.pdf`. Its SHA-256 is
`a87158fdf6ad7ffb4c783ecd9b2a8b7d47886f234464a07571a5a41c659f5d8c`.
The document has 20 pages and is titled *CAREER: Capability-Conditioned
Evaluation of Cyber-Physical Defenses Against Adaptive, Process-Grounded
Adversaries*.

## What “long-duration” means in the core experiment

Long duration changes the waveform horizon, not the number of decisions. Every
core policy still has exactly two action intervals:

- preplanned: `(a1, a2_initial)`;
- response-informed: `(a1, rho2(y_mid; a2_initial))`.

The first action is immutable in both conditions. The response-informed
condition may retain or replace only the second interval after receiving the
scheduled midpoint voltage observation. It receives no extra detector score,
tool, action authority, search history, or episode budget.

This distinction is essential. Granting many revisions to the treatment would
simultaneously change adaptation depth, observation count, compute, and query
budget. That would test a package rather than the CAREER `A` factor.

M8 records four candidate horizon cells at the current 10-second design window:

| Cell | Windows | Duration | Role |
|---|---:|---:|---|
| Legacy bridge | 84 | 14 minutes | Connect to earlier G7 evidence |
| Long-duration screen | 360 | 1 hour | First low-and-slow screen |
| Stateful extension | 2,160 | 6 hours | Test delayed state and recovery |
| Diel extension | 8,640 | 24 hours | Test load/solar-cycle alignment |

None is selected as the primary executable horizon. The selection requires a
runtime-throughput, reset, timing, and engineering-margin gate. The current
contract does not authorize any of these runs.

## Core subtle-bias library

Every strategy controls the same aggregator charging setpoint and is
parameterized along the same four CAREER axes: magnitude, onset or phase,
duration, and temporal shape.

| ID | Shape | Mechanism | Required matched controls |
|---|---|---|---|
| `B1_constant_micro_bias` | Small constant offset | Tests whether sustained low amplitude is consequential | zero bias, sign reversal, time shift |
| `B2_linear_drift` | Monotone slow drift | Accumulates displacement while limiting instantaneous innovation | equal-energy constant, slope reversal |
| `B3_staircase_drift` | Small plateaus | Separates cumulative bias from continuous slope | equal-energy linear drift, shuffled step order |
| `B4_pulse_rest` | Sparse pulse and recovery | Tests plant and detector memory under equal energy | contiguous equal-energy bias, phase shift |
| `B5_mean_zero_oscillation` | Mean-zero waveform | Tests persistence or resonance without net bias | phase shuffle, frequency-matched benign control |
| `B6_trend_aligned_bias` | Bias aligned with benign trend | Tests whether the midpoint response changes the best second action | trend-opposed and midpoint-response-shuffled controls |

“Stealth” is not assigned from small amplitude alone. A strategy is described as
low amplitude or low slew until independent confirmation establishes both its
physical consequence and its alarm exposure. An attack that is small but
ineffective is not a successful stealth attack; an attack that avoids an alarm
but causes no physical consequence is also not one.

## Long-horizon budget contract

Matching only action count would let one method win by being louder. Matching
only cumulative energy would let another concentrate the same energy into an
instantaneous step. Each comparison must therefore freeze and enforce all of
the following prospectively:

- maximum absolute setpoint bias;
- maximum setpoint slew;
- cumulative absolute bias;
- cumulative squared bias;
- setpoint-energy deviation;
- active duration;
- search episodes;
- compute time; and
- reset count.

The values must come from the frozen engineering interface and pilot error
bounds before treatment outcomes are observed. M8 intentionally contains no
executable amplitude or alarm threshold. Prospective budget violations must be
rejected atomically and retained in failure accounting.

## Primary causal factors

The CAREER factorial is `A × S × M`:

- `A` is revision permission: preplanned two-interval control versus exactly
  one midpoint revision.
- `S` is access to additional validated process relationships. It is admitted
  only after independent action-validity validation; both conditions retain
  the common interface, limits, permissions, and safety shield.
- `M` is access to a read-only validated predictive ranking of the same
  candidate actions. It is admitted only after held-out ranking validation;
  the control uses the frozen model-free ranking.

The common algorithm scaffold, raw observations, candidate library, permitted
actions, starting state, search history, schedule, safety shield, and every
budget remain fixed across `A`. The full factorial is reduced prospectively if
`S` or `M` fails its independent admission gate.

## Role of the LLM

The earlier roadmap made `IA4 − IA3` the primary orchestration contrast. The
CAREER description establishes a different hierarchy:

1. `A`, `S`, and `M` are the primary causal capability variables.
2. Complete search algorithms are a separate secondary benchmark.
3. Algorithm complexity is retained only when independently confirmed decision
   benefit clears a prespecified practical margin.

Accordingly, an LLM tool orchestrator remains useful, but only as an optional
secondary challenger after the mandatory methods: space-filling Sobol search,
direct-surrogate optimization, constrained Bayesian optimization, and CPS
falsification. It must use the same device, action family, observation
interface, safety filter, candidate data, episode limit, and confirmation rule.
Its result cannot replace or select the scaffold used to estimate `A`, `S`, or
`M`.

The existing IA0–IA5 ladder remains valuable for later defense-aware and
multi-revision extensions. It is not the committed CAREER core.

## Evidence and detector semantics

Development episodes may select a policy. The selected policy must then be
executed on fresh confirmation episodes. Best-development-run performance is
never claim-supporting evidence.

Five outcome channels remain separate:

- physical consequence;
- continuous defense evidence;
- final alarm decision;
- resource cost; and
- uncertainty plus alarm-admissibility status.

The primary physical endpoint is maximum voltage-envelope excess over monitored
buses and time, scaled by a frozen per-bus engineering tolerance and zero inside
the valid envelope. Raw per-unit voltage deviation, ampacity, protection,
recovery, alarm timing, invalid actions, refusals, timeouts, and aborts are
co-reported rather than silently discarded.

The primary alarm criterion uses 30 independent blocks and four confirmation
episodes per block. A block is exposed if any of its four episodes alarms. The
condition is admissible only when the exact one-sided 95% upper confidence bound
on block exposure is at most 0.10; with 30 blocks, the committed rule requires
zero exposed blocks. An alarm means defender awareness. It is not a physical
endpoint and does not stop the run unless mitigation is part of the deployed
defense.

The detector implementation priority from the governing draft is NSIBF, then
GDN, then TranAD, selected by outcome-blind calibration stability, execution,
reset, logging, runtime, and interface checks. This M8 artifact neither selects
nor calibrates a detector.

## Black-, gray-, and white-box extensions

The primary core provides neither detector modification nor detector-score
feedback. Broader knowledge profiles may be studied later, but only in separate
extension contracts:

| Extension | Why it is not mixed into the core |
|---|---|
| Telemetry bias injection | Changes the authority surface from command choice to measurement integrity |
| Multi-device coordination | Changes device count, spatial authority, and action dimension |
| Repeated within-run revision | Changes observation count, adaptation depth, compute, and timing |
| Configuration manipulation | Changes the controlled variable and persistence mechanism |
| Command plus concealment | Simultaneously changes command and telemetry authority |
| Initial access and attack staging | Changes the research question from process-command choice to intrusion execution |
| IA0–IA5 orchestration ladder | Tests a richer capability package than the minimal one-revision effect |

These extensions can support red-team robustness claims, but they cannot be
pooled with the primary `A` contrast or cited as evidence for it.

## Why the design is scientifically defensible

The design follows the established principle that evaluation against a weak or
mis-specified attack can overstate robustness, while also avoiding the opposite
mistake of changing several attacker capabilities at once. Relevant foundations
include resource-limited adversary models
([Teixeira et al., 2015](https://doi.org/10.1016/j.automatica.2014.10.067)),
detectability–performance tradeoffs
([Bai et al., 2017](https://doi.org/10.1016/j.automatica.2017.04.047)),
impact bounds for stealthy ICS attacks
([Urbina et al., 2016](https://doi.org/10.1145/2976749.2978388)), and the danger
of evaluating against weak attacks
([Uesato et al., 2018](https://proceedings.mlr.press/v80/uesato18a.html)).
Physics-aware watermarking is retained as a later active-defense extension
because it changes the plant input and has an operational cost
([Liu et al., 2024](https://doi.org/10.1109/TIFS.2024.3447235)).

## Machine artifacts and next gate

- `artifacts/career_stealth_contract_m8.json` is the canonical contract.
- `career_stealth_contract.schema.json` is its interchange schema.
- `g7confirm/career_stealth_contract.py` rebuilds and validates the content
  address and CAREER invariants.

The next gate is `M9_offline_two_interval_fixture`. It should use mirrored
synthetic midpoint responses to prove that only `A=1` may change the second
interval, while both conditions share exact candidate, observation, history,
and budget bytes. It must remain offline: no model call, real tool, simulator,
detector, embedding service, or evaluation data.

Passing M9 would establish protocol isolation only. It would not establish
physical harm, stealth, detector evasion, LLM superiority, runtime readiness,
or campaign authorization.
