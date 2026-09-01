# Provenance correction: legacy L5b information condition

The preserved file
`v3/g7_condition_freeze/20260830_r1/formal_uninformed/g7_l5b_search.py`
has SHA-256
`748f284fe7b90b25b8aea1328cbc72626a0dd0cf1f266720081bc33cdcfba4fb`.

Its system prompt states that benign behavior self-alarms around a particular
late-run window. Consequently, the five-episode adaptive result is uninformed
about the exact optimum only in a limited sense; it is informed about the
empirical alarm horizon. It must be labeled:

`horizon_informed_exploratory`

It must not be pooled with, substituted for, or described as the clean
confirmatory-uninformed condition. Frozen bytes and original artifacts remain
unchanged. The new condition is defined by
`prompts/clean_uninformed_v1.json` and is guarded by a fail-closed audit.

RKA provenance:

- PI protocol: `jrn_01M1ASCBF12HW9V1HXQG6N68J8`
- correction finding: `jrn_01M1ASCF8GTKWCEC9NRM1JCTMB`
- decision: `dec_01M1ASCY6S3KSPA2BNZ4JB8S8A`
- mission: `mis_01M1ASETDXKSC8CDNNPE49ZW1D`
- Phase 0–1 gate: `chk_01M1ASKZXKM4FC0VCDV8Z6SNY8`

