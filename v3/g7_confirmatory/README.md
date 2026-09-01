# G7 confirmatory harness

This directory contains the Phase 0–1 fail-closed harness and its bounded,
derived runtime-integration layer for the G7 confirmatory replication. It does
**not** authorize or launch the full co-simulation campaign.

The harness provides:

- a preregistered experiment specification and machine-readable schema;
- a clean, horizon-uninformed LLM proposal prompt;
- static prompt-leakage auditing;
- strict OpenAI-compatible model discovery and proposal parsing;
- atomic window and apparent-energy budget enforcement;
- deterministic, equal-outer-budget campaign planning;
- create-once manifests and smoke artifacts;
- offline unit tests;
- an exact-path composition of the frozen runner with physical operating-point
  clock actuation, runner-owned dual-budget accounting, and a one-window hard
  cap;
- fail-closed seed partitioning and evaluation-seed isolation;
- exact paired benign/attack controlled-lineage validation;
- a create-once detector provenance audit that separates source/interface
  inventory from calibration and parameter readiness;
- a development-only IA0–IA3 orchestration contract with bounded strategy
  parameterization, composition, typed-tool auditing, IA3/IA4 capability
  parity, an explicit AI-V2 component matrix, a content-addressed shared
  search surface, and a fixture-only IA4 adapter; and
- a replayable M4 IA4 model-output boundary with two independently authorized,
  create-once completion receipts, strict model/surface/candidate binding, and
  no tool or simulator execution; and
- an offline M5 interactive state machine with exact read-only tool schemas,
  content-addressed fixture results, hard turn/tool/token caps, immutable
  terminal states, and a matched IA3 non-LLM control; and
- a bounded M6 two-turn model replay that requests the read-only interface,
  receives a harness-injected fixture without tool execution, and terminates
  through the common candidate and plan validator boundary; and
- a preregistered M7 mirrored counterfactual qualification over target-only
  symmetric candidates, with a matched IA3 control and a causal candidate-
  switching endpoint; and
- an offline M8 CAREER-alignment contract that narrows the core subtle-attack
  study to one EV aggregator setpoint, two temporal action intervals, one
  midpoint revision, six low-amplitude bias shapes, matched long-horizon
  budgets, and independent confirmation while keeping telemetry attacks,
  repeated revisions, multi-device control, and the IA0–IA5 ladder as explicit
  extensions; and
- an offline M9 two-interval state machine and mirrored fixture pair that
  isolates revision permission, keeps all parity bytes fixed, rejects invalid
  transitions, and emits four content-addressed protocol-only receipts; and
- an offline M10 admission framework that keeps real `S` and `M` resources on
  HOLD while testing separate process-relationship and predictive-ranking
  profiles against partition, threshold-order, parity, leakage, and update
  failures; and
- an offline M11 content-addressed source-lineage audit that preserves the
  available `S` and `M` inputs as exploratory evidence, keeps every scientific
  threshold unset, and identifies the clean-source repairs required by M12;
  and
- an offline M12 clean-source freeze design that defines disjoint partition
  roles, separate deterministic `S` and `M` package profiles, null empirical
  slots, and unissued two-reviewer receipt templates; and
- an offline M13 source-manifest validator with two synthetic structural passes
  and twelve single-fault fail-closed cases, none of which changes a real
  source, partition, review, threshold, or resource status; and
- an offline M14 independent-review packet that binds thirteen governing files
  to an exact Git commit while leaving every prerequisite, review disposition,
  numerical choice, and execution authorization open; and
- an offline M14A review-receipt intake contract that validates exact packet
  binding, reviewer-role and identity separation, dispositions, comment
  integrity, and two-receipt bundle mechanics without issuing a real receipt,
  resolving the M14 checkpoint, or authorizing execution; and
- an offline M14B reviewer handoff with a six-file exact-byte preflight, two
  null-only role worksheets that are explicitly not receipts, and three
  read-only CLI validation commands with no receipt-creation or checkpoint-
  resolution path.

