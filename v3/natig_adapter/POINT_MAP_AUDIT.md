# G4 NATIG Point-Map Audit

## Scope and source identity

This audit defines the narrow point-map boundary needed for the G4 benign
cyber-path equivalence experiment. It is based on the clean, pinned NATIG
checkout at:

- commit `e163b350e243c6386477e35dead979a4cb2b7c60`;
- tree `9f10cb55d5eaa4c20a95f292b84a266e9992bc1a`; and
- G1 source-built image
  `sha256:662e1ae46656de8a97195d7a6a6f7cfef84bd0baa997fedbea859e9d76978f7c`.

The runtime source selection is explicit. `v3/deps/natig-src/build_ns3.sh:51-55`
copies `RC/code/helics/dnp3-application-new-Docker.cc` and its header over the
ns-3 HELICS application, while
`v3/deps/natig-src/Dockerfile:164-176` installs
`ns3-helics-grid-dnp3-Docker.cc` and the DNP3 library. The pinned ns-3 source
and the G1 effective source have the same SHA-256,
`dc524ee65f05d552ca29e5d6d083140cf54112c5ae0e626c29e1198fd4462656`.

The contract recommended below is a **new NATIG-derived adapter contract** for
GridEval. It is not a claim that unmodified NATIG already provides an
OpenDER/EV4 gateway, typed directionality, semantic command acceptance, or
controller-visible DNP3 telemetry.

## How stock NATIG assigns point indices

NATIG reads each point CSV in file order and appends ANALOG and BINARY names to
two separate vectors. The third CSV field is parsed as the initial value; it is
not a scale, engineering-unit, direction, or access field
(`v3/deps/natig-src/RC/code/helics/dnp3-application-new-Docker.cc:851-898`).

Consequently:

- analog indices are zero-based positions among ANALOG rows only;
- binary indices are zero-based positions among BINARY rows only; and
- a CSV line number is not a DNP3 index.

Both the master and outstation are given the same point file
(`v3/deps/natig-src/RC/code/ns3-helics-grid-dnp3-Docker.cc:860-890`).
Stock NATIG therefore reuses one analog-name vector for AI and AO lookup and
one binary-name vector for BI and BO lookup. The point file does not enforce
read-only versus writable access.

### Relevant stock IEEE-123 indices

The following indices are derived from
`v3/deps/natig-src/RC/code/points-123/points_mg1.csv`.

| DNP3 namespace | Zero-based index | CSV line | Stock point name |
|---|---:|---:|---|
| AI/AO | 60 | 61 | `load_41$constant_power_C.real` |
| AI/AO | 61 | 62 | `load_41$constant_power_C.imag` |
| AI/AO | 116 | 117 | `trip_shad_inv1$Pref` |
| AI/AO | 117 | 118 | `trip_shad_inv1$Qref` |
| AI/AO | 118 | 119 | `trip_shad_inv4$Pref` |
| AI/AO | 119 | 120 | `microgrid_switch4$current_in_A.real` |
| AI/AO | 120 | 121 | `microgrid_switch4$current_in_A.imag` |
| AI/AO | 121 | 122 | `microgrid_switch4$current_in_B.real` |
| AI/AO | 122 | 123 | `microgrid_switch4$current_in_B.imag` |
| AI/AO | 123 | 124 | `microgrid_switch4$current_in_C.real` |
| AI/AO | 124 | 125 | `microgrid_switch4$current_in_C.imag` |
| BI/BO | 0 | 126 | `microgrid_switch4$phase_A_state` |
| BI/BO | 1 | 127 | `microgrid_switch4$phase_B_state` |
| BI/BO | 2 | 128 | `microgrid_switch4$phase_C_state` |
| BI/BO | 3 | 129 | `microgrid_switch4$status` |

These are evidence about the upstream example only. In particular,
`trip_shad_inv4` is not GridEval's `DER_EV4_BESS`, and the upstream
IEEE-123 namespace is not the GridEval feeder's `l92` namespace.

## Stock master/outstation behavior

### Roles and transport

For each configured microgrid, NATIG installs a master on the control-center
node and an outstation on the field node. It uses UDP, master device address
1, station device address `i + 2`, and a configured periodic poll; the IEEE-123
preset supplies a 10-second poll request period
(`v3/deps/natig-src/RC/code/ns3-helics-grid-dnp3-Docker.cc:838-891`).

### Analog outputs

`send_control_analog` constructs `Bit32AnalogOutput` and selects either
select-before-operate or direct-operate-with-response
(`v3/deps/natig-src/RC/code/helics/dnp3-application-new-Docker.cc:1092-1101`).
The master encodes this as DNP3 **Group 41 Variation 1**
(`v3/deps/natig-src/RC/code/dnp3/dnplib/master.cpp:707-725,801-819`);
the factory registration is at
`v3/deps/natig-src/RC/code/dnp3/dnplib/factory.cpp:192-194`.

