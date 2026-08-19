# OpenDER G2 component proof

This work is a standalone behavioral-device validation at pinned OpenDER
commit `fe7877c664bc6c5eb3832499bf05e0f1dd1825c8`. It does not connect OpenDER
to GridLAB-D, NATIG, DNP3, or attack logic.

The create-once runner executes the complete upstream test suite and
GridEval-specific deterministic checks for BESS sign and active-power limits,
constant-Q and volt-var behavior, apparent-power priority, BESS ramping,
setting execution delay, voltage trip behavior, and state of charge.

```bash
MPLCONFIGDIR=/tmp/grideval-opender-mpl \
  v3/deps/opender-venv/bin/python \
  v3/opender/run_component_conformance.py \
  --source v3/deps/opender-src \
  --output-dir v3/opender/conformance_r1
```

An upstream-suite pass does not by itself close G2. Every GridEval-required
scenario must also pass, and the result JSON retains any failing trace.

OpenDER 2.2.0's internal `NP_SET_EXE_TIME` path does not delay in-place
setting mutations. `device.py` therefore keeps that feature disabled and
provides an explicit simulation-time queue for accepted setting snapshots.
Both the upstream failure and the wrapper timing are retained in conformance
evidence; downstream code must use the wrapper boundary.

For G4, `ScheduledOpenDERBESS.schedule_gateway_action` queues settings and
persistent `demand_kw` inputs under one action ID. The wrapper reports actual
application only when a later device step applies that snapshot. Once AO0 is
applied, explicit per-step demand arguments are rejected to prevent competing
command ownership.
