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
  resolution path; and
- an M15 two-tier gate that permits narrowly enumerated offline engineering
  and local advisory work while preserving thirteen M14/M14A/M14B review
  assets byte-for-byte and keeping all source, partition, admission,
  threshold, calibration, simulator, actuator, evaluation, and campaign
  actions sealed; and
- an M16 bounded local-LLM advisory record with exact input and transport
  provenance, two preserved fail-closed parse attempts, one accepted compact
  response, explicit Brain adjudication, and no external-review authority; and
- an M17 non-executable attack-defense matrix that separates the minimal
  CAREER two-interval causal design from the broader IA0-IA5 red-team track,
  defines subtle long-horizon strategies and matched controls, crosses
  black/gray/white-box information with detector and defense families, and
  requires an M18 preliminary-only gate before any runtime action; and
- an M18 bounded online-development gate that reserves disjoint purpose-
  specific preliminary partitions, authorizes registered end-to-end local
  workflow tests, binds the existing LLM and embedding services, distinguishes
  simulated from physical actuation, and keeps final evaluation sealed.
- an M19 bounded paired runtime qualification that retains one pre-simulation
  wiring failure, then completes one benign and one matched deterministic
  single-window trace through HELICS, OpenDER, and GridLAB-D with exact command
  admission/delivery reconciliation and verified ephemeral-container teardown.
  M19 explicitly does not claim post-actuation grid harm or detector/defense
  effectiveness, and final evaluation remains sealed; and
- an M20 two-window matched timing test that preserves a negative result: the
  one-window attack is admitted and delivered, but the next runner observation
  and completed GridLAB-D recorders do not yet expose a feeder response. M20
  therefore records an observation-latency gap and requires a separately
  registered three-window timing gate before any LLM-attacker runtime test;
  and
- an M21 three-window matched timing qualification that locates the first
  recorder-visible attack power at the third completed GridLAB-D row and the
  first nonzero paired feeder response at runner `t=30`. It fixes the causal
  scoring index for the next bounded same-surface LLM-attacker smoke test but
  makes no attack-effect, detector, defense, or LLM-advantage claim; and
- an M22 current-service regression over the exact M7 surface in which the
  existing LLM requests one harness-injected read-only sensitivity fixture per
  mirrored condition, makes the correct target-dependent candidate switch,
  and passes the common plan validator. The matched IA3 control also passes,
  so M22 qualifies protocol and tool-result use but does not establish
  autonomous strategy learning or LLM advantage; and
- an M23 empirical system-identification source candidate built from one
  shared benign control and symmetric +30/-30 kW, target-isolated probes at
  each of two BESS devices. It preserves the full t=30 voltage-response
  columns, one-sided estimates, centered residuals, command signs, warnings,
  and raw hashes. An independent exact-byte audit passes, while the original
  timestamp-sensitive verifier failure remains retained; the source is not
  admitted and no general sensitivity claim is made; and
- an M24 real local read-only adapter that binds the exact M23 source and
  independent audit, preserves the M7 `observe_sensitivity` schema and
  `DER_A`/`DER_B` namespace, exposes only two registered scalar gains, and
  gives IA3 and IA4 byte-identical requests and payloads. Provenance remains
  in a separate receipt; the adapter advances no simulation time and accesses
  no model, embedding service, detector, network, Docker, simulator,
  evaluation record, or actuator.

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
The M19 runtime outcome, retained failure, model-service preflight, and
single-window scientific limitation are documented in
`M19_BOUNDED_PAIRED_RUNTIME_QUALIFICATION_REPORT.md`; its create-once evidence
is under `artifacts/m19_runtime_qualification_seed5101_attempt{1,2}/`.
The M20 timing result is documented in
`M20_TWO_WINDOW_TIMING_GAP_REPORT.md`; its create-once matched-pair evidence is
under `artifacts/m20_two_window_timing_seed5102_attempt1/`. Exact zero paired
deltas at the second runner observation are treated as a timing gap, not as a
null physical-effect claim.
The M21 timing qualification is documented in
`M21_THREE_WINDOW_CAUSAL_TIMING_REPORT.md`; its create-once evidence is under
`artifacts/m21_three_window_timing_seed5103_attempt1/`. For this composition, a
window-1 command is first feeder-visible in runner window 3, so window 2 must
not be scored as a post-actuation result.
The M22 current-service regression is documented in
`M22_CURRENT_SERVICE_TOOL_USE_REGRESSION_REPORT.md`; its preregistered contract,
two action requests, and create-once receipt are under
`artifacts/m22_current_service_regression_attempt1/`. It uses synthetic fixture
injection only: no real tool, simulator, detector, defense, embedding service,
actuator, or final-evaluation record is accessed.
The M23 empirical source candidate is documented in
`M23_EMPIRICAL_SYSTEM_IDENTIFICATION_REPORT.md`; its contract, six action
requests, five network-isolated runtime traces, source, retained verifier
failure, and independent audit receipt are under
`artifacts/m23_system_identification_seed6101_attempt1/`. It is a preliminary
source-mechanics result, not a resource-admission or final-evidence gate.
The M24 adapter qualification is documented in
`M24_READ_ONLY_ADAPTER_QUALIFICATION_REPORT.md`; its create-once contract,
matched IA3/IA4 invocation receipt, and independent audit are under
`artifacts/m24_read_only_adapter_attempt1/`. Its consumer payload is
field-minimized, while complete M23 provenance remains separately
content-addressed and unadmitted.
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
The PI-confirmed M15 gate revision is documented in
`M15_CAREER_TWO_TIER_GATE_REPORT.md`; its canonical contract and schema are
`artifacts/career_two_tier_gate_m15.json` and
`career_two_tier_gate.schema.json`. M15 defers rather than waives external
review. Internal advice is non-independent and cannot issue a receipt, resolve
the deferred gate, or authorize any sealed experiment action.
The M16 advisory is documented in `M16_CAREER_INTERNAL_ADVISORY_REPORT.md`;
its evidence and schema are `artifacts/career_internal_advisory_m16.json` and
`career_internal_advisory.schema.json`. The accepted local-model response is
preserved rather than trusted: every finding has a Brain disposition, one
threshold-setting recommendation is rejected as a governance conflict, and a
stale model-access claim is explicitly corrected.
The M17 matrix is documented in
`M17_CAREER_ATTACK_DEFENSE_TRIAL_MATRIX_REPORT.md`; its canonical artifact and
schema are `artifacts/career_trial_matrix_m17.json` and
`career_trial_matrix.schema.json`. M17 assigns no source, partition, resource,
threshold, detector parameter, or run. It preserves final evaluation as an
empty sealed stage and routes all preliminary execution through M18.
The PI-authorized M18 boundary is documented in
`M18_BOUNDED_ONLINE_DEVELOPMENT_GATE_REPORT.md`; its canonical artifact and
schema are `artifacts/preliminary_only_gate_m18.json` and
`preliminary_only_gate.schema.json`. Passing M18 permits only registered,
create-once, `PRELIMINARY_ONLY` online actions. Final evaluation seeds,
confirmatory execution, physical field actuation, and final scientific claims
remain sealed.

