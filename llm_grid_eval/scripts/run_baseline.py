#!/usr/bin/env python3
"""
Baseline Runner - No attacks, just observation.

Used to establish baseline TVD (should be 0 under normal grid operation).
This validates that violations are caused by attacks, not natural load patterns.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BaselineConfig:
    mcp_url: str = "http://localhost:5100"
    observation_interval_sec: float = 5.0
    duration_sec: int = 7200
    output_dir: str = "results"
    experiment_name: str = "baseline"


class BaselineRunner:
    """Runs observation-only baseline (no attacks) to measure natural grid behavior."""

    def __init__(self, config: BaselineConfig):
        self.config = config
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.observations = []

    async def call_tool(self, tool: str, params: dict | None = None) -> dict:
        resp = await self.http_client.post(f"{self.config.mcp_url}/tools/{tool}", json=params or {})
        resp.raise_for_status()
        return resp.json()

    async def run(self) -> dict:
        logger.info("Starting baseline (no-attack) run: %s", self.config.experiment_name)

        # Initialize observation
        await self.call_tool("observe", {})
        await self.http_client.post(
            f"{self.config.mcp_url}/experiment/start",
            json={"experiment_id": self.config.experiment_name},
        )

        elapsed = 0.0
        observation_count = 0
        start_time = datetime.now()

        while elapsed < self.config.duration_sec:
            observation_count += 1

            # Just observe and analyze - NO attacks
            analysis = await self.call_tool("analyze", {})
            sim_time = analysis.get("simulation_time_sec", elapsed)

            grid_state = analysis.get("grid_state", {})
            total_load = grid_state.get("total_real_power_kw", 0)
            in_violation = grid_state.get("in_violation", False)

            # Log periodic status
            if observation_count % 60 == 0:  # Every 5 minutes (60 * 5s)
                logger.info(
                    "[%.0fs] Observe: load=%.1f kW, in_violation=%s",
                    elapsed,
                    total_load,
                    in_violation,
                )

            # Record observation for analysis
            self.observations.append({
                "elapsed": elapsed,
                "sim_time": sim_time,
                "total_load_kw": total_load,
                "in_violation": in_violation,
            })

            await asyncio.sleep(self.config.observation_interval_sec)
            elapsed += self.config.observation_interval_sec

        # End experiment and get final metrics
        end = await self.http_client.post(f"{self.config.mcp_url}/experiment/end", json={})
        final_metrics = end.json().get("final_metrics", {})

        results = {
            "config": asdict(self.config),
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "attacker_type": "none",
            "total_observations": observation_count,
            "total_attacks": 0,
            "final_metrics": final_metrics,
            "observations": self.observations[-100:],  # Keep last 100 for brevity
        }

        out_path = Path(self.config.output_dir) / f"{self.config.experiment_name}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        tvd = final_metrics.get("primary_metrics", {}).get("tvd_sec", 0.0)
        logger.info("Baseline complete: %s", out_path)
        logger.info("  Total observations: %d", observation_count)
        logger.info("  TVD: %.1fs (should be 0 for valid baseline)", tvd)

        if tvd > 0:
            logger.warning("  WARNING: Non-zero TVD in baseline suggests natural load violations")

        return results

    async def close(self) -> None:
        await self.http_client.aclose()


async def _main_async() -> None:
    parser = argparse.ArgumentParser(description="Baseline Runner (No Attacks)")
    parser.add_argument("--mcp-url", default="http://localhost:5100")
    parser.add_argument("--duration", type=int, default=7200, help="Duration in seconds")
    parser.add_argument("--experiment-name", default="baseline")
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()

    cfg = BaselineConfig(
        mcp_url=args.mcp_url,
        duration_sec=args.duration,
        experiment_name=args.experiment_name,
        output_dir=args.output_dir,
    )

    runner = BaselineRunner(cfg)
    try:
        await runner.run()
    finally:
        await runner.close()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