Although the implementation stores the request in a `float` member, it
encodes the request through `appendINT32` and reconstructs a signed 32-bit
value on decode
(`v3/deps/natig-src/RC/code/dnp3/dnplib/object.cpp:366-389`). The upstream
attack-control path multiplies its engineering value by 1000 before creating
the Group 41 Variation 1 object
(`v3/deps/natig-src/RC/code/helics/dnp3-application-new-Docker.cc:1829-1833,1919-1924`).
The outstation divides the decoded request by 1000 before publishing it
(`v3/deps/natig-src/RC/code/dnp3/dnplib/outstation.cpp:752-769`).

Thus the implemented command convention is:

```text
wire_count = engineering_value * 1000
engineering_value = wire_count / 1000
```

This provides 0.001 engineering-unit per count, but NATIG does not declare what
the engineering unit is. The endpoint/property convention supplies the unit.

### Binary outputs

Binary controls use a DNP3 **Group 12 Variation 1** Control Output Relay Block
(`v3/deps/natig-src/RC/code/dnp3/dnplib/master.cpp:780-799`). The relevant
codes are defined at
`v3/deps/natig-src/RC/code/dnp3/dnplib/object.hpp:150-185`. The outstation
implements only:

- `TRIP` as the string `OPEN`; and
- `CLOSE` as the string `CLOSED`.

Other codes throw an error
(`v3/deps/natig-src/RC/code/dnp3/dnplib/outstation.cpp:775-825`).

### Analog and binary inputs

The outstation's static telemetry response uses:

- analog input **Group 30 Variation 5**, encoded as float values; and
- binary input **Group 1 Variation 2**, encoded with status flags.

The response construction is at
`v3/deps/natig-src/RC/code/dnp3/dnplib/outstation.cpp:1083-1148`; the master
poll requests are at
`v3/deps/natig-src/RC/code/dnp3/dnplib/master.cpp:995-1004`.

This packet exchange does not yield usable controller telemetry in stock
NATIG. `Dnp3ApplicationNew::changePoint` is empty
(`v3/deps/natig-src/RC/code/helics/dnp3-application-new-Docker.cc:943-960`),
and the Group 30 Variation 5 float decoder loops over values without calling
`changePoint`
(`v3/deps/natig-src/RC/code/dnp3/dnplib/factory.cpp:251-295`). G1's packet
evidence therefore proves DNP3 exchange, not master-side delivery of typed
telemetry.

### HELICS actuation path

For an analog or binary control, the outstation maps the zero-based index back
through the relevant name vector. A valid control is converted to JSON and
sent to a `GLD/<station/property>` HELICS message destination
(`v3/deps/natig-src/RC/code/dnp3/dnplib/outstation.cpp:752-825,865-885`;
`v3/deps/natig-src/RC/code/helics/dnp3-application-new-Docker.cc:2133-2177`).
This is GridLAB-D-specific routing. A GridEval OpenDER gateway must replace the
destination and apply the point through the validated OpenDER setting queue.

## Stock conflicts and unsupported claims

1. **No OpenDER or GridEval EV4 point exists.** The stock names
   `trip_shad_inv4`, `load_92`, and `microgrid_switch4` do not identify
   `DER_EV4_BESS` at GridEval bus `l92`.

2. **The inverter map is internally incomplete.**
   `points_mg1.csv:117-119` includes inverter 1 P/Q and inverter 4 P only.
   In contrast,
   `v3/deps/natig-src/RC/code/3G-conf-123/gridlabd_config.json:401-423`
   declares inverter 1 Q/P and inverter 4 Q/P endpoints. Its aggregate
   declaration at `gridlabd_config.json:425-430` also advertises inverter 1
   `Pmax`, for which there is no corresponding CSV point.

3. **The switch partition is contradictory.**
   `v3/deps/natig-src/RC/code/3G-conf-123/grid.json:40-46` assigns
   `microgrid_switch4` to `mg1`, while `grid.json:71-76` also assigns it to
   `mg2`. The `mg2` point file instead maps `switch_300-350` at
   `v3/deps/natig-src/RC/code/points-123/points_mg2.csv:100-109` and contains
   no `microgrid_switch4` binary point.

4. **The published preset is not benign.**
   `v3/deps/natig-src/RC/code/3G-conf-123/grid.json:2-10,252-312` enables MIM
   and declares inverter, load, and switch attacks. G4 must use the G1
   no-attack overlay with `includeMIM = 0`.

