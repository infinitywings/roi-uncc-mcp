# M19 bounded paired runtime-qualification report

Date: 2026-09-03

RKA project: `prj_01KYMPK10PE9YH1TJ84PAVB9Z6`

RKA mission: `mis_01M1MEXMZZKHE53W1J9W4N5ZC8`

Authorizing decision: `dec_01M1MEP2VK98XN9KD935WDH39N`

Classification: **PRELIMINARY_ONLY**

Final evaluation: **SEALED**

## Outcome

M19 qualified one real, paired, single-window simulator path from an M18-
validated action request through policy selection, dual-budget admission,
HELICS transport, OpenDER realization, and GridLAB-D completion. The valid
pair used runtime-qualification seed `5101`, measurement-noise seed `95101`,
GridLAB-D seed `10`, the `responsive_night` operating point, and two separate
network-isolated ephemeral containers from exact image
`sha256:c79f6cc1bd1eea69c5c21b8794d9def19435f26aa7f4f71c5330c823835e4df7`.

This is a bounded plumbing qualification, not an attack-effect result. The
single sampled voltage and source-power state precedes the command actuation,
so this pair cannot estimate post-actuation grid harm. Detector execution
remained held and Volt-VAR defense was disabled. No detector, defense,
threshold, resource, or evaluation configuration was frozen.

The create-once evidence is
`artifacts/m19_runtime_qualification_seed5101_attempt2/m19_runtime_qualification.json`
(SHA-256
`7a10008b2b73f72363b667450121bcdcd22608e9dc50aa9cd5a82fec24899d74`).

## Authorization and service preflight

The checked-in M18 preflight returned zero issues immediately before runtime
work. Both benign and attack action requests independently passed
`validate_preliminary_action_request` and were rebound inside the runtime to
the exact M18 artifact, runtime source, DER config, seed, pair, and budget.
Every output is create-once and labeled `PRELIMINARY_ONLY`.

Existing model services were probed without starting, restarting, replacing,
or reconfiguring either service:

- LLM: `qwen3.6-35b-a3b` at
  `http://ccil1s26m8hj6lws:8000/v1`, owned by vLLM, with model root
  `QuantTrio/Qwen3.6-35B-A3B-AWQ` and a reported 262,144-token context;
- embedding: the RKA-configured `openai_compat` backend using
  `qwen3-embedding:0.6b`, 1,024 dimensions. Its non-persisting connection
  test passed at 92.25 ms.

The LLM request was an identity/health GET only. The embedding test performed
one non-persisting inference probe. Neither model participated in the
deterministic attack decision in M19; adaptive LLM attacker behavior therefore
remains a later preliminary stage.

## Retained failed attempt

Attempt 1 failed before HELICS broker creation, GridLAB-D startup, or any
simulated command. The mounted repository exposed `v3/opender/device.py`, but
the runtime did not add `v3/deps/opender-src/src` to `sys.path`, producing
`ModuleNotFoundError: No module named 'opender'`.

The partial generated feeder and HELICS configuration were retained at
`artifacts/m19_runtime_qualification_seed5101_attempt1/`, together with the
action requests, service preflight, and
`failure_record.json` (SHA-256
`97d249cb12ea0a18ec9d3758f63e3c68f13ef77f056ffdbf81dc6d97ef19f49f`).
The paired attack was not started. The correction added only the vendored
OpenDER package path; attempt 2 used new output paths and action requests bound
to the new runtime source hash. No failed artifact was overwritten.

## Passing matched pair

Both attempt-2 containers exited zero and were removed. Controlled lineage,
pre-actuation physical state, source state, and measurement-noise realization
were exactly equal across the pair.

| Measure | Benign | Scripted attack |
|---|---:|---:|
| Windows | 1 | 1 |
| Window duration | 10 s | 10 s |
| Perturbed-window cap | 0 | 1 |
| Apparent-energy cap | 0 kVAh | 2 kVAh |
| Perturbed windows spent | 0 | 1 |
| Admitted command-deviation energy | 0 kVAh | 0.7777778 kVAh |
| Delivered command-deviation energy | 0 kVAh | 0.7777778 kVAh |
| GridLAB-D return code | 0 | 0 |

The scripted policy requested four commands. `DER_EV5_PV = (80, 0)` was
benign-equivalent and was correctly removed before admission. The remaining
three commands were admitted and delivered without drift:

| Device | Requested P/Q | Accepted P/Q | Realized attack minus benign P/Q |
|---|---:|---:|---:|
| `DER_EV1_BESS` | `(100, 0)` | `(100, 0)` | `(+100, 0)` |
| `DER_EV3_PV` | `(0, 0)` | `(0, 0)` | `(-80, 0)` |
| `DER_EV4_BESS` | `(100, 0)` | `(100, 0)` | `(+100, 0)` |
| `DER_EV5_PV` | `(80, 0)` | removed | `(0, 0)` |

These values establish command admission, delivery, and OpenDER realization.
They do not establish downstream voltage harm because no post-actuation window
was observed.

## Runtime identity and retained anomalies

The passing pair used GridLAB-D `5.3.0-20236`, HELICS
`3.6.1-main-ge437060a1`, Python `3.10.12`, and vendored OpenDER `2.2.0`.
Both containers used `--network none`, contained no physical field connection,
and were absent from `docker ps -a` after completion.

Three warning classes remain preserved:

1. HELICS reported unknown-route messages during final teardown.
2. The Python HELICS binding warned that `helicsFederateFinalize` is
   deprecated in favor of `helicsFederateDisconnect`.
3. GridLAB-D emitted its existing FBS switch-behavior warning.

Zero exit codes and matching traces do not dismiss these warnings. They must
be re-examined before a multi-window pilot can support stability claims.

## Scientific boundary and next gate

M19 establishes only:

- one-window matched runtime plumbing;
- deterministic attack command admission and delivery; and
- OpenDER realization under a simulated feeder.

It does not establish post-actuation grid harm, detector or defense
effectiveness, multi-window stability or stealth, campaign throughput,
statistical significance, generalization, or publication-grade evidence.
Final evaluation seeds `9101–9112` were not read and remain sealed.

The next preliminary gate should be a very small multi-window system-
identification pilot, using only its registered preliminary partition, to
observe at least one post-actuation voltage/source response and to resolve or
classify teardown behavior. Only after that should an LLM-driven attacker be
connected to the same frozen strategy/tool interface and compared with the
matched deterministic rung. Detector calibration and defense comparisons must
remain on their separate registered preliminary partitions.
