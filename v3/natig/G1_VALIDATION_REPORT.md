# G1 NATIG IEEE-123 Validation Report

## Verdict

G1 establishes a bounded, public-source NATIG IEEE-123/DNP3 component proof,
but it does **not** pass the full locked-build or exact-reproducibility gate.
The upstream-source image built successfully, and the no-attack federation
completed twice with all 36 runtime assertions true. The two runs used the
same resolved image, embedded source tree, effective configuration, and seed.
They produced identical DNP3 packet traces and equal event counts, but 30 of
52 normalized artifact hashes differed because GridLAB-D physical CSV values
varied at small floating-point scales.

This result is sufficient to start the independent one-device OpenDER physical
adapter (G3). It is not sufficient for benign network equivalence (G4), attack
testing, or a claim that NATIG is bit-reproducible.

## Frozen identities

- NATIG source commit:
  `e163b350e243c6386477e35dead979a4cb2b7c60`
- NATIG source tree:
  `9f10cb55d5eaa4c20a95f292b84a266e9992bc1a`
- built image ID:
  `sha256:662e1ae46656de8a97195d7a6a6f7cfef84bd0baa997fedbea859e9d76978f7c`
- image size: 14,720,872,662 bytes
- no-attack `grid.json` SHA-256:
  `1c5e5abcf97ded95cdfb19c0391f4fb21deea10d27706b62b51749f77f655a8c`
- v3 federation wrapper SHA-256:
  `9e190e52b4e3f57ae9fd7f2a82e3a25c889d366e5845623c998fc63b75165483`

The source audit repeated byte-identically in `upstream_audit_r5` and
`upstream_audit_r6`. The benign overlay repeated byte-identically in
`benign_overlay_r5` and `benign_overlay_r6`.

## Build result

The unchanged upstream Dockerfile completed in 2,637.37 seconds. This proves
current toolchain compatibility, not a fully immutable construction. The
Dockerfile reclones NATIG HEAD and several base images, repositories, branches,
and archives are not content-pinned. The exact public dependency resolutions
and the repair requirements are frozen in `locked_dependencies.json` and
`DEPENDENCY_LOCK.md`. A v3 locked Dockerfile remains required before G4.

The published PNNL binary image was independently inspected and rejected as an
execution fallback. It embeds an older 2023 source revision and lacks a
working current IEEE-123 launch/runtime combination.

## Runtime experiments

The published IEEE-123 preset is attack-enabled. The v3 overlay disables all
MITM applications, DDoS activation, and the dynamic-route controller while
retaining the 20-second duration, 10-second DNP3 poll period, topology, and
network seed 777. NATIG's native benign direct analog command
`point 0 = -16` at 3.005 seconds remains; therefore these are no-attack runs,
not no-command runs.

The first retained execution (`benign_ieee123_r1`) exposed an upstream launcher
failure: `waf configure` failed, the shell continued, and the launcher did not
return a truthful aggregate status. The run was stopped and preserved with
return code 137 and `success=false`.

The v3 wrapper launches the broker, GridLAB-D, and the already-built ns-3
program directly and requires every child return code. Two create-once runs
then completed:

| Measure | Run r2 | Run r3 |
|---|---:|---:|
| Runner assertions | 36/36 | 36/36 |
| Elapsed wall time | 182.54 s | 181.63 s |
| DNP3 packet records | 38,514 | 38,514 |
| ns-3 master read events | 31,024 | 31,024 |
| Active recorder files | 38/38 | 38/38 |
| Minimum/maximum recorder span | 20.0/20.0 s | 20.0/20.0 s |
| Attack/reset markers | 0 | 0 |
| Normalized artifacts | 52 | 52 |

The DNP3 trace `dnp3_perf.txt` is byte-identical between runs with SHA-256
`da73f333cd3ae03d1176bc4ea8901e866f91bc19deb0ad89fc8b37d29fe86e92`.

## Reproducibility audit

The strict comparison fails: 30 of 52 normalized hashes differ, so the runs
must not be called byte-reproducible. A separate post-hoc diagnostic compared
all 38 physical CSV files structurally and numerically. Polar values were
converted to Cartesian vectors so arbitrary angles on near-zero magnitudes did
not create false divergences.

- all 38 file structures, row keys, and row counts agree;
- 1,425,150 polar cells and 485,988 unequal scalar cells were evaluated;
- maximum component absolute difference: `5.3088e-06`;
- maximum physical/vector absolute difference: `6.50001e-05`;
- maximum scaled component difference: `3.10843e-06`;
- zero differences exceed the explicitly post-hoc rule of absolute error
  `<=1e-4` **or** scaled error `<=1e-6`.

This supports approximate numerical repeatability only. The threshold was
selected after observing the byte mismatch and is frozen solely as a
diagnostic for future G1 repetitions; it is not a preregistered G4 equivalence
tolerance.

## Carried blockers

1. A locked NATIG container has not yet been built from the frozen dependency
   inventory.
2. Each successful run logged 2,223,117 HELICS drops to undeclared
   `CC/Monitor` destinations. DNP3 traffic and all four regional read paths
   still completed, but the auxiliary endpoint topology is not clean.
3. NATIG's upstream example does not capture a PCAP file; `dnp3_perf.txt`
   supplies deterministic packet-event evidence but is not a wire capture.
4. The native benign command is hard-coded in the ns-3 model and has not yet
   been mapped to an OpenDER semantic point.
5. No payload-modification or attacker-effect experiment was executed.

Items 1–4 must be resolved or explicitly replaced by a validated adapter
before G4 can pass. Item 5 remains intentionally blocked until benign
end-to-end equivalence succeeds.

## Next authorized experiment

Proceed with G3 at EV4/l92: create a v3-only feeder copy, deactivate the legacy
storage owner, connect exactly one pinned OpenDER BESS through a signed P/Q
adapter, and run deterministic positive/negative P and Q pulses at 1, 5, 10,
and 60-second coupling steps. NATIG remains outside that first physical-loop
test so device/feeder errors can be isolated before the cyber gateway is
introduced.
