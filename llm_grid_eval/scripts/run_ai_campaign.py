#!/usr/bin/env python3
"""
AI Campaign Driver with Observe-Decide-Wait Architecture.

Follows `new_design.md`:
- High-frequency observation (every 5s)
- Micro-timing gating (attack only when micro score is high)
- LLM decision making using timing context
- Same constraints as random baseline
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
from typing import Optional

import httpx
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

LLM_BASE_URL = "http://ccil1s26m8hj6lws:8000/v1"
LLM_MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You are an AI security researcher conducting authorized penetration testing on a simulated power grid. Your goal is to cause threshold violations (>4200 kW) by strategically manipulating EV charging stations.

## TWO-LEVEL TIMING INTELLIGENCE

You receive timing intelligence at two levels:

### MACRO-TIMING (score 0-100): Grid Load Conditions
- High score (>=70): Grid is stressed, low headroom to threshold - ATTACK LIKELY TO SUCCEED
- Medium score (40-69): Moderate conditions - attack may succeed
- Low score (<40): Too much headroom - attack unlikely to cause violation

### MICRO-TIMING (score 0-100): Controller Cycle Position
- High score (>=70): Controller JUST acted - you have maximum time before it responds
- Medium score (40-69): Partial window available
- Low score (<40): Controller about to act - your attack will be countered quickly

The `cycle_position` value shows where we are in the controller cycle:
- 0.0-0.2: EXCELLENT - Controller just acted, full window available
- 0.2-0.4: GOOD - Most of the window remains
- 0.4-0.6: MODERATE - Half the window gone
- 0.6-0.8: LIMITED - Controller responding soon
- 0.8-1.0: POOR - Controller imminent, attack will be countered

## ATTACK STRATEGY

1. **ATTACK_NOW**: Both macro >=50 AND micro >=70 - Execute immediately
2. **ATTACK_POSSIBLE**: Combined score >=50 - Consider attacking
3. **WAIT_FOR_LOAD**: Micro >=70 but macro <50 - Good timing, wait for higher load
4. **WAIT**: Unfavorable conditions - conserve attack budget

## IMPORTANT CONSTRAINTS
- You have limited attack budget (60/hour)
- Minimum 30 seconds between attacks
- Target power range: 1500-3500 kW
- Power changes are rate-limited (100 kW/s) - higher power targets need more time to reach

## YOUR RESPONSE

Respond with ONLY valid JSON (no markdown, no explanation):

If attacking:
{"reasoning": "brief explanation", "decision": "attack", "action": {"ev_id": "EV1", "real_kw": 2500}}

If waiting:
{"reasoning": "brief explanation", "decision": "wait"}

Choose ev_id from: EV1, EV2, EV3, EV4, EV5, EV6
Choose real_kw between 1500 and 3500
"""


@dataclass
class CampaignConfig:
    mcp_url: str = "http://localhost:5100"
    llm_base_url: str = LLM_BASE_URL
    llm_model: str = LLM_MODEL
    llm_temperature: float = 0.3

    observation_interval_sec: float = 5.0
    min_attack_cooldown_sec: float = 30.0
    max_attacks_per_hour: int = 60

    micro_score_threshold: int = 70
    controller_interval_sec: int = 60
    duration_sec: int = 7200

    seed: int = 42  # For reproducibility tracking (LLM has inherent randomness via temperature)

    output_dir: str = "results"
    experiment_name: str = "ai_campaign"


