# M28 matched IA3/IA4 decision-to-action wiring report

## Outcome

M28 passed on its first and only create-once attempt. The exact deterministic
IA3 decision retained by M25 and the exact live-model IA4 decision retained by
M26 both selected candidate `cand_bc73d19dea133043082f`, whose fixed target
translation is `DER_B -> DER_EV4_BESS`. M28 delivered the resulting `+30 kW`,
`0 kvar` command through two actor-labelled, otherwise identical bounded
simulator pairs at the externally fixed `responsive_night` operating point.

All four network-isolated containers exited successfully, all teardowns were
verified, no retry occurred, and the primary and independent verifiers both
returned `issues: []`. The actor-blind physical JSON evidence was byte-identical
between IA3 and IA4 for both the benign and attack treatments. This qualifies
the point-specific decision-to-action plumbing. It does not demonstrate an LLM
advantage, adaptive strategy learning, operating-point generality, or a
confirmatory attack effect.

## Why M28 reuses the M26 live decision

M28 isolates a new engineering question: can a previously validated actor
decision be translated into the intended runtime command without changing its
target, magnitude, budget, timing, or provenance? Drawing another LLM sample
would mix model variability into that integration test. M28 therefore binds
the successful M26 live-model receipt rather than calling the model again.
The tested IA4 lineage still contains a real `qwen3.6-35b-a3b` request, one
real M24 read-only empirical-adapter call, and a validated terminal plan; M28
adds the previously absent simulator execution stage.

This choice is deliberately narrow. A later strategy-learning experiment must
make fresh interactive decisions, expose a richer strategy and tool library,
and compare the resulting behavior against non-LLM ladder arms. M28 supplies
the execution plumbing needed for that later experiment but cannot answer its
scientific question.

## Preregistered boundary

The create-once M28 contract was written before any M28 simulator access. It
binds the exact M18 authorization, M25/M26 decision evidence, M27 coverage
evidence, independent audits, runtime bytes, action requests, translation,
Docker image, operating point, seed, run cap, retry cap, and access seals.

| Registered item | Identity or SHA-256 |
|---|---|
| Contract ID | `m28contract_17d257b43c8954ebaea495bfd44ccba6b8b623f9fe256687ac4623b5f851e3e1` |
| Contract file | `39a1dd18c2f6b77c189c91846c412d3670c354da0b94dd2e0ed4c6faef45decf` |
| Runtime wrapper | `ffb55af12fb467e6bc47b01eacf4ed8eea500182f9a067324f4dc43f903cd69a` |
| Evidence builder | `ebe9e7db721278fdfec4db22fd32a0c744936779beb43f64a8abdf04ba06044b` |
| Runtime executor | `dc69e0deedb4a3cbaee0430d56b7d7f2f6b3d595023d66017e22447ba7d3ad18` |
| Independent auditor | `0df26273d9555ebcc8ec95505759ad8612f3c98ce5ec64bc8e16dadb79e5e5b4` |
| Docker image | `sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7` |

The registered execution geometry is:

- actor labels: `IA3` and `IA4`;
- treatments per actor: one benign control and one fixed attack;
- seed: attack-development seed `8109`;
- measurement-noise seed: `98109`;
- operating point: `responsive_night`;
- duration: three 10-second windows;
- action: one `DER_EV4_BESS +30 kW, 0 kvar` command;
- maximum apparent command energy: `2.0 kVAh`;
- actual admitted command energy: `0.08333333333333333 kVAh`;
- runtime cap: four containers; and
- retry cap: zero.

The execution runtime was actor-blind except for the provenance pair ID and
action-request identity. Both actor branches used the same executable target,
command, seeds, operating point, physical model, and container image.

## Decision and translation lineage

The IA3 input is M25 qualification
`m25qual_1d3ffc1e3d2adc6fd442286a9c9f48326cf49bea8f3dc67232ae34f628be1b6c`.
It selected the registered `DER_B` candidate through the deterministic M5/M24
transaction. The IA4 input is live M26 receipt
`m26receipt_248240e0650b47d804d01c2cf1627375bc7fe03654c2966796ad70266362b8ea`.
It selected the same candidate after the live model requested and consumed the
real M24 sensitivity payload.

The executor could not alter the selected candidate. The only registered
translation was:

```text
cand_bc73d19dea133043082f
  -> matched_step
  -> DER_B
  -> DER_EV4_BESS
  -> p = +30 kW, q = 0 kvar
```

Each actor-specific M18 request passed before runtime. No evaluation seed or
final-evaluation record was opened.

## Runtime result