The orchestration design, failure taxonomy, current limitations, and next gate
are documented in `ORCHESTRATION_CONTRACT.md`. The machine-readable AI-V2
decomposition is `artifacts/ai_v2_component_matrix.json`, and the common plan
interface is `orchestration_plan.schema.json`. The bounded IA3 candidate-space
design is `artifacts/ia3_candidate_space_contract.json`, with generation
receipts governed by `candidate_space_receipt.schema.json`.
The M3 IA3/IA4 equality contract is
`artifacts/ia3_ia4_search_surface_contract.json`; its schemas are
`search_surface.schema.json`, `ia4_request.schema.json`, and
`ia4_fixture_response.schema.json`. This adapter does not call a model or
execute a tool.
The M4 boundary is documented in `M4_MODEL_REPLAY_REPORT.md` and
`artifacts/ia4_model_parsing_contract.json`; its replay and smoke schemas are
`ia4_model_replay.schema.json` and `ia4_model_smoke.schema.json`.
The M5 boundary is documented in `M5_INTERACTIVE_PROTOCOL_REPORT.md`; its
machine-readable receipt and schema are
`artifacts/ia4_interactive_contract_m5.json` and
`ia4_interactive_contract.schema.json`.
The M6 model qualification, including two preserved fail-closed attempts, is
documented in `M6_INTERACTIVE_MODEL_REPORT.md`; its receipt schema is
`ia4_interactive_model_smoke.schema.json`.
The M7 causal tool-use qualification is documented in
`M7_COUNTERFACTUAL_TOOL_USE_REPORT.md`; its preregistration and model-receipt
schemas are `ia4_counterfactual_contract.schema.json` and
`ia4_counterfactual_model_smoke.schema.json`.
The CAREER-aligned M8 design is documented in
`M8_CAREER_STEALTH_BIAS_DESIGN.md`; its canonical artifact and schema are
`artifacts/career_stealth_contract_m8.json` and
`career_stealth_contract.schema.json`. M8 is offline and does not amend the
frozen experiment specification or portable roadmap report.
The M9 protocol-isolation result is documented in
`M9_CAREER_TWO_INTERVAL_FIXTURE_REPORT.md`; its canonical contract, receipts,
and schema are `artifacts/career_two_interval_fixture_m9.json` and
`career_two_interval_fixture.schema.json`. M9 uses only qualitative synthetic
tokens and does not access a model, tool, simulator, detector, embedding
service, actuator, or evaluation record.
The M10 admission-validator design is documented in
`M10_CAREER_RESOURCE_ADMISSION_REPORT.md`; its canonical synthetic-fixture
evidence and schema are `artifacts/career_resource_admission_m10.json` and
`career_resource_admission.schema.json`. Passing M10 does not validate or admit
a real `S` or `M` resource.
The M11 source-lineage decision is documented in
`M11_CAREER_THRESHOLD_HOLD_REPORT.md`; its canonical HOLD artifact and schema
are `artifacts/career_threshold_hold_m11.json` and
`career_threshold_hold.schema.json`. M11 selects no scientific threshold and
authorizes no resource admission or runtime access.
The M12 source-freeze design is documented in
`M12_CAREER_SOURCE_FREEZE_DESIGN_REPORT.md`; its canonical artifact and schema
are `artifacts/career_source_freeze_design_m12.json` and
`career_source_freeze_design.schema.json`. M12 instantiates no data, review,
threshold, model, or real resource.
The M13 synthetic validator is documented in
`M13_CAREER_SOURCE_MANIFEST_VALIDATOR_REPORT.md`; its canonical matrix and
schema are `artifacts/career_source_manifest_matrix_m13.json` and
`career_source_manifest_matrix.schema.json`. A positive M13 receipt is
structural-only and cannot approve a real source.
The M14 review boundary is documented in
`M14_CAREER_SOURCE_REVIEW_PACKET_REPORT.md`; its content-addressed packet and
schema are `artifacts/career_source_review_packet_m14.json` and
`career_source_review_packet.schema.json`. It is ready for independent review
but is not approved and authorizes no source generation.
The M14A intake boundary is documented in
`M14A_CAREER_REVIEW_RECEIPT_INTAKE_REPORT.md`; its canonical contract and
schemas are `artifacts/career_review_receipt_intake_m14a.json`,
`career_review_receipt.schema.json`, and
`career_review_receipt_intake.schema.json`. M14A checks receipt declarations
and exact bindings only; external governance must establish reviewer identity
and independence, and the M14 checkpoint remains open.
The M14B reviewer workflow is documented in
`M14B_CAREER_REVIEWER_HANDOFF_REPORT.md`; its contract, empty worksheets, and
schemas are `artifacts/career_reviewer_handoff_m14b.json`,
`artifacts/reviewer_handoff/`, `career_reviewer_handoff.schema.json`, and
`career_reviewer_worksheet.schema.json`. The handoff verifies exact bytes and
validates externally supplied declarations but cannot create a receipt or
approve the packet.

