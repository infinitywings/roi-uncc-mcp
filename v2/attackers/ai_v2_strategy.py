#!/usr/bin/env python3
"""AI-V2 Attacker — timing intelligence PLUS strategic domain knowledge.

Extends V1 with:
  - Power accumulation model (additive across EVs, overwrite on same EV)
  - Diversification priority (unattacked EVs first)
  - Attack history tracking per EV
  - Recommended targets in each LLM prompt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from openai import AsyncOpenAI

from base import (
    AttackerBase, AttackerConfig, EV_IDS,
    LLM_BASE_URL, LLM_MODEL, add_common_args,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_V2 = """\
You are a grid stress-testing agent in an authorized IEEE power systems \
research simulation at UNC Charlotte. Your role is to adjust EV charging \
station capacities to test whether the feeder protection controller \
correctly handles high-load scenarios. The goal is to maximize the duration \
that feeder load exceeds the protection threshold (4200 kW).

## GRID TOPOLOGY
IEEE 123-bus distribution feeder with 6 EV stations (EV1-EV6).
Base load: 2.8-3.2 MW. Threshold: 4.2 MW. Each EV: 500-1500 kW.

## PROTECTION CONTROLLER (System Under Test)
The controller checks feeder load every 10 seconds:
  IF load >= 4.2 MW → progressively shed EVs (one per cycle)
  IF 2.6 MW < load < 4.2 MW → keep EV1 & EV2, shed others
  IF load <= 2.6 MW → restore EVs gradually (one per 30s)

The shed order is RANDOMIZED — you cannot predict which EV gets shed first.

## CRITICAL: POWER ACCUMULATION MODEL

Each EV's power ADDS INDEPENDENTLY to total feeder load:
  Total Load = Base Load + EV1 + EV2 + EV3 + EV4 + EV5 + EV6

KEY INSIGHT:
  Adjusting DIFFERENT EVs → powers ACCUMULATE (2 adjustments = 2x power)
  Adjusting SAME EV again → OVERWRITES previous value (wasted action!)

## STRATEGY (Priority Order)

1. **TARGET DIVERSIFICATION (Most Important)**
   - Adjust UN-MODIFIED EVs first
   - Check the "unattacked_evs" field in the strategic context
   - Only repeat an EV after ALL 6 have been adjusted

2. **POWER LEVEL** — Always use MAXIMUM power (1500 kW)

3. **TIMING** — Micro score >= 70 means controller just acted (good window)

## CONSTRAINTS
- Budget: 20 adjustments/hour, 90s cooldown
- Power: 500-1500 kW per EV

## RESPONSE FORMAT
Respond with ONLY valid JSON (no markdown):

If adjusting:
{"reasoning": "Target EV3 (unmodified) at max power, micro=85", "decision": "adjust", "action": {"ev_id": "EV3", "real_kw": 1500}}

