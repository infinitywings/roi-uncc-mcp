# M4 model-output replay and parsing report

## Scope

M4 qualifies one narrow boundary: a raw OpenAI-compatible chat completion can
be bound to the exact M3 search surface, replayed offline, parsed as one strict
IA4 response, and passed to the common adapter. It does not implement an
interactive tool loop, simulator access, detector access, embedding retrieval,
runtime actuation, calibration, evaluation, or a campaign.

The model smoke uses a synthetic two-candidate interface fixture. It is not an
experimental attack condition and does not measure strategy quality or grid
harm.

## Implemented boundary

`g7confirm/ia4_model.py` provides:

- a response schema whose surface ID and candidate enum are bound to the
  current content-addressed manifest;
- deterministic chat request construction using one development seed;
- exact single-choice, model-ID, assistant-role, and normal-stop validation;
- rejection of model-emitted tool calls and out-of-contract refusal fields;
- rejection of markdown, reasoning prefixes, duplicate JSON fields,
  non-object content, unknown candidates, request mutation, and non-finite
  JSON constants;
- a serializable completion record that can be replayed without the endpoint;
  and
- a hard-bounded transport helper allowing one model discovery and exactly one
  completion request.

M4 model responses must declare an empty `used_tool_call_ids` array. Tool
schemas remain visible on the shared surface so the future interactive design
is explicit, but no tool is callable in this milestone.

## First bounded smoke result

Artifact: `artifacts/ia4_model_smoke_m4_attempt1.json`

- Endpoint: `http://ccil1s26m8hj6lws:8000/v1`
- Model: `qwen3.6-35b-a3b`
- Completion requests: 1
- Development seed: 8101
- Temperature: 0
- Output-token cap: 512
- Finish reason: `stop`
- Prompt/completion/total tokens: 1548 / 174 / 1722
- Strict transport and parsing result: PASS
- Parsed decision: `safety_refusal`
- Tool, embedding, simulator, detector, and evaluation access: none

The response was schema-valid and content-addressed, but the model treated
`campaign_authorized=false` and `evaluation_sealed=true` as reasons not to
select a candidate. This is a behavioral comparability anomaly, not a parsing
failure. Those flags govern external harness execution; selecting a typed plan
is a non-actuating proposal. IA3 does not semantically react to governance
metadata, so leaving this ambiguity unresolved could inflate IA4 refusal rates
and confound the primary contrast.

The offline request contract now states that a plan is non-actuating, the
governance flags do not prohibit candidate selection, and safety refusal is
reserved for cases where no candidate can be selected within the declared
knowledge, authority, and schema constraints. The first receipt remains
immutable and preserves this anomaly.

## Clarified create-once smoke

Artifact: `artifacts/ia4_model_smoke_m4_attempt2_clarified.json`

After an RKA inspection checkpoint and explicit PI authorization, exactly one
new completion tested the clarified semantics. It used the same endpoint,
model, development seed, temperature, output-token cap, synthetic candidate
surface, and no-tool boundary as the first attempt.

- Endpoint: `http://ccil1s26m8hj6lws:8000/v1`
- Model: `qwen3.6-35b-a3b`
- Search surface:
  `surface_e8b57b491d4439045a988a2288c6601703fbce4ee9eee06ce6ffed710ca50412`
- Completion requests: 1
- Development seed: 8101
- Temperature: 0
- Output-token cap: 512
- Finish reason: `stop`
- Prompt/completion/total tokens: 1646 / 236 / 1882
- Strict transport and parsing result: PASS
- Parsed decision: `plan`
- Selected candidate: `cand_e203a116322e41264fda`
- Common `PlanValidator`: valid, accepted, and effective under the synthetic
  benign command fixture
- Tool, embedding, simulator, detector, and evaluation access: none

The model selected the unchanged `step_corner` candidate already present in
the content-addressed surface. Offline replay recovered the same candidate and
the common validator admitted its synthetic 30 kW action within the declared
K/A and dual-budget contract. This removes the specific governance-wording
confound observed in attempt 1. It does not demonstrate interactive tool use or
strategy quality.

## Evidentiary interpretation

M4 establishes that the configured vLLM model can return a strict response
whose model identity, surface identity, finish state, and raw bytes survive the
common parsing boundary. The clarified attempt also establishes that this one
model call can select an unchanged candidate without treating external harness
governance flags as a mandatory refusal. It does not establish correct grid
reasoning, interactive tool competence, effective attack behavior, stable
refusal behavior across conditions, or superiority over IA3.

The next implementation milestone is the offline M5 interactive state machine
documented in `M5_INTERACTIVE_PROTOCOL_REPORT.md`. Any live multi-turn model
test remains a separate gate and must use a new create-once execution overlay;
the M5 offline protocol itself explicitly authorizes neither model transport
nor tool execution.