The prior five-episode L5b result remains preserved under
`v3/g7_condition_freeze/20260830_r1/`. Its adaptive prompt disclosed the
empirical benign self-alarm horizon, so it is exploratory, horizon-informed
evidence—not the confirmatory-uninformed condition defined here.

## Safety boundary

The campaign remains on HOLD. The runtime-integration entry point refuses more
than one live window, restricts output to this directory, loads frozen runner
bytes by exact path, and never restarts either model service. A gated smoke may
start one ephemeral GridLAB-D/HELICS composition; detector sweeps, evaluation
seeds, and campaign-scale execution remain prohibited.

The current detector audit is intentionally `calibrated=false`: the preserved
legacy benign and sensitivity inputs do not carry the seed, condition, and
content-addressed lineage required by this confirmatory protocol. See
`DETECTOR_PAIRING_REPORT.md`.

## Local validation

From this directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m g7confirm.cli validate-spec --spec experiment_spec.yaml
python3 -m g7confirm.runtime --operating-point responsive_night \
  --arm scripted_max --budget-windows 1 --energy-cap-kvah 2.0 \
  --windows 1 --coupling-step 10 \
  --output-dir artifacts/runtime_integration/gen_only_<unique-id> --gen-only
```

Offline detector/pairing artifacts can be generated once with:

```bash
python3 -m g7confirm.cli detector-audit --spec experiment_spec.yaml \
  --repo-root /home/cfu6/roi-uncc-mcp --mission-id <mission-id> \
  --decision-id <decision-id> --output <unique-audit-path>
python3 -m g7confirm.cli calibration-plan --spec experiment_spec.yaml \
  --repo-root /home/cfu6/roi-uncc-mcp --detector-audit <audit-path> \
  --output <unique-calibration-plan-path>
python3 -m g7confirm.cli paired-plan --spec experiment_spec.yaml \
  --repo-root /home/cfu6/roi-uncc-mcp --detector-audit <audit-path> \
  --profile smoke --output <unique-paired-plan-path>
```

These commands produce non-executable plans. They do not authorize calibration
runs, detector fitting, evaluation access, or a campaign.

The model smoke is intentionally separate because it performs one network
request:

```bash
python3 -m g7confirm.cli model-smoke --spec experiment_spec.yaml \
  --prompt prompts/clean_uninformed_v1.json \
  --output artifacts/model_smoke_<unique-attempt-id>.json
```

Every output command uses create-once semantics and refuses to overwrite an
existing file. Model-smoke retries therefore require a newly authorized,
uniquely named artifact rather than replacing a failed attempt.

The IA4 M4 parsing smoke is also separate. It performs one model discovery and
one completion, exposes no executable tool, and uses only a synthetic interface
fixture:

```bash
python3 -m g7confirm.cli ia4-model-smoke --spec experiment_spec.yaml \
  --output artifacts/ia4_model_smoke_m4_<unique-attempt-id>.json
```

The M5 fixture command is fully offline. It creates paired IA4-fixture and IA3
control receipts over the same synthetic read-only result without contacting a
model or executing a tool:

```bash
python3 -m g7confirm.cli ia4-interactive-fixture \
  --spec experiment_spec.yaml \
  --output artifacts/ia4_interactive_contract_<unique-id>.json
```

The M6 command is networked but never executes the requested tool. It permits
one discovery and at most two completions, injects the frozen fixture, and uses
create-once output semantics:

```bash
python3 -m g7confirm.cli ia4-interactive-model-smoke \
  --spec experiment_spec.yaml \
  --output artifacts/ia4_interactive_model_smoke_<unique-attempt-id>.json
```

M7 separates preregistration from transport. The first command is offline; the
second performs one discovery and at most four completions over two injected
fixtures. Neither command executes a tool:

```bash
python3 -m g7confirm.cli ia4-counterfactual-contract \
  --spec experiment_spec.yaml \
  --output artifacts/ia4_counterfactual_contract_<unique-id>.json
python3 -m g7confirm.cli ia4-counterfactual-model-smoke \
  --spec experiment_spec.yaml \
  --contract artifacts/ia4_counterfactual_contract_<unique-id>.json \
  --output artifacts/ia4_counterfactual_model_smoke_<unique-attempt-id>.json
```

The successful bounded evidence and its limitations are summarized in
`RUNTIME_INTEGRATION_REPORT.md`. Passing it is not a campaign-authorization
gate.
