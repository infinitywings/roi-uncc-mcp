# G4 live benign overlay

This directory is a launch contract, not live-equivalence evidence.

`federation_contract.json` freezes four federates, the four-endpoint/six-edge
cyber path, two physical HELICS values, network seed 777, the canonical G3
EV4/l92 10-second physical overlay, and a one-second internal OpenDER step.
`gridlabd.json` deliberately has an empty `endpoints` list.

The default command is a create-once dry-run:

```bash
PYTHONPATH=. python3 v3/natig_adapter/run_live_benign.py \
  --output-dir v3/natig_adapter/live_benign_preflight_rN
```

Without an external manifest matching `image_manifest.schema.json`, it records
`BLOCKED_IMAGE_NOT_READY` and does not call Docker. Execution additionally
requires an immutable image ID; the frozen NATIG commit/tree; hashes for every
patch, runtime source, and binary; and one Python executable containing both
HELICS 2.7.1 bindings and OpenDER 2.2.0 with hashed module files. Neither
currently available host Python environment supplies HELICS, so host launch is
not a valid fallback.

Only an explicit `--execute --image-manifest ...` may launch. Before starting
the broker, controller, NATIG, gateway, or GridLAB-D, the runner verifies all
in-container identities. The first runtime-command argument must exactly equal
the path of the hashed binary; an unverified executable cannot be substituted.
The supplied manifest is retained byte-for-byte as
`live_image_manifest.json`; its SHA-256 and immutable image ID are recorded in
the preflight and execution identity for downstream normalization.
Afterwards, every process must return zero and every required output must be
new. Federate traces and logs must be nonempty; `broker.log` may be empty when
the HELICS 2.7.1 warning-only broker exits cleanly, in which case its zero
return code is the positive evidence. Any missing identity, endpoint, output, process result, or
forbidden attacker/impairment fails closed. Even a successful launch permits a
live-execution claim only, never a benign-equivalence claim.

After two independent runs produce normalized direct-reference and NATIG
traces, normalize the live create-once run with
`../normalize_natig_live_reference.py`, then use
`../analyze_live_equivalence.py` as the separate post-run gate.
The exact 840-second schedule, 18-operation lineage contract, 84 physical
samples, latency definitions, and tolerances are documented in
`EQUIVALENCE_TRACE_CONTRACT.md`. Raw completion alone is never promoted to
equivalence, and structurally incomplete traces are not numerically compared.