5. **The built-in command has no valid DER meaning.**
   The ns-3 model hard-codes a direct analog command at index 0 with value
   `-16` at 3.005 seconds
   (`v3/deps/natig-src/RC/code/ns3-helics-grid-dnp3-Docker.cc:891-897`).
   In the `mg1` file, analog index 0 is
   `node_36$voltage_A.real`, not a DER setting. The outstation's `/1000`
   conversion publishes `-0.016` in undeclared endpoint units. This command
   is useful only as packet-traffic stimulation.

6. **A DNP3 response is not semantic device acceptance.**
   An out-of-range AO/BO index is mapped to an `INVALID_*` key, but the
   outstation still constructs the protocol response
   (`v3/deps/natig-src/RC/code/dnp3/dnplib/outstation.cpp:759-769,798-825,865-880`).
   G4 must record gateway validation and queue acceptance separately from
   transport acknowledgment.

7. **Stock access control is too broad.**
   Because input and output lookups share the same vectors, any analog point
   can be addressed as an AO and any binary point as a BO. The adapter must
   reject every output index not explicitly listed as writable.

8. **Stock master telemetry is discarded.**
   No result should claim DNP3 telemetry equivalence until the adapter emits
   the decoded AI/BI values and their receive timestamps to the controller or
   the G4 evidence log.

## Recommended minimal one-DER contract

This table defines the new GridEval G4 adapter boundary. The index namespaces
are independent DNP3 point types even though the stock CSV implementation
conflates their name storage.

| Type/index | Name | DNP3 representation | Scale and unit | Access and semantics |
|---|---|---|---|---|
| AO0 | `DER_EV4_BESS.P_CMD_KW` | G41V1 signed int32 | `count = kW * 1000`; `kW = count / 1000` | Writable allowlist; positive is generation/discharge, negative is absorption/charge |
| AO1 | `DER_EV4_BESS.Q_CMD_KVAR` | G41V1 signed int32 | `count = kvar * 1000`; `kvar = count / 1000` | Writable allowlist; positive is injection, negative is absorption |
| AI0 | `DER_EV4_BESS.P_APPLIED_KW` | G30V5 float32 | Raw engineering kW | Read-only realized OpenDER output |
| AI1 | `DER_EV4_BESS.Q_APPLIED_KVAR` | G30V5 float32 | Raw engineering kvar | Read-only realized OpenDER output |
| AI2 | `DER_EV4_BESS.V_TERMINAL_PU` | G30V5 float32 | Raw pu | Read-only terminal-voltage input observed by OpenDER |
| AI3 | `DER_EV4_BESS.SOC_PU` | G30V5 float32 | Raw pu in `[0,1]` | Read-only OpenDER state of charge |
| BI0 | `DER_EV4_BESS.CONNECTED` | G1V2 boolean | `0=false`, `1=true` | Read-only device connection state |
| BI1 | `DER_EV4_BESS.COMMAND_ACCEPTED` | G1V2 boolean | `0=false`, `1=true` | Read-only gateway validation-and-queue result, not DNP3 response status |

There is deliberately **no BO or switch-control point in G4**. G3 assigns
`swEV4` to the physical-loop runner, holds it statically `CLOSED`, and excludes
it from HELICS control. Adding a DNP3 switch point would reintroduce competing
ownership. Any future switch experiment must explicitly transfer ownership in
a separate validation stage and, if it retains NATIG's existing convention,
use Group 12 Variation 1 `TRIP`/`CLOSE`.

## Adapter obligations for G4

The minimal contract is valid only if the NATIG-derived adapter:

1. accepts a typed controller command and permits only AO0 or AO1;
2. rejects non-finite, out-of-range, duplicate, stale, and otherwise invalid
   commands before they reach OpenDER;
3. converts G41V1 counts to kW/kvar exactly once and preserves the G3 sign
   convention;
4. sends accepted settings through the validated simulation-time OpenDER
   queue rather than OpenDER's defective internal execution-delay path;
5. records command ID plus controller-send, DNP3-receive, validation,
   queue, application, and observation times, together with rejection reason;
6. treats BI1 as gateway validation-and-queue acceptance and retains the
   append-only command log as the authoritative evidence;
7. exposes decoded AI0-AI3 and BI0-BI1 at the master rather than discarding
   them; and
8. disables MIM, DDoS, loss, delay, modification, replay, and attacker logic
   for the benign-equivalence gate.

Passing this contract would establish equivalence for the tested one-DER
command trace and observables. It would not establish general NATIG protocol
conformance, vendor-device behavior, switch control, cyberattack impact, or
multi-DER behavior.
