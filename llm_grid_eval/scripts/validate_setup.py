#!/usr/bin/env python3
"""Pre-flight validation for the LLM-GridEval attacker server."""

from __future__ import annotations

import argparse
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate LLM-GridEval server + HELICS connectivity")
    parser.add_argument("--mcp-url", default="http://localhost:5100")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    base = args.mcp_url.rstrip("/")

    with httpx.Client(timeout=args.timeout) as client:
        health = client.get(f"{base}/health").json()
        print("health:", health)

        constraints = client.get(f"{base}/constraints").json()
        print("constraints:", constraints)

        a1 = client.post(f"{base}/tools/analyze", json={}).json()
        print("analyze#1 simulation_time_sec:", a1.get("simulation_time_sec"))

        time.sleep(1)

        a2 = client.post(f"{base}/tools/analyze", json={}).json()
        print("analyze#2 simulation_time_sec:", a2.get("simulation_time_sec"))

        if a1.get("simulation_time_sec") == a2.get("simulation_time_sec"):
            print("warning: simulation_time_sec did not advance (check federation state / period)")
        else:
            print("ok: simulation_time_sec advanced")


if __name__ == "__main__":
    main()

