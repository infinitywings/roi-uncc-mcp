#!/usr/bin/env python3
"""
Random Baseline Driver - Same constraints, no timing intelligence.

The ONLY difference vs AI campaign is the decision logic.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

EV_IDS = ["EV1", "EV2", "EV3", "EV4", "EV5", "EV6"]
# Original power range restored - rate-limited ramping prevents GridLAB-D crashes
MIN_POWER_KW = 1500.0
MAX_POWER_KW = 3500.0


@dataclass
class BaselineConfig:
    mcp_url: str = "http://localhost:5100"

    observation_interval_sec: float = 5.0
    min_attack_cooldown_sec: float = 30.0
    max_attacks_per_hour: int = 60

    attack_probability: float = 0.3

    duration_sec: int = 7200
    seed: int = 42

    output_dir: str = "results"
    experiment_name: str = "random_baseline"


class RandomBaselineRunner:
    def __init__(self, config: BaselineConfig):
        self.config = config
        self.http_client = httpx.AsyncClient(timeout=120.0)
        random.seed(config.seed)

        self.last_attack_time = -config.min_attack_cooldown_sec
        self.attacks_this_hour = 0
        self.hour_start_time = 0.0

        self.attack_log = []

    async def call_tool(self, tool: str, params: dict | None = None) -> dict:
        resp = await self.http_client.post(f"{self.config.mcp_url}/tools/{tool}", json=params or {})
        resp.raise_for_status()
        return resp.json()

    def can_attack(self, sim_time: float) -> tuple[bool, str]:
        time_since_last = sim_time - self.last_attack_time
        if time_since_last < self.config.min_attack_cooldown_sec:
            return False, "Cooldown"

        if sim_time - self.hour_start_time >= 3600:
            self.attacks_this_hour = 0
            self.hour_start_time = sim_time

        if self.attacks_this_hour >= self.config.max_attacks_per_hour:
            return False, "Budget"

        return True, "OK"

    def make_random_decision(self) -> dict:
        if random.random() < self.config.attack_probability:
            return {
                "decision": "attack",
                "action": {
                    "ev_id": random.choice(EV_IDS),
                    "real_kw": random.uniform(MIN_POWER_KW, MAX_POWER_KW),
                },
            }
        return {"decision": "wait"}

    async def run(self) -> dict:
        logger.info("Starting random baseline: %s", self.config.experiment_name)

        await self.call_tool("observe", {})
        await self.http_client.post(
            f"{self.config.mcp_url}/experiment/start",
            json={"experiment_id": self.config.experiment_name},
        )

        elapsed = 0.0
        observation_count = 0

        while elapsed < self.config.duration_sec:
            observation_count += 1

            analysis = await self.call_tool("analyze", {})
            sim_time = analysis.get("simulation_time_sec", elapsed)

            macro_score = analysis.get("macro_timing", {}).get("score", 0)
            micro_score = analysis.get("micro_timing", {}).get("score", 0)
            cycle_position = analysis.get("micro_timing", {}).get("cycle_position", 0.5)

            can_attack, _ = self.can_attack(sim_time)
            if can_attack:
                decision = self.make_random_decision()
            else:
                decision = {"decision": "wait"}

            if decision.get("decision") == "attack" and "action" in decision:
                action = decision["action"]
                logger.info(
                    "[%.0fs] ATTACK %s @ %.0fkW (macro=%s micro=%s - IGNORED)",
                    elapsed,
                    action["ev_id"],
                    action["real_kw"],
                    macro_score,
                    micro_score,
                )
                result = await self.call_tool(
                    "attack",
                    {"ev_id": action["ev_id"], "real_kw": action["real_kw"]},
                )

                self.last_attack_time = sim_time
                self.attacks_this_hour += 1
                self.attack_log.append(
                    {
                        "elapsed": elapsed,
                        "sim_time": sim_time,
                        "action": action,
                        "macro_score": macro_score,
                        "micro_score": micro_score,
                        "cycle_position": cycle_position,
                        "result": result,
                    }
                )

            await asyncio.sleep(self.config.observation_interval_sec)
            elapsed += self.config.observation_interval_sec

        end = await self.http_client.post(f"{self.config.mcp_url}/experiment/end", json={})
        final_metrics = end.json().get("final_metrics", {})

        results = {
            "config": asdict(self.config),
            "start_time": datetime.now().isoformat(),
            "attacker_type": "random",
            "total_observations": observation_count,
            "total_attacks": len(self.attack_log),
            "final_metrics": final_metrics,
            "attack_log": self.attack_log,
        }

        out_path = Path(self.config.output_dir) / f"{self.config.experiment_name}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        logger.info("Baseline complete: %s", out_path)
        logger.info("  Total attacks: %d", len(self.attack_log))
        logger.info("  TVD: %.1fs", final_metrics.get("primary_metrics", {}).get("tvd_sec", 0.0))
        return results

    async def close(self) -> None:
        await self.http_client.aclose()


async def _main_async() -> None:
    parser = argparse.ArgumentParser(description="Random Attack Baseline")
    parser.add_argument("--mcp-url", default="http://localhost:5100")
    parser.add_argument("--duration", type=int, default=7200)
    parser.add_argument("--attack-probability", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--experiment-name", default="random_baseline")
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()

    cfg = BaselineConfig(
        mcp_url=args.mcp_url,
        duration_sec=args.duration,
        attack_probability=args.attack_probability,
        seed=args.seed,
        experiment_name=args.experiment_name,
        output_dir=args.output_dir,
    )

    runner = RandomBaselineRunner(cfg)
    try:
        await runner.run()
    finally:
        await runner.close()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
