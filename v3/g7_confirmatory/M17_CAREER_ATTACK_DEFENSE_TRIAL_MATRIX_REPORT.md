# M17 CAREER Attack-Defense Trial Matrix Report

## Result

M17 freezes a non-executable attack-defense trial matrix for the GridEval
preliminary program. It defines the IA0-IA5 capability ladder, subtle and
long-horizon strategy families, black/gray/white-box knowledge contracts,
detector and mitigation pairings, estimable contrasts, promotion rules, and
power-system-specific validity checks.

The canonical artifact is `artifacts/career_trial_matrix_m17.json`, governed
by `career_trial_matrix.schema.json` and validated by
`g7confirm.career_trial_matrix`.

M17 does not assign a source, seed, partition, resource, threshold, detector
parameter, or executable run. Preliminary execution requires the separate M18
gate. Final evaluation and the confirmatory campaign remain sealed.

## Governing provenance

The matrix binds the following RKA records:

- M17 design decision: `dec_01M1MAPMSFXE38S9QD8KSYG4XW`;
- preliminary-first PI directive: `jrn_01M1MC21TXF1A682E6ZHQN7C70`;
- preliminary-first Confirmation Brief: `jrn_01M1MC2K7D22HNX6CQ6PGB3B6A`;
- PI confirmation: `jrn_01M1MDAS6MN35JQ2NWFEMPEZXW`;
- preliminary-first decision: `dec_01M1MDB6Q97DXACWMN2EVE7Q9Q`; and
- resolved external-review-first checkpoint:
  `chk_01M1M97DN5EWDKSM4T1CMT76J6`.

The previous M14 review packet and receipt machinery remain historical,
content-addressed provenance. Their preservation is not evidence that review
occurred, and the preliminary-first decision does not convert any internal or
model review into external scientific approval.

## Two non-pooled research tracks

The contract separates two questions that must not be analyzed as one
treatment:

1. `CAREER_CORE_ASM` is the primary capability-conditioned causal design. It
   controls one EV aggregator active-power setpoint over two intervals and
   changes only whether the second interval may be revised after one scheduled
   midpoint observation. Its matched factors remain `A`, `S`, and `M`.
2. `RED_TEAM_IA_EXTENSION` is a secondary robustness benchmark. It permits a
   bounded multi-window IA ladder over the AS-A legitimate DER command surface
   and studies stronger strategy, knowledge, tool, detector, and defense
   interactions.

This separation prevents a result caused by additional observations, targets,
P/Q dimensions, or revisions from being attributed to the minimal CAREER
midpoint-revision effect.

## IA0-IA5 capability ladder

The ladder is monotone in declared orchestration capability, not expected
physical harm. Negative and dominated results must be retained.

| Rung | Adds only | Matched comparison |
|---|---|---|
| IA0 | Frozen schedule | Static lower bound |
| IA1 | One pre-episode strategy-library selection | IA1 minus IA0 |
| IA2 | Deterministic feedback-conditioned switching | IA2 minus IA1 |
| IA3 | Non-LLM adaptive credit assignment | IA3 minus IA2 |
| IA4 | LLM strategy and typed-tool orchestration | IA4 minus matched IA3 |
| IA5 | One bounded critique and plan revision | IA5 minus compute-matched IA4 |

IA3 and IA4 share candidate bytes, strategy grammar, typed tools, tool outputs,
feedback delay, history representation, validation, action authority, outer
rollout cap, simulator-time accounting, and failure policy. IA5 and its IA4
control additionally share total model-call and token caps. The LLM always
emits a typed proposal that passes the common external validator; it has no
unchecked actuator path.

## Subtle and long-horizon strategy families

The matrix preserves ten grid-mechanism families:

- immediate feasible P/Q corner;
- pulse-rest and intermittent schedules;
- low-slew drift;
- periodic duty-cycle shaping;
- event-synchronized action;
- riding benign voltage movement;
- coordinated P/Q action under inverter kVA limits;
- phase- and location-aware spatial subsets;
- SOC, irradiance, ramp, saturation, and local-mode state exhaustion; and
- detector-aware adaptive evasion.

