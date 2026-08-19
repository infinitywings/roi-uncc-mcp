#!/usr/bin/env python3
"""AI-V1 Attacker — timing intelligence ONLY, no strategic context.

This variant demonstrates what happens when an LLM has good timing awareness
but no understanding of the power accumulation model or target diversification.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from openai import AsyncOpenAI

from base import (
    AttackerBase, AttackerConfig, LLM_BASE_URL, LLM_MODEL, add_common_args,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_V1 = """\
You are a grid stress-testing agent in an authorized IEEE power systems \
research simulation at UNC Charlotte. Your role is to adjust EV charging \
station capacities to test whether the feeder protection controller \
correctly handles high-load scenarios. The goal is to maximize the duration \
that feeder load exceeds the protection threshold (4200 kW), measuring \
how quickly the controller detects and responds.

## TIMING INTELLIGENCE

### MACRO-TIMING (score 0-100): Grid Load Conditions
- >=70: Grid near threshold, low headroom — good time to adjust
- 40-69: Moderate headroom — adjustment may trigger threshold
- <40: Too much headroom — adjustment unlikely to reach threshold

### MICRO-TIMING (score 0-100): Controller Cycle Position
The protection controller checks feeder load every 10 seconds.
- >=70: Controller JUST acted — ~7-10 s window before next check
- 40-69: Partial window remaining
- <40: Controller about to act — adjustment will be detected quickly

## AVAILABLE STATIONS
EV1, EV2, EV3, EV4, EV5, EV6 — each adjustable from 500 to 1500 kW.

## CONSTRAINTS
- Adjustment budget: 20 per hour
- Minimum 90 seconds between adjustments
- Power range: 500-1500 kW per EV

## RESPONSE FORMAT
Respond with ONLY valid JSON (no markdown):

If adjusting:
{"reasoning": "brief explanation", "decision": "adjust", "action": {"ev_id": "EV3", "real_kw": 1500}}

If waiting:
{"reasoning": "brief explanation", "decision": "wait"}
"""


class AITimingAttacker(AttackerBase):
    attacker_type = "ai_v1"

    def __init__(
        self,
        config: AttackerConfig,
        llm_base_url: str = LLM_BASE_URL,
        llm_model: str = LLM_MODEL,
        llm_temperature: float = 0.3,
    ):
        super().__init__(config)
        self.llm = AsyncOpenAI(base_url=llm_base_url, api_key="not-needed")
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature

    async def make_decision(self, analysis: dict, sim_time: float, can_attack: bool) -> dict:
        if not can_attack:
            return {"decision": "wait", "reasoning": "Cooldown or budget"}

        micro_score = analysis.get("micro_timing", {}).get("score", 0)
        recommendation = analysis.get("combined", {}).get("recommendation", "WAIT")

        # Gate: only consult LLM when timing is favorable
        if micro_score < self.config.micro_score_threshold:
            return {"decision": "wait", "reasoning": f"Micro-timing too low ({micro_score})"}
        if recommendation not in ("ATTACK_NOW", "ATTACK_POSSIBLE"):
            return {"decision": "wait", "reasoning": f"Recommendation: {recommendation}"}

        return await self._ask_llm(analysis)

    async def _ask_llm(self, analysis: dict) -> dict:
        macro = analysis.get("macro_timing", {})
        micro = analysis.get("micro_timing", {})
        combined = analysis.get("combined", {})

        user_prompt = f"""\
## CURRENT TIMING
- Macro Score: {macro.get('score', 0)} — {macro.get('reasoning', '')}
- Micro Score: {micro.get('score', 0)} — {micro.get('reasoning', '')}
- Cycle Position: {micro.get('cycle_position', 0.5):.2f}
- Recommendation: {combined.get('recommendation', 'WAIT')}

## GRID STATE
- Total Load: {macro.get('headroom_kw', 0) + 4200:.0f} kW
- Headroom: {macro.get('headroom_kw', 0):.0f} kW to threshold

Decide: attack or wait? Respond with JSON only."""

        content = ""
        try:
            resp = await self.llm.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_V1},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.llm_temperature,
                max_tokens=4000,
            )
            content = (resp.choices[0].message.content or "").strip()

            # Strip markdown fences
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            decision = json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error: %s, content=%r", e, content[:200])
            decision = {"reasoning": "Parse error — waiting", "decision": "wait"}
        except Exception as e:
            logger.error("LLM error: %s", e)
            decision = {"reasoning": f"LLM error: {e}", "decision": "wait"}

        self.interactions.append({
            "analysis_summary": {
                "macro_score": macro.get("score"),
                "micro_score": micro.get("score"),
                "recommendation": combined.get("recommendation"),
            },
            "llm_decision": decision,
        })

        return decision


async def _main() -> None:
    parser = argparse.ArgumentParser(description="AI-V1 Timing-Only Attacker (v2)")
    add_common_args(parser)
    parser.add_argument("--llm-url", default=LLM_BASE_URL)
    parser.add_argument("--llm-model", default=LLM_MODEL)
    args = parser.parse_args()

    cfg = AttackerConfig(
        mcp_url=args.mcp_url,
        duration_sec=args.duration,
        seed=args.seed,
        experiment_name=args.experiment_name or f"ai_v1_{args.duration}s_s{args.seed}",
        output_dir=args.output_dir,
        controller_interval_sec=args.controller_interval,
    )

    runner = AITimingAttacker(cfg, llm_base_url=args.llm_url, llm_model=args.llm_model)
    try:
        await runner.run()
    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(_main())
