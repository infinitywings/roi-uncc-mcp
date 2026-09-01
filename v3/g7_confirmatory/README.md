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
  through the common candidate and plan validator boundary.

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

The successful bounded evidence and its limitations are summarized in
`RUNTIME_INTEGRATION_REPORT.md`. Passing it is not a campaign-authorization
gate.
