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

## Bounded smoke result

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
knowledge, authority, and schema constraints. The single M4 completion cap was
not expanded, so this clarification has not been tested with a second model
call.

## Evidentiary interpretation

M4 establishes that the configured vLLM model can return a strict response
whose model identity, surface identity, finish state, and raw bytes survive the
common parsing boundary. It does not establish that the model selects an
attack, reasons correctly about grid physics, uses tools effectively, avoids
governance-induced refusal under the clarified prompt, or outperforms IA3.

The next gate should test the clarified non-actuating semantics with one new
create-once smoke before designing the interactive tool state machine. Any
interactive milestone must separately define observation/action transitions,
tool-result provenance, per-turn and episode caps, failure recovery, and a
compute-matched non-LLM control.