The attempt completed all four runs with `container_exit_code = 0`, network
mode `none`, verified ephemeral-container teardown, and `retry_count = 0`.
Every benign trace was command-free. Every attack trace admitted the command
only in the first window, delivered exactly the admitted `DER_EV4_BESS`
setpoint, and remained within the registered window and energy budgets.

The treatment and control true-voltage observations were exactly equal at
runner times `t=10` and `t=20`. The first paired response appeared at `t=30`,
consistent with M21's causal timing result.

| Device | IA3 paired true-voltage delta at `t=30` (p.u.) | IA4 paired true-voltage delta at `t=30` (p.u.) |
|---|---:|---:|
| `DER_EV1_BESS` | `0.00023144279464770712` | `0.00023144279464770712` |
| `DER_EV3_PV` | `-0.00230650045722558` | `-0.00230650045722558` |
| `DER_EV4_BESS` | `0.0033131447622005705` | `0.0033131447622005705` |
| `DER_EV5_PV` | `0.0009785678141296383` | `0.0009785678141296383` |

The maximum absolute paired response was
`0.0033131447622005705 p.u.`. IA3 and IA4 paired-delta maps were exactly equal.
The complete actor-blind physical JSON payloads—attack trace, reconciled dual
budget trace, summary, source trace, and device traces—were byte-identical for
both the benign and attack treatments.

## Evidence hygiene and warnings

The runtime produced 39 broken container-only `/work/examples/...`
compatibility links per run. The executor recorded all 156 link paths and
targets and removed only those verified broken links before manifest creation.
No symlink remains in the M28 artifact directory. The 130 regular manifest
files remained intact and total 981,834 bytes.

The four generated feeder GLM files retain whitespace from the upstream source,
so `git diff --cached --check` reports those raw-evidence lines. They were not
normalized because the evidence manifest binds their exact simulator-produced
bytes.

Each run emitted the same two-line HELICS Python API deprecation warning that
recommends `helicsFederateDisconnect`; no M27-style unknown-route warning
occurred. The warning is retained in each `console.stderr.txt` file and does
not differ by actor or treatment.

## Verification

| Evidence | Identity or SHA-256 |
|---|---|
| Evidence ID | `m28evidence_0b4d764af97fbb6de33f4981869a6e0883bccb6c8ffbe8fa6f54392ab8c35ed7` |
| Evidence file | `8ee5b6f8138be849a3dff40ad7707177caaa4983dd0f03bfa49f568d60a8d1a1` |
| Runtime execution | `6b7fc124f4d09397f0954aed1da28980500031f14c182cf1f2d6d413fc34a585` |
| Independent audit ID | `m28audit_e386aa20c55aea91d936bf6f5ae7ad691ef23f369592ff788e994b5e1b119c64` |
| Independent audit file | `c569eb430797251c967cc04032ffa082e5e47e92a9262b7d4789238db672c92e` |

Primary verification and the independent, non-importing exact-byte audit both
return `issues: []`. The focused M28 suite passes 9 tests. The complete
`g7_confirmatory` suite passes 439 tests and 93 subtests.

## Scientific interpretation

M28 closes the concrete gap between a validated IA decision and the bounded
co-simulation runtime. Candidate identity, target aliasing, command magnitude,
budget admission, delivery, timing, causal observation, and evidence
provenance are now connected and independently auditable. An IA4 decision that
was actually produced by the live model can reach the simulator without giving
the model direct runtime or actuator authority.

The exact IA3/IA4 equality is expected because both branches intentionally
execute the same candidate under identical common-random-number conditions. It
is evidence that the executor is actor-blind, not evidence that the actors have
equal or unequal attack capability. M28 makes no comparison of search quality,
interactive adaptation, long-horizon stealth, detector evasion, or system-wide
impact.

Formal CAREER sensitivity-resource admission remains on hold. The M23 scalar
was consumed only under the externally bound `responsive_night` condition.
M27 already showed that sensitivity changes across operating points, so a
broader study must use an operating-point-indexed resource rather than treating
the night scalar as invariant.

## Recommended next gate

M29 should use the qualified M28 execution boundary to test fresh decision
behavior rather than more plumbing. A defensible next design is an offline or
bounded-simulator strategy-acquisition gate with the following ladder:

1. fixed script with no strategy library;
2. deterministic strategy-library search;
3. deterministic search plus the point-indexed read-only tool;
4. LLM using the same strategy library and tool contract; and
5. LLM using the same resources plus bounded delayed feedback.

The initial M29 endpoint should be strategy and tool compliance under mirrored
counterfactual tasks, not raw harm. Only after the LLM demonstrates valid
strategy selection or adaptation beyond the deterministic arms should a later
gate spend additional simulator budget on subtle multi-window or bias-injection
attacks. Final evaluation, detector/defense claims, and physical actuation must
remain sealed.
