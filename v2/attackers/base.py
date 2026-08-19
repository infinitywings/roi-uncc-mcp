"""Shared attacker base class for v2 experiments."""

from __future__ import annotations

import abc
import argparse
import asyncio
import json
import logging
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

EV_IDS = ["EV1", "EV2", "EV3", "EV4", "EV5", "EV6"]
MIN_POWER_KW = 500.0
MAX_POWER_KW = 1500.0

# Default LLM config (v2)
LLM_BASE_URL = "http://cci-siscluster1.charlotte.edu:8000/v1"
LLM_MODEL = "cyankiwi/Qwen3.5-122B-A10B-AWQ-4bit"


@dataclass
class AttackerConfig:
    mcp_url: str = "http://localhost:5100"
    observation_interval_sec: float = 5.0
    min_attack_cooldown_sec: float = 90.0
    max_attacks_per_hour: int = 20
    micro_score_threshold: int = 70
    controller_interval_sec: int = 10
    duration_sec: int = 300
    seed: int = 42
    output_dir: str = "v2/results"
    experiment_name: str = "experiment"


class AttackerBase(abc.ABC):
    """Base class for all attacker variants.

    Subclasses implement ``make_decision`` only.  The observe→decide→act loop,
    constraint enforcement, experiment lifecycle, and result serialisation live
    here so that every variant is compared on identical infrastructure.
    """

    attacker_type: str = "base"

    def __init__(self, config: AttackerConfig):
        self.config = config
        self.http = httpx.AsyncClient(timeout=300.0)
        random.seed(config.seed)

        self.last_attack_time = -config.min_attack_cooldown_sec
        self.attacks_this_hour = 0
        self.hour_start_time = 0.0

        self.attack_log: list[dict] = []
        self.interactions: list[dict] = []

    # ------------------------------------------------------------------
    # MCP helpers
    # ------------------------------------------------------------------
    async def call_tool(self, tool: str, params: dict | None = None) -> dict:
        resp = await self.http.post(f"{self.config.mcp_url}/tools/{tool}", json=params or {})
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Constraint enforcement (identical for all variants)
    # ------------------------------------------------------------------
    def can_attack(self, sim_time: float) -> tuple[bool, str]:
        elapsed = sim_time - self.last_attack_time
        if elapsed < self.config.min_attack_cooldown_sec:
            return False, f"Cooldown: {self.config.min_attack_cooldown_sec - elapsed:.1f}s"

        if sim_time - self.hour_start_time >= 3600:
            self.attacks_this_hour = 0
            self.hour_start_time = sim_time

        if self.attacks_this_hour >= self.config.max_attacks_per_hour:
            return False, "Budget exhausted"

        return True, "OK"

    # ------------------------------------------------------------------
    # Decision interface (subclass implements)
    # ------------------------------------------------------------------
    @abc.abstractmethod
    async def make_decision(self, analysis: dict, sim_time: float, can_attack: bool) -> dict:
        """Return ``{"decision": "attack"/"wait", "action": {...}, "reasoning": "..."}``."""
        ...

    def on_attack_executed(self, ev_id: str, power_kw: float, result: dict) -> None:
        """Hook called after a successful attack.  Override for strategic tracking."""

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    async def run(self) -> dict:
        cfg = self.config
        logger.info("Starting %s campaign: %s (duration=%ds, seed=%d)",
                     self.attacker_type, cfg.experiment_name, cfg.duration_sec, cfg.seed)

        # Warm-up observation
        await self.call_tool("observe", {})

        # Start experiment
        await self.http.post(f"{cfg.mcp_url}/experiment/start",
                             json={"experiment_id": cfg.experiment_name})

        elapsed = 0.0
        observation_count = 0

        while elapsed < cfg.duration_sec:
            observation_count += 1

            analysis = await self.call_tool(
                "analyze", {"controller_interval_sec": cfg.controller_interval_sec})

            sim_time = analysis.get("simulation_time_sec", elapsed)
            macro_score = analysis.get("macro_timing", {}).get("score", 0)
            micro_score = analysis.get("micro_timing", {}).get("score", 0)
            recommendation = analysis.get("combined", {}).get("recommendation", "WAIT")
            cycle_position = analysis.get("micro_timing", {}).get("cycle_position", 0.5)

            can, gate_reason = self.can_attack(sim_time)
            decision = await self.make_decision(analysis, sim_time, can)
            should_attack = decision.get("decision") in ("attack", "adjust") and "action" in decision

            if should_attack:
                action = decision["action"]
                ev_id = action.get("ev_id", "EV1")
                power_kw = action.get("real_kw", MAX_POWER_KW)

                logger.info("[%.0fs] ATTACK %s @ %.0fkW  (macro=%s micro=%s cycle=%.2f)",
                            elapsed, ev_id, power_kw, macro_score, micro_score, cycle_position)

                result = await self.call_tool("attack",
                                              {"ev_id": ev_id, "real_kw": power_kw})

                self.on_attack_executed(ev_id, power_kw, result)
                self.last_attack_time = sim_time
                self.attacks_this_hour += 1

                self.attack_log.append({
                    "elapsed": elapsed,
                    "sim_time": sim_time,
                    "action": action,
                    "reasoning": decision.get("reasoning", ""),
                    "macro_score": macro_score,
                    "micro_score": micro_score,
                    "cycle_position": cycle_position,
                    "result": result,
                })
            else:
                if observation_count % 12 == 0:
                    logger.info("[%.0fs] Observe  macro=%s micro=%s rec=%s can=%s",
                                elapsed, macro_score, micro_score, recommendation, can)

            await asyncio.sleep(cfg.observation_interval_sec)
            elapsed += cfg.observation_interval_sec

        # End experiment
        end_resp = await self.http.post(f"{cfg.mcp_url}/experiment/end", json={})
        final_metrics = end_resp.json().get("final_metrics", {})

        results = {
            "config": asdict(cfg),
            "start_time": datetime.now().isoformat(),
            "attacker_type": self.attacker_type,
            "total_observations": observation_count,
            "total_attacks": len(self.attack_log),
            "final_metrics": final_metrics,
            "attack_log": self.attack_log,
            "interactions": self.interactions,
        }

        # Save
        out_dir = Path(cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{cfg.experiment_name}.json"
        out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

        tvd = final_metrics.get("primary_metrics", {}).get("tvd_sec", 0.0)
        logger.info("Campaign complete: %s  attacks=%d  TVD=%.1fs",
                     out_path, len(self.attack_log), tvd)
        return results

    async def close(self) -> None:
        await self.http.aclose()


# ------------------------------------------------------------------
# Shared CLI argument parser
# ------------------------------------------------------------------
def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mcp-url", default="http://localhost:5100")
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--experiment-name", default=None)
    parser.add_argument("--output-dir", default="v2/results")
    parser.add_argument("--controller-interval", type=int, default=10)
