# M29-S Report Source Notes

## Reporting job

- Audience: technical research team and PI.
- Decision: determine whether the next attacker architecture should rely on a stronger LLM, a different interface, deterministic tools, or a combination.
- Scope: Attempt 4 PRELIMINARY_ONLY evidence. No M29-B, final evaluation, simulator, detector, defense, or operational red-team claims.
- Delivery surface: one portable HTML report generated from `report_artifact.json`.

## Source inventory

| Source | Role |
| --- | --- |
| `report_source.sql` | DuckDB transformations that materialize every native card, chart, and table dataset from the M29-S analysis and M29-T replay |
| `analysis_snapshot.json` | Canonical reproducible aggregation and content-addressed analysis ID |
| `../m29t_offline_replay_attempt1/replay_receipt.json` | Content-addressed zero-call replay over all saved LLM responses |
| `../m29t_offline_replay_attempt1/independent_audit.json` | Independent recomputation of every replay stage and summary |
| `primary_receipt.json` | Bound execution result and scientific qualification state |
| `development_receipt.json` | Development split outcomes and call accounting |
| `held_out_receipt.json` | Held-out split outcomes and call accounting |
| `independent_audit_addendum.json` | Clean append-only independent verification over saved evidence |

The immutable original audit failure is retained in `independent_audit_receipt.json`. The addendum explains and corrects the auditor-side order mutation without modifying frozen evidence or repeating model calls.

## Chart map

| Report section | Analytical question | Chart | Encodings | Takeaway | Palette |
| --- | --- | --- | --- | --- | --- |
| Arm outcomes | How does exact performance vary by interface and support mechanism? | Grouped horizontal bar | Arm, exact successes, split | Flat LLM arms reach 4–5 held-out successes; staged arms remain at zero; deterministic and oracle controls establish headroom | Categorical |
| Staged failure taxonomy | Why did the staged interface fail? | Horizontal bar | Failure category, cells | Ledger ordering and slot-program projection explain 120/128 failures; length explains 8/128 | Sequential |
| Construct heterogeneity | Is flat-interface performance uniform across evidence tasks? | Grouped horizontal bar | Construct, exact rate, split | Success is concentrated in authority, topology, and split-specific tasks; delayed state and constraint tasks remain unsolved | Categorical |
| Held-out slots | Which fields should tools own first? | Sorted horizontal bar | Semantic slot, exact rate | Target selection is weakest; several state and objective fields also trail simple scalar constraints | Sequential |
| Zero-call recovery | Which mechanical intervention recovers exact success? | Ordered line | Replay stage, exact rate, split/interface | Canonicalization helps flat outputs; a tool-owned ledger rescues staged outputs; forced slot projection regresses them | Categorical |

All charts are native artifact charts and cite the analysis snapshot. The HTML builder may embed verified static SVG fallbacks when a browser is available.

## Required technical-report structure

The report follows: exact title, technical summary, major finding, supporting evidence, definitions and scope, methodology, independent audit, limitations, recommended next steps, and further questions. A full arm-level table supports detailed review.

## Interpretation guardrails

- `ready` describes snapshot availability, not confirmatory claim approval.
- Pooled exact sign tests are descriptive sensitivity analyses, not registered confirmatory estimands.
- Small 16-condition split samples make one-success differences weak evidence.
- The frozen exact metric treats selected arrays as order-sensitive; offline canonicalization is required to separate representation errors from semantic errors.
- A stronger model remains a later factor. The replay supports tool-owned state and constraint enforcement, but specifically rejects forced projection from the old redundant semantic-slot object.
