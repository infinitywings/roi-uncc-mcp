# GridEval v3 Architecture

## 1. Constraints inherited from v2

The current v2 federation has five federates:

1. GridLAB-D IEEE 123-bus feeder A
2. GridLAB-D feeder B
3. GridPACK transmission
4. EV controller
5. GridEval attacker

Controller and attacker commands currently go directly to
`gld_hlc_conn/EV1` through `EV6`. That direct route bypasses any simulated
communications network. v3 must remove this bypass in every networked
condition, while retaining an explicitly labeled direct-path baseline.

The simulators also advance on different native periods: 5 seconds for
GridPACK and the attacker, 60 seconds for feeder A and the controller HELICS
configuration, and 120 seconds for feeder B. A v3 run is invalid until the
granted-time trace demonstrates causal ordering at every command and physical
update boundary.

## 2. Target federation

The initial target has seven federates:

| Federate | Kind | Native step | Responsibility |
|---|---|---:|---|
| `gridpack` | HELICS value | 5 s | Transmission/distribution boundary voltage and power |
| `gld_feeder_a` | HELICS combination | 60 s initially | IEEE 123-bus feeder and coupling objects |
| `gld_feeder_b` | HELICS value | 120 s initially | Existing second feeder |
| `ev_controller_v3` | HELICS message/value | 10 s | Defender intent and control-center logic |
| `grideval_attacker_v3` | HELICS message/value | 5 s | Adversary policy with capability enforcement |
| `natig_network` | HELICS filter/message + ns-3 | 1 s or event driven | Network topology, DNP3 delivery, impairments, attacks, PCAP |
| `opender_gateway` | HELICS combination | 1 s initially | DNP3 outstation map, OpenDER model step, physical P/Q exchange |

If the NATIG bridge cannot cleanly combine the DNP3 outstation and OpenDER
model, split `opender_gateway` into an eighth federate. The experimental
interface remains unchanged.

## 3. Two planes

### Cyber plane

All control and telemetry that would traverse a field network uses HELICS
messages:

```text
controller or attacker
        |
        | command envelope
        v
NATIG/ns-3 control-center node
        |
        | DNP3 over simulated IP network
        v
NATIG/ns-3 field node
        |
        | validated DNP3 point update
        v
OpenDER gateway
```

The reverse telemetry path uses the same field and control-center nodes.
Commands, status, alarms, measurements, acknowledgements, and quality flags
are individually timestamped and sequenced.

### Physical plane

Physical state uses HELICS values:

```text
GridLAB-D local complex voltage and frequency
        |
        v
OpenDER model: IEEE 1547 functions, limits, ramping, trip, SOC
        |
        v
GridLAB-D signed active/reactive injection
```

The cyber network must never transport the physical coupling values. Conversely,
the controller and attacker must never write OpenDER settings through value
publications.

## 4. Command ownership and arbitration

v2 allows controller and attacker messages to race at the same GridLAB-D
endpoint. v3 makes arbitration explicit:

1. The legitimate controller creates a command with a monotonically increasing
   sequence number.
2. An attacker may originate, modify, replay, delay, or suppress commands only
   through its assigned scenario capability.
3. The DNP3 outstation/gateway validates schema, point range, target, command
   type, select-before-operate policy, and freshness.
4. Accepted commands enter an append-only actuation log.
5. The latest accepted value for each point becomes the requested device
   setting after any modeled execution delay.
6. OpenDER local autonomous functions and capability limits determine realized
   `P` and `Q`; command acceptance does not imply physical tracking.

Every actuation record includes the original message ID, any derived or
modified message ID, network delivery timestamps, acceptance reason, OpenDER
setting timestamp, and first measurable physical-effect timestamp.

## 5. Device placement and mapping

### Stage 1: one BESS

| Item | Value |
|---|---|
| Device ID | `DER_EV4_BESS` |
| Feeder node | `l92` |
| Phase | C |
| Apparent power | 200 kVA initial |
| Energy | 205 kWh initial |
| Initial SOC | 0.50 |
| Physical comparison | Existing EV4 storage location |
| Cyber field node | `rtu_ev4` |

The existing `swEV4_storage` branch must be open or its inverter/battery objects
must be excluded whenever OpenDER owns the device. A preflight assertion must
fail if both are active.

### Stage 2: second device

