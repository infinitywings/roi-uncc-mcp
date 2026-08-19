# GridEval v3: NATIG and OpenDER Expansion

## Objective

GridEval v3 extends the current IEEE 123-bus experiment in two independent
directions:

1. NATIG supplies an explicit ns-3/DNP3 cyber network between control intent
   and device actuation.
2. OpenDER supplies standards-oriented PV and BESS behavior at selected feeder
   nodes.

The experiment is designed to answer whether the v2 attacker rankings and
attack effectiveness survive realistic network constraints and realistic local
DER behavior. It is not a wholesale replacement of v2. The verified v2
federation remains the direct-path reference condition.

## Design decision

Use an adapter-first hybrid integration:

- Keep GridPACK, both GridLAB-D feeders, the v2 controller, and the GridEval
  attacker.
- Add a NATIG-derived ns-3/DNP3 network federate.
- Add an OpenDER device federate and a DNP3-to-OpenDER gateway.
- Route all cyber commands and telemetry through endpoints and the network
  federate.
- Keep physical voltage, frequency, active-power, and reactive-power coupling
  on HELICS value interfaces.
- Prohibit controller or attacker endpoints from addressing GridLAB-D or
  OpenDER actuation endpoints directly in networked conditions.

This separation follows HELICS semantics: messages represent communications
that can be delayed, dropped, rerouted, or modified; values represent persistent
physical state.

## First implementation target

The smallest scientifically useful build is one OpenDER BESS at the existing
EV4/storage location on node `l92`, phase C:

- The legacy 200 kW EV4 load stays in place.
- The existing disconnected GridLAB-D storage branch is disabled for this
  condition so two battery models cannot act simultaneously.
- OpenDER receives the local terminal voltage and a declared frequency source.
- OpenDER publishes signed `P` and `Q` injection to a GridLAB-D coupling object.
- A DNP3 gateway maps authenticated controller commands to OpenDER settings.
- The same gateway publishes DER telemetry to the control center through
  NATIG.

After equivalence and causality tests pass, add a second OpenDER device at EV1
on node `l5`, phase C. Using EV1 and EV4 preserves existing electrical
locations and ratings while allowing single-device and coordinated attacks.

## Work packages and gates

| Gate | Work package | Exit criterion |
|---|---|---|
| G0 | Freeze and repair v2 evidence | Canonical config and analysis hashes recorded; timeout and statistical caveats resolved or explicitly carried forward |
| G1 | NATIG reproducible build proof | Pinned NATIG commit builds from public inputs; IEEE 123 benign DNP3 example completes twice with identical seeds |
| G2 | OpenDER component proof | PV/BESS unit traces reproduce official examples and pass sign, unit, ramp, capability, trip, and state-of-charge tests |
| G3 | One-device physical loop | GridLAB-D and OpenDER converge without cyber mediation; energy and voltage residuals meet tolerances |
| G4 | Benign network equivalence | DNP3/ns-3 path produces the same accepted command sequence as the direct path within declared timing tolerances |
| G5 | Network impairment screening | Delay, loss, jitter, and outage effects are measurable and reproducible without an attacker |
| G6 | Cyberattack campaign | Scripted, random, and LLM attackers use the identical DNP3 capability surface and matched budgets |
| G7 | Two-device campaign | Single-site and coordinated attacks are compared with paired seeds and equal control authority |
| G8 | Confirmatory campaign | Analysis plan and exclusions are frozen before confirmatory runs |

No later gate begins by silently waiving an earlier acceptance criterion.

Current execution status:

- **G0 passed with carried limitations:** v3 uses 10-second internal
  actuation and 20-second controller-visible feedback; no attack comparison
  is approved.
- **G1 bounded component proof:** the pinned upstream-source NATIG image and
  benign IEEE-123/DNP3 example execute, but locked-source construction,
  numerical repeatability, and undeclared endpoint debt remain open.
- **G2 passed with wrapper limitation:** OpenDER 2.2.0 passes 565 upstream
  tests and deterministic GridEval traces. Its internal setting delay remains
  disabled; all delayed settings use `opender/device.py`.
- **G3 passed for one physical adapter:** the l92 OpenDER BESS passes the
  paired physical-loop gate at the selected 10-second coupling cadence.
- **G4 preparation passed offline only:** the minimal AO0/AO1 point map,
  DNP3 object codec, endpoint graph, semantic bridge, gateway lifecycle, and
  840-second direct-versus-byte-coded OpenDER conformance pass. Live
  NATIG/ns-3/HELICS/GridLAB-D benign equivalence remains blocked by G1 debt.

## Repository artifacts

- [Architecture](ARCHITECTURE.md)
- [Experiment protocol](EXPERIMENT_PROTOCOL.md)
- [Self-audit and readiness gates](SELF_AUDIT.md)
- [DER device configuration](configs/der_devices.yaml)
- [Network scenario configuration](configs/network_scenarios.yaml)
- [Cyber message contract](interfaces/cyber_message.schema.json)
- [Interface notes](interfaces/README.md)
- [G4 adapter contract](natig_adapter/README.md)
- [G4 offline conformance report](natig_adapter/offline_conformance_r2/OFFLINE_CONFORMANCE_REPORT.md)

## Pinned upstream starting points

- NATIG repository: <https://github.com/pnnl/NATIG>, reviewed at
  `e163b350e243c6386477e35dead979a4cb2b7c60`
- NATIG paper: <https://arxiv.org/abs/2307.09633>
- OpenDER repository: <https://github.com/epri-dev/OpenDER>, reviewed at
  `fe7877c664bc6c5eb3832499bf05e0f1dd1825c8`
- OpenDER interface example:
  <https://github.com/epri-dev/OpenDER_interface>, reviewed at
  `1faa70bf7bd911005dc30f7b5c3c3f8fe1cf9248`
- OpenDER documentation: <https://opender.readthedocs.io/en/latest/>
- HELICS message/filter guidance:
  <https://docs.helics.org/en/latest/user-guide/fundamental_topics/message_federates.html>
- NIST DER cybersecurity practice guide:
  <https://csrc.nist.gov/pubs/sp/1800/32/final>

The reviewed NATIG workflow references development branches and PNNL-internal
Stash locations for parts of its historical ns-3/HELICS/DNP3 toolchain. G1 is
therefore a hard reproducibility gate, not a routine installation step.