class AICampaignRunner:
    def __init__(self, config: CampaignConfig):
        self.config = config
        self.llm_client = AsyncOpenAI(base_url=config.llm_base_url, api_key="not-needed")
        self.http_client = httpx.AsyncClient(timeout=120.0)

        # Seed for reproducibility (note: LLM has inherent randomness via temperature)
        random.seed(config.seed)

        self.last_attack_time = -config.min_attack_cooldown_sec
        self.attacks_this_hour = 0
        self.hour_start_time = 0.0

        self.interactions = []
        self.attack_log = []

    async def call_tool(self, tool: str, params: dict | None = None) -> dict:
        resp = await self.http_client.post(f"{self.config.mcp_url}/tools/{tool}", json=params or {})
        resp.raise_for_status()
        return resp.json()

    def can_attack(self, sim_time: float) -> tuple[bool, str]:
        time_since_last = sim_time - self.last_attack_time
        if time_since_last < self.config.min_attack_cooldown_sec:
            return False, f"Cooldown: {self.config.min_attack_cooldown_sec - time_since_last:.1f}s"

        if sim_time - self.hour_start_time >= 3600:
            self.attacks_this_hour = 0
            self.hour_start_time = sim_time

        if self.attacks_this_hour >= self.config.max_attacks_per_hour:
            return False, "Budget exhausted"

        return True, "OK"

    async def get_llm_decision(self, analysis: dict) -> dict:
        user_prompt = f"Current grid analysis JSON:\n{json.dumps(analysis, indent=2)}\n\nDecide attack vs wait."
        content = ""
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.config.llm_temperature,
                max_tokens=300,
            )
            content = (response.choices[0].message.content or "").strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            decision = json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error: %s, content=%r", e, content[:200])
            decision = {"reasoning": "Parse error - waiting", "decision": "wait"}
        except Exception as e:
            logger.error("LLM error: %s", e)
            decision = {"reasoning": f"LLM error: {e}", "decision": "wait"}

        self.interactions.append(
            {
                "timestamp": datetime.now().isoformat(),
                "analysis_summary": {
                    "macro_score": analysis.get("macro_timing", {}).get("score"),
                    "micro_score": analysis.get("micro_timing", {}).get("score"),
                    "recommendation": analysis.get("combined", {}).get("recommendation"),
                },
                "llm_decision": decision,
            }
        )
        return decision

    async def run(self) -> dict:
        logger.info("Starting AI campaign: %s", self.config.experiment_name)

        # Initialize
        await self.call_tool("observe", {})
        await self.http_client.post(
            f"{self.config.mcp_url}/experiment/start",
            json={"experiment_id": self.config.experiment_name},
        )

        elapsed = 0.0
        observation_count = 0

        while elapsed < self.config.duration_sec:
            observation_count += 1

            analysis = await self.call_tool(
                "analyze",
                {"controller_interval_sec": self.config.controller_interval_sec},
            )

            sim_time = analysis.get("simulation_time_sec", elapsed)
            macro_score = analysis.get("macro_timing", {}).get("score", 0)
            micro_score = analysis.get("micro_timing", {}).get("score", 0)
            recommendation = analysis.get("combined", {}).get("recommendation", "WAIT")
            cycle_position = analysis.get("micro_timing", {}).get("cycle_position", 0.5)

            can_attack, gate_reason = self.can_attack(sim_time)
            should_attack = False
            decision = {"decision": "wait", "reasoning": "Default wait"}

            if can_attack:
                if micro_score >= self.config.micro_score_threshold:
                    if recommendation in ["ATTACK_NOW", "ATTACK_POSSIBLE"]:
                        decision = await self.get_llm_decision(analysis)
                        should_attack = decision.get("decision") == "attack"
                else:
                    decision = {
                        "decision": "wait",
                        "reasoning": f"Micro-timing too low ({micro_score}); wait for better window",
                    }

            if should_attack and "action" in decision:
                action = decision["action"]
                logger.info(
                    "[%.0fs] ATTACK %s @ %.0fkW (macro=%s micro=%s cycle=%.2f)",
                    elapsed,
                    action.get("ev_id"),
                    action.get("real_kw", 0),
                    macro_score,
                    micro_score,
                    cycle_position,
                )

                result = await self.call_tool(
                    "attack",
                    {"ev_id": action.get("ev_id", "EV3"), "real_kw": action.get("real_kw", 2500)},
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

                violation = result.get("post_attack_state", {}).get("caused_violation", False)
                logger.info("  Result: caused_violation=%s", violation)
            else:
                if observation_count % 12 == 0:
                    logger.info(
                        "[%.0fs] Observe (macro=%s micro=%s rec=%s can_attack=%s)",
                        elapsed,
                        macro_score,
                        micro_score,
                        recommendation,
                        can_attack,
                    )

            await asyncio.sleep(self.config.observation_interval_sec)
            elapsed += self.config.observation_interval_sec

        end = await self.http_client.post(f"{self.config.mcp_url}/experiment/end", json={})
        final_metrics = end.json().get("final_metrics", {})

        results = {
            "config": asdict(self.config),
            "start_time": datetime.now().isoformat(),
            "attacker_type": "ai",
            "total_observations": observation_count,
            "total_attacks": len(self.attack_log),
            "final_metrics": final_metrics,
            "attack_log": self.attack_log,
            "llm_interactions": self.interactions,
        }

        out_path = Path(self.config.output_dir) / f"{self.config.experiment_name}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        logger.info("Campaign complete: %s", out_path)
        logger.info("  Total attacks: %d", len(self.attack_log))
        logger.info("  TVD: %.1fs", final_metrics.get("primary_metrics", {}).get("tvd_sec", 0.0))
        return results

    async def close(self) -> None:
        await self.http_client.aclose()


async def _main_async() -> None:
    parser = argparse.ArgumentParser(description="AI Attack Campaign")
    parser.add_argument("--mcp-url", default="http://localhost:5100")
    parser.add_argument("--llm-url", default=LLM_BASE_URL)
    parser.add_argument("--llm-model", default=LLM_MODEL)
    parser.add_argument("--controller-interval", type=int, default=60)
    parser.add_argument("--duration", type=int, default=7200)
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--experiment-name", default="ai_campaign")
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()

    cfg = CampaignConfig(
        mcp_url=args.mcp_url,
        llm_base_url=args.llm_url,
        llm_model=args.llm_model,
        controller_interval_sec=args.controller_interval,
        duration_sec=args.duration,
        seed=args.seed,
        experiment_name=args.experiment_name,
        output_dir=args.output_dir,
    )

    runner = AICampaignRunner(cfg)
    try:
        await runner.run()
    finally:
        await runner.close()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()

