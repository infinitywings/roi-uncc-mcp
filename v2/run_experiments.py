#!/usr/bin/env python3
"""
LLM-GridEval v2 — Experiment Runner

Orchestrates the full experiment matrix:
  Phase 1: baseline validation (no attacks, 5 min)
  Phase 2: 9 short runs (3 variants × 3 seeds × 300 s)
  Phase 3: 9 long runs  (3 variants × 3 seeds × 3600 s)

Usage:
  # Run all phases
  python v2/run_experiments.py --phase all

  # Run only Phase 2
  python v2/run_experiments.py --phase phase2

  # Run a single variant/seed
  python v2/run_experiments.py --phase phase2 --variant ai_v2 --seed 1
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRIPTS = {
    "random": "v2/attackers/random_baseline.py",
    "ai_v1": "v2/attackers/ai_v1_timing.py",
    "ai_v2": "v2/attackers/ai_v2_strategy.py",
}

VARIANTS = list(SCRIPTS.keys())
SEEDS = [1, 2, 3]


@dataclass
class ExperimentRun:
    phase: str
    variant: str
    seed: int
    duration_sec: int
    experiment_name: str


def build_matrix(phase: str, variant: str | None = None, seed: int | None = None) -> list[ExperimentRun]:
    runs: list[ExperimentRun] = []

    def add(p: str, v: str, s: int, dur: int, label: str):
        if variant and v != variant:
            return
        if seed is not None and s != seed:
            return
        runs.append(ExperimentRun(p, v, s, dur, label))

    if phase in ("phase1", "all"):
        runs.append(ExperimentRun("phase1", "baseline", 0, 300, "baseline_5m"))

    if phase in ("phase2", "all"):
        for v in VARIANTS:
            for s in SEEDS:
                add("phase2", v, s, 300, f"{v}_5m_s{s}")

    if phase in ("phase3", "all"):
        for v in VARIANTS:
            for s in SEEDS:
                add("phase3", v, s, 3600, f"{v}_1h_s{s}")

    return runs


async def wait_for_health(mcp_url: str, timeout: int = 120) -> bool:
    logger.info("Waiting for MCP server at %s ...", mcp_url)
    async with httpx.AsyncClient(timeout=10) as client:
        for _ in range(timeout // 2):
            try:
                r = await client.get(f"{mcp_url}/health")
                if r.status_code == 200:
                    logger.info("MCP server healthy")
                    return True
            except httpx.ConnectError:
                pass
            await asyncio.sleep(2)
    logger.error("MCP server not reachable after %ds", timeout)
    return False


async def cooldown(mcp_url: str, duration_sec: int = 60) -> None:
    """Advance simulation time without attacking to let controller restore EVs."""
    logger.info("Cooldown: observing for %ds to let controller settle ...", duration_sec)
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(0, duration_sec, 5):
            try:
                await client.post(f"{mcp_url}/tools/observe", json={})
            except Exception:
                pass
            await asyncio.sleep(0.1)


def run_baseline(mcp_url: str, duration_sec: int, output_dir: str, name: str) -> int:
    """Baseline: just observe, no attacks.  Returns 0 on success."""
    # We do this inline — no attacker script needed
    import json
    from datetime import datetime

    async def _baseline():
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(f"{mcp_url}/experiment/start", json={"experiment_id": name})

            elapsed = 0.0
            obs = 0
            while elapsed < duration_sec:
                obs += 1
                await client.post(f"{mcp_url}/tools/observe", json={})
                await asyncio.sleep(5)
                elapsed += 5

            end = await client.post(f"{mcp_url}/experiment/end", json={})
            metrics = end.json().get("final_metrics", {})
            tvd = metrics.get("primary_metrics", {}).get("tvd_sec", 0)

            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{name}.json").write_text(json.dumps({
                "attacker_type": "baseline",
                "config": {"experiment_name": name, "duration_sec": duration_sec},
                "total_observations": obs,
                "total_attacks": 0,
                "final_metrics": metrics,
                "attack_log": [],
            }, indent=2))

            logger.info("Baseline complete: TVD=%.1fs (should be 0)", tvd)
            return 0 if tvd == 0 else 1

    return asyncio.run(_baseline())


def run_attacker(run: ExperimentRun, mcp_url: str, base_output: str) -> int:
    """Launch an attacker script as a subprocess.  Returns exit code."""
    script = SCRIPTS.get(run.variant)
    if not script:
        logger.error("Unknown variant: %s", run.variant)
        return 1

    output_dir = f"{base_output}/{run.phase}"
    cmd = [
        sys.executable, script,
        "--mcp-url", mcp_url,
        "--duration", str(run.duration_sec),
        "--seed", str(run.seed),
        "--experiment-name", run.experiment_name,
        "--output-dir", output_dir,
    ]

    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd)
    return result.returncode


async def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-GridEval v2 Experiment Runner")
    parser.add_argument("--phase", default="all", choices=["phase1", "phase2", "phase3", "all"])
    parser.add_argument("--variant", default=None, choices=VARIANTS)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--mcp-url", default="http://localhost:5100")
    parser.add_argument("--output-dir", default="v2/results")
    parser.add_argument("--cooldown-sec", type=int, default=60)
    args = parser.parse_args()

    # Wait for federation
    if not await wait_for_health(args.mcp_url):
        sys.exit(1)

    runs = build_matrix(args.phase, args.variant, args.seed)
    logger.info("Experiment matrix: %d runs", len(runs))
    for r in runs:
        logger.info("  %s / %s / seed=%d / %ds", r.phase, r.variant, r.seed, r.duration_sec)

    total = len(runs)
    passed = 0
    failed = 0

    for i, run in enumerate(runs, 1):
        logger.info("=" * 60)
        logger.info("Run %d/%d: %s", i, total, run.experiment_name)
        logger.info("=" * 60)

        if run.variant == "baseline":
            rc = run_baseline(args.mcp_url, run.duration_sec,
                              f"{args.output_dir}/{run.phase}", run.experiment_name)
        else:
            rc = run_attacker(run, args.mcp_url, args.output_dir)

        if rc == 0:
            passed += 1
            logger.info("✓ %s completed successfully", run.experiment_name)
        else:
            failed += 1
            logger.error("✗ %s failed (exit code %d)", run.experiment_name, rc)

        # Cooldown between runs (skip after last)
        if i < total:
            await cooldown(args.mcp_url, args.cooldown_sec)

    logger.info("=" * 60)
    logger.info("COMPLETE: %d/%d passed, %d failed", passed, total, failed)
    logger.info("Results in: %s/", args.output_dir)
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