The prior five-episode L5b result remains preserved under
`v3/g7_condition_freeze/20260830_r1/`. Its adaptive prompt disclosed the
empirical benign self-alarm horizon, so it is exploratory, horizon-informed
evidence—not the confirmatory-uninformed condition defined here.

## Safety boundary

The confirmatory campaign remains on HOLD. M18 permits bounded online
development only after its preflight and per-action validation pass. The first
M19 runtime-qualification flow remains capped at one live window per run,
restricts output to this directory, loads content-addressed runner bytes, and
never starts or restarts either model service. It may start an ephemeral local
GridLAB-D/HELICS/network/detector composition and must record teardown.
The registered M20 flow is capped at exactly two live windows per run and one
attack intervention; it cannot expand itself to a third observation window.
The separately registered M21 flow is capped at exactly three live windows per
run and one attack intervention; it cannot expand itself to a fourth window.
M22 executes no simulator or real tool. M23 is capped at one benign and four
signed, single-target simulator probes, each with exactly three windows and at
most one delivered intervention; its source remains unadmitted. M24 invokes
only a local read-only adapter over the exact M23 source and audit files. It
performs no model, embedding, detector, defense, network, Docker, simulator,
evaluation, or actuator access and advances zero simulation time.
Evaluation seeds, physical field-device actuation, and campaign-scale
confirmatory execution remain prohibited.

The current detector audit is intentionally `calibrated=false`: the preserved
legacy benign and sensitivity inputs do not carry the seed, condition, and
content-addressed lineage required by this confirmatory protocol. See
`DETECTOR_PAIRING_REPORT.md`.

## Local validation

From this directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_m24_read_only_adapter -v
python3 -m g7confirm.m24_read_only_adapter --mode verify \
  --root artifacts/m24_read_only_adapter_attempt1
python3 -m g7confirm.m24_independent_audit --mode verify \
  --root artifacts/m24_read_only_adapter_attempt1
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

The M15 preflight is fully read-only and verifies the frozen roadmap and
experiment specification, the preserved M14 review machinery, and both
permission tiers:

```bash
python3 -m g7confirm.cli career-development-gate \
  --repo-root /home/cfu6/roi-uncc-mcp
```

A successful preflight authorizes offline contract/code/test work and local
advisory review on synthetic or non-evaluation inputs only. It does not
complete external review or unseal any scientific or runtime operation.

The M16 advisory evidence has a separate read-only preflight:

```bash
python3 -m g7confirm.cli career-advisory-preflight \
  --repo-root /home/cfu6/roi-uncc-mcp
```

This command first verifies the M15 boundary, then verifies the thirteen M16
inputs, accepted model-output digest, Brain adjudication, and sealed-action
state. It does not call the model or any other service.

The M17 matrix has a separate read-only preflight:

```bash
python3 -m g7confirm.cli career-trial-matrix-preflight \
  --repo-root /home/cfu6/roi-uncc-mcp
```

This command verifies the M16 evidence chain, six exact-byte design inputs,
the IA0-IA5 and knowledge-profile contracts, and the final-evaluation seal. It
does not assign or execute a preliminary trial.

The M18 bounded online-development authorization has a separate read-only
preflight:

```bash
python3 -m g7confirm.cli preliminary-only-preflight \
  --repo-root /home/cfu6/roi-uncc-mcp
```

This command verifies the complete M17 chain, disjoint preliminary partitions,
existing-service restrictions, per-action requirements, and all final seals.
It starts no process; M19 consumes the validated gate to run the first bounded
online flow.

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
