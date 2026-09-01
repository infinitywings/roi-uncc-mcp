# M9 CAREER two-interval protocol-isolation report

Status: **PASS — protocol isolation only**

Contract ID:
`careertwoint_6d57736587a6a6ad2474392a0413b784fa9633ecfa94af572798b7419b1e73a5`

Mirrored-pair ID:
`m9pair_38433ef32d206640b826cd474ecc8c70f028d60385558b675eadc0734ec9a786`

## Result

M9 implements the smallest runnable offline software fixture needed to verify the
CAREER `A` intervention. It compares two conditions that begin with the exact
same precommitted qualitative two-interval plan:

- `A0_preplanned` receives the scheduled midpoint observation but has no
  permission to change its plan;
- `A1_response_informed` receives the same observation and may replace the
  second interval exactly once.

The fixture presents two mirrored qualitative midpoint trend observations.
The deterministic reference policy is deliberately a protocol witness, not an
attacker: it maps the negative observation to the declared negative second
interval and the positive observation to the declared positive second
interval. `A0` retains the precommitted plan in both cases. `A1` selects a
different second interval in the two cases. The first interval is identical in
all three candidate plans and in all four terminal receipts.

All eight preregistered checks passed:

1. `A0` has the same terminal plan in both mirrored conditions.
2. `A1` has distinct terminal plans in the mirrored conditions.
3. Both `A0` receipts contain zero revisions.
4. Both `A1` receipts contain exactly one revision.
5. The first-interval fingerprint is identical in all four receipts.
6. The parity fingerprint is identical in all four receipts.
7. Every external-access counter is zero.
8. Every receipt is terminal and content-addressed.

This is evidence that the intervention can be represented and enforced without
changing the other declared inputs. It is not evidence that the witness policy
is effective or that any attack outcome improves.

## Intervention and state machine

Each episode begins in `precommitted`, accepts exactly one frozen midpoint
observation, moves to `awaiting_midpoint_decision`, and then reaches `terminal`.
Invalid transitions move the session to `failed_closed` and do not receive a
retry.

| Operation | `A0_preplanned` | `A1_response_informed` |
|---|---|---|
| Present one declared midpoint observation | Allowed | Allowed |
| Retain the precommitted plan | Allowed | Allowed |
| Replace the second interval after midpoint | Rejected | Allowed once |
| Change the first interval | Rejected | Rejected |
| Select outside the frozen library | Rejected | Rejected |
| Decide before midpoint or after terminal | Rejected | Rejected |

The terminal receipt binds the initial and terminal plan IDs, midpoint
observation ID, first- and second-interval fingerprints, revision count, state
sequence, parity fingerprint, and zero external-access counters.

## Frozen parity

The following inputs are content-addressed once and reused in every episode:

- precommitted initial plan;
- complete ordered candidate library;
- midpoint observation schema;
- empty pre-pair history and no-cross-condition-learning rule;
- uninstantiated M8 budget declaration;
- two-interval schedule; and
- non-executing safety-shield placeholder.

Their combined parity fingerprint is
`sha256_6776210404947b827931f192f6c3a60edf58e91c586f53440287a147aaa9f671`.
The only condition-level difference is the revision permission represented by
`A0` versus `A1`.

The fixture does not assign physical units, setpoint values, amplitude limits,
duration, feeder state, detector threshold, or alarm outcome. Its strategy and
magnitude fields are qualitative tokens. Consequently, it cannot actuate a
device even if imported by runtime code.

## Mirrored receipts

| Midpoint fixture | Capability | Revisions | Terminal behavior |
|---|---|---:|---|
| `mirror_negative` | `A0_preplanned` | 0 | Retains precommitted second interval |
| `mirror_negative` | `A1_response_informed` | 1 | Selects declared negative second interval |
| `mirror_positive` | `A0_preplanned` | 0 | Retains precommitted second interval |
| `mirror_positive` | `A1_response_informed` | 1 | Selects declared positive second interval |

The mirrored labels are synthetic protocol tokens. They do not assert that a
positive or negative voltage trend should be followed in a real feeder. A
scientifically admissible response policy must later be selected using
development episodes and confirmed on fresh blocks under the governing safety,
alarm-exposure, budget, and uncertainty rules.

## Fail-closed tests

The tests cover both successful evidence construction and prohibited paths:

- an `A0` revision attempt fails closed;
- a revision before the midpoint fails closed;
- a second decision after terminal state fails closed;
- mutated observation bytes fail closed;
- unknown or content-mutated plans are rejected;
- contract and receipt mutations invalidate their content addresses;
- all three fixture candidates must share the same first interval; and
- governance cannot authorize model, tool, simulator, detector, embedding,
  actuator, evaluation, or campaign access.

The checked-in artifact is rebuilt by
`g7confirm.career_two_interval.build_m9_artifact()` and compared byte-for-value
in the unit suite. Semantic validation is stricter than the interchange JSON
Schema and recomputes every nested content address.

## Governance and claim boundary

No model endpoint, read-only or real tool, GPU embedding service, simulator,
detector, calibration input, actuator, or evaluation record was accessed.
Evaluation remains sealed. Detector calibration, live runtime qualification,
and campaign execution remain unauthorized.

M9 does **not** establish:

- physical consequence;
- stealth or detector evasion;
- correctness of the response rule;
- attack-policy quality;
- LLM reasoning or tool-use capability;
- runtime readiness; or
- campaign authorization.

These restrictions are part of the content-addressed contract and each receipt
uses the interpretation label `protocol_isolation_only`.

## Machine artifacts

- `artifacts/career_two_interval_fixture_m9.json` contains the canonical
  contract and four terminal receipts.
- `career_two_interval_fixture.schema.json` defines the interchange shape.
- `g7confirm/career_two_interval.py` enforces semantic invariants, transitions,
  content addresses, and the mirrored acceptance gate.
- `tests/test_career_two_interval.py` covers parity, mirrored sensitivity,
  governance, mutation detection, and invalid transitions.

The governing M8 contract is
`careerstealth_3091a0e686e43b483906a37733f26dfb4cef9fd90d2ae56226e47003b3cdd394`.
The M9 design decision is `dec_01M1DK7XKSN2DPEZ3EGYZAHKJW` under mission
`mis_01KYMRDZHYN4QXC1XFTGP54E36`.

## Next gate

M10 should define independent admission contracts for the CAREER `S` and `M`
resources:

- `S` may expose only process relationships that pass a prospective
  action-validity test independent of treatment outcomes;
- `M` may expose only read-only candidate rankings that pass a held-out ranking
  test independent of the `A` comparison;
- neither resource may change the raw observation interface, action authority,
  candidate library, budgets, safety shield, confirmation rule, or revision
  count; and
- failed admission reduces the factorial prospectively rather than substituting
  an unvalidated resource.

M10 remains an offline contract gate. It does not authorize model transport,
real tool execution, simulator or detector access, or evaluation data.
