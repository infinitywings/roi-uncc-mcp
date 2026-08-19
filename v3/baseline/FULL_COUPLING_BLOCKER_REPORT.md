# Full-Coupling Benign Blocker Report

Date: 2026-07-29  
Verdict: **Reproducible first-minute FBS nonconvergence; G0 remains blocked**

## Question

Can the frozen-cadence GridPACK plus two-IEEE-123 federation complete a
benign, no-attacker trace in the campaign runtime before NATIG or OpenDER is
introduced?

## Exact test

The v3 runner used only temporary overlays and left v2 unchanged. It restored
the complete five-federate timing topology:

1. the retained GridPACK transmission executable;
2. IEEE-123 Feeder A at its source 60-second minimum timestep;
3. IEEE-123 Feeder B at its source 120-second minimum timestep;
4. a 60-second controller with the v2 Hour-7 first-grant protective action
   (EV3 through EV6 set to zero); and
5. an inert 5-second pacing federate matching the MCP/attacker participant.

No attack pulse was sent. The exact campaign image was
`roi-img:latest`, image ID
`sha256:86c0e62ec71478dfd5ef2e41a95a08b64a53603322fbd4661d0c4479b7549637`
and repository digest
`missingrain/roi-img@sha256:e16084eb7313c81fdb3731ef9ee8939165db53a377ec588b46866ab7a0e405c6`.

## Repeated result

Two independent create-once runs produced the same structural outcome:

- the controller received one physical observation at the first 60-second
  grant and sent the protective EV3-EV6 commands;
- the inert 5-second participant completed normally (`return code 0`);
- both feeders reported `convergence iteration limit reached for object
  meter:190` at simulation time 60 seconds and exited with return code 2;
- GridPACK propagated the federate error and aborted with return code -6; and
- no attack command preceded the failure.

The JSON files are not byte-identical because HELICS diagnostics contain wall
clock timestamps, generated core IDs, and container hostnames. The
machine-readable analysis confirms equal source, overlay, runner, controller
observation, return-code, failure-object, and failure-time signatures.

## Interpretation

This falsifies the immediate next gate: the retained full federation cannot
currently establish a benign first-minute baseline in its pinned campaign
runtime. The isolated Feeder A cadence repair remains valid component
evidence, but it cannot be promoted to full-system equivalence.

NATIG and OpenDER are not implicated in this failure and must not yet be added
to attack comparisons. Doing so would confound network/device effects with a
pre-existing numerical failure.

## Required resolution

The next experimental work must be a numerical root-cause study of the
GridPACK-to-GridLAB-D boundary at the first 60-second exchange. It should
capture the three received source-voltage phasors and feeder load
publications, replay them against each feeder independently, and identify the
smallest input or model transition that causes `meter:190` to fail. A repair
must then pass a no-attacker full trace twice before G0 can close.

Canonical evidence:

- `full_coupling_frozen60_nopulse_roi_pacer_r6/full_coupling_cadence_arm.json`
- `full_coupling_frozen60_nopulse_roi_pacer_r7/full_coupling_cadence_arm.json`
- `full_coupling_blocker_analysis_r1/full_coupling_blocker_analysis.json`
- `run_full_coupling_cadence_arm.py`
- `analyze_full_coupling_blocker.py`
