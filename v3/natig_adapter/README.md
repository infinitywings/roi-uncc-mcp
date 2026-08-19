# G4 NATIG adapter boundary

This directory freezes the endpoint and point-map contracts for the G4
one-DER benign-equivalence gate. It does not claim that stock NATIG already
implements the adapter, and it contains no attack execution evidence.

`endpoint_graph.json` defines exactly four global cyber-message endpoints:

```text
controller/der_ev4
  <-> natig/cc_der_ev4
  <-> natig/der_ev4
  <-> gateway/der_ev4
```

The middle hop is DNP3 over ns-3. The outer hops are HELICS messages. Physical
coupling is a separate HELICS-value plane: GridLAB-D publishes terminal
voltage to the gateway, and the gateway publishes the OpenDER-derived complex
load to GridLAB-D. GridLAB-D owns no message endpoint. Direct
controller-to-gateway, NATIG-to-GridLAB-D, and cyber-message-to-physical-value
edges are forbidden.

## Stock G1 endpoint debt

The pinned G1 configuration is not this contract. Its GridLAB-D configuration
contains 117 routes to an undeclared `CC/Monitor`; each successful run logged
2,223,117 dropped messages. NATIG also registered the unused `fout` endpoint
and a special `trip_shad_inv1$Pref` endpoint. The G4 graph excludes all three
names instead of hiding the debt behind a dummy sink. Stock NATIG's outstation
callback also targets `GLD/...` directly, which must be replaced by the
gateway-only edge before any end-to-end G4 run.

`POINT_MAP_AUDIT.md` documents the source audit behind the minimal DNP3
contract. The frozen map permits only AO0 active kW and AO1 reactive kvar as
G41V1 signed-int32 commands at 0.001 engineering unit/count. AI0-AI3 are
G30V5 float32 engineering values for active power, reactive power, terminal
voltage, and state of charge. BI0/BI1 are separate G1V2 Boolean points for
connected and gateway command acceptance. `dnp3_codec.py` consumes that same
validated map for AO, AI, and BI metadata; it does not maintain a second
point-assignment table.

`gateway_bridge.py` is the explicit trust boundary missing from the stock
transport. A fixed authenticated master/outstation binding supplies identity;
SELECT creates a deterministic local transaction and OPERATE must carry the
exact same station, point, and G41V1 object body. The bridge never treats a
DNP3 command status byte as gateway or device acceptance.

## Pinned-source overlay

`patches/0001-grideval-g4-gateway-overlay.patch` is owned by v3 and leaves
`v3/deps/natig-src` untouched. It narrows the compiled outstation path to one
G41V1 AO0/AO1 object, status zero, and exact SELECT-before-OPERATE
correlation. It disables the generic AO/BO-to-GLD mapper, sends opaque events
only to `gateway/der_ev4`, fixes signed G41V1 decoding, and makes G30V5
float32 serialization/deserialization explicitly little-endian.

The decoder path is checked for initialized byte assembly. In the pinned
source, a commented-out `throw` accidentally made each first assignment the
body of an undersize `if`, so valid buffers skipped initialization. The
overlay repairs all five `removeUINT8/16/24/32/48` primitives with an explicit
undersize return, deterministic initialization, and widened operands before
shifts. This directly covers G1V2 through `removeUINT8`, G41V1 through
`removeINT32`/`removeUINT32`, and G30V5 through
`removeFloat`/`removeUINT32`.

The pinned checkout mixes CRLF and LF source files. Always use
`apply_overlay.py`: it verifies commit `e163b350...`, tree `9f10cb55...`, a
clean tracked worktree, and six byte-level file digests before invoking Git
with the required line-ending accommodation. Check-only is the default:

```bash
python3 v3/natig_adapter/apply_overlay.py \
  --source v3/deps/natig-src

# Apply only to a disposable build copy, never the pinned dependency:
python3 v3/natig_adapter/apply_overlay.py \
  --source /path/to/disposable/natig-build-source --apply
```

`overlay_protocol.py` validates the C++ callback JSON and reconstructs the
five-byte G41V1 body for `gateway_bridge.py`. It also builds the exact return
telemetry shape: four ordered analog values and two ordered Boolean values.
`overlay/points_der_ev4.csv` supplies the corresponding NATIG static-poll
order (AI0-AI3 then BI0-BI1).

## Executed offline conformance

`run_offline_conformance.py` compares two independent real OpenDER instances:

1. semantic envelope → gateway → OpenDER; and
2. G41V1 codec → bridge → gateway → OpenDER.

The canonical create-once `offline_conformance_r2` evidence passes two exact
840-second repeats of the G3 pulse schedule. All 18 SBO commands per path were
selected, accepted, queued, and applied at the next one-second device step;
P/Q/SOC differences were zero, and 5,040 G30V5/G1V2 telemetry roundtrips met
their bounds. This is offline adapter conformance, not live NATIG equivalence.

The overlay and its hostile tests are not evidence of live NATIG equivalence.
The next live step is to apply it in the locked disposable build context, build
NATIG, and run the benign one-DER schedule over HELICS/ns-3/DNP3. Until that
run completes, only offline adapter conformance and clean patch applicability
are established.

`analyze_live_equivalence.py` implements the subsequent, separate post-run
gate. It requires complete normalized traces from both direct-reference and
NATIG executions, checks the exact 840-second/18-operation schedule and
application lineage, and only then compares P, Q, voltage, SOC, and latency.
See `live_benign/EQUIVALENCE_TRACE_CONTRACT.md`. Its synthetic tests are
analyzer validation, not live-equivalence evidence.

`normalize_g3_direct_reference.py` performs a create-once, byte-pinned
projection of the independently executed G3 pulse/coupling-10 artifact into
that schema. The current result and its observed-versus-derived provenance are
in `direct_reference_r1/`. This normalization launched no process and is not a
new direct-reference run.

## Offline validation

Run the contract validator and optionally inspect one or more physical
GridLAB-D HELICS configurations:

```bash
python3 v3/natig_adapter/validate_endpoint_graph.py
python3 v3/natig_adapter/validate_endpoint_graph.py \
  --gridlabd-config path/to/gridlabd-config.json
```

The tests use the Python standard library and remain compatible with pytest:

```bash
python3 v3/natig_adapter/tests/test_endpoint_graph.py -v
pytest -q v3/natig_adapter/tests/test_endpoint_graph.py
pytest -q v3/cyber_gateway/tests v3/natig_adapter/tests
python3 v3/natig_adapter/run_offline_conformance.py
```
