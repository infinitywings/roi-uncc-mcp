# LLM-GridEval — Journal Expansion Draft (power-systems venue)

**Target:** a power-systems journal (IEEE Trans. Smart Grid / Trans. Power Systems /
SmartGridComm). Same core contribution as the ACM Sustainability Week workshop
paper — the **Evaluation Validity Gap (EVG)** — but reframed to lead with grid
physics and hardened against the workshop version's three deepest reviewer gaps
by rebasing the co-simulation onto an explicit **NATIG ns-3/DNP3 cyber network**
and **OpenDER (IEEE-1547) device behavior**. This draft holds the two sections
that change most; the Related Work, EVG definition, and campaign narrative carry
over from the workshop paper.

Status of evidence: G0–G4 passed (benign network equivalence for one OpenDER
BESS on the immutable NATIG r24 runtime). **G5 (network-impairment screening,
no attacker) is in progress and already yields a concrete network-mediation
result** (below). No attacker campaign (G6) has been run; all attacker-effect
claims remain gated behind the confirmatory phase.

---

## 3. System and Threat Model (expanded)

### 3.1 System model

We retain the workshop transmission–distribution plant — a GridPACK IEEE-9-bus
transmission network and GridLAB-D IEEE-123-node feeders coupled through HELICS —
and add two realism layers that the workshop model omitted.

**Explicit cyber network (NATIG).** Every controller and attacker command, and
every telemetry reading, now traverses a simulated **DNP3-over-ns-3** field
network derived from NATIG (PNNL). Following HELICS semantics we split the
federation into two planes: *messages* carry cyber traffic (commands, telemetry)
and are subject to delay, loss, reordering, and modification; *values* carry the
persistent physical state (V, f, P, Q). An endpoint-graph validator forbids any
cyber source from addressing a physical actuation endpoint directly, so command
acceptance and physical actuation are distinct, timestamped events. A control
center polls a remote DER outstation over DNP3 with SELECT-before-OPERATE
semantics, schema/range/freshness validation, and an append-only actuation log.

**Standards-based device (OpenDER).** The workshop paper's linear additive EV
load is replaced at the study node (feeder bus l92) by a pinned OpenDER
(EPRI, IEEE-1547) battery energy storage system exposing active-power limiting,
ramp limits, autonomous volt-var, voltage ride-through / trip and reconnection,
and state-of-charge bounds. Identical accepted remote settings can therefore
yield *different* physical outcomes depending on the device's autonomous local
functions — an axis the linear model cannot express.

The workshop direct-HELICS path is retained as a labeled **direct-path reference
arm**; the network-mediated arm is scientifically admissible only because benign
equivalence between the two was first established (G4): with no impairment and no
attacker, the DNP3/ns-3 path reproduces the direct path's accepted command
sequence and steady P/Q within a frozen tolerance on the identical runtime.

### 3.2 Threat model

The adversary reaches the plant only through an explicit **DNP3 capability
surface** over the ns-3 network, via a compromised authorized control application
or a declared man-in-the-middle location. Read access is to DNP3 telemetry;
write access is to a whitelisted set of DER points within safety limits. Crucially,
*command sent no longer implies command actuated*: an operation must survive
network transport, SELECT-before-OPERATE timing, freshness, and range validation
before the device applies it. A scenario grants an explicit, auditable subset of
capabilities — observe, originate, modify/replay one point, delay/drop, or
generate bounded congestion — making the capability manifest an experimental
factor and enforcing attacker equality across comparison arms rather than
assuming it.

We separate two families that the workshop single-primitive model could not:
**availability** impairments (delay, jitter, loss, outage, bounded congestion),
which degrade delivery without altering semantics, and **integrity** attacks
(command modification, replay, false telemetry), which do. G5 (this expansion)
characterizes the availability family with **no attacker present**, so that any
later attacker effect is measured as a departure from a validated impairment
reference, never confounded with integration artifacts. Relay-trip and
frequency-response attacks remain out of scope until a modeled relay and a
validated dynamic frequency signal exist; the combined stack is a behavioral
device model behind a protocol gateway, not a vendor DNP3 / IEEE-2030.5 server.

---

## 6. Results — Network Mediation (new)

Before any adversary, we ask whether realistic network impairment measurably and
reproducibly changes DER command delivery and physical impact (the network-effect
hypothesis H2). We inject a declared, bounded, seeded ns-3 application-layer DNP3
impairment on the command/telemetry path — no attacker process — and screen delay,
bounded jitter, and bandwidth arms on the immutable NATIG r24 runtime (seed 777,
840 s, one OpenDER BESS at l92, 10 s control/coupling cadence), each against a
0 ms / nominal-bandwidth control.

**Primary observation — command delivery is bimodal in the current DNP3 stack.**
The controller originates all 18 remote operations and all 18 DNP3 SELECTs reach
the device gateway in every arm. Under the exact nominal channel, all 18 OPERATEs
also arrive and actuate. Under *any* modeled channel non-ideality we tested —
a per-message delay as small as 1 ms, bounded jitter, or a bandwidth cap of a few
kb/s — a fixed subset of 8 OPERATEs is lost inside the ns-3/DNP3 transport before
reaching the gateway (no gateway rejection is recorded), reducing delivered
control authority to 10 of 18 (56 %). The result is threshold-near-zero and
saturating (1 ms and 1 s produce the identical dropped set) and reproducible
across reruns because the network draws are seeded.

**Physical consequence.** The un-actuated OPERATEs leave the BESS holding stale
setpoints: relative to the nominal control, 24 of 84 coupling steps diverge, with
a maximum active-power error equal to the full commanded step (10 kW) and an
integrated active-power error of 2.4×10^3 kW·s; the surviving operations are
predominantly on the reactive axis. Command *acceptance* thus decouples from
physical *effect* the moment a non-ideal field network is interposed.

**Interpretation and an explicit integrity caveat.** The near-zero, uniform,
delay/jitter/bandwidth-independent threshold indicates that this bimodal loss is
*not* a physical timing effect (1 ms cannot exhaust a 5 s SELECT-before-OPERATE
window) but a sensitivity of the DNP3 master's SELECT/OPERATE scheduling to any
departure from the default channel — i.e. an implementation characteristic of the
current NATIG transport rather than a fundamental property of grid control under
latency. We therefore treat it as a *reproducibility and robustness finding about
the co-simulation stack* that must be root-caused at the ns-3 source level before
any impairment magnitude (or the delay/loss/jitter contrast the campaign needs)
can be trusted, and before it can inform the EVG-under-mediation question. This is
reported transparently rather than as a headline grid result; hardening the DNP3
transport so that impairment factors are separable is a precondition of the
confirmatory campaign.

**Why the axis still matters for the EVG.** Independent of the specific stack
defect, the experiment demonstrates the qualitative point the workshop model could
not express: once commands must survive a real field network, *delivery itself
becomes contingent*, command acceptance decouples from physical effect, and both a
robustness floor (a static attacker loses commands it cannot anticipate) and a new
adaptive axis (an observation-driven attacker could route around delivery loss)
appear. Quantifying them is the object of the attacker campaign (G6) once the
transport is hardened.

**Scope and caveats.** These are *screening-tier* results establishing measurability
and reproducibility, not the pre-registered confirmatory campaign. Because the
current DNP3 transport is not robust to any perturbation, the delay/jitter/
bandwidth arms are presently indistinguishable; separating them requires resolving
the stack sensitivity above. Loss, outage, and bounded-congestion arms (the latter
via a Node[]/CSMA topology) complete the availability family in the full paper.
