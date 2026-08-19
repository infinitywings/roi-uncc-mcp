# v3/deps — pinned upstream dependencies (not vendored)

These upstream sources are **gitignored** and reconstructed on demand, so the
repo tracks the pinned commits (below) plus `fetch_deps.sh`, never the ~1GB of
upstream git history or the multi-GB build images.

| Dependency | Upstream | Pinned commit | Notes |
|---|---|---|---|
| NATIG   | https://github.com/pnnl/NATIG   | `e163b350e243c6386477e35dead979a4cb2b7c60` | ns-3.35 / DNP3 / HELICS 2.7.1 / GridLAB-D 4.3; IEEE-123 & 9500 |
| OpenDER | https://github.com/epri-dev/OpenDER | `fe7877c664bc6c5eb3832499bf05e0f1dd1825c8` | release 2.2.0 (IEEE-1547 PV/BESS behavior) |

Run `bash v3/deps/fetch_deps.sh` to populate `natig-src/`, `opender-src/`, and
build `opender-venv/`. The locked NATIG build recipe lives in
`v3/natig/locked_build/` (Dockerfile + patches + validators).
