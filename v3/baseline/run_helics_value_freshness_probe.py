#!/usr/bin/env python3
"""Two-federate HELICS probe for controller input freshness.

A 10-second plant federate publishes a monotonically increasing sample ID.
A controller federate executes either the frozen v2 loop (period 60) or the
repaired loop (period 10, initial decision at current time zero). The result
measures which physical-side samples each logical controller decision sees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import queue
from collections import Counter
from pathlib import Path
from typing import Any

import helics as h


CONDITIONS = (
    {
        "name": "frozen_v2_loop",
        "controller_period_s": 60,
        "initial_grant_s": -1,
    },
    {
        "name": "repaired_period10_loop",
        "controller_period_s": 10,
        "initial_grant_s": 0,
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def federate_info(broker_address: str, period_s: int) -> Any:
    fi = h.helicsCreateFederateInfo()
    h.helicsFederateInfoSetCoreTypeFromString(fi, "zmq")
    h.helicsFederateInfoSetCoreInitString(fi, "--federates=1")
    h.helicsFederateInfoSetBroker(fi, broker_address)
    h.helicsFederateInfoSetTimeProperty(
        fi, h.HELICS_PROPERTY_TIME_PERIOD, float(period_s)
    )
    return fi


def plant_worker(
    broker_name: str,
    broker_address: str,
    duration_s: int,
    interval_s: int,
    result_queue: Any,
) -> None:
    try:
        fed = h.helicsCreateValueFederate(
            f"{broker_name}_plant", federate_info(broker_address, interval_s)
        )
        publication = h.helicsFederateRegisterGlobalTypePublication(
            fed, f"{broker_name}/sample_id", "int", ""
        )
        h.helicsFederateEnterExecutingMode(fed)
        events = []

        h.helicsPublicationPublishInteger(publication, 0)
        events.append({"granted_time_s": 0.0, "published_sample_id": 0})
        for target in range(interval_s, duration_s + 1, interval_s):
            grant = float(h.helicsFederateRequestTime(fed, target))
            sample_id = target // interval_s
            h.helicsPublicationPublishInteger(publication, sample_id)
            events.append(
                {
                    "granted_time_s": grant,
                    "published_sample_id": sample_id,
                }
            )

        h.helicsFederateFinalize(fed)
        h.helicsFederateFree(fed)
        result_queue.put({"role": "plant", "events": events})
    except Exception as exc:
        result_queue.put(
            {"role": "plant", "error": f"{type(exc).__name__}: {exc}"}
        )
        raise


def controller_worker(
    broker_name: str,
    broker_address: str,
    condition: dict[str, Any],
    duration_s: int,
    interval_s: int,
    result_queue: Any,
) -> None:
    try:
        fed = h.helicsCreateValueFederate(
            f"{broker_name}_controller",
            federate_info(
                broker_address, int(condition["controller_period_s"])
            ),
        )
        subscription = h.helicsFederateRegisterSubscription(
            fed, f"{broker_name}/sample_id", ""
        )
        h.helicsInputSetDefaultInteger(subscription, -1)
        h.helicsFederateEnterExecutingMode(fed)

        granted = float(condition["initial_grant_s"])
        events = []
        for logical_t in range(0, duration_s, interval_s):
            requested_t = None
            if granted < logical_t:
                requested_t = logical_t
                granted = float(h.helicsFederateRequestTime(fed, logical_t))
            events.append(
                {
                    "logical_decision_time_s": logical_t,
                    "requested_time_s": requested_t,
                    "granted_time_s": granted,
                    "input_updated": bool(h.helicsInputIsUpdated(subscription)),
                    "observed_sample_id": int(
                        h.helicsInputGetInteger(subscription)
                    ),
                }
            )

        if granted < duration_s:
            h.helicsFederateRequestTime(fed, duration_s)
        h.helicsFederateFinalize(fed)
        h.helicsFederateFree(fed)
        result_queue.put({"role": "controller", "events": events})
    except Exception as exc:
        result_queue.put(
            {"role": "controller", "error": f"{type(exc).__name__}: {exc}"}
        )
        raise


def run_condition(
    condition: dict[str, Any], duration_s: int, interval_s: int
) -> dict[str, Any]:
    broker_name = f"freshness_{condition['name']}"
    broker = h.helicsCreateBroker("zmq", broker_name, "-f 2")
    broker_address = h.helicsBrokerGetAddress(broker)
    context = mp.get_context("spawn")
    result_queue = context.Queue()
    plant = context.Process(
        target=plant_worker,
        args=(
            broker_name,
            broker_address,
            duration_s,
            interval_s,
            result_queue,
        ),
    )
    controller = context.Process(
        target=controller_worker,
        args=(
            broker_name,
            broker_address,
            condition,
            duration_s,
            interval_s,
            result_queue,
        ),
    )
    plant.start()
    controller.start()
    plant.join(30)
    controller.join(30)
    if plant.is_alive() or controller.is_alive():
        for process in (plant, controller):
            if process.is_alive():
                process.terminate()
                process.join(5)
        raise RuntimeError(f"{condition['name']} timed out")
    if plant.exitcode != 0 or controller.exitcode != 0:
        raise RuntimeError(
            f"{condition['name']} process failure: "
            f"plant={plant.exitcode}, controller={controller.exitcode}"
        )

    results = {}
    for _ in range(2):
        try:
            item = result_queue.get(timeout=5)
        except queue.Empty as exc:
            raise RuntimeError(f"{condition['name']} missing child result") from exc
        results[item["role"]] = item
    h.helicsBrokerDisconnect(broker)
    h.helicsBrokerFree(broker)

    if "error" in results["plant"] or "error" in results["controller"]:
        raise RuntimeError(f"{condition['name']} worker error: {results}")
    controller_events = results["controller"]["events"]
    samples = [event["observed_sample_id"] for event in controller_events]
    grants = [event["granted_time_s"] for event in controller_events]
    repeated_adjacent_samples = sum(
        current == previous
        for previous, current in zip(samples, samples[1:])
    )
    grant_counts = Counter(grants)
    return {
        **condition,
        "plant_events": results["plant"]["events"],
        "controller_events": controller_events,
        "controller_decision_count": len(controller_events),
        "distinct_observed_sample_count": len(set(samples) - {-1}),
        "default_sample_observation_count": samples.count(-1),
        "repeated_adjacent_sample_count": repeated_adjacent_samples,
        "max_decisions_at_one_grant": max(grant_counts.values()),
        "observed_sample_sequence": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    conditions = [
        run_condition(condition, args.duration, args.interval)
        for condition in CONDITIONS
    ]
    payload = {
        "schema_version": "1.0",
        "probe": "GridEval controller value freshness",
        "helics_version": h.helicsGetVersion(),
        "duration_s": args.duration,
        "plant_period_s": args.interval,
        "logical_controller_interval_s": args.interval,
        "script_sha256_before_run": sha256(Path(__file__).resolve()),
        "conditions": conditions,
        "interpretation_scope": (
            "This proves HELICS value delivery and input freshness with a "
            "synthetic monotonic plant publication. It does not substitute "
            "for a GridLAB-D power/actuation trace."
        ),
    }
    output_path = output_dir / "value_freshness_probe.json"
    output_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {output_path}")
    for condition in conditions:
        print(
            f"{condition['name']}: distinct_samples="
            f"{condition['distinct_observed_sample_count']} "
            f"repeated_adjacent={condition['repeated_adjacent_sample_count']} "
            f"max_decisions_per_grant="
            f"{condition['max_decisions_at_one_grant']}"
        )
    h.helicsCloseLibrary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