Add `DER_EV1_PV` or `DER_EV1_BESS` at `l5`, phase C, after G4. Use a BESS for
the cleanest legacy-storage comparison; use PV only after an irradiance and
available-power trace has been declared. Do not change both device type and
network scenario in the first paired comparison.

## 6. DNP3 point-map minimum

The exact point indices are generated and frozen per campaign. The semantic
minimum is:

| Direction | Point | Unit/encoding | Purpose |
|---|---|---|---|
| telemetry | terminal voltage | pu plus raw V | OpenDER input and operator visibility |
| telemetry | frequency | Hz | OpenDER input and operator visibility |
| telemetry | active power | kW, signed | Realized output |
| telemetry | reactive power | kvar, signed | Realized output |
| telemetry | SOC | pu | BESS state |
| telemetry | connection state | enum | connected, momentary cessation, tripped |
| telemetry | alarm/quality | bit field | stale, invalid, comms loss, limit active |
| command | connect permit | boolean | Remote connection permission |
| command | active power limit | pu | IEEE 1547 active-power limiting |
| command | reactive mode | enum | constant Q, PF, volt-var, watt-var |
| command | reactive setpoint | pu | Mode-dependent setpoint |
| command | curve selection/settings | versioned object | Approved autonomous function |

All sign conventions are from the feeder perspective and must be proven with a
positive and negative pulse test. The configuration declares whether positive
`P` means injection or consumption; adapters perform conversions exactly once.

## 7. Network topology

Start with a star Ethernet/CSMA topology because it is the simplest NATIG
configuration and matches a control-center/field-device experiment:

```text
control_center
      |
  aggregation_switch
      |
  rtu_ev4 [and later rtu_ev1]
```

Only after benign equivalence:

- add deterministic delay;
- add bounded random delay and loss;
- add constrained bandwidth/queueing;
- add DDoS-induced congestion;
- add MITM modification/replay at a declared link or node.

Ring, mesh, Wi-Fi, 4G, and 5G are not first-stage factors. They are follow-up
topology studies if the star results show a meaningful cyber-physical effect.

## 8. Timing contract

Each federate records:

- requested and granted HELICS time;
- source event time;
- send, network ingress, network egress, receive, accept, setting-apply, and
  physical-effect times;
- sequence number and random seed.

Initial proposal:

- OpenDER internal step: 1 s
- ns-3 scheduler: event-driven with 1 s HELICS synchronization ceiling
- attacker observation/action: 5 s
- controller decision and DER/feeder actuation: 10 s
- controller-visible physical feedback: 20 s under the validated
  non-iterative HELICS coupling
- GridLAB-D: retain 60 s only for frozen v2 reproduction; use the validated
  10 s feeder step for the legacy-device v3 bridge and separately test 1–5 s
  coupling for dynamic OpenDER functions

Frequency-watt and frequency ride-through are excluded from the MVP unless the
frequency signal is shown to vary causally with the simulated grid. A fixed
60 Hz placeholder is acceptable for interface tests but not for a scientific
frequency-response claim.

## 9. NATIG integration boundary

Do not copy NATIG’s `run-123.sh` federation into GridEval unchanged. It assumes
its own IEEE 123 model, two federates, a different broker port, and a custom
ns-3/DNP3/HELICS toolchain. Reuse and pin:

- the ns-3/HELICS/DNP3 bridge pattern;
- public patches or submodules required to reproduce it;
- configuration generation for HELICS endpoints and DNP3 points;
- network topology and attack applications;
- PCAP and network-metric collection.

GridEval owns:

- the seven/eight-federate launch manifest;
- cyber message schema and point semantics;
- GridLAB-D/OpenDER physical adapter;
- attacker capability enforcement;
- experiment manifests and analysis.

## 10. Build and security boundary

- Pin upstream commits, container base images, compiler, ns-3, HELICS, DNP3,
  OpenDER, GridLAB-D, and GridPACK versions.
- Build without relying on private PNNL repositories. If that is impossible,
  record G1 as failed and implement the same public interface with maintained
  public ns-3/HELICS components.
- Run attack traffic only inside an isolated container network.
- Use synthetic addresses and no route to operational DER, utility, or public
  network endpoints.
- Store PCAPs and payloads as research data; scrub credentials and never embed
  real access tokens.
