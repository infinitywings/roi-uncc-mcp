#!/usr/bin/env python3
"""CLI entrypoint for the modular MCP agent."""

from __future__ import annotations

import argparse
from pathlib import Path

from ev_setpoint_mcp.agent.agent import MCPAgent
from ev_setpoint_mcp.agent.config import AgentConfig, LLMConfig, LoggingConfig, RuntimeConfig


def build_config(args: argparse.Namespace) -> AgentConfig:
    logging_cfg = None
    if args.log or args.llm_log:
        logging_cfg = LoggingConfig(
            campaign_log=Path(args.log).resolve(),
            llm_log=Path(args.llm_log).resolve(),
            max_memory_events=args.max_memory_events,
        )

    llm_cfg = LLMConfig(
        api_base=args.llm_base,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        request_timeout=args.llm_timeout,
    )

    runtime_cfg = RuntimeConfig(
        interval_seconds=args.interval,
        action_delay_seconds=args.action_delay,
        max_steps=args.steps,
        duration_seconds=args.duration_seconds,
        wait_for_server=args.wait,
    )

    instructions = args.instructions
    if args.instructions_file:
        instructions = Path(args.instructions_file).read_text(encoding="utf-8")

    return AgentConfig(
        primitive_url=args.server,
        tools=args.tools,
        llm=llm_cfg,
        runtime=runtime_cfg,
        logging=logging_cfg,
        enable_auto_observation=not args.disable_auto_observe,
        topology_refresh_seconds=args.topology_refresh,
        instructions=instructions,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the modular MCP attack agent.")
    parser.add_argument("--server", default="http://localhost:5100/primitive", help="MCP primitive endpoint URL")
    parser.add_argument("--llm-base", default="http://localhost:8000/v1", help="LLM API base URL")
    parser.add_argument("--model", default="openai/gpt-oss-120b", help="LLM model identifier")
    parser.add_argument("--temperature", type=float, default=0.7, help="LLM sampling temperature")
    parser.add_argument("--max-tokens", type=int, default=1500, help="Maximum tokens from the LLM response")
    parser.add_argument("--llm-timeout", type=int, default=120, help="Timeout for LLM requests (seconds)")
    parser.add_argument("--steps", type=int, default=0, help="Maximum agent iterations (0 = unlimited)")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds to wait between agent iterations")
    parser.add_argument("--action-delay", type=float, default=1.0, help="Delay between consecutive tool executions")
    parser.add_argument("--wait", type=int, default=120, help="Seconds to wait for MCP readiness")
    parser.add_argument("--duration-seconds", type=int, default=86_400, help="Simulated duration before stopping")
    parser.add_argument("--log", default="/workspace/examples/2bus-13bus/logs/ai_campaign.log", help="Campaign log path")
    parser.add_argument("--llm-log", default="/workspace/examples/2bus-13bus/logs/llm_interactions.jsonl",
                        help="LLM interaction log path")
    parser.add_argument("--max-memory-events", type=int, default=50, help="Maximum events stored in agent memory")
    parser.add_argument("--tools", nargs="*", default=["discover_topology", "monitor_protection_systems",
                                                       "analyze_power_flow", "set_ev_capacity"],
                        help="Subset of tools to advertise to the LLM")
    parser.add_argument("--disable-auto-observe", action="store_true",
                        help="Disable automatic grid observation between steps")
    parser.add_argument("--topology-refresh", type=int, default=None,
                        help="Seconds between topology refreshes (default: cache indefinitely)")
    parser.add_argument("--instructions", default="Decide which tools to invoke next. You may choose multiple tools per turn.",
                        help="Instruction text appended to the user prompt")
    parser.add_argument("--instructions-file", help="Path to a file containing the instructions text")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = build_config(args)
    agent = MCPAgent(config)
    agent.run()


if __name__ == "__main__":
    main()
