# M29-A independent audit plan

## Independence boundary

The independent auditor will be implemented in
`g7confirm/m29_independent_audit.py`. It may use only the Python standard
library and must not import `m29_hybrid_contract`, `m29_counterfactual`, the
primary verifier, controller implementations, or optimizer implementation.
It reads immutable JSON bytes and named source files directly.

## Required recomputations

The auditor must independently:

1. reject duplicate JSON keys, non-finite numbers, unexpected files, and schema
   or identity drift;
2. recompute the design contract ID and every source SHA-256;
3. verify the exact five-arm factor matrix and four registered contrasts,
   including the deferred status of the critic contrast;
4. verify that `IA3-O` and `IA4-H` bind the same optimizer source, candidate
   surface, constraints, history, feedback, and environment-query cap;
5. verify that `IA4-H` and `IA4-HG` differ only in the registered
   representation factor and carry the same semantic digest;
6. verify exactly eight mirrored intervention classes and sixteen unique
   condition IDs with preregistered expectations;
7. recompute each arm/condition endpoint from terminal receipts, including
   typed-request validity, tool/strategy selection, validity compliance,
   switching, regret, extrapolation, refusals, invalid proposals, and effective
   decisions;
8. recompute model, optimizer, read-only-tool, environment-query, wall-time,
   and decision accounting as separate quantities;
9. verify every effective decision has a common-validator admission record;
10. scan all receipts for prohibited access and require false/empty seals for
    Docker, simulator, detector, defense, embedding, physical actuation,
    evaluation records, and seeds `9101` through `9112`; and
11. compare its canonical endpoint table byte-for-byte with the primary
    endpoint table.

## Source-drift policy

Any missing source, hash mismatch, unregistered factor, altered expectation,
silent retry, overwritten attempt, prohibited access flag, or endpoint mismatch
is an issue. The auditor returns a non-empty `issues` array and the gate cannot
pass. Warnings cannot downgrade an issue.

## Claim boundary

An empty issue list may support only development evidence about protocol
competence, typed compilation, scoped tool use, validity compliance, and
evidence-conditioned switching. The auditor must reject report metadata that
authorizes LLM superiority, physical harm, stealth, detector evasion,
generalization, confirmatory inference, or M29-B execution.
