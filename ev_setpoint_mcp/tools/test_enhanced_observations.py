#!/usr/bin/env python3
"""Quick test to verify enhanced observation service fields."""

import json
import sys

import requests


def test_observations() -> int:
    url = "http://localhost:5100/primitive"
    print("Testing enhanced observation service...")

    resp = requests.post(url, json={"method": "get_grid_status", "params": {}})
    data = resp.json()
    result = data.get("result", {})

    checks = [
        ("defender_timing", result.get("defender_timing")),
        ("load_patterns", result.get("load_patterns")),
        ("attack_opportunity", result.get("attack_opportunity")),
    ]

    all_pass = True
    for name, value in checks:
        if value:
            print(f"✓ {name}: present")
            snippet = json.dumps(value, indent=2)
            print(f"  {snippet[:200]}{'...' if len(snippet) > 200 else ''}")
        else:
            print(f"✗ {name}: MISSING")
            all_pass = False

    opp = result.get("attack_opportunity", {})
    if opp.get("recommendation"):
        print(f"\n→ Attack recommendation: {opp['recommendation']}")
        print(f"  Reasoning: {opp.get('reasoning', 'N/A')}")
        print(f"  Combined score: {opp.get('combined_score', 'N/A')}")

    if all_pass:
        print("\n✓ All enhanced observation fields present!")
        return 0
    print("\n✗ Some fields missing - check observation_service.py")
    return 1


if __name__ == "__main__":
    sys.exit(test_observations())
