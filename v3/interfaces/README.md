# GridEval v3 Interface Contract

`cyber_message.schema.json` defines the semantic envelope exchanged between the
GridEval control/attacker applications, the NATIG bridge, and the OpenDER
gateway. NATIG may encode the fields into DNP3 points, but logs at both sides
must retain this envelope or a lossless reconstruction.

## Rules

1. `message_id` is globally unique within a campaign.
2. `sequence` is monotonic per source/target/command stream.
3. `event_time_s` is the simulated time at which the source created the event.
4. Network and gateway timestamps are appended to logs; intermediaries do not
   overwrite `event_time_s`.
5. A modified or replayed message retains `parent_message_id` and receives a
   new `message_id`.
6. Unknown fields or unsupported schema versions are rejected.
7. Numeric DNP3 points carry declared scaling and range metadata in the frozen
   point map.
8. Command acceptance and physical realization are separate events.

## Minimum command types

- `connect_permit`
- `active_power_setpoint`
- `active_power_limit`
- `reactive_mode`
- `reactive_setpoint`
- `autonomous_curve`

The G4 pulse trace uses signed `active_power_setpoint` in kW and
`reactive_setpoint` in kvar. Other types stay disabled until their component
tests pass or are explicitly enabled in the frozen point map.

## Minimum telemetry types

- `terminal_voltage`
- `frequency`
- `active_power`
- `reactive_power`
- `state_of_charge`
- `connection_state`
- `quality`

## Example command

```json
{
  "schema_version": "0.1",
  "kind": "command",
  "message_id": "run-0042-controller-000017",
  "event_time_s": 180.0,
  "source": "ev_controller_v3",
  "target": "DER_EV4_BESS",
  "sequence": 17,
  "type": "active_power_limit",
  "payload": {
    "value": 0.75,
    "unit": "pu",
    "valid_until_s": 190.0
  }
}
```
