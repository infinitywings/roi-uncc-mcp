#!/usr/bin/env python3
"""Random Baseline Attacker — no timing intelligence, no strategy."""

from __future__ import annotations

import argparse
import asyncio
import random

from base import AttackerBase, AttackerConfig, EV_IDS, MIN_POWER_KW, MAX_POWER_KW, add_common_args


class RandomAttacker(AttackerBase):
    attacker_type = "random"

    def __init__(self, config: AttackerConfig, attack_probability: float = 0.3):
        super().__init__(config)
        self.attack_probability = attack_probability

    async def make_decision(self, analysis: dict, sim_time: float, can_attack: bool) -> dict:
        if not can_attack:
            return {"decision": "wait", "reasoning": "Cooldown or budget"}
        if random.random() < self.attack_probability:
            return {
                "decision": "attack",
                "reasoning": "Random coin flip",
                "action": {
                    "ev_id": random.choice(EV_IDS),
                    "real_kw": round(random.uniform(MIN_POWER_KW, MAX_POWER_KW), 1),
                },
            }
        return {"decision": "wait", "reasoning": "Coin flip: wait"}


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Random Baseline Attacker (v2)")
    add_common_args(parser)
    parser.add_argument("--attack-probability", type=float, default=0.3)
    args = parser.parse_args()

    cfg = AttackerConfig(
        mcp_url=args.mcp_url,
        duration_sec=args.duration,
        seed=args.seed,
        experiment_name=args.experiment_name or f"random_{args.duration}s_s{args.seed}",
        output_dir=args.output_dir,
        controller_interval_sec=args.controller_interval,
    )

    runner = RandomAttacker(cfg, attack_probability=args.attack_probability)
    try:
        await runner.run()
    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(_main())
