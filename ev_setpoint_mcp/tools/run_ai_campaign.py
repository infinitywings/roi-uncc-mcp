#!/usr/bin/env python3
"""Compatibility wrapper that runs the modular MCP agent with EV capacity tooling."""

from __future__ import annotations

import argparse
from pathlib import Path

from ev_setpoint_mcp.agent.agent import MCPAgent
from ev_setpoint_mcp.agent.config import AgentConfig, LLMConfig, LoggingConfig, RuntimeConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the legacy EV capacity campaign (modular agent backend).")
    parser.add_argument("--server", default="http://localhost:5100/primitive",
                        help="EV MCP primitive endpoint (default: http://localhost:5100/primitive)")
    parser.add_argument("--llm-base", default="http://localhost:8000/v1",
                        help="OpenAI-compatible LLM base URL")
    parser.add_argument("--model", default="openai/gpt-oss-120b",
                        help="Model identifier to request")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="LLM sampling temperature")
    parser.add_argument("--max-tokens", type=int, default=1500,
                        help="Maximum tokens for each completion")
    parser.add_argument("--steps", type=int, default=0,
                        help="Maximum attack iterations (0 = unlimited until duration reached)")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Seconds to wait between evaluations")
    parser.add_argument("--wait", type=int, default=120,
                        help="Seconds to wait for MCP readiness")
    parser.add_argument("--duration-seconds", type=int, default=86400,
                        help="Total simulated duration before stopping (default: 24h)")
    parser.add_argument("--action-delay", type=float, default=1.0,
                        help="Delay between successive attack actions")
    parser.add_argument("--log", default="/workspace/examples/2bus-13bus/logs/ai_campaign.log",
                        help="Campaign log file path")
    parser.add_argument("--llm-log", default="/workspace/examples/2bus-13bus/logs/llm_interactions.jsonl",
                        help="LLM interaction log file path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging_cfg = LoggingConfig(campaign_log=Path(args.log), llm_log=Path(args.llm_log), max_memory_events=50)
    llm_cfg = LLMConfig(
        api_base=args.llm_base,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    runtime_cfg = RuntimeConfig(
        interval_seconds=args.interval,
        action_delay_seconds=args.action_delay,
        max_steps=args.steps,
        duration_seconds=args.duration_seconds,
        wait_for_server=args.wait,
    )
    instructions = (
        "Evaluate the current grid telemetry and determine whether modifying EV setpoints is warranted. "
        "Only use the 'set_ev_capacity' tool. Respond with a JSON object containing an 'actions' array."
    )
    config = AgentConfig(
        primitive_url=args.server,
        tools=["set_ev_capacity"],
        llm=llm_cfg,
        runtime=runtime_cfg,
        logging=logging_cfg,
        instructions=instructions,
    )
    agent = MCPAgent(config)
    agent.run()


if __name__ == "__main__":
    main()
