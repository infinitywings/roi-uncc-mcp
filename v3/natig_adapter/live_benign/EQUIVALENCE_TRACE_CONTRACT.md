# G4 post-run equivalence trace contract

`analyze_live_equivalence.py` is a post-run gate. It does not launch HELICS,
normalize incomplete logs, or create missing lineage. Each independently
executed path must emit one normalized JSON trace with schema
`grideval-g4-equivalence-trace/1.0`.

The two input roles are `direct_reference` and `natig`. Each trace has exactly
these top-level fields:

```text
schema_version, path, execution, commands, applications, samples
```

`execution` must say `status: complete` and cover exactly `0..840` seconds.
`provenance` must identify nonempty hashed input artifacts, producer runner
and HELICS/OpenDER versions, normalizer identity, whether normalization was a
new execution (it must be false), observed versus derived fields, and
comparison qualifications.
The command array must contain exactly 18 accepted AO operations in canonical
order: AO0 then AO1 at 0, 60, 180, 240, 360, 420, 540, 600, and 720 seconds.
Every command carries a path-local unique `command_id` and `application_id`.
The 18 application rows must preserve the same schedule order and match those
two IDs, point, value, and unit exactly. This provides path-local
accepted-command-to-device-application lineage without requiring identifiers
to be identical between the direct and DNP3 paths.

Each trace must contain 84 physical rows at exactly 10, 20, ..., 840 seconds:

```text
time_s, p_kw, q_kvar, voltage_pu, soc_pu
```

Missing, extra, duplicated, reordered, non-finite, out-of-range, unaccepted,
or lineage-inconsistent rows fail the execution-evidence gate. Equivalence is
reported as `NOT_EVALUATED` in that case.

When both execution traces pass, the default numerical limits are:

| Quantity | Limit |
|---|---:|
| Active-power absolute difference | 0.001 kW |
| Reactive-power absolute difference | 0.001 kvar |
| Voltage absolute difference | 0.0001 pu |
| SOC absolute difference | 0.000001 pu |
| Maximum acceptance latency, either path | 10 s |
| Maximum application latency, either path | 12 s |
| Acceptance-latency difference between paths | 10 s |
| Application-latency difference between paths | 10 s |

Latency is computed from the frozen controller event time. Acceptance and
application timestamps must not precede that event. All limits are embedded
in the output report and can be overridden only through explicit CLI flags.

Example:

```bash
PYTHONPATH=. python3 v3/natig_adapter/analyze_live_equivalence.py \
  --direct-trace /evidence/direct_reference_trace.json \
  --natig-trace /evidence/natig_trace.json \
  --output /evidence/g4_equivalence_report.json
```

The output is create-once. A zero exit code and
`equivalence_claim_permitted: true` require both an execution `PASS` and an
equivalence `PASS`. Synthetic passing tests demonstrate analyzer mechanics
only; they are not experiment evidence and are never stored as live traces.

If producer HELICS versions differ, the analyzer requires the exact
cross-version qualification:

```text
cross-version HELICS comparison: direct_reference=<version>; natig=<version>
```

The current direct reference reports `3.6.1 (2025-02-24)` and the locked NATIG
runtime reports `2.7.1`. A future pass is therefore explicitly
cross-version-qualified and cannot be described as same-runtime replication.
