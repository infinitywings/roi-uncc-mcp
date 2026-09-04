# M29-S frozen execution protocol

Plan-validation gate `chk_01M1PNY0YBT8K26DEW6CK0E838` is `GO` for M29-S
implementation and bounded execution-contract preparation. It does not open
M29-B. The approved plan evidence is Attempt 2 contract
`m29scontract_2718c430056e1314ec36f107feb2ca1ec160e2d430b0bc94bb4d527ecc922fe0`
and independent plan-audit receipt
`m29splanaudit_df21393fa47ffe702a9b03443939cdb6f2b6c8d88c868e9abd7bfafa9fb04de7`.

## Runtime components

`g7confirm/m29s_campaign.py` implements:

- physically separate, content-addressed development and held-out packets;
- a commitment file that binds the held-out packet without requiring the
  development runner to load held-out bytes;
- read-only identity probes for the existing qwen LLM and existing GPU
  embedding service;
- split-specific frozen-corpus embedding and cosine top-4 selection;
- feedback-matched first requests, paired random seeds, two-call causal arms,
  and one-call descriptive references;
- value-free validator feedback and exactly one non-retrying revision;
- local schema validation plus deterministic, non-repairing staged
  projection;
- interleaved condition-level execution schedules;
- create-once cells, split receipts, a development freeze, and a final primary
  receipt; and
- a source-bound execution contract that must pass before any chat call.

`g7confirm/m29s_independent_audit.py` imports neither the runner nor the
semantic compiler. It independently reconstructs request parity, content
addresses, source hashes, staged projection, endpoint scores, call totals,
validator non-leakage, service lineage, and access seals from serialized
artifacts. It runs before the primary receipt so its verdict can enter the
registered mechanism gate.

## Split sequence

1. Generate separate development and held-out packets plus one hash
   commitment from the plan-gated design fixture.
2. Probe service identities without lifecycle changes or LLM chat calls.
3. Embed each frozen split corpus and query set with the registered existing
   GPU embedding model.
4. Register an execution contract binding all source bytes, artifact hashes,
   service identities, prompts, schedules, and the 576-call maximum.
5. Execute the development split with exactly 288 requests.
6. Freeze its 192 cells, split receipt, source hashes, and prompt-bearing
   requests.
7. Execute held-out only if the development freeze and original execution
   contract still verify byte-for-byte. No adaptation is permitted.
8. Run the non-importing independent audit, then issue the primary receipt.

A defect found after development begins requires a new create-once attempt.
There is no retry, overwrite, repair, or prompt-tuning path within an attempt.

## Access and claim boundary

The only network operations are read-only model discovery, embedding, and
offline chat completion. The runner never accesses Docker, HELICS, OpenDER,
GridLAB-D, a simulator, detector, defense, network impairment, physical
actuation, final-evaluation records or seeds, or RKA governance as attacker
context. A passing mechanism gate permits only a proposal for a later offline
complementarity study and cannot promote any confirmatory or physical claim.
