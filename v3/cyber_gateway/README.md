# GridEval v3 deterministic cyber gateway

This directory is the standalone, offline-testable G4 command boundary between
the semantic v3 cyber envelope and the OpenDER BESS settings. It does not run
NATIG, ns-3, DNP3, HELICS, GridLAB-D, or Docker.

## Contract

- `dnp3_point_map.yaml` is JSON-compatible YAML so it can be parsed with the
  Python standard library and consumed by YAML tooling.
- The message envelope remains exactly
  `v3/interfaces/cyber_message.schema.json`; DNP3 `select` and `operate` are
  passed as transport metadata to `CyberGateway.ingest`.
- Every enabled point checks exact type (including rejecting booleans as
  numbers), unit, range/enum, target, source authority, source sequence,
  simulation-time freshness, expiry, lineage, and SBO state.
- SELECT and OPERATE carry the same immutable message and ID. A second SELECT
  or OPERATE is a duplicate. An OPERATE consumes its SELECT.
- Accepted operations enter a stable `(due_time_s, acceptance_sequence)` heap.
  No wall-clock or random input affects ordering.
- Every select, acceptance, rejection, sink queueing, and confirmed OpenDER
  application is appended as one canonical JSON line. Existing event-log
  content is never truncated.

The G4 pulse surface is AO0 `active_power_setpoint` in signed kW and AO1
`reactive_setpoint` in signed kvar. Both use a signed 32-bit count scaled by
0.001 engineering unit/count, matching the stock NATIG count/1000 convention.
They are the only enabled and authorized output points. AO2
`active_power_limit`, AO3 `reactive_mode`, `autonomous_curve`, and every binary
output remain disabled.

The read-only telemetry surface is frozen independently from the output
namespace: AI0/AI1 are realized active kW/reactive kvar, AI2 is terminal
voltage pu, and AI3 is state of charge pu. They are raw G30V5 float32
engineering values, with no integer scale. BI0 is the G1V2 connected Boolean;
BI1 is the G1V2 `command_accepted` Boolean and means gateway validation plus
queue acceptance, never DNP3 response status or a packed quality field.

Point-map loading is fail-closed for this exact contract: DNP3 object, wire
type, group/index, command scale and signed-int32 range, point uniqueness,
authority, SBO exact-value matching, telemetry shape, device/address, and sign
conventions must all match before a gateway can start.

## OpenDER application boundary

`advance_to(t, sink=device)` calls
`ScheduledOpenDERBESS.schedule_gateway_action` and removes an action from the
gateway heap only after the sink call succeeds. AO0 becomes persistent
`demand_kw` and owns that input on every later one-second step; a competing
explicit demand then fails closed.

AO1 is one queued snapshot: it disables QV, QP, and constant-PF modes, converts
kvar to `CONST_Q` pu using the frozen 200 kVA rating, and enables constant-Q
only for a nonzero request. Zero kvar disables the mode, matching G3.

Lifecycle records are separate:

1. `command_accepted` means gateway validation and insertion into its queue.
   BI1 has this meaning; it is not physical application.
2. `sink_queued` means the OpenDER wrapper accepted the immutable action.
3. `opender_action_applied` is emitted only after the caller passes the exact
   record returned by a later OpenDER step to
   `record_opender_applications`.

Application reporting fails closed on unknown or duplicate actions, changed
settings or inputs, and due-time mismatches. The caller must align gateway and
device time, call `advance_to` before `step`, and feed application records back
to the gateway. If that final call is omitted, the log correctly stops at
`sink_queued`. OpenDER `NP_SET_EXE_TIME` remains zero.

## Offline tests

Run:

```bash
v3/deps/opender-venv/bin/python -m pytest -q v3/cyber_gateway/tests
```

Before a campaign, record the exact point-map digest:

```bash
v3/deps/opender-venv/bin/python -c \
  'from v3.cyber_gateway import point_map_sha256; print(point_map_sha256())'
```

This module proves deterministic validation/arbitration and OpenDER setting
mapping only. It is not benign direct-versus-NATIG equivalence evidence.
Its `gateway_decision` values are local policy decisions, never DNP3 response
or acknowledgement codes.