Every family names a mechanism-specific matched control and diagnostic
signature. No numeric amplitude, duration, threshold, or seed is selected in
M17. “Stealth” therefore remains an empirical joint property of physical
consequence and alarm exposure, not a label inferred from small magnitude.

## Knowledge and box-level contract

Box level is encoded by
`K=(grid, detector, training_data, defense, feedback)`, with each component
set to `none`, `partial`, or `exact`.

- `K0` is black-box with no outcome feedback.
- `K1` is black-box with delayed binary feedback.
- `K2` is gray-box with partial system, detector, data, defense, and feedback
  information.
- `K3` is white-box with exact frozen information.

Knowledge never encodes physical authority, target count, query budget,
compute, or feedback timing. White-box information is released only after the
relevant preliminary detector/defense package is frozen. Exact evaluation
partition contents are never part of K.

## Detector and defense coverage

The passive detector plane contains:

- command-envelope policy checks;
- physics-residual or voltage-sensitivity consistency;
- sequential change detection;
- cross-layer intent/delivery/acceptance/realized-PQ consistency;
- hybrid central/local reconstruction evidence;
- temporal state prediction;
- graph-based localization; and
- transparent score/alarm fusion.

Each detector records both its intended coverage and a known blind spot. The
mitigation plane separately contains alarm-only observation, safe command
screening, local autonomous fallback, physics-aware watermarking, and
event-triggered moving-target defense. Every active defense must report its
operational cost and new failure modes; detection quality is evaluated first
under alarm-only observation so mitigation cannot hide detector weakness.

## Power-system validity invariants

Every later preliminary trial must:

- index results by operating point, phase, location, and DER type;
- preserve BESS SOC and PV irradiance as temporal state;
- model inverter kVA saturation, priority, ramping, and mode transitions;
- preserve local Volt-VAR arbitration and any remote-Q override behavior;
- log requested, admitted, accepted, and realized P/Q separately;
- retain network delivery, loss, delay, reordering, and duplication lineage;
- compare against the paired benign trajectory;
- separate physical consequence, continuous detector evidence, alarm,
  mitigation, and operational cost; and
- estimate alarm exposure per trajectory or independent block rather than per
  shuffled row.

## Sequential trial plan

The matrix avoids an infeasible full Cartesian product:

1. `T0` qualifies contracts and information boundaries with synthetic,
   non-executable fixtures.
2. `T1` performs a later M18-gated preliminary mechanism screen, beginning
   with black-box K0/K1 and transparent D0-D3 evidence. Negative results are
   retained; only distinct mechanisms or harm/alarm/cost frontier points
   advance.
3. `T2` performs later adaptive stress testing only after a preliminary
   detector package is frozen. It adds selected gray/white-box profiles,
   learned detectors, fusion, and mitigation sequentially.
4. `T3` is the final confirmatory stage. It contains no assigned rungs,
   profiles, defenses, sources, or seeds and remains sealed until
   post-preliminary external consultation and a later final-freeze decision.

## Read-only preflight

From `v3/g7_confirmatory`:

```bash
python3 -m g7confirm.cli career-trial-matrix-preflight \
  --repo-root /home/cfu6/roi-uncc-mcp
```

The command verifies the upstream M16 advisory, all six M17 input assets by
exact bytes, the content-addressed artifact, capability/knowledge parity, and
the non-executable governance boundary. It creates no file, performs no RKA
write, contacts no model or embedding service, and exposes no unseal command.

## Validation scope

`tests/test_career_trial_matrix.py` passed 16 tests. The complete
`v3/g7_confirmatory` suite passed 331 tests, and the read-only preflight
returned zero issues. These checks establish contract integrity and comparison
structure only. They do not demonstrate physical harm, detector performance,
LLM superiority, mitigation effectiveness, external validity, or readiness for
final evaluation.

## Next gate

M18 must encode the preliminary-only governance boundary before any source,
partition, threshold, detector, simulator, actuator, or runtime action. It may
authorize only bounded preliminary work with explicit purpose labels and must
keep a disjoint final evaluation partition untouched. It cannot authorize
confirmatory claims or a final campaign.
