# Research Overview

The ROI UNCC MCP project investigates how large language models can plan coordinated cyber attacks on simulated power grids and how those AI-driven campaigns compare against randomly generated attacks.

## Research Goals
- Explore the effectiveness of AI-planned attack sequences versus stochastic baselines
- Provide a safe environment for studying cyber-physical vulnerabilities in electric grids
- Generate reproducible metrics for impact and resilience

## Proposed Approach
1. Use **GridLAB-D** and **GridPACK** federated through **HELICS** to simulate distribution and transmission systems.
2. Expose a RESTful **MCP server** that accepts high level attack plans from an LLM strategist.
3. Implement attack primitives (data spoofing, load injection, reconnaissance, command blocking) with built‑in safety limits.
4. Measure grid impact to evaluate how well the AI strategy performs against a random baseline.

## Random vs AI Comparison
The configuration file [`config/random_vs_ai_demo.yaml`](../config/random_vs_ai_demo.yaml) runs a side‑by‑side campaign where the same grid scenario is executed once with AI planning and once with random actions. The resulting metrics highlight efficiency differences between the two approaches.

## Safety and Ethics
- Runs only in a simulated environment; it cannot connect to real infrastructure.
- Intended solely for defensive cybersecurity research.
- Researchers are responsible for responsible disclosure of findings.

