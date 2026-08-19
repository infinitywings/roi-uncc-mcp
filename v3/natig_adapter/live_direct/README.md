# G4 live direct-reference arm

This arm removes NATIG from the command and telemetry path while preserving
the canonical IEEE 123-bus GridLAB-D model, the EV4 OpenDER wrapper, HELICS
timing, pulse schedule, and gateway policy. It is a paired live control arm,
not a replacement for the NATIG run.

The controller sends the exact semantic schedule directly to
`gateway/der_ev4`. The gateway validates every field, performs SELECT and
OPERATE at receipt through `CyberGateway`, advances the same one-second
OpenDER model inside the ten-second physical coupling loop, and returns
telemetry directly to `controller/der_ev4`.

The runner is create-once and permits only the immutable r24-derived image
manifest:

```bash
python3 v3/natig_adapter/run_live_direct.py \
  --output-dir v3/natig_adapter/live_direct_preflight_r1

python3 v3/natig_adapter/run_live_direct.py \
  --output-dir v3/natig_adapter/live_direct_run_r1 \
  --execute
```

Every successful execution records the exact image and package identities,
execution user, process return codes, staged-file inventory, and runtime-file
inventory in `live_direct_preflight.json`. The arm launches exactly three
federates (controller, gateway, GridLAB-D) plus their broker; it launches no
NATIG, attacker, or impairment process.
