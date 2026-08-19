# NATIG G1 lineage / G4 toolchain dependency lock

The immutable identities used for the bounded 3G/IEEE-123 proof are recorded
in `locked_dependencies.json`. The lock deliberately excludes 5G-LENA, Java,
and the repository's historical `patch/helics-backup`; none is required for
G1.

The current locked Docker recipe is a G4-patched NATIG **compiled toolchain
base**, not a live-ready G4 image. It installs the audited experiment
executable at `/usr/local/bin/grideval-natig-g4` and preserves self-contained
Git identity for the live admission interface, but the derived image must add a locked
Python runtime containing importable HELICS 2.7.1 bindings and OpenDER 2.2.0
with its numeric dependencies.

## Locked construction

- build only for `linux/amd64` from the architecture-specific Python 3.6 image
  digest;
- consume the audited NATIG checkout through a self-contained depth-one local
  clone rather than cloning repository HEAD; retain its original HEAD/tree and
  assert the staged G4 overlay tree for live image admission;
- fetch HELICS 2.7.1, GridLAB-D 4.3, the locked ns-3 revision, and helics-ns3 by commit and
  assert each resulting tree;
- retain reconstructed helics-ns3 tree `6f17d114...` as G1 lineage and assert
  G4's separately reconstructed patched tree `3d745193...`;
- fetch every source archive over authenticated HTTPS and verify SHA-256
  before extraction;
- replace mutable Debian mirrors with a dated snapshot, pin direct package
  versions, and retain `dpkg-query` output;
- disable HELICS git/submodule mutation during configure and verify its gitlink
  identities;
- inline only the required 3G ns-3 patch/configure steps rather than running
  `build_ns3.sh`, which deletes and reclones its checkout;
- disable ns-3 tests, unused examples, and MPI for the G1 runtime, and replace
  optimized-profile `-march=native` with an explicit portable amd64 target;
- set `SOURCE_DATE_EPOCH=1757796209`, UTC, and a fixed locale.

## Important distinction

`HELICS-v2.x-waf` is presently obtainable as a public lightweight tag at
commit `11e91ab...`. The upstream clone is therefore compatible today, but it
does not assert the immutable identity. This is a lock defect, not a missing
dependency.

The pinned PNNL binary image is a separate 2023 source revision and is not a
current-source build substitute. Its toolchain may be used as historical
evidence only.

## Scientific configuration

The native `3G-conf-123` preset is attack-enabled. G4 uses a derived,
create-once overlay with MITM, DDoS, and the dynamic route controller disabled.
The upstream hard-coded direct-analog command at 3.005 seconds is removed.
All live controls must traverse the frozen controller -> NATIG DNP3
SELECT/OPERATE -> gateway -> OpenDER path. The effective configuration,
launcher, network model, point files, and feeder models must all match the
frozen hashes before a run can pass.
