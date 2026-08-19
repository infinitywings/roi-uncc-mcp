# Locked NATIG G4 build

This recipe produces the **G4 locked NATIG toolchain base**, not a live-ready
G4 experiment image. It deliberately does not claim to satisfy
`run_live_benign.py`: a derived locked image still needs one Python runtime
containing importable HELICS 2.7.1 bindings, OpenDER 2.2.0, and its numeric
dependencies, followed by a complete immutable live-image manifest.

This directory owns the replacement for NATIG's mutable upstream Docker path.
It never edits `v3/deps/natig-src` and never clones NATIG inside the image.
`prepare_context.py` verifies the pinned checkout, verifies the reviewed G4
applicator and patch by SHA-256, applies them to a disposable depth-one clone,
asserts the resulting Git tree, removes the local-source remote, retains a
self-contained one-commit Git object set for live admission, normalizes
mtimes, and writes a byte manifest for every exported NATIG and Git-metadata
file except `.git/index`. Git can refresh the index's stat/cache-tree bytes
during read-only inspection, so its content is admitted separately by the
locked `git write-tree` result. The validator requires that this is the only
semantic-only file and rejects any unaccounted exported path.
`run_locked_build.py` repeats that complete validation immediately before
Docker admission. The Dockerfile independently enumerates the copied NATIG
tree and rejects any path not covered by the byte manifest or the single
index-tree exception. It also copies the patched G4 main into ns-3 scratch
before configuration, compiles it, installs the resulting executable at
`/usr/local/bin/grideval-natig-g4`, and rejects a missing executable.

The Dockerfile fails closed on:

- the architecture-specific base-image digest;
- two dated Debian snapshot InRelease digests, every direct package version,
  and the final installed package inventory;
- NATIG source commit/tree, G4 applicator/patch digests, and G4 result tree;
- all fetched Git commit/tree identities, the ns-3 tag object, and all ten
  HELICS gitlink commit/tree pairs;
- export of HELICS's pinned JsonCpp 1.9.2 static archive and matching headers,
  plus a GCC 8.4 smoke link that rejects any dynamic JsonCpp fallback;
- every downloaded source archive and the exact HELICS Apps wheel SHA-256;
- the reconstructed NATIG helics-ns3 overlay tree;
- application of the reviewed ns-3 portable-amd64 patch.

Create a fresh context (the output must not already exist):

```bash
python3 v3/natig/locked_build/prepare_context.py \
  --source v3/deps/natig-src \
  --lock v3/natig/locked_dependencies.json \
  --applicator v3/natig_adapter/apply_overlay.py \
  --overlay-patch \
    v3/natig_adapter/patches/0001-grideval-g4-gateway-overlay.patch \
  --output-dir /tmp/grideval-natig-g4-context-r1

python3 v3/natig/locked_build/validate_locked_build.py \
  --context /tmp/grideval-natig-g4-context-r1

docker build \
  --platform linux/amd64 \
  --no-cache \
  --progress=plain \
  --tag grideval/natig:g4-locked-base-r1 \
  /tmp/grideval-natig-g4-context-r1
```

This establishes dependency identity, not bit-for-bit image reproducibility.
BuildKit/engine identity, kernel/CPU scheduling, compiled binary determinism,
and the complete transitive Debian package list are not predeclared. The
transitive packages are constrained by immutable snapshots and captured after
installation in `/usr/local/share/natig-dpkg-inventory.tsv`. The resulting
image ID, package inventory, build log, and build-context manifest must be
preserved as G4 evidence before any live equivalence result can pass.
