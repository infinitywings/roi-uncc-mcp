# GridEval v3 Self-Audit

## Evidence-to-design audit

| Design choice | Evidence | Confidence | Remaining test |
|---|---|---|---|
| NATIG for explicit cyber mediation | NATIG combines HELICS, GridLAB-D, ns-3, and DNP3 and includes IEEE 123 examples | High for capability | Public, pinned rebuild in G1 |
| OpenDER for device behavior | EPRI model exposes PV/BESS IEEE 1547-oriented functions and P/Q outputs | High for model scope | Verify exact pinned API and traces in G2 |
| Separate cyber messages and physical values | HELICS documentation distinguishes filterable messages from persistent physical values | High | Federation topology/bypass test |
| Adapter-first rather than NATIG wholesale | NATIG launch assumptions conflict with the current five-federate GridPACK experiment | High from code review | Minimal bridge prototype |
| EV4/l92 first device site | Existing v2 feeder already contains a 200 kW, 205 kWh storage location there | High from local model | Sensitivity/observability pilot |
| Frequency functions deferred | Current transmission exchange publishes phase voltages, not a validated dynamic frequency | High from local configs | Add and validate a causal frequency source |

## Known risks

### R1 — NATIG reproducibility

The reviewed NATIG workflow references historical tags without commit
assertions and optional private PNNL Stash locations. Mitigation: pin the
public repository, inventory every dependency and patch, and fail G1 if a
clean public build cannot be reproduced.

G1 pinned public NATIG commit
`e163b350e243c6386477e35dead979a4cb2b7c60` (tree
`9f10cb55d5eaa4c20a95f292b84a266e9992bc1a`) and found that its Dockerfile
reclones moving NATIG HEAD rather than consuming the pinned checkout. The
upstream build is retained as compatibility evidence, not treated as a pinned
reproducibility proof. A v3-only locked build is required for G1 to pass.

### R11 — Published NATIG control is attack-enabled

The public IEEE-123 `3G-conf-123` preset enables three MITM applications from
simulation second 1 through 20. It cannot serve as a no-attack control.
Mitigation: generate and hash a v3-only overlay with `includeMIM=0`,
`DDoS.Active=0`, and `Controller.use=0`; assert the effective in-container
configuration after every run. Preserve the upstream preset and its hash.
Merely setting attack probability to zero is insufficient: the MITM code can
still schedule a reset-to-real-value direct operate. G1 therefore disables the
MITM applications entirely and rejects attack/reset markers or an attack log.

### R12 — NATIG launcher false success

The public Docker-mode launcher backgrounds all federates and exits zero
without waiting. Even its waiting branch ends with unconditional `exit 0`.
Mitigation: run the waiting branch only as a process coordinator, then
independently require effective no-attack configuration, complete output logs,
no surviving federate processes, no fatal signatures, and immutable artifact
hashes.

### R2 — Hidden direct path

The current controller and attacker both target GridLAB-D EV endpoints.
Mitigation: create separate v3 endpoint configurations, inspect the federation
graph automatically, and reject any networked run containing a cyber source
whose destination is a physical actuation endpoint.

### R3 — Double-counted storage

EV1 and EV4 already have GridLAB-D inverter/battery structures.
Mitigation: a preflight assertion proves exactly one device model owns each
site.

### R4 — Timestep aliasing

OpenDER dynamic functions cannot be interpreted scientifically at a 60–120 s
physical coupling step without validation.
Mitigation: component tests at 1 s, convergence studies at 1/5/10/60 s, and
claims limited to the validated resolution.

### R5 — Non-dynamic or constant frequency

A nominal frequency property does not prove a meaningful electromechanical
frequency response.
Mitigation: exclude frequency attack/response hypotheses until a causal
frequency source and cross-simulator validation are present.

### R6 — Sign and unit ambiguity

Load convention, inverter convention, OpenDER per-unit bases, and DNP3 scaled
analogs can invert or rescale an effect.
Mitigation: positive/negative pulse tests, explicit bases, one conversion per
boundary, and power-balance assertions.

### R7 — Attacker capability mismatch

An LLM attacker can appear superior if it has more observations, actions, time,
or retries.
Mitigation: a capability manifest is generated per condition and equality is
asserted before paired runs.

### R8 — Ceiling conditions and small samples

The v2 Hour 14 condition is insensitive, and earlier groups are small.
Mitigation: Hour 14 is a negative control; pilot for variance and power the
confirmatory paired contrasts.

### R9 — Informative failures

HELICS timeouts or solver failures may correlate with stronger attacks.
Mitigation: retain failure records, compare failure rates, and conduct a
worst-case composite sensitivity analysis.

### R10 — Protocol realism overclaim

OpenDER is a behavioral device model, not a DNP3 or IEEE 2030.5 server.
Mitigation: attribute protocol behavior to the gateway/NATIG layer and device
behavior to OpenDER. Do not call the combined model a vendor implementation.

