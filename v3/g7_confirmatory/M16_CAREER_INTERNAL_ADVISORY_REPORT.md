# M16 CAREER Internal Advisory Report

## Result

M16 completed one bounded internal design advisory with the already-running
local `qwen3.6-35b-a3b` service. The accepted response is preserved with its
input manifest, request digest, model identity, usage, two failed-closed
transport attempts, and one successful compact-schema attempt. Brain
adjudication accepts two findings for offline design, accepts four with
corrections, and rejects one because it conflicts with the M15 gate.

This is not external review, independent review, scientific approval, or a
receipt. It changes no sealed action.

The canonical evidence is `artifacts/career_internal_advisory_m16.json`,
governed by `career_internal_advisory.schema.json` and validated by
`g7confirm.career_internal_advisory`.

## Input and service boundary

The request supplied thirteen design or non-evaluation files totaling 128,077
bytes. Each path, byte count, and SHA-256 digest is bound in the artifact. The
inputs cover M8-M15 design reports, the red-team design, research and
orchestration protocols, detector-defense review, and the frozen experiment
specification.

The transport record discloses:

- endpoint: `http://ccil1s26m8hj6lws:8000/v1`;
- model: `qwen3.6-35b-a3b`;
- model root: `QuantTrio/Qwen3.6-35B-A3B-AWQ`;
- deterministic request seed: `1616`;
- accepted request SHA-256:
  `d0ef5406f3d812abd79b07ed5e1790c324486ad2bf41b7a0b8ef2a563f47a6d3`;
- accepted usage: 30,997 prompt, 2,011 completion, and 33,008 total tokens;
  and
- accepted review SHA-256:
  `de226e18ad97fa2de78ca80ab6ecd418e7f48c215db1aadd7a79b06f4ced2e8a`.

No model or embedding service was started or restarted. The embedding service
was not needed because the complete bounded input set fit directly in the
model context. No simulator, detector, actuator, or evaluation record was
accessed.

## Fail-closed attempts

The first full-schema response contained an invalid unescaped control
character. Strict JSON parsing rejected it. The second full-schema response
remained structurally invalid because a JSON delimiter was missing. A third
and final attempt used a smaller strict schema and produced one valid response.

The two invalid responses contribute only transport-status evidence. Their
content was not interpreted, repaired, or promoted into the project record.
The accepted response was parsed, reserialized, digest-bound, and then
independently adjudicated.

## Useful advisory findings

The review reinforced several design choices:

- M9 isolates midpoint revision permission but remains a synthetic protocol
  witness, not physical or stealth evidence.
- The single-EV-aggregator `S` boundary and exact-M9-library `M` boundary are
  necessary to avoid authority and treatment leakage.
- Power-system attack design should include operating-point-dependent P/Q
  coupling, local Volt-VAR overrides, inverter saturation and mode changes,
  device asymmetry, and temporal state such as state of charge.
- The strongest subtle strategy extensions are riding-the-wave control and
  coordinated P/Q action, because both exploit the command-to-physics map
  rather than merely maximizing instantaneous deviation.
- Cross-layer command-response consistency is important because a purely
  physical residual can miss malicious intent that remains physically
  plausible.
- IA3/IA4 candidate, information, history, budget, and validation parity is a
  prerequisite for interpreting an LLM capability effect.

These points may guide offline contracts. They do not establish empirical
performance.

## Brain adjudication

The model output was advisory, so every finding received an explicit project
disposition:

| Finding | Disposition | Project interpretation |
|---|---|---|
| F10 | Accept with correction | Preserve the source-contamination diagnosis, but recognize that M12-M15 are already complete and permit design-only checks. |
| F20 | Accept with correction | Preserve the synthetic-versus-physical limitation; reject the stale proposal to proceed through already-completed M10-M14 milestones. |
| F30 | Accept for offline design | Specify riding-the-wave and coordinated-P/Q strategies as non-executable contracts; defer execution. |
| F40 | Accept with correction | Preserve the partition-leakage question in the dormant packet; do not describe M14 as still needing preparation. |
| F50 | Reject: governance conflict | The suggestion to set detector thresholds in M16 violates the M15 threshold-fitting and calibration seals. |
| F60 | Accept with correction | Preserve the two-tier interpretation; reject the claim that all model access is prohibited because M15 permits bounded local advisory use. |
| F70 | Accept for offline design | Preserve IA3/IA4 parity as a causal-ablation requirement; defer runtime comparisons. |

The F50 rejection is important: a model recommendation never overrides the
machine gate. F60 also demonstrates that model output is not treated as an
authoritative reading of the current project state.

## Power-system-specific implications

M17 should represent each strategy as an interaction among four distinct
surfaces:

1. physical authority: active/reactive setpoints, inverter headroom, local
   modes, device constraints, and temporal state;
2. grid context: phase, location, operating point, sensitivity sign and
   magnitude, and load/PV trajectory;
3. attacker adaptation: static schedule, fixed feedback rule, deterministic
   bandit learning, LLM selection, or bounded LLM tool interaction; and
4. defender exposure: measurements, command logs, detector scores, thresholds,
   topology, and delayed/binary feedback.

Separating these surfaces prevents an apparent intelligence gain from being
caused by extra authority, information, or budget.

## M17 offline design target

The next safe milestone is an offline attack-defense trial matrix. It should:

- define the IA0-IA5 ladder with a matched comparator and one incremental
  capability per transition;
- define subtle long-horizon strategy families without selecting empirical
  amplitudes or thresholds;
- distinguish persistent bias, slow drift, duty-cycle shaping,
  operating-point riding, coordinated P/Q action, recovery-aware behavior,
  and detector-feedback adaptation;
- cross each strategy with black-, gray-, and white-box knowledge contracts;
- map each trial to physics-only, cross-layer, temporal/change-point, and
  sequential/learned detector families;
- state power-system invariants and invalidation checks before any runtime
  implementation; and
- produce only non-executable plans, schemas, and synthetic fixtures.

M17 must not generate a real source, assign partitions, admit a resource,
choose or fit a threshold, calibrate a detector, run a simulator or actuator,
open evaluation records, or execute a campaign.

## Read-only verification

From `v3/g7_confirmatory`:

```bash
python3 -m g7confirm.cli career-advisory-preflight \
  --repo-root /home/cfu6/roi-uncc-mcp
```

The command verifies M15 first, checks all thirteen M16 inputs by exact bytes,
validates the accepted model output and Brain adjudication, and reports every
sealed action. It creates no file and performs no RKA write.

The targeted M14B/M15/M16 run passed 46 tests, the complete
`v3/g7_confirmatory` suite passed 315 tests, and the read-only M16 preflight
returned zero issues. Passing these checks demonstrates evidence preservation
and governance enforcement only. It does not validate any model recommendation
empirically or satisfy the deferred external-review gate.