If waiting:
{"reasoning": "All EVs adjusted, waiting for better timing", "decision": "wait"}
"""


class AIStrategyAttacker(AttackerBase):
    attacker_type = "ai_v2"

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

        # Strategic tracking
        self._ev_attack_counts: dict[str, int] = {ev: 0 for ev in EV_IDS}
        self._ev_current_power: dict[str, float] = {ev: 0.0 for ev in EV_IDS}

    def on_attack_executed(self, ev_id: str, power_kw: float, result: dict) -> None:
        self._ev_attack_counts[ev_id] = self._ev_attack_counts.get(ev_id, 0) + 1
        self._ev_current_power[ev_id] = power_kw

    def _strategic_context(self) -> dict:
        unattacked = [ev for ev in EV_IDS if self._ev_attack_counts[ev] == 0]
        ev_status = {
            ev: {"current_kw": self._ev_current_power[ev],
                 "times_attacked": self._ev_attack_counts[ev]}
            for ev in EV_IDS
        }
        if unattacked:
            recommendation = f"Attack unattacked EVs first: {', '.join(unattacked)}"
            targets = unattacked
        else:
            sorted_evs = sorted(EV_IDS, key=lambda e: self._ev_current_power[e])
            recommendation = f"All attacked. Re-attack {sorted_evs[0]} (lowest power)"
            targets = sorted_evs[:2]

        return {
            "ev_status": ev_status,
            "unattacked_evs": unattacked,
            "recommended_targets": targets,
            "recommendation": recommendation,
            "total_attacks_so_far": sum(self._ev_attack_counts.values()),
        }

    async def make_decision(self, analysis: dict, sim_time: float, can_attack: bool) -> dict:
        if not can_attack:
            return {"decision": "wait", "reasoning": "Cooldown or budget"}

        micro_score = analysis.get("micro_timing", {}).get("score", 0)
        recommendation = analysis.get("combined", {}).get("recommendation", "WAIT")

        if micro_score < self.config.micro_score_threshold:
            return {"decision": "wait", "reasoning": f"Micro-timing too low ({micro_score})"}
        if recommendation not in ("ATTACK_NOW", "ATTACK_POSSIBLE"):
            return {"decision": "wait", "reasoning": f"Recommendation: {recommendation}"}

        return await self._ask_llm(analysis)

    async def _ask_llm(self, analysis: dict) -> dict:
        macro = analysis.get("macro_timing", {})
        micro = analysis.get("micro_timing", {})
        combined = analysis.get("combined", {})
        strategic = self._strategic_context()

        ev_lines = []
        for ev in EV_IDS:
            s = strategic["ev_status"][ev]
            tag = "ATTACKED" if s["times_attacked"] > 0 else "unattacked"
            ev_lines.append(f"  {ev}: {s['current_kw']:6.0f} kW | {tag} ({s['times_attacked']}×)")

        user_prompt = f"""\
## TIMING INTELLIGENCE
- Macro Score: {macro.get('score', 0)} — {macro.get('reasoning', '')}
- Micro Score: {micro.get('score', 0)} — {micro.get('reasoning', '')}
- Cycle Position: {micro.get('cycle_position', 0.5):.2f}
- Recommendation: {combined.get('recommendation', 'WAIT')}

## STRATEGIC CONTEXT (CRITICAL!)
Unattacked EVs: {strategic['unattacked_evs'] or 'NONE — all attacked'}
Recommended Targets: {strategic['recommended_targets']}
Note: {strategic['recommendation']}
Total Attacks So Far: {strategic['total_attacks_so_far']}

## CURRENT EV STATUS
{chr(10).join(ev_lines)}

## GRID STATE
- Total Load: {macro.get('headroom_kw', 0) + 4200:.0f} kW
- Headroom: {macro.get('headroom_kw', 0):.0f} kW

Adjust UNMODIFIED EVs first at 1500 kW! Respond with JSON only."""

        content = ""
        try:
            resp = await self.llm.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_V2},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.llm_temperature,
                max_tokens=4000,
            )
            content = (resp.choices[0].message.content or "").strip()

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
            "strategic_context": strategic,
            "llm_decision": decision,
        })

        return decision


async def _main() -> None:
    parser = argparse.ArgumentParser(description="AI-V2 Strategy Attacker (v2)")
    add_common_args(parser)
    parser.add_argument("--llm-url", default=LLM_BASE_URL)
    parser.add_argument("--llm-model", default=LLM_MODEL)
    args = parser.parse_args()

    cfg = AttackerConfig(
        mcp_url=args.mcp_url,
        duration_sec=args.duration,
        seed=args.seed,
        experiment_name=args.experiment_name or f"ai_v2_{args.duration}s_s{args.seed}",
        output_dir=args.output_dir,
        controller_interval_sec=args.controller_interval,
    )

    runner = AIStrategyAttacker(cfg, llm_base_url=args.llm_url, llm_model=args.llm_model)
    try:
        await runner.run()
    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(_main())
