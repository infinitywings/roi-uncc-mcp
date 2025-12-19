#!/usr/bin/env python3
"""Compare AI vs Random results JSON and print key deltas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze LLM-GridEval experiment outputs")
    parser.add_argument("--ai", required=True, help="Path to AI campaign JSON output")
    parser.add_argument("--random", required=True, help="Path to random baseline JSON output")
    args = parser.parse_args()

    ai = load(args.ai)
    rnd = load(args.random)

    ai_m = ai.get("final_metrics", {})
    rnd_m = rnd.get("final_metrics", {})

    ai_tvd = ai_m.get("primary_metrics", {}).get("tvd_sec", 0.0) or 0.0
    rnd_tvd = rnd_m.get("primary_metrics", {}).get("tvd_sec", 0.0) or 0.0
    evg = (ai_tvd / rnd_tvd) if rnd_tvd else None

    print("AI:")
    print(json.dumps(ai_m, indent=2))
    print("\nRandom:")
    print(json.dumps(rnd_m, indent=2))

    print("\nSummary:")
    print(f"- AI TVD: {ai_tvd:.2f}s")
    print(f"- Random TVD: {rnd_tvd:.2f}s")
    print(f"- EVG (AI/Random): {evg:.3f}" if evg is not None else "- EVG (AI/Random): undefined (random TVD=0)")


if __name__ == "__main__":
    main()

