-- DuckDB transformations that materialize the native report datasets from the
-- content-addressed M29-S analysis snapshot. Run from this artifact directory.

CREATE OR REPLACE TEMP VIEW m29s_analysis AS
SELECT *
FROM read_json_auto('analysis_snapshot.json');

CREATE OR REPLACE TEMP VIEW m29t_replay AS
SELECT *
FROM read_json_auto('../m29t_offline_replay_attempt1/replay_receipt.json');

CREATE OR REPLACE TEMP VIEW arm_outcomes AS
SELECT
    item.arm,
    item.arm_id,
    item.conditions,
    item.exact_rate,
    item.exact_successes,
    item.final_contract_violations,
    item.invalid_outputs,
    item.model_calls,
    item.split
FROM m29s_analysis,
UNNEST(arm_summary) AS rows(item);

CREATE OR REPLACE TEMP VIEW flat_constructs AS
SELECT
    item.cells,
    item.construct,
    item.exact_rate,
    item.exact_successes,
    item.split
FROM m29s_analysis,
UNNEST(construct_summary) AS rows(item)
WHERE item.interface = 'Flat LLM';

CREATE OR REPLACE TEMP VIEW heldout_slots AS
SELECT
    item.cells,
    item.exact,
    item.exact_rate,
    item.slot
FROM m29s_analysis,
UNNEST(flat_slot_summary) AS rows(item)
WHERE item.split = 'Held-out';

CREATE OR REPLACE TEMP VIEW interface_contrasts AS
SELECT
    item.contrast,
    item.discordant_pairs,
    item.flat_arm,
    item.flat_wins,
    item.staged_arm,
    item.staged_wins,
    item.ties,
    item.two_sided_exact_sign_p
FROM m29s_analysis,
UNNEST(pooled_interface_contrasts) AS rows(item);

CREATE OR REPLACE TEMP VIEW staged_failures AS
SELECT
    item.cells,
    item.failure_category,
    item.share
FROM m29s_analysis,
UNNEST(staged_final_failure_summary) AS rows(item);

CREATE OR REPLACE TEMP VIEW headline AS
SELECT
    0.3125::DOUBLE AS best_llm_heldout_rate,
    0.75::DOUBLE AS deterministic_heldout_rate,
    1.0::DOUBLE AS oracle_heldout_rate,
    0.0::DOUBLE AS staged_valid_program_rate,
    model_calls
FROM m29s_analysis;

CREATE OR REPLACE TEMP VIEW offline_headline AS
SELECT
    0.46875::DOUBLE AS flat_o2_heldout_rate,
    0.5::DOUBLE AS staged_o3_heldout_rate,
    0.3125::DOUBLE AS staged_o5_heldout_rate,
    new_model_calls
FROM m29t_replay;

CREATE OR REPLACE TEMP VIEW recovery_ladder AS
SELECT
    CASE WHEN item.split = 'development' THEN 'Development' ELSE 'Held-out' END AS split,
    CASE WHEN item.interface = 'flat' THEN 'Flat' ELSE 'Staged' END AS interface,
    concat(
        CASE WHEN item.split = 'development' THEN 'Development' ELSE 'Held-out' END,
        ' · ',
        CASE WHEN item.interface = 'flat' THEN 'Flat' ELSE 'Staged' END
    ) AS series,
    stage.stage,
    stage.exact_successes,
    stage.semantics_exact,
    item.cells,
    stage.exact_successes::DOUBLE / item.cells AS exact_rate
FROM m29t_replay,
UNNEST(summary.by_split_interface) AS rows(item),
LATERAL (VALUES
    ('O0 Recorded', item.O0_recorded.all_slot_exact, item.O0_recorded.semantics_exact),
    ('O1 Saved JSON', item.O1_saved_json.all_slot_exact, item.O1_saved_json.semantics_exact),
    ('O2 Canonical arrays', item.O2_canonical_arrays.all_slot_exact, item.O2_canonical_arrays.semantics_exact),
    ('O3 Tool ledger', item.O3_tool_ledger.all_slot_exact, item.O3_tool_ledger.semantics_exact),
    ('O4 Tool projection', item.O4_tool_projection.all_slot_exact, item.O4_tool_projection.semantics_exact),
    ('O5 Ledger + projection', item.O5_tool_ledger_projection.all_slot_exact, item.O5_tool_ledger_projection.semantics_exact)
) AS stage(stage, exact_successes, semantics_exact);

CREATE OR REPLACE TEMP VIEW audit_trace AS
SELECT *
FROM (VALUES
    ('Execution contract', 'm29sexec_ec8d30b7ac3f5156b189769e35f6bc08a6369c755414b3c297b16d008dab78c5', 'Bound', 'Attempt 4 plan and sources fixed before execution'),
    ('Primary receipt', 'm29sprimary_9dfa32e6a78a367746a90d47b73c6cf4d2ec80cea35fe8cc5af364963d12aca9', 'Passed; not proposal-eligible', 'Execution valid, scientific qualification gates not met'),
    ('Original independent audit', 'm29saudit_86b95385559a3a50e1794ab4cf042b3916279b49fe1274e8ed3ecdaf39cf6cfd', 'Failed; preserved', '204 metric discrepancies caused by auditor-side array sorting'),
    ('Independent audit addendum', 'm29sauditadd_563d4c98c9b80282537c88f1aa5d96ac9faffa88b47f28cdf80d7695e272928e', 'Passed', 'Zero issues; frozen evidence unchanged; no calls repeated')
) AS rows(artifact, identifier, status, interpretation);
