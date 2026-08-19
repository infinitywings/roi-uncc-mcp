#!/usr/bin/env python3
"""Measure controller-loop grant behavior in the pinned HELICS runtime.

Run this inside the local docker-cosim image, which supplies HELICS 3.6.1.
The probe intentionally uses a single federate: it isolates HELICS period and
request semantics from GridLAB-D, GridPACK, attacker, and network behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import helics as h


CONDITIONS = (
    {
        "name": "frozen_v2_loop",
        "period_s": 60,
        "initial_grant_s": -1,
        "description": "Frozen v2 sentinel and guarded request loop.",
    },
    {
        "name": "period10_only",
        "period_s": 10,
        "initial_grant_s": -1,
        "description": "Only change period to 10; retain frozen sentinel.",
    },
    {
        "name": "repaired_period10_loop",
        "period_s": 10,
        "initial_grant_s": 0,
        "description": (
            "Initialize at HELICS current time 0, then request each later "
            "10-second decision time."
        ),
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_condition(
    condition: dict[str, Any], duration_s: int, interval_s: int
) -> dict[str, Any]:
    name = condition["name"]
    broker_name = f"{name}_broker"
    broker = h.helicsCreateBroker("zmq", broker_name, "-f 1")
    fi = h.helicsCreateFederateInfo()
    h.helicsFederateInfoSetCoreTypeFromString(fi, "zmq")
    h.helicsFederateInfoSetCoreInitString(
        fi, f"--federates=1 --broker={broker_name}"
    )
    h.helicsFederateInfoSetTimeProperty(
        fi, h.HELICS_PROPERTY_TIME_PERIOD, float(condition["period_s"])
    )
    fed = h.helicsCreateValueFederate(f"{name}_federate", fi)
    h.helicsFederateEnterExecutingMode(fed)

    granted = float(condition["initial_grant_s"])
    events = []
    for logical_t in range(0, duration_s, interval_s):
        requested_t = None
        grant_before = granted
        if granted < logical_t:
            requested_t = logical_t
            granted = float(h.helicsFederateRequestTime(fed, logical_t))
        events.append(
            {
                "logical_decision_time_s": logical_t,
                "grant_before_s": grant_before,
                "requested_time_s": requested_t,
                "granted_time_s": granted,
            }
        )

    h.helicsFederateFinalize(fed)
    h.helicsFederateFree(fed)
    h.helicsBrokerDisconnect(broker)
    h.helicsBrokerFree(broker)

    counts = Counter(event["granted_time_s"] for event in events)
    request_events = [
        event for event in events if event["requested_time_s"] is not None
    ]
    return {
        **condition,
        "events": events,
        "request_count": len(request_events),
        "distinct_grant_count": len(counts),
        "decisions_per_grant": {
            str(int(grant)): count for grant, count in sorted(counts.items())
        },
        "all_post_start_decisions_have_matching_grant": all(
            event["logical_decision_time_s"] == event["granted_time_s"]
            for event in events
            if event["logical_decision_time_s"] > 0
        ),
        "max_decisions_at_one_grant": max(counts.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    script_path = Path(__file__).resolve()
    results = [
        run_condition(condition, args.duration, args.interval)
        for condition in CONDITIONS
    ]

    payload = {
        "schema_version": "1.0",
        "probe": "GridEval controller cadence",
        "helics_version": h.helicsGetVersion(),
        "duration_s": args.duration,
        "logical_interval_s": args.interval,
        "script_sha256_before_run": sha256(script_path),
        "conditions": results,
        "interpretation": {
            "frozen_v2_loop": (
                "The frozen loop groups multiple 10-second logical decisions "
                "at each 60-second HELICS grant."
            ),
            "period10_only": (
                "Changing period alone leaves the t=0 sentinel request and "
                "groups t=0 and t=10 at the first grant."
            ),
            "repaired_period10_loop": (
                "Initializing at current time 0 gives t=0 one initial decision "
                "and aligns every later logical decision with its own grant."
            ),
            "scope": (
                "This isolates time-grant semantics. A two-federate physical "
                "pulse test remains required to validate fresh input and "
                "downstream actuation at each grant."
            ),
        },
    }
    output_path = output_dir / "cadence_probe.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {output_path}")
    for result in results:
        print(
            f"{result['name']}: requests={result['request_count']} "
            f"grants={result['distinct_grant_count']} "
            f"max_decisions_per_grant={result['max_decisions_at_one_grant']} "
            "post_start_aligned="
            f"{result['all_post_start_decisions_have_matching_grant']}"
        )
    h.helicsCloseLibrary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
