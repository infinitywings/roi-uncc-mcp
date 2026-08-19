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

## 6. Results — Network Mediation and Device Behavior

The expansion adds two realism layers to the workshop's direct-HELICS, ideal-
setpoint study, and we report what each establishes on the immutable NATIG r24
runtime (seed 777, 840 s, one OpenDER BESS at l92, 10 s cadence).

**Benign network equivalence (established).** With no attacker and no impairment,
the DNP3-over-ns-3 path reproduces the direct control path's accepted command
sequence and steady physical response within a frozen tolerance on the identical
runtime (all 18 remote-DER SELECT/OPERATE operations delivered and applied;
per-sample active/reactive/voltage/SOC residuals below the equivalence bounds).
This licenses the network-mediated arm as a faithful substrate *at the nominal
channel* and cleanly separates "the network carried the command" from "the device
tracked it."

**Device behavior (OpenDER, established).** Replacing the linear additive EV load
with a pinned IEEE-1547 OpenDER BESS makes the device layer standards-based:
active-power limiting, ramp limits, autonomous volt-var, ride-through/trip, and
SOC bounds. Identical accepted remote settings can therefore produce different
physical outcomes depending on the device's autonomous functions — an axis the
linear model cannot express and the basis for the device-autonomy contrasts.

**Network impairment (deferred — a co-simulation-stack limitation).** We attempted
to screen delay/jitter/bandwidth on the DNP3/ns-3 path and uncovered a limitation
of the current NATIG transport rather than a grid result: command delivery is
*bimodal*. The path delivers all 18 remote-DER OPERATEs only at the exact nominal
channel; under **any** modeled non-ideality (a delay as small as 1 ms, bounded
jitter, or a few-kb/s bandwidth cap) it deterministically drops a fixed subset of
8 OPERATEs inside the ns-3/DNP3 transport, reducing delivered control authority to
10 of 18. Because the effect is threshold-near-zero, magnitude-independent, and
does not survive a controller-schedule workaround, it reflects a timing defect in
the simulated DNP3 master's poll/control interleaving, not the physics of DER
control under latency. We report it transparently as a **reproducibility and
robustness finding about the co-simulation stack**, and defer quantitative
network-impairment (and the EVG-under-mediation question) until the transport is
hardened so impairment factors are separable. This is a precondition of the
confirmatory campaign and is called out explicitly rather than reported as a
grid-physics result.

**Net expansion.** Relative to the workshop paper, the contribution deepens along
two established axes — a faithful (at nominal) explicit DNP3/ns-3 cyber substrate
and a standards-based IEEE-1547 device layer — plus a corrected, hardened
statistical treatment of the direct-path EVG. The impairment and attacker-under-
mediation arms are scoped as future work behind a hardened NATIG transport.