## Automated preflight assertions

Before each run, the eventual runner must verify:

- [ ] Config schema and campaign manifest validate.
- [ ] Git and dependency identities are captured.
- [ ] Federation count equals the declared topology.
- [ ] Endpoint graph contains no forbidden bypass.
- [ ] Every DNP3 point maps to exactly one semantic field.
- [ ] Every command target exists and is authorized.
- [ ] Device and feeder base voltage, kVA, kW, kvar, and energy units agree.
- [ ] Exactly one storage implementation is active per site.
- [ ] All seeds are present and distinct by subsystem.
- [ ] Output directory is new and immutable after completion.
- [ ] Simulated network is isolated from external interfaces.

After each run:

- [ ] All federates finalized or a failure class was recorded.
- [ ] HELICS time is monotonic per federate.
- [ ] Event timestamps satisfy send ≤ ingress ≤ egress ≤ receive ≤ accept ≤
      setting-apply ≤ physical-effect when each event exists.
- [ ] Command counts reconcile across source, PCAP, DNP3, gateway, and device
      logs.
- [ ] Power and energy residuals meet tolerance.
- [ ] Required PCAP, event, physical, and metadata hashes exist.
- [ ] No NaN/Inf appears in a successful trace.
- [ ] Inclusion/exclusion follows the frozen rule.

## Review gate

A self-audit may approve code validity and component equivalence. It may not
promote a pilot into confirmatory evidence, change the primary outcome after
viewing results, or erase failures. Those changes require a new versioned
protocol and RKA decision with provenance.

## G0 execution record

- [x] Frozen v2 campaign identity verified before analysis.
- [x] All 45 planned slots reconciled: 37 completed and 8 failed.
- [x] Welch tests corrected with `equal_var=False`.
- [x] Exact permutation tests and Holm correction added.
- [x] Missingness structure and physical worst-case bounds reported.
- [x] Fresh-output reproducibility check produced byte-identical JSON and CSV.
- [x] Controller period/source semantics audited.
- [x] Live HELICS 3.6.1 cadence probe reproduced byte-for-byte.
- [x] Frozen loop measured at up to seven logical decisions per grant.
- [x] Repaired period-10 loop measured at one logical decision per grant.
- [x] Two-federate value probe measured 5 distinct samples and 25 adjacent
      repeats across 30 frozen-loop decisions.
- [x] Repaired value probe measured 29 fresh post-start samples and zero
      adjacent repeats.
- [x] Both GridLAB-D feeder periods identified as 60 seconds; minimum
      timesteps identified as 60 and 120 seconds and frozen by hash.
- [x] Actual IEEE-123 Feeder A frozen and physical-10 arms executed twice.
- [x] Pre-pulse component state agrees within 1 W per phase.
- [x] Bounded EV4 effect magnitude agrees within 2% across cadence arms.
- [x] Physical-10 internal actuation measured at 10 seconds.
- [x] Physical-10 controller-visible feedback measured at 20 seconds.
- [x] Frozen internal actuation/feedback measured at 60/120 seconds.
- [x] Isolated 1.5 MW FBS convergence failure preserved and classified.
- [x] Full-coupling first-minute failure reproduced with exact five-federate
      timing topology.
- [x] Invalid co-phasal GridPACK boundary captured and causally replayed.
- [x] V3-only non-cumulative phase-rotation repair built and hashed.
- [x] Repaired frozen full federation completed twice with zero return codes.
- [x] Clean full control/pulse arms completed at frozen60 and physical10.
- [x] Full bounded effect magnitude agrees within 2% across cadence arms.
- [x] V3 timing contract frozen at 10-second actuation / 20-second feedback.
- [x] Token-limit configuration discrepancy resolved to effective runtime code.
- [x] V3 protocol explicitly adopts measured 20-second physical feedback.
- [x] Full GridPACK-coupled bounded equivalence demonstrated.
- [x] G0 approved for independent NATIG/OpenDER component proofs.
- [ ] Preserved 1.5 MW command limit characterized before campaign-scale use.
- [ ] Benign network/device equivalence demonstrated before attack comparison.

G0 passes with carried limitations for G1/G2 component proofs. The frozen v2
fresh 10-second-feedback mechanism remains falsified; v3 uses measured
10-second actuation / 20-second feedback. No attack comparison is approved.
See `baseline/G0_VALIDATION_REPORT.md`.

## G1 execution record

- [x] NATIG source commit and clean tree frozen and verified in-container.
- [x] Public dependency resolutions inventoried to exact commits/digests.
- [x] Upstream-source container build completed and image ID captured.
- [x] Published PNNL image inspected and rejected as an invalid current
      fallback.
