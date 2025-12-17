#!/usr/bin/env python3
"""Random baseline attacker for comparison with AI attacker."""

from __future__ import annotations

import argparse
import json
import random
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("America/New_York")

EV_IDS = ["EV1", "EV2", "EV3", "EV4", "EV5", "EV6"]
MIN_ATTACK_KW = 1500
MAX_ATTACK_KW = 3500
ATTACK_PROBABILITY = 0.3


def fetch_grid_state(primitive_url: str) -> Dict[str, Any]:
    resp = requests.post(primitive_url, json={"method": "get_grid_status", "params": {}}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_attack(primitive_url: str, ev_id: str, real_kw: float, metadata: Dict[str, Any]) -> Dict[str, Any]:
    params = {
        "ev_id": ev_id,
        "real_power_kw": real_kw,
        "reactive_power_kvar": 0,
        "metadata": metadata,
    }
    resp = requests.post(primitive_url, json={"method": "set_ev_capacity", "params": params}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def log_event(log_path: Path, event: Dict[str, Any]):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(event, default=str) + "\n")


def wait_for_server(base_url: str, timeout: int):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.post(base_url, json={"method": "get_grid_status", "params": {}}, timeout=5)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError(f"Server not ready after {timeout}s")


def run_random_baseline(args: argparse.Namespace):
    log_path = Path(args.log)
    results_path = Path(args.results)

    random.seed(args.seed)

    log_event(
        log_path,
        {
            "event": "campaign_start",
            "timestamp": datetime.now(TZ).isoformat(),
            "attacker_type": "random_baseline",
            "config": vars(args),
        },
    )

    wait_for_server(args.server, args.wait)

    step = 0
    start_sim_time = None
    total_attacks = 0
    successful_attacks = 0
    total_violation_duration = 0.0
    attack_outcomes: List[Dict[str, Any]] = []

    while True:
        step += 1
        try:
            grid_state = fetch_grid_state(args.server)
        except Exception as e:
            log_event(log_path, {"event": "fetch_error", "step": step, "error": str(e)})
            time.sleep(args.interval)
            continue

        result = grid_state.get("result", {})
        sim_time = result.get("simulation_time_sec", 0)
        if start_sim_time is None:
            start_sim_time = sim_time

        if args.duration_seconds > 0 and (sim_time - start_sim_time) >= args.duration_seconds:
            break
        if args.steps > 0 and step > args.steps:
            break

        current_load = result.get("system_metrics", {}).get("total_real_power_kw", 0)
        threshold = result.get("system_metrics", {}).get("threshold_kw", 4200)

        log_event(
            log_path,
            {"event": "observation", "step": step, "simulation_time_sec": sim_time, "total_load_kw": current_load},
        )

        if random.random() < ATTACK_PROBABILITY:
            ev_id = random.choice(EV_IDS)
            real_kw = random.uniform(MIN_ATTACK_KW, MAX_ATTACK_KW)
            interaction_id = str(uuid.uuid4())
            metadata = {"interaction_id": interaction_id, "step": step, "attacker_type": "random"}
            try:
                pre_load = current_load
                attack_result = send_attack(args.server, ev_id, real_kw, metadata)
                time.sleep(2)
                post_state = fetch_grid_state(args.server)
                post_load = post_state.get("result", {}).get("system_metrics", {}).get("total_real_power_kw", 0)

                caused_violation = post_load > threshold
                total_attacks += 1
                if caused_violation:
                    successful_attacks += 1
                    total_violation_duration += args.interval

                outcome = {
                    "timestamp": datetime.now(TZ).isoformat(),
                    "ev_id": ev_id,
                    "real_kw": real_kw,
                    "pre_load_kw": pre_load,
                    "post_load_kw": post_load,
                    "caused_violation": caused_violation,
                }
                attack_outcomes.append(outcome)

                log_event(
                    log_path,
                    {
                        "event": "attack_executed",
                        "step": step,
                        "interaction_id": interaction_id,
                        "ev_id": ev_id,
                        "real_kw": real_kw,
                        "outcome": outcome,
                        "attack_result": attack_result,
                    },
                )
            except Exception as e:
                total_attacks += 1
                log_event(log_path, {"event": "attack_failed", "step": step, "ev_id": ev_id, "error": str(e)})
        else:
            log_event(log_path, {"event": "attack_skipped", "step": step, "reason": "random_decision"})

        time.sleep(args.interval)

    final_results = {
        "experiment_name": args.experiment_name,
        "attacker_type": "random_baseline",
        "seed": args.seed,
        "total_attacks": total_attacks,
        "successful_attacks": successful_attacks,
        "success_rate": (successful_attacks / total_attacks * 100) if total_attacks > 0 else 0,
        "total_violation_duration_sec": total_violation_duration,
        "attack_outcomes": attack_outcomes,
    }

    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("w") as f:
        json.dump(final_results, f, indent=2, default=str)

    log_event(log_path, {"event": "campaign_complete", "results": final_results})

    print("\nRandom baseline complete!")
    print(f"Total attacks: {total_attacks}")
    print(f"Successful: {successful_attacks}")
    print(f"Success rate: {final_results['success_rate']:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Random baseline attacker")
    parser.add_argument("--server", default="http://localhost:5100/primitive")
    parser.add_argument("--wait", type=int, default=120)
    parser.add_argument("--steps", type=int, default=0)
    parser.add_argument("--duration-seconds", type=int, default=86400)
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--experiment-name", default="random_baseline")
    parser.add_argument("--log", default="logs/random_baseline.log")
    parser.add_argument("--results", default="results/random_baseline_results.json")
    args = parser.parse_args()
    run_random_baseline(args)


if __name__ == "__main__":
    main()
