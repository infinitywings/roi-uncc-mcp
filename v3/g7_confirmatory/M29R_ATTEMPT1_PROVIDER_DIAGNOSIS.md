# M29-R Attempt 1 Provider Diagnosis

## Outcome

M29-R Attempt 1 is a retained provider-compatibility failure. It does not
support a scientific conclusion about LLM compilation, direct planning,
hybrid optimization, or retrieval.

All 48 registered LLM cells received HTTP 500 before the service reported any
prompt or completion tokens. The 48 deterministic cells completed, including
the independent oracle ceiling at 16/16. The reproducible primary receipt is
`m29rprimary_b65f11e837a51f6c116d96e6b5fc4c819b3692710c308fbaa4ffebaf85d1b026`;
the independent audit is
`m29raudit_71ffa8a13c9a07c54fc911d8f3ca318a18b7ee7234ff9b2a5680b7f6d16120cc`.

## Single-factor diagnosis

Five post-attempt probes were used only for provider diagnosis and are not
experimental cells:

1. Replaying one exact failed request returned HTTP 500 with an empty
   `InternalServerError` message.
2. A minimal chat request without structured output returned HTTP 200.
3. A minimal JSON-schema request returned HTTP 200.
4. The frozen complex schema paired with a minimal prompt returned HTTP 500.
5. The same complex schema with only `uniqueItems` removed returned HTTP 200.

This isolates the deployed structured-output compiler's handling of
`uniqueItems` as sufficient for the observed HTTP 500. The local
`StrategyProgram` validator already rejects duplicate targets, windows, and
evidence identifiers, so omitting this unsupported provider hint need not
relax the admitted semantic contract.

The successful fifth probe also ended with `finish_reason=length` after 640
completion tokens because thinking was enabled. Earlier qualified GridEval
Qwen integrations explicitly set
`chat_template_kwargs.enable_thinking=false`. Attempt 2 should restore that
provider setting without increasing the registered completion budget.

## Attempt 2 boundary

Attempt 2 may change only the provider-facing transport representation:

- recursively omit `uniqueItems` from the provider response schema;
- retain all uniqueness checks in the local validator;
- set `chat_template_kwargs.enable_thinking=false`;
- set `stream=false` and `n=1` explicitly.

Evidence bytes, corpus views, arm membership, condition membership, seeds,
optimizer implementation, independent oracle, common validator, endpoints,
and unlock thresholds must remain unchanged. Attempt 1 remains immutable.

## Authorization accounting

The conservative request count is 53 of the PI-authorized 100: 48 registered
Attempt 1 requests plus five diagnostic requests. The matched Attempt 2 battery
requires 48 additional requests, so execution requires a total ceiling of at
least 101. The design, implementation, tests, and fresh plan audit may proceed
offline before that one-request authorization gap is resolved.

All evidence remains `PRELIMINARY_ONLY`. M29-B, simulator access, detector and
defense access, physical actuation, final evaluation, and seeds 9101--9112
remain sealed.