- [x] Attack-enabled upstream IEEE-123 preset identified.
- [x] Create-once no-attack overlay generated twice byte-identically.
- [x] Upstream launcher false-success/reconfiguration failure preserved.
- [x] V3 wrapper hardened to track broker, GridLAB-D, and ns-3 exit status.
- [x] Two 20-second no-attack IEEE-123 runs completed with 36/36 assertions.
- [x] Both runs produced 38/38 physical recorders and 38,514 DNP3 packet
      records.
- [x] Exact output-hash comparison executed and retained as a failure.
- [x] Post-hoc polar-aware numerical diagnosis recorded separately.
- [ ] Locked-source container built from the immutable dependency inventory.
- [ ] Undeclared `CC/Monitor` HELICS destinations eliminated.
- [ ] Wire-format capture added or the packet-event substitute formally
      justified for G4.
- [ ] NATIG DNP3 points mapped to OpenDER semantic fields.
- [ ] Benign end-to-end equivalence demonstrated before attack comparison.

G1 is a bounded component proof, not a full WP1 pass. The exact same-seed
physical hashes differ in 30/52 artifacts despite identical DNP3 traces and
small numerical differences. Each run also logged 2,223,117 auxiliary HELICS
endpoint drops. G3 may proceed independently; G4 and all attack-effect work
remain blocked. See `natig/G1_VALIDATION_REPORT.md`.

## G3 execution record

- [x] Canonical Feeder A source/config and pinned runtime identities asserted.
- [x] Complete legacy EV4 storage owner tree removed from a v3-only overlay.
- [x] OpenDER coupling corrected to bus l92, outside the legacy charger switch.
- [x] Existing EV4 charger load preserved and `swEV4=CLOSED` recorded.
- [x] HELICS config contains no switch target and no message endpoints.
- [x] Positive/negative 10 kW and 10 kvar sign/unit mapping verified.
- [x] Pulse and matched-null arms completed at 1/5/10/60-second coupling.
- [x] One-second OpenDER internal step held fixed in every arm.
- [x] Local applied-power mapping residual remains below 0.005 VA.
- [x] SOC/energy accounting agrees within `3.89e-16` SOC.
- [x] Paired source P/Q balance meets 2 kW/kvar at 1/5/10 seconds.
- [x] Ten seconds selected as the coarsest passing coupling cadence.
- [x] Sixty seconds retained as a five-gate physical convergence failure.
- [x] Selected 10-second pulse/null repeat is numerically exact.
- [x] Superseded topology and evaluator/deadlock failures remain preserved.
- [x] Typed DNP3 point map and cyber gateway validated.
- [ ] Benign direct-reference versus NATIG equivalence demonstrated.

G3 passes only for the tested one-device physical adapter and schedule. It
does not include NATIG, DNP3, GridPACK, cyber impairment, or attacker behavior.
G4 may begin; attack-effect experiments remain blocked. See
`opender_federate/G3_VALIDATION_REPORT.md`.

## G4 preparation execution record

- [x] Minimal writable surface frozen to AO0 active kW and AO1 reactive kvar.
- [x] AO2, AO3, autonomous curves, and all switch outputs disabled.
- [x] Telemetry frozen to AI0-AI3 and independent BI0/BI1 status points.
- [x] G41V1, G30V5, and G1V2 object-body codecs validated with hostile cases.
- [x] Stock status/index remapping defect reproduced and rejected.
- [x] Exact four-endpoint cyber graph separated from the HELICS-value plane.
- [x] Legacy `CC/Monitor`, `fout`, direct controller/gateway, and
      NATIG/GridLAB-D paths rejected by the graph validator.
- [x] Deterministic outstation trust boundary correlates one immutable
      semantic envelope across SELECT and OPERATE.
- [x] Gateway acceptance, sink queueing, and actual OpenDER application are
      distinct, fail-closed lifecycle stages.
- [x] AO0 persists as the sole device demand input; AO1 atomically matches the
      G3 constant-Q mode semantics.
- [x] Two 840-second offline direct-versus-byte-coded OpenDER runs match
      exactly for P, Q, SOC, command lifecycle, and source hashes.
- [x] All 5,040 analog/binary telemetry roundtrips meet declared bounds.
- [ ] Locked NATIG image rebuilt with the frozen source and adapter patch.
- [ ] Live DNP3/ns-3 traffic traverses the exact endpoint graph without
      GridLAB-D message endpoints or undeclared destinations.
- [ ] Direct-reference and live benign NATIG paths meet the G4 physical and
      latency equivalence criteria.

The offline adapter-conformance result is a bounded preparation PASS, not G4
completion. It exercises real OpenDER models but no NATIG, ns-3, HELICS, or
GridLAB-D runtime. The G4 mission therefore remains active and all impairment
or attack-effect work remains blocked. See
`natig_adapter/offline_conformance_r2/OFFLINE_CONFORMANCE_REPORT.md`.
