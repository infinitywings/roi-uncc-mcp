# NATIG G1 public-build proof

This directory holds create-once build and benign-example evidence for pinned
NATIG commit `e163b350e243c6386477e35dead979a4cb2b7c60`.

The first attempt always uses the upstream Dockerfile unchanged. Failures are
retained. Any reproducibility repair is implemented as a separate v3-only
Dockerfile and must pin every repository, base image, and downloadable
archive; it must not overwrite upstream source.

G1 is a component proof only. It does not connect NATIG to OpenDER or the
GridEval federation and does not execute an attacker-effect experiment.

## Upstream audit

`audit_upstream.py` independently records the pinned commit/tree, hashes the
build and launch files, and checks known reproducibility hazards. Its
create-once runs detect all ten declared conditions: one critical, six high,
and three medium. Each audit generation is compared byte-for-byte before it is
admitted to the G1 manifest.

The critical issue is that the upstream Dockerfile clones NATIG HEAD inside the
image instead of using the audited checkout. Other high-severity conditions
include mutable or unauthenticated dependencies and an ns-3 HELICS adapter
cloned by tag without an exact-commit assertion. Therefore a successful upstream
build is useful compatibility evidence but cannot by itself satisfy the pinned
reproducibility gate.

The upstream Docker launcher also returns immediately outside its `RC` mode
and ends with unconditional `exit 0`. G1 uses `run_benign_ieee123.py`, which
selects `RC` only to wait for every child, then independently validates
configuration, output logs, process termination, and artifact hashes.

## No-attack configuration

The published `3G-conf-123/grid.json` is not a benign preset. It enables three
MITM applications with attack types, target points, probabilities, and active
windows from simulation second 1 through 20.

`make_benign_overlay.py` creates a v3-only overlay and manifest without editing
the pinned source. It changes only:

- `Simulation[0].includeMIM`: `1` to `0`;
- `DDoS[0].Active`: forced to `0` (already zero upstream);
- `Controller[0].use`: forced to `0` (already zero upstream).

The 20-second duration, 10-second DNP3 polling period, topology, and network
seed 777 remain unchanged. Two generated overlays are byte-identical with SHA
`1c5e5abc...`.

The runtime container uses Docker network mode `none`; all HELICS traffic stays
on its loopback interface and all communications traffic is simulated inside
ns-3. A launcher return code is never accepted as sole success evidence.

## Public binary image audit

PNNL's public image resolves to immutable digest
`sha256:3377d75a211729d2a878fffaa183010c5047fa7182efc2de9102df59d8b1c6b3`,
but it is not a current G1 execution fallback. It embeds clean NATIG commit
`2aafee9...` from 2023 rather than the pinned 2025 source. Its generic launcher
selects 5G/IEEE-9500, its IEEE-123 launcher requires absent MPI executables, its
active configs are for the large feeder, and it contains no built ns-3
libraries. No federation was started from this image. It is retained only as
historical toolchain evidence.

See `DEPENDENCY_LOCK.md` and `locked_dependencies.json` for the source-based
immutable construction.

## Execution result

The upstream-source image built successfully as
`sha256:662e1ae46656de8a97195d7a6a6f7cfef84bd0baa997fedbea859e9d76978f7c`.
One preserved upstream-launch attempt failed because the script ignored a
failed `waf configure`. The v3 wrapper then completed two clean 20-second
no-attack runs (`benign_ieee123_r2` and `r3`) with 36/36 assertions, 38/38
recorders, 38,514 DNP3 packet records, and 31,024 master read events in each.

`compare_benign_runs.py` compares normalized physical/configuration/DNP3 hashes
while excluding only GridLAB-D wall-clock metadata headers. The exact check
fails because 30/52 hashes differ; this is retained as a reproducibility
failure. `analyze_numeric_reproducibility.py` separately performs a clearly
post-hoc, vector-aware numerical diagnosis. The physical CSV structures agree,
and all differences fit its frozen diagnostic rule of absolute error `<=1e-4`
or scaled error `<=1e-6`.

Both successful runs also contain 2,223,117 HELICS drops to undeclared
`CC/Monitor` destinations. This does not erase the completed DNP3 exchanges,
but it blocks any clean end-to-end topology claim. See
`G1_VALIDATION_REPORT.md` for the bounded verdict and carried blockers.
